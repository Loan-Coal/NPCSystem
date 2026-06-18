"""
generic_graph_base.py - Shared session/registry base for generic graph services.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: execute business logic or validate payloads.

Dependencies injected: AsyncSession, TypeRegistry.
"""
from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.type_registry.contracts import TypeRegistry


class _GenericGraphServiceBase:
    """Provides shared session and registry access for generic graph service classes."""

    def __init__(self, session: AsyncSession, registry: TypeRegistry) -> None:
        """Initialise base service with injected session and registry.

        Args:
            session: Active Neo4j async session used for all Cypher queries.
            registry: Compiled type registry providing node and edge type definitions.
        """
        self._session = session
        self._registry = registry

    async def _run(self, query: str, **params: Any) -> Any:
        return await self._session.run(cast(Any, query), **params)
