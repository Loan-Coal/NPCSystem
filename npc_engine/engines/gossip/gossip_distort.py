"""
gossip_distort.py - Pure deterministic gossip distortion function.

Does NOT: access databases or external services.

Dependencies injected: None.
"""

from hashlib import sha256
from typing import cast, Literal

from pydantic import BaseModel, ConfigDict, Field


DistortionType = Literal["omission", "exaggeration", "role_swap", "timeline_shift"]


class GossipDistortion(BaseModel):
    """Normalized distortion payload used by gossip engine."""

    summary: str
    distortion_type: DistortionType | None
    distortion_level: int = Field(ge=0, le=100)

    model_config = ConfigDict(frozen=True)


def _distortion_probability(honesty: int, trust: int, severity: int, base: float) -> float:
    honesty_term = (1.0 - (honesty / 100.0)) * 0.5
    severity_term = (severity / 100.0) * 0.3
    trust_term = (trust / 100.0) * 0.2
    return max(0.0, min(1.0, base + honesty_term + severity_term - trust_term))


def _seed_value(summary: str, honesty: int, trust: int, tick_id: int) -> int:
    token = f"{summary}|{honesty}|{trust}|{tick_id}".encode("utf-8")
    return int(sha256(token).hexdigest()[:8], 16)


def _apply_template(summary: str, distortion_type: str) -> str:
    if distortion_type == "omission":
        words = summary.split()
        return " ".join(words[: max(1, len(words) // 2)])
    if distortion_type == "exaggeration":
        return f"It was utterly catastrophic: {summary}"
    if distortion_type == "role_swap":
        return f"They say the opposite happened: {summary}"
    if distortion_type == "timeline_shift":
        return f"Long ago, {summary}"
    return summary


def gossip_distort(
    event_summary: str,
    sharer_honesty: int,
    sharer_receiver_trust: int,
    event_severity: int,
    tick_id: int,
    distortion_base: float,
) -> GossipDistortion:
    """Return deterministic distortion payload based on bounded probability."""

    probability = _distortion_probability(
        honesty=sharer_honesty,
        trust=sharer_receiver_trust,
        severity=event_severity,
        base=distortion_base,
    )
    seed = _seed_value(event_summary, sharer_honesty, sharer_receiver_trust, tick_id)
    gate = (seed % 1000) / 1000.0
    if gate > probability:
        return GossipDistortion(summary=event_summary, distortion_type=None, distortion_level=0)

    distortion_types = ["omission", "exaggeration", "role_swap", "timeline_shift"]
    distortion_type = cast(DistortionType, distortion_types[seed % len(distortion_types)])
    level = int(min(100, max(1, int(probability * 100))))
    distorted = _apply_template(event_summary, distortion_type=distortion_type)
    return GossipDistortion(summary=distorted, distortion_type=distortion_type, distortion_level=level)
