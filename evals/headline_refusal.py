"""
Module: headline_refusal
Layer: evals (standalone eval harness, outside the npc_engine layer model)
Purpose: Decide, per battery, whether an engine rate may be published at all —
         refusing any rate at or below what a canned null responder scores.
Dependencies: null_baseline (evals/).
Used by: evals/summary.py (the console and markdown emitters).

The rule (R2.5 step 3c): never publish a headline where engine <= null. A rate that
a fixed string answering nothing can match is not evidence about the engine; it is
evidence about the battery. Applied strictly per population and never to a union,
because combining populations is the error DEC-243 removed.
"""

from __future__ import annotations

from typing import Any

#: Rendered in place of the rate when a battery fails the comparison.
_REFUSAL_TEMPLATE: str = (
    "REFUSED — engine {engine:.4f} <= null {null:.4f} over the same battery and "
    "expectation set ({expectation_set}, null measured {measured_utc}). "
    "A rate a canned non-answer matches is evidence about the battery, not the engine."
)


def refusal_for_battery(
    battery: str,
    engine_rate: float | None,
    baseline: dict[str, dict[str, Any]],
) -> str | None:
    """Return a refusal string when this battery's rate must not be published.

    Args:
        battery: Battery name, matching a key in the recorded baseline.
        engine_rate: The engine's measured rate over that battery; None when the
            battery did not run.
        baseline: {battery: entry}, from `null_baseline.load_null_baseline`.
    Returns:
        The refusal to print instead of the rate, or None when publication stands.

    Not gated (returns None) when the engine rate is absent — there is no comparison
    to draw — or when the battery has no recorded null. An unmeasured null is absence
    of evidence, and refusing on it would punish that as though it were evidence; the
    gap is surfaced by the baseline artifact's own completeness check instead.
    """
    if engine_rate is None:
        return None
    entry = baseline.get(battery)
    if entry is None:
        return None
    null_rate = float(entry["null_rate"])
    if engine_rate > null_rate:
        return None
    return _REFUSAL_TEMPLATE.format(
        engine=engine_rate,
        null=null_rate,
        expectation_set=entry["expectation_set"],
        measured_utc=entry["measured_utc"],
    )
