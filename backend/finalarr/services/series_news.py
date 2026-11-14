"""News for one series: what Finalarr knows (announcements, matched headlines)
plus a web news search for the title (Google News RSS, optional, cached)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.core.news_filter import is_season_news
from finalarr.db import models as m
from finalarr.services.news import anilist_titles
from finalarr.services.season_sources import JsonCache
from finalarr.sources.feeds import FeedError, FeedItem, fetch_feed, google_news_url

EVENT_TYPES = ("news_mention", "season_announced", "sequel_announced")
MAX_ITEMS = 10
MAX_AGE = timedelta(days=365)
WEB_TTL = timedelta(hours=6)
SHORT_TITLE_CHARS = 8
CONTEXT = {"anime": {"de": "anime", "en": "anime"}, "series": {"de": "Serie", "en": "series"}}
# Ask for season/episode news up front; is_season_news filters the rest.
FOCUS = {"de": "(Staffel OR Folge)", "en": "(season OR episode)"}

Fetch = Callable[[str], list[FeedItem]]


def news_query(title: str, series_type: str, language: str) -> str:
    """Exact title (main part before a colon); short or one-word titles get a
    context word, otherwise "24" or "Severance" match everything."""
    head = title.split(":", 1)[0].strip()
    core = head if len(head.split()) >= 2 else title.strip()
    query = f'"{core}"'
    if len(core) < SHORT_TITLE_CHARS or len(core.split()) < 2:
        kind = "anime" if series_type == "anime" else "series"
        query += f" {CONTEXT[kind].get(language, CONTEXT[kind]['en'])}"
    return f"{query} {FOCUS.get(language, FOCUS['en'])}"


def _event_items(s: Session, series: m.Series) -> list[dict[str, Any]]:
    rows = s.scalars(
        select(m.Event)
        .where(m.Event.series_id == series.id, m.Event.type.in_(EVENT_TYPES))
        .order_by(m.Event.id.desc())
        .limit(MAX_ITEMS)
    )
    return [
        {
            "kind": "event",
            "event_type": e.type,
            "payload": json.loads(e.payload_json),
            "published": e.created_at.isoformat(),
        }
        for e in rows
    ]


def _web_items(
    items: list[dict[str, Any]], now: datetime, titles: list[str]
) -> list[dict[str, Any]]:
    oldest = (now - MAX_AGE).isoformat()
    recent = [
        i
        for i in items
        if i["published"] and i["published"] >= oldest and is_season_news(i["title"], titles)
    ]
    return sorted(recent, key=lambda i: i["published"], reverse=True)[:MAX_ITEMS]


def series_news(
    s: Session,
    series: m.Series,
    language: str,
    cache: JsonCache,
    fetch: Fetch = fetch_feed,
    web: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(UTC)
    items = _event_items(s, series)
    error = False
    if web:
        query = news_query(series.title, series.series_type, language)

        def search() -> list[dict[str, Any]]:
            return [
                {
                    "kind": "web",
                    "title": i.title,
                    "link": i.link,
                    "source": i.source,
                    "published": i.published.isoformat() if i.published else None,
                }
                for i in fetch(google_news_url(query, language))
            ]

        try:
            found = cache.remember(f"news:{language}:{query}", WEB_TTL, search)
            titles = [series.title, *anilist_titles(s).get(series.id, [])]
            items += _web_items(found, moment, titles)
        except FeedError:
            error = True
    return {"items": items, "web_enabled": web, "web_error": error}
