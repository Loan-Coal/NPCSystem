"""
Module: embedding_refresh
Layer: engines
Purpose: Pair a handler's embedding INVALIDATION with the INSERT it has always implied,
         behind the flag that keeps an eval run's corpus frozen (DEC-210).
Does NOT: encode text, query the graph, or decide when a node is stale.
Dependencies injected: the embedding index, a corpus refresher, the flag, a logger.
Used by: engines.events.event_handler, engines.gossip.gossip_handler.

Why this exists
---------------
`invalidate_embedding_safely` next door is the delete half, and until DEC-208 it was the
ONLY half that existed anywhere in src/ — the handlers have been deleting entries that
were never inserted. The instrument and the product want different things here: an eval
run needs a corpus that cannot move (paired_arms interleaves arms inside one run, so
within-run drift lands unevenly across arms and no receipt field could recover the
distinction afterwards), and the product needs one that tracks the graph. Hence a flag,
and hence a LOG LINE whose absence is what verifies the OFF state — reading .env is not
verification, which DEC-206 established at the cost of a fixture diff.
"""

from __future__ import annotations

import logging
from typing import Protocol

from npc_engine.engines.embedding_invalidation import (
    EmbeddingInvalidationTarget,
    invalidate_embedding_safely,
)

__all__ = ["INCREMENTAL_UPSERT_LOG_EVENT", "CorpusRefresherProtocol", "refresh_embedding_safely"]

INCREMENTAL_UPSERT_LOG_EVENT = "vector_store.incremental_upsert"
"""The event name P10's preflight greps for during a probe turn.

Named as a constant so the gate and the emitter cannot drift apart: a preflight that
greps for a string a refactor renamed passes vacuously, which is the same failure mode
as trusting the flag.
"""


class CorpusRefresherProtocol(Protocol):
    """Re-embeds one node and writes it into the vector store."""

    async def refresh(self, node_id: str) -> bool:
        """Refresh one node's vector-store entry.

        Args:
            node_id: Identifier of the node to re-embed and upsert.

        Returns:
            True when an entry was written, False when the node carries no embedding.
        """


async def refresh_embedding_safely(
    *,
    embedding_index: EmbeddingInvalidationTarget,
    refresher: CorpusRefresherProtocol | None,
    item_id: str,
    enabled: bool,
    logger: logging.Logger,
    entity_label: str,
) -> None:
    """Invalidate one entry, then re-insert it when incremental upsert is enabled.

    Invalidation is UNCONDITIONAL — it is the existing behaviour and removing a stale
    vector is always correct. Only the insert is flagged, so turning the flag off leaves
    an eval run with exactly the boot-time corpus it started with.

    Best-effort throughout: corpus freshness must never fail an event emission or a
    gossip tick, so both halves log and continue.

    Args:
        embedding_index: Index supporting invalidate.
        refresher: Corpus refresher, or None when none is wired (invalidate-only).
        item_id: Identifier of the node whose entry is being refreshed.
        enabled: Settings.VECTOR_STORE_INCREMENTAL_UPSERT.
        logger: Caller's logger, so the line is attributed to the handler.
        entity_label: Human-readable entity type for log messages.
    """
    await invalidate_embedding_safely(
        embedding_index=embedding_index, item_id=item_id,
        logger=logger, entity_label=entity_label,
    )
    if not enabled or refresher is None:
        return
    await _upsert_refreshed_entry(
        refresher=refresher, item_id=item_id, logger=logger, entity_label=entity_label,
    )


async def _upsert_refreshed_entry(
    *,
    refresher: CorpusRefresherProtocol,
    item_id: str,
    logger: logging.Logger,
    entity_label: str,
) -> None:
    """Run the refresh and emit the line P10's preflight looks for; never raise."""
    try:
        refreshed = await refresher.refresh(item_id)
    except Exception as exc:  # noqa: BLE001 - best effort; the handler must still finish
        logger.warning(
            "%s failed for %s=%s: %s", INCREMENTAL_UPSERT_LOG_EVENT, entity_label, item_id, exc
        )
        return
    logger.info(
        "%s %s=%s refreshed=%s", INCREMENTAL_UPSERT_LOG_EVENT, entity_label, item_id, refreshed
    )
