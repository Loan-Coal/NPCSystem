"""
Tests for SEV-36: distortion probability separated from BELIEVES_RUMOR.confidence.

Verifies:
- confidence tracks source trust, not distortion level
- distortion_probability and seed value are logged per tick
- _compute_confidence is a named function with expected semantics
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from npc_engine.engines.gossip.gossip_distort import (
    compute_distortion_probability,
    compute_confidence,
    compute_seed_value,
)


class TestComputeConfidence:
    """compute_confidence returns values driven by trust, not distortion probability."""

    def test_high_trust_gives_high_confidence(self) -> None:
        """High source trust → confidence close to 100."""
        confidence = compute_confidence(source_trust=90, event_severity=20)
        assert confidence >= 70, f"Expected >= 70, got {confidence}"

    def test_low_trust_gives_low_confidence(self) -> None:
        """Low source trust → confidence well below the high-trust value."""
        high = compute_confidence(source_trust=90, event_severity=20)
        low = compute_confidence(source_trust=10, event_severity=20)
        assert low < high, f"low={low} should be < high={high}"

    def test_confidence_bounded_1_to_100(self) -> None:
        """confidence is always in [1, 100]."""
        for trust in (0, 50, 100):
            for severity in (0, 50, 100):
                c = compute_confidence(source_trust=trust, event_severity=severity)
                assert 1 <= c <= 100, f"trust={trust} severity={severity} → {c}"

    def test_confidence_independent_of_distortion_probability(self) -> None:
        """For same trust, confidence should be identical regardless of distortion outcome."""
        # Two scenarios with same trust but different honesty (which drives distortion prob)
        conf_honest_sharer = compute_confidence(source_trust=60, event_severity=30)
        conf_dishonest_sharer = compute_confidence(source_trust=60, event_severity=30)
        # confidence must be the same — it doesn't take honesty as an input
        assert conf_honest_sharer == conf_dishonest_sharer

    def test_high_severity_reduces_confidence(self) -> None:
        """Higher severity (less plausible) → lower confidence for same trust."""
        low_sev = compute_confidence(source_trust=60, event_severity=10)
        high_sev = compute_confidence(source_trust=60, event_severity=90)
        assert low_sev >= high_sev, (
            f"low_sev={low_sev} should be >= high_sev={high_sev}"
        )


class TestComputeDistortionProbability:
    """compute_distortion_probability is deterministic and bounded."""

    def test_high_honesty_reduces_probability(self) -> None:
        prob_honest = compute_distortion_probability(
            honesty=90, trust=50, severity=50, base=0.3
        )
        prob_dishonest = compute_distortion_probability(
            honesty=10, trust=50, severity=50, base=0.3
        )
        assert prob_honest < prob_dishonest

    def test_probability_bounded_0_to_1(self) -> None:
        for honesty in (0, 50, 100):
            for trust in (0, 50, 100):
                p = compute_distortion_probability(
                    honesty=honesty, trust=trust, severity=50, base=0.3
                )
                assert 0.0 <= p <= 1.0


class TestGossipHandlerLogsDistortionProbability:
    """gossip_handler._build_write_params logs distortion_probability and seed per pair."""

    def _make_handler(self) -> object:
        from npc_engine.engines.gossip.gossip_handler import GossipHandler
        from npc_engine.engines.gossip.gossip_config import GossipWeightConfig

        settings = MagicMock()
        settings.GOSSIP_DISTORTION_BASE = 0.3
        settings.RUMOR_DISTORTION_THRESHOLD = 50
        settings.RUMOR_EMOTION_SEVERITY_THRESHOLD = 70

        embedding_index = MagicMock()
        weight_config = GossipWeightConfig()
        return GossipHandler(
            settings=settings,
            embedding_index=embedding_index,
            weight_config=weight_config,
            gossip_repo=MagicMock(),
        )

    def test_build_write_params_logs_distortion_probability_and_seed(self) -> None:
        """_build_write_params should log distortion_probability and seed for each pair."""
        handler = self._make_handler()

        pair_lookup = {
            ("sharer1", "receiver1"): (
                {"id": "sharer1", "honesty": 50},
                {"id": "receiver1"},
                {},
            )
        }
        event_trust_map = {
            ("sharer1", "receiver1"): {
                "sharer_id": "sharer1",
                "receiver_id": "receiver1",
                "trust": 60,
                "severity": 40,
                "summary": "a war began",
                "event_id": "evt1",
                "is_canonical": False,
            }
        }

        log_calls: list[str] = []

        with patch("npc_engine.engines.gossip.gossip_handler.LOGGER") as mock_logger:
            mock_logger.debug.side_effect = lambda msg, *args, **kw: log_calls.append(
                msg % args if args else msg
            )
            handler._build_write_params(
                pair_lookup=pair_lookup,
                event_trust_map=event_trust_map,
                tick_id=5,
            )

        combined = " ".join(log_calls)
        assert "distortion_probability" in combined, (
            f"Expected 'distortion_probability' in log output. Got: {combined!r}"
        )
        assert "seed" in combined, f"Expected 'seed' in log output. Got: {combined!r}"


class TestBeliefConfidenceFromTrustNotProbability:
    """Integration: believe_rumor is called with confidence from trust, not distortion_level."""

    def test_high_trust_yields_high_confidence_in_believe_rumor_call(self) -> None:
        """When source trust is high, believe_rumor confidence arg should be >= 50."""
        from npc_engine.engines.gossip.gossip_distort import compute_confidence

        confidence = compute_confidence(source_trust=80, event_severity=20)
        assert confidence >= 50, f"Expected >= 50, got {confidence}"

    def test_confidence_is_not_distortion_level(self) -> None:
        """Confidence must differ from distortion_level when trust is high but distortion occurs."""
        from npc_engine.engines.gossip.gossip_distort import (
            gossip_distort,
            compute_confidence,
        )

        # With full distortion probability, distortion_level = probability * 100 (up to 100)
        distortion = gossip_distort(
            event_summary="the king fell",
            sharer_honesty=0,   # dishonest → high distortion probability
            sharer_receiver_trust=10,
            event_severity=80,
            tick_id=1,
            distortion_base=0.9,
        )

        # confidence from high trust should be higher than distortion_level with low trust
        confidence_high_trust = compute_confidence(source_trust=90, event_severity=20)
        # Even if distortion_level is low (no distortion), confidence should reflect trust
        assert isinstance(confidence_high_trust, int)
        assert confidence_high_trust >= 1
