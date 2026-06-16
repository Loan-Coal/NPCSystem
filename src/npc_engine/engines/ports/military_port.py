"""
Module: military_port
Layer: engines
Purpose: Structural Protocol for the military graph domain — the army-conflict and
         resource-yield reads/writes the MilitaryEngine's battle and resource
         services need (armies in conflict, armies at a location, faction resource
         nodes, plus army-strength / control-edge / treasury / depletion writes and
         battle-event emission), so the services depend on an abstraction instead of
         importing graph query/writer functions and holding a Neo4j session.
         Implemented in graph/repositories/military_repository.py.
Does NOT: open sessions, run Cypher, resolve battles, call LLMs, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.military.military_battle_service,
         npc_engine.engines.military.military_resource_service,
         npc_engine.engines.military.military_engine; implemented structurally by
         npc_engine.graph.repositories.military_repository.Neo4jMilitaryRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class MilitaryGraphPort(Protocol):
    """Military-domain graph reads/writes required by the military services."""

    async def get_armies_in_conflict(self) -> list[dict[str, Any]]:
        """Return locations occupied by armies from at least two factions."""
        ...

    async def get_army_at_location(self, *, location_id: str) -> list[dict[str, Any]]:
        """Return all armies occupying a location (army_id, faction_id, strength)."""
        ...

    async def get_faction_resource_nodes(self) -> list[dict[str, Any]]:
        """Return (faction, resource_node) pairs for non-depleted controlled resources."""
        ...

    async def set_army_strength(self, *, army_id: str, strength: int) -> None:
        """Update the strength of an army."""
        ...

    async def set_controls_location(
        self,
        *,
        faction_id: str,
        location_id: str,
        control_strength: int,
        contested_by: str | None = None,
    ) -> None:
        """Upsert a CONTROLS edge from a faction to a location."""
        ...

    async def remove_controls_location(self, *, faction_id: str, location_id: str) -> None:
        """Delete a CONTROLS edge from a faction to a location."""
        ...

    async def emit_battle_event(
        self,
        *,
        event_id: str,
        summary: str,
        severity: int,
        location_id: str,
        occurred_at: str,
        tick_id: int,
        winner_faction_id: str,
    ) -> None:
        """Write a public battle Event node to the graph."""
        ...

    async def add_faction_treasury(self, *, faction_id: str, amount: int) -> None:
        """Add (or subtract, if negative) amount to a faction's treasury."""
        ...

    async def set_resource_depletion(self, *, resource_node_id: str, depletion: int) -> None:
        """Set the depletion level of a ResourceNode."""
        ...
