"""
gossip_distort.py - Pure deterministic gossip distortion function.
Layer: engines
Purpose: Apply a deterministic, hash-seeded distortion strategy to a rumour summary so gossip mutates predictably as it propagates.

Does NOT: access databases or external services.

Dependencies injected: None.
"""

from hashlib import sha256
from typing import cast, Literal

from pydantic import BaseModel, ConfigDict, Field

from npc_engine.engines.gossip.distortion_strategy import STRATEGY_REGISTRY, REGISTRY_KEYS


DistortionType = Literal["omission", "exaggeration", "role_swap", "timeline_shift"]


class GossipDistortion(BaseModel):
    """Normalized distortion payload used by gossip engine."""

    summary: str
    distortion_type: DistortionType | None
    distortion_level: int = Field(ge=0, le=100)

    model_config = ConfigDict(frozen=True)


def compute_distortion_probability(honesty: int, trust: int, severity: int, base: float) -> float:
    """Compute the probability that a gossip event is distorted.

    This is NOT the same as BELIEVES_RUMOR.confidence. It is the RNG gate
    value used only to decide whether distortion occurs; it is never written
    to the graph.

    Args:
        honesty: Sharer honesty attribute (0–100); higher → lower distortion.
        trust: Trust from sharer to receiver (0–100); higher → lower distortion.
        severity: Event severity (0–100); higher → higher distortion.
        base: Base distortion rate (e.g. Settings.GOSSIP_DISTORTION_BASE).

    Returns:
        Probability in [0.0, 1.0].
    """
    honesty_term = (1.0 - (honesty / 100.0)) * 0.5
    severity_term = (severity / 100.0) * 0.3
    trust_term = (trust / 100.0) * 0.2
    return max(0.0, min(1.0, base + honesty_term + severity_term - trust_term))


def compute_confidence(source_trust: int, event_severity: int) -> int:
    """Compute the confidence value written to BELIEVES_RUMOR.confidence.

    Confidence represents how certain the receiving NPC is in what they heard.
    It is a function of how much the receiver trusts the source and how
    plausible the event is (higher severity → lower plausibility → lower
    confidence). It is entirely independent of whether distortion occurred.

    Args:
        source_trust: Trust level from sharer to receiver (0–100).
        event_severity: Event severity (0–100); high severity reduces plausibility.

    Returns:
        Confidence in [1, 100].
    """
    plausibility = 1.0 - (event_severity / 100.0) * 0.3
    raw = (source_trust / 100.0) * plausibility
    return int(min(100, max(1, round(raw * 100))))


def compute_seed_value(summary: str, honesty: int, trust: int, tick_id: int) -> int:
    """Compute the deterministic RNG seed for a gossip pair + tick.

    Args:
        summary: Source event summary text.
        honesty: Sharer honesty attribute.
        trust: Trust level from sharer to receiver.
        tick_id: Current game tick.

    Returns:
        Integer seed derived from SHA-256 of the combined inputs.
    """
    token = f"{summary}|{honesty}|{trust}|{tick_id}".encode("utf-8")
    return int(sha256(token).hexdigest()[:8], 16)


# Private aliases kept for internal use (avoid breaking call sites in this module)
_distortion_probability = compute_distortion_probability
_seed_value = compute_seed_value


def gossip_distort(
    event_summary: str,
    sharer_honesty: int,
    sharer_receiver_trust: int,
    event_severity: int,
    tick_id: int,
    distortion_base: float,
    faction_standing: int | None = None,
    hostile_distortion_factor: float = 1.0,
    is_canonical: bool = False,
) -> GossipDistortion:
    """Return a deterministic GossipDistortion based on bounded probability.

    Probability is derived from honesty, trust, and severity parameters.
    The tick_id and summary are hashed together to produce a stable, reproducible
    distortion outcome for the same inputs.

    When faction_standing is <= -50, the computed probability is multiplied by
    hostile_distortion_factor before the gate check, increasing distortion likelihood
    between hostile-faction pairs.

    Canonical events (is_canonical=True) are never distorted — they pass through
    unchanged with distortion_type=None and distortion_level=0.

    Args:
        event_summary: Source event summary text to potentially distort.
        sharer_honesty: Sharer's honesty attribute (0–100).
        sharer_receiver_trust: Trust level from sharer to receiver (0–100).
        event_severity: Event severity (0–100); higher severity increases distortion chance.
        tick_id: Current game tick; seeds deterministic randomness.
        distortion_base: Base distortion probability added to attribute terms.
        faction_standing: Best STANDS_WITH value between sharer and receiver factions,
            or None if no standing edges exist. Standing <= -50 triggers hostile amplification.
        hostile_distortion_factor: Multiplier applied to probability when faction_standing
            indicates hostility. Values above 1.0 increase distortion likelihood.
        is_canonical: When True, skip all distortion and return the summary unchanged.

    Returns:
        GossipDistortion with the (possibly modified) summary and distortion metadata.
    """
    if is_canonical:
        return GossipDistortion(summary=event_summary, distortion_type=None, distortion_level=0)

    probability = _distortion_probability(
        honesty=sharer_honesty,
        trust=sharer_receiver_trust,
        severity=event_severity,
        base=distortion_base,
    )
    if faction_standing is not None and faction_standing <= -50:
        probability = min(1.0, probability * hostile_distortion_factor)
    seed = _seed_value(event_summary, sharer_honesty, sharer_receiver_trust, tick_id)
    gate = (seed % 1000) / 1000.0
    if gate > probability:
        return GossipDistortion(summary=event_summary, distortion_type=None, distortion_level=0)

    distortion_type = cast(DistortionType, REGISTRY_KEYS[seed % len(REGISTRY_KEYS)])
    level = int(min(100, max(1, int(probability * 100))))
    distorted = STRATEGY_REGISTRY[distortion_type](event_summary)
    return GossipDistortion(summary=distorted, distortion_type=distortion_type, distortion_level=level)
