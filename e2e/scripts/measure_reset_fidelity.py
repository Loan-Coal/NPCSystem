"""
measure_reset_fidelity.py - Measure what `preconditions.reset_world` actually
                            clears, and what it does not (EVAL-P12.1).

Assumption: the stack is running and all three worlds are seeded
            (docker-compose up -d; make demo-seed seed-village-world seed-tavern-world).

    python e2e/scripts/measure_reset_fidelity.py
    make measure-reset-fidelity

Snapshots every component the HTTP API can read, runs a mutating scenario, calls
reset_world, snapshots again, and classifies each mutated component as cleared or
surviving. Emits docs/RESET_FIDELITY.md and evals/reset_fidelity.json (the one
evals/sequence_fidelity.py reads at EVAL-P12.4).

⚠️ THIS SCRIPT CANNOT REPORT A CONVENIENT ANSWER. The tier is never chosen:
ResetFidelityReport derives it from `surviving` and refuses a tier contradicting
the evidence. Stores the API cannot read are recorded `unknown:<name>`, keeping the
tier PARTIAL — dropping them is the one way this could turn PARTIAL into false FULL.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "evals"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from preconditions import WorldBaseline, reset_world  # noqa: E402
from reset_fidelity_markdown import render  # noqa: E402
from reset_fidelity_record import ResetFidelityReport, assign_tier  # noqa: E402
from reset_snapshot import (  # noqa: E402
    CHARACTER_NODE_TYPE,
    UNOBSERVABLE_STORES,
    WORLD_STATE_NODE_TYPE,
    classify,
    digest,
    snapshot_world_state,
    unknown_entries,
    unwrap,
)

JSON_ARTIFACT = _REPO_ROOT / "evals" / "reset_fidelity.json"
MARKDOWN_ARTIFACT = _REPO_ROOT / "docs" / "RESET_FIDELITY.md"

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_RESET_REPEATS = 5
_TIMEOUT_S = 120.0
_MUTATION_NPC = "mira_innkeeper"
_MUTATION_PLAYER = "player_demo"
_MUTATION_MESSAGE = "What have you heard about the war in the north?"
_MUTATION_TICKS = 7

# The world_state values the scenario writes, chosen to differ from WorldBaseline()
# on both properties reset_world PATCHes. Without this the scenario never touches
# the reset's own targets, so the measurement cannot show the reset clearing
# anything and understates it — `cleared` comes back empty for the wrong reason.
_MUTATION_EPOCH = "war"
_MUTATION_CONDITIONS = ["northern_war"]
_WORLD_STATE_PATH = "/v1/graph/nodes/world_state/world"


def _api_key() -> str:
    """Read API_KEY_SECRET out of .env, the way the Makefile does."""
    match = re.search(r"^API_KEY_SECRET=(.+)", (_REPO_ROOT / ".env").read_text(encoding="utf-8"), re.M)
    return match.group(1).strip() if match else ""


def _git_sha() -> str:
    """Return the short commit hash the measurement was taken at."""
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _get(client: httpx.Client, base_url: str, path: str) -> Any:
    """GET a path and return its unwrapped payload, or None on a non-200."""
    response = client.get(f"{base_url}{path}", timeout=_TIMEOUT_S)
    if response.status_code != 200:
        return None
    return unwrap(response.json())


def type_names(client: httpx.Client, base_url: str) -> tuple[list[str], list[str]]:
    """Read the live node and edge type names from the schema registry.

    Args:
        client: Authenticated HTTP client.
        base_url: Engine base URL.
    Returns:
        (node type names, edge type names).
    Raises:
        RuntimeError: If the registry cannot be read — snapshotting a subset of
            the graph silently would understate what survives.
    """
    registry = _get(client, base_url, "/v1/admin/schema/registry")
    if not registry:
        raise RuntimeError("cannot read /v1/admin/schema/registry — is the stack up?")
    return (
        [t["name"] for t in registry.get("node_types", [])],
        [t["name"] for t in registry.get("edge_types", [])],
    )


def character_ids(client: httpx.Client, base_url: str) -> list[str]:
    """Return every Character id in the graph, sorted."""
    rows = _get(client, base_url, f"/v1/graph/nodes/{CHARACTER_NODE_TYPE}") or []
    return sorted(str(row["id"]) for row in rows if "id" in row)


def snapshot(
    client: httpx.Client,
    base_url: str,
    node_types: list[str],
    edge_types: list[str],
    npc_ids: list[str],
) -> dict[str, str]:
    """Digest every component of engine state the API exposes.

    Args:
        client: Authenticated HTTP client.
        base_url: Engine base URL.
        node_types: Node type names to enumerate.
        edge_types: Edge type names to enumerate.
        npc_ids: Character ids whose emotion state to read.
    Returns:
        Component name → sha256 digest.
    """
    state: dict[str, str] = {}
    for node_type in node_types:
        rows = _get(client, base_url, f"/v1/graph/nodes/{node_type}") or []
        if node_type == WORLD_STATE_NODE_TYPE:
            state.update(snapshot_world_state(rows))
            continue
        state[f"graph.nodes.{node_type}"] = digest(rows)
    for edge_type in edge_types:
        state[f"graph.edges.{edge_type}"] = digest(_get(client, base_url, f"/v1/graph/edges/{edge_type}") or [])

    emotions = {i: _get(client, base_url, f"/v1/npc/{i}/emotion") for i in npc_ids}
    state["emotion_store"] = digest(emotions)
    clock = _get(client, base_url, "/v1/clock/state") or {}
    state["game_clock.tick_id"] = digest(clock.get("tick_id"))
    state["engine_status_store"] = digest(_get(client, base_url, "/v1/admin/system/engines"))
    return state


def mutate(client: httpx.Client, base_url: str, npc_ids: list[str]) -> list[str]:
    """Run a mutating scenario: one dialogue turn, a gossip tick, a clock advance.

    Chosen because between them they write graph edges (KNOWS_ABOUT), emotion
    state, dialogue session state and the tick counter — i.e. they touch every
    store the reset would have to clear to be FULL.

    Args:
        client: Authenticated HTTP client.
        base_url: Engine base URL.
        npc_ids: Characters eligible for the gossip tick.
    Returns:
        Human-readable descriptions of the mutations that succeeded.
    Raises:
        RuntimeError: If every mutation failed — measuring a reset against an
            unchanged world would report FULL for the wrong reason.
    """
    tick = int((_get(client, base_url, "/v1/clock/state") or {}).get("tick_id", 0))
    steps: list[tuple[str, str, dict[str, Any], str]] = [
        ("PATCH", _WORLD_STATE_PATH,
         {"properties": {"epoch": _MUTATION_EPOCH, "active_conditions": _MUTATION_CONDITIONS}},
         f"PATCH world_state (epoch={_MUTATION_EPOCH}, conditions={_MUTATION_CONDITIONS})"),
        ("POST", "/v1/dialogue",
         {"player_id": _MUTATION_PLAYER, "npc_id": _MUTATION_NPC,
          "player_message": _MUTATION_MESSAGE},
         f"POST /v1/dialogue ({_MUTATION_PLAYER} -> {_MUTATION_NPC})"),
        ("POST", "/v1/admin/batch/gossip_tick",
         {"tick_override": tick + 1, "npc_ids": npc_ids[:8], "max_pairs": 4},
         "POST /v1/admin/batch/gossip_tick (max_pairs=4)"),
        ("POST", "/v1/clock/advance", {"delta_ticks": _MUTATION_TICKS},
         f"POST /v1/clock/advance (delta_ticks={_MUTATION_TICKS})"),
    ]

    applied: list[str] = []
    for method, path, payload, label in steps:
        response = client.request(method, f"{base_url}{path}", json=payload, timeout=_TIMEOUT_S)
        if response.status_code == 200:
            applied.append(label)

    if not applied:
        raise RuntimeError("no mutation succeeded — the world is unchanged, so nothing can be measured")
    return applied


def timed_resets(client: httpx.Client, base_url: str, repeats: int) -> list[int]:
    """Call reset_world `repeats` times, returning each call's wall-clock ms.

    Args:
        client: Authenticated HTTP client.
        base_url: Engine base URL.
        repeats: Number of resets to time.
    Returns:
        Per-call durations in milliseconds, in call order.
    """
    baseline = WorldBaseline()
    costs: list[int] = []
    for _ in range(repeats):
        started = time.perf_counter()
        reset_world(client, base_url, baseline)
        costs.append(int((time.perf_counter() - started) * 1000))
    return costs


def build_report(
    cleared: tuple[str, ...], surviving: tuple[str, ...], costs: list[int], git_sha: str
) -> ResetFidelityReport:
    """Assemble the artifact model, with unobservable stores folded into `surviving`.

    Args:
        cleared: Components that returned to their pre-scenario digest.
        surviving: Components that did not.
        costs: Measured per-reset costs in ms.
        git_sha: Short commit hash.
    Returns:
        A ResetFidelityReport whose tier is derived, never chosen.
    """
    all_surviving = tuple(surviving) + unknown_entries()
    return ResetFidelityReport(
        fidelity=assign_tier(all_surviving),
        cleared=cleared,
        surviving=all_surviving,
        duration_ms=sorted(costs)[len(costs) // 2],
        measured_at=datetime.now(timezone.utc).isoformat(),
        git_sha=git_sha,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the measurement and write both artifacts.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    """
    parser = argparse.ArgumentParser(prog="python e2e/scripts/measure_reset_fidelity.py")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--repeats", type=int, default=DEFAULT_RESET_REPEATS)
    args = parser.parse_args(argv)

    key = args.api_key or _api_key()
    with httpx.Client(headers={"Authorization": f"Bearer {key}"}) as client:
        node_types, edge_types = type_names(client, args.base_url)
        npc_ids = character_ids(client, args.base_url)
        print(f"Snapshotting {len(node_types)} node types, {len(edge_types)} edge types, "
              f"{len(npc_ids)} characters ...")

        # Put the world at WorldBaseline() BEFORE the baseline snapshot. Without
        # this the world may already hold the values the scenario writes, the
        # scenario then changes nothing there, and the reset's own targets fall
        # out of the measurement entirely.
        reset_world(client, args.base_url, WorldBaseline())
        baseline = snapshot(client, args.base_url, node_types, edge_types, npc_ids)
        applied = mutate(client, args.base_url, npc_ids)
        print("Mutations applied:\n  " + "\n  ".join(applied))
        mutated = snapshot(client, args.base_url, node_types, edge_types, npc_ids)

        costs = timed_resets(client, args.base_url, args.repeats)
        after = snapshot(client, args.base_url, node_types, edge_types, npc_ids)

    cleared, surviving = classify(baseline, mutated, after)
    report = build_report(cleared, surviving, costs, _git_sha())

    JSON_ARTIFACT.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    MARKDOWN_ARTIFACT.write_text(
        render(report, applied, costs, len(baseline), UNOBSERVABLE_STORES), encoding="utf-8"
    )

    print(f"\nfidelity={report.fidelity}  cleared={len(cleared)}  "
          f"surviving={len(report.observed_surviving)}  unobservable={len(report.unobservable)}")
    print(f"per-reset cost: median {report.duration_ms} ms of {costs}")
    print(f"wrote {JSON_ARTIFACT.relative_to(_REPO_ROOT)} and "
          f"{MARKDOWN_ARTIFACT.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
