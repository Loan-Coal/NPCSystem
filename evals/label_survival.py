"""
Module: label_survival
Layer: evals (eval harness — not part of src/)
Purpose: Predict, without spending a regeneration or a labelling pass, which
         existing calibration labels would survive against a candidate
         transcript. Runs the same criteria-hash comparison
         label_merge._has_drifted performs at import time, as a read-only
         simulation: "if I import this transcript right now, which of my
         393 human verdicts keep their trust, which get flagged
         needs_review, and which have no matching row at all?"
         Exists so "is the corpus frozen?" is a build-time check
         (scripts/check_label_survival.py) instead of something re-derived
         from memory before every regeneration or labelling spend — see
         project-harness/ROADMAP.md Phase A1 (EVAL-P20→P24 unblock plan).
Dependencies: pydantic, content_hash, export_item, transcript_index,
              calibration_records, record_identity
Used by: scripts/check_label_survival.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from calibration_records import CalibrationLabel
from content_hash import sha256_text
from export_item import ExportItem
from transcript_index import build_transcript_index

LabelKey = tuple[str, str]


class SurvivalReport(BaseModel):
    """Outcome of simulating a labels file against a candidate transcript.

    Attributes:
        survives: (record_id, scorer) keys whose stored human_verdict would
            keep its trust — either no matching transcript item exists to
            compare against yet, or the criteria hash is unchanged.
        drifts: Keys whose criteria_sha256 would change — label_merge would
            flag these needs_review and clear pre_label on import.
        orphaned: Keys present in the labels file with no matching
            (record_id, scorer) in the candidate transcript. Not itself a
            problem (label_merge keeps orphaned rows unchanged) but worth
            surfacing: it usually means a case was renamed or removed.
        new: (record_id, scorer) keys present in the candidate transcript
            with no existing label — rows a labelling pass must still cover.
    """

    model_config = ConfigDict(frozen=True)

    survives: tuple[LabelKey, ...]
    drifts: tuple[LabelKey, ...]
    orphaned: tuple[LabelKey, ...]
    new: tuple[LabelKey, ...]

    @property
    def is_frozen(self) -> bool:
        """True iff no existing label would drift or lose its match.

        This is the freeze-gate condition: it does not require zero `new`
        rows (a first-time labelling pass is expected to have plenty), only
        that nothing already labelled would be invalidated by importing this
        transcript.
        """
        return not self.drifts and not self.orphaned


def _has_drifted(existing_hash: str, incoming_hash: str) -> bool:
    """Same truth table as label_merge._has_drifted — kept in sync deliberately.

    Compares only when both sides carry a hash (DEC-181 / EVAL-P20.3b):
    rows written before content addressing existed have an empty
    criteria_sha256 and must not be reported as drifted.
    """
    return bool(existing_hash and incoming_hash and existing_hash != incoming_hash)


def simulate_survival(
    labels: Sequence[CalibrationLabel],
    transcript_path: Path,
) -> SurvivalReport:
    """Classify every (record_id, scorer) pair against a candidate transcript.

    Args:
        labels: Existing CalibrationLabel rows (e.g. read_calibration_labels
            of the real labels file).
        transcript_path: Path to a generation transcript's outputs.jsonl —
            either the transcript already on disk (a self-check: "is
            anything drifted right now, before I even regenerate?") or a
            freshly regenerated one (the real freeze-gate check for
            Phase B3).
    Returns:
        A SurvivalReport classifying every existing label key and every
        transcript-derived key.
    Raises:
        FileNotFoundError: If transcript_path does not exist.
        UnknownMatcherKindError: If a deterministic record's matcher kind
            has no criteria rendering rule.
    """
    incoming_index = build_transcript_index(transcript_path)
    incoming_by_key: dict[LabelKey, ExportItem] = {
        (item.record_id, item.scorer): item for item in incoming_index.values()
    }
    existing_by_key: dict[LabelKey, CalibrationLabel] = {row.key: row for row in labels}

    survives, drifts, orphaned = _classify_existing_labels(existing_by_key, incoming_by_key)
    new = [key for key in incoming_by_key if key not in existing_by_key]

    return SurvivalReport(
        survives=tuple(survives),
        drifts=tuple(drifts),
        orphaned=tuple(orphaned),
        new=tuple(new),
    )


def _classify_existing_labels(
    existing_by_key: dict[LabelKey, CalibrationLabel],
    incoming_by_key: dict[LabelKey, ExportItem],
) -> tuple[list[LabelKey], list[LabelKey], list[LabelKey]]:
    """Classify every existing label key against the incoming transcript index.

    Split out of simulate_survival purely to keep that function under the
    40-line cap.

    Returns:
        (survives, drifts, orphaned) key lists.
    """
    survives: list[LabelKey] = []
    drifts: list[LabelKey] = []
    orphaned: list[LabelKey] = []

    for key, row in existing_by_key.items():
        incoming = incoming_by_key.get(key)
        if incoming is None:
            orphaned.append(key)
            continue
        incoming_hash = sha256_text(incoming.criteria)
        if _has_drifted(row.criteria_sha256, incoming_hash):
            drifts.append(key)
        else:
            survives.append(key)

    return survives, drifts, orphaned


def format_survival_report(report: SurvivalReport) -> str:
    """Render a human-readable summary of a survival simulation.

    Never hides drift or orphaning behind a bare count: this module exists
    precisely so a "the corpus is frozen" claim is checkable, not asserted.
    """
    lines = [
        f"Labels checked: {len(report.survives) + len(report.drifts) + len(report.orphaned)}",
        f"  survive:  {len(report.survives)}",
        f"  drift:    {len(report.drifts)}",
        f"  orphaned: {len(report.orphaned)}",
        f"New (unlabelled) rows in the candidate transcript: {len(report.new)}",
    ]
    if report.drifts:
        shown = ", ".join(f"{r}/{s}" for r, s in report.drifts[:5])
        more = " ..." if len(report.drifts) > 5 else ""
        lines.append(f"  DRIFTED: {shown}{more}")
    if report.orphaned:
        shown = ", ".join(f"{r}/{s}" for r, s in report.orphaned[:5])
        more = " ..." if len(report.orphaned) > 5 else ""
        lines.append(f"  ORPHANED: {shown}{more}")
    lines.append("FROZEN" if report.is_frozen else "NOT FROZEN — see drift/orphan lists above")
    return "\n".join(lines)
