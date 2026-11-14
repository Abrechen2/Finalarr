"""Keep only season and episode news (German and English headlines).

A headline must mention seasons, episodes, premieres, finales, renewals,
cancellations, delays or trailers, and must not be about merchandise, films,
manga or novels, home video, games, events or guides. Exclusions win unless
the headline announces, renews, cancels or delays something. The series' own
titles are removed first, so "Game of Thrones" does not count as a game and
"Slime" stays harmless.

``news_kind`` types a headline (renewal, announcement, cancellation, delay,
date, trailer, other); ``evidence_sentence`` picks the sentence of a feed
summary that carries the news.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Iterable
from typing import Literal

NewsKind = Literal["cancellation", "delay", "renewal", "announcement", "date", "trailer", "other"]

_INCLUDE = re.compile(
    r"\b("
    r"staffel\w*|seasons?|s\d{1,2}|\d+(st|nd|rd|th) season|teil \d+|part \d+|cour|"
    r"episoden?|episodes?|folgen?|ep \d+|"
    r"premiere\w*|staffelstart|startet|starttermin|start date|finale|"
    r"release date|erscheinungsdatum|air ?dates?|airs|airing|ausstrahlung|broadcast\w*|"
    r"verlaengert|renewed|renewal|cancell?ed|abgesetzt|eingestellt|"
    r"delay\w*|postponed|verschoben|pause|hiatus|"
    r"trailer|teaser|pv"
    r")\b"
)
_EXCLUDE = re.compile(
    r"(kollektion|collection|figur|figure|nendoroid|statue|pluesch|plush|merch|"
    r"apparel|fashion|shirt|hoodie|cosplay|\bcafe\b|collab|kooperation|kollaboration|gacha|"
    r"\bspiel\w*|\bgames?\b|videospiel|\bmanga\b|light novel|\bnovels?\b|\broman\b|"
    r"\bband \d+|\bvolume\b|\bvol \d+|blu ?ray|\bdvd\b|\bbox\b|"
    r"\bfilm\b|\bmovie\b|kinofilm|watch order|reihenfolge|interview|"
    r"konzert|concert|ausstellung|exhibition|pop up|\btickets?\b|gewinnspiel|preorder|vorbestell|"
    r"\blike\b|to watch|\breview\w*|\brecap\w*|rueckblick|\bkritik\b|ranking|\branked\b|"
    r"\bsongs?\b|soundtrack|music video|musikvideo|steelcase|\bedition\b|showcar|\bwirbt\b)"
)
# First match wins: a cancelled or delayed season matters more than its trailer.
_KINDS: tuple[tuple[NewsKind, re.Pattern[str]], ...] = (
    ("cancellation", re.compile(r"\b(cancell?ed|cancels?|abgesetzt|eingestellt|axed)\b")),
    ("delay", re.compile(r"\b(delay\w*|postponed?|verschoben|verschiebt|pause|hiatus)\b")),
    (
        "renewal",
        re.compile(
            r"\b(verlaengert|renewed|renewal|renews|(erhaelt|bekommt|gets) (eine |a )?"
            r"(\w+ )?(staffel|season))\b"
        ),
    ),
    (
        "announcement",
        re.compile(r"\b(angekuendigt|ankuendigung|announced?|announcement|confirmed|bestaetigt)\b"),
    ),
    (
        "date",
        re.compile(
            r"\b(premiere\w*|staffelstart|startet|starttermin|start date|release date|"
            r"erscheinungsdatum|air ?dates?|dated|airs)\b"
        ),
    ),
    ("trailer", re.compile(r"\b(trailer|teaser|pv)\b")),
)
_STRONG: tuple[NewsKind, ...] = ("cancellation", "delay", "renewal", "announcement")
MAX_EVIDENCE_CHARS = 240
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _normalize(text: str) -> str:
    text = text.lower().translate(_UMLAUTS)
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


MIN_TITLE_CHARS = 4
COMPACT_MAX_WORDS = 3


def _title_forms(titles: Iterable[str]) -> list[str]:
    """Each title, its main part before a colon ("Mushoku Tensei: Jobless …") and,
    for short titles, the written-together form."""
    forms = set()
    for title in titles:
        for form in (title, title.split(":", 1)[0]):
            normalized = _normalize(form)
            if len(normalized) >= MIN_TITLE_CHARS or normalized.isdigit():
                forms.add(normalized)
                if 1 < len(normalized.split()) <= COMPACT_MAX_WORDS:
                    forms.add(normalized.replace(" ", ""))  # "DAN DA DAN" → "dandadan"
    return sorted(forms, key=len, reverse=True)


def is_season_news(headline: str, titles: Iterable[str]) -> bool:
    """Season/episode news that names the series in the headline itself (search
    engines also match article bodies, which yields listicles about other shows)."""
    text = f" {_normalize(headline)} "
    forms = _title_forms(titles)
    if not any(f" {form} " in text for form in forms):
        return False
    for form in forms:
        text = text.replace(f" {form} ", " ")
    if not _INCLUDE.search(text):
        return False
    excluded = _EXCLUDE.search(text)
    return excluded is None or _strong_before(text, excluded.start())


def _strong_before(text: str, position: int) -> bool:
    """ "Season 3 announced alongside figures" is season news; in "Blu-ray box for
    season 2 announced" the merchandise comes first and is the subject."""
    return any(
        (match := pattern.search(text)) is not None and match.start() < position
        for kind, pattern in _KINDS
        if kind in _STRONG
    )


def _kind(normalized: str) -> NewsKind:
    return next((kind for kind, pattern in _KINDS if pattern.search(normalized)), "other")


def news_kind(headline: str) -> NewsKind:
    return _kind(_normalize(headline))


def evidence_sentence(summary: str) -> str | None:
    """First sentence of a feed summary (HTML allowed) that talks about seasons or
    episodes; None when there is none."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", summary)).split())
    for sentence in re.findall(r"[^.!?]+[.!?]?", text):
        sentence = re.sub(r"\s+([.!?,])", r"\1", sentence.strip())
        if sentence and _INCLUDE.search(_normalize(sentence)):
            return sentence[:MAX_EVIDENCE_CHARS]
    return None
