"""TVmaze API client (free, no key): early season announcements for TV series.

TVmaze answers 20 requests per 10 s per IP; Finalarr keeps its own budget below
that and waits instead of failing, since it only runs in background jobs.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import date, datetime

import requests
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from finalarr.ratelimit import RateLimiter

TVMAZE_URL = "https://api.tvmaze.com"
TIMEOUT_SECONDS = 10
DEFAULT_BUDGET = (15, 10)  # requests, seconds
_SHOW_LOCATION = re.compile(r"^https://api\.tvmaze\.com/shows/(\d+)$")


class TvmazeError(RuntimeError):
    pass


class TvmazeSeason(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    number: int
    premiere_date: date | None = Field(default=None, alias="premiereDate")
    end_date: date | None = Field(default=None, alias="endDate")
    episode_order: int | None = Field(default=None, alias="episodeOrder")


class _Named(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""


class _NextEpisode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    season: int | None = None
    number: int | None = None
    airstamp: datetime | None = None


class _Embedded(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nextepisode: _NextEpisode | None = None


class TvmazeShow(BaseModel):
    """Channel and next episode of a show (``/shows/{id}?embed=nextepisode``)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    network: _Named | None = None
    web_channel: _Named | None = Field(default=None, alias="webChannel")
    embedded: _Embedded = Field(default_factory=_Embedded, alias="_embedded")

    @property
    def channel(self) -> str | None:
        named = self.web_channel or self.network
        return named.name if named and named.name else None

    @property
    def next_at(self) -> datetime | None:
        return self.embedded.nextepisode.airstamp if self.embedded.nextepisode else None

    @property
    def next_season(self) -> int | None:
        return self.embedded.nextepisode.season if self.embedded.nextepisode else None

    @property
    def next_number(self) -> int | None:
        return self.embedded.nextepisode.number if self.embedded.nextepisode else None


class TvmazeClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        budget: tuple[int, float] = DEFAULT_BUDGET,
    ) -> None:
        self._http = session or requests.Session()
        self._sleep = sleep
        self._budget = RateLimiter(budget[0], budget[1], clock=clock)
        self._window = budget[1]

    def show_id_for_tvdb(self, tvdb_id: int) -> int | None:
        response = self._get("/lookup/shows", {"thetvdb": tvdb_id})
        if response.status_code == 404:
            return None
        match = _SHOW_LOCATION.match(response.headers.get("Location", ""))
        if response.status_code not in (301, 302) or not match:
            raise TvmazeError("Unexpected TVmaze lookup answer")
        return int(match[1])

    def seasons(self, show_id: int) -> list[TvmazeSeason]:
        response = self._get(f"/shows/{show_id}/seasons")
        if response.status_code != 200:
            raise TvmazeError(f"TVmaze answered HTTP {response.status_code}")
        try:
            return TypeAdapter(list[TvmazeSeason]).validate_json(response.content)
        except ValidationError:
            raise TvmazeError("Unexpected response from TVmaze") from None

    def show(self, show_id: int) -> TvmazeShow:
        response = self._get(f"/shows/{show_id}", {"embed": "nextepisode"})
        if response.status_code != 200:
            raise TvmazeError(f"TVmaze answered HTTP {response.status_code}")
        try:
            return TvmazeShow.model_validate_json(response.content)
        except ValidationError:
            raise TvmazeError("Unexpected response from TVmaze") from None

    def _get(self, path: str, params: dict[str, int | str] | None = None) -> requests.Response:
        for attempt in range(2):
            while not self._budget.hit("tvmaze"):
                self._sleep(self._window / 4)
            try:
                response = self._http.get(
                    TVMAZE_URL + path, params=params, timeout=TIMEOUT_SECONDS, allow_redirects=False
                )
            except requests.RequestException:
                raise TvmazeError("TVmaze cannot be reached") from None
            if response.status_code != 429:
                return response
            if attempt == 0:
                retry = response.headers.get("Retry-After", "")
                self._sleep(int(retry) if retry.isdigit() else self._window)
        raise TvmazeError("TVmaze rate limit reached")
