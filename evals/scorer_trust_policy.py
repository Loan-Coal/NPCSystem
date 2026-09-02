"""
Module: scorer_trust_policy
Layer: evals (eval harness — not part of src/)
Purpose: Kappa-based scorer trust policy. Defines what calibration score licenses
         what claim — below 0.40 a scorer is hidden; 0.40–0.60 it may be shown
         but not published; 0.60+ it is fully publishable. Encodes policy as a
         function so a report cannot quote a rate its own calibration does not support.
Dependencies: dataclasses, enum, typing
Used by: evals/report.py, tests/unit/evals/test_trust_policy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIDDEN_THRESHOLD: float = 0.40
PUBLISH_THRESHOLD: float = 0.60


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TrustLevel(str, Enum):
    """Publication tier assigned to a scorer based on its inter-rater kappa."""

    HIDDEN = "hidden"
    RESTRICTED = "restricted"
    PUBLISHABLE = "publishable"


@dataclass(frozen=True)
class PolicyRefusal:
    """Returned when a scorer cannot be published (or shown).

    All three identification fields are required so that any report that receives
    a refusal can name exactly which scorer failed and at what kappa + interval.
    """

    scorer: str
    kappa: float
    interval: tuple[float, float]
    trust_level: TrustLevel

    def __str__(self) -> str:
        lo, hi = self.interval
        return (
            f"PolicyRefusal(scorer={self.scorer!r}, kappa={self.kappa}, "
            f"interval=({lo}, {hi}), trust_level={self.trust_level.value!r})"
        )


# ---------------------------------------------------------------------------
# Policy function
# ---------------------------------------------------------------------------


def _trust_level_for(kappa: float) -> TrustLevel:
    """Bucket a point estimate into its trust tier (HIDDEN below 0.40, else RESTRICTED)."""
    return TrustLevel.HIDDEN if kappa < HIDDEN_THRESHOLD else TrustLevel.RESTRICTED


def check_publication(
    scorer: str,
    kappa: float,
    interval: tuple[float, float],
) -> PolicyRefusal | None:
    """Return a refusal if the scorer cannot be published; None if it can.

    Thresholds (docs/SCORER_TRUST_POLICY.md): kappa < 0.40 → HIDDEN, not shown at
    all; 0.40 <= kappa < 0.60 → RESTRICTED, shown but not published; kappa >= 0.60
    → publishable **only if the interval agrees**.

    The interval decides (CR-L03-02, DEC-244): publication requires the point
    estimate AND the CI lower bound to clear PUBLISH_THRESHOLD. A CI floor below
    the threshold caps the scorer at RESTRICTED rather than HIDDEN — the point
    estimate is real evidence, so the scorer may still be shown; it is the
    *publication* claim the interval refuses to license.

    Args:
        scorer: Identifier of the scorer being checked.
        kappa: Point-estimate Cohen's κ from the calibration run.
        interval: (lo, hi) 95 % bootstrap CI on kappa. Must be a real measurement —
            callers may not synthesise a placeholder (DEC-244).

    Returns:
        None when the scorer is fully publishable; a PolicyRefusal otherwise.
    """
    if kappa >= PUBLISH_THRESHOLD and interval[0] >= PUBLISH_THRESHOLD:
        return None
    return PolicyRefusal(
        scorer=scorer,
        kappa=kappa,
        interval=interval,
        trust_level=_trust_level_for(kappa),
    )
