"""Emby and Jellyfin (a fork of Emby): one client, two item routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from finalarr.sources.media.base import (
    DEFAULT_PAGE_SIZE,
    MediaError,
    MediaUserInfo,
    WatchedItem,
    get_json,
    tvdb_id,
)

SERIES_BATCH = 50


def _played_on(user_data: dict[str, Any]) -> date | None:
    raw = str(user_data.get("LastPlayedDate") or "")
    try:
        return datetime.fromisoformat(raw[:19]).date() if raw else None
    except ValueError:
        return None


class EmbyClient:
    name = "Emby"

    def __init__(
        self,
        url: str,
        token: str,
        session: requests.Session | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._url = url.rstrip("/")
        self._headers = {"X-Emby-Token": token, "Accept": "application/json"}
        self._http = session or requests.Session()
        self._page = page_size

    def _items_route(self, user_id: str) -> tuple[str, dict[str, str]]:
        return f"/Users/{user_id}/Items", {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return get_json(self._http, self.name, self._url + path, self._headers, params)

    def test(self) -> str:
        info = self._get("/System/Info")
        if not isinstance(info, dict):
            raise MediaError(f"Unexpected response from {self.name}")
        return f"{info.get('ServerName', self.name)} {info.get('Version', '')}".strip()

    def users(self) -> list[MediaUserInfo]:
        rows = self._get("/Users")
        if not isinstance(rows, list):
            raise MediaError(f"Unexpected response from {self.name}")
        return [
            MediaUserInfo(str(r["Id"]), str(r.get("Name") or r["Id"])) for r in rows if r.get("Id")
        ]

    def watched(self, user_id: str) -> list[WatchedItem]:
        path, extra = self._items_route(user_id)
        episodes: list[dict[str, Any]] = []
        start = 0
        while True:
            page = self._get(
                path,
                {
                    **extra,
                    "Recursive": "true",
                    "IncludeItemTypes": "Episode",
                    "IsPlayed": "true",
                    "Fields": "ProviderIds",
                    "EnableImages": "false",
                    "StartIndex": start,
                    "Limit": self._page,
                },
            )
            rows = page.get("Items") if isinstance(page, dict) else None
            if not isinstance(rows, list):
                raise MediaError(f"Unexpected response from {self.name}")
            episodes += rows
            start += len(rows)
            if not rows or start >= int(page.get("TotalRecordCount") or 0):
                break
        series_ids = sorted({str(e["SeriesId"]) for e in episodes if e.get("SeriesId")})
        tvdb = self._series_tvdb(path, extra, series_ids)
        return [
            WatchedItem(
                series_tvdb=tvdb.get(str(e.get("SeriesId"))),
                series_title=str(e.get("SeriesName") or ""),
                season=int(e["ParentIndexNumber"]),
                episode=int(e["IndexNumber"]),
                watched_on=_played_on(e.get("UserData") or {}),
            )
            for e in episodes
            if isinstance(e.get("ParentIndexNumber"), int) and isinstance(e.get("IndexNumber"), int)
        ]

    def _series_tvdb(
        self, path: str, extra: dict[str, str], series_ids: list[str]
    ) -> dict[str, int | None]:
        found: dict[str, int | None] = {}
        for i in range(0, len(series_ids), SERIES_BATCH):
            chunk = series_ids[i : i + SERIES_BATCH]
            page = self._get(path, {**extra, "Ids": ",".join(chunk), "Fields": "ProviderIds"})
            for row in page.get("Items", []) if isinstance(page, dict) else []:
                providers = {k.lower(): v for k, v in (row.get("ProviderIds") or {}).items()}
                found[str(row.get("Id"))] = tvdb_id(providers.get("tvdb"))
        return found


class JellyfinClient(EmbyClient):
    name = "Jellyfin"

    def _items_route(self, user_id: str) -> tuple[str, dict[str, str]]:
        # /Users/{id}/Items is deprecated since Jellyfin 10.9.
        return "/Items", {"userId": user_id}
