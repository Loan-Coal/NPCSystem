"""
Module: tests.unit.evals.test_panel_metrics_format
Layer: tests
Purpose: Unit tests for evals/panel_metrics_format.py's pooled-kappa-inflation
         caveat — the fix for k3_61b01dad_negadv's trend row reporting a
         pooled panel_kappa of 0.831 ("almost perfect") while every individual
         criterion sat below the 0.40 trust floor (0.254/0.308/0.003), with
         nothing flagging that the pooled figure does not mean the judges
         agree.
Dependencies: pytest; panel_metrics (PanelMetrics, CriterionAgreement, ...),
         panel_metrics_format (console_lines, markdown_rows), judge_panel
         (AgreementResult), kappa_stats (KappaResult)
Used by: make test (pytest discovery)
"""

from __future__ import annotations

from judge_panel import AgreementResult
from kappa_stats import KappaResult
from panel_metrics import CriterionAgreement, PanelMetrics, RepeatFlipResult
from panel_metrics_format import console_lines, markdown_rows

_NO_FLIPS = RepeatFlipResult(
    records_with_flips=0, unanimous_flips=0, solo_flips=0, flips_by_judge=(), n_records=0,
)
_AGREEMENT = AgreementResult(agreeing_pairs=90, total_pairs=100, rate=0.9, ci_low=0.8, ci_high=0.95)


def _metrics(kappa: float, by_criterion: tuple[CriterionAgreement, ...]) -> PanelMetrics:
    """Build a PanelMetrics with a given pooled kappa and per-criterion breakdown."""
    return PanelMetrics(
        agreement=_AGREEMENT,
        kappa=KappaResult(
            kappa=kappa, observed_agreement=0.9, chance_agreement=0.4,
            n_items=357, ci_low=kappa - 0.05, ci_high=kappa + 0.05,
        ),
        by_criterion=by_criterion,
        repeat_flips=_NO_FLIPS,
        n_items=357,
        pass_base_rate=0.8,
    )


# The exact k3_61b01dad_negadv numbers: pooled 0.831 clears HIDDEN_THRESHOLD
# (0.40) while every one of the three criteria sits below it.
_INFLATED = _metrics(
    kappa=0.8313819547815351,
    by_criterion=(
        CriterionAgreement(judge_kind="affirms_judge", n_items=135, unanimous=132, kappa=0.2536286919831172),
        CriterionAgreement(judge_kind="commits_judge", n_items=111, unanimous=81, kappa=0.3083218661175653),
        CriterionAgreement(judge_kind="tone_judge", n_items=111, unanimous=109, kappa=0.002966381015163611),
    ),
)

# A normal run where the pooled figure and the per-criterion figures agree —
# k3_77688e7_regen1's real numbers: pooled 0.581, criteria 0.519/0.422/0.753.
_CONSISTENT = _metrics(
    kappa=0.5807453416149063,
    by_criterion=(
        CriterionAgreement(judge_kind="affirms_judge", n_items=135, unanimous=125, kappa=0.5193448848801339),
        CriterionAgreement(judge_kind="refusal_judge", n_items=75, unanimous=64, kappa=0.4222689075630257),
        CriterionAgreement(judge_kind="tone_judge", n_items=135, unanimous=129, kappa=0.7533996346661249),
    ),
)


def test_console_lines_flags_inflated_pooled_kappa() -> None:
    """Pooled kappa clearing the trust floor while every criterion sits below
    it must print a caveat, not just the per-criterion breakdown."""
    lines = "\n".join(console_lines(_INFLATED))
    assert "0.831" in lines
    assert "may be inflated" in lines


def test_console_lines_does_not_flag_a_consistent_run() -> None:
    """No caveat when the pooled figure isn't contradicted by every criterion."""
    lines = "\n".join(console_lines(_CONSISTENT))
    assert "may be inflated" not in lines


def test_markdown_rows_flags_inflated_pooled_kappa() -> None:
    rows = "\n".join(markdown_rows(_INFLATED))
    assert "may be inflated" in rows


def test_markdown_rows_does_not_flag_a_consistent_run() -> None:
    rows = "\n".join(markdown_rows(_CONSISTENT))
    assert "may be inflated" not in rows


def test_caveat_does_not_fire_with_no_criteria() -> None:
    """No by_criterion breakdown at all (e.g. a single judge_kind run) must
    not spuriously flag — there is nothing to contradict the pooled figure."""
    metrics = _metrics(kappa=0.9, by_criterion=())
    assert "may be inflated" not in "\n".join(console_lines(metrics))


def test_caveat_does_not_fire_when_pooled_kappa_itself_is_low() -> None:
    """A low pooled kappa is already honestly bad; no separate flag needed."""
    metrics = _metrics(
        kappa=0.1,
        by_criterion=(CriterionAgreement(judge_kind="tone_judge", n_items=10, unanimous=1, kappa=0.05),),
    )
    assert "may be inflated" not in "\n".join(console_lines(metrics))


def test_console_lines_and_markdown_rows_empty_without_a_panel() -> None:
    assert console_lines(None) == []
    assert markdown_rows(None) == []
