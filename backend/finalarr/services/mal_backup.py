"""MyAnimeList (via Jikan) as a second source for anime sequels.

For every AniList entry Fribb maps to a followed series, the MAL sequel links
are checked. A sequel that has not started and is mapped to no TVDB season is
reported as ``sequel_announced`` — but only if Fribb can name its AniList id,
so the AniList enricher and this watcher share one fingerprint and never
report the same sequel twice. Jikan is slow and often down: results are cached
and every failure just ends the run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.enricher import NEWS_WINDOW, record_sequel
from finalarr.services.season_sources import JsonCache
from finalarr.sources.jikan import JikanAnime, JikanError

log = logging.getLogger(__name__)
CACHE_TTL = timedelta(hours=12)
SERIES_TYPES = {"TV", "ONA"}

OnEvents = Callable[[Session, list[m.Event]], None]


class _Jikan(Protocol):
    def sequel_ids(self, mal_id: int) -> list[int]: ...

    def anime(self, mal_id: int) -> JikanAnime: ...


class MalSequelWatcher:
    def __init__(
        self,
        db: Database,
        jikan: _Jikan,
        cache: JsonCache,
        on_events: OnEvents | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = db
        self._jikan = jikan
        self._cache = cache
        self._on_events = on_events
        self._clock = clock

    def run(self) -> None:
        with self._db.session() as s:
            rows = s.execute(
                select(m.Series.id, m.FribbId.mal_id)
                .join(m.AnilistMapping, m.AnilistMapping.tvdb_id == m.Series.tvdb_id)
                .join(m.FribbId, m.FribbId.anilist_id == m.AnilistMapping.anilist_id)
                .where(m.Series.followed.is_(True))
                .distinct()
            ).all()
            mal_to_anilist = {
                mal: a for a, mal in s.execute(select(m.FribbId.anilist_id, m.FribbId.mal_id))
            }
            mapped = set(s.scalars(select(m.AnilistMapping.anilist_id)))
        try:
            for series_id, mal_id in rows:
                for sequel_mal in self._sequels(mal_id):
                    anilist_id = mal_to_anilist.get(sequel_mal)
                    if anilist_id is None or anilist_id in mapped:
                        continue
                    self._maybe_announce(series_id, anilist_id, self._anime(sequel_mal))
        except JikanError as error:
            log.info("MyAnimeList (Jikan) unavailable: %s", error)

    def _sequels(self, mal_id: int) -> list[int]:
        found: list[int] = self._cache.remember(
            f"mal:sequels:{mal_id}", CACHE_TTL, lambda: self._jikan.sequel_ids(mal_id)
        )
        return found

    def _anime(self, mal_id: int) -> JikanAnime:
        raw = self._cache.remember(
            f"mal:anime:{mal_id}",
            CACHE_TTL,
            lambda: self._jikan.anime(mal_id).model_dump(by_alias=True),
        )
        return JikanAnime.model_validate(raw)

    def _maybe_announce(self, series_id: int, anilist_id: int, anime: JikanAnime) -> None:
        start = anime.start_date
        today: date = self._clock().date()
        if not anime.upcoming or anime.type not in SERIES_TYPES:
            return
        if start is not None and start < today - NEWS_WINDOW:
            return
        with self._db.session() as s:
            series = s.get(m.Series, series_id)
            if series is None:
                return
            event = record_sequel(
                s, series, anilist_id, anime.title, start, anime.episodes, ["myanimelist"]
            )
            if event is not None and self._on_events:
                self._on_events(s, [event])
            s.commit()
