"""
Module: context_capture
Layer: evals (eval harness — not part of src/)
Purpose: HTTP helper that calls GET /v1/admin/debug/retrieval and returns a frozen
         tuple of RetrievedItem instances for embedding in GenerationRecords.
Dependencies: httpx, logging, retrieved_item
Used by: generate_runner

Note: The debug retrieval endpoint re-runs retrieval with session_turns=[] — the
returned context is an *approximation* of what produced each engine reply.
See retrieved_item module docstring for the full caveat.
"""

from __future__ import annotations

import logging

import httpx

from retrieved_item import RetrievedItem

_RETRIEVAL_ENDPOINT = "/v1/admin/debug/retrieval"
_logger = logging.getLogger(__name__)


def capture_retrieval_context(
    client: httpx.Client,
    base_url: str,
    npc_id: str,
    query: str,
) -> tuple[RetrievedItem, ...]:
    """Call GET /v1/admin/debug/retrieval and return context items as RetrievedItems.

    Returns an empty tuple on any HTTP or parsing error, but logs the failure with
    the NPC identity so a retrieval failure is distinguishable from a genuine empty
    context.  An empty return without a log entry is the bug this guards against.

    Args:
        client: Active httpx.Client with auth headers.
        base_url: NPC engine base URL.
        npc_id: NPC identifier.
        query: Player message used as the retrieval signal.
    Returns:
        Frozen tuple of RetrievedItem instances (empty on error).
    """
    try:
        resp = client.get(
            f"{base_url}{_RETRIEVAL_ENDPOINT}",
            params={"npc_id": npc_id, "query": query},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return tuple(
            RetrievedItem(
                key=item["key"],
                tier=item["tier"],
                priority=item["priority"],
                text=item["text"],
            )
            for item in data.get("context_items", [])
        )
    except Exception as exc:
        _logger.warning("retrieval_capture failed npc_id=%s query=%r: %s", npc_id, query[:40], exc)
        return ()
