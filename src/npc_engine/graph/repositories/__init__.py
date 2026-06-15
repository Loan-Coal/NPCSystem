"""
Package: repositories
Layer: graph
Purpose: Neo4j-backed repository adapters that implement the engine-layer graph
         Ports (structural Protocols). Each adapter holds a GraphDB driver holder
         and opens a session per operation, so engines depend on an abstraction and
         never hold a Neo4j session — the swap seam for cache/alternate-DB/microservice
         backends (DEC-122 / SEV-24).
Does NOT: contain business/decay logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (per adapter, at the api composition root).
Public surface: Neo4jNeedRepository.
"""

from __future__ import annotations

from npc_engine.graph.repositories.need_repository import Neo4jNeedRepository

__all__ = ["Neo4jNeedRepository"]
