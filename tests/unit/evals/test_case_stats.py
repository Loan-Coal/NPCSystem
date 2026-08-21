"""
Module: test_case_stats
Layer: test (unit)
Purpose: Tests for evals/case_stats.py — CaseStat model, classify, and aggregate.
         Fixtures build minimal JudgedRecord stubs to avoid live infrastructure.
Dependencies: pytest, case_stats (evals/), eval_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from case_stats import CaseStat, aggregate, classify
from eval_records import JudgedRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(record_id: str, repetition: int, passed: bool) -> JudgedRecord:
    """Build a minimal JudgedRecord stub with only the fields aggregate needs."""
    return JudgedRecord(
        record_id=record_id,
        source="runner",
        npc_id="test_npc",
        player_id="test_player",
        player_message="hello",
        npc_response="hi",
        criteria="test criteria",
        judge_kind="tone_judge",
        expected_polarity="pass_on_yes",
        repetition=repetition,
        passed=passed,
        score=passed,
    )


def _k3_records(case_id: str, results: tuple[bool, bool, bool]) -> list[JudgedRecord]:
    """Build 3 records for a case with the given per-repetition pass results."""
    return [_make_record(case_id, rep, result) for rep, result in enumerate(results)]


def _fixture_records() -> list[JudgedRecord]:
    """k=3 fixture: one flaky (2/3), one stable_pass (3/3), one stable_fail (0/3)."""
    return (
        _k3_records("flaky_case", (True, False, True))
        + _k3_records("pass_case", (True, True, True))
        + _k3_records("fail_case", (False, False, False))
    )


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


def test_two_of_three_classifies_flaky() -> None:
    """2/3 passes classifies as flaky."""
    assert classify(2, 3) == "flaky"


def test_three_of_three_classifies_stable_pass() -> None:
    """3/3 passes classifies as stable_pass."""
    assert classify(3, 3) == "stable_pass"


def test_zero_of_three_classifies_stable_fail() -> None:
    """0/3 passes classifies as stable_fail."""
    assert classify(0, 3) == "stable_fail"


def test_one_of_three_classifies_flaky() -> None:
    """1/3 passes (partial) also classifies as flaky."""
    assert classify(1, 3) == "flaky"


def test_classify_k_zero_raises() -> None:
    """classify with k=0 must raise ValueError."""
    with pytest.raises(ValueError, match="k"):
        classify(0, 0)


# ---------------------------------------------------------------------------
# aggregate()
# ---------------------------------------------------------------------------


def test_aggregate_flaky_ci() -> None:
    """2/3 case reports flaky with Wilson CI [0.208, 0.939] to 3 dp."""
    stats = {s.case_id: s for s in aggregate(_fixture_records())}
    flaky = stats["flaky_case"]
    assert flaky.classification == "flaky"
    assert flaky.passes == 2
    assert flaky.k == 3
    assert round(flaky.ci_low, 3) == 0.208
    assert round(flaky.ci_high, 3) == 0.939


def test_aggregate_stable_pass() -> None:
    """3/3 case reports stable_pass."""
    stats = {s.case_id: s for s in aggregate(_fixture_records())}
    assert stats["pass_case"].classification == "stable_pass"
    assert stats["pass_case"].passes == 3


def test_aggregate_stable_fail() -> None:
    """0/3 case reports stable_fail."""
    stats = {s.case_id: s for s in aggregate(_fixture_records())}
    assert stats["fail_case"].classification == "stable_fail"
    assert stats["fail_case"].passes == 0


def test_aggregate_flaky_cases_first() -> None:
    """aggregate returns flaky cases before stable ones."""
    result = aggregate(_fixture_records())
    assert result[0].classification == "flaky"
    assert all(s.classification != "flaky" for s in result[1:])


def test_aggregate_pass_rate_field() -> None:
    """pass_rate field equals passes/k."""
    stats = {s.case_id: s for s in aggregate(_fixture_records())}
    assert abs(stats["flaky_case"].pass_rate - 2 / 3) < 1e-9


def test_aggregate_empty_returns_empty_tuple() -> None:
    """aggregate([]) returns an empty tuple."""
    assert aggregate([]) == ()


def test_case_stat_is_frozen() -> None:
    """CaseStat is immutable — mutation raises an error."""
    stat = CaseStat(
        case_id="x",
        k=3,
        passes=3,
        pass_rate=1.0,
        ci_low=0.438,
        ci_high=1.0,
        classification="stable_pass",
    )
    # quality-ok: the assertion is 'any mutation is rejected' and the two model families raise different types (pydantic v2 frozen -> ValidationError, frozen dataclass -> FrozenInstanceError); narrowing per-site is deferred, see ISSUES
    with pytest.raises(Exception):
        stat.passes = 0  # type: ignore[misc]
