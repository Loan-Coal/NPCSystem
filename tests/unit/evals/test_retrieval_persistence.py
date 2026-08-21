"""
Module: tests.unit.evals.test_retrieval_persistence
Layer: test (unit)
Purpose: Retrieval metrics must be written to disk, not only printed. `evals retrieval`
         took no arguments and printed to stdout, so precision@k could never be trended,
         compared or gated — the one metric in the contract with no artifact behind it.
Dependencies: pytest; evals.retrieval_summary
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from retrieval_summary import (  # noqa: E402
    RETRIEVAL_METRICS_FILE,
    RetrievalSummary,
    write_retrieval_metrics,
)


def _summary() -> RetrievalSummary:
    return RetrievalSummary(
        total_cases=15, mean_precision_at_k=0.31, mean_recall_at_k=0.44,
        mean_mrr=0.52, cases_above_threshold=4,
    )


def test_metrics_are_written_as_json_into_the_generation_dir(tmp_path: Path) -> None:
    written = write_retrieval_metrics(_summary(), gen_dir=tmp_path, retrieval_profile="default")

    assert written == tmp_path / RETRIEVAL_METRICS_FILE
    assert written.exists()


def test_persisted_metrics_carry_every_summary_field(tmp_path: Path) -> None:
    write_retrieval_metrics(_summary(), gen_dir=tmp_path, retrieval_profile="default")
    payload = json.loads((tmp_path / RETRIEVAL_METRICS_FILE).read_text(encoding="utf-8"))

    assert payload["total_cases"] == 15
    assert payload["mean_precision_at_k"] == 0.31
    assert payload["mean_recall_at_k"] == 0.44
    assert payload["mean_mrr"] == 0.52
    assert payload["cases_above_threshold"] == 4


def test_persisted_metrics_name_the_profile_they_were_measured_under(tmp_path: Path) -> None:
    """A precision number without its retrieval profile cannot be attributed to an arm."""
    write_retrieval_metrics(_summary(), gen_dir=tmp_path, retrieval_profile="aggressive")
    payload = json.loads((tmp_path / RETRIEVAL_METRICS_FILE).read_text(encoding="utf-8"))

    assert payload["retrieval_profile"] == "aggressive"


def test_writing_creates_the_directory_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "does_not_exist_yet"
    write_retrieval_metrics(_summary(), gen_dir=target, retrieval_profile="default")

    assert (target / RETRIEVAL_METRICS_FILE).exists()
