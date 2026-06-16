"""
Module: reputation_port
Layer: engines
Purpose: Structural Protocol for the reputation-write graph domain (the bounded
         trust/affection nudge applied to an existing RELATES_TO edge), so the
         reputation engine depends on one abstraction and holds no Neo4j session
         (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, derive standing, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/reputation/reputation_engine; implemented structurally by
         npc_engine.graph.repositories.reputation_repository.Neo4jReputationRepository.
"""

from __future__ import annotations

from typing import Protocol


class ReputationGraphPort(Protocol):
    """Write access for the 1-hop reputation nudge (bounded delta on an existing edge)."""

    async def apply_trust_nudge(
        self,
        *,
        src_id: str,
        dst_id: str,
        delta_trust: int,
        delta_affection: int,
    ) -> None:
        """Apply bounded trust/affection deltas to an existing RELATES_TO edge (no-op if absent)."""
        ...
