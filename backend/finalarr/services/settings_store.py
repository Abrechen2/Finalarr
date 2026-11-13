"""Global rules stored in the ``settings`` table, with defaults (PLAN.md 4.3, 16.3)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalarr.core.model import Policy
from finalarr.db.models import Setting

DEFAULTS: dict[str, Any] = {
    "renotify_on_growth": False,
    "renotify_after_file_loss": False,
    "stable_runs": 2,
    "include_specials_default": False,
    "respect_monitoring_default": True,
    "reconcile_interval_minutes": 30,
}


def load_settings(session: Session) -> dict[str, Any]:
    stored = {row.key: json.loads(row.value_json) for row in session.scalars(select(Setting))}
    return {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}


def save_settings(session: Session, values: dict[str, Any]) -> None:
    unknown = set(values) - set(DEFAULTS)
    if unknown:
        raise KeyError(f"Unknown settings: {sorted(unknown)}")
    for key, value in values.items():
        session.merge(Setting(key=key, value_json=json.dumps(value)))


def policy_from(values: dict[str, Any]) -> Policy:
    return Policy(
        renotify_on_growth=bool(values["renotify_on_growth"]),
        renotify_after_file_loss=bool(values["renotify_after_file_loss"]),
        stable_runs=int(values["stable_runs"]),
    )
