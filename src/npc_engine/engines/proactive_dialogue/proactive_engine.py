"""
Module: proactive_engine
Layer: engines
Purpose: Detects high-vividness unshared NPC memories co-located with an idle player
         and generates one in-character proactive dialogue line via the LLM.
Does NOT: wire into the tick scheduler, send WS messages, persist state, or hold a
         Neo4j session. Graph reads go through injected ports (DEC-122 / SEV-24).
Dependencies: engines.llm.protocols, engines.proactive_dialogue.models,
              engines.ports.proactive_memory_read_port, engines.ports.player_location_read_port,
              common.yaml_utils
Dependencies injected: LLMGenerateProtocol, ProactiveMemoryReadPort, PlayerLocationReadPort.
Used by: scheduler.tick_scheduler (via proactive_tick_adapter)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.llm.protocols import LLMGenerateProtocol
from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger

if TYPE_CHECKING:
    from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
    from npc_engine.engines.ports.proactive_memory_read_port import ProactiveMemoryReadPort

_logger = logging.getLogger(__name__)

# Vividness value at or above which a memory qualifies as a trigger candidate.
HIGH_VIVIDNESS_THRESHOLD: int = 70
# Minimum ticks a player must have been idle at the NPC's location to trigger.
MIN_IDLE_TICKS: int = 2
# Maximum memories fetched per trigger check (caps graph read cost).
_MAX_MEMORIES_PER_CHECK: int = 10
# LLM generation defaults.
_MAX_TOKENS: int = 128
_TEMPERATURE: float = 0.8

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "proactive"
_TRIGGER_PROMPT_PATH = _PROMPTS_DIR / "trigger_v1.yaml"


def _load_prompt(path: Path) -> dict[str, str]:
    """Load a prompt YAML file from disk.

    Args:
        path: Filesystem path to the YAML prompt file.

    Returns:
        Dict with at least ``system`` and ``user_template`` keys.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        ValueError: If the YAML root is not a mapping.
    """
    return load_yaml_mapping(path, f"prompt file {path.name} must be a YAML mapping")


def _select_best_memory(memories: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-vividness qualifying memory, or None if none qualify.

    Qualifying condition: vividness >= HIGH_VIVIDNESS_THRESHOLD and not shared.

    Args:
        memories: Memory dicts from the memory service.

    Returns:
        Memory dict with the highest vividness, or None.
    """
    candidates = [
        m for m in memories
        if int(m.get("vividness", 0)) >= HIGH_VIVIDNESS_THRESHOLD
        and not m.get("shared", False)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda m: int(m.get("vividness", 0)))


class ProactiveDialogueEngine:
    """Detects triggers and generates one proactive NPC dialogue line.

    On each call to ``check_trigger`` the engine reads the NPC's unshared
    memories, checks whether the player is co-located and idle, and returns
    a ``ProactiveTrigger`` if conditions are met. ``generate_line`` takes
    that trigger and produces one in-character ``ProactiveLine`` via the LLM.

    No state is held beyond injected dependencies — safe for concurrent use.
    """

    def __init__(
        self,
        llm_client: LLMGenerateProtocol,
        memory_service: ProactiveMemoryReadPort,
        location_service: PlayerLocationReadPort,
        prompts_dir: Path = _PROMPTS_DIR,
    ) -> None:
        """Initialise the engine with injected dependencies.

        Args:
            llm_client: LLM adapter implementing LLMGenerateProtocol.
            memory_service: ProactiveMemoryReadPort returning unshared memories (sessionless).
            location_service: PlayerLocationReadPort returning player idle-tick counts.
            prompts_dir: Override path to the proactive prompt directory
                (defaults to src/npc_engine/prompts/proactive/).
        """
        self._llm = llm_client
        self._memory_service = memory_service
        self._location_service = location_service
        self._prompt = _load_prompt(prompts_dir / "trigger_v1.yaml")

    async def check_trigger(
        self,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> ProactiveTrigger | None:
        """Check whether the NPC should proactively address the player this tick.

        Reads unshared memories from the memory port, picks the highest-vividness
        qualifying memory, then checks player idle ticks via the location port.
        Returns a ``ProactiveTrigger`` only when BOTH conditions are satisfied.

        Args:
            npc_id: ID of the NPC being evaluated.
            player_id: ID of the potentially co-located player.
            tick_id: Current game tick.

        Returns:
            ProactiveTrigger if conditions met, else None.
        """
        memories = await self._memory_service.get_unshared_memories(
            npc_id=npc_id, k=_MAX_MEMORIES_PER_CHECK
        )
        best = _select_best_memory(memories)
        if best is None:
            return None

        idle_ticks = await self._location_service.get_player_idle_ticks(
            npc_id=npc_id, player_id=player_id, tick_id=tick_id
        )
        if idle_ticks < MIN_IDLE_TICKS:
            _logger.debug(
                "proactive_trigger skipped",
                extra={"npc_id": npc_id, "player_id": player_id, "idle_ticks": idle_ticks},
            )
            return None

        _logger.info(
            "proactive_trigger fired",
            extra={
                "npc_id": npc_id,
                "player_id": player_id,
                "tick_id": tick_id,
                "memory_id": best.get("memory_id"),
                "vividness": best.get("vividness"),
            },
        )
        return ProactiveTrigger(
            npc_id=npc_id,
            player_id=player_id,
            tick_id=tick_id,
            reason="unshared_memory",
            memory_id=str(best.get("memory_id", "")),
            memory_content=str(best.get("content", "")),
            memory_vividness=int(best.get("vividness", 0)),
        )

    async def generate_line(
        self,
        trigger: ProactiveTrigger,
    ) -> ProactiveLine:
        """Generate one in-character proactive line from the trigger.

        Builds the user prompt from trigger_v1.yaml, calls the LLM once via
        ``llm_client.generate()``, and returns a ``ProactiveLine``.

        Args:
            trigger: Trigger produced by check_trigger.

        Returns:
            ProactiveLine with npc_id, content, reason, and tick populated.

        Raises:
            LLMTimeoutError: If the LLM backend times out.
            LLMRequestError: If the LLM backend returns an error.
        """
        user_prompt = self._prompt["user_template"].format(
            npc_id=trigger.npc_id,
            player_id=trigger.player_id,
            memory_content=trigger.memory_content,
        )
        system = self._prompt.get("system", "")
        _logger.info(
            "proactive_generate_line",
            extra={
                "npc_id": trigger.npc_id,
                "player_id": trigger.player_id,
                "tick": trigger.tick_id,
                "memory_id": trigger.memory_id,
            },
        )
        raw_line = await self._llm.generate(
            prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            temperature=_TEMPERATURE,
            system=system,
        )
        return ProactiveLine(
            npc_id=trigger.npc_id,
            content=raw_line.strip(),
            reason=trigger.reason,
            tick=trigger.tick_id,
        )
