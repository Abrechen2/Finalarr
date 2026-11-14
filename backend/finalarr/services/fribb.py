"""TVDB season → AniList id mapping from Fribb's anime-lists.

AniList has no TVDB lookup, so this community list is the bridge. It is
refreshed weekly; manual pins (source "manual") are never touched.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import requests
from sqlalchemy import delete
from sqlalchemy.orm import Session

from finalarr.db.models import AnilistCache, AnilistMapping, FribbId
from finalarr.db.session import Database
from finalarr.services.source_catalog import disabled_sources

log = logging.getLogger(__name__)

FRIBB_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
REFRESH_AFTER = timedelta(days=7)
META_KEY = "meta:fribb"
DOWNLOAD_TIMEOUT = 60

Mapping = tuple[int, int, int]  # (tvdb_id, tvdb_season, anilist_id)


def parse_fribb(raw: bytes) -> list[Mapping]:
    rows: set[Mapping] = set()
    for entry in json.loads(raw):
        tvdb, anilist = entry.get("tvdb_id"), entry.get("anilist_id")
        season = (entry.get("season") or {}).get("tvdb")
        if isinstance(tvdb, int) and isinstance(anilist, int) and isinstance(season, int):
            rows.add((tvdb, season, anilist))
    return sorted(rows)


def parse_fribb_ids(raw: bytes) -> list[tuple[int, int]]:
    """(anilist_id, mal_id) pairs, including entries Fribb has not mapped to TVDB yet."""
    pairs: dict[int, int] = {}
    for entry in json.loads(raw):
        anilist, mal = entry.get("anilist_id"), entry.get("mal_id")
        if isinstance(anilist, int) and isinstance(mal, int):
            pairs[anilist] = mal
    return sorted(pairs.items())


def download_fribb() -> bytes:
    response = requests.get(FRIBB_URL, timeout=DOWNLOAD_TIMEOUT, allow_redirects=False)
    response.raise_for_status()
    return response.content


def store_fribb(
    session: Session,
    rows: list[Mapping],
    now: datetime,
    ids: list[tuple[int, int]] | None = None,
) -> None:
    session.execute(delete(AnilistMapping).where(AnilistMapping.source == "fribb"))
    if ids is not None:
        session.execute(delete(FribbId))
        session.add_all(FribbId(anilist_id=a, mal_id=mal) for a, mal in ids)
    session.add_all(
        AnilistMapping(tvdb_id=t, tvdb_season=s, anilist_id=a, source="fribb", fetched_at=now)
        for t, s, a in rows
    )
    session.merge(AnilistCache(key=META_KEY, body_json="{}", expires_at=now + REFRESH_AFTER))


def fribb_is_stale(session: Session, now: datetime) -> bool:
    meta = session.get(AnilistCache, META_KEY)
    if meta is None:
        return True
    expires = (
        meta.expires_at if meta.expires_at.tzinfo else meta.expires_at.replace(tzinfo=now.tzinfo)
    )
    return expires <= now


def refresh_if_stale(
    db: Database,
    download: Callable[[], bytes] = download_fribb,
    now: datetime | None = None,
) -> bool:
    """Weekly refresh; a failed download keeps the old mapping."""
    moment = now or datetime.now(UTC)
    with db.session() as s:
        if "fribb" in disabled_sources(s) or not fribb_is_stale(s, moment):
            return False
    try:
        raw = download()
        rows, ids = parse_fribb(raw), parse_fribb_ids(raw)
    except (requests.RequestException, ValueError) as error:
        log.warning("Fribb anime-lists refresh failed: %s", error)
        return False
    with db.session() as s:
        store_fribb(s, rows, moment, ids=ids)
        s.commit()
    log.info("Fribb anime-lists refreshed: %d TVDB season mappings", len(rows))
    return True
