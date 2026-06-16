"""
Module: faction_politics_engine
Layer: engines
Purpose: Deterministic engine that adjusts faction standings based on recent events and applies
         slow decay toward neutral. Runs once per tick advance.
Does NOT: call LLMs, open Neo4j sessions, run Cypher, or expose HTTP routes.
Dependencies injected: FactionPoliticsRules + FactionPoliticsGraphPort (via constructor).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from npc_engine.engines.faction_politics.rules_loader import FactionPoliticsRules

if TYPE_CHECKING:
    from npc_engine.engines.ports.faction_politics_port import FactionPoliticsGraphPort

_LOGGER = logging.getLogger(__name__)

_STANDING_MIN = -100
_STANDING_MAX = 100
_DECAY_CAUSE_RULE_ID = "decay"


class FactionPoliticsEngine:
    """Adjusts faction standings deterministically based on world events and time decay.

    On each tick:
    1. Reads recent events that have a src_character_id.
    2. For each event whose type matches a rule, looks up the source character's
       factions and adjusts standing toward any faction standing partners.
    3. Applies decay: all standings drift toward 0 by rate_per_tick if their
       magnitude exceeds min_magnitude.
    """

    def __init__(self, rules: FactionPoliticsRules, repo: FactionPoliticsGraphPort) -> None:
        """Initialise the engine with a loaded rule set and graph repository.

        Args:
            rules: Validated FactionPoliticsRules loaded from rules.yaml.
            repo: FactionPoliticsGraphPort adapter for reads + the atomic standing write.
        """
        self._rules = rules
        self._repo = repo
        self._lock = asyncio.Lock()
        self._rule_index: dict[str, int] = {r.event_type: r.standing_delta for r in rules.rules}

    async def run_tick(self, *, tick_id: int = 0, **_: Any) -> dict[str, Any]:
        """Execute one faction politics tick: apply event rules then decay.

        Args:
            tick_id: Current game tick; written onto FactionStandingEvent nodes.
            **_: Swallows the scheduler's ``session=`` kwarg during the SEV-24 migration.

        Returns:
            Dict with keys ``rule_applications`` (int) and ``decay_applications`` (int).
        """
        async with self._lock:
            rule_apps, modified_pairs = await self._apply_rules(tick_id=tick_id)
            decay_apps = await self._apply_decay(skip=modified_pairs, tick_id=tick_id)
            _LOGGER.info(
                "faction_politics tick: %d rule applications, %d decay applications",
                rule_apps,
                decay_apps,
            )
            return {"rule_applications": rule_apps, "decay_applications": decay_apps}

    async def _apply_rules(self, *, tick_id: int = 0) -> tuple[int, set[tuple[str, str]]]:
        """Apply event-based standing rules and record each change as a FactionStandingEvent.

        Args:
            tick_id: Current game tick for FactionStandingEvent nodes.

        Returns:
            Tuple of (number of standing updates applied, set of (src_id, dst_id) pairs modified).
        """
        events: list[dict[str, str]] = await self._repo.get_recent_events()
        applied = 0
        modified_pairs: set[tuple[str, str]] = set()
        for event in events:
            delta = self._rule_index.get(event["event_type"])
            if delta is None:
                continue
            factions = await self._repo.get_character_factions(character_id=event["src_character_id"])
            if not factions:
                continue
            standings = await self._repo.get_all_standings()
            applied += await self._apply_event_to_factions(
                event, delta=delta, factions=factions, standings=standings, modified=modified_pairs,
                tick_id=tick_id,
            )
        return applied, modified_pairs

    async def _apply_event_to_factions(
        self,
        event: dict[str, str],
        *,
        delta: int,
        factions: list[str],
        standings: list[dict[str, Any]],
        modified: set[tuple[str, str]],
        tick_id: int,
    ) -> int:
        """Adjust standings of every partner of the source character's factions for one event.

        Args:
            event: Event dict with event_id and event_type.
            delta: Signed standing change from the matched rule.
            factions: Source character's faction ids.
            standings: All current STANDS_WITH edges.
            modified: Accumulator of (src, dst) pairs changed this tick (mutated).
            tick_id: Current game tick.

        Returns:
            Number of standing updates applied for this event.
        """
        applied = 0
        for src_faction in factions:
            partners = {s["dst_id"] for s in standings if s["src_id"] == src_faction}
            for dst_faction in partners:
                changed = await self._adjust_pair(
                    event, delta=delta, src_faction=src_faction, dst_faction=dst_faction,
                    standings=standings, tick_id=tick_id,
                )
                if changed:
                    applied += 1
                    modified.add((src_faction, dst_faction))
        return applied

    async def _adjust_pair(
        self,
        event: dict[str, str],
        *,
        delta: int,
        src_faction: str,
        dst_faction: str,
        standings: list[dict[str, Any]],
        tick_id: int,
    ) -> bool:
        """Apply one rule delta to a single (src, dst) standing pair, clamped to bounds.

        Returns:
            True if the standing changed and was committed, False otherwise.
        """
        current = next(
            (s["standing"] for s in standings
             if s["src_id"] == src_faction and s["dst_id"] == dst_faction),
            0,
        )
        new_standing = max(_STANDING_MIN, min(_STANDING_MAX, current + delta))
        if new_standing == current:
            return False
        await self._repo.commit_standing_change(
            src_id=src_faction, dst_id=dst_faction, new_standing=new_standing,
            delta=delta, tick=tick_id,
            cause_event_id=event.get("event_id"), cause_rule_id=event["event_type"],
        )
        return True

    async def _apply_decay(
        self,
        *,
        skip: set[tuple[str, str]] | None = None,
        tick_id: int = 0,
    ) -> int:
        """Drift all faction standings toward zero by rate_per_tick.

        Records each decay as a FactionStandingEvent with cause_rule_id="decay".

        Args:
            skip: Pairs modified by rules this tick; these are excluded from decay.
            tick_id: Current game tick for FactionStandingEvent nodes.

        Returns:
            Number of standings updated by decay.
        """
        standings = await self._repo.get_all_standings()
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
            await self._repo.commit_standing_change(
                src_id=s["src_id"], dst_id=s["dst_id"], new_standing=new_standing,
                delta=new_standing - current, tick=tick_id, cause_rule_id=_DECAY_CAUSE_RULE_ID,
            )
            applied += 1
        return applied
