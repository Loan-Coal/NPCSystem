"""
Module: proactive_memory_read_port
Layer: engines
Purpose: Structural Protocol for the proactive-dialogue memory read (unshared, vividness-
         ordered NPC memories) so ProactiveDialogueEngine depends on one abstraction and
         holds no Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, score triggers, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: engines/proactive_dialogue/proactive_engine; implemented structurally by
         npc_engine.graph.repositories.proactive_memory_read_repository
         .Neo4jProactiveMemoryReadRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class ProactiveMemoryReadPort(Protocol):
    """Read-only access to an NPC's unshared memories for proactive triggering."""

    async def get_unshared_memories(
        self, *, npc_id: str, k: int = 10
    ) -> list[dict[str, Any]]:
        """Return up to k unshared memory dicts for npc_id, sorted by vividness desc."""
        ...
