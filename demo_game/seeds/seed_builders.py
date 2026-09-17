"""
Module: seed_builders
Layer: demo_game (external client)
Purpose: Pure builder functions and shared constants for the demo-world seeder.
         No I/O — every function is a pure transformation of its inputs.
Dependencies: pydantic
Used by: demo_game.seeds.seed_io, demo_game.seeds.seed_domain, demo_game.seeds.seed
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared constants (used by seed_io and seed_domain as well)
# ---------------------------------------------------------------------------

_GAME_TIME: dict = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
# Prior-era timestamp for is_historical memories (e.g. a war fought long before the
# current year-1 epoch). Marks a memory as long-past so the NPC frames it as a past
# recollection, never the current situation (S26.3, ISSUE-093).
_HISTORICAL_GAME_TIME: dict = {"year": 0, "season": "autumn", "day": 1, "time_of_day": "night"}
_WORLD_STATE_ID = "world"
# Scarcity constraint (S7.2): bribing all 3 factions to win threshold costs 4*20*3=240 gold.
# Starting at 60 the player demonstrably cannot win by bribing alone; must earn via quest/trade.
_PLAYER_STARTING_GOLD = 60


# ---------------------------------------------------------------------------
# Internal ID helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _belief_id(npc_id: str, content: str) -> str:
    """Derive stable belief node ID: bel_{npc_id}_{sha1(content)[:8]}."""
    return f"bel_{npc_id}_{hashlib.sha1(content.encode()).hexdigest()[:8]}"


def _goal_id(npc_id: str, n: int) -> str:
    """Derive stable goal node ID: goal_{npc_id}_{n} (0-based index)."""
    return f"goal_{npc_id}_{n}"


def _memory_id(npc_id: str, n: int) -> str:
    """Derive stable memory node ID: mem_{npc_id}_{n} (0-based index)."""
    return f"mem_{npc_id}_{n}"


def _secret_id(npc_id: str) -> str:
    """Derive stable secret node ID: sec_{npc_id} (one secret per NPC)."""
    return f"sec_{npc_id}"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WorldStatePayload(BaseModel):
    """Typed world_state node property payload for the demo seeder (ISSUE-084).

    `.model_dump()` yields the property dict consumed by the generic node upsert.
    """

    id: str
    epoch: str
    active_conditions: list[str]
    faction_standings: dict[str, int] = Field(default_factory=dict)
    time_of_day: str = "morning"
    weather: str = "clear"
    last_updated_at: str
    last_graph_updated_at: str


# ---------------------------------------------------------------------------
# Builder functions (pure — no I/O)
# ---------------------------------------------------------------------------


def build_location_payload(
    id: str,
    name: str,
    location_tag: str,
    descriptor: str,
) -> dict:
    """Return a Location node property dict ready for upsert_node.

    Args:
        id: Stable node ID, e.g. "loc_tavern".
        name: Human-readable display name.
        location_tag: Short tag used by the engine for archetype logic.
        descriptor: One-sentence description of the location.

    Returns:
        Dict with all required Location properties.
    """
    now = _now()
    return {
        "id": id,
        "name": name,
        "location_tag": location_tag,
        "descriptor": descriptor,
        "region": "city",
        "last_graph_updated_at": now,
    }


def build_faction_payload(
    id: str,
    name: str,
    archetype: str,
    description: str,
) -> dict:
    """Return a Faction node property dict ready for upsert_node.

    Args:
        id: Stable faction ID, e.g. "merchants_guild".
        name: Human-readable faction name.
        archetype: Faction archetype (mercantile, military, criminal, etc.).
        description: One-sentence description.

    Returns:
        Dict with all required Faction properties.
    """
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "description": description,
        "is_active": True,
        "created_at": now,
        "last_graph_updated_at": now,
    }


def build_npc_payload(
    id: str,
    name: str,
    archetype: str,
    faction_id: str,
    location_id: str,
    biography: str,
    gossipy: int,
    credulity: int,
    honesty: int,
    voice_descriptor: str | None = None,
) -> dict:
    """Return a Character node property dict ready for upsert_node.

    Args:
        id: Stable character ID, e.g. "mira_innkeeper".
        name: Display name.
        archetype: Character archetype (innkeeper, merchant, guard_captain, etc.).
        faction_id: Faction node ID or "neutral".
        location_id: Home location node ID.
        biography: One-sentence biography.
        gossipy: Tendency to spread information (0–100).
        credulity: Tendency to believe information (0–100).
        honesty: Tendency to tell the truth (0–100).
        voice_descriptor: Optional LLM voice/tone guidance string.

    Returns:
        Dict with all required Character properties.
    """
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "faction": faction_id,
        "biography": biography,
        "is_player": False,
        "is_active": True,
        "gossipy": gossipy,
        "credulity": credulity,
        "honesty": honesty,
        "current_mood": "neutral",
        "voice_descriptor": voice_descriptor,
        "created_at": now,
        "updated_at": now,
        "last_graph_updated_at": now,
    }


def build_event_payload(
    id: str,
    summary: str,
    event_type: str,
    location_id: str,
    severity: int,
    is_public: bool = False,
    tick_id: int = 0,
) -> dict:
    """Return an Event node property dict ready for upsert_node.

    Args:
        id: Stable event ID, e.g. "northern_war_begins".
        summary: Short description of what happened.
        event_type: Event category (conflict, discovery, crime, etc.).
        location_id: Where the event occurred.
        severity: How impactful the event is (0–100).
        is_public: Whether the event is broadly known.
        tick_id: Game tick at which the event occurred.

    Returns:
        Dict with all required Event properties.
    """
    now = _now()
    return {
        "id": id,
        "summary": summary,
        "event_type": event_type,
        "location_id": location_id,
        "severity": severity,
        "is_public": is_public,
        "tick_id": tick_id,
        "occurred_at": now,
        "last_graph_updated_at": now,
    }


def build_world_state_payload(
    epoch: str,
    active_conditions: list[str],
) -> WorldStatePayload:
    """Return a typed world_state node property payload.

    Args:
        epoch: Current epoch name (e.g. "peace", "war").
        active_conditions: List of active condition IDs.

    Returns:
        WorldStatePayload with all required world_state properties.
    """
    now = _now()
    return WorldStatePayload(
        id=_WORLD_STATE_ID,
        epoch=epoch,
        active_conditions=active_conditions,
        last_updated_at=now,
        last_graph_updated_at=now,
    )
