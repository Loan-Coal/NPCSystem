"""
Module: player_model_engine
Layer: engines
Purpose: Derives an NPC's theory-of-mind model of the player (perceived_trust,
         perceived_intent) from relation scalars and an optional interaction signal.
Does NOT: call LLMs, query Neo4j, manage sessions, or schedule ticks.
Dependencies injected: None (stateless pure engine — no constructor dependencies).
Used by: (slice 2) scheduler tick handler that persists via graph.player_model_writer.
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Trust composite bounds
# ---------------------------------------------------------------------------

TRUST_CLAMP_MIN: int = 0
TRUST_CLAMP_MAX: int = 100

# ---------------------------------------------------------------------------
# Intent classification thresholds
# ---------------------------------------------------------------------------

HOSTILE_TRUST_THRESHOLD: int = 25   # perceived_trust < this → hostile
FRIENDLY_TRUST_THRESHOLD: int = 60  # perceived_trust >= this → friendly

# ---------------------------------------------------------------------------
# Intent label constants
# ---------------------------------------------------------------------------

INTENT_HOSTILE: str = "hostile"
INTENT_NEUTRAL: str = "neutral"
INTENT_FRIENDLY: str = "friendly"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PlayerModelInput(BaseModel):
    """Input scalars used to derive an NPC's model of the player.

    Attributes:
        npc_id: Unique identifier of the NPC building the model.
        player_id: Unique identifier of the player being modelled.
        trust: Raw trust scalar from the RELATES_TO edge (any integer).
        fear: Raw fear scalar from the RELATES_TO edge (any integer).
        affection: Raw affection scalar from the RELATES_TO edge (any integer).
        interaction_signal: Optional bump to apply after deriving from scalars
            (positive = trust boost, negative = trust penalty). None means no signal.
    """

    npc_id: str
    player_id: str
    trust: int
    fear: int
    affection: int
    interaction_signal: int | None = None


class PlayerModelUpdate(BaseModel):
    """Output of the player-model derivation step.

    Attributes:
        npc_id: NPC that owns this model.
        player_id: Player being modelled.
        perceived_trust: Derived trust score clamped to [0, 100].
        perceived_intent: Classified intent label string.
    """

    npc_id: str
    player_id: str
    perceived_trust: int
    perceived_intent: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PlayerModelEngine:
    """Pure stateless engine that computes a PlayerModelUpdate from input scalars.

    No I/O, no LLM, no graph calls. Inject as-is; no constructor arguments required.
    """

    def derive(self, inputs: PlayerModelInput) -> PlayerModelUpdate:
        """Derive an NPC's player model from relation scalars.

        Composite trust = clamp(trust + affection - fear, 0, 100).
        An optional interaction_signal is applied as a direct addend before clamping.
        Intent is classified by comparing the clamped trust against named thresholds.

        Args:
            inputs: PlayerModelInput carrying the NPC/player IDs and relation scalars.

        Returns:
            PlayerModelUpdate with perceived_trust and perceived_intent populated.
        """
        raw = inputs.trust + inputs.affection - inputs.fear
        if inputs.interaction_signal is not None:
            raw += inputs.interaction_signal
        perceived_trust = max(TRUST_CLAMP_MIN, min(TRUST_CLAMP_MAX, raw))
        perceived_intent = self._classify_intent(perceived_trust)
        return PlayerModelUpdate(
            npc_id=inputs.npc_id,
            player_id=inputs.player_id,
            perceived_trust=perceived_trust,
            perceived_intent=perceived_intent,
        )

    def _classify_intent(self, trust: int) -> str:
        if trust < HOSTILE_TRUST_THRESHOLD:
            return INTENT_HOSTILE
        if trust >= FRIENDLY_TRUST_THRESHOLD:
            return INTENT_FRIENDLY
        return INTENT_NEUTRAL
