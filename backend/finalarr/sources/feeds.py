"""RSS headlines (LiveChart.me, Anime News Network), parsed with defusedxml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import requests
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

TIMEOUT_SECONDS = 15
MAX_BYTES = 2 * 1024 * 1024

FEEDS = {
    "livechart": "https://www.livechart.me/feeds/headlines",
    "animenewsnetwork": "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=w",
}


class FeedError(RuntimeError):
    pass


GOOGLE_NEWS = "https://news.google.com/rss/search"
_GOOGLE_EDITIONS = {"de": ("de", "DE", "DE:de"), "en": ("en-US", "US", "US:en")}


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str | None
    published: datetime | None
    source: str | None = None


def google_news_url(query: str, language: str) -> str:
    """Google News RSS search in the UI language (free, no key)."""
    hl, gl, ceid = _GOOGLE_EDITIONS.get(language, _GOOGLE_EDITIONS["en"])
    return f"{GOOGLE_NEWS}?{urlencode({'q': query, 'hl': hl, 'gl': gl, 'ceid': ceid})}"


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _safe_link(value: str | None) -> str | None:
    link = (value or "").strip()
    return link if link.startswith(("https://", "http://")) else None


def fetch_feed(url: str) -> list[FeedItem]:
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException:
        raise FeedError("Feed cannot be reached") from None
    if response.status_code != 200 or len(response.content) > MAX_BYTES:
        raise FeedError(f"Feed answered HTTP {response.status_code}")
    return parse_feed(response.content)


def parse_feed(raw: bytes) -> list[FeedItem]:
    try:
        root = fromstring(raw)
    except (ParseError, DefusedXmlException):
        raise FeedError("Feed is not valid or safe XML") from None
    return [
        FeedItem(
            title=(item.findtext("title") or "").strip(),
            link=_safe_link(item.findtext("link")),
            published=_date(item.findtext("pubDate")),
            source=(item.findtext("source") or "").strip() or None,
        )
        for item in root.iter("item")
        if (item.findtext("title") or "").strip()
    ]
