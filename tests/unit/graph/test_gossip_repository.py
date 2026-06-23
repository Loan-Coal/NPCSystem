"""
Unit tests for Neo4jGossipRepository.

Verifies that the adapter opens a session per call and correctly delegates
to the underlying graph functions, including the CAS retry in log_gossip.
Uses a fake GraphDB that returns a single reusable mock session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.repositories.gossip_repository import Neo4jGossipRepository


# ---------------------------------------------------------------------------
# Fake GraphDB
# ---------------------------------------------------------------------------


def _make_graph_db(session: AsyncMock) -> MagicMock:
    """Return a fake GraphDB whose get_session() yields the given mock session."""
    graph_db = MagicMock()
    graph_db.connect = AsyncMock()

    @asynccontextmanager
    async def _get_session():
        yield session

    graph_db.get_session = _get_session
    return graph_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_gossip_pairs_delegates() -> None:
    """fetch_gossip_pairs must call graph fetch_gossip_pairs and return its result."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    expected = [{"a": {"id": "npc1"}, "b": {"id": "npc2"}}]

    with patch(
        "npc_engine.graph.repositories.gossip_repository.fetch_gossip_pairs",
        new=AsyncMock(return_value=expected),
    ) as mock_fetch:
        result = await repo.fetch_gossip_pairs()

    mock_fetch.assert_called_once_with(session)
    assert result == expected


@pytest.mark.asyncio
async def test_get_goals_for_character_delegates() -> None:
    """get_goals_for_character must delegate to graph layer with correct kwargs."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    expected = [{"id": "g1", "target_id": "npc2"}]

    with patch(
        "npc_engine.graph.repositories.gossip_repository.get_goals_for_character",
        new=AsyncMock(return_value=expected),
    ) as mock_goals:
        result = await repo.get_goals_for_character("npc1", k=10, status_filter="active")

    mock_goals.assert_called_once_with(session, character_id="npc1", k=10, status_filter="active")
    assert result == expected


@pytest.mark.asyncio
async def test_fetch_known_node_ids_delegates() -> None:
    """fetch_known_node_ids must delegate and return node id set."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    expected: set[str] = {"event-1", "event-2"}

    with patch(
        "npc_engine.graph.repositories.gossip_repository.fetch_known_node_ids",
        new=AsyncMock(return_value=expected),
    ) as mock_fn:
        result = await repo.fetch_known_node_ids("npc1")

    mock_fn.assert_called_once_with(session, character_id="npc1")
    assert result == expected


@pytest.mark.asyncio
async def test_select_batch_event_trust_delegates() -> None:
    """select_batch_event_trust must delegate with the pairs list."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    pairs = [{"sharer_id": "a", "receiver_id": "b"}]
    expected = [{"sharer_id": "a", "receiver_id": "b", "event_id": "e1", "trust": 60}]

    with patch(
        "npc_engine.graph.repositories.gossip_repository.select_batch_event_trust",
        new=AsyncMock(return_value=expected),
    ) as mock_fn:
        result = await repo.select_batch_event_trust(pairs=pairs)

    mock_fn.assert_called_once_with(session, pairs=pairs)
    assert result == expected


@pytest.mark.asyncio
async def test_write_batch_knowledge_propagation_delegates() -> None:
    """write_batch_knowledge_propagation must delegate the writes list."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    writes = [{"receiver_id": "b", "event_id": "e1"}]

    with patch(
        "npc_engine.graph.repositories.gossip_repository.write_batch_knowledge_propagation",
        new=AsyncMock(),
    ) as mock_fn:
        await repo.write_batch_knowledge_propagation(writes=writes)

    mock_fn.assert_called_once_with(session, writes=writes)


@pytest.mark.asyncio
async def test_create_rumor_delegates() -> None:
    """create_rumor must delegate with all keyword args and return the id."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with patch(
        "npc_engine.graph.repositories.gossip_repository.create_rumor",
        new=AsyncMock(return_value="rumor-1"),
    ) as mock_fn:
        result = await repo.create_rumor(
            content="war",
            origin_event_id="evt-1",
            created_at_tick=5,
            severity=80,
            is_fabricated=False,
        )

    mock_fn.assert_called_once_with(
        session,
        content="war",
        origin_event_id="evt-1",
        created_at_tick=5,
        severity=80,
        is_fabricated=False,
    )
    assert result == "rumor-1"


@pytest.mark.asyncio
async def test_believe_rumor_delegates() -> None:
    """believe_rumor must delegate with all keyword args."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with patch(
        "npc_engine.graph.repositories.gossip_repository.believe_rumor",
        new=AsyncMock(),
    ) as mock_fn:
        await repo.believe_rumor(
            character_id="npc1",
            rumor_id="rumor-1",
            confidence=70,
            tick=5,
            from_character_id="npc2",
        )

    mock_fn.assert_called_once_with(
        session,
        character_id="npc1",
        rumor_id="rumor-1",
        confidence=70,
        tick=5,
        from_character_id="npc2",
    )


@pytest.mark.asyncio
async def test_select_gossip_secret_delegates() -> None:
    """select_gossip_secret must delegate and return the secret dict or None."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))
    expected = {"secret_id": "s1", "severity": 90}

    with patch(
        "npc_engine.graph.repositories.gossip_repository.select_gossip_secret",
        new=AsyncMock(return_value=expected),
    ) as mock_fn:
        result = await repo.select_gossip_secret("npc1")

    mock_fn.assert_called_once_with(session, sharer_id="npc1")
    assert result == expected


@pytest.mark.asyncio
async def test_log_gossip_writes_on_first_successful_cas() -> None:
    """log_gossip must read, append, then CAS-write; return after first success."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with (
        patch(
            "npc_engine.graph.repositories.gossip_repository.fetch_relation_log",
            new=AsyncMock(return_value='[]'),
        ),
        patch(
            "npc_engine.graph.repositories.gossip_repository.update_relation_log",
            new=AsyncMock(return_value=True),
        ) as mock_update,
    ):
        await repo.log_gossip(src_id="a", dst_id="b", tick_id=1, trust_delta=1)

    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_log_gossip_retries_on_cas_conflict() -> None:
    """log_gossip must retry up to 3 times on CAS conflict (update_relation_log=False)."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with (
        patch(
            "npc_engine.graph.repositories.gossip_repository.fetch_relation_log",
            new=AsyncMock(return_value='[]'),
        ),
        patch(
            "npc_engine.graph.repositories.gossip_repository.update_relation_log",
            new=AsyncMock(return_value=False),
        ) as mock_update,
    ):
        await repo.log_gossip(src_id="a", dst_id="b", tick_id=1, trust_delta=1)

    assert mock_update.call_count == 3


@pytest.mark.asyncio
async def test_log_gossip_skips_missing_edge() -> None:
    """log_gossip must return silently when fetch_relation_log returns None."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with (
        patch(
            "npc_engine.graph.repositories.gossip_repository.fetch_relation_log",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "npc_engine.graph.repositories.gossip_repository.update_relation_log",
            new=AsyncMock(),
        ) as mock_update,
    ):
        await repo.log_gossip(src_id="a", dst_id="b", tick_id=1, trust_delta=1)

    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_propagate_secret_delegates_undistorted() -> None:
    """propagate_secret must write KNOWS_SECRET with knowledge_state='knows' when not distorted."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with patch(
        "npc_engine.graph.repositories.gossip_repository.write_secret_propagation",
        new=AsyncMock(),
    ) as mock_fn:
        await repo.propagate_secret(
            receiver_id="npc2",
            secret_id="s1",
            source_character_id="npc1",
            tick_id=5,
            distorted=False,
        )

    call_kwargs = mock_fn.call_args
    assert call_kwargs.kwargs["knowledge_state"] == "knows"


@pytest.mark.asyncio
async def test_propagate_secret_delegates_distorted() -> None:
    """propagate_secret must write KNOWS_SECRET with knowledge_state='rumor' when distorted."""
    session = AsyncMock()
    repo = Neo4jGossipRepository(_make_graph_db(session))

    with patch(
        "npc_engine.graph.repositories.gossip_repository.write_secret_propagation",
        new=AsyncMock(),
    ) as mock_fn:
        await repo.propagate_secret(
            receiver_id="npc2",
            secret_id="s1",
            source_character_id="npc1",
            tick_id=5,
            distorted=True,
        )

    call_kwargs = mock_fn.call_args
    assert call_kwargs.kwargs["knowledge_state"] == "rumor"
