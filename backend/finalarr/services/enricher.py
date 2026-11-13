"""AniList enrichment for followed anime (PLAN.md 4.1, 4.2).

Per TVDB season: the mapped AniList entries (manual pins win over Fribb) give
the expected count (split cours are summed), the parts of a split-cour season,
and — for an entry that has not finished — a season row Sonarr may not know
yet, so the evaluator can announce it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.sources.anilist import AnilistError, AnilistMedia

log = logging.getLogger(__name__)
UPCOMING = {"NOT_YET_RELEASED", "RELEASING"}

OnChange = Callable[[int, int], None]


class _Media(Protocol):
    def media(self, ids: list[int]) -> dict[int, AnilistMedia]: ...


class AnimeEnricher:
    def __init__(self, db: Database, anilist: _Media, on_change: OnChange) -> None:
        self._db = db
        self._anilist = anilist
        self._on_change = on_change

    def run(self) -> None:
        with self._db.session() as s:
            series_ids = list(s.scalars(select(m.Series.id).where(m.Series.followed.is_(True))))
        for series_id in series_ids:
            try:
                self.enrich(series_id)
            except AnilistError as error:
                log.info("AniList enrichment paused: %s", error)
                return

    def enrich(self, series_id: int) -> None:
        with self._db.session() as s:
            series = s.get(m.Series, series_id)
            if series is None:
                return
            if series.series_type != "anime" or series.tvdb_id is None:
                series.anilist_resolution = "none"
                s.commit()
                return
            mapping, resolution = season_mapping(s, series.tvdb_id)
            series.anilist_resolution = resolution
            ids = sorted({i for group in mapping.values() for i in group})
            s.commit()
        media = self._anilist.media(ids) if ids else {}
        with self._db.session() as s:
            series = s.get_one(m.Series, series_id)
            results = [
                _apply_season(series, number, [media[i] for i in group if i in media])
                for number, group in sorted(mapping.items())
            ]
            changed = any(results)
            s.commit()
            instance_id, sonarr_id = series.instance_id, series.sonarr_id
        if changed:
            self._on_change(instance_id, sonarr_id)


def season_mapping(s: Session, tvdb_id: int) -> tuple[dict[int, list[int]], str]:
    rows = s.scalars(select(m.AnilistMapping).where(m.AnilistMapping.tvdb_id == tvdb_id)).all()
    manual: dict[int, list[int]] = {}
    auto: dict[int, list[int]] = {}
    for row in rows:
        (manual if row.source == "manual" else auto).setdefault(row.tvdb_season, []).append(
            row.anilist_id
        )
    mapping = {**auto, **manual}
    resolution = "manual" if manual else "auto" if auto else "unresolved"
    return mapping, resolution


def _apply_season(series: m.Series, number: int, entries: list[AnilistMedia]) -> bool:
    entries = sorted(entries, key=lambda e: (e.start_date or date.max, e.id))
    season = next((x for x in series.seasons if x.number == number), None)
    if season is None:
        if not any(e.status in UPCOMING for e in entries):
            return False
        season = m.Season(number=number)
        series.seasons.append(season)
    counts = [e.episodes for e in entries]
    total = sum(c for c in counts if c) if entries and all(counts) else None
    start = min((e.start_date for e in entries if e.start_date), default=None)
    changed = (season.anilist_count, season.anilist_start) != (total, start)
    season.anilist_count, season.anilist_start = total, start
    return _apply_parts(season, entries if total else []) or changed


def _apply_parts(season: m.Season, entries: list[AnilistMedia]) -> bool:
    """Consecutive episode ranges for split cours; one entry means no parts."""
    wanted: list[tuple[int, int, int, int, str]] = []
    first = 1
    for index, entry in enumerate(entries if len(entries) > 1 else [], start=1):
        last = first + (entry.episodes or 0) - 1
        wanted.append((index, entry.id, first, last, entry.title))
        first = last + 1
    current = [
        (p.part_index, p.anilist_id, p.episode_from, p.episode_to, p.title) for p in season.parts
    ]
    if current == wanted:
        return False
    season.parts.clear()
    for index, anilist_id, start, end, title in wanted:
        season.parts.append(
            m.AnimePart(
                part_index=index,
                anilist_id=anilist_id,
                episode_from=start,
                episode_to=end,
                title=title,
            )
        )
    return True
