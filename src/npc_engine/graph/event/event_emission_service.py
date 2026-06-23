"""
Module: event_emission_service
Layer: graph
Purpose: Atomic event-emission unit-of-work. Inside ONE run_in_tx transaction it upserts
         the Event node, seeds NPC awareness, applies faction reputation deltas + routine
         overrides for characters at the location, and conditionally records a high-severity
         world condition — so the EventGraphPort can expose the whole write as a single
         atomic call and no transaction leaks to the engine (DEC-122 / SEV-24).
Does NOT: select templates, match disruption rules, call LLMs, or import the engines layer.
Dependencies injected: AsyncSession (per call); RoutineOverridePlan data from the caller.
Used by: npc_engine.graph.repositories.event_repository.Neo4jEventRepository.
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel, ConfigDict

from npc_engine.graph.event.event_queries import get_characters_at_location, seed_awareness_tx
from npc_engine.graph.event.event_writer import _EventNode, upsert_event
from npc_engine.graph.reputation.reputation_writer import adjust_reputation_for_event
from npc_engine.graph.scheduling.routine_queries import set_routine_override
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.graph.world_state.world_state_writer import upsert_world_state_tx
from npc_engine.utils.errors import ReputationNotFoundError

LOGGER = logging.getLogger(__name__)


class RoutineOverridePlan(BaseModel):
    """One disruption-driven routine override applied to characters at the event location."""

    override_location: str
    expires_at_tick: int

    model_config = ConfigDict(frozen=True)


async def emit_event_atomic(
    session: AsyncSession,
    *,
    event: _EventNode,
    event_id: str,
    location_id: str,
    tick_id: int,
    faction_id: str | None,
    reputation_delta: int | None,
    routine_overrides: list[RoutineOverridePlan],
    world_condition_event_type: str | None,
    world_id: str,
) -> None:
    """Persist one event and its side effects in a single atomic transaction.

    Args:
        session: Active Neo4j async session used to open the transaction.
        event: Validated Event node model written via upsert_event.
        event_id: Event node id (used for awareness seeding).
        location_id: Location the event occurs at; scopes awareness/reputation/overrides.
        tick_id: Current game tick recorded on awareness/override writes.
        faction_id: Faction whose reputation shifts, or None to skip reputation.
        reputation_delta: Reputation change applied per character, or None to skip.
        routine_overrides: Disruption overrides to apply to characters at the location.
        world_condition_event_type: Event type to add to world active_conditions, or None.
        world_id: World node id for the conditional world-state update.
    """

    async def _work(tx: AsyncTransaction) -> None:
        await upsert_event(tx, event)
        await seed_awareness_tx(tx, event_id=event_id, location_id=location_id, tick_id=tick_id)
        await _apply_reputation(
            tx, location_id=location_id, faction_id=faction_id, delta=reputation_delta
        )
        await _apply_routine_overrides(tx, location_id=location_id, overrides=routine_overrides)
        await _apply_world_condition(tx, world_id=world_id, event_type=world_condition_event_type)

    await run_in_tx(session, _work)


async def _apply_reputation(
    tx: AsyncTransaction, *, location_id: str, faction_id: str | None, delta: int | None
) -> None:
    """Apply a reputation delta to every character at the location (no-op when unset)."""
    if faction_id is None or delta is None:
        return
    for char_id in await get_characters_at_location(tx, location_id=location_id):  # type: ignore[arg-type]
        try:
            await adjust_reputation_for_event(
                tx, character_id=char_id, faction_id=faction_id, delta=delta
            )
        except ReputationNotFoundError:
            LOGGER.debug(
                "emit_event_atomic: no reputation edge for char=%s faction=%s — skipped",
                char_id,
                faction_id,
            )


async def _apply_routine_overrides(
    tx: AsyncTransaction, *, location_id: str, overrides: list[RoutineOverridePlan]
) -> None:
    """Write each disruption override onto every character at the location."""
    if not overrides:
        return
    char_ids = await get_characters_at_location(tx, location_id=location_id)  # type: ignore[arg-type]
    for override in overrides:
        for char_id in char_ids:
            await set_routine_override(
                tx,  # type: ignore[arg-type]
                char_id,
                override.override_location,
                override.expires_at_tick,
            )


async def _apply_world_condition(
    tx: AsyncTransaction, *, world_id: str, event_type: str | None
) -> None:
    """Add a high-severity event type to the world active_conditions list, idempotently."""
    if event_type is None:
        return
    world_state = await get_world_state(tx, world_id=world_id)
    if event_type not in world_state.active_conditions:
        updated = world_state.model_copy(
            update={"active_conditions": [*world_state.active_conditions, event_type]}
        )
        await upsert_world_state_tx(tx=tx, world_state=updated)
