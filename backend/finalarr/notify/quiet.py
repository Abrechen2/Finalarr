"""Quiet hours per channel: deliveries wait until the window ends (PLAN.md 3, 4.x)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse(value: str) -> time:
    match = _HHMM.match(value)
    if not match:
        raise ValueError("time must be HH:MM (00:00-23:59)")
    return time(int(match[1]), int(match[2]))


@dataclass(frozen=True)
class QuietHours:
    start: str
    end: str

    def __post_init__(self) -> None:
        _parse(self.start)
        _parse(self.end)


def quiet_until(quiet: QuietHours, now: datetime, zone: tzinfo) -> datetime | None:
    """End of the quiet window containing ``now`` (aware, UTC-comparable), else None."""
    start, end = _parse(quiet.start), _parse(quiet.end)
    if start == end:
        return None
    local = now.astimezone(zone)
    clock = local.time()
    overnight = start > end
    inside = (clock >= start or clock < end) if overnight else (start <= clock < end)
    if not inside:
        return None
    end_day = local.date() + timedelta(days=1) if overnight and clock >= start else local.date()
    return datetime.combine(end_day, end, tzinfo=zone)
