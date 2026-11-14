"""Where a season's episode count comes from: every source's number and the decision.

Only stored and cached data is read (AniList through its cache, TVmaze/TMDB/Trakt from
the season cache the announcement job fills); nothing here waits on a slow source.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.core.model import SEASON_FINALE_TYPES
from finalarr.db import models as m
from finalarr.services.season_sources import JsonCache
from finalarr.sources.anilist import AnilistError, AnilistMedia

SEASON_CACHES = {
    "tvmaze": "https://www.tvmaze.com/shows/{id}",
    "tmdb": "https://www.themoviedb.org/tv/{id}",
    "trakt": "https://trakt.tv/shows/{id}",
}


class _Anilist(Protocol):
    def media(self, ids: list[int]) -> dict[int, AnilistMedia]: ...


def _counted(series: m.Series, season: m.Season) -> list[m.Episode]:
    return [e for e in season.episodes if e.monitored or not series.respect_monitoring]


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _sonarr(series: m.Series, season: m.Season) -> dict[str, Any]:
    episodes = _counted(series, season)
    now = datetime.now(UTC)
    finale = next((e.number for e in episodes if e.finale_type in SEASON_FINALE_TYPES), None)
    return {
        "source": "sonarr",
        "count": len(episodes),
        "detail": {
            # Unmonitored episodes do not count while "respect monitoring" is on.
            "listed": len(season.episodes),
            "unmonitored": len(season.episodes) - len(episodes),
            "aired": sum(1 for e in episodes if (a := _aware(e.air_date_utc)) and a <= now),
            "on_disk": sum(1 for e in episodes if e.has_file),
            "finale": finale,
        },
        "url": f"{series.instance.url}/series/{series.title_slug}",
    }


def _anilist(
    s: Session, series: m.Series, season: m.Season, anilist: _Anilist
) -> dict[str, Any] | None:
    if series.tvdb_id is None:
        return None
    rows = s.scalars(
        select(m.AnilistMapping).where(
            m.AnilistMapping.tvdb_id == series.tvdb_id,
            m.AnilistMapping.tvdb_season == season.number,
        )
    ).all()
    manual = [r for r in rows if r.source == "manual"]
    ids = sorted({r.anilist_id for r in (manual or rows)})
    if not ids and season.anilist_count is None:
        return None
    try:
        found = anilist.media(ids) if ids else {}
    except AnilistError:
        found = {}
    return {
        "source": "anilist",
        "count": season.anilist_count,
        "entries": [
            {
                "id": i,
                "title": found[i].title if i in found else None,
                "episodes": found[i].episodes if i in found else None,
                "status": found[i].status if i in found else None,
                "url": f"https://anilist.co/anime/{i}",
            }
            for i in ids
        ],
        "parts": [
            {"index": p.part_index, "from": p.episode_from, "to": p.episode_to, "title": p.title}
            for p in sorted(season.parts, key=lambda p: p.part_index)
        ],
    }


def _cached_seasons(series: m.Series, season: m.Season, cache: JsonCache) -> list[dict[str, Any]]:
    found = []
    for name, url in SEASON_CACHES.items():
        hit, show_id = cache.get(f"{name}:show:{series.tvdb_id}")
        if not hit or show_id is None:
            continue
        hit, rows = cache.get(f"{name}:seasons:{show_id}")
        if not hit:
            continue
        count = next(
            (episodes for number, _start, episodes in rows if number == season.number), None
        )
        if count:
            found.append({"source": name, "count": count, "url": url.format(id=show_id)})
    return found


def count_sources(
    s: Session, series: m.Series, season: m.Season, cache: JsonCache, anilist: _Anilist
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = [_sonarr(series, season)]
    if (entry := _anilist(s, series, season, anilist)) is not None:
        rows.append(entry)
    if series.tvdb_id is not None:
        rows += _cached_seasons(series, season, cache)
    if season.expected_override is not None:
        rows.append({"source": "override", "count": season.expected_override})
    return {
        "expected": season.expected_count,
        "expected_source": season.expected_source,
        "disputed": season.disputed,
        "state": season.state,
        "last_evaluated_at": (
            season.last_evaluated_at.isoformat() if season.last_evaluated_at else None
        ),
        "sources": rows,
    }
