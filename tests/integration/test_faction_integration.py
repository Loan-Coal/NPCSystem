"""
test_faction_integration.py - Integration tests for Faction graph operations.

Does NOT: validate HTTP route wiring or auth middleware.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.faction.faction_service import FactionService
from npc_engine.utils.errors import FactionMembershipError, FactionNotFoundError


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


class _MinimalFaction:
    """Minimal faction fixture compatible with FactionService.upsert_faction."""

    def __init__(self, faction_id: str, name: str) -> None:
        self.id = faction_id
        self.name = name
        self.description = None
        self.archetype = "military"
        self.is_active = True
        self.created_at = "2026-01-01T00:00:00+00:00"
        self.last_graph_updated_at = "2026-01-01T00:00:00+00:00"

    def model_dump(self, *, mode: str = "python") -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "archetype": self.archetype,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_graph_updated_at": self.last_graph_updated_at,
        }


# ---------------------------------------------------------------------------
# Helpers that create prerequisite nodes using raw Cypher
# ---------------------------------------------------------------------------


async def _create_character(session, character_id: str) -> None:
    await session.run(
        "MERGE (c:Character {id: $id}) SET c.name = $name, c.is_active = true",
        id=character_id,
        name=f"test-char-{character_id}",
    )


async def _create_location(session, location_id: str) -> None:
    await session.run(
        "MERGE (l:Location {id: $id}) SET l.name = $name, l.location_tag = 'test', l.descriptor = 'test'",
        id=location_id,
        name=f"test-loc-{location_id}",
    )


async def _cleanup(session, *node_ids: str) -> None:
    for nid in node_ids:
        await session.run(
            "MATCH (n {id: $id}) DETACH DELETE n",
            id=nid,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_faction_and_read_back() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_id = _uid("faction")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_id, "Iron Hand"))

            result = await service.get_faction(faction_id)
            assert result is not None
            assert result["name"] == "Iron Hand"
            assert result["archetype"] == "military"
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_id)
        await driver.close()


@pytest.mark.asyncio
async def test_add_member_list_members_remove_member() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_id = _uid("faction")
    char_id = _uid("char")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_id, "Shadow Guild"))
            await _create_character(session, char_id)

            await service.add_member(character_id=char_id, faction_id=faction_id, role="member", status="active")

            members = await service.get_members_of_faction(faction_id)
            assert len(members) == 1
            assert members[0]["character"]["id"] == char_id
            assert members[0]["membership"]["role"] == "member"

            await service.remove_member(character_id=char_id, faction_id=faction_id)

            members_after = await service.get_members_of_faction(faction_id)
            assert members_after == []
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_id, char_id)
        await driver.close()


@pytest.mark.asyncio
async def test_remove_member_raises_when_not_a_member() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_id = _uid("faction")
    char_id = _uid("char")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_id, "Storm Watch"))
            await _create_character(session, char_id)

            with pytest.raises(FactionMembershipError):
                await service.remove_member(character_id=char_id, faction_id=faction_id)
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_id, char_id)
        await driver.close()


@pytest.mark.asyncio
async def test_set_standing_independent_directions() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_a = _uid("faction")
    faction_b = _uid("faction")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_a, "Faction A"))
            await service.upsert_faction(_MinimalFaction(faction_b, "Faction B"))

            await service.set_standing(src_id=faction_a, dst_id=faction_b, standing=75)
            await service.set_standing(src_id=faction_b, dst_id=faction_a, standing=-50)

            a_to_b = await service.get_standing(faction_a, faction_b)
            b_to_a = await service.get_standing(faction_b, faction_a)

            assert a_to_b == 75
            assert b_to_a == -50
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_a, faction_b)
        await driver.close()


@pytest.mark.asyncio
async def test_set_and_remove_controls() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_id = _uid("faction")
    loc_id = _uid("loc")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_id, "City Guard"))
            await _create_location(session, loc_id)

            await service.set_controls(faction_id=faction_id, location_id=loc_id)

            controlled = await service.get_controlled_locations(faction_id)
            assert len(controlled) == 1
            assert controlled[0]["id"] == loc_id

            await service.remove_controls(faction_id=faction_id, location_id=loc_id)

            controlled_after = await service.get_controlled_locations(faction_id)
            assert controlled_after == []
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_id, loc_id)
        await driver.close()


@pytest.mark.asyncio
async def test_remove_controls_raises_when_no_edge() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    faction_id = _uid("faction")
    loc_id = _uid("loc")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(faction_id, "No Territory"))
            await _create_location(session, loc_id)

            with pytest.raises(FactionNotFoundError):
                await service.remove_controls(faction_id=faction_id, location_id=loc_id)
    finally:
        async with driver.session() as session:
            await _cleanup(session, faction_id, loc_id)
        await driver.close()


@pytest.mark.asyncio
async def test_list_factions_and_filter_by_active() -> None:
    uri, user, password = _skip_if_no_neo4j()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    active_id = _uid("faction")
    inactive_id = _uid("faction")
    try:
        async with driver.session() as session:
            service = FactionService(session=session)
            await service.upsert_faction(_MinimalFaction(active_id, "Active Faction"))
            inactive = _MinimalFaction(inactive_id, "Inactive Faction")
            inactive.is_active = False  # type: ignore[attr-defined]
            await service.upsert_faction(inactive)

            all_factions = await service.list_factions()
            ids = {f["id"] for f in all_factions}
            assert active_id in ids
            assert inactive_id in ids

            active_only = await service.list_factions(is_active=True)
            active_ids = {f["id"] for f in active_only}
            assert active_id in active_ids
            assert inactive_id not in active_ids
    finally:
        async with driver.session() as session:
            await _cleanup(session, active_id, inactive_id)
        await driver.close()
