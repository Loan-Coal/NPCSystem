"""
generic_graph_service.py - Combined registry-driven graph CRUD service.

Does NOT: enforce auth scopes or define node/edge logic directly.

Dependencies injected: AsyncSession, TypeRegistry.
"""

from graph.generic_node_service import GenericNodeService
from graph.generic_edge_service import GenericEdgeService

__all__ = ["GenericGraphService"]


class GenericGraphService(GenericNodeService, GenericEdgeService):
    """Combined registry-backed node and edge CRUD service.

    Inherits from GenericNodeService and GenericEdgeService.
    Constructor signature: (session: AsyncSession, registry: TypeRegistry).
    """
