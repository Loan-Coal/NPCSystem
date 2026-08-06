"""
Module: test_retrieval_join
Layer: test (unit)
Purpose: Verify compute_crosstab and score_record correctly classify JudgedRecords
         into the 2×2 retrieval_hit × case_passed cross-table.
Dependencies: pytest, evals.retrieval_join, eval_records, retrieved_item
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from eval_records import JudgedRecord
from evals.retrieval_join import CrossTab, PerRecordResult, compute_crosstab, score_record
from retrieved_item import RetrievedItem


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _make_record(
    case_id: str,
    passed: bool,
    retrieved_keys: list[str],
    kind: str = "keyword_none",
    index: int = 0,
) -> JudgedRecord:
    """Build a minimal JudgedRecord for testing."""
    items = tuple(
        RetrievedItem(key=k, tier="unknown", priority=0, text="")
        for k in retrieved_keys
    )
    return JudgedRecord(
        record_id=f"{case_id}:{kind}:{index}",
        source="runner",
        npc_id="test_npc",
        player_id="test_player",
        player_message="test question",
        npc_response="test answer",
        criteria="test criteria",
        judge_kind=None,
        expected_polarity="pass_on_yes",
        passed=passed,
        score=passed,
        reasoning="",
        retrieved_context=items,
    )


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_retrieved_but_failed_is_a_generation_failure() -> None:
    """Retrieval hit + judge fail → retrieved_and_failed (generation failure)."""
    record = _make_record(
        case_id="case_adv_foo",
        passed=False,
        retrieved_keys=["character:aldric_merchant"],
    )
    annotations = {"case_adv_foo": ["aldric_merchant"]}
    result = compute_crosstab([record], annotations)

    assert result.retrieved_and_failed == 1, (
        "A record where a relevant node was retrieved but the judge failed must be "
        "classified as a generation failure (retrieved_and_failed cell)."
    )
    assert result.retrieved_and_passed == 0
    assert result.not_retrieved_and_failed == 0
    assert result.not_retrieved_and_passed == 0


# ---------------------------------------------------------------------------
# All four 2×2 cells
# ---------------------------------------------------------------------------


def test_retrieved_and_passed_cell() -> None:
    """Retrieval hit + judge pass → retrieved_and_passed."""
    record = _make_record(
        case_id="case_adv_bar",
        passed=True,
        retrieved_keys=["character:mira_innkeeper"],
    )
    annotations = {"case_adv_bar": ["mira_innkeeper"]}
    result = compute_crosstab([record], annotations)

    assert result.retrieved_and_passed == 1
    assert result.retrieved_and_failed == 0


def test_not_retrieved_and_failed_is_retrieval_failure() -> None:
    """Retrieval miss + judge fail → not_retrieved_and_failed (retrieval failure)."""
    record = _make_record(
        case_id="case_neg_baz",
        passed=False,
        retrieved_keys=["character:unrelated_node"],
    )
    annotations = {"case_neg_baz": ["northern_war_begins"]}
    result = compute_crosstab([record], annotations)

    assert result.not_retrieved_and_failed == 1
    assert result.retrieved_and_failed == 0


def test_not_retrieved_and_passed_is_lucky() -> None:
    """Retrieval miss + judge pass → not_retrieved_and_passed (lucky pass)."""
    record = _make_record(
        case_id="case_adv_lucky",
        passed=True,
        retrieved_keys=[],
    )
    annotations = {"case_adv_lucky": ["northern_war_begins"]}
    result = compute_crosstab([record], annotations)

    assert result.not_retrieved_and_passed == 1
    assert result.retrieved_and_passed == 0


# ---------------------------------------------------------------------------
# Four-cell sum invariant
# ---------------------------------------------------------------------------


def test_four_cells_sum_to_annotated_count() -> None:
    """The four 2×2 cells must always sum to annotated_count."""
    records = [
        _make_record("case_adv_a", passed=True, retrieved_keys=["character:mira_innkeeper"]),
        _make_record("case_adv_b", passed=False, retrieved_keys=["character:mira_innkeeper"]),
        _make_record("case_neg_c", passed=False, retrieved_keys=["character:unrelated"]),
        _make_record("case_adv_d", passed=True, retrieved_keys=[]),
        _make_record("case_unannotated_e", passed=True, retrieved_keys=[]),
    ]
    annotations = {
        "case_adv_a": ["mira_innkeeper"],
        "case_adv_b": ["mira_innkeeper"],
        "case_neg_c": ["northern_war_begins"],
        "case_adv_d": ["northern_war_begins"],
        # case_unannotated_e intentionally absent
    }
    result = compute_crosstab(records, annotations)

    assert result.annotated_count == 4
    assert result.excluded_count == 1
    assert result.total_input == 5
    assert (
        result.retrieved_and_passed
        + result.retrieved_and_failed
        + result.not_retrieved_and_failed
        + result.not_retrieved_and_passed
        == result.annotated_count
    )


# ---------------------------------------------------------------------------
# Excluded count is explicit, never silent
# ---------------------------------------------------------------------------


def test_unannotated_records_surface_in_excluded_count() -> None:
    """Records for unannotated cases must appear in excluded_count, never silently dropped."""
    record = _make_record(
        case_id="case_001_unannotated",
        passed=True,
        retrieved_keys=["character:mira_innkeeper"],
    )
    result = compute_crosstab([record], annotations={})

    assert result.excluded_count == 1
    assert result.annotated_count == 0
    assert result.total_input == 1


# ---------------------------------------------------------------------------
# score_record unit tests
# ---------------------------------------------------------------------------


def test_score_record_hit_when_relevant_retrieved() -> None:
    """score_record marks retrieval_hit=True when a relevant node is in retrieved context."""
    record = _make_record(
        case_id="case_adv_foo",
        passed=False,
        retrieved_keys=["character:mira_innkeeper", "rag:northern_war_begins"],
    )
    per_record = score_record(record, relevant=["northern_war_begins"])

    assert per_record.retrieval_hit is True
    assert per_record.recall > 0.0


def test_score_record_miss_when_no_relevant_retrieved() -> None:
    """score_record marks retrieval_hit=False when no relevant node is retrieved."""
    record = _make_record(
        case_id="case_neg_foo",
        passed=False,
        retrieved_keys=["character:mira_innkeeper"],
    )
    per_record = score_record(record, relevant=["northern_war_begins"])

    assert per_record.retrieval_hit is False
    assert per_record.recall == 0.0


def test_score_record_exposes_precision() -> None:
    """score_record computes precision_at_k alongside recall_at_k."""
    record = _make_record(
        case_id="case_adv_foo",
        passed=True,
        retrieved_keys=["character:mira_innkeeper", "character:aldric_merchant"],
    )
    per_record = score_record(record, relevant=["mira_innkeeper"])

    # 1 of 2 retrieved items is relevant → precision = 0.5, recall = 1.0
    assert per_record.precision == pytest.approx(0.5)
    assert per_record.recall == pytest.approx(1.0)


def test_empty_retrieved_context_is_miss() -> None:
    """A record with no retrieved_context is always a retrieval miss."""
    record = _make_record(
        case_id="case_adv_empty",
        passed=False,
        retrieved_keys=[],
    )
    per_record = score_record(record, relevant=["aldric_merchant"])

    assert per_record.retrieval_hit is False
    assert per_record.recall == 0.0
