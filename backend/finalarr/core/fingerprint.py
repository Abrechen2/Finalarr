"""Deterministic event fingerprints; the events table keeps them UNIQUE."""

import hashlib

from finalarr.core.model import EventType


def fingerprint(
    event_type: EventType, instance_id: int, series_id: int, season_number: int, key: str
) -> str:
    raw = f"{event_type}|{instance_id}|{series_id}|{season_number}|{key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
