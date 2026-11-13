"""Turns the compact YAML cases in ``cases/`` into evaluator inputs.

Episode shorthand: ``episodes: {count, first_air, interval_days (default 7),
finale: {n: type}, unmonitored: "3,5"}``. Each run may override ``count`` and
``first_air`` and sets ``files`` as a range list ("1-3,5"). Episode ids are
``1000 + number`` so ids and numbers never coincide by accident.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from finalarr.core.model import Episode, Policy, SeasonInput

CASES_DIR = Path(__file__).parent / "cases"


def parse_numbers(spec: str | int | None) -> list[int]:
    if spec is None or spec == "":
        return []
    numbers: list[int] = []
    for part in str(spec).split(","):
        lo, _, hi = part.strip().partition("-")
        numbers.extend(range(int(lo), int(hi or lo) + 1))
    return numbers


def as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def episode_id(number: int) -> int:
    return 1000 + number


def build_input(case: dict[str, Any], run: dict[str, Any]) -> SeasonInput:
    season = case["season"]
    spec = {**case["episodes"], **{k: run[k] for k in ("count", "first_air") if k in run}}
    files = set(parse_numbers(run.get("files")))
    unmonitored = set(parse_numbers(spec.get("unmonitored")))
    finales = {int(k): v for k, v in (spec.get("finale") or {}).items()}
    first_air = as_datetime(spec["first_air"]) if spec.get("first_air") else None
    interval = timedelta(days=spec.get("interval_days", 7))
    episodes = tuple(
        Episode(
            sonarr_id=episode_id(n),
            number=n,
            air_date=first_air + interval * (n - 1) if first_air else None,
            monitored=n not in unmonitored,
            has_file=n in files,
            finale_type=finales.get(n),
        )
        for n in range(1, spec.get("count", 0) + 1)
    )
    return SeasonInput(
        instance_id=1,
        series_id=42,
        season_number=season["number"],
        episodes=episodes,
        expected_override=season.get("expected_override"),
        anilist_count=run.get("anilist_count", season.get("anilist_count")),
        include_specials=season.get("include_specials", False),
        anilist_start=season.get("anilist_start"),
        respect_monitoring=season.get("respect_monitoring", True),
    )


def build_policy(case: dict[str, Any]) -> Policy:
    return replace(Policy(), **case.get("policy", {}))


def load_cases() -> list[tuple[str, dict[str, Any]]]:
    return [
        (path.stem, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(CASES_DIR.glob("*.yaml"))
    ]
