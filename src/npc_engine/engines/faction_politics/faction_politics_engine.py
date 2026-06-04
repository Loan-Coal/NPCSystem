"""
Module: faction_politics_engine
Layer: engines
Purpose: Deterministic engine that adjusts faction standings based on recent events and applies
         slow decay toward neutral. Runs once per tick advance.
Does NOT: call LLMs or expose HTTP routes.
Dependencies injected: FactionPoliticsRules (via constructor), AsyncSession (per tick call).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.faction_politics.rules_loader import FactionPoliticsRules
from npc_engine.graph.faction_history_service import record_standing_change
from npc_engine.graph.faction_politics_queries import (
    get_all_standings,
    get_character_factions,
    get_recent_events,
)
from npc_engine.graph.faction_writer import set_standing

_LOGGER = logging.getLogger(__name__)


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

    async def run_tick(self, session: AsyncSession, tick_id: int = 0) -> dict[str, Any]:
        """Execute one faction politics tick: apply event rules then decay.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick; written onto FactionStandingEvent nodes.

        Returns:
            Dict with keys ``rule_applications`` (int) and ``decay_applications`` (int).
        """
        async with self._lock:
            rule_apps, modified_pairs = await self._apply_rules(session, tick_id=tick_id)
            decay_apps = await self._apply_decay(session, skip=modified_pairs, tick_id=tick_id)
            _LOGGER.info(
                "faction_politics tick: %d rule applications, %d decay applications",
                rule_apps,
                decay_apps,
            )
            return {"rule_applications": rule_apps, "decay_applications": decay_apps}

    async def _apply_rules(
        self, session: AsyncSession, *, tick_id: int = 0
    ) -> tuple[int, set[tuple[str, str]]]:
        """Apply event-based standing rules and record each change as a FactionStandingEvent.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick for FactionStandingEvent nodes.

        Returns:
            Tuple of (number of standing updates applied, set of (src_id, dst_id) pairs modified).
        """
        events: list[dict[str, str]] = await get_recent_events(session)

        applied = 0
        modified_pairs: set[tuple[str, str]] = set()
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
                        await record_standing_change(
                            session,
                            src_faction_id=src_faction,
                            dst_faction_id=dst_faction,
                            delta=delta,
                            new_standing=new_standing,
                            tick=tick_id,
                            cause_event_id=event.get("event_id"),
                            cause_rule_id=event["event_type"],
                        )
                        applied += 1
                        modified_pairs.add((src_faction, dst_faction))
        return applied, modified_pairs

    async def _apply_decay(
        self,
        session: AsyncSession,
        *,
        skip: set[tuple[str, str]] | None = None,
        tick_id: int = 0,
    ) -> int:
        """Drift all faction standings toward zero by rate_per_tick.

        Records each decay as a FactionStandingEvent with cause_rule_id="decay".

        Args:
            session: Active Neo4j async session.
            skip: Pairs modified by rules this tick; these are excluded from decay.
            tick_id: Current game tick for FactionStandingEvent nodes.

        Returns:
            Number of standings updated by decay.
        """
        standings = await self._get_all_standings(session)
        rate = self._rules.decay.rate_per_tick
        min_mag = self._rules.decay.min_magnitude
        skip_set = skip or set()
        applied = 0
        for s in standings:
            if (s["src_id"], s["dst_id"]) in skip_set:
                continue
            current = s["standing"]
            if abs(current) < min_mag:
                continue
            new_standing = current - rate if current > 0 else current + rate
            tx = await session.begin_transaction()
            async with tx:
                await set_standing(tx, src_id=s["src_id"], dst_id=s["dst_id"], standing=new_standing)
            await record_standing_change(
                session,
                src_faction_id=s["src_id"],
                dst_faction_id=s["dst_id"],
                delta=new_standing - current,
                new_standing=new_standing,
                tick=tick_id,
                cause_rule_id="decay",
            )
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
        return await get_character_factions(session, character_id=character_id)

    async def _get_all_standings(self, session: AsyncSession) -> list[dict[str, Any]]:
        """Fetch all STANDS_WITH edges from the graph.

        Args:
            session: Active Neo4j async session.

        Returns:
            List of dicts with src_id, dst_id, standing keys.
        """
        return await get_all_standings(session)
