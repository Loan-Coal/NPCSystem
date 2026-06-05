"""
Module: quickstart
Layer: demo_game (standalone script — zero npc_engine imports)
Purpose: Self-contained hello-world that proves the clone→up→seed→talk pitch.
         Checks /health, seeds one location + NPC + event, posts one dialogue turn,
         and prints the NPC reply. Safe to re-run (idempotent).
Dependencies: httpx, os, sys (stdlib + httpx only)
Used by: make hello (added by orchestrator), direct: python -m demo_game.quickstart
"""

from __future__ import annotations

import os
import sys

import httpx

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
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the quickstart flow: health check → seed → dialogue → print reply."""
    base_url = os.environ.get("NPC_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("NPC_API_KEY", "")

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
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"[quickstart] Error: {exc}", file=sys.stderr)
        sys.exit(1)
