"""
Module: calibration_records
Layer: evals (eval harness — not part of src/)
Purpose: Pydantic v2 model for calibration labels and JSONL persistence.
         CalibrationLabel stores the scorer's own verdict, a pre-label from
         the reference model, an optional human verdict for EVAL-P5, and
         (criteria, player_message, observed) display passthrough so a human
         adjudicator can actually see what they are adjudicating against.
Dependencies: pydantic, stdlib (logging, pathlib, typing)
Used by: label_runner, adjudicate, calibration (EVAL-P5.2–P5.5)
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

_logger = logging.getLogger(__name__)


class DuplicateLabelKeyError(ValueError):
    """Raised when a labels file contains the same (record_id, scorer) twice.

    Attributes:
        record_id: The duplicated record identifier.
        scorer: The duplicated scorer name.
    """

    def __init__(self, record_id: str, scorer: str) -> None:
        self.record_id = record_id
        self.scorer = scorer
        super().__init__(
            f"duplicate label key: {record_id} / {scorer}. "
            "Adjudication replaces rows by this key, so a duplicate means one "
            "human verdict silently overwrites another."
        )

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
            Secondary confusion axis. None means no current reference-labeller
            opinion exists for this row's content — label_merge clears it to
            None (alongside pre_labeller_model) whenever drift is detected
            (EVAL-P20.3a / ISSUE-153), rather than silently carrying forward an
            opinion that described different (pre-drift) content. calibration.py's
            secondary-axis functions exclude None rows rather than miscounting them.
        pre_labeller_model: Model that produced pre_label (e.g. 'claude-opus-5').
            "" when pre_label is None — no labeller produced the current opinion.
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
        needs_review: True when a merge (label_merge.merge_labels) detected the
            criteria changed under an existing human_verdict (EVAL-P20.3b /
            DEC-181: criteria only — an output_text change alone is NOT
            drift; see output_sha256/criteria_sha256 below and
            docs/EVAL_METHODOLOGY.md §3). Rows flagged here are excluded from
            every calibration statistic (calibration.py) and re-surfaced by
            adjudicate.collect_pending until a human re-judges them (EVAL-P19.0).
        prior_human_verdict: Set by adjudicate.collect_pending when it
            re-presents a needs_review row — the verdict recorded before the
            criteria changed, so the adjudicator sees what they decided last
            time. Cleared back to None once the row is re-adjudicated.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    output_text: str
    scorer_verdict: bool
    pre_label: bool | None
    pre_labeller_model: str
    human_verdict: bool | None
    adjudicated_at: str | None
    notes: str

    criteria: str = ""
    player_message: str = ""
    observed: dict[str, Any] = {}

    # Provenance / content addressing. All default so the rows written before
    # these fields existed still load unchanged.
    #
    # output_sha256: fingerprint of output_text at import time. Audit/evidence
    #   trail only (EVAL-P20.3b / DEC-181) — label_merge._has_drifted no longer
    #   reads it; a changed output_text does not by itself invalidate trust.
    # criteria_sha256: fingerprint of `criteria`. The ONLY hash _has_drifted
    #   reads — a change here is what sets needs_review.
    label_schema_version: int = 1
    gen_id: str = ""
    golden_set_version: str = ""
    output_sha256: str = ""
    criteria_sha256: str = ""
    human_labeller: str = ""
    needs_review: bool = False
    prior_human_verdict: bool | None = None

    @property
    def key(self) -> tuple[str, str]:
        """Identity of the labelled item: (record_id, scorer).

        One record can be judged by several scorers, so record_id alone is not
        unique. Every merge, dedup and replace keys on this pair.
        """
        return (self.record_id, self.scorer)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _backup_path(path: Path, timestamp: str) -> Path:
    """Return the .bak sibling path for a given file and timestamp."""
    return path.with_suffix(path.suffix + f".{timestamp}.bak")


def _holds_human_work(path: Path) -> bool:
    """True if the file on disk contains at least one adjudicated row.

    Read defensively: a corrupt or partially-written file is treated as holding
    human work, because the safe action for an unreadable file is to back it up
    rather than to overwrite it silently.
    """
    try:
        return any(row.human_verdict is not None for row in read_calibration_labels(path))
    except Exception as exc:
        _logger.warning("_holds_human_work: treating %s as human work — unreadable: %s", path, exc)
        return True


def write_calibration_labels(
    path: Path,
    rows: Sequence[CalibrationLabel],
) -> None:
    """Write calibration labels to a JSONL file, one record per line.

    Writes atomically (temp file + os.replace) so an interrupted write cannot
    truncate an existing label set — the adjudication CLI rewrites the whole
    file after every verdict, so a torn write during a multi-hour session would
    otherwise destroy the run. If the destination already holds adjudicated
    rows, a timestamped .bak copy is made first.

    Args:
        path: Destination file path. Parent directories are created if needed.
        rows: Sequence of CalibrationLabel instances to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and _holds_human_work(path):
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        shutil.copy2(path, _backup_path(path, stamp))

    content = "".join(row.model_dump_json() + "\n" for row in rows)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def read_calibration_labels(path: Path) -> list[CalibrationLabel]:
    """Load calibration labels from a JSONL file.

    Args:
        path: Path to a JSONL file written by write_calibration_labels.
    Returns:
        List of CalibrationLabel instances in file order.
    Raises:
        FileNotFoundError: If path does not exist.
        ValidationError: If any line does not conform to CalibrationLabel schema.
        DuplicateLabelKeyError: If any (record_id, scorer) appears twice. A
            duplicated key is never benign: adjudicate replaces rows by key, so
            a duplicate means one verdict silently overwrites another.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [
        CalibrationLabel.model_validate_json(line)
        for line in lines
        if line.strip()
    ]

    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row.key in seen:
            raise DuplicateLabelKeyError(row.record_id, row.scorer)
        seen.add(row.key)
    return rows
