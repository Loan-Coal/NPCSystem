#!/usr/bin/env python
"""
Module: ceiling_baseline
Layer: harness (repo-level dev tool)
Purpose: The recorded assembled-context ceiling measurement, and its read/write contract,
         so the shipped window is checked against an artifact with provenance rather than
         a literal hand-copied into a test (B6/R2.7b).
Dependencies: pydantic (stdlib otherwise).
Used by: scripts/check_ceiling_baseline.py, scripts/probe_context_ceiling.py (--record),
         tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py.

Mirrors the base_rate_contract.py / check_base_rate.py split: the model and its file I/O
live here, the gate decision lives in the checker.

WHAT THIS IS NOT: a re-measurement. Re-measuring needs a live stack, an API key and a
seeded graph, so it stays operator-run via `make probe-ceiling ... --record`. What is
gated is that the number the tests assert against is a RECORDED MEASUREMENT that says what
it measured, rather than a literal whose provenance lives only in a docstring and rots
silently when the corpus moves under it.

Tier naming: the probe reports tiers as `tier0/tierA/tierB/tierC` (the receipt's names),
while the shipped llm_config.yaml calls them `tier_a/tier_b/tier_c`. The artifact records
the SHIPPED names, because the assertion that consumes it compares against shipped tier
ceilings; `probe_context_ceiling.py` does the mapping when it writes. `tier_0` is optional
and absent from the seeded DEC-215 record, which measured only tiers A/B/C — an absent
tier reads as "not measured", never as zero.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "BASELINE_PATH",
    "CeilingBaseline",
    "MissingCeilingBaselineError",
    "read_ceiling_baseline",
    "write_ceiling_baseline",
]

BASELINE_PATH: Path = Path(__file__).resolve().parent / "ceiling_baseline.json"

#: Provenance fields that must be non-empty. Each one answers a question that makes the
#: measurement comparable to a later one; a blank answer is the ISSUE-246 failure shape.
PROVENANCE_FIELDS: tuple[str, ...] = ("npc_id", "retrieval_profile", "corpus_sha", "measured_at")


class MissingCeilingBaselineError(RuntimeError):
    """Raised when the artifact is absent, unparseable, or fails its own schema.

    Absent must not degrade to "nothing to check", and corrupt must not degrade to
    "no baseline" — both read as green, which is the silent-pass this gate exists to stop.
    """


class CeilingBaseline(BaseModel):
    """The recorded assembled-context ceiling the shipped window is judged against.

    Attributes:
        roster_ceiling_tokens: Largest assembled context across the probe roster. The
            LARGER of the receipt's per-item sum and the serialized blob, because a window
            sized to the smaller has headroom that does not exist.
        tier_maxima: Shipped tier name -> largest per-tier spend over the same run. An
            absent tier was not measured; it is never inferred as zero.
        npc_id: NPC that produced the roster maximum.
        retrieval_profile: Arm the assembly ran under. A ceiling measured on a narrow arm
            does not bound a wide one.
        corpus_sha: Corpus the measurement was taken over. The ceiling is a property of
            the corpus as much as of the code.
        measured_at: ISO date of the measurement.
        source: Decision or task that recorded it, for a reader tracing the number back.
    """

    model_config = ConfigDict(frozen=True)

    roster_ceiling_tokens: int = Field(gt=0)
    tier_maxima: dict[str, int]
    npc_id: str
    retrieval_profile: str
    corpus_sha: str
    measured_at: str
    source: str = ""


def read_ceiling_baseline(path: Path = BASELINE_PATH) -> CeilingBaseline:
    """Load the recorded measurement.

    Args:
        path: Artifact to read.
    Returns:
        The parsed measurement.
    Raises:
        MissingCeilingBaselineError: When the file is absent, unparseable, or fails the
            schema. Every one of those is a hard failure by design — see the class
            docstring for why none of them may read as green.
    """
    if not path.exists():
        raise MissingCeilingBaselineError(
            f"no ceiling baseline at {path}: record one with "
            f"`make probe-ceiling ARGS='--record'` against a live stack"
        )
    try:
        return CeilingBaseline.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, ValueError) as exc:
        raise MissingCeilingBaselineError(f"ceiling baseline at {path} is unreadable: {exc!r}") from exc


def write_ceiling_baseline(baseline: CeilingBaseline, path: Path = BASELINE_PATH) -> None:
    """Record `baseline` as the artifact the gate reads.

    Written with an explicit LF newline: .gitattributes normalizes this repo to LF, and a
    default text write on Windows produces CRLF, which rewrites the whole file in git's
    eyes and buries the one changed number in a whole-file diff.

    Args:
        baseline: The measurement to record.
        path: Artifact to write.
    """
    payload = json.dumps(baseline.model_dump(), indent=2)
    path.write_text(f"{payload}\n", encoding="utf-8", newline="")
