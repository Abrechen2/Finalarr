"""TVmaze, TMDB and Trakt as season sources for the announcement watcher, with
a small JSON cache in the database (the ``anilist_cache`` table is generic)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from finalarr.db.models import AnilistCache
from finalarr.db.session import Database
from finalarr.services.announcements import Announced, SourceError
from finalarr.sources.tmdb import TmdbError
from finalarr.sources.trakt import TraktError
from finalarr.sources.tvmaze import TvmazeError, TvmazeSeason

ID_TTL = timedelta(days=30)
MISSING_ID_TTL = timedelta(days=7)
SEASONS_TTL = timedelta(hours=12)
_MISSING = "null"


class JsonCache:
    def __init__(self, db: Database, clock: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self._db = db
        self._clock = clock

    def get(self, key: str) -> tuple[bool, Any]:
        with self._db.session() as s:
            row = s.get(AnilistCache, key)
            if row is None:
                return False, None
            expires = (
                row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
            )
            if expires <= self._clock():
                return False, None
            return True, json.loads(row.body_json)

    def put(self, key: str, value: Any, ttl: timedelta) -> None:
        with self._db.session() as s:
            s.merge(
                AnilistCache(key=key, body_json=json.dumps(value), expires_at=self._clock() + ttl)
            )
            s.commit()

    def remember(
        self, key: str, ttl: timedelta, fetch: Callable[[], Any], miss_ttl: timedelta | None = None
    ) -> Any:
        hit, value = self.get(key)
        if hit:
            return value
        value = fetch()
        self.put(key, value, miss_ttl if value is None and miss_ttl else ttl)
        return value


Row = tuple[int, date | None, int | None]


class _RowsClient(Protocol):
    def seasons(self, show_id: int) -> list[Row]: ...


def _rows(rows: list[Any]) -> list[Announced]:
    return [
        Announced(int(n), date.fromisoformat(d) if isinstance(d, str) else d, e) for n, d, e in rows
    ]


def _encode(rows: list[Row]) -> list[list[Any]]:
    return [[n, d.isoformat() if d else None, e] for n, d, e in rows]


class TvmazeSource:
    name = "tvmaze"

    def __init__(self, client: Any, cache: JsonCache) -> None:
        self._client = client
        self._cache = cache

    def seasons(self, tvdb_id: int) -> list[Announced]:
        try:
            show_id = self._cache.remember(
                f"tvmaze:show:{tvdb_id}",
                ID_TTL,
                lambda: self._client.show_id_for_tvdb(tvdb_id),
                MISSING_ID_TTL,
            )
            if show_id is None:
                return []
            rows = self._cache.remember(
                f"tvmaze:seasons:{show_id}",
                SEASONS_TTL,
                lambda: _encode([_tvmaze_row(s) for s in self._client.seasons(show_id)]),
            )
        except TvmazeError as error:
            raise SourceError(str(error)) from None
        return _rows(rows)


def _tvmaze_row(season: TvmazeSeason) -> Row:
    return season.number, season.premiere_date, season.episode_order


class _KeyedSource:
    name = ""
    _errors: tuple[type[Exception], ...] = ()

    def __init__(self, client: Any, cache: JsonCache) -> None:
        self._client = client
        self._cache = cache

    def _lookup(self, tvdb_id: int) -> int | None:
        raise NotImplementedError

    def seasons(self, tvdb_id: int) -> list[Announced]:
        try:
            show_id = self._cache.remember(
                f"{self.name}:show:{tvdb_id}", ID_TTL, lambda: self._lookup(tvdb_id), MISSING_ID_TTL
            )
            if show_id is None:
                return []
            rows = self._cache.remember(
                f"{self.name}:seasons:{show_id}",
                SEASONS_TTL,
                lambda: _encode(self._client.seasons(show_id)),
            )
        except self._errors as error:
            raise SourceError(str(error)) from None
        return _rows(rows)


class TmdbSource(_KeyedSource):
    name = "tmdb"
    _errors = (TmdbError,)

    def _lookup(self, tvdb_id: int) -> int | None:
        result: int | None = self._client.tv_id_for_tvdb(tvdb_id)
        return result


class TraktSource(_KeyedSource):
    name = "trakt"
    _errors = (TraktError,)

    def _lookup(self, tvdb_id: int) -> int | None:
        result: int | None = self._client.show_id_for_tvdb(tvdb_id)
        return result
