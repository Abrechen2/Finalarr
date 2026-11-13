"""AniList media cache in the database (TTL per PLAN.md section 9)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select

from finalarr.db.models import AnilistCache
from finalarr.db.session import Database
from finalarr.sources.anilist import AnilistMedia

RELEASING_TTL = timedelta(minutes=15)
FINISHED_TTL = timedelta(days=7)
MISS_TTL = timedelta(hours=1)
AIRING_SLACK = timedelta(minutes=1)
_FINISHED = {"FINISHED", "CANCELLED"}


class _Client(Protocol):
    def media_batch(self, ids: list[int]) -> dict[int, AnilistMedia]: ...

    def search(self, text: str) -> list[AnilistMedia]: ...


def _key(media_id: int) -> str:
    return f"media:{media_id}"


def ttl_for(media: AnilistMedia | None, now: datetime) -> datetime:
    if media is None:
        return now + MISS_TTL
    if media.status in _FINISHED:
        return now + FINISHED_TTL
    expiry = now + RELEASING_TTL
    if media.next_airing_at is not None:
        expiry = min(expiry, media.next_airing_at + AIRING_SLACK)
    return expiry


class CachedAnilist:
    def __init__(
        self,
        db: Database,
        client: _Client,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = db
        self._client = client
        self._clock = clock

    def search(self, text: str) -> list[AnilistMedia]:
        return self._client.search(text)

    def media(self, ids: list[int]) -> dict[int, AnilistMedia]:
        now = self._clock()
        found: dict[int, AnilistMedia] = {}
        fresh: set[int] = set()
        with self._db.session() as s:
            rows = s.scalars(
                select(AnilistCache).where(AnilistCache.key.in_([_key(i) for i in ids]))
            )
            for row in rows:
                expires = (
                    row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
                )
                if expires <= now:
                    continue
                media_id = int(row.key.split(":", 1)[1])
                fresh.add(media_id)
                if row.body_json != "null":
                    found[media_id] = AnilistMedia.model_validate_json(row.body_json)
        missing = [i for i in dict.fromkeys(ids) if i not in fresh]
        if not missing:
            return found
        fetched = self._client.media_batch(missing)
        with self._db.session() as s:
            for media_id in missing:
                media = fetched.get(media_id)
                body = media.model_dump_json(by_alias=True) if media else "null"
                s.merge(
                    AnilistCache(key=_key(media_id), body_json=body, expires_at=ttl_for(media, now))
                )
            s.commit()
        return found | fetched
