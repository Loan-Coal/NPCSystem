"""
Module: raw_label_rows
Layer: evals (eval harness — not part of src/)
Purpose: The labeller-side contract — the minimal JSONL row a labelling pass may
         emit, its contamination guard, and the reader for that file. Kept apart
         from label_import (the join) because this is the only surface a labeller
         is allowed to influence, and it must stay small enough to audit at a
         glance.
Dependencies: json, pathlib, pydantic, label_import_errors
Used by: label_import
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from label_import_errors import ContaminatedRowError

# Fields a labeller must never supply. output_text would let a labeller echo
# back the text it was shown instead of judging it; scorer_verdict would let the
# machine's answer leak into the human axis, which is the one comparison the
# whole calibration artifact exists to make.
CONTAMINATING_FIELDS: frozenset[str] = frozenset({"output_text", "scorer_verdict"})


class RawLabelRow(BaseModel):
    """Minimal JSONL row produced by a labelling pass.

    The labeller returns only these four fields; all other CalibrationLabel
    fields are joined from the transcript and judged records by import_labels.

    Attributes:
        record_id: Stable identifier matching the generation transcript.
        scorer: Which scorer is being labelled (e.g. 'tone_judge').
        pre_label: The labeller's proposed verdict (True = pass, False = fail).
        notes: Free-text annotation from the labeller (empty string when absent).
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    pre_label: bool
    notes: str = ""


def check_contamination(raw: dict[str, Any], record_id: str) -> None:
    """Raise ContaminatedRowError if a raw row carries a forbidden field.

    Args:
        raw: The raw dict as read from the labelling JSONL.
        record_id: Identifier used in the error message.
    Raises:
        ContaminatedRowError: If any contaminating field is present.
    """
    for field in CONTAMINATING_FIELDS:
        if field in raw:
            raise ContaminatedRowError(record_id, field)


def read_raw_rows(path: Path) -> list[dict[str, Any]]:
    """Load raw label rows from a JSONL file written by a labelling pass.

    Args:
        path: Path to the labeller's minimal JSONL output.
    Returns:
        List of raw dicts in file order.
    Raises:
        FileNotFoundError: If the path does not exist.
        json.JSONDecodeError: If any line is not valid JSON.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
