"""
Module: label_export_yield
Layer: evals (eval harness — not part of src/)
Purpose: Project, before any human labels a single new item, whether a scorer's
         adjudicated labels COULD reach DEC-260's adequacy floor
         (MIN_MINORITY_LABELS, MIN_CASE_CLUSTERS) if every unlabelled
         expected-negative candidate in a candidate transcript were labelled
         minority — the best case. Exists so a stratified label-export batch is
         never produced for a scorer that cannot possibly clear the floor from
         what is actually available (this task, 2026-09-04): report the numbers
         and refuse rather than shipping a batch that cannot support a kappa
         estimate.
Dependencies: dataclasses, typing; calibration_records (CalibrationLabel),
         export_item (ExportItem), label_adequacy (floor constants + the private
         minority-count helper, reused rather than re-derived — same precedent
         as deterministic_records reusing anti_hallucination_runner._is_grounded),
         label_export_strata (case_id_of, stratum_of)
Used by: label_export_stratified (CLI report + refusal gate),
         tests/unit/evals/test_label_export_yield.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from calibration_records import CalibrationLabel
from export_item import ExportItem
from label_adequacy import MIN_CASE_CLUSTERS, MIN_MINORITY_LABELS, _clean_adjudicated, _minority_count
from label_export_strata import case_id_of, stratum_of

LabelKey = tuple[str, str]


@dataclass(frozen=True)
class ProjectedYield:
    """Best-case projection of one scorer's minority-label count and cluster span.

    Attributes:
        scorer: Scorer identifier being projected.
        existing_minority_n: Minority count among labels that survive against the
            candidate transcript (label_survival.simulate_survival) — a label
            against output the candidate transcript no longer produces does not
            count toward a floor this transcript's batch would support.
        existing_n_clusters: Case clusters those surviving labels span.
        available_negative_candidates: Unlabelled expected-negative items for
            this scorer in the candidate transcript — the pool a stratified
            batch draws from.
        available_negative_clusters: Case clusters those candidates span.
        ceiling_minority_n: existing_minority_n + available_negative_candidates
            — the best case, every candidate labelled minority.
        ceiling_n_clusters: Size of the union of existing and candidate clusters.
        meets_floor: True iff the ceiling clears both DEC-260 floors.
        reason: Human-readable explanation naming the actual numbers; populated
            only when meets_floor is False.
    """

    scorer: str
    existing_minority_n: int
    existing_n_clusters: int
    available_negative_candidates: int
    available_negative_clusters: int
    ceiling_minority_n: int
    ceiling_n_clusters: int
    meets_floor: bool
    reason: str = ""


def project_yield(
    scorer: str,
    surviving_labels: Sequence[CalibrationLabel],
    candidate_items: Sequence[ExportItem],
    already_labelled_keys: frozenset[LabelKey],
    negative_cases: frozenset[str],
) -> ProjectedYield:
    """Project one scorer's best-case adequacy ceiling against a candidate transcript.

    Args:
        scorer: Scorer identifier to project.
        surviving_labels: This scorer's CalibrationLabel rows that survive
            against the candidate transcript (label_survival.simulate_survival).
        candidate_items: Every ExportItem built from the candidate transcript,
            any scorer — filtered to `scorer` internally.
        already_labelled_keys: Every (record_id, scorer) key that already
            carries a label in the labels file, surviving or not — excluded
            from the candidate pool so a projection never counts a row that
            cannot be freshly labelled.
        negative_cases: Declared expected-negative case_ids (label_export_strata).
    Returns:
        The projection.
    """
    clean_surviving = _clean_adjudicated(surviving_labels)
    existing_minority_n = _minority_count(clean_surviving)
    existing_clusters = {case_id_of(row.record_id) for row in clean_surviving}

    candidates = _unlabelled_negative_candidates(scorer, candidate_items, already_labelled_keys, negative_cases)
    candidate_clusters = {case_id_of(item.record_id) for item in candidates}

    return _build_projection(scorer, existing_minority_n, existing_clusters, candidates, candidate_clusters)


def _build_projection(
    scorer: str,
    existing_minority_n: int,
    existing_clusters: set[str],
    candidates: list[ExportItem],
    candidate_clusters: set[str],
) -> ProjectedYield:
    """Assemble the ProjectedYield from the counts project_yield derives.

    Split out of project_yield purely to keep that function under the 40-line cap.
    """
    ceiling_minority_n = existing_minority_n + len(candidates)
    ceiling_n_clusters = len(existing_clusters | candidate_clusters)
    meets_floor = ceiling_minority_n >= MIN_MINORITY_LABELS and ceiling_n_clusters >= MIN_CASE_CLUSTERS

    reason = "" if meets_floor else _refusal_reason(
        scorer, ceiling_minority_n, ceiling_n_clusters, len(candidates), len(candidate_clusters)
    )

    return ProjectedYield(
        scorer=scorer,
        existing_minority_n=existing_minority_n,
        existing_n_clusters=len(existing_clusters),
        available_negative_candidates=len(candidates),
        available_negative_clusters=len(candidate_clusters),
        ceiling_minority_n=ceiling_minority_n,
        ceiling_n_clusters=ceiling_n_clusters,
        meets_floor=meets_floor,
        reason=reason,
    )


def _unlabelled_negative_candidates(
    scorer: str,
    candidate_items: Sequence[ExportItem],
    already_labelled_keys: frozenset[LabelKey],
    negative_cases: frozenset[str],
) -> list[ExportItem]:
    """This scorer's candidate items that are both unlabelled and expected_negative.

    Split out of project_yield purely to keep that function under the 40-line cap.
    """
    return [
        item
        for item in candidate_items
        if item.scorer == scorer
        and (item.record_id, item.scorer) not in already_labelled_keys
        and stratum_of(case_id_of(item.record_id), negative_cases) == "expected_negative"
    ]


def _refusal_reason(
    scorer: str,
    ceiling_minority_n: int,
    ceiling_n_clusters: int,
    available_candidates: int,
    available_clusters: int,
) -> str:
    """Build the human-readable refusal reason, naming every number involved."""
    return (
        f"{scorer}: projected ceiling insufficient — {ceiling_minority_n} best-case "
        f"minority item(s) across {ceiling_n_clusters} cluster(s) "
        f"(need >={MIN_MINORITY_LABELS} across >={MIN_CASE_CLUSTERS}); only "
        f"{available_candidates} unlabelled expected-negative candidate(s) available "
        f"across {available_clusters} cluster(s) in this transcript"
    )


def project_all(
    scorers: Sequence[str],
    labels: Sequence[CalibrationLabel],
    surviving_keys: frozenset[LabelKey],
    candidate_items: Sequence[ExportItem],
    negative_cases: frozenset[str],
) -> list[ProjectedYield]:
    """Project every scorer's ceiling in one call, in the given order.

    Args:
        scorers: Scorer identifiers to project, in report order.
        labels: Every existing CalibrationLabel row (any scorer) — used both to
            find each scorer's surviving rows and to exclude every already-
            labelled key from the candidate pool.
        surviving_keys: (record_id, scorer) keys that survive against the
            candidate transcript (label_survival.simulate_survival().survives).
        candidate_items: Every ExportItem built from the candidate transcript.
        negative_cases: Declared expected-negative case_ids.
    Returns:
        One ProjectedYield per scorer, same order as `scorers`.
    """
    already_labelled = frozenset(row.key for row in labels)
    projections = []
    for scorer in scorers:
        surviving_for_scorer = [row for row in labels if row.key in surviving_keys and row.scorer == scorer]
        projections.append(
            project_yield(scorer, surviving_for_scorer, candidate_items, already_labelled, negative_cases)
        )
    return projections


def format_projection_table(projections: Sequence[ProjectedYield]) -> str:
    """Render a per-scorer projected-yield report, floor numbers included.

    Args:
        projections: Projections in the order they should print.
    Returns:
        A multi-line report, one row per scorer plus a header naming the floor.
    """
    lines = [f"Adequacy floor: >={MIN_MINORITY_LABELS} minority labels across >={MIN_CASE_CLUSTERS} clusters."]
    for p in projections:
        verdict = "CLEARS FLOOR" if p.meets_floor else "REFUSED"
        lines.append(
            f"  {p.scorer:<16} existing {p.existing_minority_n}/{p.existing_n_clusters}c "
            f"+ available {p.available_negative_candidates}/{p.available_negative_clusters}c "
            f"= ceiling {p.ceiling_minority_n}/{p.ceiling_n_clusters}c  [{verdict}]"
        )
        if p.reason:
            lines.append(f"    {p.reason}")
    return "\n".join(lines)
