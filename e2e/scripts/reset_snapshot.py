"""
reset_snapshot.py - Snapshot every piece of engine state the HTTP API can read,
                    and diff two snapshots (EVAL-P12.1).

Layer: e2e tooling. Imports nothing from src/ or evals/.

A snapshot is a flat dict of `component name -> sha256 digest`. Comparing digests
rather than payloads keeps the artifact small and makes "did this change" a
one-line answer, which is the only question the fidelity measurement asks.

WHAT THIS CANNOT SEE is as load-bearing as what it can. UNOBSERVABLE_STORES lists
every in-process singleton from api/dependencies_stores.py that the API exposes no
read endpoint for. They are reported as `unknown:<name>`, never omitted: an
unobservable store silently dropped is exactly how a PARTIAL reset is written up
as a FULL one.

Usage: imported by e2e/scripts/measure_reset_fidelity.py.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

WORLD_STATE_NODE_TYPE = "world_state"
CHARACTER_NODE_TYPE = "Character"

# The two properties preconditions.reset_world actually PATCHes. Broken out of
# the world_state node digest so the artifact can say which of them was cleared,
# rather than reporting one opaque "world_state changed".
RESET_TARGET_PROPERTIES: tuple[str, ...] = ("epoch", "active_conditions")

# In-process singletons with no read endpoint. Verified against
# src/npc_engine/api/dependencies_stores.py and the live OpenAPI schema on
# 2026-08-10. Each entry is (store, why it cannot be observed).
UNOBSERVABLE_STORES: tuple[tuple[str, str], ...] = (
    ("session_store", "GET /v1/dialogue/pending is per-player and returns only queued "
                      "items; there is no endpoint that dumps session history or turn state"),
    ("dialogue_context_cache", "PartialDialogueContextCache has no route at all"),
    ("embedding_index", "GET /v1/admin/debug/retrieval requires (npc_id, query) and returns "
                        "ranked hits for that query; it cannot enumerate the index"),
    ("idempotency_service", "no route"),
    ("negotiation_store", "no route; state is reachable only by continuing a negotiation"),
    ("reindex_job_service", "GET /v1/admin/graph/reindex/{job_id} needs a job id known in "
                            "advance; jobs cannot be listed"),
)


def digest(payload: Any) -> str:
    """Hash a JSON-serialisable payload stably.

    Args:
        payload: Any JSON-serialisable object.
    Returns:
        Hex sha256 over the canonical JSON form.
    """
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def unwrap(body: Any) -> Any:
    """Return the `data` payload of an envelope response, or the body itself.

    Args:
        body: A decoded JSON response body.
    Returns:
        `body["data"]` for the standard success envelope, else `body`.
    """
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def snapshot_world_state(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Digest the world_state node, splitting out the reset's own target properties.

    Args:
        rows: The world_state node rows from GET /v1/graph/nodes/world_state.
    Returns:
        Component→digest for each reset target property plus the remainder.
    """
    node = rows[0] if rows else {}
    out = {
        f"world_state.{prop}": digest(node.get(prop))
        for prop in RESET_TARGET_PROPERTIES
    }
    rest = {k: v for k, v in node.items() if k not in RESET_TARGET_PROPERTIES}
    out["world_state.other_properties"] = digest(rest)
    return out


def unknown_entries() -> tuple[str, ...]:
    """Return the `unknown:<store>` markers for every unobservable store."""
    return tuple(f"unknown:{name}" for name, _reason in UNOBSERVABLE_STORES)


def changed(before: dict[str, str], after: dict[str, str]) -> tuple[str, ...]:
    """Components whose digest differs between two snapshots.

    A key present in only one snapshot counts as changed — an appearing or
    vanishing component is a difference, not a missing measurement.

    Args:
        before: Earlier snapshot.
        after: Later snapshot.
    Returns:
        Sorted component names that differ.
    """
    keys = set(before) | set(after)
    return tuple(sorted(k for k in keys if before.get(k) != after.get(k)))


def classify(
    baseline: dict[str, str],
    mutated: dict[str, str],
    after_reset: dict[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split the components a scenario mutated into cleared and surviving.

    Only components the scenario actually changed carry information: a component
    the scenario never touched proves nothing about the reset either way, so it
    appears in neither list.

    Args:
        baseline: Snapshot before the mutating scenario ran.
        mutated: Snapshot after it ran, before the reset.
        after_reset: Snapshot after reset_world returned.
    Returns:
        (cleared, surviving) — cleared returned to their baseline digest,
        surviving did not.
    """
    touched = changed(baseline, mutated)
    cleared = tuple(c for c in touched if after_reset.get(c) == baseline.get(c))
    surviving = tuple(c for c in touched if after_reset.get(c) != baseline.get(c))
    return cleared, surviving
