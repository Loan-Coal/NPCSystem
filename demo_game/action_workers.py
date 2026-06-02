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

import queue

from demo_game.client import EngineClient
from demo_game.constants import BRIBE_GOLD_COST, BRIBE_STANDING_GAIN
from demo_game.knowledge_sidebar_fetcher import fetch_npc_knowledge

_STANDING_CAP = 100
_STANDING_FLOOR = -100
_CHAR_NODE_TYPE = "Character"


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

    Pushes ("ok", faction_id, new_standing) on success or ("err", npc_id, exc) on failure.
    If the player cannot afford the bribe, pushes ("err", npc_id, InsufficientGoldError).
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

        client.put_npc_reputation(player_id, faction_id, new_standing)
        client.patch_node(_CHAR_NODE_TYPE, player_id, {"currency_balance": gold - BRIBE_GOLD_COST})
        result_q.put(("ok", faction_id, new_standing))
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
