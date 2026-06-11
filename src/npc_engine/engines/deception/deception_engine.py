"""
Module: deception_engine
Layer: engines
Purpose: Plant a deliberate false belief on an NPC — records a BELIEVES edge with
         is_deception=True and deception_goal_id for intrigue and social-drama scenarios (EXP-228).
Does NOT: call LLMs, validate world-state consistency, or open Neo4j transactions directly.
          All Cypher is delegated to graph.knowledge_writer.write_belief.
Dependencies: graph.knowledge_writer.write_belief, pydantic.BaseModel, neo4j.AsyncSession
Dependencies injected: AsyncSession (per call); no stateful constructor deps.
Used by: (future) engines.dialogue.dialogue_handler, engines.quest, scenario scripts
"""

from __future__ import annotations

from neo4j import AsyncSession
from pydantic import BaseModel, Field

from npc_engine.graph.knowledge_writer import write_belief

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DECEPTION_CONFIDENCE: int = 75


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class DeceptionBelief(BaseModel):
    """Typed result returned by DeceptionEngine.plant_belief.

    Attributes:
        belief_id: Stable SHA-256-derived id of the persisted belief node.
        npc_id: ID of the NPC who now holds the false belief.
        content: Text of the false belief that was planted.
        confidence: Confidence level stored on the BELIEVES edge (0–100).
        is_deception: Always True for beliefs produced by this engine.
        deception_goal_id: Goal ID that motivated the deception.
    """

    belief_id: str
    npc_id: str
    content: str
    confidence: int = Field(ge=0, le=100)
    is_deception: bool
    deception_goal_id: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DeceptionEngine:
    """Engine that persists a deliberate false belief on an NPC.

    No LLM call is made — the caller supplies the belief content and the goal
    that motivates the deception.  The engine delegates the write to
    graph.knowledge_writer.write_belief with is_deception=True and the given
    deception_goal_id, then returns a typed DeceptionBelief result.

    Injected dependencies: none (stateless; all I/O is delegated via write_belief
    which receives the session per call).
    """

    async def plant_belief(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        target_belief_content: str,
        deception_goal_id: str,
        confidence: int = _DEFAULT_DECEPTION_CONFIDENCE,
        source_character_id: str,
        learned_at_tick: int,
        game_time_str: str,
    ) -> DeceptionBelief:
        """Persist a deliberately false belief on the target NPC.

        Writes a BELIEVES edge with is_deception=True and deception_goal_id set
        to the supplied goal identifier.  Existing callers of write_belief are
        unaffected (back-compat defaults on the writer).

        Args:
            session: Active Neo4j async session.
            npc_id: ID of the NPC who will hold the false belief.
            target_belief_content: Text of the false belief to plant.
            deception_goal_id: Identifier of the goal that motivates this deception.
            confidence: Confidence stored on the BELIEVES edge (default 75).
            source_character_id: ID of the character planting the belief (provenance).
            learned_at_tick: Game tick at which the belief was planted (provenance).
            game_time_str: Human-readable game-time string for the belief node.

        Returns:
            DeceptionBelief with is_deception=True and the supplied deception_goal_id.
        """
        belief_id = await write_belief(
            session,
            npc_id=npc_id,
            content=target_belief_content,
            confidence=confidence,
            source_character_id=source_character_id,
            learned_at_tick=learned_at_tick,
            game_time_str=game_time_str,
            is_deception=True,
            deception_goal_id=deception_goal_id,
        )
        return DeceptionBelief(
            belief_id=belief_id,
            npc_id=npc_id,
            content=target_belief_content,
            confidence=confidence,
            is_deception=True,
            deception_goal_id=deception_goal_id,
        )
