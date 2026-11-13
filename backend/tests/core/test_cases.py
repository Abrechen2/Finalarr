"""Table-driven evaluator cases (PLAN.md section 12). A new bug = a new YAML case."""

from typing import Any

import pytest

from finalarr.core.evaluator import evaluate
from finalarr.core.model import Event, SeasonMemory

from .case_loader import (
    as_datetime,
    build_input,
    build_policy,
    episode_id,
    load_cases,
    parse_numbers,
)


def _event_view(event: Event, expected: dict[str, Any]) -> dict[str, Any]:
    """Project an event onto the keys the case cares about."""
    view: dict[str, Any] = {"type": event.type}
    payload = event.payload
    if "episodes" in expected:
        view["episodes"] = payload["episode_ids"]
    for key in ("have", "expected", "finale", "first_air"):
        if key in expected:
            view[key] = payload.get(key)
    return view


def _expected_view(expected: dict[str, Any]) -> dict[str, Any]:
    view = dict(expected)
    if "episodes" in view:
        view["episodes"] = [episode_id(n) for n in parse_numbers(view["episodes"])]
    if "finale" in view:
        view["finale"] = episode_id(view["finale"])
    return view


@pytest.mark.parametrize(("name", "case"), load_cases(), ids=[n for n, _ in load_cases()])
def test_case(name: str, case: dict[str, Any]) -> None:
    memory = SeasonMemory.initial()
    policy = build_policy(case)
    for index, run in enumerate(case["runs"]):
        result = evaluate(build_input(case, run), memory, as_datetime(run["now"]), policy)
        expect = run["expect"]
        where = f"{name} run {index}"

        if "state" in expect:
            assert result.memory.state == expect["state"], where
        if "disputed" in expect:
            assert result.disputed == expect["disputed"], where
        wanted = [_expected_view(e) for e in expect["events"]]
        got = [_event_view(ev, w) for ev, w in zip(result.events, wanted, strict=False)]
        assert len(result.events) == len(wanted), f"{where}: {[e.type for e in result.events]}"
        assert got == wanted, where
        memory = result.memory


def test_renotify_after_file_loss_gets_a_new_fingerprint() -> None:
    """Codex review: a repeat the policy asks for must survive the UNIQUE fingerprint."""
    case = dict(load_cases())["file_deleted_renotify_enabled"]
    memory = SeasonMemory.initial()
    fingerprints = []
    for run in case["runs"]:
        result = evaluate(
            build_input(case, run), memory, as_datetime(run["now"]), build_policy(case)
        )
        fingerprints += [e.fingerprint for e in result.events]
        memory = result.memory
    assert len(fingerprints) == 2
    assert len(set(fingerprints)) == 2


def test_finale_payload_carries_the_episode_number() -> None:
    case = dict(load_cases())["finale_before_missing_files"]
    memory = SeasonMemory.initial()
    payloads = []
    for run in case["runs"]:
        result = evaluate(
            build_input(case, run), memory, as_datetime(run["now"]), build_policy(case)
        )
        payloads += [e.payload for e in result.events]
        memory = result.memory
    assert payloads[0]["finale_number"] == 4
