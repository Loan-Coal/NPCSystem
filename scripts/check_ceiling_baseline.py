#!/usr/bin/env python
"""
Module: check_ceiling_baseline
Layer: harness (repo-level dev tool)
Purpose: Red when the recorded assembled-context ceiling has lost its provenance, or when
         the window that ships can no longer hold it (B6/R2.7b).
Dependencies: stdlib, pydantic (via ceiling_baseline), npc_engine.config.
Used by: `make check-ceiling-baseline`, tests/unit/scripts/test_check_ceiling_baseline.py.

WHAT THIS GATES, precisely: that the ceiling the tests assert against is a recorded
measurement carrying enough provenance to be compared to a later one, and that the shipped
default window still clears it. It does NOT re-measure — that needs a live stack and stays
operator-run (`make probe-ceiling ARGS='--record'`).

Why provenance is a gate rather than a nicety: ISSUE-246 is the worked example. The trend
stack records one row whose `generation_model_digest` is null, so its exit condition ("two
rows sharing a model digest") can never be satisfied by any future row — the measurement
cannot say what it measured, and nothing noticed until someone tried to use it. A ceiling
recorded without its NPC, arm and corpus would fail the same way, one release later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ceiling_baseline import (  # noqa: E402
    PROVENANCE_FIELDS,
    BASELINE_PATH,
    CeilingBaseline,
    MissingCeilingBaselineError,
    read_ceiling_baseline,
)


def provenance_gaps(baseline: CeilingBaseline) -> tuple[str, ...]:
    """Name every provenance field the measurement left blank.

    Args:
        baseline: The recorded measurement.
    Returns:
        One human-readable reason per blank field; empty when the record is complete.
    """
    return tuple(
        f"{field} is blank: a measurement that does not record {field} cannot be "
        f"compared to a later one (the ISSUE-246 shape)"
        for field in PROVENANCE_FIELDS
        if not str(getattr(baseline, field, "")).strip()
    )


def _shipped_budget() -> int:
    """PROMPT_TOKEN_BUDGET as a checkout with no .env derives it, read off the class.

    `.env` is untracked, so the class default is what every other checkout runs. Reading
    `Settings()` instead would pick up whatever the local `.env` says and pass vacuously —
    the same trap test_shipped_window_holds_the_measured_ceiling documents.
    """
    from npc_engine.config import MIN_PROMPT_TOKEN_BUDGET, Settings  # noqa: PLC0415
    from npc_engine.config_prompt_window import PROMPT_WINDOW_OVERHEAD_TOKENS  # noqa: PLC0415

    window = int(Settings.model_fields["OLLAMA_CONTEXT_LENGTH"].default)
    return max(MIN_PROMPT_TOKEN_BUDGET, window - PROMPT_WINDOW_OVERHEAD_TOKENS)


def budget_shortfall(baseline: CeilingBaseline) -> tuple[str, ...]:
    """Red when the shipped default budget cannot hold the recorded ceiling.

    Args:
        baseline: The recorded measurement.
    Returns:
        One reason when the budget is short; empty otherwise.
    """
    budget = _shipped_budget()
    if budget >= baseline.roster_ceiling_tokens:
        return ()
    return (
        f"shipped default budget {budget} is below the recorded roster ceiling "
        f"{baseline.roster_ceiling_tokens}: the configuration that ships cannot hold its "
        f"own assembled context and will drop tier-A items (ISSUE-209)",
    )


def main(path: Path | None = None) -> int:
    """Red when the recorded ceiling lost its provenance or the window cannot hold it.

    Args:
        path: Artifact to read; defaults to scripts/ceiling_baseline.json.
    Returns:
        0 when the record is complete and the window clears it, else 1.
    """
    print("check-ceiling-baseline:")
    try:
        baseline = read_ceiling_baseline(BASELINE_PATH if path is None else path)
    except MissingCeilingBaselineError as exc:
        print(f"  FAIL - {exc}")
        return 1

    reasons = provenance_gaps(baseline) + budget_shortfall(baseline)
    for reason in reasons:
        print(f"  {reason}")
    if reasons:
        print(f"  FAIL - {len(reasons)} problem(s) with the recorded ceiling.")
        return 1

    print(
        f"  OK - {baseline.roster_ceiling_tokens} tokens on {baseline.npc_id} "
        f"(arm={baseline.retrieval_profile}, corpus={baseline.corpus_sha}, "
        f"measured {baseline.measured_at}); shipped budget {_shipped_budget()} clears it."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measured-ceiling artifact gate (B6/R2.7b).")
    parser.add_argument("--path", type=Path, default=None, help="Artifact to check.")
    sys.exit(main(path=parser.parse_args().path))
