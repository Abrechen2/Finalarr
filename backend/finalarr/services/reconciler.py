"""Reconciler: Sonarr → database → evaluator → events (PLAN.md 4, "polling decides").

Sonarr is read outside any transaction; each series is then written in one
short transaction together with its season state and new events (outbox).
Only followed series have their episodes fetched and evaluated.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, object_session

from finalarr.core.codec import dump_memory, load_memory
from finalarr.core.evaluator import evaluate
from finalarr.core.model import Episode as CoreEpisode
from finalarr.core.model import Evaluation, Part, Policy, SeasonInput, SeasonMemory
from finalarr.crypto import SecretBox
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.reconcile_queue import FULL_SYNC
from finalarr.services.settings_store import load_settings, policy_from
from finalarr.sources.sonarr import SonarrClient, SonarrEpisode, SonarrError, SonarrSeries

log = logging.getLogger(__name__)

ClientFactory = Callable[[m.SonarrInstance], Any]
EventHook = Callable[[Session, list[m.Event]], None]


def default_client_factory(box: SecretBox) -> ClientFactory:
    def build(instance: m.SonarrInstance) -> SonarrClient:
        return SonarrClient(instance.url, box.decrypt(instance.api_key_enc))

    return build


def _utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything in Finalarr is UTC."""
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class Reconciler:
    def __init__(
        self,
        db: Database,
        box: SecretBox,
        client_factory: ClientFactory | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        on_events: EventHook | None = None,
    ) -> None:
        self._db = db
        self._client_factory = client_factory or default_client_factory(box)
        self._clock = clock
        self._on_events = on_events

    def reconcile(self, instance_id: int, sonarr_series_id: int = FULL_SYNC) -> None:
        with self._db.session() as s:
            instance = s.get(m.SonarrInstance, instance_id)
            if instance is None or not instance.enabled:
                return
            client = self._client_factory(instance)
        try:
            if sonarr_series_id == FULL_SYNC:
                self._full(instance_id, client)
            else:
                self._one(instance_id, client, sonarr_series_id)
        except SonarrError as error:
            log.warning("Reconcile of instance %s failed: %s", instance_id, error)
            self._mark(instance_id, str(error))
            return
        self._mark(instance_id, None)

    def _mark(self, instance_id: int, error: str | None) -> None:
        with self._db.session() as s:
            instance = s.get(m.SonarrInstance, instance_id)
            if instance is None:
                return
            instance.last_error = error
            if error is None:
                instance.last_sync_at = self._clock()
            s.commit()

    def _full(self, instance_id: int, client: Any) -> None:
        labels = client.tags()
        remote = client.series_list()
        with self._db.session() as s:
            known = {
                row.sonarr_id: row
                for row in s.scalars(select(m.Series).where(m.Series.instance_id == instance_id))
            }
            for gone in set(known) - {r.id for r in remote}:
                s.delete(known[gone])
            followed = []
            for series in remote:
                row = self._upsert_series(s, instance_id, known.get(series.id), series, labels)
                if row.followed:
                    followed.append(series.id)
            s.commit()
        for sonarr_id in followed:
            self._episodes(instance_id, sonarr_id, client.episodes(sonarr_id))

    def _one(self, instance_id: int, client: Any, sonarr_series_id: int) -> None:
        labels = client.tags()
        series = client.series(sonarr_series_id)
        with self._db.session() as s:
            row = s.scalar(
                select(m.Series).where(
                    m.Series.instance_id == instance_id, m.Series.sonarr_id == sonarr_series_id
                )
            )
            row = self._upsert_series(s, instance_id, row, series, labels)
            followed = row.followed
            s.commit()
        if followed:
            self._episodes(instance_id, sonarr_series_id, client.episodes(sonarr_series_id))

    def _upsert_series(
        self,
        s: Session,
        instance_id: int,
        row: m.Series | None,
        series: SonarrSeries,
        labels: dict[int, str],
    ) -> m.Series:
        if row is None:
            defaults = load_settings(s)
            row = m.Series(
                instance_id=instance_id,
                sonarr_id=series.id,
                include_specials=defaults["include_specials_default"],
                respect_monitoring=defaults["respect_monitoring_default"],
            )
            s.add(row)
        row.title = series.title
        row.sort_title = series.sort_title or series.title.lower()
        row.title_slug = series.title_slug
        row.year = series.year
        row.tvdb_id = series.tvdb_id
        row.series_type = series.series_type if series.series_type in m.SERIES_TYPES else "standard"
        row.status = series.status
        row.monitored = series.monitored
        row.poster_url = series.poster_url
        row.tags_json = json.dumps(sorted(labels[t] for t in series.tags if t in labels))
        seasons = {season.number: season for season in row.seasons}
        for remote in series.seasons:
            season = seasons.get(remote.season_number)
            if season is None:
                season = m.Season(number=remote.season_number)
                row.seasons.append(season)
            season.monitored = remote.monitored
        return row

    def _episodes(self, instance_id: int, sonarr_id: int, episodes: list[SonarrEpisode]) -> None:
        now = self._clock()
        with self._db.session() as s:
            series = s.scalar(
                select(m.Series).where(
                    m.Series.instance_id == instance_id, m.Series.sonarr_id == sonarr_id
                )
            )
            if series is None:
                return
            policy = policy_from(load_settings(s))
            by_season: dict[int, list[SonarrEpisode]] = {}
            for episode in episodes:
                by_season.setdefault(episode.season_number, []).append(episode)
            seasons = {season.number: season for season in series.seasons}
            for number in by_season.keys() - seasons.keys():
                seasons[number] = m.Season(number=number)
                series.seasons.append(seasons[number])
            watched = series_watched(series)
            created: list[m.Event] = []
            for number, season in seasons.items():
                _sync_episodes(season, by_season.get(number, []))
                s.flush()
                created += self._evaluate(s, series, season, policy, now, watched)
            if created and self._on_events:
                self._on_events(s, created)
            s.commit()

    def _evaluate(
        self,
        s: Session,
        series: m.Series,
        season: m.Season,
        policy: Policy,
        now: datetime,
        watched: bool,
    ) -> list[m.Event]:
        memory = season_memory(season, watched)
        result = evaluate(season_input(series, season), memory, now, policy)
        _store_result(season, result, now)
        return record_events(s, series, season, result)


def series_watched(series: m.Series) -> bool:
    """True once any season of the series has been evaluated before this run."""
    return any(
        season.memory_json and load_memory(season.memory_json).initialized
        for season in series.seasons
    )


def season_memory(season: m.Season, watched: bool) -> SeasonMemory:
    """Stored memory; a season new to an already watched series skips the silent
    baseline, so its announcement is not swallowed (the baseline is per series)."""
    if season.memory_json:
        return load_memory(season.memory_json)
    return replace(SeasonMemory.initial(), initialized=watched)


def season_input(series: m.Series, season: m.Season) -> SeasonInput:
    return SeasonInput(
        instance_id=series.instance_id,
        series_id=series.sonarr_id,
        season_number=season.number,
        episodes=tuple(
            CoreEpisode(
                sonarr_id=e.sonarr_episode_id,
                number=e.number,
                air_date=_utc(e.air_date_utc),
                monitored=e.monitored,
                has_file=e.has_file,
                finale_type=e.finale_type,
            )
            for e in season.episodes
        ),
        expected_override=season.expected_override,
        anilist_count=season.anilist_count,
        include_specials=series.include_specials,
        respect_monitoring=series.respect_monitoring,
        anilist_start=season.anilist_start,
        parts=tuple(
            Part(p.part_index, p.anilist_id, p.episode_from, p.episode_to) for p in season.parts
        ),
    )


def _sync_episodes(season: m.Season, remote: Iterable[SonarrEpisode]) -> None:
    current = {e.sonarr_episode_id: e for e in season.episodes}
    incoming = {e.id: e for e in remote}
    gone_ids = current.keys() - incoming.keys()
    for gone in gone_ids:
        season.episodes.remove(current[gone])
    if gone_ids:
        # Sonarr may re-create an episode under a new id with the same number:
        # delete first, or the insert hits UNIQUE(season_id, number).
        object_session(season).flush()  # type: ignore[union-attr]
    for sonarr_id, episode in incoming.items():
        row = current.get(sonarr_id)
        if row is None:
            row = m.Episode(sonarr_episode_id=sonarr_id, number=episode.episode_number)
            season.episodes.append(row)
        row.number = episode.episode_number
        row.absolute_number = episode.absolute_episode_number
        row.title = episode.title
        row.air_date_utc = episode.air_date_utc
        row.monitored = episode.monitored
        row.has_file = episode.has_file
        row.finale_type = episode.finale_type


def _store_result(season: m.Season, result: Evaluation, now: datetime) -> None:
    if result.memory.state != season.state:
        season.state = result.memory.state
        season.state_since = now
    season.memory_json = dump_memory(result.memory)
    season.expected_count = result.expected_count
    season.disputed = result.disputed
    season.expected_source = (
        "override"
        if season.expected_override is not None
        else "anilist"
        if result.disputed or (result.expected_count and not season.episodes)
        else "sonarr"
        if result.expected_count
        else None
    )
    season.last_evaluated_at = now


def record_events(
    s: Session, series: m.Series, season: m.Season, result: Evaluation
) -> list[m.Event]:
    """Insert new events; an existing fingerprint is a no-op (PLAN.md 4.3)."""
    created = []
    for event in result.events:
        payload = {
            **event.payload,
            "title": series.title,
            "series_type": series.series_type,
            "sonarr_url": f"{series.instance.url}/series/{series.title_slug}",
        }
        if event.type == "part_complete":
            part = next(p for p in season.parts if p.part_index == event.payload["part"])
            payload |= {"part_title": part.title, "parts_mode": season.parts_mode}
        inserted = s.execute(
            insert(m.Event)
            .values(
                type=event.type,
                instance_id=series.instance_id,
                series_id=series.id,
                season_id=season.id,
                fingerprint=event.fingerprint,
                payload_json=json.dumps(payload),
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["fingerprint"])
            .returning(m.Event.id)
        ).scalar()
        if inserted is not None:
            created.append(s.get_one(m.Event, inserted))
    return created
