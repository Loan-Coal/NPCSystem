"""
Module: memory_consolidation_engine
Layer: engines
Purpose: Consolidates recent session turns into a Memory node via a single LLM summarisation call.
Does NOT: query Neo4j directly — delegates to the injected MemoryConsolidationGraphPort.
Dependencies: engines.llm.protocols, engines.dialogue.session_store, engines.ports.memory_consolidation_port,
              config, world.time_utils, common.yaml_utils
Dependencies injected: SessionStore, LLMGenerateProtocol, MemoryConsolidationGraphPort, Settings.
Used by: scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.config import Settings
from npc_engine.engines.llm.protocols import LLMGenerateProtocol
from npc_engine.world.time_utils import TimePoint

if TYPE_CHECKING:
    from npc_engine.engines.dialogue.session_store import SessionStore
    from npc_engine.engines.ports.memory_consolidation_port import MemoryConsolidationGraphPort

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

    run_tick parallelises consolidation across NPCs using asyncio.gather bounded
    by asyncio.Semaphore(settings.MAX_CONCURRENT_TICKS). Each parallel task drives
    the injected MemoryConsolidationGraphPort, which opens its own Neo4j session per
    operation (DEC-122 / SEV-24), so the engine holds no session.
    """

    def __init__(
        self,
        session_store: SessionStore,
        llm_client: LLMGenerateProtocol,
        memory_repo: MemoryConsolidationGraphPort,
        settings: Settings,
        turn_threshold: int,
        clear_turns_after: bool = False,
        max_tokens: int = 300,
        temperature: float = 0.4,
    ) -> None:
        """Initialise the memory consolidation engine.

        Args:
            session_store: SessionStore to read dialogue turns from.
            llm_client: LLM adapter for generating the summary paragraph.
            memory_repo: Graph port for belief/memory/witness reads + the Memory write.
            settings: Application settings (supplies MAX_CONCURRENT_TICKS).
            turn_threshold: Minimum turn count before consolidation triggers.
            clear_turns_after: When True, clears consolidated turns from the store.
            max_tokens: Maximum tokens to generate in the summarisation call.
            temperature: Sampling temperature for the summarisation call.
        """
        self._session_store = session_store
        self._llm_client = llm_client
        self._memory_repo = memory_repo
        self._settings = settings
        self._turn_threshold = turn_threshold
        self._clear_turns = clear_turns_after
        self._max_tokens = max_tokens
        self._temperature = temperature
        prompt_data = load_yaml_mapping(_PROMPT_PATH, "consolidation_v1.yaml must have a mapping root")
        self._system_prompt: str = prompt_data["system"]
        self._user_template: str = prompt_data["user_template"]

    async def consolidate(
        self,
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
            npc_id: ID of the NPC whose turns to consolidate.
            game_time: Game-time snapshot at moment of consolidation.

        Returns:
            Memory ID string if consolidation occurred, else None.
        """
        turns = await self._session_store.get_all_turns_for_npc(npc_id)
        if len(turns) < self._turn_threshold:
            return None

        # Fetch existing beliefs and recent memories so the LLM avoids redundancy.
        existing_beliefs = await self._memory_repo.get_beliefs(character_id=npc_id, k=5)
        recent_memories = await self._memory_repo.get_recent_memories(character_id=npc_id, k=3)
        beliefs_text = json.dumps([b.get("content", "") for b in (existing_beliefs or [])])
        memories_text = json.dumps([m.get("content", "") for m in (recent_memories or [])])

        # L1-05: collapse newlines within each turn so a stored player message
        # cannot inject a forged prompt line (e.g. a fake EXISTING_BELIEFS field).
        turns_text = "\n".join(f"- {t.replace(chr(13), ' ').replace(chr(10), ' ')}" for t in turns)
        user_message = self._user_template.format(
            npc_id=npc_id,
            turns_text=turns_text,
            existing_beliefs=beliefs_text,
            recent_memories=memories_text,
        )

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
            witnessed = await self._memory_repo.get_undisclosed_witnesses(npc_id=npc_id)
            if witnessed:
                max_clarity = max(int(w.get("clarity", 0)) for w in witnessed)
                vividness = max(vividness, max_clarity)
                if any(bool(w.get("is_canonical", False)) for w in witnessed):
                    vividness = 100
        except Exception as exc:
            _LOGGER.warning(
                "witnessed_query_failed",
                extra={"npc_id": npc_id, "error": str(exc)},
            )

        memory_id = await self._memory_repo.create_memory(
            character_id=npc_id,
            content=summary.strip(),
            vividness=vividness,
            emotional_charge=_EMOTIONAL_CHARGE,
            game_time=game_time,
        )

        if self._clear_turns:
            await self._session_store.clear_all_turns_for_npc(npc_id)

        return memory_id

    async def _consolidate_bounded(
        self,
        sem: asyncio.Semaphore,
        npc_id: str,
        game_time: TimePoint,
    ) -> str | None:
        """Acquire the semaphore then consolidate one NPC via the graph port.

        The semaphore caps the number of simultaneously open LLM + graph
        connections; the port opens its own session per graph operation.

        Args:
            sem: Shared semaphore bounding concurrent tasks.
            npc_id: NPC to consolidate.
            game_time: Game-time snapshot passed through to consolidate().

        Returns:
            Memory ID if consolidation occurred, else None.
        """
        async with sem:
            return await self.consolidate(npc_id=npc_id, game_time=game_time)

    async def run_tick(
        self,
        *,
        game_time: TimePoint,
    ) -> dict[str, Any]:
        """Consolidate memories for all eligible NPCs in parallel.

        Called by the tick scheduler on its configured cadence. Fans out one
        coroutine per eligible NPC, bounded by
        asyncio.Semaphore(settings.MAX_CONCURRENT_TICKS). Each coroutine drives the
        injected MemoryConsolidationGraphPort, which manages its own session per
        operation (DEC-122 / SEV-24).

        Args:
            game_time: Current game-time snapshot.

        Returns:
            Dict with ``consolidated`` (list of npc_ids whose memory was created).
        """
        npc_ids = await self._session_store.get_active_npc_ids(self._turn_threshold)
        sem = asyncio.Semaphore(self._settings.MAX_CONCURRENT_TICKS)
        results = await asyncio.gather(
            *(self._consolidate_bounded(sem, n, game_time) for n in npc_ids)
        )
        consolidated = [n for n, mid in zip(npc_ids, results) if mid is not None]
        return {"consolidated": consolidated}
