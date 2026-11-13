"""JSON round trip for SeasonMemory, stored in ``seasons.memory_json``."""

from __future__ import annotations

import json
from typing import Any

from finalarr.core.model import SeasonMemory


def dump_memory(memory: SeasonMemory) -> str:
    data: dict[str, Any] = {
        "state": memory.state,
        "initialized": memory.initialized,
        "announced_ids": sorted(memory.announced_ids),
        "finale_ids": sorted(memory.finale_ids),
        "completed_count": memory.completed_count,
        "last_expected": memory.last_expected,
        "stable_runs": memory.stable_runs,
        "season_announced": memory.season_announced,
        "file_losses": memory.file_losses,
        "parts_done": sorted(memory.parts_done),
    }
    return json.dumps(data)


def load_memory(raw: str | None) -> SeasonMemory:
    if not raw:
        return SeasonMemory.initial()
    data = json.loads(raw)
    return SeasonMemory(
        state=data["state"],
        initialized=bool(data["initialized"]),
        announced_ids=frozenset(data["announced_ids"]),
        finale_ids=frozenset(data["finale_ids"]),
        completed_count=data["completed_count"],
        last_expected=data["last_expected"],
        stable_runs=int(data["stable_runs"]),
        season_announced=bool(data["season_announced"]),
        file_losses=int(data.get("file_losses", 0)),
        parts_done=frozenset(data.get("parts_done", [])),
    )
