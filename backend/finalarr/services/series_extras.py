"""Extras for one series page: next episode, trailer, where to watch, English dub.

Sonarr's own dates come first; AniList (anime), TVmaze and the optional TMDB and
AnimeSchedule sources fill in. Remote answers are cached; a failing source only
drops its part and is named in ``errors``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.db import models as m
from finalarr.services.season_sources import ID_TTL, MISSING_ID_TTL, JsonCache
from finalarr.sources.anilist import AnilistError, AnilistMedia
from finalarr.sources.animeschedule import AnimeScheduleClient, AnimeScheduleError
from finalarr.sources.tmdb import TmdbClient, TmdbError
from finalarr.sources.tvmaze import TvmazeClient, TvmazeError

SHOW_TTL = timedelta(hours=6)
DUB_TTL = timedelta(hours=12)


class _Anilist(Protocol):
    def media(self, ids: list[int]) -> dict[int, AnilistMedia]: ...


@dataclass(frozen=True)
class ExtrasSources:
    cache: JsonCache
    tvmaze: TvmazeClient | None
    anilist: _Anilist | None = None
    tmdb: TmdbClient | None = None
    animeschedule: AnimeScheduleClient | None = None
    region: str = "DE"


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _sonarr_next(series: m.Series, now: datetime) -> dict[str, Any] | None:
    upcoming = [
        (aired, season.number, episode.number)
        for season in series.seasons
        if season.number > 0
        for episode in season.episodes
        if (aired := _utc(episode.air_date_utc)) is not None and aired > now
    ]
    if not upcoming:
        return None
    aired, season, number = min(upcoming)
    return {"season": season, "episode": number, "at": aired.isoformat(), "source": "sonarr"}


def _latest_anilist(s: Session, series: m.Series) -> tuple[int | None, list[int]]:
    """AniList ids mapped to the highest TVDB season (manual pins win)."""
    if series.series_type != "anime" or series.tvdb_id is None:
        return None, []
    rows = s.scalars(
        select(m.AnilistMapping).where(m.AnilistMapping.tvdb_id == series.tvdb_id)
    ).all()
    if not rows:
        return None, []
    season = max(r.tvdb_season for r in rows)
    current = [r for r in rows if r.tvdb_season == season]
    manual = [r for r in current if r.source == "manual"]
    return season, sorted({r.anilist_id for r in (manual or current)})


class _Collector:
    def __init__(self, sources: ExtrasSources, now: datetime) -> None:
        self.sources = sources
        self.now = now
        self.errors: list[str] = []

    def tvmaze_show(self, tvdb_id: int | None) -> dict[str, Any] | None:
        client = self.sources.tvmaze
        if client is None or tvdb_id is None:
            return None
        cache = self.sources.cache
        try:
            show_id = cache.remember(
                f"tvmaze:show:{tvdb_id}",
                ID_TTL,
                lambda: client.show_id_for_tvdb(tvdb_id),
                MISSING_ID_TTL,
            )
            if show_id is None:
                return None
            body: dict[str, Any] = cache.remember(
                f"tvmaze:info:{show_id}", SHOW_TTL, lambda: _show_json(client, show_id)
            )
        except TvmazeError:
            self.errors.append("tvmaze")
            return None
        return body

    def anilist(self, ids: list[int]) -> list[AnilistMedia]:
        if self.sources.anilist is None or not ids:
            return []
        try:
            found = self.sources.anilist.media(ids)
        except AnilistError:
            self.errors.append("anilist")
            return []
        return [found[i] for i in ids if i in found]

    def tmdb(self, tvdb_id: int | None) -> dict[str, Any] | None:
        client = self.sources.tmdb
        if client is None or tvdb_id is None:
            return None
        cache, region = self.sources.cache, self.sources.region
        try:
            tv_id = cache.remember(
                f"tmdb:show:{tvdb_id}",
                ID_TTL,
                lambda: client.tv_id_for_tvdb(tvdb_id),
                MISSING_ID_TTL,
            )
            if tv_id is None:
                return None
            body: dict[str, Any] = cache.remember(
                f"tmdb:extras:{tv_id}:{region}", SHOW_TTL, lambda: _tmdb_json(client, tv_id, region)
            )
        except TmdbError:
            self.errors.append("tmdb")
            return None
        return body

    def dub(self, mal_id: int | None) -> dict[str, Any] | None:
        client = self.sources.animeschedule
        if client is None or mal_id is None:
            return None
        try:
            body: dict[str, Any] | None = self.sources.cache.remember(
                f"animeschedule:{mal_id}", DUB_TTL, lambda: _dub_json(client, mal_id)
            )
        except AnimeScheduleError:
            self.errors.append("animeschedule")
            return None
        return body


def _show_json(client: TvmazeClient, show_id: int) -> dict[str, Any]:
    show = client.show(show_id)
    return {
        "channel": show.channel,
        "next": {
            "season": show.next_season,
            "episode": show.next_number,
            "at": show.next_at.isoformat(),
        }
        if show.next_at
        else None,
    }


def _tmdb_json(client: TmdbClient, tv_id: int, region: str) -> dict[str, Any]:
    extras = client.extras(tv_id, region)
    return {"trailer": extras.trailer, "providers": list(extras.providers), "link": extras.link}


def _dub_json(client: AnimeScheduleClient, mal_id: int) -> dict[str, Any] | None:
    info = client.by_mal_id(mal_id)
    if info is None:
        return None
    return {
        "premiere": info.dub_premiere.isoformat() if info.dub_premiere else None,
        "next": info.dub_next.isoformat() if info.dub_next else None,
        "delayed_until": info.delayed_until.isoformat() if info.delayed_until else None,
        "delay_note": info.delay_note,
        "url": info.url,
    }


def _future(entry: dict[str, Any] | None, now: datetime) -> dict[str, Any] | None:
    if not entry or not entry.get("at"):
        return None
    return entry if datetime.fromisoformat(entry["at"]) > now else None


def _anilist_next(media: list[AnilistMedia], season: int | None) -> dict[str, Any] | None:
    airing = [
        (at, x.next_airing.episode)
        for x in media
        if x.next_airing is not None and (at := x.next_airing_at) is not None
    ]
    if not airing:
        return None
    at, episode = min(airing)
    return {"season": season, "episode": episode, "at": at.isoformat(), "source": "anilist"}


def series_extras(
    s: Session, series: m.Series, sources: ExtrasSources, now: datetime
) -> dict[str, Any]:
    collect = _Collector(sources, now)
    season, anilist_ids = _latest_anilist(s, series)
    media = collect.anilist(anilist_ids)
    show = collect.tvmaze_show(series.tvdb_id)
    tmdb = collect.tmdb(series.tvdb_id)
    mal_id = (
        s.scalar(select(m.FribbId.mal_id).where(m.FribbId.anilist_id == anilist_ids[0]))
        if anilist_ids and sources.animeschedule
        else None
    )
    tvmaze_next = show.get("next") if show else None
    next_episode = (
        _sonarr_next(series, now)
        or _future(_anilist_next(media, season), now)
        or _future({**tvmaze_next, "source": "tvmaze"} if tvmaze_next else None, now)
    )
    trailer = next((x.youtube_trailer for x in media if x.youtube_trailer), None) or (
        tmdb or {}
    ).get("trailer")
    watch: list[dict[str, str | None]] = [
        {"name": site, "url": url, "source": "anilist"}
        for x in media[:1]
        for site, url in x.streaming_links
    ]
    known = {str(w["name"]).lower() for w in watch}
    watch += [
        {"name": name, "url": (tmdb or {}).get("link"), "source": "tmdb"}
        for name in (tmdb or {}).get("providers", [])
        if name.lower() not in known
    ]
    return {
        "next_episode": next_episode,
        "trailer": {"youtube_id": trailer} if trailer else None,
        "channel": (show or {}).get("channel") or series.network or None,
        "watch": watch,
        "watch_region": sources.region if tmdb else None,
        "dub": collect.dub(mal_id),
        "errors": collect.errors,
    }
