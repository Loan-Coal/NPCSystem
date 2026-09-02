"""
Module: null_baseline
Layer: evals (standalone eval harness, outside the npc_engine layer model)
Purpose: Load the recorded null-responder baseline — what a canned non-answer scores
         against each battery — so a published rate can be compared to it.
Dependencies: json, pathlib (stdlib).
Used by: headline_refusal, scripts/check_null_baseline.py.

The number lives in `evals/null_baseline.json` rather than in code, for the reason
DEC-242 established for the context ceiling: a measurement embedded in a source file
cannot say what it measured, so it rots silently. Each entry records the hedge, the
judge model, the expectation set and the date, and a reader can tell at a glance
whether the figure still describes the current battery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The recorded artifact. Rewritten by re-running the probe, never edited by hand.
NULL_BASELINE_PATH: Path = Path(__file__).resolve().parent / "null_baseline.json"

#: Fields every entry must carry. A rate without these is a guess, not a measurement.
REQUIRED_FIELDS: tuple[str, ...] = (
    "battery",
    "null_rate",
    "passes",
    "turns",
    "hedge_sha256",
    "judge_model",
    "expectation_set",
    "measured_utc",
)


class NullBaselineError(Exception):
    """Raised when the recorded baseline is missing, malformed, or incomplete."""


def load_null_baseline(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return {battery: entry} from the recorded artifact.

    Args:
        path: Override for the artifact location; defaults to NULL_BASELINE_PATH.
    Returns:
        The `batteries` mapping. Empty when the artifact is absent — an absent
        baseline means "not yet measured", which is not the same as "measured zero"
        and must not be treated as one.
    Raises:
        NullBaselineError: When the artifact exists but does not parse, or an entry
            omits a required provenance field.
    """
    target = path or NULL_BASELINE_PATH
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NullBaselineError(f"{target} is not valid JSON: {exc}") from exc
    batteries = raw.get("batteries")
    if not isinstance(batteries, dict):
        raise NullBaselineError(f"{target} has no 'batteries' object")
    for name, entry in batteries.items():
        _assert_complete(name, entry)
    return batteries


def _assert_complete(name: str, entry: Any) -> None:
    """Raise unless one battery entry carries every provenance field."""
    if not isinstance(entry, dict):
        raise NullBaselineError(f"battery {name!r} is not an object")
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    if missing:
        raise NullBaselineError(f"battery {name!r} is missing {', '.join(missing)}")
