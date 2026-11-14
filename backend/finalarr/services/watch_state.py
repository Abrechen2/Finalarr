"""Watched state for the UI: who saw what of a series, what is still unwatched on disk.

"Unwatched" means: a regular episode with a file that no selected user has watched.
Specials (season 0) never count.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.orm import Session

from finalarr.db import models as m

CONTINUE_LIMIT = 10


def _seen_by_anyone() -> Any:
    """Correlated: some selected user watched this episode of this series."""
    return exists().where(
        m.WatchedEpisode.series_id == m.Season.series_id,
        m.WatchedEpisode.season_number == m.Season.number,
        m.WatchedEpisode.episode_number == m.Episode.number,
    )


def _unwatched_on_disk(series_id: Any) -> Select[Any]:
    return (
        select(m.Episode.id)
        .join(m.Season)
        .where(
            m.Season.series_id == series_id,
            m.Season.number > 0,
            m.Episode.has_file.is_(True),
            ~_seen_by_anyone(),
        )
    )


def _next(s: Session, series_id: int) -> tuple[int, dict[str, int] | None]:
    rows = s.execute(
        select(m.Season.number, m.Episode.number)
        .select_from(m.Episode)
        .join(m.Season)
        .where(m.Episode.id.in_(_unwatched_on_disk(series_id)))
        .order_by(m.Season.number, m.Episode.number)
    ).all()
    first = {"season": rows[0][0], "episode": rows[0][1]} if rows else None
    return len(rows), first


def series_watch(s: Session, series: m.Series) -> dict[str, Any]:
    users = s.execute(
        select(
            m.MediaUser.name,
            m.MediaServer.name,
            func.count(),
            func.max(m.WatchedEpisode.watched_on),
        )
        .select_from(m.WatchedEpisode)
        .join(m.MediaUser)
        .join(m.MediaServer)
        .where(m.WatchedEpisode.series_id == series.id, m.WatchedEpisode.season_number > 0)
        .group_by(m.MediaUser.id)
        .order_by(func.count().desc(), m.MediaUser.name)
    ).all()
    episodes: dict[str, list[str]] = {}
    for season, episode, name in s.execute(
        select(m.WatchedEpisode.season_number, m.WatchedEpisode.episode_number, m.MediaUser.name)
        .join(m.MediaUser)
        .where(m.WatchedEpisode.series_id == series.id)
        .order_by(m.MediaUser.id)
    ):
        episodes.setdefault(f"{season}x{episode}", []).append(name)
    unwatched, first = _next(s, series.id)
    return {
        # Without a media server the UI shows no watch panel at all.
        "enabled": s.scalar(select(exists().where(m.MediaServer.id.is_not(None)))) or False,
        "users": [
            {
                "name": name,
                "server": server,
                "watched": count,
                "last_watched": last.isoformat() if last else None,
            }
            for name, server, count, last in users
        ],
        "episodes": episodes,
        "unwatched_on_disk": unwatched,
        "next_unwatched": first,
    }


def watch_filter[T](query: Select[T], value: str) -> Select[T]:
    """started: someone watched it; behind: started, files unwatched; caught_up: started,
    nothing on disk unwatched."""
    started = exists().where(
        m.WatchedEpisode.series_id == m.Series.id, m.WatchedEpisode.season_number > 0
    )
    behind = exists(_unwatched_on_disk(m.Series.id))
    conditions = {
        "started": started,
        "behind": and_(started, behind),
        "caught_up": and_(started, ~behind),
    }
    return query.where(conditions[value])


def continue_watching(s: Session, limit: int = CONTINUE_LIMIT) -> list[dict[str, Any]]:
    """Followed series someone started that have unwatched episodes on disk, most
    recently watched first."""
    last = (
        select(m.WatchedEpisode.series_id, func.max(m.WatchedEpisode.watched_on).label("last"))
        .group_by(m.WatchedEpisode.series_id)
        .subquery()
    )
    rows = s.execute(
        watch_filter(
            select(m.Series, last.c.last)
            .join(last, last.c.series_id == m.Series.id)
            .where(m.Series.followed.is_(True)),
            "behind",
        )
        .order_by(last.c.last.desc().nulls_last(), m.Series.title)
        .limit(limit)
    ).all()
    result = []
    for series, last_watched in rows:
        unwatched, first = _next(s, series.id)
        result.append(
            {
                "series_id": series.id,
                "title": series.title,
                "poster_url": series.poster_url,
                "unwatched": unwatched,
                "next": first,
                "last_watched": last_watched.isoformat() if last_watched else None,
            }
        )
    return result


def watched_counts(s: Session, series_ids: list[int]) -> dict[int, int]:
    """Per series: the most regular episodes any one selected user has watched."""
    per_user = (
        select(m.WatchedEpisode.series_id, func.count().label("n"))
        .where(m.WatchedEpisode.series_id.in_(series_ids), m.WatchedEpisode.season_number > 0)
        .group_by(m.WatchedEpisode.series_id, m.WatchedEpisode.user_id)
        .subquery()
    )
    rows = s.execute(
        select(per_user.c.series_id, func.max(per_user.c.n)).group_by(per_user.c.series_id)
    )
    return {sid: n for sid, n in rows}
