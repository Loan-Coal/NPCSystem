"""
Module: action_workers
Layer: demo_game
Purpose: Background-thread worker functions for the demo game. Each worker runs
         in a daemon thread, executes one API call, and pushes the result or exception
         onto a queue for the main thread to drain each frame.
Dependencies: demo_game.client, demo_game.knowledge_sidebar_fetcher
Used by: demo_game.game_controller
"""

from __future__ import annotations

import logging
import queue

from demo_game.client import EngineClient, EngineClientError
from demo_game.constants import BRIBE_GOLD_COST, BRIBE_STANDING_GAIN, SPREAD_RUMOR_TEXT, SPREAD_RUMOR_SEVERITY
from demo_game.knowledge_sidebar_fetcher import fetch_npc_knowledge

_logger = logging.getLogger(__name__)

_STANDING_CAP = 100
_STANDING_FLOOR = -100
_CHAR_NODE_TYPE = "Character"


def _get_player_location(client: EngineClient, player_id: str) -> str | None:
    """Return the player's current location ID, or None on failure."""
    try:
        edges = client.get_graph_edges("LOCATED_AT", src_id=player_id)
        return next((e.get("dst_id") for e in edges if e.get("dst_id")), None)
    except EngineClientError as exc:
        _logger.warning("get_player_location failed: %s", exc)
        return None


def _get_current_tick(client: EngineClient) -> int | None:
    """Return the current game tick from the clock state, or None on failure."""
    try:
        state = client.get_clock_state()
        tick = state.get("data", {}).get("tick_id")
        return int(tick) if tick is not None else None
    except EngineClientError as exc:
        _logger.warning("get_current_tick failed: %s", exc)
        return None


def dialogue_worker(client: EngineClient, payload: dict, result_q: queue.Queue) -> None:
    """Call post_dialogue and push the result or exception onto result_q."""
    try:
        result_q.put(client.post_dialogue(**payload))
    except Exception as exc:
        result_q.put(exc)


def fetch_sidebar_worker(client: EngineClient, npc_id: str, result_q: queue.Queue) -> None:
    """Fetch KNOWS_ABOUT pairs for npc_id and push (status, npc_id, data)."""
    try:
        pairs = fetch_npc_knowledge(client, npc_id)
        result_q.put(("ok", npc_id, pairs))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


def generate_quest_worker(client: EngineClient, npc_id: str, result_q: queue.Queue) -> None:
    """Call post_quest_generate and push ("ok", quest_dict) or ("err", exc)."""
    try:
        data = client.post_quest_generate(npc_id)
        quest_id = data.get("quest_id")
        quest = client.get_quest(quest_id) if quest_id else None
        result_q.put(("ok", quest))
    except Exception as exc:
        result_q.put(("err", exc))


def travel_worker(client: EngineClient, player_id: str, location_id: str, result_q: queue.Queue) -> None:
    """Move player to location_id and advance the clock by one tick.

    Removes any existing LOCATED_AT edge(s) for the player before adding the
    new one so the player is never simultaneously at two locations.

    Pushes ("ok", location_id) on success, ("err", location_id, exc) on failure.
    """
    try:
        existing = client.get_graph_edges("LOCATED_AT", src_id=player_id)
        for edge in existing:
            old_loc = edge.get("dst_id")
            if old_loc and old_loc != location_id:
                client.delete_edge("LOCATED_AT", player_id, old_loc)
        client.upsert_edge("LOCATED_AT", player_id, location_id, {})
        client.advance_clock(delta_ticks=1)
        result_q.put(("ok", location_id))
    except Exception as exc:
        result_q.put(("err", location_id, exc))


def bribe_worker(
    client: EngineClient,
    player_id: str,
    npc_id: str,
    faction_id: str,
    result_q: queue.Queue,
) -> None:
    """Pay BRIBE_GOLD_COST to improve the player's standing with faction_id by BRIBE_STANDING_GAIN.

    Reads the player's current gold and standing, validates sufficient funds,
    then writes the new standing and deducts the cost.

    When the player's current location and tick are retrievable, calls
    adjust_npc_reputation so a gossip-propagatable reputation Event is seeded
    for co-located NPCs. Falls back to put_npc_reputation if either lookup fails.

    Pushes ("ok", faction_id, new_standing) on success or ("err", npc_id, exc) on failure.
    If the player cannot afford the bribe, pushes ("err", npc_id, ValueError).
    """
    try:
        char = client.get_node(_CHAR_NODE_TYPE, player_id) or {}
        gold = int(char.get("currency_balance") or 0)
        if gold < BRIBE_GOLD_COST:
            result_q.put(("err", npc_id, ValueError(f"Not enough gold (have {gold}, need {BRIBE_GOLD_COST})")))
            return

        reps = client.get_npc_reputation(player_id)
        current = next((int(r.get("standing") or 0) for r in reps if r.get("faction_id") == faction_id), 0)
        new_standing = min(_STANDING_CAP, current + BRIBE_STANDING_GAIN)

        location_id = _get_player_location(client, player_id)
        tick_id = _get_current_tick(client)

        if location_id is not None and tick_id is not None:
            resp = client.adjust_npc_reputation(player_id, faction_id, BRIBE_STANDING_GAIN, location_id, tick_id)
            new_standing = int((resp.get("data") or {}).get("standing") or new_standing)
        else:
            client.put_npc_reputation(player_id, faction_id, new_standing)

        client.patch_node(_CHAR_NODE_TYPE, player_id, {"currency_balance": gold - BRIBE_GOLD_COST})
        result_q.put(("ok", faction_id, new_standing))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


def consolidate_memory_worker(
    client: EngineClient,
    npc_id: str,
    player_id: str,
    result_q: queue.Queue,
) -> None:
    """Consolidate session dialogue turns for npc_id into a Memory node.

    Pushes ("ok", npc_id, memory_id) if a memory was created (memory_id may be
    None if the turn threshold was not met), or ("err", npc_id, exc) on failure.
    """
    try:
        memory_id = client.consolidate_memory(npc_id, player_id)
        result_q.put(("ok", npc_id, memory_id))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


def spread_rumor_worker(
    client: EngineClient,
    npc_id: str,
    result_q: queue.Queue,
) -> None:
    """Plant the default rumor at npc_id and push ("ok", npc_id, event_id) or ("err", npc_id, exc).

    Fetches the current tick from the clock endpoint so the Event node is stamped
    with the correct occurred_at value.  Falls back to tick_id=0 if the clock is
    unreachable.
    """
    try:
        tick_id = _get_current_tick(client) or 0
        resp = client.spread_rumor(
            target_npc_id=npc_id,
            rumor_text=SPREAD_RUMOR_TEXT,
            severity=SPREAD_RUMOR_SEVERITY,
            tick_id=tick_id,
        )
        event_id = (resp.get("data") or {}).get("event_id", "")
        result_q.put(("ok", npc_id, event_id))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


def correct_rumor_worker(
    client: EngineClient,
    npc_id: str,
    event_id: str,
    result_q: queue.Queue,
) -> None:
    """Mark npc_id's belief in event_id as corrected and push ("ok", npc_id, event_id) or ("err", npc_id, exc)."""
    try:
        client.correct_rumor(npc_id=npc_id, event_id=event_id)
        result_q.put(("ok", npc_id, event_id))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


def inspect_worker(client: EngineClient, npc_id: str, result_q: queue.Queue) -> None:
    """Fetch all NPC graph data and push ("ok", npc_id, data_dict) or ("err", npc_id, exc).

    Sequentially fetches npc_state (character + relations + events), items, reputation,
    goals, beliefs, and emotion. Partial failures for optional fields are swallowed so
    the card always renders with whatever data is available.
    """
    try:
        state = client.get_npc_state(npc_id)
        char = state.get("character") or {}
        relations = state.get("relations") or []
        events = state.get("events") or []

        try:
            items = client.get_items_for_character(npc_id)
        except Exception:
            items = []

        try:
            factions = client.get_npc_reputation(npc_id)
        except Exception:
            factions = []

        try:
            goals = client.get_goals(npc_id)
        except Exception:
            goals = []

        try:
            beliefs = client.get_beliefs(npc_id)
        except Exception:
            beliefs = []

        try:
            emotion = client.get_npc_emotion(npc_id) or {}
        except Exception:
            emotion = {}

        result_q.put(("ok", npc_id, {
            "character": char,
            "relations": relations,
            "events": events,
            "items": items,
            "factions": factions,
            "goals": goals,
            "beliefs": beliefs,
            "emotion": emotion,
        }))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))
