"""What the user is waiting for, as one sentence per series (key + values for the UI).

Looks at the newest season with episodes and at announcements of later seasons or
sequels. The UI turns ``key`` into a DE/EN sentence.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.db import models as m

ANNOUNCEMENTS = ("season_announced", "sequel_announced")
# A sequel that started more than this long ago is not "announced" any more.
STARTED_GRACE = timedelta(days=14)


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _counted(series: m.Series, season: m.Season) -> list[m.Episode]:
    return [e for e in season.episodes if e.monitored or not series.respect_monitoring]


def _announcement(s: Session, series: m.Series, latest: int, today: date) -> dict[str, Any] | None:
    events = s.scalars(
        select(m.Event)
        .where(m.Event.series_id == series.id, m.Event.type.in_(ANNOUNCEMENTS))
        .order_by(m.Event.id.desc())
    )
    for event in events:
        payload = json.loads(event.payload_json)
        first_air = payload.get("first_air")
        start = date.fromisoformat(first_air[:10]) if first_air else None
        if event.type == "season_announced" and int(payload.get("season") or 0) <= latest:
            continue
        if start is not None and start < today - STARTED_GRACE:
            continue
        return {
            "key": "announced" if start else "renewed_open",
            "season": payload.get("season"),
            "sequel_title": payload.get("sequel_title"),
            "first_air": first_air,
        }
    return None


def _season_state(series: m.Series, season: m.Season, now: datetime) -> dict[str, Any] | None:
    episodes = _counted(series, season)
    have = sum(1 for e in episodes if e.has_file)
    missing = sum(
        1
        for e in episodes
        if not e.has_file and (aired := _utc(e.air_date_utc)) is not None and aired <= now
    )
    base = {"season": season.number, "have": have, "expected": season.expected_count}
    if season.state not in ("airing", "scheduled", "aired"):
        return None
    if season.disputed:
        return {"key": "disputed", **base, "anilist": season.anilist_count}
    if missing:
        return {"key": "missing", **base, "missing": missing}
    if season.state == "aired":
        return None
    if season.expected_count is None:
        return {"key": "count_unknown", **base}
    return {"key": season.state, **base}


def waiting_state(s: Session, series: m.Series, now: datetime) -> dict[str, Any]:
    if not series.followed:
        return {"key": "not_followed"}
    seasons = sorted(
        (x for x in series.seasons if x.number > 0 and x.episodes),
        key=lambda x: x.number,
    )
    latest = seasons[-1] if seasons else None
    if latest is not None and (state := _season_state(series, latest, now)) is not None:
        return state
    announced = _announcement(s, series, latest.number if latest else 0, now.date())
    if announced is not None:
        return announced
    if latest is not None and latest.state == "complete":
        key = "ended" if series.status == "ended" else "complete_no_sequel"
        return {"key": key, "season": latest.number}
    return {"key": "nothing_known"}
