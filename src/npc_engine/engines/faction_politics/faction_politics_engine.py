"""
Module: faction_politics_engine
Layer: engines
Purpose: Deterministic engine that adjusts faction standings based on recent events and applies
         slow decay toward neutral. Runs once per tick advance.
Does NOT: call LLMs, create new graph nodes or edges, or expose HTTP routes.
Dependencies injected: FactionPoliticsRules (via constructor), AsyncSession (per tick call).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.faction_politics.rules_loader import FactionPoliticsRules
from npc_engine.graph.faction_writer import set_standing

_LOGGER = logging.getLogger(__name__)

_DEFAULT_EVENT_LIMIT = 20

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_RECENT_EVENTS = """
MATCH (e:Event)
WHERE e.src_character_id IS NOT NULL
  AND e.event_type IS NOT NULL
RETURN e.event_type AS event_type, e.src_character_id AS src_character_id
ORDER BY e.tick_id DESC
LIMIT $limit
"""

CYPHER_GET_CHARACTER_FACTIONS = """
MATCH (c:Character {id: $character_id})-[:MEMBER_OF]->(f:Faction)
WHERE f.is_active = true
RETURN f.id AS faction_id
"""

CYPHER_GET_ALL_STANDINGS = """
MATCH (a:Faction)-[r:STANDS_WITH]->(b:Faction)
RETURN a.id AS src_id, b.id AS dst_id, r.standing AS standing
"""


class FactionPoliticsEngine:
    """Adjusts faction standings deterministically based on world events and time decay.

    On each tick:
    1. Reads recent events that have a src_character_id.
    2. For each event whose type matches a rule, looks up the source character's
       factions and adjusts standing toward any faction standing partners.
    3. Applies decay: all standings drift toward 0 by rate_per_tick if their
       magnitude exceeds min_magnitude.
    """

    def __init__(self, rules: FactionPoliticsRules) -> None:
        """Initialise the engine with a loaded rule set.

        Args:
            rules: Validated FactionPoliticsRules loaded from rules.yaml.
        """
        self._rules = rules
        self._lock = asyncio.Lock()
        self._rule_index: dict[str, int] = {r.event_type: r.standing_delta for r in rules.rules}

    async def run_tick(self, session: AsyncSession) -> dict[str, Any]:
        """Execute one faction politics tick: apply event rules then decay.

        Args:
            session: Active Neo4j async session.

        Returns:
            Dict with keys ``rule_applications`` (int) and ``decay_applications`` (int).
        """
        async with self._lock:
            rule_apps = await self._apply_rules(session)
            decay_apps = await self._apply_decay(session)
            _LOGGER.info(
                "faction_politics tick: %d rule applications, %d decay applications",
                rule_apps,
                decay_apps,
            )
            return {"rule_applications": rule_apps, "decay_applications": decay_apps}

    async def _apply_rules(self, session: AsyncSession) -> int:
        """Apply event-based standing rules.

        Args:
            session: Active Neo4j async session.

        Returns:
            Number of standing updates applied.
        """
        result = await session.run(CYPHER_GET_RECENT_EVENTS, limit=_DEFAULT_EVENT_LIMIT)
        events: list[dict[str, str]] = [
            {"event_type": r["event_type"], "src_character_id": r["src_character_id"]}
            async for r in result
        ]

        applied = 0
        for event in events:
            delta = self._rule_index.get(event["event_type"])
            if delta is None:
                continue
            factions = await self._get_character_factions(session, event["src_character_id"])
            if not factions:
                continue
            standings = await self._get_all_standings(session)
            for src_faction in factions:
                partners = {s["dst_id"] for s in standings if s["src_id"] == src_faction}
                for dst_faction in partners:
                    current = next(
                        (s["standing"] for s in standings if s["src_id"] == src_faction and s["dst_id"] == dst_faction),
                        0,
                    )
                    new_standing = max(-100, min(100, current + delta))
                    if new_standing != current:
                        tx = await session.begin_transaction()
                        async with tx:
                            await set_standing(tx, src_id=src_faction, dst_id=dst_faction, standing=new_standing)
                        applied += 1
        return applied

    async def _apply_decay(self, session: AsyncSession) -> int:
        """Drift all faction standings toward zero by rate_per_tick.

        Args:
            session: Active Neo4j async session.

        Returns:
            Number of standings updated by decay.
        """
        standings = await self._get_all_standings(session)
        rate = self._rules.decay.rate_per_tick
        min_mag = self._rules.decay.min_magnitude
        applied = 0
        for s in standings:
            current = s["standing"]
            if abs(current) < min_mag:
                continue
            new_standing = current - rate if current > 0 else current + rate
            tx = await session.begin_transaction()
            async with tx:
                await set_standing(tx, src_id=s["src_id"], dst_id=s["dst_id"], standing=new_standing)
            applied += 1
        return applied

    async def _get_character_factions(self, session: AsyncSession, character_id: str) -> list[str]:
        """Return faction IDs the character belongs to.

        Args:
            session: Active Neo4j async session.
            character_id: ID of the character node.

        Returns:
            List of faction ID strings.
        """
        result = await session.run(CYPHER_GET_CHARACTER_FACTIONS, character_id=character_id)
        return [r["faction_id"] async for r in result]

    async def _get_all_standings(self, session: AsyncSession) -> list[dict[str, Any]]:
        """Fetch all STANDS_WITH edges from the graph.

        Args:
            session: Active Neo4j async session.

        Returns:
            List of dicts with src_id, dst_id, standing keys.
        """
        result = await session.run(CYPHER_GET_ALL_STANDINGS)
        return [
            {"src_id": r["src_id"], "dst_id": r["dst_id"], "standing": int(r["standing"])}
            async for r in result
        ]
