"""
generic_graph_service.py - Combined registry-driven graph CRUD service.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: enforce auth scopes or define node/edge logic directly.

Dependencies injected: AsyncSession, TypeRegistry.
"""
from __future__ import annotations

from npc_engine.graph.generic_node_service import GenericNodeService
from npc_engine.graph.generic_edge_service import GenericEdgeService

__all__ = ["GenericGraphService"]


class GenericGraphService(GenericNodeService, GenericEdgeService):
    """Combined registry-backed node and edge CRUD service.

    Inherits from GenericNodeService and GenericEdgeService.
    Constructor signature: (session: AsyncSession, registry: TypeRegistry).
    """
