"""
Module: record_identity
Layer: evals (eval harness — not part of src/)
Purpose: Compose and parse the repetition-qualified item id used by the calibration
         labelling pass. GenerationRecord.record_id is '<case>:<kind>:<index>' and
         deliberately omits `repetition`, so a k>1 run emits k records sharing one
         record_id with different npc_response text. Joining labels on the bare
         record_id silently collapses those repetitions (last one wins), attaching
         a label made against one response to a different response's verdict.
         This module makes the labelled unit uniquely addressable.
Dependencies: stdlib only
Used by: label_export (emits composite ids), label_import (joins on them)
Does NOT: mutate records, decide verdicts

Lives outside eval_records.py because that module is at its 300-line cap.
"""

from __future__ import annotations

# Separator between the base record_id and the repetition index. Chosen because
# ':' already delimits the three record_id segments and would be ambiguous.
REPETITION_SEPARATOR: str = "#r"


def composite_item_id(record_id: str, repetition: int) -> str:
    """Build the repetition-qualified id that uniquely addresses one labelled output.

    Args:
        record_id: The transcript's '<case>:<kind>:<index>' identifier.
        repetition: Zero-based repeat index within a k-repeat run.
    Returns:
        e.g. 'case_001:tone_judge:0#r2'. Always suffixed, including for
        repetition 0, so k=1 and k>1 runs share one unambiguous format.
    """
    return f"{record_id}{REPETITION_SEPARATOR}{repetition}"


def split_item_id(item_id: str) -> tuple[str, int]:
    """Recover (record_id, repetition) from a composite item id.

    An id with no separator is treated as repetition 0 so labels produced before
    this format existed still import rather than failing the whole batch.

    Args:
        item_id: A composite id, or a bare legacy record_id.
    Returns:
        (base record_id, repetition index).
    """
    base, separator, suffix = item_id.rpartition(REPETITION_SEPARATOR)
    if not separator:
        return item_id, 0
    try:
        return base, int(suffix)
    except ValueError:  # quality-ok: non-integer suffix → treat whole id as case 0, correct default
        return item_id, 0
