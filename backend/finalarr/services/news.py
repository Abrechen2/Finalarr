"""News hints: recent headlines that name a followed series (``news_mention``).

Headlines are free text, so matching is deliberately strict: the normalised
series title (or an AniList title of it) must appear as a whole phrase and be
long enough not to match by accident. A hint links to the article; it is not
an announcement the state machine relies on.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from finalarr.core.fingerprint import fingerprint
from finalarr.db import models as m
from finalarr.db.session import Database
from finalarr.services.settings_store import load_settings
from finalarr.sources.feeds import FeedError, FeedItem

log = logging.getLogger(__name__)
RECENT = timedelta(days=3)
MIN_CHARS = 8
MIN_WORDS = 2

Feed = tuple[str, Callable[[], list[FeedItem]]]
OnEvents = Callable[[Session, list[m.Event]], None]
ExtraTitles = Callable[[Session], dict[int, list[str]]]


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


def title_matches(title: str, headline: str) -> bool:
    if len(title) < MIN_CHARS or len(title.split()) < MIN_WORDS:
        return False
    return f" {title} " in f" {headline} "


class NewsWatcher:
    def __init__(
        self,
        db: Database,
        feeds: list[Feed],
        on_events: OnEvents | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        extra_titles: ExtraTitles = lambda _s: {},
    ) -> None:
        self._db = db
        self._feeds = feeds
        self._on_events = on_events
        self._clock = clock
        self._extra_titles = extra_titles

    def run(self) -> None:
        with self._db.session() as s:
            if not load_settings(s)["news_feeds"]:
                return
        since = self._clock() - RECENT
        items: list[tuple[str, FeedItem]] = []
        for name, fetch in self._feeds:
            try:
                items += [(name, i) for i in fetch() if i.published and i.published >= since]
            except FeedError as error:
                log.info("News feed %s unavailable: %s", name, error)
        if not items:
            return
        with self._db.session() as s:
            titles = self._titles(s)
            created = [
                event
                for feed, item in items
                for series_id in _matching(titles, normalize(item.title))
                if (event := _record(s, series_id, feed, item)) is not None
            ]
            if created and self._on_events:
                self._on_events(s, created)
            s.commit()

    def _titles(self, s: Session) -> dict[int, set[str]]:
        titles: dict[int, set[str]] = {
            series_id: {normalize(title)}
            for series_id, title in s.execute(
                select(m.Series.id, m.Series.title).where(m.Series.followed.is_(True))
            )
        }
        for series_id, extra in self._extra_titles(s).items():
            if series_id in titles:
                titles[series_id] |= {normalize(t) for t in extra}
        return titles


def anilist_titles(s: Session) -> dict[int, list[str]]:
    """AniList titles and synonyms of followed series, from the media cache only."""
    rows = s.execute(
        select(m.Series.id, m.AnilistCache.body_json)
        .join(m.AnilistMapping, m.AnilistMapping.tvdb_id == m.Series.tvdb_id)
        .join(
            m.AnilistCache,
            m.AnilistCache.key == "media:" + cast(m.AnilistMapping.anilist_id, String),
        )
        .where(m.Series.followed.is_(True))
    ).all()
    titles: dict[int, list[str]] = {}
    for series_id, body in rows:
        media = json.loads(body) if body and body != "null" else {}
        names = [*(media.get("title") or {}).values(), *(media.get("synonyms") or [])]
        titles.setdefault(series_id, []).extend(n for n in names if isinstance(n, str) and n)
    return titles


def _matching(titles: dict[int, set[str]], headline: str) -> list[int]:
    return sorted(
        sid for sid, names in titles.items() if any(title_matches(n, headline) for n in names)
    )


def _record(s: Session, series_id: int, feed: str, item: FeedItem) -> m.Event | None:
    series = s.get_one(m.Series, series_id)
    payload = {
        "title": series.title,
        "headline": item.title,
        "link": item.link,
        "feed": feed,
        "published": item.published.isoformat() if item.published else None,
    }
    key = fingerprint(
        "news_mention", series.instance_id, series.sonarr_id, 0, item.link or item.title
    )
    event_id = s.execute(
        insert(m.Event)
        .values(
            type="news_mention",
            instance_id=series.instance_id,
            series_id=series.id,
            season_id=None,
            fingerprint=key,
            payload_json=json.dumps(payload),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["fingerprint"])
        .returning(m.Event.id)
    ).scalar()
    return s.get_one(m.Event, event_id) if event_id is not None else None
