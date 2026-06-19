"""
embedding_invalidation.py - Shared helper for best-effort embedding invalidation.
Layer: engines
Purpose: Shared helper for best-effort embedding invalidation.

Does NOT: decide business behavior when invalidation fails.

Dependencies injected: Embedding index instance and logger.
"""

from __future__ import annotations

import logging
from typing import Protocol


class EmbeddingInvalidationTarget(Protocol):
    """Protocol for objects supporting asynchronous embedding invalidation."""

    async def invalidate(self, item_id: str) -> None:
        """Remove the embedding entry for the given item.

        Args:
            item_id: Unique identifier of the item whose embedding should be invalidated.
        """


async def invalidate_embedding_safely(
    *,
    embedding_index: EmbeddingInvalidationTarget,
    item_id: str,
    logger: logging.Logger,
    entity_label: str,
) -> None:
    """Invalidate one embedding entry without raising on failure.

    Args:
        embedding_index: Index supporting the invalidate protocol.
        item_id: Identifier of the item to invalidate.
        logger: Logger used to emit a warning if invalidation fails.
        entity_label: Human-readable entity type for log messages (e.g. ``"Character"``).
    """

    try:
        await embedding_index.invalidate(item_id=item_id)
    except Exception as exc:
        logger.warning("embedding invalidate failed for %s=%s: %s", entity_label, item_id, exc)