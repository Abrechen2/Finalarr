"""AniList GraphQL client (public API, no key). PLAN.md 4.1 and section 9.

AniList allows 90 requests/min nominally and 30/min while degraded; Finalarr
keeps its own budget well below that and honours 429 ``Retry-After``. Media are
fetched in batches of up to 50 ids per request.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from finalarr.ratelimit import RateLimiter

ANILIST_URL = "https://graphql.anilist.co"
TIMEOUT_SECONDS = 10
BATCH_SIZE = 50
DEFAULT_BUDGET_PER_MINUTE = 10
DEFAULT_RETRY_SECONDS = 60

_FIELDS = """
id format status episodes seasonYear
title { romaji english } synonyms
startDate { year month day } endDate { year month day }
nextAiringEpisode { episode airingAt }
relations { edges { relationType node { id type format status episodes } } }
"""
_BATCH_QUERY = "query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){" + _FIELDS + "}}}"
_SEARCH_QUERY = (
    "query($search:String){Page(perPage:10){media(search:$search,type:ANIME){" + _FIELDS + "}}}"
)


class AnilistError(RuntimeError):
    pass


class AnilistRateLimited(AnilistError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"AniList rate limit reached; retry in {retry_after} s")
        self.retry_after = retry_after


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


class _FuzzyDate(_Model):
    year: int | None = None
    month: int | None = None
    day: int | None = None

    def to_date(self) -> date | None:
        if self.year is None:
            return None
        return date(self.year, self.month or 1, self.day or 1)


class _Title(_Model):
    romaji: str | None = None
    english: str | None = None


class _Node(_Model):
    id: int
    type: str | None = None
    format: str | None = None
    status: str | None = None
    episodes: int | None = None


class _Edge(_Model):
    relation_type: str = Field(alias="relationType")
    node: _Node


class _Relations(_Model):
    edges: tuple[_Edge, ...] = ()


class _NextAiring(_Model):
    episode: int
    airing_at: int = Field(alias="airingAt")


class AnilistMedia(_Model):
    id: int
    format: str | None = None
    status: str | None = None
    episodes: int | None = None
    season_year: int | None = Field(default=None, alias="seasonYear")
    titles: _Title = Field(alias="title")
    synonyms: tuple[str, ...] = ()
    start: _FuzzyDate = Field(default_factory=_FuzzyDate, alias="startDate")
    end: _FuzzyDate = Field(default_factory=_FuzzyDate, alias="endDate")
    next_airing: _NextAiring | None = Field(default=None, alias="nextAiringEpisode")
    relations: _Relations = Field(default_factory=_Relations)

    @property
    def title(self) -> str:
        return self.titles.english or self.titles.romaji or f"AniList {self.id}"

    @property
    def start_date(self) -> date | None:
        return self.start.to_date()

    @property
    def end_date(self) -> date | None:
        return self.end.to_date()

    @property
    def next_airing_at(self) -> datetime | None:
        return datetime.fromtimestamp(self.next_airing.airing_at, UTC) if self.next_airing else None

    @property
    def relation_ids(self) -> list[tuple[str, int]]:
        return [(e.relation_type, e.node.id) for e in self.relations.edges]


class _Page(_Model):
    media: tuple[AnilistMedia, ...] = ()


class _Data(_Model):
    page: _Page = Field(alias="Page")


class _Response(_Model):
    data: _Data | None = None
    errors: tuple[dict[str, Any], ...] | None = None


class AnilistClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        budget_per_minute: int = DEFAULT_BUDGET_PER_MINUTE,
    ) -> None:
        self._http = session or requests.Session()
        self._budget = RateLimiter(budget_per_minute, 60)

    def media_batch(self, ids: list[int]) -> dict[int, AnilistMedia]:
        found: dict[int, AnilistMedia] = {}
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start : start + BATCH_SIZE]
            for media in self._query(_BATCH_QUERY, {"ids": chunk}):
                found[media.id] = media
        return found

    def search(self, text: str) -> list[AnilistMedia]:
        return list(self._query(_SEARCH_QUERY, {"search": text}))

    def _query(self, query: str, variables: dict[str, Any]) -> tuple[AnilistMedia, ...]:
        if not self._budget.hit("anilist"):
            raise AnilistRateLimited(DEFAULT_RETRY_SECONDS)
        try:
            response = self._http.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                headers={"Accept": "application/json"},
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise AnilistError("AniList cannot be reached") from None
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "")
            raise AnilistRateLimited(int(retry) if retry.isdigit() else DEFAULT_RETRY_SECONDS)
        if response.status_code != 200:
            raise AnilistError(f"AniList answered HTTP {response.status_code}")
        try:
            body = _Response.model_validate_json(response.content)
        except ValidationError:
            raise AnilistError("Unexpected response from AniList") from None
        if body.errors or body.data is None:
            raise AnilistError("AniList reported an error for the query")
        return body.data.page.media
