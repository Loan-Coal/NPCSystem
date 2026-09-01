"""
Module: test_check_ceiling_baseline
Layer: tests (unit)
Purpose: RED anchor + behaviour tests for the measured-ceiling artifact gate (B6/R2.7b).
Dependencies: pytest, ceiling_baseline + check_ceiling_baseline (scripts/)
Used by: `make test`, `make check` via test-cov.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ceiling_baseline import (  # noqa: E402
    BASELINE_PATH,
    CeilingBaseline,
    MissingCeilingBaselineError,
    read_ceiling_baseline,
)
from check_ceiling_baseline import main, provenance_gaps  # noqa: E402

_COMPLETE = {
    "roster_ceiling_tokens": 1151,
    "tier_maxima": {"tier_a": 857, "tier_b": 96, "tier_c": 145},
    "npc_id": "mira_innkeeper",
    "retrieval_profile": "default",
    "corpus_sha": "2b19e47a",
    "measured_at": "2026-08-27",
    "source": "DEC-215",
}


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "ceiling_baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8", newline="")
    return path


# ---------------------------------------------------------------------------
# provenance_gaps() — the RED anchor
# ---------------------------------------------------------------------------


def test_a_complete_baseline_has_no_provenance_gaps(tmp_path: Path) -> None:
    """The seeded DEC-215 measurement must satisfy its own gate."""
    assert provenance_gaps(read_ceiling_baseline(_write(tmp_path, _COMPLETE))) == ()


@pytest.mark.parametrize("field", ["npc_id", "corpus_sha", "measured_at", "retrieval_profile"])
def test_an_empty_provenance_field_is_a_gap(tmp_path: Path, field: str) -> None:
    """RED anchor for the ISSUE-246 shape: a measurement with no identity.

    `trend_v1.jsonl` records one row whose `generation_model_digest` is null, which is why
    ISSUE-246's exit condition ("two rows sharing a model digest") can never be satisfied —
    a measurement that does not say what it measured cannot be compared to a later one, and
    the defect is invisible until someone tries. The ceiling artifact refuses to be written
    or read in that state rather than discovering it a release later.
    """
    gaps = provenance_gaps(read_ceiling_baseline(_write(tmp_path, {**_COMPLETE, field: ""})))

    assert field in " ".join(gaps)


def test_a_missing_artifact_raises_rather_than_reading_as_green(tmp_path: Path) -> None:
    """Absent must not degrade to "nothing to check", which is the silent-pass shape."""
    with pytest.raises(MissingCeilingBaselineError):
        read_ceiling_baseline(tmp_path / "nope.json")


def test_a_corrupt_artifact_raises(tmp_path: Path) -> None:
    """Same reasoning as read_baseline's corrupt-vs-absent split in check_base_rate."""
    path = tmp_path / "ceiling_baseline.json"
    path.write_text("{not json", encoding="utf-8", newline="")

    with pytest.raises(MissingCeilingBaselineError):
        read_ceiling_baseline(path)


def test_the_model_rejects_a_non_positive_ceiling(tmp_path: Path) -> None:
    """A zero ceiling would let any window pass, which is worse than no artifact."""
    with pytest.raises(MissingCeilingBaselineError):
        read_ceiling_baseline(_write(tmp_path, {**_COMPLETE, "roster_ceiling_tokens": 0}))


# ---------------------------------------------------------------------------
# The shipped artifact and gate
# ---------------------------------------------------------------------------


def test_the_committed_artifact_records_the_dec_215_measurement() -> None:
    """The artifact replaces a hand-copied literal, so it must carry the same number."""
    baseline = read_ceiling_baseline()

    assert baseline.roster_ceiling_tokens == 1151
    assert baseline.tier_maxima == {"tier_a": 857, "tier_b": 96, "tier_c": 145}
    assert baseline.npc_id == "mira_innkeeper"


def test_the_committed_artifact_is_where_the_gate_looks() -> None:
    """A gate reading a different path than the probe writes would pass vacuously."""
    assert BASELINE_PATH.exists(), "scripts/ceiling_baseline.json must be committed"


def test_main_is_green_on_the_live_tree() -> None:
    """The shipped window must hold the recorded ceiling, with provenance intact."""
    assert main() == 0
