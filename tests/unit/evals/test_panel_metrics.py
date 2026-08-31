"""
Module: test_panel_metrics
Layer: test (unit)
Purpose: Tests for evals/panel_metrics.py — chance-corrected inter-judge agreement
         (Fleiss kappa), the per-criterion breakdown, and the per-judge repeat-flip
         decomposition. RED anchors for ISSUE-181 (agreement grouped by record_id
         alone, pooling k repeats and inflating n) and for the class-imbalance
         blind spot that made raw agreement 0.956 look like a strong panel.
Dependencies: pytest, eval_records, judge_panel, kappa_stats, panel_metrics (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

from eval_records import GenerationRecord
from judge_panel import PanelScoredRecord, PanelVerdict
from kappa_stats import fleiss_kappa
from panel_metrics import compute_panel_metrics

_PANEL = ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")


def _scored(
    record_id: str,
    judge_kind: str,
    polarity: str,
    repetition: int,
    scores: dict[str, bool | None],
) -> PanelScoredRecord:
    """Build one record's panel result."""
    record = GenerationRecord(
        record_id=record_id,
        source="anti_hallucination",
        npc_id="npc",
        player_id="p",
        player_message="m",
        npc_response="r",
        criteria="c",
        judge_kind=judge_kind,
        expected_polarity=polarity,
        repetition=repetition,
    )
    return PanelScoredRecord(
        record=record,
        verdicts=tuple(
            PanelVerdict(record_id=record_id, judge_model=m, score=s, error="")
            for m, s in scores.items()
        ),
    )


# ---------------------------------------------------------------------------
# Fleiss kappa
# ---------------------------------------------------------------------------


def test_fleiss_kappa_is_undefined_when_every_verdict_is_the_same() -> None:
    """All-pass data has no variance to correct against — kappa must be None, not 1.0.

    tone_judge in the 2026-08-17 run was unanimous on 135/135 records; reporting
    kappa=1.0 there would claim perfect chance-corrected agreement from zero signal.
    """
    items = [[True, True, True] for _ in range(10)]
    result = fleiss_kappa(items)
    assert result.kappa is None
    assert result.undefined_reason


def test_fleiss_kappa_matches_hand_computed_value() -> None:
    """Two categories, 3 raters, 4 items — checked against the textbook formula."""
    items = [
        [True, True, True],
        [True, True, False],
        [False, False, False],
        [False, False, True],
    ]
    # P_i = 1.0, 1/3, 1.0, 1/3  -> Pbar = 2/3
    # marginals: 6 True, 6 False of 12 -> Pe = 0.5
    # kappa = (2/3 - 1/2) / (1 - 1/2) = 1/3
    result = fleiss_kappa(items)
    assert result.kappa is not None
    assert abs(result.kappa - 1.0 / 3.0) < 1e-9
    assert abs(result.observed_agreement - 2.0 / 3.0) < 1e-9
    assert abs(result.chance_agreement - 0.5) < 1e-9


def test_fleiss_kappa_is_far_below_raw_agreement_under_class_imbalance() -> None:
    """The headline finding: 95%-pass data makes raw agreement flattering.

    19 unanimous passes plus 1 split record gives very high observed agreement,
    but the base rate explains nearly all of it, so kappa must be much lower.
    """
    items = [[True, True, True] for _ in range(19)] + [[True, False, False]]
    result = fleiss_kappa(items)
    assert result.kappa is not None
    assert result.observed_agreement > 0.9
    assert result.kappa < result.observed_agreement / 2.0


def test_fleiss_kappa_ignores_inconclusive_votes() -> None:
    """Items with fewer than 2 real votes cannot be rated and are excluded."""
    items = [[True, None, None], [True, True, False], [False, False, True]]
    result = fleiss_kappa(items)
    assert result.n_items == 2


# ---------------------------------------------------------------------------
# RED anchor — ISSUE-181: grouping must key on (record_id, repetition)
# ---------------------------------------------------------------------------


def test_agreement_does_not_pool_repetitions_of_one_record_id() -> None:
    """Three repeats of one record_id are three items, not one 9-vote item.

    Pooling them (the 2026-08-17 behaviour) produced C(9,2)=36 pairs per record
    instead of 3x3=9, inflating n 4x and silently counting each judge against
    ITSELF on a different generation.
    """
    scored = [
        _scored("case_x:tone_judge:5", "tone_judge", "pass_on_yes", rep, {m: True for m in _PANEL})
        for rep in (0, 1, 2)
    ]
    metrics = compute_panel_metrics(scored)

    assert metrics.n_items == 3, "3 repeats are 3 rateable items"
    assert metrics.agreement.total_pairs == 9, "3 items x C(3,2) pairs, not C(9,2)=36"


def test_agreement_pairs_never_compare_a_judge_with_itself() -> None:
    """Every counted pair is two DIFFERENT seats on the SAME generation."""
    scored = [
        _scored("case_x:tone_judge:5", "tone_judge", "pass_on_yes", rep, {m: True for m in _PANEL})
        for rep in (0, 1, 2)
    ] + [
        _scored("case_y:tone_judge:1", "tone_judge", "pass_on_yes", rep, {m: False for m in _PANEL})
        for rep in (0, 1, 2)
    ]
    metrics = compute_panel_metrics(scored)
    assert metrics.agreement.total_pairs == 6 * 3


# ---------------------------------------------------------------------------
# Per-criterion breakdown
# ---------------------------------------------------------------------------


def test_per_criterion_breakdown_isolates_the_noisy_criterion() -> None:
    """A criterion the panel splits on is reported separately from a clean one."""
    clean = [
        _scored(f"c{i}:tone_judge:1", "tone_judge", "pass_on_yes", 0, {m: True for m in _PANEL})
        for i in range(5)
    ]
    noisy = [
        _scored(
            f"c{i}:refusal_judge:1",
            "refusal_judge",
            "pass_on_yes",
            0,
            {"mixtral:8x7b": True, "qwen2.5:14b": False, "llama3.1:8b": True},
        )
        for i in range(5)
    ]
    metrics = compute_panel_metrics(clean + noisy)
    by_kind = {c.judge_kind: c for c in metrics.by_criterion}

    assert by_kind["tone_judge"].unanimous == 5
    assert by_kind["refusal_judge"].unanimous == 0
    assert by_kind["tone_judge"].n_items == 5


# ---------------------------------------------------------------------------
# Repeat-flip decomposition (engine noise vs judge noise)
# ---------------------------------------------------------------------------


def test_repeat_flips_separate_solo_from_unanimous_flips() -> None:
    """A flip all judges make is engine variance; a flip one judge makes is judge noise."""
    # record A: every judge changes its mind between rep 0 and rep 1 -> engine-driven
    engine = [
        _scored("case_a:tone_judge:1", "tone_judge", "pass_on_yes", 0, {m: True for m in _PANEL}),
        _scored("case_a:tone_judge:1", "tone_judge", "pass_on_yes", 1, {m: False for m in _PANEL}),
    ]
    # record B: only qwen changes its mind -> judge-driven
    judge = [
        _scored("case_b:tone_judge:1", "tone_judge", "pass_on_yes", 0, {m: True for m in _PANEL}),
        _scored(
            "case_b:tone_judge:1",
            "tone_judge",
            "pass_on_yes",
            1,
            {"mixtral:8x7b": True, "qwen2.5:14b": False, "llama3.1:8b": True},
        ),
    ]
    metrics = compute_panel_metrics(engine + judge)

    assert metrics.repeat_flips.unanimous_flips == 1
    assert metrics.repeat_flips.solo_flips == 1
    flips_by_judge = dict(metrics.repeat_flips.flips_by_judge)
    assert flips_by_judge["qwen2.5:14b"] == 2  # flipped on both record A and record B
    assert flips_by_judge["mixtral:8x7b"] == 1  # flipped only on record A


def test_polarity_is_applied_before_computing_kappa() -> None:
    """Kappa must be computed on pass/fail decisions, not raw YES/NO.

    Pooling raw scores across pass_on_yes and pass_on_no criteria artificially
    balances the marginals and inflates kappa. Two criteria that both PASS
    unanimously must look unanimous even though their raw scores are opposite.
    """
    yes_side = [
        _scored(f"a{i}:tone_judge:1", "tone_judge", "pass_on_yes", 0, {m: True for m in _PANEL})
        for i in range(5)
    ]
    no_side = [
        _scored(f"b{i}:affirms_judge:1", "affirms_judge", "pass_on_no", 0, {m: False for m in _PANEL})
        for i in range(5)
    ]
    metrics = compute_panel_metrics(yes_side + no_side)

    # All 10 items are unanimous PASSES once polarity is applied, so there is no
    # variance and kappa is undefined. On raw scores the marginals would be 50/50.
    assert metrics.kappa.kappa is None
    assert metrics.kappa.undefined_reason
