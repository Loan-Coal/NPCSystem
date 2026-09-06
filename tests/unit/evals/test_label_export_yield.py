"""
Module: test_label_export_yield
Layer: test (unit)
Purpose: RED anchor + behaviour tests for label_export_yield.py — the best-case
         adequacy-ceiling projection a stratified label-export batch must clear
         BEFORE it is written, so a batch is never produced for a judge that
         cannot possibly support a kappa estimate (DEC-260's floor).
Dependencies: pytest; calibration_records, export_item, label_adequacy,
         label_export_yield (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from calibration_records import CalibrationLabel
from export_item import ExportItem
from label_adequacy import MIN_CASE_CLUSTERS, MIN_MINORITY_LABELS
from label_export_yield import ProjectedYield, format_projection_table, project_all, project_yield


def _item(record_id: str, scorer: str = "commits_judge") -> ExportItem:
    return ExportItem(
        record_id=record_id,
        scorer=scorer,
        npc_id="npc_a",
        player_message="hi",
        criteria="answer yes",
        output_text="an answer",
    )


def _label(record_id: str, scorer: str, *, human_verdict: bool | None) -> CalibrationLabel:
    return CalibrationLabel(
        record_id=record_id,
        scorer=scorer,
        output_text="an answer",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
        human_verdict=human_verdict,
        adjudicated_at="2026-09-01T00:00:00Z",
        notes="",
    )


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_a_judge_with_no_negative_candidates_is_refused() -> None:
    """RED anchor. A judge with zero unlabelled expected-negative candidates and
    zero existing minority labels can never clear DEC-260's floor no matter how
    the batch is sampled — this must be reported and refused (no batch produced)
    rather than left to fail silently after the fact, the exact failure this
    task exists to prevent (ISSUE-285's premise, corrected: see the module for
    scorers that DO have candidates)."""
    items = [_item(f"case_pos_{i:03d}:some_judge:0#r0", scorer="some_judge") for i in range(5)]
    # every candidate is expected_positive — nothing declared negative at all.
    projection = project_yield(
        "some_judge",
        surviving_labels=[],
        candidate_items=items,
        already_labelled_keys=frozenset(),
        negative_cases=frozenset(),
    )
    assert projection.meets_floor is False
    assert projection.ceiling_minority_n == 0
    assert projection.available_negative_candidates == 0
    assert "some_judge" in projection.reason
    assert str(MIN_MINORITY_LABELS) in projection.reason
    assert str(MIN_CASE_CLUSTERS) in projection.reason


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_a_judge_with_enough_negative_candidates_clears_the_floor() -> None:
    """30 distinct expected-negative clusters clear both the 25-minority and
    10-cluster floors in the best case."""
    negative_cases = frozenset(f"case_neg_{i:03d}" for i in range(30))
    items = [_item(f"case_neg_{i:03d}:tone_judge:0#r0", scorer="tone_judge") for i in range(30)]
    projection = project_yield("tone_judge", [], items, frozenset(), negative_cases)
    assert projection.meets_floor is True
    assert projection.ceiling_minority_n == 30
    assert projection.ceiling_n_clusters == 30
    assert projection.reason == ""


def test_existing_surviving_minority_labels_count_toward_the_ceiling() -> None:
    """A scorer that already has surviving minority labels needs fewer new
    candidates to clear the floor — the ceiling adds to what already exists."""
    existing = [
        _label(f"maj_{i:03d}:tone_judge:0", "tone_judge", human_verdict=True) for i in range(40)
    ] + [
        _label(f"min_{i:03d}:tone_judge:0", "tone_judge", human_verdict=False) for i in range(20)
    ]
    negative_cases = frozenset(f"case_neg_{i:03d}" for i in range(5))
    items = [_item(f"case_neg_{i:03d}:tone_judge:0#r0", scorer="tone_judge") for i in range(5)]
    projection = project_yield("tone_judge", existing, items, frozenset(), negative_cases)
    assert projection.existing_minority_n == 20  # min(40 True, 20 False)
    # 20 existing minority + 5 new candidates = 25 (exactly the floor).
    assert projection.ceiling_minority_n == 25
    # 60 existing clusters (40 maj_ + 20 min_) + 5 new (case_neg_000..004) = 65.
    assert projection.ceiling_n_clusters == 65
    assert projection.meets_floor is True


def test_already_labelled_candidates_are_excluded_from_the_pool() -> None:
    """A candidate whose (record_id, scorer) key already carries a label must
    not be double-counted as an available new candidate."""
    negative_cases = frozenset({"case_neg_a"})
    items = [_item("case_neg_a:commits_judge:0#r0", scorer="commits_judge")]
    already_labelled = frozenset({("case_neg_a:commits_judge:0#r0", "commits_judge")})
    projection = project_yield("commits_judge", [], items, already_labelled, negative_cases)
    assert projection.available_negative_candidates == 0
    assert projection.meets_floor is False


def test_expected_positive_candidates_never_count_toward_the_ceiling() -> None:
    """Even a large pool of unlabelled candidates does not help if none of them
    is declared expected_negative — the ceiling only counts the stratum a
    stratified batch would actually oversample."""
    negative_cases: frozenset[str] = frozenset()
    items = [_item(f"case_pos_{i:03d}:commits_judge:0#r0", scorer="commits_judge") for i in range(100)]
    projection = project_yield("commits_judge", [], items, frozenset(), negative_cases)
    assert projection.ceiling_minority_n == 0
    assert projection.meets_floor is False


def test_needs_review_and_unadjudicated_existing_rows_do_not_count() -> None:
    """Mirrors label_adequacy's own exclusions: a drifted (needs_review) row or
    one with no human_verdict yet contributes to neither class."""
    pending = _label("case_x:tone_judge:0", "tone_judge", human_verdict=None)
    drifted = _label("case_y:tone_judge:0", "tone_judge", human_verdict=False).model_copy(
        update={"needs_review": True}
    )
    projection = project_yield("tone_judge", [pending, drifted], [], frozenset(), frozenset())
    assert projection.existing_minority_n == 0
    assert projection.existing_n_clusters == 0


# ---------------------------------------------------------------------------
# project_all / format_projection_table
# ---------------------------------------------------------------------------


def test_project_all_projects_every_scorer_in_order() -> None:
    negative_cases = frozenset({"case_neg_a"})
    items = [_item("case_neg_a:commits_judge:0#r0", scorer="commits_judge")]
    projections = project_all(["commits_judge", "tone_judge"], [], frozenset(), items, negative_cases)
    assert [p.scorer for p in projections] == ["commits_judge", "tone_judge"]
    assert projections[1].available_negative_candidates == 0


def test_format_projection_table_names_the_floor_and_every_scorer() -> None:
    projections = [
        ProjectedYield(
            scorer="commits_judge",
            existing_minority_n=0,
            existing_n_clusters=0,
            available_negative_candidates=37,
            available_negative_clusters=37,
            ceiling_minority_n=37,
            ceiling_n_clusters=37,
            meets_floor=True,
        ),
        ProjectedYield(
            scorer="refusal_judge",
            existing_minority_n=0,
            existing_n_clusters=0,
            available_negative_candidates=0,
            available_negative_clusters=0,
            ceiling_minority_n=0,
            ceiling_n_clusters=0,
            meets_floor=False,
            reason="refusal_judge: projected ceiling insufficient",
        ),
    ]
    text = format_projection_table(projections)
    assert str(MIN_MINORITY_LABELS) in text
    assert str(MIN_CASE_CLUSTERS) in text
    assert "commits_judge" in text and "CLEARS FLOOR" in text
    assert "refusal_judge" in text and "REFUSED" in text
