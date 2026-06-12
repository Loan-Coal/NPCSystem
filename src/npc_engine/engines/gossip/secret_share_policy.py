"""
Module: secret_share_policy
Layer: engines
Purpose: Pure policy mapping a relationship Standing band to the probability that an
         NPC shares a secret during gossip (F3.1) — replacing the old flat random gate
         so secret-sharing tracks how the sharer regards the receiver.
Does NOT: read the graph, call the LLM, or hold state.
Dependencies injected: none (pure function over the Standing enum).
Used by: engines.gossip.gossip_handler (secret-propagation gate).
"""

from __future__ import annotations

from npc_engine.engines.relationship.standing import Standing

# Per-band secret-share probabilities (named — no magic numbers). Hostile/wary NPCs
# never confide; trust graded upward through neutral → friendly → allied.
SECRET_SHARE_PROB_HOSTILE: float = 0.0
SECRET_SHARE_PROB_WARY: float = 0.0
SECRET_SHARE_PROB_NEUTRAL: float = 0.1
SECRET_SHARE_PROB_FRIENDLY: float = 0.35
SECRET_SHARE_PROB_ALLIED: float = 0.6

_PROBABILITY_BY_STANDING: dict[Standing, float] = {
    Standing.HOSTILE: SECRET_SHARE_PROB_HOSTILE,
    Standing.WARY: SECRET_SHARE_PROB_WARY,
    Standing.NEUTRAL: SECRET_SHARE_PROB_NEUTRAL,
    Standing.FRIENDLY: SECRET_SHARE_PROB_FRIENDLY,
    Standing.ALLIED: SECRET_SHARE_PROB_ALLIED,
}


def secret_share_probability(standing: Standing) -> float:
    """Return the probability an NPC shares a secret given its Standing toward the receiver.

    Args:
        standing: The sharer's Standing band toward the receiver.

    Returns:
        Probability in [0.0, 1.0]; 0.0 for HOSTILE/WARY (never confide).
    """
    return _PROBABILITY_BY_STANDING[standing]
