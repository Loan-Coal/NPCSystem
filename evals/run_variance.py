"""
Module: run_variance
Layer: evals (eval harness — not part of src/)
Purpose: Describe what was DELIBERATELY VARIED between two comparable runs, so an A/B
         report names its own independent variable instead of just two gen_ids.
Dependencies: stdlib only (typing)
Used by: evals/compare.py (the report's "differs:" line); tests/unit/evals/test_trend_attribution.py

Does NOT: decide comparability. That is compare.py's `_comparability_error`, which refuses
on harness_version / judge_model / k. The fields described here are the opposite kind: they
are EXPECTED to differ, because they are the thing under test. Reporting them is what stops
a confident McNemar verdict being attached to the wrong cause.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["NO_VARIANT_DELTA", "VARIANT_FIELDS", "describe_variant_delta"]

NO_VARIANT_DELTA: str = "no declared variant difference (arms differ only by run identity)"
"""Reported when two arms match on every variant field.

Said explicitly rather than by printing nothing: a silent absence reads as "not checked",
and an A/B whose arms turned out identical is a finding, not a blank.
"""

VARIANT_FIELDS: tuple[str, ...] = (
    "retrieval_profile",
    "dialogue_prompt_hash",
    "git_sha",
    "prompt_token_budget",
)
"""Fields that identify an experimental arm, in report order."""

_ABSENT = "<absent>"


def describe_variant_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    """Return a human-readable description of the variant fields that differ.

    A field missing on one side is reported as differing rather than treated as equal:
    an older arm that predates a field is a real comparability caveat, and silently
    calling it "the same" is exactly the kind of quiet equality this harness exists to
    avoid.

    Args:
        before: Variant fields of the baseline arm.
        after: Variant fields of the candidate arm.
    Returns:
        A one-line summary naming each differing field and both values, or
        NO_VARIANT_DELTA when every field matches.
    """
    parts: list[str] = []
    for field in VARIANT_FIELDS:
        lhs = before.get(field, _ABSENT)
        rhs = after.get(field, _ABSENT)
        if lhs != rhs:
            parts.append(f"{field}: {lhs!r} -> {rhs!r}")
    return "; ".join(parts) if parts else NO_VARIANT_DELTA
