"""
Module: deception_engine
Layer: engines
Purpose: Plant a deliberate false belief on an NPC — records a BELIEVES edge with
         is_deception=True and deception_goal_id for intrigue and social-drama scenarios (EXP-228).
Does NOT: call LLMs, validate world-state consistency, or open Neo4j sessions — the belief
          write is delegated to the injected KnowledgeGraphPort (reuses its write_belief).
Dependencies: engines.ports.knowledge_port, pydantic.BaseModel
Dependencies injected: KnowledgeGraphPort (via constructor); no per-call session.
Used by: (future) engines.dialogue.dialogue_handler, engines.quest, scenario scripts
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from npc_engine.engines.ports.knowledge_port import KnowledgeGraphPort

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
    that motivates the deception.  The engine delegates the write to the injected
    KnowledgeGraphPort.write_belief with is_deception=True and the given
    deception_goal_id, then returns a typed DeceptionBelief result.

    Injected dependencies: KnowledgeGraphPort (all I/O is delegated to it; the engine
    holds no Neo4j session — DEC-122 / SEV-24).
    """

    def __init__(self, *, knowledge_repo: KnowledgeGraphPort) -> None:
        """Store the injected belief-domain repository port.

        Args:
            knowledge_repo: Port whose write_belief persists the false belief.
        """
        self._repo = knowledge_repo

    async def plant_belief(
        self,
        *,
        npc_id: str,
        target_belief_content: str,
        deception_goal_id: str,
        confidence: int = _DEFAULT_DECEPTION_CONFIDENCE,
        source_character_id: str,
        learned_at_tick: int,
        game_time_str: str,
    ) -> DeceptionBelief:
        """Persist a deliberately false belief (BELIEVES edge with is_deception=True +
        deception_goal_id) on the target NPC and return the DeceptionBelief. Existing
        write_belief callers are unaffected (back-compat defaults on the writer).
        """
        belief_id = await self._repo.write_belief(
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
