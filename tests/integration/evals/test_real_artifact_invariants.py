"""
Module: tests.integration.evals.test_real_artifact_invariants
Layer: tests
Purpose: Integrity checks over the committed k3_73e6c36 eval artifact.
         These are INTEGRITY checks, NOT correctness checks — they verify the artifact
         is internally consistent and has not been silently edited, not that any
         pipeline computed the right value. All six invariants are green today.
         A green suite here does NOT mean the pipeline is correct; see EVAL-P15.2
         conservation identities and EVAL-P15.6 mutation gate for correctness evidence.
Dependencies: hashlib, json, pathlib, pytest; conftest fixtures
Used by: make test (via pytest discovery), EVAL-P15.2
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_case_id(record_id: str) -> str:
    """Extract case_id from record_id (format: case_id:matcher_kind:repetition)."""
    parts = record_id.rsplit(":", 2)
    return parts[0] if len(parts) == 3 else record_id


# ---------------------------------------------------------------------------
# Part A — artifact-shape invariants
# ---------------------------------------------------------------------------


def test_every_judged_record_resolves_in_the_transcript(
    outputs: list[dict[str, Any]],
    judged: list[dict[str, Any]],
    det_judged: list[dict[str, Any]],
) -> None:
    """Every record_id in judged.jsonl ∪ deterministic_judged.jsonl resolves in outputs.jsonl."""
    output_ids = {r["record_id"] for r in outputs}
    missing = []
    for row in judged:
        if row["record_id"] not in output_ids:
            missing.append(("judged", row["record_id"]))
    for row in det_judged:
        if row["record_id"] not in output_ids:
            missing.append(("deterministic_judged", row["record_id"]))
    assert missing == [], f"{len(missing)} verdict record_ids absent from outputs: {missing[:5]}"


def test_verdict_files_are_disjoint(
    judged: list[dict[str, Any]],
    det_judged: list[dict[str, Any]],
) -> None:
    """judged.jsonl and deterministic_judged.jsonl share no record_ids."""
    judged_ids = {r["record_id"] for r in judged}
    det_ids = {r["record_id"] for r in det_judged}
    overlap = judged_ids & det_ids
    assert overlap == set(), f"verdict files overlap on {len(overlap)} record_ids: {sorted(overlap)[:5]}"


def test_every_output_has_valid_repetition(
    outputs: list[dict[str, Any]],
    k_value: int,
) -> None:
    """Every output row has repetition ∈ {0 .. k-1}."""
    valid = set(range(k_value))
    bad = [r["record_id"] for r in outputs if r.get("repetition") not in valid]
    assert bad == [], f"{len(bad)} rows with repetition outside {{0..{k_value - 1}}}: {bad[:5]}"


def test_every_output_has_positive_duration(
    outputs: list[dict[str, Any]],
) -> None:
    """Every output row has duration_ms > 0."""
    bad = [r["record_id"] for r in outputs if not (r.get("duration_ms") or 0) > 0]
    assert bad == [], f"{len(bad)} rows with non-positive duration_ms: {bad[:5]}"


def test_every_output_has_nonempty_context(
    outputs: list[dict[str, Any]],
) -> None:
    """Every output row has a non-empty retrieved_context field."""
    bad = [r["record_id"] for r in outputs if not r.get("retrieved_context")]
    assert bad == [], f"{len(bad)} rows with empty retrieved_context: {bad[:5]}"


def test_label_sha256_matches_transcript(
    labels: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> None:
    """All 393 labels' output_sha256 fields match an npc_response in the transcript."""
    transcript_hashes = {
        hashlib.sha256(r["npc_response"].encode("utf-8")).hexdigest()
        for r in outputs
    }
    mismatches = [
        lbl["record_id"]
        for lbl in labels
        if lbl.get("output_sha256") not in transcript_hashes
    ]
    assert mismatches == [], (
        f"{len(mismatches)} labels whose output_sha256 does not appear in the transcript: "
        f"{mismatches[:5]}"
    )
