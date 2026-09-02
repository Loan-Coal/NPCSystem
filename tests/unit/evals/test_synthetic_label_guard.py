"""
Module: test_synthetic_label_guard
Layer: test (unit)
Purpose: Unit tests for synthetic_label_guard.py — the hard refusal that stops a
         mock/oracle labelling run from writing over the 393 hand-made human
         verdicts in calibration_records.LABELS_FILE. label-import's --out
         DEFAULTS to that file, so a target that forgets the flag destroys two
         sittings of human adjudication; this guard is the only thing between
         those two facts.
Dependencies: pathlib, pytest, calibration_records, label_import,
              label_import_errors, synthetic_label_guard (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from calibration_records import LABELS_FILE
from label_import_errors import SyntheticLabelTargetError
from synthetic_label_guard import (
    SYNTHETIC_MODEL_PREFIXES,
    check_synthetic_label_target,
    is_synthetic_model,
)

# ---------------------------------------------------------------------------
# The prefixes the guard recognises
# ---------------------------------------------------------------------------


def test_mock_and_oracle_are_both_recognised_as_synthetic() -> None:
    assert set(SYNTHETIC_MODEL_PREFIXES) == {"mock-", "oracle-"}


@pytest.mark.parametrize(
    "model",
    ["mock-random-v1", "oracle-matrix-v1", "mock-anything", "oracle-"],
)
def test_synthetic_model_ids_are_detected(model: str) -> None:
    assert is_synthetic_model(model) is True


@pytest.mark.parametrize("model", ["claude-opus-5", "mixtral:8x7b", "qwen2.5:7b", "mocking-bird"])
def test_real_model_ids_are_not_detected_as_synthetic(model: str) -> None:
    assert is_synthetic_model(model) is False


# ---------------------------------------------------------------------------
# The refusal itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["mock-random-v1", "oracle-matrix-v1"])
def test_synthetic_model_targeting_the_real_labels_file_raises(model: str) -> None:
    with pytest.raises(SyntheticLabelTargetError) as excinfo:
        check_synthetic_label_target(model, LABELS_FILE)
    assert model in str(excinfo.value)
    assert LABELS_FILE.name in str(excinfo.value)


def test_an_unresolved_relative_path_to_the_labels_file_is_still_refused() -> None:
    """The guard compares resolved paths — a relative spelling must not slip past."""
    relative = Path(os.path.relpath(LABELS_FILE, Path.cwd()))
    with pytest.raises(SyntheticLabelTargetError):
        check_synthetic_label_target("oracle-matrix-v1", relative)


def test_a_dot_segment_path_to_the_labels_file_is_still_refused() -> None:
    noisy = LABELS_FILE.parent / "." / ".." / "calibration" / LABELS_FILE.name
    with pytest.raises(SyntheticLabelTargetError):
        check_synthetic_label_target("mock-random-v1", noisy)


def test_synthetic_model_targeting_any_other_path_is_allowed(tmp_path: Path) -> None:  # quality-ok: check_synthetic_label_target raises on a disallowed target
    check_synthetic_label_target("oracle-matrix-v1", tmp_path / "labels_oracle.jsonl")


def test_a_real_model_may_still_target_the_real_labels_file() -> None:  # quality-ok: check_synthetic_label_target raises on a disallowed target
    """The guard must not break the human labelling path it exists to protect."""
    check_synthetic_label_target("claude-opus-5", LABELS_FILE)


# ---------------------------------------------------------------------------
# Wired into the CLI, and refusing before it reads anything
# ---------------------------------------------------------------------------


def test_label_import_main_refuses_a_synthetic_run_at_the_default_out(tmp_path: Path) -> None:
    """main() must refuse before touching any input file.

    The inputs below do not exist. If the guard runs first the call raises
    SyntheticLabelTargetError; if it runs late it raises FileNotFoundError
    instead — which would mean a run with real inputs had already begun.
    """
    from label_import import main

    argv = [
        "--raw", str(tmp_path / "absent_raw.jsonl"),
        "--transcript", str(tmp_path / "absent_outputs.jsonl"),
        "--judged", str(tmp_path / "absent_judged.jsonl"),
        "--model", "oracle-matrix-v1",
    ]
    with pytest.raises(SyntheticLabelTargetError):
        main(argv)


def test_label_import_main_allows_a_synthetic_run_at_an_explicit_out(tmp_path: Path) -> None:
    """Same call with --out elsewhere gets past the guard (and fails on missing input)."""
    from label_import import main

    argv = [
        "--raw", str(tmp_path / "absent_raw.jsonl"),
        "--transcript", str(tmp_path / "absent_outputs.jsonl"),
        "--judged", str(tmp_path / "absent_judged.jsonl"),
        "--model", "oracle-matrix-v1",
        "--out", str(tmp_path / "labels_oracle.jsonl"),
    ]
    with pytest.raises(FileNotFoundError):
        main(argv)
