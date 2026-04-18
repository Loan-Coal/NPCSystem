"""
embedding_invalidation.py - Shared helper for best-effort embedding invalidation.

Does NOT: decide business behavior when invalidation fails.

Dependencies injected: Embedding index instance and logger.
"""

from __future__ import annotations

import logging
from typing import Protocol


class EmbeddingInvalidationTarget(Protocol):
    """Protocol for objects supporting asynchronous embedding invalidation."""

    async def invalidate(self, item_id: str) -> None: ...


async def invalidate_embedding_safely(
    *,
    embedding_index: EmbeddingInvalidationTarget,
    item_id: str,
    logger: logging.Logger,
    entity_label: str,
) -> None:
    """Run invalidate as best effort and log warnings without raising."""

    try:
        await embedding_index.invalidate(item_id=item_id)
    except Exception as exc:
        logger.warning("embedding invalidate failed for %s=%s: %s", entity_label, item_id, exc)