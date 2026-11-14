"""Plex: watch history per account through the owner's token (works for Plex Home
managed users too, which have no login of their own)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
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

SHOW_BATCH = 50
TVDB_GUID = "tvdb://"
LEGACY_TVDB = re.compile(r"^com\.plexapp\.agents\.thetvdb://(\d+)")


def _container(body: Any, name: str) -> dict[str, Any]:
    container = body.get("MediaContainer") if isinstance(body, dict) else None
    if not isinstance(container, dict):
        raise MediaError(f"Unexpected response from {name}")
    return container


class PlexClient:
    name = "Plex"

    def __init__(
        self,
        url: str,
        token: str,
        session: requests.Session | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._http = session or requests.Session()
        self._page = page_size

    def _get(
        self, path: str, params: dict[str, Any] | None = None, start: int | None = None
    ) -> dict[str, Any]:
        headers = {"X-Plex-Token": self._token, "Accept": "application/json"}
        if start is not None:
            headers |= {
                "X-Plex-Container-Start": str(start),
                "X-Plex-Container-Size": str(self._page),
            }
        return _container(
            get_json(self._http, self.name, self._url + path, headers, params), self.name
        )

    def test(self) -> str:
        info = self._get("/")
        return f"{info.get('friendlyName', self.name)} {info.get('version', '')}".strip()

    def users(self) -> list[MediaUserInfo]:
        # Account 0 is the server's internal system account.
        return [
            MediaUserInfo(str(a["id"]), str(a.get("name") or a["id"]))
            for a in self._get("/accounts").get("Account", [])
            if a.get("id") and a.get("name")
        ]

    def watched(self, user_id: str) -> list[WatchedItem]:
        latest: dict[str, dict[str, Any]] = {}
        start = 0
        while True:
            page = self._get(
                "/status/sessions/history/all",
                {"accountID": user_id, "sort": "viewedAt:desc"},
                start=start,
            )
            rows = page.get("Metadata", [])
            for row in rows:
                if row.get("type") != "episode":
                    continue
                key = str(row.get("ratingKey"))
                if key not in latest or int(row.get("viewedAt") or 0) > int(
                    latest[key].get("viewedAt") or 0
                ):
                    latest[key] = row
            start += len(rows)
            if not rows or start >= int(page.get("totalSize") or page.get("size") or 0):
                break
        shows = sorted(
            {
                str(r["grandparentRatingKey"])
                for r in latest.values()
                if r.get("grandparentRatingKey")
            }
        )
        tvdb = self._show_tvdb(shows)
        return [
            WatchedItem(
                series_tvdb=tvdb.get(str(r.get("grandparentRatingKey"))),
                series_title=str(r.get("grandparentTitle") or ""),
                season=int(r["parentIndex"]),
                episode=int(r["index"]),
                watched_on=(
                    datetime.fromtimestamp(int(r["viewedAt"]), UTC).date()
                    if r.get("viewedAt")
                    else None
                ),
            )
            for r in latest.values()
            if isinstance(r.get("parentIndex"), int) and isinstance(r.get("index"), int)
        ]

    def _show_tvdb(self, keys: list[str]) -> dict[str, int | None]:
        found: dict[str, int | None] = {}
        for i in range(0, len(keys), SHOW_BATCH):
            chunk = keys[i : i + SHOW_BATCH]
            body = self._get(f"/library/metadata/{','.join(chunk)}", {"includeGuids": 1})
            for show in body.get("Metadata", []):
                guids = [str(g.get("id", "")) for g in show.get("Guid", [])]
                tvdb = next(
                    (tvdb_id(g[len(TVDB_GUID) :]) for g in guids if g.startswith(TVDB_GUID)), None
                )
                if tvdb is None and (legacy := LEGACY_TVDB.match(str(show.get("guid", "")))):
                    tvdb = int(legacy[1])  # libraries still on the old TheTVDB agent
                found[str(show.get("ratingKey"))] = tvdb
        return found
