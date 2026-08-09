"""
Module: test_trust_policy
Layer: test (unit)
Purpose: Unit tests for scorer_trust_policy.py — kappa threshold policy that gates
         what claims a calibration score licenses (EVAL-P11.1).
Dependencies: pytest, scorer_trust_policy (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from scorer_trust_policy import PolicyRefusal, TrustLevel, check_publication

# ---------------------------------------------------------------------------
# RED anchor — must fail before the policy is implemented
# ---------------------------------------------------------------------------


def test_low_kappa_scorer_cannot_be_published() -> None:
    """A scorer at kappa 0.35 (below HIDDEN threshold 0.40) is refused publication."""
    refusal = check_publication("tone_judge", kappa=0.35, interval=(0.10, 0.48))
    assert refusal is not None, "Expected a refusal for kappa=0.35 but got None"
    assert refusal.scorer == "tone_judge"
    assert refusal.kappa == pytest.approx(0.35)
    assert refusal.interval == (pytest.approx(0.10), pytest.approx(0.48))
    assert refusal.trust_level == TrustLevel.HIDDEN


# ---------------------------------------------------------------------------
# Additional policy tests (GREEN)
# ---------------------------------------------------------------------------


def test_hidden_scorer_cannot_be_shown() -> None:
    """A scorer at kappa 0.35 is not even shown — trust_level is HIDDEN."""
    refusal = check_publication("tone_judge", kappa=0.35, interval=(0.10, 0.48))
    assert refusal is not None
    assert refusal.trust_level == TrustLevel.HIDDEN


def test_restricted_scorer_shown_but_not_published() -> None:
    """A scorer at kappa 0.55 (0.40–0.60) may be shown but not published."""
    refusal = check_publication("entity_judge", kappa=0.55, interval=(0.38, 0.70))
    assert refusal is not None
    assert refusal.trust_level == TrustLevel.RESTRICTED


def test_publishable_scorer_has_no_refusal() -> None:
    """A scorer at kappa 0.72 (>= 0.60) returns None — fully licensed for publication."""
    refusal = check_publication("knowledge_judge", kappa=0.72, interval=(0.55, 0.87))
    assert refusal is None


def test_boundary_exactly_at_hidden_threshold() -> None:
    """kappa == 0.40 is RESTRICTED (threshold is strict below-0.40 for HIDDEN)."""
    refusal = check_publication("edge_scorer", kappa=0.40, interval=(0.20, 0.58))
    assert refusal is not None
    assert refusal.trust_level == TrustLevel.RESTRICTED


def test_boundary_exactly_at_publish_threshold() -> None:
    """kappa == 0.60 is publishable — threshold is strict below-0.60 for RESTRICTED."""
    refusal = check_publication("edge_scorer", kappa=0.60, interval=(0.42, 0.76))
    assert refusal is None


def test_refusal_names_scorer_kappa_and_interval() -> None:
    """str(refusal) or its fields must expose scorer, kappa, and interval for reports."""
    refusal = check_publication("tone_judge", kappa=0.35, interval=(0.10, 0.48))
    assert refusal is not None
    text = str(refusal)
    assert "tone_judge" in text
    assert "0.35" in text
    # interval bounds appear somewhere
    assert "0.10" in text or "0.1" in text
    assert "0.48" in text
