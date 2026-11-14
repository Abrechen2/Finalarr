"""Dashboard: airing seasons, upcoming finales, recent reports (PLAN.md 16.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import Blueprint
from flask.typing import ResponseReturnValue
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from finalarr.api.common import database
from finalarr.api.events import event_view
from finalarr.api.series import counted
from finalarr.db.models import Channel, Delivery, Episode, Event, Season, Series, SonarrInstance

bp = Blueprint("dashboard", __name__, url_prefix="/api/v1")
RECENT_EVENTS = 10
ACTIVE_STATES = ("scheduled", "airing", "aired")


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _finale(episodes: list[Episode]) -> Episode | None:
    explicit = [e for e in episodes if e.finale_type in ("season", "series")]
    dated = [e for e in episodes if e.air_date_utc is not None]
    if explicit:
        return explicit[0]
    return max(dated, key=lambda e: (_aware(e.air_date_utc), e.number)) if dated else None


def _season_card(series: Series, season: Season, now: datetime) -> dict[str, Any] | None:
    episodes = counted(series, season)
    upcoming = sorted(
        (a, e.number) for e in episodes if (a := _aware(e.air_date_utc)) is not None and a > now
    )
    finale = _finale(episodes)
    finale_at = _aware(finale.air_date_utc) if finale else None
    return {
        "series_id": series.id,
        "season_id": season.id,
        "title": series.title,
        "poster_url": series.poster_url,
        "season": season.number,
        "state": season.state,
        "have": sum(1 for e in episodes if e.has_file),
        "expected": season.expected_count,
        "disputed": season.disputed,
        "next_air_date": upcoming[0][0].isoformat() if upcoming else None,
        "next_episode": upcoming[0][1] if upcoming else None,
        "finale_episode": finale.number if finale and finale_at and finale_at > now else None,
        "finale_air_date": finale_at.isoformat() if finale_at and finale_at > now else None,
    }


@bp.get("/dashboard")
def dashboard() -> ResponseReturnValue:
    now = datetime.now(UTC)
    with database().session() as s:
        followed = s.scalars(
            select(Series)
            .where(Series.followed.is_(True))
            .options(selectinload(Series.seasons).selectinload(Season.episodes))
        ).all()
        cards = [
            card
            for series in followed
            for season in series.seasons
            if season.number > 0 and season.state in ACTIVE_STATES
            if (card := _season_card(series, season, now)) is not None
        ]
        recent = s.scalars(
            select(Event)
            .options(selectinload(Event.deliveries).selectinload(Delivery.channel))
            .order_by(Event.id.desc())
            .limit(RECENT_EVENTS)
        ).all()
        onboarding = {
            "instance": bool(s.scalar(select(exists().where(SonarrInstance.id.is_not(None))))),
            "followed": bool(followed),
            "channel": bool(s.scalar(select(exists().where(Channel.id.is_not(None))))),
        }
        airing = sorted(
            # Only seasons still airing: old seasons with missing files are library
            # gaps, not news, and would bury the few that matter.
            (c for c in cards if c["state"] == "airing"),
            key=lambda c: (c["next_air_date"] or "9999", c["title"]),
        )
        finales = sorted(
            (c for c in cards if c["finale_air_date"]),
            key=lambda c: c["finale_air_date"],
        )
        return {
            "airing": airing,
            "upcoming_finales": [
                {**c, "episode": c["finale_episode"], "air_date": c["finale_air_date"]}
                for c in finales
            ],
            "recent_events": [event_view(e) for e in recent],
            "onboarding": onboarding,
        }
