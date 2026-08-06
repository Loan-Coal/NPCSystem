"""
Module: retrieval_join
Layer: evals (evaluation harness)
Purpose: Cross-tabulate retrieval_hit × case_passed to separate generation failure
         from retrieval failure. Per annotated JudgedRecord, computes context recall
         and precision using evals.retrieval_matchers, then bins into a 2×2 table.
         Unannotated records surface as an explicit excluded count — never silently dropped
         (the whole phase exists because a silent empty join looked like a working table).
Dependencies: evals.context_keys, evals.retrieval_matchers, eval_records
Used by: evals.report (planned)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from eval_records import JudgedRecord
from evals.context_keys import node_id_from_key
from evals.retrieval_matchers import precision_at_k, recall_at_k

# Recall strictly above this threshold is treated as a retrieval "hit".
RECALL_HIT_THRESHOLD: float = 0.0


@dataclass(frozen=True)
class PerRecordResult:
    """Retrieval metrics plus verdict for one JudgedRecord.

    Attributes:
        record_id: Copied from the source JudgedRecord.
        case_id: Extracted from record_id (first colon-delimited segment).
        recall: recall_at_k over all retrieved context items.
        precision: precision_at_k over all retrieved context items.
        retrieval_hit: True when recall > RECALL_HIT_THRESHOLD.
        case_passed: Copied from JudgedRecord.passed.
    """

    record_id: str
    case_id: str
    recall: float
    precision: float
    retrieval_hit: bool
    case_passed: bool


@dataclass(frozen=True)
class CrossTab:
    """2×2 cross-tabulation of retrieval_hit × case verdict.

    Attributes:
        retrieved_and_passed: Retrieval hit AND judge passed.
        retrieved_and_failed: Retrieval hit BUT judge failed (generation failure).
        not_retrieved_and_failed: Retrieval miss AND judge failed (retrieval failure).
        not_retrieved_and_passed: Retrieval miss BUT judge passed (lucky pass).
        excluded_count: Records from unannotated cases (no relevant_node_ids entry).
        total_input: Total records fed in (annotated_count + excluded_count).
    """

    retrieved_and_passed: int
    retrieved_and_failed: int
    not_retrieved_and_failed: int
    not_retrieved_and_passed: int
    excluded_count: int
    total_input: int

    @property
    def annotated_count(self) -> int:
        """Number of annotated records — the four-cell denominator."""
        return (
            self.retrieved_and_passed
            + self.retrieved_and_failed
            + self.not_retrieved_and_failed
            + self.not_retrieved_and_passed
        )


def _case_id_from_record_id(record_id: str) -> str:
    """Extract the case_id prefix from a record_id string.

    Record IDs follow ``<case_id>:<judge_kind>:<index>``; this returns the first
    colon-delimited segment.

    Args:
        record_id: A JudgedRecord.record_id string.
    Returns:
        The case_id portion.
    """
    return record_id.split(":")[0]


def _node_ids_from_context(record: JudgedRecord) -> list[str]:
    """Extract node IDs from a record's retrieved_context items.

    Applies node_id_from_key to each item's key (strips prefix, e.g.
    ``character:mira_innkeeper`` → ``mira_innkeeper``).

    Args:
        record: A JudgedRecord.
    Returns:
        List of node IDs, one per retrieved context item.
    """
    return [node_id_from_key(item.key) for item in record.retrieved_context]


def score_record(
    record: JudgedRecord,
    relevant: list[str],
) -> PerRecordResult:
    """Compute retrieval metrics and verdict for one JudgedRecord.

    Uses recall_at_k and precision_at_k with k = number of retrieved items so that
    the full retrieved context is evaluated without truncation.

    Args:
        record: A judged eval record.
        relevant: Ground-truth relevant node IDs for this record's case.
    Returns:
        PerRecordResult with recall, precision, retrieval_hit flag, and case verdict.
    """
    case_id = _case_id_from_record_id(record.record_id)
    retrieved = _node_ids_from_context(record)
    k = len(retrieved)
    relevant_set = set(relevant)
    recall = recall_at_k(retrieved, relevant_set, k=k)
    precision = precision_at_k(retrieved, relevant_set, k=k)
    return PerRecordResult(
        record_id=record.record_id,
        case_id=case_id,
        recall=recall,
        precision=precision,
        retrieval_hit=recall > RECALL_HIT_THRESHOLD,
        case_passed=record.passed,
    )


def compute_crosstab(
    records: Sequence[JudgedRecord],
    annotations: dict[str, list[str]],
) -> CrossTab:
    """Cross-tabulate retrieval_hit × case_passed across a sequence of JudgedRecords.

    For each record, the case_id is extracted from record.record_id. If no annotation
    entry exists for that case_id, the record is counted as excluded. Otherwise,
    recall_at_k is computed over retrieved_context vs. relevant_node_ids and the record
    is binned into the matching 2×2 cell.

    Excluded records are surfaced explicitly in excluded_count and total_input — never
    silently dropped, so the caller always knows the full denominator.

    Args:
        records: JudgedRecords from a completed eval run.
        annotations: Mapping of case_id → relevant_node_ids list.
    Returns:
        CrossTab with four cell counts, excluded_count, and total_input.
    """
    retrieved_and_passed = 0
    retrieved_and_failed = 0
    not_retrieved_and_failed = 0
    not_retrieved_and_passed = 0
    excluded = 0

    for record in records:
        case_id = _case_id_from_record_id(record.record_id)
        if case_id not in annotations:
            excluded += 1
            continue
        per = score_record(record, annotations[case_id])
        if per.retrieval_hit and per.case_passed:
            retrieved_and_passed += 1
        elif per.retrieval_hit and not per.case_passed:
            retrieved_and_failed += 1
        elif not per.retrieval_hit and not per.case_passed:
            not_retrieved_and_failed += 1
        else:
            not_retrieved_and_passed += 1

    return CrossTab(
        retrieved_and_passed=retrieved_and_passed,
        retrieved_and_failed=retrieved_and_failed,
        not_retrieved_and_failed=not_retrieved_and_failed,
        not_retrieved_and_passed=not_retrieved_and_passed,
        excluded_count=excluded,
        total_input=len(records),
    )
