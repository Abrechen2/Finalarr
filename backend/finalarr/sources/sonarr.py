"""Sonarr v3/v4 API client (read-only). Responses are validated at the boundary.

Only three endpoints are needed: system status, the series list and the
episodes of one series. ``hasFile`` on each episode is enough to know what is
on disk, so episode files are never fetched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar
from urllib.parse import urlsplit

import requests
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

TIMEOUT_SECONDS = 10
_T = TypeVar("_T")


class SonarrError(RuntimeError):
    """Base class; messages are safe to show and never contain the API key."""


class SonarrUnreachable(SonarrError):
    pass


class SonarrAuthError(SonarrError):
    pass


class SonarrResponseError(SonarrError):
    pass


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)


class SonarrImage(_Model):
    cover_type: str = Field(alias="coverType")
    remote_url: str | None = Field(default=None, alias="remoteUrl")


class SonarrSeason(_Model):
    season_number: int = Field(alias="seasonNumber")
    monitored: bool = True


class SonarrSeries(_Model):
    id: int
    title: str
    sort_title: str = Field(default="", alias="sortTitle")
    title_slug: str = Field(default="", alias="titleSlug")
    year: int | None = None
    tvdb_id: int | None = Field(default=None, alias="tvdbId")
    series_type: str = Field(default="standard", alias="seriesType")
    status: str = ""
    monitored: bool = True
    images: tuple[SonarrImage, ...] = ()
    seasons: tuple[SonarrSeason, ...] = ()
    tags: tuple[int, ...] = ()
    overview: str = ""
    network: str = ""
    runtime: int | None = None
    genres: tuple[str, ...] = ()

    @property
    def poster_url(self) -> str | None:
        return self._image("poster")

    @property
    def fanart_url(self) -> str | None:
        return self._image("fanart")

    def _image(self, cover_type: str) -> str | None:
        return next((i.remote_url for i in self.images if i.cover_type == cover_type), None)


class SonarrEpisode(_Model):
    id: int
    series_id: int = Field(alias="seriesId")
    season_number: int = Field(alias="seasonNumber")
    episode_number: int = Field(alias="episodeNumber")
    absolute_episode_number: int | None = Field(default=None, alias="absoluteEpisodeNumber")
    title: str = ""
    air_date_utc: datetime | None = Field(default=None, alias="airDateUtc")
    monitored: bool = True
    has_file: bool = Field(default=False, alias="hasFile")
    finale_type: str | None = Field(default=None, alias="finaleType")


class SonarrTag(_Model):
    id: int
    label: str


class SonarrStatus(_Model):
    app_name: str = Field(default="", alias="appName")
    version: str = ""


def validate_base_url(url: str) -> str:
    """Accept only ``http(s)://host[:port][/path]`` without credentials."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("URL must start with http:// or https:// and name a host")
    if parts.username or parts.password:
        raise ValueError("URL must not contain credentials")
    return url.strip().rstrip("/")


class SonarrClient:
    def __init__(
        self, base_url: str, api_key: str, session: requests.Session | None = None
    ) -> None:
        self._base = validate_base_url(base_url)
        self._key = api_key
        self._http = session or requests.Session()

    def system_status(self) -> SonarrStatus:
        return self._get("/api/v3/system/status", SonarrStatus)

    def series_list(self) -> list[SonarrSeries]:
        return self._get("/api/v3/series", list[SonarrSeries])

    def tags(self) -> dict[int, str]:
        return {t.id: t.label for t in self._get("/api/v3/tag", list[SonarrTag])}

    def series(self, series_id: int) -> SonarrSeries:
        return self._get(f"/api/v3/series/{series_id}", SonarrSeries)

    def episodes(self, series_id: int) -> list[SonarrEpisode]:
        return self._get("/api/v3/episode", list[SonarrEpisode], {"seriesId": series_id})

    def _get(self, path: str, shape: type[_T], params: dict[str, Any] | None = None) -> _T:
        try:
            response = self._http.get(
                self._base + path,
                params=params,
                headers={"X-Api-Key": self._key, "Accept": "application/json"},
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise SonarrUnreachable(f"Sonarr did not answer within {TIMEOUT_SECONDS} s") from None
        except requests.RequestException:
            raise SonarrUnreachable("Sonarr cannot be reached") from None
        if response.status_code in (401, 403):
            raise SonarrAuthError("Sonarr rejected the API key")
        if response.is_redirect:
            raise SonarrResponseError("Sonarr answered with a redirect; check the URL")
        if response.status_code != 200:
            raise SonarrResponseError(f"Sonarr answered HTTP {response.status_code} for {path}")
        try:
            return TypeAdapter(shape).validate_json(response.content)
        except ValidationError:
            raise SonarrResponseError(f"Unexpected response from Sonarr for {path}") from None
