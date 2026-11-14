"""Notification texts DE/EN, Telegram-safe HTML (PLAN.md 16.5)."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

LANGUAGES = ("de", "en")
# Order matches the "kinds" text of each language.
NEWS_KINDS = ("cancellation", "delay", "renewal", "announcement", "date", "trailer")
NEWS_ICONS = ("🛑", "⏸️", "🔁", "📅", "🗓️", "🎬")

_TEXT = {
    "de": {
        "episodes_available": "📺 <b>{title}</b> S{s:02d} {ranges} verfügbar ({have}/{expected})",
        "finale_available": (
            "🏁 Finale: <b>{title}</b> S{s:02d}E{e:02d} verfügbar ({have}/{expected})"
        ),
        "season_complete": "✅ <b>{title}</b> Staffel {s} komplett ({have}/{expected})",
        "part_complete": "🧩 <b>{title}</b> Staffel {s} Teil {part} komplett",
        "part_as_season": "✅ <b>{part_title}</b> komplett",
        "season_announced": "📅 <b>{title}</b>: Staffel {s} angekündigt",
        "sequel_announced": "📅 <b>{title}</b>: Fortsetzung angekündigt – {sequel_title}",
        "announced_detail": " (Start {date}, {expected} Folgen)",
        "sequel_detail": " (Start {date})",
        "news_mention": "📰 <b>{title}</b> in den News: {headline}",
        "episode_delayed": "⏸️ <b>{title}</b> S{s:02d}E{n:02d} verschoben: {old} → {new}",
        "open": "offen",
        "typed_news": "{icon} <b>{title}</b> – {kind}: {headline}",
        "kinds": "Absetzung|Verschiebung|Verlängerung|Ankündigung|Termin|Trailer",
        "quote": "„{text}“",
        "article": "Artikel",
        "date": "%d.%m.%Y",
        "test": "✅ Finalarr: Testnachricht – dieser Kanal funktioniert.",
    },
    "en": {
        "episodes_available": "📺 <b>{title}</b> S{s:02d} {ranges} available ({have}/{expected})",
        "finale_available": (
            "🏁 Finale: <b>{title}</b> S{s:02d}E{e:02d} available ({have}/{expected})"
        ),
        "season_complete": "✅ <b>{title}</b> season {s} complete ({have}/{expected})",
        "part_complete": "🧩 <b>{title}</b> season {s} part {part} complete",
        "part_as_season": "✅ <b>{part_title}</b> complete",
        "season_announced": "📅 <b>{title}</b>: season {s} announced",
        "sequel_announced": "📅 <b>{title}</b>: sequel announced – {sequel_title}",
        "announced_detail": " (starts {date}, {expected} episodes)",
        "sequel_detail": " (starts {date})",
        "news_mention": "📰 <b>{title}</b> in the news: {headline}",
        "episode_delayed": "⏸️ <b>{title}</b> S{s:02d}E{n:02d} postponed: {old} → {new}",
        "open": "open",
        "typed_news": "{icon} <b>{title}</b> – {kind}: {headline}",
        "kinds": "cancelled|delayed|renewed|announced|date|trailer",
        "quote": "“{text}”",
        "article": "Article",
        "date": "%d/%m/%Y",
        "test": "✅ Finalarr: test message – this channel works.",
    },
}


def _texts(language: str) -> dict[str, str]:
    return _TEXT[language if language in LANGUAGES else "de"]


def episode_ranges(numbers: list[int]) -> str:
    """[1,2,3,5] → "E01–E03, E05" """
    ordered = sorted(set(numbers))
    parts: list[str] = []
    start = 0
    for i, current in enumerate(ordered):
        if i + 1 < len(ordered) and ordered[i + 1] == current + 1:
            continue
        first = ordered[start]
        parts.append(f"E{first:02d}" if first == current else f"E{first:02d}–E{current:02d}")
        start = i + 1
    return ", ".join(parts)


def channel_test_text(language: str) -> str:
    return _texts(language)["test"]


def render(
    event_type: str, payload: dict[str, Any], language: str, finalarr_url: str | None
) -> str:
    texts = _texts(language)
    values = {
        "title": escape(str(payload.get("title", "?"))),
        "s": int(payload.get("season") or 0),
        "have": payload.get("have", 0),
        "expected": payload.get("expected") or "?",
        "ranges": episode_ranges(payload.get("episodes", [])),
        "e": int(payload.get("finale_number") or 0),
        "part": payload.get("part", "?"),
        "part_title": escape(str(payload.get("part_title", ""))),
        "sequel_title": escape(str(payload.get("sequel_title", ""))),
        "headline": escape(str(payload.get("headline", ""))),
        "n": int(payload.get("episode") or 0),
        "old": _day(payload.get("old"), texts),
        "new": _day(payload.get("new"), texts),
    }
    key = event_type
    if (
        event_type == "part_complete"
        and payload.get("parts_mode") == "parts"
        and payload.get("part_title")
    ):
        key = "part_as_season"
    text = texts[key].format(**values)
    if event_type in ("season_announced", "sequel_announced") and payload.get("first_air"):
        day = _when(str(payload["first_air"]), texts["date"])
        detail = "announced_detail" if event_type == "season_announced" else "sequel_detail"
        text += texts[detail].format(date=day, expected=values["expected"])
    if event_type == "news_mention":
        text = _typed_news(text, payload, values, texts)
        return text + _links([(texts["article"], payload.get("link")), ("Finalarr", finalarr_url)])
    return text + _links([("Finalarr", finalarr_url), ("Sonarr", payload.get("sonarr_url"))])


def _typed_news(
    text: str, payload: dict[str, Any], values: dict[str, Any], texts: dict[str, str]
) -> str:
    kind = payload.get("news_kind")
    if kind in NEWS_KINDS:
        index = NEWS_KINDS.index(kind)
        label = texts["kinds"].split("|")[index]
        text = texts["typed_news"].format(icon=NEWS_ICONS[index], kind=label, **values)
    if payload.get("evidence"):
        text += "\n<i>" + texts["quote"].format(text=escape(str(payload["evidence"]))) + "</i>"
    return text


def _day(value: Any, texts: dict[str, str]) -> str:
    return date.fromisoformat(str(value)[:10]).strftime(texts["date"]) if value else texts["open"]


def _when(first_air: str, day_format: str) -> str:
    """AniList often knows only the year (stored as 1 January): show just the year then."""
    day = date.fromisoformat(first_air[:10])
    return str(day.year) if (day.month, day.day) == (1, 1) else day.strftime(day_format)


def _links(targets: list[tuple[str, Any]]) -> str:
    links = [
        f'<a href="{escape(url, quote=True)}">{name}</a>'
        for name, url in targets
        if isinstance(url, str) and url.startswith(("http://", "https://"))
    ]
    return "\n" + " · ".join(links) if links else ""
