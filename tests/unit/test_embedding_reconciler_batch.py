"""
Unit tests for SEV-29 embedding reconciler batch fix.

Verifies that the reconciler calls embed_batch once with the full list of stale
nodes rather than encoding one-at-a-time inside N individual upsert calls, and
that it issues a single batched Cypher to mark nodes as indexed instead of N
individual mark-indexed queries.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from npc_engine.retrieval.embedding import EmbeddingReconciler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_iter(records: list[dict]):
    """Return an async iterator over the given records."""

    async def _gen():
        for r in records:
            yield r

    return _gen()


def _make_graph_db_and_session(records: list[dict]) -> tuple[MagicMock, AsyncMock]:
    """Return (graph_db, session) mocks that yield the given stale-node records."""
    session = AsyncMock()

    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter(records))
    read_result.consume = AsyncMock()

    write_result = AsyncMock()
    write_result.consume = AsyncMock()

    # session.run: 1st = stale-node SELECT, 2nd = batch mark-indexed write
    session.run = AsyncMock(side_effect=[read_result, write_result])

    graph_db = MagicMock()
    graph_db.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
    graph_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
    return graph_db, session


def _make_records(n: int) -> list[dict]:
    return [
        {
            "id": f"char-{i}",
            "kind": "Character",
            "text": f"name-{i} warrior biography",
            "payload": {"id": f"char-{i}", "name": f"name-{i}"},
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconciler_calls_embed_batch_once():
    """embed_batch must be called exactly once with all node texts (not N individual encodes).

    Before the fix the reconciler called upsert N times, each of which called
    the sentence encoder once — giving N encode calls.  After the fix it must
    call embed_batch once with a list of all N texts.
    """
    n_nodes = 5
    records = _make_records(n_nodes)
    graph_db, session = _make_graph_db_and_session(records)

    embedding_index = AsyncMock()
    embedding_index.embed_batch = AsyncMock(
        return_value=[[0.0] * 384] * n_nodes
    )

    reconciler = EmbeddingReconciler(
        graph_db=graph_db,
        embedding_index=embedding_index,
        interval_seconds=60,
        batch_size=200,
    )

    stats = await reconciler.reconcile_once()

    # embed_batch called exactly once
    embedding_index.embed_batch.assert_called_once()
    texts_arg = embedding_index.embed_batch.call_args[0][0]
    assert len(texts_arg) == n_nodes

    assert stats["processed"] == n_nodes
    assert stats["failed"] == 0


@pytest.mark.asyncio
async def test_reconciler_batched_write_issues_at_most_2_session_runs():
    """After embedding, the reconciler must use at most 2 session.run calls.

    One for the stale-node SELECT and one for the batched mark-indexed SET.
    """
    n_nodes = 4
    records = _make_records(n_nodes)
    graph_db, session = _make_graph_db_and_session(records)

    embedding_index = AsyncMock()
    embedding_index.embed_batch = AsyncMock(
        return_value=[[0.1] * 384] * n_nodes
    )

    reconciler = EmbeddingReconciler(
        graph_db=graph_db,
        embedding_index=embedding_index,
        interval_seconds=60,
        batch_size=200,
    )

    await reconciler.reconcile_once()

    # At most 2 session.run calls: 1 SELECT + 1 batch SET
    assert session.run.call_count <= 2, (
        f"Expected at most 2 session.run calls for {n_nodes} nodes "
        f"but got {session.run.call_count}"
    )


@pytest.mark.asyncio
async def test_reconciler_returns_zero_when_no_stale_nodes():
    """reconcile_once returns processed=0, failed=0 when there are no stale nodes."""
    # When batch is empty there's only 1 session.run call (the SELECT) and it
    # returns no records — the write is skipped entirely.
    session = AsyncMock()
    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter([]))
    read_result.consume = AsyncMock()
    session.run = AsyncMock(return_value=read_result)

    graph_db = MagicMock()
    graph_db.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
    graph_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)

    embedding_index = AsyncMock()
    embedding_index.embed_batch = AsyncMock(return_value=[])

    reconciler = EmbeddingReconciler(
        graph_db=graph_db,
        embedding_index=embedding_index,
        interval_seconds=60,
    )

    stats = await reconciler.reconcile_once()

    assert stats["processed"] == 0
    assert stats["failed"] == 0
    # embed_batch should not be called when there are no stale nodes
    embedding_index.embed_batch.assert_not_called()
