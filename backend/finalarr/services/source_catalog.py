"""Every outside data source Finalarr uses, with its terms, and the user's on/off switch.

Sonarr is not listed: without it there is nothing to do. The UI explains each source's
use and terms (i18n keys by id); the backend only knows ids, links and switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from finalarr.services.settings_store import load_settings, save_settings


@dataclass(frozen=True)
class SourceInfo:
    id: str
    name: str
    url: str
    terms_url: str
    # Settings attribute that holds the source's key; None = works without one.
    key_setting: str | None = None
    # Feeds the season logic itself; switching it off loses core features.
    core: bool = False


CATALOG: tuple[SourceInfo, ...] = (
    SourceInfo(
        "anilist",
        "AniList",
        "https://anilist.co",
        "https://docs.anilist.co/guide/terms-of-use",
        core=True,
    ),
    SourceInfo(
        "fribb",
        "Fribb's anime-lists",
        "https://github.com/Fribb/anime-lists",
        "https://github.com/Fribb/anime-lists",
        core=True,
    ),
    SourceInfo("jikan", "MyAnimeList (Jikan)", "https://myanimelist.net", "https://jikan.moe"),
    SourceInfo(
        "tvmaze", "TVmaze", "https://www.tvmaze.com", "https://www.tvmaze.com/api#licensing"
    ),
    SourceInfo(
        "tmdb",
        "TMDB",
        "https://www.themoviedb.org",
        "https://www.themoviedb.org/api-terms-of-use",
        key_setting="tmdb_api_key",
    ),
    SourceInfo(
        "trakt",
        "Trakt",
        "https://trakt.tv",
        "https://trakt.tv/terms",
        key_setting="trakt_client_id",
    ),
    SourceInfo(
        "animeschedule",
        "AnimeSchedule.net",
        "https://animeschedule.net",
        "https://animeschedule.net/api/v3/documentation",
        key_setting="animeschedule_token",
    ),
    SourceInfo(
        "livechart", "LiveChart.me", "https://www.livechart.me", "https://www.livechart.me/terms"
    ),
    SourceInfo(
        "animenewsnetwork",
        "Anime News Network",
        "https://www.animenewsnetwork.com",
        "https://www.animenewsnetwork.com/copyright-policy",
    ),
    SourceInfo(
        "anime2you", "Anime2You", "https://www.anime2you.de", "https://www.anime2you.de/impressum/"
    ),
    SourceInfo(
        "crunchyroll",
        "Crunchyroll News",
        "https://www.crunchyroll.com/news",
        "https://www.crunchyroll.com/tos",
    ),
    SourceInfo(
        "google_news", "Google News", "https://news.google.com", "https://policies.google.com/terms"
    ),
    SourceInfo("youtube", "YouTube", "https://www.youtube.com", "https://www.youtube.com/t/terms"),
)
IDS = frozenset(s.id for s in CATALOG)


def disabled_sources(session: Session) -> frozenset[str]:
    values = load_settings(session)
    off = set(values["sources_disabled"]) & IDS
    # The older rules switch for the web news search is the same thing.
    if not values["series_news_web"]:
        off.add("google_news")
    return frozenset(off)


def set_source(session: Session, source_id: str, enabled: bool) -> None:
    if source_id not in IDS:
        raise KeyError(source_id)
    off = set(load_settings(session)["sources_disabled"]) & IDS
    off = off - {source_id} if enabled else off | {source_id}
    changes: dict[str, Any] = {"sources_disabled": sorted(off)}
    if source_id == "google_news":
        changes["series_news_web"] = enabled
    save_settings(session, changes)


def source_views(session: Session, settings: Any) -> list[dict[str, Any]]:
    off = disabled_sources(session)
    return [
        {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "terms_url": s.terms_url,
            "core": s.core,
            "needs_key": s.key_setting is not None,
            "configured": s.key_setting is None or getattr(settings, s.key_setting) is not None,
            "enabled": s.id not in off,
        }
        for s in CATALOG
    ]
