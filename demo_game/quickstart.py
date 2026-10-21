"""
Module: quickstart
Layer: demo_game (standalone script — zero npc_engine imports)
Purpose: Self-contained hello-world that proves the clone→up→seed→talk pitch.
         `make hello` checks /health, seeds one location + NPC + event, posts one
         dialogue turn, and prints the NPC reply (idempotent).
         `make chat NPC=<id>` runs an interactive REPL: reads stdin lines and sends
         each via the WS dialogue route, printing npc_response, emotion, and
         relation_deltas. Exits on EOF.
Dependencies: httpx, websockets, argparse, os, sys, queue (stdlib + httpx/websockets)
Used by: make hello, make chat NPC=<id>, direct: python -m demo_game.quickstart
"""

from __future__ import annotations

import argparse
import os
import queue
import sys

import httpx

from demo_game.dialogue_ws import dialogue_ws_worker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOCATION_ID = "quickstart_market"
_NPC_ID = "quickstart_trader"
_EVENT_ID = "quickstart_rumor"
_PLAYER_ID = "player_demo"
_SESSION_ID = "qs_session_001"
_SEED_TIMEOUT = 10.0
_DIALOGUE_TIMEOUT = 120.0


# ---------------------------------------------------------------------------
# Seed helpers (idempotent — skip if node/edge already exists)
# ---------------------------------------------------------------------------


def _seed_node(client: httpx.Client, node_type: str, properties: dict) -> None:
    """Upsert a graph node, skipping silently if it already exists.

    Args:
        client: Authenticated httpx.Client.
        node_type: Registered node type, e.g. "Location", "Character", "Event".
        properties: Property dict including the node's id field.
    """
    node_id = properties["id"]
    check = client.get(f"/v1/graph/nodes/{node_type}/{node_id}", timeout=_SEED_TIMEOUT)
    if check.status_code == 200:
        return
    resp = client.post(f"/v1/graph/nodes/{node_type}", json={"properties": properties}, timeout=_SEED_TIMEOUT)
    resp.raise_for_status()


def _seed_edge(
    client: httpx.Client,
    edge_type: str,
    src_id: str,
    dst_id: str,
    properties: dict | None = None,
) -> None:
    """Upsert a graph edge, skipping silently if it already exists.

    Args:
        client: Authenticated httpx.Client.
        edge_type: Registered edge type, e.g. "LOCATED_AT", "KNOWS_ABOUT".
        src_id: Source node ID.
        dst_id: Destination node ID.
        properties: Optional edge properties.
    """
    check = client.get(f"/v1/graph/edges/{edge_type}/{src_id}/{dst_id}", timeout=_SEED_TIMEOUT)
    if check.status_code == 200:
        return
    resp = client.post(
        f"/v1/graph/edges/{edge_type}",
        json={"src_id": src_id, "dst_id": dst_id, "properties": properties or {}},
        timeout=_SEED_TIMEOUT,
    )
    resp.raise_for_status()


def _seed_world(client: httpx.Client) -> None:
    """Seed one location, one NPC, one event, and the linking edges.

    Args:
        client: Authenticated httpx.Client.
    """
    _seed_node(client, "Location", {
        "id": _LOCATION_ID,
        "name": "Quickstart Market",
        "location_tag": "market",
        "descriptor": "A small open-air market — the ideal place to learn the engine.",
        "region": "city",
        "last_graph_updated_at": "2026-01-01T00:00:00+00:00",
    })

    _seed_node(client, "Character", {
        "id": _NPC_ID,
        "name": "Quinn the Trader",
        "archetype": "merchant",
        "faction": "neutral",
        "biography": "A wandering trader who hears every rumour that passes through the market.",
        "is_player": False,
        "is_active": True,
        "gossipy": 70,
        "credulity": 50,
        "honesty": 65,
        "current_mood": "neutral",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "last_graph_updated_at": "2026-01-01T00:00:00+00:00",
    })

    _seed_node(client, "Event", {
        "id": _EVENT_ID,
        "summary": "Strange lights were spotted on the northern road last night.",
        "event_type": "discovery",
        "location_id": _LOCATION_ID,
        "severity": 40,
        "is_public": True,
        "tick_id": 0,
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "last_graph_updated_at": "2026-01-01T00:00:00+00:00",
        "item_type": "event",
    })

    _seed_edge(client, "LOCATED_AT", _NPC_ID, _LOCATION_ID)
    _seed_edge(client, "KNOWS_ABOUT", _NPC_ID, _EVENT_ID, {
        "knowledge_state": "rumor",
        "learned_at_tick": 0,
    })


# ---------------------------------------------------------------------------
# REPL helpers
# ---------------------------------------------------------------------------


def _print_reply(result_q: queue.Queue) -> None:
    """Drain result_q and print npc_response, emotion, and relation_deltas.

    Args:
        result_q: Populated queue from dialogue_ws_worker (fully drained on return).
    """
    tokens: list[str] = []
    while True:
        try:
            kind, data = result_q.get_nowait()
        except queue.Empty:
            break
        if kind == "token":
            tokens.append(str(data))
        elif kind == "done":
            npc_response = "".join(tokens)
            emotion = data.get("emotion", "")
            relation_deltas = data.get("relation_deltas", {})
            print(f"npc_response: {npc_response}")
            print(f"emotion: {emotion}")
            print(f"relation_deltas: {relation_deltas}")
            return
        elif kind == "error":
            raise RuntimeError(str(data))


def chat_repl(ws_base_url: str, api_key: str, npc_id: str) -> None:
    """Read stdin lines and send each to npc_id over the WS dialogue route.

    Each line produces one call to dialogue_ws_worker; the reply is printed as
    npc_response, emotion, and relation_deltas. Exits on EOF.

    Args:
        ws_base_url: WebSocket base URL, e.g. ``ws://localhost:8000``.
        api_key: Bearer token for authentication.
        npc_id: Target NPC identifier.
    """
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        result_q: queue.Queue = queue.Queue()
        payload = {
            "player_id": _PLAYER_ID,
            "npc_id": npc_id,
            "player_message": line,
            "location_id": _LOCATION_ID,
            "session_id": _SESSION_ID,
        }
        dialogue_ws_worker(ws_base_url, api_key, payload, result_q)
        _print_reply(result_q)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Dispatch to hello-world flow or interactive REPL based on --npc argument.

    Args:
        argv: Argument list; defaults to [] when None so test callers are unaffected
            by the process sys.argv. Pass sys.argv[1:] from __main__ for CLI use.
    """
    parser = argparse.ArgumentParser(description="NPC Engine quickstart")
    parser.add_argument("--npc", default=None, help="NPC id for chat REPL mode")
    args = parser.parse_args([] if argv is None else argv)

    base_url = os.environ.get("NPC_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("NPC_API_KEY", "")

    if args.npc:
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        chat_repl(ws_url, api_key, args.npc)
        return

    client = httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}"},
    )

    # 1. Health check
    health = client.get("/health", timeout=_SEED_TIMEOUT)
    health.raise_for_status()
    print(f"[quickstart] Engine healthy — {health.json()}")

    # 2. Seed minimal world
    _seed_world(client)
    print(f"[quickstart] World seeded (location={_LOCATION_ID}, npc={_NPC_ID}, event={_EVENT_ID})")

    # 3. One dialogue turn
    resp = client.post(
        "/v1/dialogue",
        json={
            "player_id": _PLAYER_ID,
            "npc_id": _NPC_ID,
            "player_message": "Hello, what do you know?",
            "location_id": _LOCATION_ID,
            "session_id": _SESSION_ID,
        },
        timeout=_DIALOGUE_TIMEOUT,
    )
    resp.raise_for_status()
    reply = resp.json().get("response_text", "")
    print(f"\nQuinn the Trader says: {reply}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as exc:  # noqa: BLE001
        print(f"[quickstart] Error: {exc}", file=sys.stderr)
        sys.exit(1)
