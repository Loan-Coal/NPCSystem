"""
Module: judge_identity
Layer: evals (eval harness — not part of src/)
Purpose: Resolve which judge actually scored a generation directory, for
         comparability checks between A/B arms. Prefers run_status.json (written
         by every pass since DEC-189, and a record of what really ran) over
         meta.json's config.judge_model (a generation-time snapshot that cannot
         distinguish a single-judge pass from a panel pass).
Dependencies: json, pathlib
Used by: compare._read_run_meta
Does NOT: score records, decide verdicts, import from src/npc_engine/

WHY THIS EXISTS (ISSUE-185)
compare.py refuses to compare two runs whose judge_model differs, but read that
value from meta.json — a RunConfig snapshot captured at *generation* time. Since
--panel landed, one generation config can be scored either by a single judge or
by the 3-model panel, producing materially different judged.jsonl verdicts under
a byte-identical meta.json. The gate therefore passed, and compare_runs reported
a confident McNemar verdict whose delta was partly the *instrument* changing
rather than the engine — the exact confound that makes an A/B comparison
worthless. Lives in its own module because compare.py is already over the
300-line cap and this is a self-contained lookup.
"""

from __future__ import annotations

import json
from pathlib import Path

_RUN_STATUS_FILE: str = "run_status.json"
_ENCODING: str = "utf-8"

_PANEL_KEY: str = "judge_panel"
_JUDGE_MODEL_KEY: str = "judge_model"

# Rendered identity for a panel pass, e.g. 'panel:llama3.1:8b+mixtral:8x7b'.
# The roster is sorted so that seat ORDER — which consensus_verdict is
# indifferent to, being a >=2-of-3 count — cannot cause a spurious refusal,
# while a changed seat still does.
_PANEL_PREFIX: str = "panel:"
_ROSTER_SEPARATOR: str = "+"


def render_panel_identity(roster: list[str]) -> str:
    """Render a panel roster as a stable comparability identity string."""
    return _PANEL_PREFIX + _ROSTER_SEPARATOR.join(sorted(roster))


def resolve_judge_identity(gen_dir: Path, fallback: str | None) -> str | None:
    """Return the judge identity that actually scored gen_dir.

    Args:
        gen_dir: Generation directory, which may contain a run_status.json.
        fallback: meta.json's config.judge_model, used for directories written
            before DEC-189 introduced run_status.json (and whenever that file is
            absent, unreadable, or records no judge at all).
    Returns:
        'panel:<sorted roster>' for a panel pass, the model name for a single
        judge pass, or `fallback` when nothing better is on disk.
    """
    status_path = gen_dir / _RUN_STATUS_FILE
    if not status_path.exists():
        return fallback
    try:
        status = json.loads(status_path.read_text(encoding=_ENCODING))
    except (json.JSONDecodeError, OSError):
        return fallback  # quality-ok: corrupt status must degrade, never abort a compare
    if not isinstance(status, dict):
        return fallback

    roster = status.get(_PANEL_KEY) or []
    if isinstance(roster, list) and roster:
        return render_panel_identity([str(seat) for seat in roster])

    single = status.get(_JUDGE_MODEL_KEY)
    return str(single) if single else fallback
