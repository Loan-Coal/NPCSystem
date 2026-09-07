"""
Module: label_export
Layer: evals (eval harness — not part of src/)
Purpose: Library primitives for exporting transcript records as batches of at
         most 25 items for the CLI labelling pass (EVAL-P5.6, replacing
         EVAL-P5.2's httpx runner). Each item carries record_id, scorer,
         npc_id, player_message, criteria, output_text, and — for graph
         scorer records — a vocabulary snapshot. scorer_verdict and all judge
         verdicts are NEVER emitted: the artifact is void if the labeller can
         see the answer being measured.
         ExportItem and the GenerationRecord derivation logic live in
         export_item.py (shared with transcript_index.py's label_import join);
         this module re-exports them for backward compatibility and owns only
         filtering and batch writing.
         Has no CLI of its own (measurement-remediation trim, 2026-09):
         the only user-facing verb is `label-export-stratified`, which applies
         DEC-260's adequacy floor before writing anything. The unguarded
         `label-export` verb let a labelling pass skip that floor and was
         retired; `write_export_batches` remains the primitive
         `label_export_stratified.py` composes.
Dependencies: json, pathlib, export_item
Used by: label_export_stratified (the label-export-stratified verb)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from export_item import (
    GRAPH_SCORER_KINDS,
    ExportItem,
    build_export_item,
    build_export_items,
)

# Re-exported for backward compatibility: callers historically imported
# ExportItem/build_export_item/build_export_items/GRAPH_SCORER_KINDS from this
# module. Do not remove without checking for external importers.
__all__ = [
    "ExportItem",
    "build_export_item",
    "build_export_items",
    "GRAPH_SCORER_KINDS",
    "MAX_BATCH_SIZE",
    "filter_by_scorer",
    "write_export_batches",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BATCH_SIZE: int = 25


# ---------------------------------------------------------------------------
# Scorer filtering (hand-labelling ergonomics)
# ---------------------------------------------------------------------------


def filter_by_scorer(
    items: Sequence[ExportItem],
    scorers: set[str] | None,
) -> list[ExportItem]:
    """Keep only items whose scorer is in `scorers`.

    Used to export a labelling set for the scorers worth a human's time. Scorers
    whose verdict never varies across a run (e.g. schema, which passed every
    record) cannot yield a meaningful kappa no matter how carefully they are
    labelled, so excluding them is a real saving rather than a shortcut.

    Args:
        items: Export items to filter.
        scorers: Scorer names to keep; None means keep everything.
    Returns:
        Items in original order, filtered.
    Raises:
        ValueError: If a requested scorer matches no item — a silent empty
            export would look like a completed pass with nothing to label.
    """
    if scorers is None:
        return list(items)

    present = {item.scorer for item in items}
    unknown = scorers - present
    if unknown:
        raise ValueError(
            f"No items for scorer(s) {sorted(unknown)}. Present in this transcript: "
            f"{sorted(present)}"
        )
    return [item for item in items if item.scorer in scorers]


# ---------------------------------------------------------------------------
# Batch writing
# ---------------------------------------------------------------------------


def write_export_batches(
    items: Sequence[ExportItem],
    out_dir: Path,
    batch_size: int = MAX_BATCH_SIZE,
) -> list[Path]:
    """Write items as JSON batch files of at most batch_size items each.

    Files are named batch_001.json, batch_002.json, …
    Creates out_dir and parents if needed; overwrites any existing batch files.

    Args:
        items: ExportItems to write.
        out_dir: Directory to write batch files into.
        batch_size: Maximum number of items per batch file (default 25).
    Returns:
        Ordered list of Path objects for the written batch files.
    Raises:
        ValueError: If batch_size is less than 1.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    items_list = list(items)

    for batch_num, start in enumerate(range(0, max(len(items_list), 1), batch_size), 1):
        batch = items_list[start : start + batch_size]
        if not batch:
            break
        path = out_dir / f"batch_{batch_num:03d}.json"
        payload = [item.model_dump() for item in batch]
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths.append(path)

    return paths
