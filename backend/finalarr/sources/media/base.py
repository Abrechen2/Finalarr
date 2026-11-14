"""Shared types and HTTP handling for the media server clients."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import requests

TIMEOUT_SECONDS = 20
DEFAULT_PAGE_SIZE = 500


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaUserInfo:
    remote_id: str
    name: str


@dataclass(frozen=True)
class WatchedItem:
    series_tvdb: int | None  # None: the server knows no TVDB id, the series stays unmatched
    series_title: str
    season: int
    episode: int
    watched_on: date | None


class MediaClient(Protocol):
    def __init__(self, url: str, token: str) -> None: ...

    def test(self) -> str: ...

    def users(self) -> list[MediaUserInfo]: ...

    def watched(self, user_id: str) -> list[WatchedItem]: ...


def get_json(
    http: requests.Session,
    name: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> Any:
    """GET a JSON document; errors name the server, never the token."""
    try:
        response = http.get(
            url, params=params, headers=headers, timeout=TIMEOUT_SECONDS, allow_redirects=False
        )
    except requests.RequestException:
        raise MediaError(f"{name} cannot be reached") from None
    if response.status_code in (401, 403):
        raise MediaError(f"{name} rejected the token")
    if response.status_code != 200:
        raise MediaError(f"{name} answered HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError:
        raise MediaError(f"Unexpected response from {name}") from None


def tvdb_id(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None
