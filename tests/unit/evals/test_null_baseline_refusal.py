"""
Module: test_null_baseline_refusal
Layer: test (unit)
Purpose: R2.5 step 3c — a battery's headline rate is not published when the engine
         scores at or below the recorded null responder over that same battery.
         The rule is applied per population (DEC-243); a union is never formed.
Dependencies: pytest, null_baseline (evals/), headline_refusal (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from headline_refusal import refusal_for_battery
from null_baseline import NULL_BASELINE_PATH, load_null_baseline


def _baseline(rate: float) -> dict:
    return {
        "adversarial": {
            "battery": "adversarial",
            "null_rate": rate,
            "passes": 37,
            "turns": 37,
            "cases": 37,
            "hedge_sha256": "0" * 64,
            "judge_model": "mixtral:8x7b",
            "expectation_set": "guard_expectations.expected_with_guards",
            "measured_utc": "2026-09-02",
            "measured_at_git_sha": "abcdef0",
            "note": "test fixture",
        }
    }


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def test_an_engine_rate_below_the_null_is_refused() -> None:
    """The measured case: engine 0.8468 against a null that scores 1.000."""
    refusal = refusal_for_battery("adversarial", 0.8468, _baseline(1.0))
    assert refusal is not None
    assert "0.8468" in refusal
    assert "1.0" in refusal


def test_an_engine_rate_exactly_at_the_null_is_refused() -> None:
    """Ties do not publish. Matching a canned non-answer demonstrates nothing."""
    assert refusal_for_battery("adversarial", 0.75, _baseline(0.75)) is not None


def test_an_engine_rate_above_the_null_publishes() -> None:
    """Strictly above the null is the only publishable case."""
    assert refusal_for_battery("adversarial", 0.90, _baseline(0.75)) is None


def test_a_battery_with_no_recorded_null_is_not_gated() -> None:
    """An unmeasured battery is not silently refused — it is simply not gated.

    Refusing here would make every battery unpublishable the moment the artifact
    is missing a row, which punishes absence of evidence as if it were evidence.
    The gap is surfaced by check_null_baseline, not by a refusal on the headline.
    """
    assert refusal_for_battery("capability", 0.5, _baseline(1.0)) is None


def test_a_battery_whose_engine_rate_is_absent_is_not_gated() -> None:
    """No engine rate means no comparison to draw."""
    assert refusal_for_battery("adversarial", None, _baseline(1.0)) is None


# ---------------------------------------------------------------------------
# The recorded artifact
# ---------------------------------------------------------------------------


def test_the_shipped_baseline_records_the_measured_adversarial_null() -> None:
    """The artifact holds the 2026-09-03 (M3.3) measurement, not a placeholder.

    This was 1.000 until M3.3 re-authored the 37 guard cases against DEC-256. The prior
    rate is kept in the artifact so the two are comparable, and the hedge is unchanged,
    so the move is a property of the battery and not of the adversary.
    """
    baseline = load_null_baseline()
    assert "adversarial" in baseline
    entry = baseline["adversarial"]
    assert entry["null_rate"] == pytest.approx(0.0)
    assert entry["previous_null_rate"] == pytest.approx(1.0)
    assert entry["turns"] == 37
    assert entry["expectation_set"] == "guard_expectations.expected_with_guards"


def test_the_shipped_baseline_now_publishes_the_adversarial_rate() -> None:
    """M3.3's outcome, pinned: the engine rate clears a null that no longer scores.

    The refusal rule is unchanged and still enforced (see the rule tests above) — what
    changed is the battery it is measured over.
    """
    assert refusal_for_battery("adversarial", 0.8468, load_null_baseline()) is None


def test_every_recorded_entry_states_what_it_measured() -> None:
    """A recorded number without provenance is indistinguishable from a guess.

    This is the R2.7b lesson applied to the null baseline: the artifact must say
    which hedge, which judge, and which expectation set produced the rate.
    """
    raw = json.loads(Path(NULL_BASELINE_PATH).read_text(encoding="utf-8"))
    for name, entry in raw["batteries"].items():
        for field in (
            "null_rate", "passes", "turns", "hedge_sha256",
            "judge_model", "expectation_set", "measured_utc",
        ):
            assert field in entry, f"{name} is missing {field}"
        assert len(entry["hedge_sha256"]) == 64


# ---------------------------------------------------------------------------
# The wiring — the rule must reach the rendered output, per population
# ---------------------------------------------------------------------------


def _summary(**over):
    from summary import EvalSummary

    base = dict(
        total_cases=10, evaluated_cases=10, total_turns=244,
        guard_cases=8, guard_turns=234, hallucination_failures=0,
        schema_failures=0, keyword_none_failures=0, tone_judge_failures=0,
        affirms_judge_failures=0, other_failures=0, skipped_cases=0,
        adversarial_rate=0.8468, adversarial_passes=94, adversarial_turns=111,
        adversarial_ci_low=0.77, adversarial_ci_high=0.90,
        anti_hallucination_rate=0.9106, anti_hallucination_passes=112,
        anti_hallucination_turns=123,
        anti_hallucination_ci_low=0.85, anti_hallucination_ci_high=0.95,
        capability_rate=0.80, capability_passes=8, capability_turns=10,
        capability_ci_low=0.49, capability_ci_high=0.94,
    )
    base.update(over)
    return EvalSummary(**base)


def test_the_console_emitter_refuses_the_adversarial_rate_against_a_matching_null() -> None:
    """End-to-end: an engine rate does not print when the null over that battery matches it.

    The null is injected rather than read from the shipped artifact: this test is about the
    emitter's refusal path, and pinning it to the recorded rate made it fail the moment M3.3
    legitimately moved that rate from 1.000 to 0.000.
    """
    from summary import format_summary_lines

    text = "\n".join(format_summary_lines(_summary(), null_baseline=_baseline(1.0)))
    adversarial_line = next(ln for ln in text.splitlines() if "Guard, adversarial" in ln)
    assert "REFUSED" in adversarial_line
    assert "0.847" not in adversarial_line


def test_the_refusal_is_per_population_and_never_a_union() -> None:
    """DEC-243: the other two batteries are untouched by the adversarial refusal."""
    from summary import format_summary_lines

    lines = format_summary_lines(_summary())
    ah = next(ln for ln in lines if "Guard, anti-hallucination" in ln)
    cap = next(ln for ln in lines if "Capability rate" in ln)
    assert "REFUSED" not in ah and "0.911" in ah
    assert "REFUSED" not in cap and "0.800" in cap


def test_an_explicit_empty_baseline_renders_rates_ungated() -> None:
    """Passing {} disables the gate, so callers with no baseline still render."""
    from summary import format_summary_lines

    lines = format_summary_lines(_summary(), null_baseline={})
    assert "REFUSED" not in "\n".join(lines)


def test_the_markdown_emitter_refuses_too() -> None:
    """The published artifact is markdown; the console is not the only surface."""
    from summary import format_summary_markdown

    text = "\n".join(format_summary_markdown(_summary(), null_baseline=_baseline(1.0)))
    assert "REFUSED" in text
