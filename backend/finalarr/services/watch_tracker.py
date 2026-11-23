"""Watch tracker: what the selected users watched, in numbers, and what is still missing.

Counts are per episode, not per viewing: an episode two people watched counts once in
the "everyone" view. Specials (season 0) never count. Episodes from the first sync have
no date; they count in the totals but in no week or month. Which episodes exist is known
only for followed series, so a series nobody follows has state "unknown".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from finalarr.db import models as m
from finalarr.services.watch_state import EPISODE_ORDER

WEEKS = 12
# Behind and nothing watched for this long: probably dropped.
ABANDONED_DAYS = 30
STATES = ("all", "behind", "abandoned", "caught_up", "finished", "unknown")
SORTS = ("recent", "open", "title")


@dataclass(frozen=True)
class _Row:
    series: m.Series
    watched: int
    last: date | None
    unwatched: int | None
    next_pos: int | None
    state: str


def _scope[*Ts](query: Select[*Ts], user_id: int | None) -> Select[*Ts]:
    """Regular episodes of selected users on enabled servers (or of one of them)."""
    users = (
        select(m.MediaUser.id)
        .join(m.MediaServer)
        .where(m.MediaUser.selected.is_(True), m.MediaServer.enabled.is_(True))
    )
    if user_id is not None:
        users = users.where(m.MediaUser.id == user_id)
    return query.where(m.WatchedEpisode.user_id.in_(users), m.WatchedEpisode.season_number > 0)


def _episodes(user_id: int | None) -> Any:
    """One row per watched episode: series, position, latest day anyone in scope saw it."""
    return _scope(
        select(
            m.WatchedEpisode.series_id,
            (
                m.WatchedEpisode.season_number * EPISODE_ORDER + m.WatchedEpisode.episode_number
            ).label("pos"),
            func.max(m.WatchedEpisode.watched_on).label("day"),
        ).group_by(
            m.WatchedEpisode.series_id,
            m.WatchedEpisode.season_number,
            m.WatchedEpisode.episode_number,
        ),
        user_id,
    ).subquery()


def _after_furthest(s: Session, summary: Any, on_disk: bool) -> dict[int, tuple[int, int]]:
    """Per series: count and first position of regular episodes after the furthest
    watched one (only those with a file when ``on_disk``)."""
    pos = m.Season.number * EPISODE_ORDER + m.Episode.number
    query = (
        select(m.Season.series_id, func.count(), func.min(pos))
        .select_from(m.Episode)
        .join(m.Season)
        .join(summary, summary.c.series_id == m.Season.series_id)
        .where(m.Season.number > 0, pos > summary.c.furthest)
        .group_by(m.Season.series_id)
    )
    if on_disk:
        query = query.where(m.Episode.has_file.is_(True))
    return {sid: (count, first) for sid, count, first in s.execute(query)}


def _state(series: m.Series, unwatched: int, remaining: int, last: date | None, today: date) -> str:
    if series.status == "ended" and remaining == 0:
        return "finished"
    if unwatched == 0:
        return "caught_up"
    if last is not None and (today - last).days > ABANDONED_DAYS:
        return "abandoned"
    return "behind"


def _rows(s: Session, user_id: int | None, today: date) -> list[_Row]:
    episodes = _episodes(user_id)
    summary = (
        select(
            episodes.c.series_id,
            func.count().label("watched"),
            func.max(episodes.c.pos).label("furthest"),
            func.max(episodes.c.day).label("last"),
        )
        .group_by(episodes.c.series_id)
        .subquery()
    )
    on_disk = _after_furthest(s, summary, on_disk=True)
    remaining = _after_furthest(s, summary, on_disk=False)
    rows = []
    for series, watched, last in s.execute(
        select(m.Series, summary.c.watched, summary.c.last).join(
            summary, summary.c.series_id == m.Series.id
        )
    ):
        if not series.followed:
            rows.append(_Row(series, watched, last, None, None, "unknown"))
            continue
        unwatched, first = on_disk.get(series.id, (0, None))
        state = _state(series, unwatched, remaining.get(series.id, (0, None))[0], last, today)
        rows.append(_Row(series, watched, last, unwatched, first, state))
    return rows


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def tracker_stats(
    s: Session, user_id: int | None, today: date, weeks: int = WEEKS
) -> dict[str, Any]:
    """Totals, this week and month, episodes per week (oldest first), series by state."""
    week = _week_start(today)
    first_week = week - timedelta(weeks=weeks - 1)
    month = today.replace(day=1)
    episodes = _episodes(user_id)
    total, minutes, undated = s.execute(
        select(
            func.count(),
            func.coalesce(func.sum(m.Series.runtime), 0),
            func.count().filter(episodes.c.day.is_(None)),
        )
        .select_from(episodes)
        .join(m.Series, m.Series.id == episodes.c.series_id)
    ).one()
    # Per period, an episode counts once however many in scope watched it in it.
    seen = [
        (sid, season, episode, day)
        for sid, season, episode, day in s.execute(
            _scope(
                select(
                    m.WatchedEpisode.series_id,
                    m.WatchedEpisode.season_number,
                    m.WatchedEpisode.episode_number,
                    m.WatchedEpisode.watched_on,
                ).where(m.WatchedEpisode.watched_on >= min(first_week, month)),
                user_id,
            )
        )
        if day is not None
    ]
    per_week: dict[date, set[tuple[int, int, int]]] = {}
    for sid, season, episode, day in seen:
        per_week.setdefault(_week_start(day), set()).add((sid, season, episode))

    def distinct_since(start: date) -> int:
        return len({(sid, se, ep) for sid, se, ep, day in seen if day >= start})

    states = [row.state for row in _rows(s, user_id, today)]
    return {
        "episodes": total,
        "minutes": minutes,
        "undated": undated,
        "this_week": distinct_since(week),
        "this_month": distinct_since(month),
        "weekly": [
            {
                "week": (first_week + timedelta(weeks=i)).isoformat(),
                "episodes": len(per_week.get(first_week + timedelta(weeks=i), ())),
            }
            for i in range(weeks)
        ],
        "series": {
            "started": len(states),
            # Abandoned series are behind, too.
            "behind": sum(state in ("behind", "abandoned") for state in states),
            "abandoned": states.count("abandoned"),
            "caught_up": states.count("caught_up"),
            "finished": states.count("finished"),
            "unknown": states.count("unknown"),
        },
    }


def _matches(row: _Row, state: str) -> bool:
    if state == "all":
        return True
    if state == "behind":
        return row.state in ("behind", "abandoned")
    return row.state == state


def tracker_series(
    s: Session, user_id: int | None, today: date, state: str = "all", sort: str = "recent"
) -> list[dict[str, Any]]:
    """Every series someone in scope started, with what is still unwatched on disk."""
    rows = [row for row in _rows(s, user_id, today) if _matches(row, state)]
    recent = sorted(rows, key=lambda r: r.series.sort_title or r.series.title.lower())
    recent.sort(key=lambda r: r.last or date.min, reverse=True)
    if sort == "title":
        rows = sorted(rows, key=lambda r: r.series.sort_title or r.series.title.lower())
    elif sort == "open":
        rows = sorted(
            recent, key=lambda r: -1 if r.unwatched is None else r.unwatched, reverse=True
        )
    else:
        rows = recent
    return [
        {
            "series_id": row.series.id,
            "title": row.series.title,
            "poster_url": row.series.poster_url,
            "state": row.state,
            "watched": row.watched,
            "unwatched": row.unwatched,
            "next": (
                {"season": row.next_pos // EPISODE_ORDER, "episode": row.next_pos % EPISODE_ORDER}
                if row.next_pos is not None
                else None
            ),
            "last_watched": row.last.isoformat() if row.last else None,
        }
        for row in rows
    ]
