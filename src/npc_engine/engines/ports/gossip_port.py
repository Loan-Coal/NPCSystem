"""
Module: gossip_port
Layer: engines
Purpose: Structural Protocol for the gossip graph domain — pair selection, batch
         event/trust reads, knowledge propagation, rumor creation, secret sharing,
         and relation-log updates. GossipHandler and pair_selector depend on this
         Protocol instead of importing graph queries or holding a Neo4j session
         (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, apply distortion logic, or call LLMs.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.gossip.gossip_handler.GossipHandler;
         npc_engine.engines.gossip.pair_selector.select_pairs;
         implemented structurally by
         npc_engine.graph.repositories.gossip_repository.Neo4jGossipRepository.
"""

from __future__ import annotations

from typing import Protocol, Any


class GossipGraphPort(Protocol):
    """Reads and writes for the gossip domain — pair selection through secret propagation."""

    async def fetch_gossip_pairs(self) -> list[dict[str, Any]]:
        """Return all co-located active NPC pairs eligible for gossip exchange."""
        ...

    async def get_goals_for_character(
        self, character_id: str, *, k: int, status_filter: str
    ) -> list[dict[str, Any]]:
        """Return up to k goals for the character filtered by status."""
        ...

    async def fetch_known_node_ids(self, character_id: str) -> set[str]:
        """Return the set of node IDs the character knows about via KNOWS_ABOUT."""
        ...

    async def select_batch_event_trust(
        self, pairs: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """Fetch event and trust data for all sharer/receiver pairs in one query."""
        ...

    async def write_batch_knowledge_propagation(self, writes: list[dict[str, Any]]) -> None:
        """Merge KNOWS_ABOUT edges for all receiver/event pairs in one query."""
        ...

    async def create_rumor(
        self,
        *,
        content: str,
        origin_event_id: str | None,
        created_at_tick: int,
        severity: int,
        is_fabricated: bool,
    ) -> str:
        """Merge a root Rumor node and return its ID."""
        ...

    async def believe_rumor(
        self,
        *,
        character_id: str,
        rumor_id: str,
        confidence: int,
        tick: int,
        from_character_id: str | None,
    ) -> None:
        """Create or update a BELIEVES_RUMOR edge from character to rumor."""
        ...

    async def select_gossip_secret(self, sharer_id: str) -> dict[str, Any] | None:
        """Return the most severe secret the sharer holds, or None."""
        ...

    async def log_gossip(
        self, *, src_id: str, dst_id: str, tick_id: int, trust_delta: int
    ) -> None:
        """Append a gossip interaction entry to the RELATES_TO delta log (CAS retry)."""
        ...

    async def propagate_secret(
        self,
        *,
        receiver_id: str,
        secret_id: str,
        source_character_id: str,
        tick_id: int,
        distorted: bool,
    ) -> None:
        """Merge a KNOWS_SECRET edge from the receiver to the secret."""
        ...
