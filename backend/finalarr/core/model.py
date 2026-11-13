"""Immutable value types for the pure season evaluator (PLAN.md 4.2-4.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

State = Literal["unknown", "scheduled", "airing", "aired", "complete"]
EventType = Literal["season_announced", "episodes_available", "finale_available", "season_complete"]

# Sonarr `finaleType` values that mark the end of a season; `midseason` does not.
SEASON_FINALE_TYPES = frozenset({"season", "series"})


@dataclass(frozen=True)
class Episode:
    sonarr_id: int
    number: int
    air_date: datetime | None
    monitored: bool
    has_file: bool
    finale_type: str | None = None


@dataclass(frozen=True)
class SeasonInput:
    instance_id: int
    series_id: int
    season_number: int
    episodes: tuple[Episode, ...]
    expected_override: int | None = None
    anilist_count: int | None = None
    include_specials: bool = False
    respect_monitoring: bool = True


@dataclass(frozen=True)
class Policy:
    renotify_on_growth: bool = False
    renotify_after_file_loss: bool = False
    # Consecutive evaluations the expected count must stay unchanged before "complete".
    stable_runs: int = 2


@dataclass(frozen=True)
class SeasonMemory:
    """Everything the evaluator needs to remember between runs, and nothing else."""

    state: State
    initialized: bool
    announced_ids: frozenset[int]
    finale_ids: frozenset[int]
    completed_count: int | None
    last_expected: int | None
    stable_runs: int
    season_announced: bool
    # Policy-approved file losses so far; keeps repeat notifications distinct.
    file_losses: int = 0

    @classmethod
    def initial(cls) -> SeasonMemory:
        return cls("unknown", False, frozenset(), frozenset(), None, None, 0, False)


@dataclass(frozen=True)
class Event:
    type: EventType
    fingerprint: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Evaluation:
    memory: SeasonMemory
    events: tuple[Event, ...]
    expected_count: int | None
    disputed: bool
