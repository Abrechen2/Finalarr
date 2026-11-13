"""Calendar API and the subscribable iCal feed.

The feed follows the same rules as other token URLs (cf. the webhook): the
token in the path is the permission, every failure is the same 404 so nobody
can probe for tokens, answers are private (no shared cache), not indexed, and
sent without a Referer. Rotating the token or switching the feed off revokes
every existing subscription at once.
"""

from __future__ import annotations

import hmac
import json
import secrets
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from flask import Blueprint, Response, current_app, request
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from finalarr.api.common import ApiProblem, database, parse_body
from finalarr.db.models import Setting
from finalarr.errors import api_error
from finalarr.ratelimit import RateLimiter
from finalarr.services.calendar import CalendarOptions, build_entries, render_ics
from finalarr.services.settings_store import load_settings

bp = Blueprint("calendar", __name__)
FEED_SETTING = "calendar_feed_token"
TOKEN_BYTES = 32
MAX_RANGE_DAYS = 62
FEED_READS_PER_MINUTE = 30
FEED_HEADERS = {
    "Cache-Control": "private, max-age=300",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Referrer-Policy": "no-referrer",
    "Content-Disposition": 'inline; filename="finalarr.ics"',
}


class FeedSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


def options_from(values: dict[str, object]) -> CalendarOptions:
    return CalendarOptions(
        scope=values["calendar_scope"],  # type: ignore[arg-type]
        hide_downloaded=bool(values["calendar_hide_downloaded"]),
        announcements=bool(values["calendar_announcements"]),
    )


def _token(s: Session) -> str | None:
    row = s.get(Setting, FEED_SETTING)
    return json.loads(row.value_json) if row else None


def _feed_view(token: str | None) -> dict[str, object]:
    return {"enabled": token is not None, "path": f"/ical/{token}.ics" if token else None}


def _day(name: str) -> date:
    try:
        return date.fromisoformat(request.args[name])
    except (KeyError, ValueError):
        raise ApiProblem(400, "bad_request", f"{name} must be a date (YYYY-MM-DD)") from None


@bp.get("/api/v1/calendar")
def calendar_range() -> ResponseReturnValue:
    start, end = _day("start"), _day("end")
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise ApiProblem(400, "bad_request", f"end must be 0..{MAX_RANGE_DAYS} days after start")
    with database().session() as s:
        entries = build_entries(s, start, end, options_from(load_settings(s)))
    return {"entries": [{**asdict(e), "start": e.start.isoformat()} for e in entries]}


@bp.get("/api/v1/calendar/feed")
def feed_status() -> ResponseReturnValue:
    with database().session() as s:
        return _feed_view(_token(s))


@bp.put("/api/v1/calendar/feed")
def feed_switch() -> ResponseReturnValue:
    body = parse_body(FeedSwitch)
    with database().session() as s:
        token = _token(s)
        if body.enabled and token is None:
            token = secrets.token_hex(TOKEN_BYTES)
            s.merge(Setting(key=FEED_SETTING, value_json=json.dumps(token)))
        elif not body.enabled and token is not None:
            s.delete(s.get_one(Setting, FEED_SETTING))
            token = None
        s.commit()
        return _feed_view(token)


@bp.post("/api/v1/calendar/feed/rotate")
def feed_rotate() -> ResponseReturnValue:
    with database().session() as s:
        if _token(s) is None:
            raise ApiProblem(409, "feed_disabled", "Switch the calendar feed on first")
        token = secrets.token_hex(TOKEN_BYTES)
        s.merge(Setting(key=FEED_SETTING, value_json=json.dumps(token)))
        s.commit()
        return _feed_view(token)


@bp.get("/ical/<feed>")
def feed(feed: str) -> ResponseReturnValue:
    limiter: RateLimiter = current_app.extensions["finalarr.feed_limiter"]
    if not limiter.hit(request.remote_addr or "unknown"):
        return api_error(429, "rate_limited", "Too many calendar requests")
    token = feed.removesuffix(".ics") if feed.endswith(".ics") else ""
    settings = current_app.extensions["finalarr.settings"]
    with database().session() as s:
        stored = _token(s)
        if not token or stored is None or not hmac.compare_digest(token, stored):
            return api_error(404, "not_found", "Not found")
        values = load_settings(s)
        today = datetime.now(UTC).date()
        entries = build_entries(
            s,
            today - timedelta(days=int(values["calendar_days_back"])),
            today + timedelta(days=int(values["calendar_days_ahead"])),
            options_from(values),
        )
    language = request.args.get("lang") or settings.language
    body = render_ics(entries, language, settings.public_url)
    response = Response(body, content_type="text/calendar; charset=utf-8")
    response.headers.update(FEED_HEADERS)
    return response
