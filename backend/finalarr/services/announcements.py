"""Season announcements for TV series from TVmaze, TMDB and Trakt.

Sonarr only learns about a season once TheTVDB lists its episodes. These
sources usually know a renewed season much earlier. Their answers are merged
per season (earliest known start, any episode count) and reported with the
same fingerprint the evaluator uses for ``season_announced``, so a season is
announced once no matter which source — or Sonarr — knows it first.

Series Fribb maps to AniList are anime and handled by the AniList enricher.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy import exists, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from finalarr.core.fingerprint import fingerprint
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.source_catalog import disabled_sources

log = logging.getLogger(__name__)
NEWS_WINDOW = timedelta(days=30)

OnEvents = Callable[[Session, list[m.Event]], None]


class SourceError(RuntimeError):
    """A source is unavailable for now; the watcher carries on without it."""


@dataclass(frozen=True)
class Announced:
    season: int
    start: date | None
    episodes: int | None


class SeasonSource(Protocol):
    name: str

    def seasons(self, tvdb_id: int) -> list[Announced]: ...


@dataclass
class _Merged:
    start: date | None = None
    episodes: int | None = None
    sources: tuple[str, ...] = ()


class AnnouncementWatcher:
    def __init__(
        self,
        db: Database,
        sources: list[SeasonSource],
        on_events: OnEvents | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = db
        self._sources = sources
        self._on_events = on_events
        self._clock = clock

    def run(self) -> None:
        with self._db.session() as s:
            off = disabled_sources(s)
        sources = [source for source in self._sources if source.name not in off]
        if not sources:
            return
        with self._db.session() as s:
            mapped = exists().where(m.AnilistMapping.tvdb_id == m.Series.tvdb_id)
            targets = s.execute(
                select(m.Series.id, m.Series.tvdb_id).where(
                    m.Series.followed.is_(True), m.Series.tvdb_id.is_not(None), ~mapped
                )
            ).all()
        for series_id, tvdb_id in targets:
            if tvdb_id is None:  # excluded by the query; narrows the type
                continue
            merged = self._ask(tvdb_id, sources)
            if merged:
                self._record(series_id, merged)

    def _ask(self, tvdb_id: int, sources: list[SeasonSource]) -> dict[int, _Merged]:
        merged: dict[int, _Merged] = {}
        for source in sources:
            try:
                answers = source.seasons(tvdb_id)
            except SourceError as error:
                log.info("%s unavailable: %s", source.name, error)
                continue
            for answer in answers:
                entry = merged.setdefault(answer.season, _Merged())
                starts = [d for d in (entry.start, answer.start) if d is not None]
                entry.start = min(starts) if starts else None
                entry.episodes = entry.episodes or answer.episodes
                entry.sources = tuple(sorted({*entry.sources, source.name}))
        return merged

    def _record(self, series_id: int, merged: dict[int, _Merged]) -> None:
        today = self._clock().date()
        with self._db.session() as s:
            series = s.get(m.Series, series_id)
            if series is None:
                return
            listed = {season.number for season in series.seasons if season.episodes}
            created = [
                event
                for number, info in sorted(merged.items())
                if number > 0 and number not in listed
                if info.start is None or info.start >= today - NEWS_WINDOW
                if (event := _announce(s, series, number, info)) is not None
            ]
            if created and self._on_events:
                self._on_events(s, created)
            s.commit()


def _announce(s: Session, series: m.Series, number: int, info: _Merged) -> m.Event | None:
    payload = {
        "season": number,
        "title": series.title,
        "series_type": series.series_type,
        "expected": info.episodes,
        "first_air": info.start.isoformat() if info.start else None,
        "sources": list(info.sources),
        "sonarr_url": f"{series.instance.url}/series/{series.title_slug}",
    }
    # Same key as the evaluator's announcement: whoever knows first reports it.
    key = fingerprint("season_announced", series.instance_id, series.sonarr_id, number, "")
    event_id = s.execute(
        insert(m.Event)
        .values(
            type="season_announced",
            instance_id=series.instance_id,
            series_id=series.id,
            season_id=None,
            fingerprint=key,
            payload_json=json.dumps(payload),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["fingerprint"])
        .returning(m.Event.id)
    ).scalar()
    return s.get_one(m.Event, event_id) if event_id is not None else None
