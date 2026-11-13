"""Jikan (unofficial MyAnimeList API, no key): backup for AniList sequel data.

Jikan is often slow or down; every failure is a JikanError and the caller
carries on without it. Its documented limit is 3 requests/s and 60/min.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from finalarr.ratelimit import RateLimiter

JIKAN_URL = "https://api.jikan.moe/v4"
TIMEOUT_SECONDS = 15
BUDGET = (30, 60)
UPCOMING_STATUS = {"Not yet aired", "Currently Airing"}


class JikanError(RuntimeError):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


class _Aired(_Model):
    start: str | None = Field(default=None, alias="from")


class JikanAnime(_Model):
    mal_id: int
    title: str
    type: str | None = None
    status: str | None = None
    episodes: int | None = None
    aired: _Aired = Field(default_factory=_Aired)

    @property
    def upcoming(self) -> bool:
        return self.status in UPCOMING_STATUS

    @property
    def start_date(self) -> date | None:
        if not self.aired.start:
            return None
        try:
            return datetime.fromisoformat(self.aired.start).date()
        except ValueError:
            return None


class _Entry(_Model):
    mal_id: int
    type: str


class _Relation(_Model):
    relation: str
    entry: tuple[_Entry, ...] = ()


class _Relations(_Model):
    data: tuple[_Relation, ...] = ()


class _AnimeBody(_Model):
    data: JikanAnime


class JikanClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = session or requests.Session()
        self._sleep = sleep
        self._budget = RateLimiter(BUDGET[0], BUDGET[1], clock=clock)

    def sequel_ids(self, mal_id: int) -> list[int]:
        body = self._get(f"/anime/{mal_id}/relations", _Relations)
        return [
            e.mal_id
            for r in body.data
            if r.relation == "Sequel"
            for e in r.entry
            if e.type == "anime"
        ]

    def anime(self, mal_id: int) -> JikanAnime:
        return self._get(f"/anime/{mal_id}", _AnimeBody).data

    def _get[M: BaseModel](self, path: str, shape: type[M]) -> M:
        for attempt in range(2):
            while not self._budget.hit("jikan"):
                self._sleep(1)
            try:
                response = self._http.get(
                    JIKAN_URL + path, timeout=TIMEOUT_SECONDS, allow_redirects=False
                )
            except requests.RequestException:
                raise JikanError("Jikan (MyAnimeList) cannot be reached") from None
            if response.status_code == 429 and attempt == 0:
                self._sleep(2)
                continue
            if response.status_code != 200:
                raise JikanError(f"Jikan answered HTTP {response.status_code}")
            try:
                return shape.model_validate_json(response.content)
            except ValidationError:
                raise JikanError("Unexpected response from Jikan") from None
        raise JikanError("Jikan rate limit reached")
