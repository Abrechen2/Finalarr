"""TMDB API (needs a free key): season list with air dates, often early."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

TMDB_URL = "https://api.themoviedb.org/3"
TIMEOUT_SECONDS = 10

SeasonRow = tuple[int, date | None, int | None]


class TmdbError(RuntimeError):
    pass


@dataclass(frozen=True)
class TmdbExtras:
    trailer: str | None
    providers: tuple[str, ...]  # subscription services in the country
    link: str | None  # TMDB watch page (JustWatch data, needs attribution)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class TmdbClient:
    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        self._key = api_key
        self._http = session or requests.Session()

    def tv_id_for_tvdb(self, tvdb_id: int) -> int | None:
        body = self._get(f"/find/{tvdb_id}", {"external_source": "tvdb_id"})
        results = body.get("tv_results") or []
        return int(results[0]["id"]) if results else None

    def seasons(self, tv_id: int) -> list[SeasonRow]:
        body = self._get(f"/tv/{tv_id}")
        return [
            (int(s["season_number"]), _date(s.get("air_date")), s.get("episode_count") or None)
            for s in body.get("seasons") or []
        ]

    def extras(self, tv_id: int, country: str) -> TmdbExtras:
        body = self._get(f"/tv/{tv_id}", {"append_to_response": "videos,watch/providers"})
        videos = (body.get("videos") or {}).get("results") or []
        trailer = next(
            (
                v.get("key")
                for v in videos
                if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")
            ),
            None,
        )
        region = ((body.get("watch/providers") or {}).get("results") or {}).get(country) or {}
        providers = tuple(
            p["provider_name"] for p in region.get("flatrate") or [] if p.get("provider_name")
        )
        link = region.get("link")
        return TmdbExtras(
            trailer,
            providers,
            link if isinstance(link, str) and link.startswith("https://") else None,
        )

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        headers = {"Accept": "application/json"}
        if self._key.startswith("eyJ"):  # v4 read access token
            headers["Authorization"] = f"Bearer {self._key}"
        else:
            query["api_key"] = self._key
        try:
            response = self._http.get(
                TMDB_URL + path,
                params=query,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise TmdbError("TMDB cannot be reached") from None
        if response.status_code != 200:
            raise TmdbError(f"TMDB answered HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise TmdbError("Unexpected response from TMDB") from None
        if not isinstance(body, dict):
            raise TmdbError("Unexpected response from TMDB")
        return body
