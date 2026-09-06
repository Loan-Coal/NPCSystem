"""
Module: label_export_strata
Layer: evals (eval harness — not part of src/)
Purpose: Declared (not derived) case-family stratum used to oversample
         expected-negative records in a stratified label-export batch. A case's
         stratum says whether it was authored to have a real chance of eliciting
         a minority (violation) human verdict — case_neg/case_adv, the guard
         battery — or not. Declared as a checked-in YAML list rather than a
         case_id prefix check at export time, so a naming-convention change (or
         a new case family) cannot silently reclassify a case (this task,
         2026-09-04; see evals/calibration/case_strata.yaml for the list).
Dependencies: pathlib, typing, yaml (PyYAML)
Used by: label_export_yield (projection), label_export_sampling (batch
         selection), tests/unit/evals/test_label_export_strata.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

Stratum = Literal["expected_negative", "expected_positive"]

#: Checked-in declaration of every case authored to elicit a minority verdict.
CASE_STRATA_FILE: Path = Path(__file__).parent / "calibration" / "case_strata.yaml"


def load_expected_negative_cases(path: Path = CASE_STRATA_FILE) -> frozenset[str]:
    """Read the declared expected-negative case_id list.

    Args:
        path: Path to the strata YAML file (default: the checked-in declaration).
    Returns:
        The declared case_ids. Empty if the file declares none.
    Raises:
        FileNotFoundError: If path does not exist — a missing declaration must
            not silently be read as "no case is negative", which is a
            different, false, claim.
    """
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return frozenset(str(case_id) for case_id in doc.get("expected_negative_cases", []))


def case_id_of(record_id: str) -> str:
    """Extract the case cluster id from a (possibly repetition-qualified) record_id.

    Mirrors calibration._extract_case_clusters / label_adequacy._cluster_count:
    the case_id is always the record_id's first ':'-delimited segment.
    """
    return record_id.split(":")[0]


def stratum_of(case_id: str, negative_cases: frozenset[str]) -> Stratum:
    """Classify one case_id by its declared stratum.

    Args:
        case_id: A case's bare identifier (see case_id_of).
        negative_cases: The declared expected-negative set (load_expected_negative_cases).
    Returns:
        "expected_negative" if case_id is declared, "expected_positive" otherwise.
    """
    return "expected_negative" if case_id in negative_cases else "expected_positive"
