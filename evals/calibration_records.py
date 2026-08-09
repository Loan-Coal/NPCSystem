"""
Module: calibration_records
Layer: evals (eval harness — not part of src/)
Purpose: Pydantic v2 model for calibration labels and JSONL persistence.
         CalibrationLabel stores the scorer's own verdict, a pre-label from
         the reference model, an optional human verdict for EVAL-P5, and
         (criteria, player_message, observed) display passthrough so a human
         adjudicator can actually see what they are adjudicating against.
Dependencies: pydantic, stdlib (pathlib, typing)
Used by: label_runner, adjudicate, calibration (EVAL-P5.2–P5.5)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Default labels file location
# ---------------------------------------------------------------------------

LABELS_FILE: Path = Path(__file__).parent / "calibration" / "labels_v1.jsonl"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class CalibrationLabel(BaseModel):
    """One labelled output record for human adjudication.

    output_text is stored verbatim (not as a pointer) so the artifact is
    self-contained and reproducible even if the generation transcripts change.

    The headline calibration axis is scorer_verdict vs human_verdict — this
    measures how much you can trust the automated scorer. pre_label vs
    human_verdict is the secondary (reference-labeller vs maintainer).

    Attributes:
        record_id: Stable identifier from the generation transcript
            (same format as GenerationRecord.record_id).
        scorer: Which scorer is being calibrated (e.g. 'tone_judge').
        output_text: The NPC output text being labelled, stored inline.
        scorer_verdict: The automated scorer's own output for this row
            (True = pass, False = fail). Headline confusion axis.
        pre_label: Reference-model-proposed label (True = pass, False = fail).
            Secondary confusion axis.
        pre_labeller_model: Model that produced pre_label (e.g. 'claude-opus-5').
        human_verdict: Maintainer's verdict after adjudication; None = not yet done.
        adjudicated_at: ISO-8601 timestamp of adjudication, or None if pending.
        notes: Free-text annotation from the adjudicator (empty string when absent).
        criteria: What the scorer requires — verbatim judge criteria, or a
            rendering of a deterministic matcher's expectation. Display-only
            passthrough joined from the generation transcript at import time
            (see label_import); never sent to or echoed by the labeller.
            Defaults to "" so rows written before this field existed still load.
        player_message: The player's turn that prompted output_text. Same
            passthrough/backward-compat contract as criteria.
        observed: Response fields the matcher inspects beyond output_text
            (e.g. facial_expression.type, relation_deltas.trust) — the value
            actually being judged for in_set/range/schema scorers, which is
            otherwise absent from output_text and makes those rows unlabelable
            without it. Empty for text-only scorers. Same passthrough/
            backward-compat contract as criteria.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    output_text: str
    scorer_verdict: bool
    pre_label: bool
    pre_labeller_model: str
    human_verdict: bool | None
    adjudicated_at: str | None
    notes: str
    criteria: str = ""
    player_message: str = ""
    observed: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def write_calibration_labels(
    path: Path,
    rows: Sequence[CalibrationLabel],
) -> None:
    """Write calibration labels to a JSONL file, one record per line.

    Creates parent directories if needed. Overwrites any existing file.

    Args:
        path: Destination file path.
        rows: Sequence of CalibrationLabel instances to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(row.model_dump_json() for row in rows)
    path.write_text(content, encoding="utf-8")


def read_calibration_labels(path: Path) -> list[CalibrationLabel]:
    """Load calibration labels from a JSONL file.

    Args:
        path: Path to a JSONL file written by write_calibration_labels.
    Returns:
        List of CalibrationLabel instances in file order.
    Raises:
        FileNotFoundError: If path does not exist.
        ValidationError: If any line does not conform to CalibrationLabel schema.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        CalibrationLabel.model_validate_json(line)
        for line in lines
        if line.strip()
    ]
