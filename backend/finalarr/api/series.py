"""Series list/detail and follow switches (PLAN.md section 7, 16.3)."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.orm import Session, object_session, selectinload

from finalarr.api.common import ApiProblem, database, not_found, parse_body
from finalarr.db.models import AnilistMapping, Episode, Season, Series, SonarrInstance
from finalarr.services.reconcile_queue import enqueue
from finalarr.services.series_extras import series_extras
from finalarr.services.series_news import series_news
from finalarr.services.settings_store import load_settings
from finalarr.sources.feeds import fetch_feed

bp = Blueprint("series", __name__, url_prefix="/api/v1/series")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
TYPE_FILTERS = {"anime": ("anime",), "standard": ("standard", "daily")}


class SeriesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    followed: bool | None = None
    include_specials: bool | None = None
    respect_monitoring: bool | None = None
    calendar: bool | None = None


class FollowMonitored(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: int | None = None
    tag: str | None = Field(default=None, min_length=1, max_length=100)


def counted(series: Series, season: Season) -> list[Episode]:
    return [e for e in season.episodes if e.monitored or not series.respect_monitoring]


def season_summary(series: Series, season: Season) -> dict[str, Any]:
    return {
        "id": season.id,
        "number": season.number,
        "state": season.state,
        "expected": season.expected_count,
        "have": sum(1 for e in counted(series, season) if e.has_file),
        "disputed": season.disputed,
    }


def series_summary(series: Series) -> dict[str, Any]:
    return {
        "id": series.id,
        "instance_id": series.instance_id,
        "title": series.title,
        "year": series.year,
        "series_type": series.series_type,
        "status": series.status,
        "poster_url": series.poster_url,
        "monitored": series.monitored,
        "followed": series.followed,
        "include_specials": series.include_specials,
        "respect_monitoring": series.respect_monitoring,
        "calendar": series.calendar,
        "anilist_id": series.anilist_id,
        "anilist_resolution": series.anilist_resolution,
        "tags": json.loads(series.tags_json or "[]"),
        "seasons": [season_summary(series, s) for s in series.seasons],
    }


def episode_detail(episode: Episode) -> dict[str, Any]:
    return {
        "id": episode.id,
        "number": episode.number,
        "absolute_number": episode.absolute_number,
        "title": episode.title,
        "air_date": episode.air_date_utc.isoformat() if episode.air_date_utc else None,
        "monitored": episode.monitored,
        "has_file": episode.has_file,
        "finale_type": episode.finale_type,
        "delayed_from": episode.delayed_from.isoformat() if episode.delayed_from else None,
    }


def _anilist_by_season(series: Series) -> dict[int, tuple[list[int], bool]]:
    session = object_session(series)
    if session is None or series.tvdb_id is None or series.series_type != "anime":
        return {}
    rows = session.scalars(
        select(AnilistMapping).where(AnilistMapping.tvdb_id == series.tvdb_id)
    ).all()
    manual = {r.tvdb_season for r in rows if r.source == "manual"}
    result: dict[int, tuple[list[int], bool]] = {}
    for row in sorted(rows, key=lambda r: r.anilist_id):
        if row.tvdb_season in manual and row.source != "manual":
            continue
        ids, _ = result.setdefault(row.tvdb_season, ([], row.tvdb_season in manual))
        ids.append(row.anilist_id)
    return result


def series_detail(series: Series) -> dict[str, Any]:
    body = series_summary(series)
    anilist = _anilist_by_season(series)
    body["sonarr_url"] = f"{series.instance.url}/series/{series.title_slug}"
    body["details"] = {
        "overview": series.overview,
        "network": series.network,
        "runtime": series.runtime,
        "genres": json.loads(series.genres_json or "[]"),
        "fanart_url": series.fanart_url,
    }
    body["seasons"] = [
        {
            **season_summary(series, season),
            "expected_source": season.expected_source,
            "expected_override": season.expected_override,
            "anilist_count": season.anilist_count,
            "parts_mode": season.parts_mode,
            "anilist_ids": anilist.get(season.number, ([], False))[0],
            "anilist_pinned": anilist.get(season.number, ([], False))[1],
            "anilist_start": season.anilist_start.isoformat() if season.anilist_start else None,
            "monitored": season.monitored,
            "state_since": season.state_since.isoformat() if season.state_since else None,
            "episodes": [episode_detail(e) for e in season.episodes],
            "parts": [
                {
                    "index": p.part_index,
                    "from": p.episode_from,
                    "to": p.episode_to,
                    "title": p.title,
                }
                for p in season.parts
            ],
        }
        for season in series.seasons
    ]
    return body


def _encode_cursor(series: Series) -> str:
    raw = f"{series.sort_title}\x1f{series.id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        title, _, sid = base64.urlsafe_b64decode(cursor.encode()).decode().rpartition("\x1f")
        return title, int(sid)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise ApiProblem(400, "bad_request", "Invalid cursor") from None


def _filtered(query: Select[Series]) -> Select[Series]:
    args = request.args
    if args.get("followed") in ("true", "false"):
        query = query.where(Series.followed.is_(args["followed"] == "true"))
    if args.get("instance", "").isdigit():
        query = query.where(Series.instance_id == int(args["instance"]))
    if "type" in args:
        if args["type"] not in TYPE_FILTERS:
            raise ApiProblem(400, "bad_request", "type must be anime or standard")
        query = query.where(Series.series_type.in_(TYPE_FILTERS[args["type"]]))
    if args.get("q"):
        query = query.where(Series.title.icontains(args["q"].strip(), autoescape=True))
    return query


def _limit() -> int:
    raw = request.args.get("limit", str(DEFAULT_LIMIT))
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_LIMIT:
        raise ApiProblem(400, "bad_request", f"limit must be 1..{MAX_LIMIT}")
    return int(raw)


@bp.get("")
def list_series() -> ResponseReturnValue:
    limit = _limit()
    query = _filtered(
        select(Series)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
        .order_by(Series.sort_title, Series.id)
    )
    if request.args.get("cursor"):
        title, sid = _decode_cursor(request.args["cursor"])
        query = query.where(
            or_(Series.sort_title > title, and_(Series.sort_title == title, Series.id > sid))
        )
    with database().session() as s:
        rows = list(s.scalars(query.limit(limit + 1)))
        page = rows[:limit]
        return {
            "items": [series_summary(r) for r in page],
            "next_cursor": _encode_cursor(page[-1]) if len(rows) > limit else None,
        }


def _load(s: Session, series_id: int) -> Series:
    series = s.get(Series, series_id)
    if series is None:
        raise not_found("Series")
    return series


def _nudge(anilist: bool = False) -> None:
    keys = ["finalarr.nudge", "finalarr.nudge_anilist"] if anilist else ["finalarr.nudge"]
    for key in keys:
        nudge = current_app.extensions.get(key)
        if nudge:
            nudge()


@bp.get("/tags")
def list_tags() -> ResponseReturnValue:
    with database().session() as s:
        labels = {label for raw in s.scalars(select(Series.tags_json)) for label in json.loads(raw)}
    return sorted(labels)


@bp.get("/<int:series_id>/news")
def get_series_news(series_id: int) -> ResponseReturnValue:
    language = request.args.get("lang", "de")
    if language not in ("de", "en"):
        raise ApiProblem(400, "bad_request", "lang must be de or en")
    with database().session() as s:
        series = _load(s, series_id)
        return series_news(
            s,
            series,
            language,
            current_app.extensions["finalarr.json_cache"],
            fetch=current_app.extensions.get("finalarr.news_fetch", fetch_feed),
            web=bool(load_settings(s)["series_news_web"]),
        )


@bp.get("/<int:series_id>/extras")
def get_series_extras(series_id: int) -> ResponseReturnValue:
    with database().session() as s:
        return series_extras(
            s, _load(s, series_id), current_app.extensions["finalarr.extras"], datetime.now(UTC)
        )


@bp.get("/<int:series_id>")
def get_series(series_id: int) -> ResponseReturnValue:
    with database().session() as s:
        return series_detail(_load(s, series_id))


@bp.patch("/<int:series_id>")
def patch_series(series_id: int) -> ResponseReturnValue:
    body = parse_body(SeriesPatch)
    with database().session() as s:
        series = _load(s, series_id)
        newly_followed = body.followed is True and not series.followed
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(series, field, value)
        if (
            newly_followed
            or body.include_specials is not None
            or body.respect_monitoring is not None
        ):
            enqueue(s, series.instance_id, series.sonarr_id)
        s.commit()
        result = series_detail(series)
    _nudge(anilist=newly_followed)
    return result


@bp.post("/follow-monitored")
def follow_monitored() -> ResponseReturnValue:
    body = parse_body(FollowMonitored)
    with database().session() as s:
        query = update(Series).where(Series.monitored.is_(True), Series.followed.is_(False))
        if body.instance_id is not None:
            query = query.where(Series.instance_id == body.instance_id)
        if body.tag is not None:
            # tags_json is a JSON list of labels; match the quoted label exactly.
            query = query.where(Series.tags_json.contains(json.dumps(body.tag), autoescape=True))
        changed = s.execute(query.values(followed=True)).rowcount  # type: ignore[attr-defined]
        instances = select(SonarrInstance.id).where(SonarrInstance.enabled.is_(True))
        if body.instance_id is not None:
            instances = instances.where(SonarrInstance.id == body.instance_id)
        for instance_id in s.scalars(instances):
            enqueue(s, instance_id)
        s.commit()
    _nudge(anilist=True)
    return {"followed": changed}
