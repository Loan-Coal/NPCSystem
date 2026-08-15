"""
Module: test_refusal_rate
Layer: test (unit)
Purpose: Tests for evals/refusal_rate.py — score_refusal_rate and fmt_refusal_rate.
         Validates that over-refusal is correctly counted and that the P0.4 fixture
         reproduces the recorded 4/15 over-refusal result without a live LLM run.
Dependencies: pytest, refusal_rate (evals/), matchers (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from matchers import JudgeResult
from refusal_rate import RefusalRateResult, fmt_refusal_rate, score_refusal_rate

# Path to the P0.4 recorded grounded responses fixture.
_P04_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "evals" / "calibration" / "p04_grounded_responses.json"
)


# ---------------------------------------------------------------------------
# Judge stubs
# ---------------------------------------------------------------------------


def _judge_always_refusal(response: str) -> JudgeResult:
    """Stub that always returns YES (refusal)."""
    return JudgeResult(score=True)


def _judge_never_refusal(response: str) -> JudgeResult:
    """Stub that always returns NO (not a refusal)."""
    return JudgeResult(score=False)


def _judge_always_infra_failure(response: str) -> JudgeResult:
    """Stub that always returns infra failure (score=None)."""
    return JudgeResult(score=None, error="infra_failure")


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_grounded_refusal_is_counted_as_a_failure() -> None:
    """A grounded case where the judge says YES (refusal) is counted as an over-refusal.

    RED anchor: before refusal_rate.py exists this test fails on import.
    After implementation: one refusal response → over_refusals=1, evaluated=1.
    """
    result = score_refusal_rate(
        ["I'm afraid I cannot tell you that."],
        judge_fn=_judge_always_refusal,
    )
    assert result.over_refusals == 1
    assert result.evaluated == 1
    assert result.rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_non_refusal_response_is_not_counted_as_failure() -> None:
    """When the judge says NO, the response is not counted as an over-refusal."""
    result = score_refusal_rate(
        ["The war started in the north three months ago."],
        judge_fn=_judge_never_refusal,
    )
    assert result.over_refusals == 0
    assert result.evaluated == 1


def test_infra_failure_excluded_from_denominator() -> None:
    """Infra failures (score=None) are excluded from evaluated and from the rate."""
    result = score_refusal_rate(
        ["some response"],
        judge_fn=_judge_always_infra_failure,
    )
    assert result.evaluated == 0
    assert result.over_refusals == 0
    assert result.rate is None


def test_empty_input_returns_none_rate() -> None:
    """An empty response list produces a result with rate=None and zero counts."""
    result = score_refusal_rate([], judge_fn=_judge_never_refusal)
    assert result.total_grounded == 0
    assert result.evaluated == 0
    assert result.rate is None


def test_mixed_verdicts_count_correctly() -> None:
    """Mixed verdicts: 2 refusals, 2 answers, 1 infra failure → evaluated=4, over_refusals=2."""
    call_index = [0]
    verdicts = [True, False, True, False, None]

    def _sequenced_judge(response: str) -> JudgeResult:
        score = verdicts[call_index[0]]
        call_index[0] += 1
        return JudgeResult(score=score, error="infra_failure" if score is None else "")

    responses = ["r1", "r2", "r3", "r4", "r5"]
    result = score_refusal_rate(responses, judge_fn=_sequenced_judge)
    assert result.total_grounded == 5
    assert result.evaluated == 4
    assert result.over_refusals == 2
    assert result.rate == pytest.approx(0.5)


def test_fmt_refusal_rate_with_data() -> None:
    """fmt_refusal_rate formats k/n, rate, and CI when data is available."""
    result = RefusalRateResult(
        total_grounded=15,
        evaluated=15,
        over_refusals=4,
        rate=4 / 15,
        ci_low=0.109,
        ci_high=0.519,
    )
    formatted = fmt_refusal_rate(result)
    assert "4/15" in formatted
    assert "CI" in formatted


def test_fmt_refusal_rate_no_data() -> None:
    """fmt_refusal_rate returns N/A notice when no evaluated turns exist."""
    result = RefusalRateResult(
        total_grounded=0,
        evaluated=0,
        over_refusals=0,
        rate=None,
        ci_low=None,
        ci_high=None,
    )
    assert fmt_refusal_rate(result) == "N/A (no evaluated turns)"


# ---------------------------------------------------------------------------
# Validation — P0.4 recorded fixture
# ---------------------------------------------------------------------------


def test_summary_includes_over_refusal_rate() -> None:
    """format_summary_lines renders the over-refusal rate when one is supplied.

    RED anchor for EVAL-P20.3: fails today because format_summary_lines has no
    parameter to receive a RefusalRateResult — refusal_rate.py's own docstring
    says the summary integration is 'future', and `grep score_refusal_rate`
    finds zero non-test callers. Also pins that the excluded (infra-failure)
    count is visible, not hidden the way plain 'k/n' would hide it.
    """
    import summary  # noqa: PLC0415  (evals/ path — deferred import, matches sibling tests)

    guard_case = {
        "case_id": "case_adv_x",
        "description": "",
        "passed": True,
        "expectations": [{"kind": "keyword_none", "passed": True, "skipped": False, "detail": ""}],
        "response": {"npc_response": "x"},
        "error": None,
    }
    cap_case = {
        "case_id": "case_pos_x",
        "description": "",
        "passed": True,
        "expectations": [{"kind": "affirms_judge", "passed": True, "skipped": False, "detail": ""}],
        "response": {"npc_response": "y"},
        "error": None,
    }
    s = summary.summarize([guard_case, cap_case])
    refusal = RefusalRateResult(
        total_grounded=10,
        evaluated=8,
        over_refusals=2,
        rate=0.25,
        ci_low=0.07,
        ci_high=0.59,
    )

    lines = summary.format_summary_lines(s, refusal_result=refusal)
    blob = "\n".join(lines)

    assert "over-refusal" in blob.lower()
    assert "2/8" in blob
    assert "excluded: 2/10" in blob.lower()


def test_p04_fixture_reproduces_4_of_15_over_refusals() -> None:
    """Replaying the P0.4 grounded set with recorded verdicts reproduces 4/15 over-refusals.

    The fixture records the 15 evaluated grounded cases from the P0.4 baseline run.
    A stub judge that returns the pre-recorded is_refusal verdict reproduces the
    4/15 over-refusal result without a live LLM run.
    """
    fixture_data = json.loads(_P04_FIXTURE.read_text(encoding="utf-8"))
    responses = [entry["npc_response"] for entry in fixture_data]
    verdict_list = [entry["is_refusal"] for entry in fixture_data]

    call_count = [0]

    def _recorded_judge(response: str) -> JudgeResult:
        idx = call_count[0]
        call_count[0] += 1
        return JudgeResult(score=verdict_list[idx])

    result = score_refusal_rate(responses, judge_fn=_recorded_judge)
    assert result.evaluated == 15
    assert result.over_refusals == 4
    assert result.rate == pytest.approx(4 / 15)
