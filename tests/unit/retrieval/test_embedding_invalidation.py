"""
test_embedding_invalidation.py - Unit tests for invalidate_embedding_safely.

Does NOT: connect to vector stores or any external service.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.embedding_invalidation import invalidate_embedding_safely


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_index(*, raises: Exception | None = None) -> AsyncMock:
    index = AsyncMock()
    if raises is not None:
        index.invalidate = AsyncMock(side_effect=raises)
    else:
        index.invalidate = AsyncMock(return_value=None)
    return index


def _make_logger() -> MagicMock:
    return MagicMock(spec=logging.Logger)


# ---------------------------------------------------------------------------
# invalidate_embedding_safely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_calls_invalidate_once():
    index = _make_index()
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="npc_1",
        logger=logger,
        entity_label="Character",
    )

    index.invalidate.assert_awaited_once_with(item_id="npc_1")


@pytest.mark.asyncio
async def test_success_does_not_log_warning():
    index = _make_index()
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="npc_1",
        logger=logger,
        entity_label="Character",
    )

    logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_exception_does_not_propagate():
    index = _make_index(raises=RuntimeError("store unavailable"))
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="npc_1",
        logger=logger,
        entity_label="Character",
    )


@pytest.mark.asyncio
async def test_exception_logs_warning():
    index = _make_index(raises=RuntimeError("store unavailable"))
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="npc_1",
        logger=logger,
        entity_label="Character",
    )

    logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_exception_warning_contains_entity_label():
    index = _make_index(raises=ValueError("bad index"))
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="item_42",
        logger=logger,
        entity_label="Item",
    )

    warning_args = logger.warning.call_args[0]
    assert "Item" in warning_args


@pytest.mark.asyncio
async def test_exception_warning_contains_item_id():
    index = _make_index(raises=ValueError("bad index"))
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="item_42",
        logger=logger,
        entity_label="Item",
    )

    warning_args = logger.warning.call_args[0]
    assert "item_42" in warning_args


@pytest.mark.asyncio
async def test_different_entity_labels_use_correct_label():
    index = _make_index(raises=Exception("fail"))
    logger = _make_logger()

    await invalidate_embedding_safely(
        embedding_index=index,
        item_id="loc_1",
        logger=logger,
        entity_label="Location",
    )

    warning_args = logger.warning.call_args[0]
    assert "Location" in warning_args
