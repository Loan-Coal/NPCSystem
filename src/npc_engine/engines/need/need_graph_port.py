"""
Module: need_graph_port
Layer: engines
Purpose: Structural Protocol describing the graph operations NeedDecayEngine requires,
         so the engine depends on an abstraction (DIP) instead of importing concrete
         graph functions or holding a Neo4j session. The Neo4j implementation lives in
         graph/repositories/need_repository.py and is injected at the api composition
         root; a cache, alternate DB, or HTTP/microservice adapter can be substituted
         behind the same Protocol without touching the engine.
Does NOT: open sessions, run Cypher, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.need.need_decay_engine; implemented structurally by
         npc_engine.graph.repositories.need_repository.Neo4jNeedRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class NeedGraphPort(Protocol):
    """Graph operations required by NeedDecayEngine: read needs, write levels.

    The rows are returned as plain dicts (matching the underlying graph reader);
    converting them to a Pydantic row model is deferred to the strict-typing pass
    (SEV-15) so this seam stays behavior-preserving.
    """

    async def get_all_needs_with_location(self) -> list[dict[str, Any]]:
        """Return all Need rows joined with location + satisfier magnitude."""
        ...

    async def set_need_level(self, *, need_id: str, level: int) -> None:
        """Persist a Need node's new level (clamped to [0, 100] by the writer)."""
        ...
