"""
Module: label_merge
Layer: evals (eval harness — not part of src/)
Purpose: Reconcile a freshly-derived set of CalibrationLabel rows against the
         rows already on disk, refreshing machine-derived fields while
         preserving every human-authored field. This is what makes it safe to
         re-run the judge after fixing its criteria without re-labelling.
Dependencies: pydantic, calibration_records
Used by: label_import (the --merge path)
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from calibration_records import (
    CalibrationLabel,
    DuplicateLabelKeyError,
    read_calibration_labels,
)

# Fields recomputed from the transcript/judged files on every import. Everything
# NOT listed here is human-authored (or human-derived) and is carried forward
# from the existing row untouched.
_MACHINE_FIELDS: tuple[str, ...] = (
    "output_text",
    "scorer_verdict",
    "criteria",
    "player_message",
    "observed",
    "gen_id",
    "golden_set_version",
    "output_sha256",
    "criteria_sha256",
)


class MergeResult(BaseModel):
    """Outcome of reconciling incoming labels against existing ones.

    Attributes:
        rows: The merged label set, existing-file order first, then new rows.
        preserved: Count of rows whose existing human verdict was carried over.
        added: Count of incoming rows that had no existing counterpart.
        drifted: Keys whose output or criteria hash changed under a stored human
            verdict — the verdict is kept but flagged needs_review.
        orphaned: Keys present on disk but absent from the incoming set. Kept,
            never dropped: they represent human work whose record may simply be
            missing from this particular transcript.
    """

    model_config = ConfigDict(frozen=True)

    rows: tuple[CalibrationLabel, ...]
    preserved: int
    added: int
    drifted: tuple[str, ...]
    orphaned: tuple[str, ...]


def load_existing_or_refuse(
    out_path: Path,
    *,
    allow_merge: bool,
    allow_overwrite: bool,
) -> list[CalibrationLabel]:
    """Load the destination labels file, enforcing the no-clobber policy.

    Overwriting adjudicated rows is the one mistake that costs hours of
    irreplaceable labelling, so a bare command must never do it.

    Args:
        out_path: Destination labels file.
        allow_merge: True when --merge was given.
        allow_overwrite: True when --force-overwrite was given.
    Returns:
        Existing rows, or [] when the file does not exist.
    Raises:
        SystemExit: If the file holds human verdicts and neither flag was given.
    """
    if not out_path.exists():
        return []

    existing = read_calibration_labels(out_path)
    adjudicated = sum(1 for row in existing if row.human_verdict is not None)
    if adjudicated and not (allow_merge or allow_overwrite):
        raise SystemExit(
            f"refusing to overwrite {out_path}: it holds {adjudicated} human "
            f"verdict(s).\n"
            "  --merge            keep them and refresh the machine-derived fields\n"
            "  --force-overwrite  discard them (a .bak is written first)"
        )
    return existing


def format_merge_report(result: MergeResult, out_path: Path, imported: int) -> str:
    """Render a human-readable summary of a merge, including every warning.

    Drift and orphans are always surfaced: a silently shrunken or re-pointed
    label set is the failure mode this whole module exists to prevent.
    """
    lines = [
        f"Merged {imported} label(s) → {out_path}",
        f"  human verdicts preserved: {result.preserved}",
        f"  new rows added:           {result.added}",
    ]
    if result.drifted:
        shown = ", ".join(result.drifted[:5])
        more = " ..." if len(result.drifted) > 5 else ""
        lines.append(
            f"  WARNING: {len(result.drifted)} row(s) flagged needs_review — drifted "
            f"(output/criteria hash changed, or scorer_verdict changed on identical "
            f"content) under an existing human verdict: {shown}{more}"
        )
    if result.orphaned:
        lines.append(
            f"  NOTE: {len(result.orphaned)} existing label(s) had no record in this "
            f"transcript and were kept unchanged."
        )
    return "\n".join(lines)


def _index(rows: Sequence[CalibrationLabel]) -> dict[tuple[str, str], CalibrationLabel]:
    """Index labels by (record_id, scorer), rejecting duplicates."""
    out: dict[tuple[str, str], CalibrationLabel] = {}
    for row in rows:
        if row.key in out:
            raise DuplicateLabelKeyError(row.record_id, row.scorer)
        out[row.key] = row
    return out


def _has_drifted(existing: CalibrationLabel, incoming: CalibrationLabel) -> bool:
    """True if the content or verdict the human judged differs from the incoming row.

    Drift is either of two things (ISSUE-160):
      1. output_sha256 or criteria_sha256 changed — the human judged different text.
      2. scorer_verdict changed on hash-identical content — ordinary LLM judge
         non-determinism (no seed exists for judge calls, DEC-146) still means the
         automated verdict a human's judgment is being compared against has moved,
         even though the text itself has not. A verdict-only flip was previously
         invisible here (real case: case_adv_lira_troop_positions:tone_judge:4#r0).

    Compares hashes only when both sides carry one — rows written before content
    addressing existed have empty hashes and must not be reported as drifted.
    """
    for field in ("output_sha256", "criteria_sha256"):
        old = getattr(existing, field)
        new = getattr(incoming, field)
        if old and new and old != new:
            return True
    return existing.scorer_verdict != incoming.scorer_verdict


def _refresh(existing: CalibrationLabel, incoming: CalibrationLabel) -> CalibrationLabel:
    """Return existing with machine fields taken from incoming, human fields kept."""
    update: dict[str, object] = {f: getattr(incoming, f) for f in _MACHINE_FIELDS}
    if _has_drifted(existing, incoming):
        # pre_label/pre_labeller_model are not in _MACHINE_FIELDS (label_import
        # sources them from a separate, not-necessarily-fresh reference-labelling
        # file — incoming's value is not trustworthy either), so drift clears
        # them explicitly rather than leaving existing's now-stale opinion in
        # place forever (ISSUE-153). calibration.py's secondary-axis functions
        # treat pre_label=None as "no current opinion", not "opinion: False".
        update["pre_label"] = None
        update["pre_labeller_model"] = ""
        if existing.human_verdict is not None:
            update["needs_review"] = True
    return existing.model_copy(update=update)


def merge_labels(
    existing: Sequence[CalibrationLabel],
    incoming: Sequence[CalibrationLabel],
) -> MergeResult:
    """Merge incoming labels into existing ones, never losing a human verdict.

    For each incoming row that matches an existing (record_id, scorer):
    machine-derived fields are refreshed and human_verdict / adjudicated_at /
    notes / pre_label / pre_labeller_model / human_labeller are preserved. If
    the output or criteria hash changed under an adjudicated row, the row is
    additionally flagged needs_review rather than silently re-pointed at
    different content.

    Args:
        existing: Rows currently on disk (may be empty).
        incoming: Freshly derived rows from label_import.
    Returns:
        MergeResult carrying the merged rows and a report of what happened.
    Raises:
        DuplicateLabelKeyError: If either input contains a repeated key.
    """
    existing_by_key = _index(existing)
    incoming_by_key = _index(incoming)

    merged: list[CalibrationLabel] = []
    drifted: list[str] = []
    preserved = 0

    for key, old in existing_by_key.items():
        new = incoming_by_key.get(key)
        if new is None:
            merged.append(old)
            continue
        if _has_drifted(old, new):
            drifted.append(old.record_id)
        merged.append(_refresh(old, new))
        if old.human_verdict is not None:
            preserved += 1

    added = [row for key, row in incoming_by_key.items() if key not in existing_by_key]
    orphaned = [key[0] for key in existing_by_key if key not in incoming_by_key]

    return MergeResult(
        rows=tuple(merged + added),
        preserved=preserved,
        added=len(added),
        drifted=tuple(drifted),
        orphaned=tuple(orphaned),
    )
