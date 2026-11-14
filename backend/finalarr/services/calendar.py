"""Calendar of what you are waiting for: in the UI and as a subscribable iCal feed.

Only followed series with the calendar switch on. The scope decides how much:
``finales`` (season finales), ``milestones`` (season premieres and finales, the
default) or ``all`` episodes. Episodes already on disk are hidden unless asked
for, and announced start dates (TVmaze, AniList, …) come as all-day entries —
except year-only dates, which AniList stores as 1 January.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from icalendar import Calendar, Event
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from finalarr.db import models as m

Scope = Literal["finales", "milestones", "all"]
Kind = Literal["episode", "premiere", "finale", "announcement"]
EPISODE_LENGTH = timedelta(minutes=30)
SEASON_FINALE_TYPES = {"season", "series"}


@dataclass(frozen=True)
class CalendarOptions:
    scope: Scope = "milestones"
    hide_downloaded: bool = True
    announcements: bool = True


@dataclass(frozen=True)
class CalendarEntry:
    uid: str
    kind: Kind
    title: str
    season: int
    episode: int | None
    episode_title: str
    start: datetime | date
    all_day: bool
    series_id: int | None
    has_file: bool = False
    sequel_title: str | None = None
    delayed_from: datetime | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _kind(season: m.Season, episode: m.Episode) -> Kind:
    numbers = [e.number for e in season.episodes]
    if episode.finale_type in SEASON_FINALE_TYPES:
        return "finale"
    complete_list = season.expected_count and len(numbers) >= season.expected_count
    no_explicit = not any(e.finale_type in SEASON_FINALE_TYPES for e in season.episodes)
    if complete_list and no_explicit and episode.number == max(numbers):
        return "finale"
    if episode.number == min(numbers):
        return "premiere"
    return "episode"


def _wanted(kind: Kind, scope: Scope) -> bool:
    if scope == "all":
        return True
    if scope == "milestones":
        return kind in ("premiere", "finale")
    return kind == "finale"


def _episode_entries(
    s: Session, start: date, end: date, opts: CalendarOptions
) -> list[CalendarEntry]:
    lower = datetime.combine(start, time.min, UTC)
    upper = datetime.combine(end, time.max, UTC)
    series_rows = s.scalars(
        select(m.Series)
        .where(m.Series.followed.is_(True), m.Series.calendar.is_(True))
        .options(selectinload(m.Series.seasons).selectinload(m.Season.episodes))
    )
    found = []
    for series in series_rows:
        for season in series.seasons:
            if season.number == 0 and not series.include_specials:
                continue
            for episode in season.episodes:
                if episode.air_date_utc is None:
                    continue
                aired = _aware(episode.air_date_utc)
                if not lower <= aired <= upper:
                    continue
                if series.respect_monitoring and not episode.monitored:
                    continue
                if opts.hide_downloaded and episode.has_file:
                    continue
                kind = _kind(season, episode)
                if _wanted(kind, opts.scope):
                    found.append(
                        CalendarEntry(
                            uid=f"finalarr-episode-{episode.sonarr_episode_id}@finalarr",
                            kind=kind,
                            title=series.title,
                            season=season.number,
                            episode=episode.number,
                            episode_title=episode.title,
                            start=aired,
                            all_day=False,
                            series_id=series.id,
                            has_file=episode.has_file,
                            delayed_from=_aware(episode.delayed_from)
                            if episode.delayed_from
                            else None,
                        )
                    )
    return found


def _announcement_entries(s: Session, start: date, end: date) -> list[CalendarEntry]:
    found = []
    events = s.scalars(
        select(m.Event).where(m.Event.type.in_(("season_announced", "sequel_announced")))
    )
    for event in events:
        payload = json.loads(event.payload_json)
        raw = payload.get("first_air")
        if not raw:
            continue
        day = date.fromisoformat(str(raw)[:10])
        if (day.month, day.day) == (1, 1) or not start <= day <= end:
            continue  # year-only dates are stored as 1 January
        found.append(
            CalendarEntry(
                uid=f"finalarr-announcement-{event.fingerprint[:24]}@finalarr",
                kind="announcement",
                title=str(payload.get("title", "?")),
                season=int(payload.get("season") or 0),
                episode=None,
                episode_title="",
                start=day,
                all_day=True,
                series_id=event.series_id,
                sequel_title=payload.get("sequel_title"),
            )
        )
    return found


def build_entries(s: Session, start: date, end: date, opts: CalendarOptions) -> list[CalendarEntry]:
    entries = _episode_entries(s, start, end, opts)
    if opts.announcements:
        listed = {(e.title, e.season) for e in entries}
        entries += [
            a for a in _announcement_entries(s, start, end) if (a.title, a.season) not in listed
        ]

    def sort_key(entry: CalendarEntry) -> tuple[datetime, str, int]:
        moment = (
            entry.start
            if isinstance(entry.start, datetime)
            else datetime.combine(entry.start, time.max, UTC)
        )
        return moment, entry.title, entry.episode or 0

    return sorted(entries, key=sort_key)


_LABELS = {
    "de": {
        "finale": "Finale",
        "premiere": "Staffelstart",
        "season": "Staffel {n}",
        "announced": "Start angekündigt",
        "on_disk": "bereits vorhanden",
        "delayed": "verschoben (vorher {day})",
        "day": "%d.%m.",
    },
    "en": {
        "finale": "Finale",
        "premiere": "Season premiere",
        "season": "Season {n}",
        "announced": "start announced",
        "on_disk": "already on disk",
        "delayed": "postponed (was {day})",
        "day": "%d/%m",
    },
}


def summary(entry: CalendarEntry, language: str) -> str:
    labels = _LABELS.get(language, _LABELS["de"])
    if entry.kind == "announcement":
        what = entry.sequel_title or labels["season"].format(n=entry.season)
        return f"{entry.title}: {what} – {labels['announced']}"
    text = f"{entry.title} S{entry.season:02d}E{(entry.episode or 0):02d}"
    if entry.kind in ("finale", "premiere"):
        text += f" – {labels[entry.kind]}"
    if entry.delayed_from:
        text += " – " + labels["delayed"].format(day=entry.delayed_from.strftime(labels["day"]))
    return text


def render_ics(entries: list[CalendarEntry], language: str, public_url: str | None) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//Finalarr//Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", "Finalarr")
    calendar.add("refresh-interval", timedelta(hours=1), parameters={"VALUE": "DURATION"})
    calendar.add("x-published-ttl", "PT1H")
    stamp = datetime.now(UTC)
    for entry in entries:
        event = Event()
        event.add("uid", entry.uid)
        event.add("dtstamp", stamp)
        event.add("summary", summary(entry, language))
        if entry.all_day:
            event.add("dtstart", entry.start)
        else:
            event.add("dtstart", entry.start)
            event.add("duration", EPISODE_LENGTH)
        if entry.episode_title:
            event.add("description", entry.episode_title)
        if public_url and entry.series_id:
            event.add("url", f"{public_url}/series/{entry.series_id}")
        event.add("transp", "TRANSPARENT")
        calendar.add_component(event)
    body: bytes = calendar.to_ical()
    return body
