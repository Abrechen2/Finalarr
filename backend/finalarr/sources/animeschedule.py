"""AnimeSchedule.net API v3 (optional app token): English dub dates and delay notes.

Its terms ask for attribution and forbid bulk mirroring, so Finalarr asks only for
single anime the user follows, caches the answer and links back to the site.
"""

from __future__ import annotations

from datetime import UTC, datetime

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ANIMESCHEDULE_URL = "https://animeschedule.net/api/v3"
SITE_URL = "https://animeschedule.net/anime"
TIMEOUT_SECONDS = 10
_FIRST_REAL_YEAR = 1900  # the API writes "0001-01-01" for "unknown"


class AnimeScheduleError(RuntimeError):
    pass


class DubInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    route: str
    dub_premiere: datetime | None = Field(default=None, alias="dubPremier")
    dub_next: datetime | None = Field(default=None, alias="dubTime")
    delayed_until: datetime | None = Field(default=None, alias="delayedUntil")
    delay_note: str = Field(default="", alias="delayedDesc")

    @field_validator("dub_premiere", "dub_next", "delayed_until")
    @classmethod
    def _known(cls, value: datetime | None) -> datetime | None:
        if value is None or value.year < _FIRST_REAL_YEAR:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    @property
    def url(self) -> str:
        return f"{SITE_URL}/{self.route}"


class _Page(BaseModel):
    model_config = ConfigDict(extra="ignore")
    anime: tuple[DubInfo, ...] = ()


class AnimeScheduleClient:
    def __init__(self, token: str, session: requests.Session | None = None) -> None:
        self._token = token
        self._http = session or requests.Session()

    def by_mal_id(self, mal_id: int) -> DubInfo | None:
        try:
            response = self._http.get(
                f"{ANIMESCHEDULE_URL}/anime",
                params={"mal-ids": mal_id},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise AnimeScheduleError("AnimeSchedule cannot be reached") from None
        if response.status_code != 200:
            raise AnimeScheduleError(f"AnimeSchedule answered HTTP {response.status_code}")
        try:
            page = _Page.model_validate_json(response.content)
        except ValidationError:
            raise AnimeScheduleError("Unexpected response from AnimeSchedule") from None
        return page.anime[0] if page.anime else None
