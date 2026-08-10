"""
Module: synthetic_label_guard
Layer: evals (eval harness — not part of src/)
Purpose: Refuse any synthetic (mock/oracle) labelling run whose destination
         resolves to the real human labels file. `label-import`'s `--out`
         defaults to `calibration_records.LABELS_FILE`, so a synthetic target
         that forgets the flag silently overwrites hand-made human verdicts
         that no re-run can reproduce.
Dependencies: os, pathlib, calibration_records, label_import_errors
Used by: label_import.main (called before any input is read),
         scripts/oracle_labeller.py (declares its own paths against it)
Does NOT: read or write any file. It compares paths and raises.

Kept out of label_import.py so the refusal is a named module with its own test
file rather than four lines buried in a CLI, and so the oracle labeller can
import the check without importing the whole import pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path

from calibration_records import LABELS_FILE
from label_import_errors import SyntheticLabelTargetError

# Model-identifier prefixes that mark a labelling pass as machine-generated.
# `mock-` is scripts/mock_labeller.py (random labels); `oracle-` is
# scripts/oracle_labeller.py (rule-based labels). Neither is a human verdict.
SYNTHETIC_MODEL_PREFIXES: tuple[str, ...] = ("mock-", "oracle-")


def is_synthetic_model(model: str) -> bool:
    """Return True when a `--model` identifier denotes a synthetic labeller.

    Args:
        model: The pre-labeller model identifier, e.g. 'oracle-matrix-v1'.
    Returns:
        True if the identifier carries a synthetic prefix.
    """
    return model.startswith(SYNTHETIC_MODEL_PREFIXES)


def _same_file(left: Path, right: Path) -> bool:
    """Compare two paths for identity without requiring either to exist."""
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def check_synthetic_label_target(model: str, out_path: Path) -> None:
    """Refuse a synthetic labelling run aimed at the real human labels file.

    Compares absolute, case-normalised paths, so a relative spelling or a path
    carrying `.`/`..` segments cannot slip past the check.

    Args:
        model: The `--model` identifier of the labelling pass.
        out_path: The destination labels file the run would write.
    Returns:
        None. A permitted combination returns silently.
    Raises:
        SyntheticLabelTargetError: If `model` is synthetic and `out_path`
            resolves to `calibration_records.LABELS_FILE`.
    """
    if not is_synthetic_model(model):
        return
    if _same_file(out_path, LABELS_FILE):
        raise SyntheticLabelTargetError(model, out_path)
