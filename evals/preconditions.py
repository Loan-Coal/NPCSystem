"""
Module: preconditions
Layer: evals (eval harness — not part of src/)
Purpose: Reusable clean-state + precondition guard for eval runs — reset world_state
         to a declared baseline, ensure the player node exists, and assert required
         nodes/edges are present before any case is scored.
Dependencies: datetime, typing, pydantic, httpx (via the injected client only).
Used by: evals/runner.py, evals/anti_hallucination_runner.py, e2e clean_world fixture.
Does NOT: import from src/npc_engine/ (keeps evals/ src-free), call any LLM.

Closes the ISSUE-119 contamination half (no world reset) and makes the harness
comply with the strict-player policy (ISSUE-118) by creating the player node
unconditionally rather than as a side-effect of reputation setup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

_WORLD_STATE_PATCH_PATH = "/v1/graph/nodes/world_state/world"
_CHARACTER_NODE_PATH = "/v1/graph/nodes/Character"
_DEFAULT_TIMEOUT_S = 10.0

_PLAYER_DEFAULTS: dict[str, Any] = {
    "archetype": "player",
    "biography": "The player character.",
    "is_player": True,
    "is_active": True,
    "gossipy": 50,
    "credulity": 50,
    "honesty": 50,
    "current_mood": "neutral",
    "voice_descriptor": None,
}

PreconditionKind = Literal["node", "edge", "world_condition"]


class PreconditionError(Exception):
    """Raised when an eval precondition is not met (missing node/edge/world condition).

    Fails loud so an eval never runs silently against a contaminated or unseeded graph.
    """

    def __init__(self, kind: PreconditionKind, missing: tuple[str, ...]) -> None:
        self.kind = kind
        self.missing = missing
        super().__init__(f"Unmet {kind} precondition(s): {', '.join(missing) or '(none)'}")


class WorldBaseline(BaseModel):
    """Declared clean baseline for world_state before an eval run."""

    model_config = ConfigDict(frozen=True)

    epoch: Literal["age_of_peace", "war"] = "age_of_peace"
    active_conditions: tuple[str, ...] = ()


class Preconditions(BaseModel):
    """Nodes/edges that must exist before an eval is scored, plus the player id."""

    required_nodes: tuple[tuple[str, str], ...] = ()
    required_edges: tuple[str, ...] = ()
    player_id: str = "player_demo"


def build_player_props(player_id: str, now: str | None = None) -> dict[str, Any]:
    """Return the Character node properties for an eval player node."""
    stamp = now or datetime.now(timezone.utc).isoformat()
    return {
        "id": player_id,
        "name": player_id,
        **_PLAYER_DEFAULTS,
        "created_at": stamp,
        "updated_at": stamp,
        "last_graph_updated_at": stamp,
    }


def reset_world(client: Any, base_url: str, baseline: WorldBaseline) -> None:
    """PATCH world_state to the declared baseline. Raises PreconditionError on non-200."""
    resp = client.patch(
        f"{base_url}{_WORLD_STATE_PATCH_PATH}",
        json={
            "properties": {
                "epoch": baseline.epoch,
                "active_conditions": list(baseline.active_conditions),
            }
        },
        timeout=_DEFAULT_TIMEOUT_S,
    )
    if resp.status_code != 200:
        raise PreconditionError("world_condition", (f"world_state:{baseline.epoch}",))


def ensure_player_node(client: Any, base_url: str, player_id: str) -> None:
    """Create the player Character node if it does not exist (strict-player policy)."""
    check = client.get(f"{base_url}{_CHARACTER_NODE_PATH}/{player_id}", timeout=_DEFAULT_TIMEOUT_S)
    if check.status_code != 404:
        return
    resp = client.post(
        f"{base_url}{_CHARACTER_NODE_PATH}",
        json={"properties": build_player_props(player_id)},
        timeout=_DEFAULT_TIMEOUT_S,
    )
    if resp.status_code >= 400:
        raise PreconditionError("node", (f"Character:{player_id}",))


def _missing_nodes(client: Any, base_url: str, nodes: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    """Return identifiers of required nodes that return 404."""
    missing: list[str] = []
    for label, node_id in nodes:
        resp = client.get(f"{base_url}/v1/graph/nodes/{label}/{node_id}", timeout=_DEFAULT_TIMEOUT_S)
        if resp.status_code == 404:
            missing.append(f"{label}:{node_id}")
    return tuple(missing)


def _missing_edges(client: Any, base_url: str, edges: tuple[str, ...]) -> tuple[str, ...]:
    """Return edge types that are absent or empty."""
    missing: list[str] = []
    for edge_type in edges:
        resp = client.get(f"{base_url}/v1/graph/edges/{edge_type}", timeout=_DEFAULT_TIMEOUT_S)
        if resp.status_code != 200 or not resp.json().get("data"):
            missing.append(edge_type)
    return tuple(missing)


def assert_preconditions(client: Any, base_url: str, pre: Preconditions) -> None:
    """Assert required nodes and edges exist, else raise PreconditionError."""
    missing_nodes = _missing_nodes(client, base_url, pre.required_nodes)
    if missing_nodes:
        raise PreconditionError("node", missing_nodes)
    missing_edges = _missing_edges(client, base_url, pre.required_edges)
    if missing_edges:
        raise PreconditionError("edge", missing_edges)


def prepare(client: Any, base_url: str, *, baseline: WorldBaseline, pre: Preconditions) -> None:
    """Reset world to baseline, ensure the player node, then assert preconditions."""
    reset_world(client, base_url, baseline)
    ensure_player_node(client, base_url, pre.player_id)
    assert_preconditions(client, base_url, pre)
