"""
Module: memory_consolidation_engine
Layer: engines
Purpose: Consolidates recent session turns into a Memory node via a single LLM summarisation call.
Does NOT: query Neo4j directly — delegates to graph.memory_service.create_memory.
Dependencies: engines.llm.protocols, engines.dialogue.session_store, graph.memory_service,
              world.time_utils, common.yaml_utils
Dependencies injected: SessionStore, LLMClientProtocol, AsyncSession (per call).
Used by: scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.graph.memory_service import create_memory
from npc_engine.graph.witnessed_queries import get_undisclosed_witnesses
from npc_engine.world.time_utils import TimePoint

if TYPE_CHECKING:
    from npc_engine.engines.dialogue.session_store import SessionStore

_LOGGER = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "memory_consolidation"
    / "consolidation_v1.yaml"
)

_VIVIDNESS = 75
_EMOTIONAL_CHARGE = 0


class MemoryConsolidationEngine:
    """Consolidates NPC session turn histories into long-term Memory nodes.

    For each NPC with enough recent dialogue turns, calls the LLM with a
    summarisation prompt and persists the result as a Memory node in Neo4j.
    LLM errors are caught and logged; the engine skips the NPC gracefully.
    """

    def __init__(
        self,
        session_store: SessionStore,
        llm_client: LLMClientProtocol,
        turn_threshold: int,
        clear_turns_after: bool = False,
        max_tokens: int = 300,
        temperature: float = 0.4,
    ) -> None:
        """Initialise the memory consolidation engine.

        Args:
            session_store: SessionStore to read dialogue turns from.
            llm_client: LLM adapter for generating the summary paragraph.
            turn_threshold: Minimum turn count before consolidation triggers.
            clear_turns_after: When True, clears consolidated turns from the store.
            max_tokens: Maximum tokens to generate in the summarisation call.
            temperature: Sampling temperature for the summarisation call.
        """
        self._session_store = session_store
        self._llm_client = llm_client
        self._turn_threshold = turn_threshold
        self._clear_turns = clear_turns_after
        self._max_tokens = max_tokens
        self._temperature = temperature
        prompt_data = load_yaml_mapping(_PROMPT_PATH, "consolidation_v1.yaml must have a mapping root")
        self._system_prompt: str = prompt_data["system"]
        self._user_template: str = prompt_data["user_template"]

    async def consolidate(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        game_time: TimePoint,
    ) -> str | None:
        """Consolidate all session turns for an NPC into a Memory node.

        Fetches turns from the SessionStore across all player sessions for this
        NPC. Returns None without calling the LLM if the turn count is below
        the configured threshold. LLM errors are caught and logged; the method
        returns None on failure so the caller can continue safely.

        Args:
            session: Active Neo4j async session.
            npc_id: ID of the NPC whose turns to consolidate.
            game_time: Game-time snapshot at moment of consolidation.

        Returns:
            Memory ID string if consolidation occurred, else None.
        """
        turns = self._session_store.get_all_turns_for_npc(npc_id)
        if len(turns) < self._turn_threshold:
            return None

        turns_text = "\n".join(f"- {t}" for t in turns)
        user_message = self._user_template.format(npc_id=npc_id, turns_text=turns_text)

        try:
            summary = await self._llm_client.generate(
                prompt=user_message,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=self._system_prompt,
            )
        except Exception:
            _LOGGER.exception("LLM error during consolidation for NPC %s — skipping", npc_id)
            return None

        # Boost vividness when the NPC has undisclosed WITNESSED observations,
        # since high-clarity first-hand observations form more vivid memories.
        # Canonical events (IS_CANONICAL=true) always produce maximum-vividness memories
        # to prevent them from being summarized or decayed by future consolidation passes.
        vividness = _VIVIDNESS
        try:
            witnessed = await get_undisclosed_witnesses(session, npc_id=npc_id)
            if witnessed:
                max_clarity = max(int(w.get("clarity", 0)) for w in witnessed)
                vividness = max(vividness, max_clarity)
                if any(bool(w.get("is_canonical", False)) for w in witnessed):
                    vividness = 100
        except Exception:
            pass  # Never let WITNESSED query failure block memory creation

        memory_id = await create_memory(
            session,
            character_id=npc_id,
            content=summary.strip(),
            vividness=vividness,
            emotional_charge=_EMOTIONAL_CHARGE,
            game_time=game_time,
        )

        if self._clear_turns:
            self._session_store.clear_all_turns_for_npc(npc_id)

        return memory_id

    async def run_tick(
        self,
        session: AsyncSession,
        *,
        game_time: TimePoint,
    ) -> dict:
        """Consolidate memories for all NPCs with enough session turns.

        Called by the tick scheduler on its configured cadence. Iterates all
        NPCs whose turn count meets the threshold and calls consolidate for each.

        Args:
            session: Active Neo4j async session.
            game_time: Current game-time snapshot.

        Returns:
            Dict with ``consolidated`` (list of npc_ids whose memory was created).
        """
        npc_ids = self._session_store.get_active_npc_ids(self._turn_threshold)
        consolidated: list[str] = []
        for npc_id in npc_ids:
            memory_id = await self.consolidate(session, npc_id=npc_id, game_time=game_time)
            if memory_id is not None:
                consolidated.append(npc_id)
        return {"consolidated": consolidated}
