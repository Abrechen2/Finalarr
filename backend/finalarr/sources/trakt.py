"""Trakt API (needs a free client id): season list with first air dates."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

TRAKT_URL = "https://api.trakt.tv"
TIMEOUT_SECONDS = 10

SeasonRow = tuple[int, date | None, int | None]


class TraktError(RuntimeError):
    pass


def _date(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date() if value else None
    except ValueError:
        return None


class TraktClient:
    def __init__(self, client_id: str, session: requests.Session | None = None) -> None:
        self._client_id = client_id
        self._http = session or requests.Session()

    def show_id_for_tvdb(self, tvdb_id: int) -> int | None:
        body = self._get(f"/search/tvdb/{tvdb_id}", {"type": "show"})
        shows = [r["show"] for r in body if isinstance(r, dict) and r.get("type") == "show"]
        return int(shows[0]["ids"]["trakt"]) if shows else None

    def seasons(self, show_id: int) -> list[SeasonRow]:
        body = self._get(f"/shows/{show_id}/seasons", {"extended": "full"})
        return [
            (int(s["number"]), _date(s.get("first_aired")), s.get("episode_count") or None)
            for s in body
            if isinstance(s, dict)
        ]

    def _get(self, path: str, params: dict[str, str]) -> list[Any]:
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self._client_id,
        }
        try:
            response = self._http.get(
                TRAKT_URL + path,
                params=params,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise TraktError("Trakt cannot be reached") from None
        if response.status_code != 200:
            raise TraktError(f"Trakt answered HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise TraktError("Unexpected response from Trakt") from None
        if not isinstance(body, list):
            raise TraktError("Unexpected response from Trakt")
        return body
