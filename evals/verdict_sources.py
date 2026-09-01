"""
Module: verdict_sources
Layer: evals (eval harness utility — not part of src/)
Purpose: Load and unify verdict rows from judged.jsonl and deterministic_judged.jsonl
         into a single normalised sequence so summary and compare consume both verdict
         sources without needing to know which file a row came from.
Dependencies: json, logging, pathlib, collections; pydantic
Used by: summary (summarize_from_dir), compare (load_unified_rows, source_counts)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JUDGED_FILE: str = "judged.jsonl"
DET_JUDGED_FILE: str = "deterministic_judged.jsonl"

_ENCODING: str = "utf-8"
_SOURCE_JUDGED: Literal["judged"] = "judged"
_SOURCE_DET: Literal["deterministic"] = "deterministic"

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class VerdictRow(BaseModel):
    """Normalised verdict row from either verdict source.

    Attributes:
        record_id: Stable expectation-slot ID, e.g. 'case_pos_a:tone_judge:0'.
        case_id: Case this slot belongs to — from the 'case_id' key in judged.jsonl
                 or derived as the colon-prefix of record_id in deterministic_judged.jsonl.
        kind: Matcher or judge kind string (judge_kind or matcher_kind field).
        passed: Whether this slot passed after polarity was applied.
        source: Which file the row was read from ('judged' or 'deterministic').
        repetition: Repetition index within the case's k runs (default 0).
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    case_id: str
    kind: str
    passed: bool
    source: Literal["judged", "deterministic"]
    repetition: int = 0


# ---------------------------------------------------------------------------
# Private file readers
# ---------------------------------------------------------------------------


def _read_judged_file(path: Path) -> list[VerdictRow]:
    """Parse judged.jsonl into VerdictRow list, raising on malformed lines.

    Args:
        path: Path to judged.jsonl.
    Returns:
        Parsed rows; empty list if the file is absent.
    Raises:
        ValueError: On any malformed line — a corrupt row must not silently shrink
                    the denominator that compare and summarize rely on.
    """
    if not path.exists():
        return []
    rows: list[VerdictRow] = []
    for line in path.read_text(encoding=_ENCODING).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
            rows.append(
                VerdictRow(
                    record_id=raw["record_id"],
                    case_id=raw["case_id"],
                    kind=raw.get("judge_kind") or "",
                    passed=bool(raw["passed"]),
                    source=_SOURCE_JUDGED,
                    repetition=int(raw.get("repetition", 0)),
                )
            )
        except Exception as exc:
            raise ValueError(
                f"malformed judged row in {path}: {stripped[:80]!r}"
            ) from exc
    return rows


def _read_det_file(path: Path) -> list[VerdictRow]:
    """Parse deterministic_judged.jsonl into VerdictRow list, raising on malformed lines.

    case_id is derived from record_id by stripping the trailing :<kind>:<index> segments
    (the same convention judge_case_grouping.case_id_from_record_id uses).

    Args:
        path: Path to deterministic_judged.jsonl.
    Returns:
        Parsed rows; empty list if the file is absent.
    Raises:
        ValueError: On any malformed line.
    """
    if not path.exists():
        return []
    rows: list[VerdictRow] = []
    for line in path.read_text(encoding=_ENCODING).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
            record_id: str = raw["record_id"]
            rows.append(
                VerdictRow(
                    record_id=record_id,
                    case_id=record_id.rsplit(":", 2)[0],
                    kind=raw.get("matcher_kind") or "",
                    passed=bool(raw["passed"]),
                    source=_SOURCE_DET,
                    repetition=int(raw.get("repetition", 0)),
                )
            )
        except Exception as exc:
            raise ValueError(
                f"malformed deterministic row in {path}: {stripped[:80]!r}"
            ) from exc
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_unified_rows(gen_dir: Path) -> list[VerdictRow]:
    """Read both verdict sources and return a deduplicated unified list.

    judged.jsonl takes precedence over deterministic_judged.jsonl when both contain
    the same slot — the judge verdict is authoritative for any slot it covers.

    The dedup key is (record_id, repetition), not record_id alone (R2.6b / CR-L03-06).
    A record_id is `<case_id>:<judge_kind>:<index>` and encodes no repetition, so keying
    on it alone made all k repetitions of a slot collide and kept only the last one
    written. Measured on `k3_77688e7_regen1` before the fix: 975 rows in, 325 out —
    650 discarded, and every survivor carried repetition 2. Downstream that turned
    `summarize_from_dir` into a case counter reporting `guard_cases == guard_turns == 78`
    on a k=3 generation, which is the second guard denominator ISSUE-243 and the published
    170/186 disagreed with.

    Args:
        gen_dir: Generation directory containing judged.jsonl and/or
                 deterministic_judged.jsonl. Missing files are silently skipped.
    Returns:
        Combined VerdictRow list, deduplicated by (record_id, repetition);
        judged wins ties within one repetition.
    Raises:
        ValueError: If any line in either file fails to parse.
    """
    det_rows = _read_det_file(gen_dir / DET_JUDGED_FILE)
    judged_rows = _read_judged_file(gen_dir / JUDGED_FILE)
    seen: dict[tuple[str, int], VerdictRow] = {}
    for row in det_rows:
        seen[(row.record_id, row.repetition)] = row
    for row in judged_rows:
        # judged overwrites deterministic for the same slot in the same repetition
        seen[(row.record_id, row.repetition)] = row
    return list(seen.values())


def source_counts(rows: Sequence[VerdictRow]) -> dict[str, int]:
    """Count rows by source label.

    Args:
        rows: Unified verdict rows from load_unified_rows.
    Returns:
        Dict mapping source label to slot count (keys: 'judged', 'deterministic').
    """
    counts: dict[str, int] = {_SOURCE_JUDGED: 0, _SOURCE_DET: 0}
    for row in rows:
        counts[row.source] = counts.get(row.source, 0) + 1
    return counts


def to_summarize_results(rows: Sequence[VerdictRow]) -> list[dict]:
    """Convert unified rows into per-(case_id, repetition) result dicts for summarize().

    Each (case_id, repetition) pair becomes one result dict — matching the shape
    runner._run_case produces — with all matching slots as expectation entries.

    Args:
        rows: Unified VerdictRow list from load_unified_rows.
    Returns:
        List of per-turn result dicts consumable by summary.summarize.
    """
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row.case_id, row.repetition)].append(
            {"kind": row.kind, "passed": row.passed, "skipped": False, "detail": ""}
        )
    return [
        {
            "case_id": case_id,
            "expectations": exps,
            "passed": all(e["passed"] for e in exps),
        }
        for (case_id, _rep), exps in groups.items()
    ]
