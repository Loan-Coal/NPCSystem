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
        drifted: Keys whose criteria hash changed under a stored human verdict —
            the verdict is kept but flagged needs_review (EVAL-P20.3b: output_text
            is no longer part of the drift definition; see _has_drifted).
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
    return list(existing)


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
            f"  WARNING: {len(result.drifted)} row(s) flagged needs_review — the "
            f"scorer's criteria changed (EVAL-P20.3b: output_text is no longer part "
            f"of the drift definition) under an existing human verdict: {shown}{more}"
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
    """True if the criteria the human judged against has changed.

    DRIFT DEFINITION (EVAL-P20.3b / ISSUE-168 rescope, superseding EVAL-P20.3a
    Step 3's ISSUE-160 fix — chosen via AskUserQuestion, DEC-181): a
    `human_verdict` stays trusted as long as the scorer's `criteria` is
    unchanged, regardless of the exact `output_text` the NPC produced or what
    the automated `scorer_verdict` currently says. This redefines what a
    stored `human_verdict` means: it is no longer "a human read *this exact
    response* and judged it", it is "a human judged how this scorer's
    criteria applies to this case, and that judgment survives paraphrase."

    Why: DEC-176 measured byte-identical reproduction as low as 4.2% at the
    shipped `max_tokens=512` — an exact-output-text trust policy invalidates
    ~295 rows on every regeneration *by design*, regardless of whether the
    NPC's answer actually changed in substance. `output_sha256` is still
    computed and stored on every row (see calibration_records.py) as an
    evidence/audit trail — it is simply no longer read here.

    This does not weaken the live anti-hallucination safety gate: the guard/
    capability rate in summary.py scores every run's *current* text fresh via
    matchers.py's judges on every call, independent of any stored
    `human_verdict`. A stale-trusted `human_verdict` can only degrade the
    calibration/kappa signal (is the automated judge trustworthy?), never let
    an actual hallucination through unflagged.

    Compares the hash only when both sides carry one — rows written before
    content addressing existed have empty hashes and must not be reported as
    drifted.
    """
    old = existing.criteria_sha256
    new = incoming.criteria_sha256
    return bool(old and new and old != new)


def _refresh(
    existing: CalibrationLabel,
    incoming: CalibrationLabel,
    *,
    replace_pre_label: bool,
) -> CalibrationLabel:
    """Return existing with machine fields taken from incoming, human fields kept.

    Args:
        existing: Row currently on disk.
        incoming: Freshly derived row for the same (record_id, scorer) key.
        replace_pre_label: When True, incoming's pre_label/pre_labeller_model
            overwrite existing's unconditionally (ISSUE-175) — the explicit
            opt-in for importing a genuine second-rater pass (e.g. Opus,
            EVAL-P22.3) over rows that already carry a pre_label. Default
            False preserves the historical behaviour: pre_label is not in
            _MACHINE_FIELDS because label_import normally sources it from a
            not-necessarily-fresh reference-labelling file, so an incoming
            value is not trustworthy by default and is only cleared (never
            replaced) on drift.
    """
    update: dict[str, object] = {f: getattr(incoming, f) for f in _MACHINE_FIELDS}
    if replace_pre_label:
        update["pre_label"] = incoming.pre_label
        update["pre_labeller_model"] = incoming.pre_labeller_model
    if _has_drifted(existing, incoming):
        if not replace_pre_label:
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
    *,
    replace_pre_label: bool = False,
) -> MergeResult:
    """Merge incoming labels into existing ones, never losing a human verdict.

    For each incoming row that matches an existing (record_id, scorer):
    machine-derived fields are refreshed and human_verdict / adjudicated_at /
    notes / human_labeller are preserved. pre_label / pre_labeller_model are
    preserved by default (see _refresh) unless replace_pre_label=True. If
    the criteria hash changed under an adjudicated row, the row is
    additionally flagged needs_review rather than silently re-pointed at
    different content.

    Args:
        existing: Rows currently on disk (may be empty).
        incoming: Freshly derived rows from label_import.
        replace_pre_label: When True, incoming's pre_label/pre_labeller_model
            overwrite existing's for every matched row — the explicit opt-in
            for importing a genuine second-rater pass (ISSUE-175).
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
        merged.append(_refresh(old, new, replace_pre_label=replace_pre_label))
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
