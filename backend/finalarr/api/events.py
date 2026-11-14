"""Event log and season evaluation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from finalarr.api.common import ApiProblem, database, not_found
from finalarr.core.evaluator import evaluate
from finalarr.db.models import EVENT_TYPES, Delivery, Event, Season, utcnow
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.reconciler import season_input, season_memory, series_initialized
from finalarr.services.settings_store import load_settings, policy_from

bp = Blueprint("events", __name__, url_prefix="/api/v1")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def delivery_view(delivery: Delivery) -> dict[str, Any]:
    return {
        "id": delivery.id,
        "channel_id": delivery.channel_id,
        "channel_name": delivery.channel.name,
        "status": delivery.status,
        "attempts": delivery.attempts,
        "last_error": delivery.last_error,
        "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
    }


def event_view(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "created_at": event.created_at.isoformat(),
        "series_id": event.series_id,
        "season_id": event.season_id,
        "fingerprint": event.fingerprint,
        "payload": json.loads(event.payload_json),
        "deliveries": [delivery_view(d) for d in event.deliveries],
    }


def _int_arg(name: str, default: int | None = None, maximum: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    if not raw.isdigit() or int(raw) < 1 or (maximum and int(raw) > maximum):
        raise ApiProblem(400, "bad_request", f"{name} must be a positive number")
    return int(raw)


def _filtered(query: Select[Event]) -> Select[Event]:
    args = request.args
    if "type" in args:
        if args["type"] not in EVENT_TYPES:
            raise ApiProblem(400, "bad_request", "Unknown event type")
        query = query.where(Event.type == args["type"])
    series = _int_arg("series")
    if series:
        query = query.where(Event.series_id == series)
    if args.get("q"):
        query = query.where(Event.payload_json.icontains(args["q"].strip(), autoescape=True))
    if "since" in args:
        try:
            since = datetime.fromisoformat(args["since"].replace("Z", "+00:00"))
        except ValueError:
            raise ApiProblem(400, "bad_request", "since must be an ISO timestamp") from None
        query = query.where(Event.created_at >= since)
    cursor = _int_arg("cursor")
    if cursor:
        query = query.where(Event.id < cursor)
    return query


@bp.get("/events")
def list_events() -> ResponseReturnValue:
    limit = _int_arg("limit", DEFAULT_LIMIT, MAX_LIMIT) or DEFAULT_LIMIT
    query = _filtered(
        select(Event)
        .options(selectinload(Event.deliveries).selectinload(Delivery.channel))
        .order_by(Event.id.desc())
    )
    with database().session() as s:
        rows = list(s.scalars(query.limit(limit + 1)))
        page = rows[:limit]
        return {
            "items": [event_view(e) for e in page],
            "next_cursor": str(page[-1].id) if len(rows) > limit else None,
        }


@bp.post("/seasons/<int:season_id>/evaluate")
def evaluate_season(season_id: int) -> ResponseReturnValue:
    """``?dry_run=true`` evaluates stored data and changes nothing; otherwise a
    fresh reconcile of the series is queued."""
    with database().session() as s:
        season = s.get(Season, season_id)
        if season is None:
            raise not_found("Season")
        series = season.series
        if request.args.get("dry_run") != "true":
            enqueue(s, series.instance_id, series.sonarr_id)
            s.commit()
            nudge = current_app.extensions.get("finalarr.nudge")
            if nudge:
                nudge()
            return {"queued": True}, 202
        result = evaluate(
            season_input(series, season),
            season_memory(season, series_initialized(series)),
            utcnow(),
            policy_from(load_settings(s)),
        )
        s.rollback()
        return {
            "dry_run": True,
            "state": result.memory.state,
            "expected": result.expected_count,
            "disputed": result.disputed,
            "events": [{"type": e.type, "payload": e.payload} for e in result.events],
        }
