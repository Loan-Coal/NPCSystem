"""
Module: test_battery_trust
Layer: test (unit)
Purpose: The scorer trust policy (scorer_trust_policy.check_publication) must reach
         the rendered battery rate — refusing a HIDDEN battery, caveating a RESTRICTED
         one, and leaving a PUBLISHABLE one untouched. Before battery_trust.py existed,
         evals/summary.py, evals/report.py and evals/headline_refusal.py had zero
         references to scorer_trust_policy (measured 2026-09-04), so a battery whose
         only contributing scorer sat at kappa 0.849 with a CI floor of -0.010 still
         printed its rate unqualified.
Dependencies: pytest, battery_trust (evals/), trend_store (ScorerKappa), summary (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from battery_trust import BATTERY_JUDGED_SCORERS, battery_publication_status, trust_gate
from scorer_trust_policy import TrustLevel
from trend_store import ScorerKappa


def _kappa(scorer: str, kappa: float, lo: float, hi: float, n: int = 100) -> ScorerKappa:
    return ScorerKappa(scorer=scorer, kappa=kappa, ci_low=lo, ci_high=hi, n=n)


# ---------------------------------------------------------------------------
# battery_publication_status — the pure decision
# ---------------------------------------------------------------------------


def test_publishable_when_every_contributing_scorer_clears_the_bar() -> None:
    """capability's only judged scorer (tone_judge) clears kappa and CI floor."""
    status = battery_publication_status(
        "capability", [_kappa("tone_judge", 0.90, 0.75, 0.98)],
    )
    assert status.level == TrustLevel.PUBLISHABLE
    assert status.refusals == ()


def test_hidden_when_a_contributing_scorer_is_below_the_hidden_threshold() -> None:
    """kappa < 0.40 is HIDDEN — the battery must not print at all."""
    status = battery_publication_status(
        "capability", [_kappa("tone_judge", 0.20, -0.10, 0.50)],
    )
    assert status.level == TrustLevel.HIDDEN
    assert len(status.refusals) == 1
    assert status.refusals[0].scorer == "tone_judge"


def test_restricted_when_kappa_clears_but_the_ci_floor_does_not() -> None:
    """The measured case: tone_judge kappa 0.849, CI floor -0.010 (CR-L03-02/DEC-244)."""
    status = battery_publication_status(
        "capability", [_kappa("tone_judge", 0.849, -0.010, 1.0)],
    )
    assert status.level == TrustLevel.RESTRICTED
    assert status.refusals[0].scorer == "tone_judge"


def test_hidden_beats_restricted_when_a_battery_has_multiple_contributing_scorers() -> None:
    """adversarial contributes affirms_judge + commits_judge; the worst level wins."""
    status = battery_publication_status(
        "adversarial",
        [
            _kappa("affirms_judge", 0.849, -0.010, 1.0),   # RESTRICTED
            _kappa("commits_judge", 0.20, -0.10, 0.50),    # HIDDEN
        ],
    )
    assert status.level == TrustLevel.HIDDEN


def test_a_scorer_never_calibrated_does_not_gate_its_battery() -> None:
    """Absence of a kappa row is absence of evidence, not a HIDDEN verdict.

    Mirrors headline_refusal's rule for an unmeasured null baseline: refusing here
    would make every battery unpublishable the moment calibration has not run yet.
    """
    status = battery_publication_status("capability", [])
    assert status.level == TrustLevel.PUBLISHABLE
    assert status.refusals == ()


def test_battery_scorer_map_excludes_mechanical_matchers() -> None:
    """schema/keyword_none/keyword_any carry no kappa; only judge-calibrated scorers gate."""
    for scorers in BATTERY_JUDGED_SCORERS.values():
        assert "schema" not in scorers
        assert "keyword_none" not in scorers
        assert "keyword_any" not in scorers


# ---------------------------------------------------------------------------
# trust_gate — the rendered string
# ---------------------------------------------------------------------------


def test_trust_gate_hides_the_rate_string_entirely() -> None:
    result = trust_gate("capability", "8/10  0.800  95% CI [0.49-0.94]",
                         [_kappa("tone_judge", 0.20, -0.10, 0.50)])
    assert "HIDDEN" in result
    assert "0.800" not in result


def test_trust_gate_appends_a_caveat_without_dropping_the_rate() -> None:
    result = trust_gate("capability", "8/10  0.800  95% CI [0.49-0.94]",
                         [_kappa("tone_judge", 0.849, -0.010, 1.0)])
    assert "0.800" in result
    assert "RESTRICTED" in result


def test_trust_gate_passes_publishable_rates_through_unchanged() -> None:
    original = "8/10  0.800  95% CI [0.49-0.94]"
    result = trust_gate("capability", original, [_kappa("tone_judge", 0.90, 0.75, 0.98)])
    assert result == original


# ---------------------------------------------------------------------------
# Wiring — the gate must reach format_summary_markdown / format_summary_lines
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


def test_format_summary_markdown_refuses_a_hidden_battery() -> None:
    """RED anchor: fails today — summary.py has zero references to scorer_trust_policy."""
    from summary import format_summary_markdown

    text = "\n".join(format_summary_markdown(
        _summary(), null_baseline={},
        scorer_kappas=[_kappa("tone_judge", 0.20, -0.10, 0.50)],
    ))
    capability_row = next(ln for ln in text.splitlines() if "Capability (case_pos_*)" in ln)
    assert "HIDDEN" in capability_row
    assert "0.800" not in capability_row


def test_format_summary_lines_caveats_a_restricted_battery() -> None:
    from summary import format_summary_lines

    text = "\n".join(format_summary_lines(
        _summary(), null_baseline={},
        scorer_kappas=[_kappa("tone_judge", 0.849, -0.010, 1.0)],
    ))
    capability_line = next(ln for ln in text.splitlines() if "Capability rate" in ln)
    assert "RESTRICTED" in capability_line
    assert "0.800" in capability_line


def test_no_scorer_kappas_argument_renders_ungated_as_before() -> None:
    """Additive default: omitting scorer_kappas must not change existing callers' output."""
    from summary import format_summary_lines

    text = "\n".join(format_summary_lines(_summary(), null_baseline={}))
    assert "HIDDEN" not in text
    assert "RESTRICTED" not in text
