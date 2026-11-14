"""Watched state for the UI: who saw what of a series, what is still unwatched on disk.

"Unwatched" means: a regular episode with a file that comes after the furthest episode
any selected user has watched (season, then episode) and that nobody has watched.
Episodes skipped before that point and specials (season 0) never count.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.orm import Session

from finalarr.db import models as m

CONTINUE_LIMIT = 10
# Orders (season, episode) as one number: season 3 episode 12 → 3_00012.
EPISODE_ORDER = 100_000


def _seen_by_anyone() -> Any:
    """Correlated: some selected user watched this episode of this series."""
    return exists().where(
        m.WatchedEpisode.series_id == m.Season.series_id,
        m.WatchedEpisode.season_number == m.Season.number,
        m.WatchedEpisode.episode_number == m.Episode.number,
    )


def _furthest(series_id: Any) -> Any:
    """Correlated scalar: position of the furthest regular episode anyone watched."""
    return (
        select(
            func.max(
                m.WatchedEpisode.season_number * EPISODE_ORDER + m.WatchedEpisode.episode_number
            )
        )
        .where(m.WatchedEpisode.series_id == series_id, m.WatchedEpisode.season_number > 0)
        .scalar_subquery()
    )


def _unwatched_on_disk(series_id: Any) -> Select[Any]:
    return (
        select(m.Episode.id)
        .join(m.Season)
        .where(
            m.Season.series_id == series_id,
            m.Season.number > 0,
            m.Episode.has_file.is_(True),
            m.Season.number * EPISODE_ORDER + m.Episode.number > _furthest(series_id),
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
    episodes: dict[str, list[int]] = {}
    for season, episode, user_id in s.execute(
        select(
            m.WatchedEpisode.season_number,
            m.WatchedEpisode.episode_number,
            m.WatchedEpisode.user_id,
        )
        .where(m.WatchedEpisode.series_id == series.id)
        .order_by(m.WatchedEpisode.user_id)
    ):
        episodes.setdefault(f"{season}x{episode}", []).append(user_id)
    viewers = [
        {"id": uid, "name": name, "server": server}
        for uid, name, server in s.execute(
            select(m.MediaUser.id, m.MediaUser.name, m.MediaServer.name)
            .join(m.MediaServer)
            .where(m.MediaUser.selected.is_(True), m.MediaServer.enabled.is_(True))
            .order_by(m.MediaUser.id)
        )
    ]
    corrected = sorted(
        {
            f"{season}x{episode}"
            for season, episode in s.execute(
                select(m.WatchOverride.season_number, m.WatchOverride.episode_number).where(
                    m.WatchOverride.series_id == series.id
                )
            )
        }
    )
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
        "viewers": viewers,
        "corrected": corrected,
        "unwatched_on_disk": unwatched,
        "next_unwatched": first,
    }


def watch_filter[T](query: Select[T], value: str) -> Select[T]:
    """started: someone watched it; behind: started, files unwatched; caught_up: started,
    followed, nothing on disk unwatched."""
    started = exists().where(
        m.WatchedEpisode.series_id == m.Series.id, m.WatchedEpisode.season_number > 0
    )
    behind = exists(_unwatched_on_disk(m.Series.id))
    conditions = {
        "started": started,
        "behind": and_(started, behind),
        # Episode lists exist only for followed series; without one it is a guess.
        "caught_up": and_(started, m.Series.followed.is_(True), ~behind),
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


def correct_watched(
    s: Session,
    series_id: int,
    user_id: int,
    episodes: list[tuple[int, int]],
    watched: bool | None,
    today: date,
) -> None:
    """Mark episodes (not) watched for one selected user, or take corrections back
    (``watched=None``; the next sync restores what the server says)."""
    user = s.get(m.MediaUser, user_id)
    if user is None or not user.selected:
        raise LookupError("user")
    for season, episode in episodes:
        key = {
            "user_id": user_id,
            "series_id": series_id,
            "season_number": season,
            "episode_number": episode,
        }
        override = s.get(m.WatchOverride, key)
        if watched is None:
            if override is not None:
                s.delete(override)
            continue
        if override is None:
            s.add(m.WatchOverride(**key, watched=watched))
        else:
            override.watched = watched
        row = s.get(m.WatchedEpisode, key)
        if watched and row is None:
            s.add(m.WatchedEpisode(**key, watched_on=today))
        elif not watched and row is not None:
            s.delete(row)
