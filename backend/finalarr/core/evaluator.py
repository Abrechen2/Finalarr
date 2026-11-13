"""Pure season evaluator: ``evaluate(season, memory, now, policy) -> Evaluation``.

No I/O and no clock: everything comes in as arguments (PLAN.md 4.3). Rules:

- The first evaluation of a season is a silent baseline, so an existing library
  never floods the channel. Specials (season 0) stay silent unless included.
- One run emits at most one library event, the most significant one:
  ``season_complete`` > ``finale_available`` > ``episodes_available``. The lower
  milestones are still recorded, so they never fire later for the same files.
- ``season_complete`` needs an expected count that did not change for
  ``policy.stable_runs`` evaluations and no open dispute with AniList.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from finalarr.core.fingerprint import fingerprint
from finalarr.core.model import (
    SEASON_FINALE_TYPES,
    Episode,
    Evaluation,
    Event,
    EventType,
    Policy,
    SeasonInput,
    SeasonMemory,
    State,
)

SPECIALS_SEASON = 0


@dataclass(frozen=True)
class _Snapshot:
    """What the current library says about one season, derived from the input."""

    counted: tuple[Episode, ...]
    expected: int | None
    disputed: bool
    with_file: frozenset[int]
    stable_runs: int
    state: State


def evaluate(
    season: SeasonInput, memory: SeasonMemory, now: datetime, policy: Policy
) -> Evaluation:
    snap = _snapshot(season, memory, now, policy)
    new_ids = snap.with_file - memory.announced_ids
    new_finales = (_finale_ids(season, snap) & new_ids) - memory.finale_ids
    fires_complete = snap.state == "complete" and _complete_is_due(memory, snap, policy)
    silent = not memory.initialized or (
        season.season_number == SPECIALS_SEASON and not season.include_specials
    )

    events: tuple[Event, ...] = ()
    if not silent:
        events = _library_event(season, snap, new_ids, new_finales, fires_complete)
        if _announce_is_due(memory, snap):
            events = (_announcement(season, snap), *events)

    next_memory = _remember(memory, snap, new_finales, policy)
    return Evaluation(next_memory, events, snap.expected, snap.disputed)


def _snapshot(
    season: SeasonInput, memory: SeasonMemory, now: datetime, policy: Policy
) -> _Snapshot:
    counted = tuple(e for e in season.episodes if e.monitored or not season.respect_monitoring)
    expected, disputed = _expected_count(season, len(counted))
    with_file = frozenset(e.sonarr_id for e in counted if e.has_file)
    unchanged = memory.last_expected is None or memory.last_expected == expected
    stable_runs = memory.stable_runs + 1 if unchanged else 1
    stable = memory.last_expected is None or stable_runs >= policy.stable_runs
    state = _state(counted, expected, with_file, now, stable and not disputed)
    return _Snapshot(counted, expected, disputed, with_file, stable_runs, state)


def _expected_count(season: SeasonInput, sonarr_count: int) -> tuple[int | None, bool]:
    """Override wins; a larger AniList count disputes Sonarr's (split-cour trap)."""
    if season.expected_override is not None:
        return season.expected_override, False
    anilist = season.anilist_count
    if anilist is not None and anilist > sonarr_count:
        return anilist, sonarr_count > 0
    return (sonarr_count or None), False


def _state(
    counted: Sequence[Episode],
    expected: int | None,
    with_file: frozenset[int],
    now: datetime,
    may_complete: bool,
) -> State:
    if not counted or expected is None:
        return "unknown"
    aired = [e for e in counted if e.air_date is not None and e.air_date <= now]
    if not aired:
        return "scheduled"
    if len(aired) < len(counted) or len(counted) < expected:
        return "airing"
    if len(with_file) < len(counted) or not may_complete:
        return "aired"
    return "complete"


def _finale_ids(season: SeasonInput, snap: _Snapshot) -> frozenset[int]:
    """Explicit Sonarr finale, else the last episode when the count is corroborated."""
    explicit = frozenset(e.sonarr_id for e in snap.counted if e.finale_type in SEASON_FINALE_TYPES)
    if explicit:
        return explicit
    corroborated = season.expected_override is not None or season.anilist_count == len(snap.counted)
    if snap.counted and corroborated and len(snap.counted) == snap.expected:
        return frozenset({max(snap.counted, key=lambda e: e.number).sonarr_id})
    return frozenset()


def _complete_is_due(memory: SeasonMemory, snap: _Snapshot, policy: Policy) -> bool:
    if memory.completed_count is None:
        return True
    grown = snap.expected is not None and snap.expected > memory.completed_count
    return policy.renotify_on_growth and grown


def _announce_is_due(memory: SeasonMemory, snap: _Snapshot) -> bool:
    return (
        not memory.season_announced
        and memory.state == "unknown"
        and snap.state != "unknown"
        and not snap.with_file
    )


def _library_event(
    season: SeasonInput,
    snap: _Snapshot,
    new_ids: frozenset[int],
    new_finales: frozenset[int],
    fires_complete: bool,
) -> tuple[Event, ...]:
    payload = _payload(snap, new_ids)
    if new_finales:
        payload["finale"] = min(new_finales)
    if fires_complete:
        return (_event("season_complete", season, str(snap.expected), payload),)
    if new_finales:
        return (_event("finale_available", season, str(payload["finale"]), payload),)
    if new_ids:
        key = ",".join(str(i) for i in sorted(new_ids))
        return (_event("episodes_available", season, key, payload),)
    return ()


def _announcement(season: SeasonInput, snap: _Snapshot) -> Event:
    dates = [e.air_date for e in snap.counted if e.air_date is not None]
    payload: dict[str, Any] = {
        "season": season.season_number,
        "expected": snap.expected,
        "first_air": min(dates).date().isoformat() if dates else None,
    }
    return _event("season_announced", season, "", payload)


def _payload(snap: _Snapshot, new_ids: frozenset[int]) -> dict[str, Any]:
    numbers = {e.sonarr_id: e.number for e in snap.counted}
    ids = sorted(new_ids, key=lambda i: numbers[i])
    return {
        "episode_ids": ids,
        "episodes": [numbers[i] for i in ids],
        "have": len(snap.with_file),
        "expected": snap.expected,
    }


def _event(event_type: EventType, season: SeasonInput, key: str, payload: dict[str, Any]) -> Event:
    fp = fingerprint(event_type, season.instance_id, season.series_id, season.season_number, key)
    return Event(event_type, fp, {"season": season.season_number, **payload})


def _remember(
    memory: SeasonMemory, snap: _Snapshot, new_finales: frozenset[int], policy: Policy
) -> SeasonMemory:
    announced = memory.announced_ids | snap.with_file
    finales = memory.finale_ids | new_finales
    if policy.renotify_after_file_loss:
        announced = snap.with_file
        finales = finales & snap.with_file
    completed = memory.completed_count
    if snap.state == "complete" and _complete_is_due(memory, snap, policy):
        completed = snap.expected
    return SeasonMemory(
        state=snap.state,
        initialized=True,
        announced_ids=announced,
        finale_ids=finales,
        completed_count=completed,
        last_expected=snap.expected,
        stable_runs=snap.stable_runs,
        season_announced=memory.season_announced or _announce_is_due(memory, snap),
    )
