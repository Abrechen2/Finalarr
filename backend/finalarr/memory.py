"""Keeps the long-running worker's memory flat.

Python frees objects after each job, but glibc keeps the freed pages, and the many
short-lived objects of a sync fragment its heap: the container grew by days until the
kernel killed it (2026-11). Every background job therefore hands free memory back with
``malloc_trim`` and logs when it grew the process noticeably. The image also sets
``MALLOC_ARENA_MAX=2``, so the scheduler's threads do not each get their own arena.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import functools
import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

# Growth per job worth a log line; normal jobs stay well below.
REPORT_MB = 30

_libc: Any = None
try:
    _name = ctypes.util.find_library("c")
    _libc = ctypes.CDLL(_name) if _name else None
    if _libc is not None and not hasattr(_libc, "malloc_trim"):  # musl, macOS
        _libc = None
except OSError:  # pragma: no cover - no C library to load
    _libc = None


def rss_mb() -> int | None:
    """Resident memory of this process in MB (Linux), else None."""
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:  # pragma: no cover - not Linux
        return None
    return None  # pragma: no cover


def trim() -> None:
    """Return free heap pages to the system (glibc only)."""
    if _libc is not None:
        _libc.malloc_trim(0)


def tracked(name: str, job: Callable[[], object]) -> Callable[[], None]:
    """Run ``job``, then trim; log when it grew the process by REPORT_MB or more."""

    @functools.wraps(job)
    def run() -> None:
        before = rss_mb()
        try:
            job()
        finally:
            after = rss_mb()
            trim()
            if before is not None and after is not None and after - before >= REPORT_MB:
                log.info(
                    "%s raised memory by %d MB (%d -> %d MB)", name, after - before, before, after
                )

    return run
