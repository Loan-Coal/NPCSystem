"""
Module: label_import_errors
Layer: evals (eval harness — not part of src/)
Purpose: Typed exceptions for label_import.py's join, contamination and
         synthetic-target checks. Split out of label_import.py to stay under
         the 300-line cap.
Dependencies: stdlib only
Used by: label_import (raises), synthetic_label_guard (raises),
         tests/unit/evals/test_label_import.py and
         tests/unit/evals/test_synthetic_label_guard.py (catch)
"""

from __future__ import annotations

from pathlib import Path


class UnknownRecordIdError(Exception):
    """Raised when a raw label row references a record_id absent from the transcript index.

    Attributes:
        record_id: The offending identifier.
    """

    def __init__(self, record_id: str) -> None:
        self.record_id = record_id
        super().__init__(
            f"record_id {record_id!r} not found in transcript index — "
            f"this row cannot be imported without its source output_text and scorer_verdict."
        )


class MissingVerdictError(Exception):
    """Raised when a labelled record has no scorer_verdict in any judged file.

    A calibration row without the scorer's own verdict has nothing to compare the
    label against; importing it as a default False would fabricate a data point.
    Deterministic records need `python -m evals deterministic-verdicts` — the LLM
    judge pass alone does not cover them.

    Attributes:
        record_id: The offending identifier.
    """

    def __init__(self, record_id: str) -> None:
        self.record_id = record_id
        super().__init__(
            f"record_id {record_id!r} has no scorer_verdict in the supplied judged file(s). "
            f"Deterministic scorers require a deterministic-verdicts pass; pass its output "
            f"as an additional --judged argument."
        )


class ContaminatedRowError(Exception):
    """Raised when a raw label row carries a field that would contaminate labelling.

    A row containing output_text or scorer_verdict has been exposed to the
    answer it is measured against; the artifact is void if used.

    Attributes:
        record_id: The offending row's identifier.
        field: The contaminating field name.
    """

    def __init__(self, record_id: str, field: str) -> None:
        self.record_id = record_id
        self.field = field
        super().__init__(
            f"Raw label row {record_id!r} contains contaminating field {field!r} — "
            f"the labeller must not see scorer_verdict or output_text before labelling."
        )


class SyntheticLabelTargetError(Exception):
    """Raised when a mock/oracle labelling run targets the real human labels file.

    `label-import`'s `--out` defaults to `calibration_records.LABELS_FILE`, which
    holds hand-made human verdicts produced across two adjudication sittings.
    A synthetic run that forgets `--out` would overwrite them, and no re-run can
    reproduce them. This is a refusal, not a warning.

    Attributes:
        model: The offending `--model` identifier.
        out_path: The destination that resolved to the real labels file.
    """

    def __init__(self, model: str, out_path: Path) -> None:
        self.model = model
        self.out_path = out_path
        super().__init__(
            f"Refusing to write synthetic labels from model {model!r} to {out_path} — "
            f"that path resolves to the real human labels file. Human verdicts there "
            f"cannot be regenerated. Pass an explicit --out under "
            f"evals/calibration/oracle/ instead."
        )
