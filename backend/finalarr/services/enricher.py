"""AniList enrichment for followed anime (PLAN.md 4.1, 4.2).

Any series whose TVDB id Fribb maps is treated as anime, whatever its Sonarr
series type. Per TVDB season: the mapped AniList entries (manual pins win over
Fribb) give the expected count (split cours are summed), the parts of a
split-cour season, and — for an entry that has not finished — a season row
Sonarr may not know yet, so the evaluator can announce it.

Fresh sequels are usually on AniList long before Fribb maps them to a TVDB
season. A SEQUEL of a mapped entry that has not started yet and is mapped
nowhere is reported once as ``sequel_announced``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from finalarr.core.fingerprint import fingerprint
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.sources.anilist import AnilistError, AnilistMedia

log = logging.getLogger(__name__)
UPCOMING = {"NOT_YET_RELEASED", "RELEASING"}
SERIES_FORMATS = {"TV", "TV_SHORT", "ONA"}
NEWS_WINDOW = timedelta(days=30)

OnChange = Callable[[int, int], None]
OnEvents = Callable[[Session, list[m.Event]], None]


class _Media(Protocol):
    def media(self, ids: list[int]) -> dict[int, AnilistMedia]: ...


class AnimeEnricher:
    def __init__(
        self,
        db: Database,
        anilist: _Media,
        on_change: OnChange,
        on_events: OnEvents | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = db
        self._anilist = anilist
        self._on_change = on_change
        self._on_events = on_events
        self._clock = clock

    def run(self) -> None:
        with self._db.session() as s:
            series_ids = list(s.scalars(select(m.Series.id).where(m.Series.followed.is_(True))))
            anime_tvdb_ids = s.scalars(
                select(m.Series.tvdb_id).where(
                    m.Series.followed.is_(True),
                    m.Series.tvdb_id.is_not(None),
                )
            ).all()
            wanted = sorted(
                {
                    anilist_id
                    for tvdb_id in anime_tvdb_ids
                    if tvdb_id is not None
                    for group in season_mapping(s, tvdb_id)[0].values()
                    for anilist_id in group
                }
            )
        try:
            # One request per 50 ids fills the cache for every series below,
            # a second one the sequels of all those entries.
            known = self._anilist.media(wanted)
            self._anilist.media(sorted(_upcoming_sequels(list(known.values()))))
        except AnilistError as error:
            log.info("AniList enrichment paused: %s", error)
            return
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
            if series.tvdb_id is None:
                series.anilist_resolution = "none"
                s.commit()
                return
            mapping, resolution = season_mapping(s, series.tvdb_id)
            if resolution == "unresolved" and series.series_type != "anime":
                resolution = "none"  # not an anime as far as anyone knows
            series.anilist_resolution = resolution
            ids = sorted({i for group in mapping.values() for i in group})
            s.commit()
        media = self._anilist.media(ids) if ids else {}
        with self._db.session() as s:
            series = s.get(m.Series, series_id)
            if series is None:  # removed by a reconcile while AniList was asked
                return
            results = [
                _apply_season(s, series, number, [media[i] for i in group if i in media])
                for number, group in sorted(mapping.items())
            ]
            results += [
                _clear_season(s, season)
                for season in series.seasons
                if season.number not in mapping
            ]
            changed = any(results)
            s.commit()
            instance_id, sonarr_id = series.instance_id, series.sonarr_id
        if changed:
            self._on_change(instance_id, sonarr_id)
        self._announce_sequels(series_id, list(media.values()))

    def _announce_sequels(self, series_id: int, known: list[AnilistMedia]) -> None:
        candidates = _upcoming_sequels(known)
        if not candidates:
            return
        with self._db.session() as s:
            mapped = set(
                s.scalars(
                    select(m.AnilistMapping.anilist_id).where(
                        m.AnilistMapping.anilist_id.in_(candidates)
                    )
                )
            )
        fresh = sorted(candidates - mapped)
        if not fresh:
            return
        sequels = self._anilist.media(fresh)
        today = self._clock().date()
        with self._db.session() as s:
            series = s.get(m.Series, series_id)
            if series is None:
                return
            created = [
                event
                for sequel in sequels.values()
                if sequel.status in UPCOMING and _is_news(sequel.start_date, today)
                if (event := _record_sequel(s, series, sequel)) is not None
            ]
            if created and self._on_events:
                self._on_events(s, created)
            s.commit()


def _upcoming_sequels(entries: list[AnilistMedia]) -> set[int]:
    return {
        edge.node.id
        for entry in entries
        for edge in entry.relations.edges
        if edge.relation_type == "SEQUEL"
        and edge.node.format in SERIES_FORMATS
        and edge.node.status in UPCOMING
    }


def _is_news(start: date | None, today: date) -> bool:
    return start is None or start >= today - NEWS_WINDOW


def _record_sequel(s: Session, series: m.Series, sequel: AnilistMedia) -> m.Event | None:
    return record_sequel(
        s, series, sequel.id, sequel.title, sequel.start_date, sequel.episodes, ["anilist"]
    )


def record_sequel(
    s: Session,
    series: m.Series,
    anilist_id: int,
    title: str,
    start: date | None,
    episodes: int | None,
    sources: list[str],
) -> m.Event | None:
    """Insert once per (series, AniList entry); any source reporting the same entry
    uses the same fingerprint, so an existing one is a no-op."""
    payload = {
        "title": series.title,
        "series_type": series.series_type,
        "anilist_id": anilist_id,
        "sequel_title": title,
        "first_air": start.isoformat() if start else None,
        "expected": episodes,
        "sources": sources,
        "sonarr_url": f"{series.instance.url}/series/{series.title_slug}",
    }
    key = fingerprint("sequel_announced", series.instance_id, series.sonarr_id, 0, str(anilist_id))
    event_id = s.execute(
        insert(m.Event)
        .values(
            type="sequel_announced",
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


def _clear_season(s: Session, season: m.Season) -> bool:
    """A season whose AniList mapping was withdrawn loses the AniList data."""
    if season.anilist_count is None and season.anilist_start is None and not season.parts:
        return False
    season.anilist_count, season.anilist_start = None, None
    _apply_parts(s, season, [])
    return True


def _apply_season(s: Session, series: m.Series, number: int, entries: list[AnilistMedia]) -> bool:
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
    return _apply_parts(s, season, entries if total else []) or changed


def _apply_parts(s: Session, season: m.Season, entries: list[AnilistMedia]) -> bool:
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
    s.flush()  # delete the old rows before inserting their replacements (UNIQUE index)
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
