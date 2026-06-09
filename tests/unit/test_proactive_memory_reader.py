"""
Tests for ProactiveMemoryReader (EXP-10 slice-2).

All tests are fully mocked — no DB, no graph connections.

Covers:
  - memories returned sorted by vividness DESC
  - every returned memory has shared: False (waiver: memory.yaml has no shared field)
  - session.run called with correct parameters
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session(rows: list[dict]) -> MagicMock:
    """Build a mock AsyncSession that returns ``rows`` from session.run()."""
    mock_result = AsyncMock()
    mock_result.consume = AsyncMock()

    async def _aiter(_self=None):
        for row in rows:
            mock_record = MagicMock()
            mock_record.__getitem__ = lambda s, k: row[k]
            # Support dict(record) by providing keys()
            mock_record.keys = MagicMock(return_value=list(row.keys()))
            mock_record.data = MagicMock(return_value=row)
            # Make dict(record) work
            mock_record.__iter__ = MagicMock(return_value=iter(row.keys()))
            yield mock_record

    mock_result.__aiter__ = _aiter
    mock_result.single = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.run = AsyncMock(return_value=mock_result)
    return mock_session


def _make_rows(
    records: list[tuple[str, str, int]],
) -> list[dict]:
    """Build Neo4j-style row dicts from (memory_id, content, vividness) tuples."""
    return [
        {"memory_id": mid, "content": content, "vividness": vividness}
        for mid, content, vividness in records
    ]


# ---------------------------------------------------------------------------
# test_memory_reader_returns_memories_sorted_vividness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_reader_returns_memories_sorted_vividness() -> None:
    """ProactiveMemoryReader returns rows in vividness DESC order as supplied by Cypher."""
    from npc_engine.graph.proactive_memory_reader import ProactiveMemoryReader

    rows = _make_rows([
        ("m1", "first memory", 90),
        ("m2", "second memory", 70),
        ("m3", "third memory", 40),
    ])
    session = _make_mock_session(rows)

    reader = ProactiveMemoryReader()
    memories = await reader.get_unshared_memories(session, npc_id="npc_1", k=5)

    assert len(memories) == 3
    vividness_values = [m["vividness"] for m in memories]
    assert vividness_values == sorted(vividness_values, reverse=True), (
        f"Expected DESC order, got {vividness_values}"
    )
    assert memories[0]["memory_id"] == "m1"


# ---------------------------------------------------------------------------
# test_memory_reader_all_marked_unshared
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_reader_all_marked_unshared() -> None:
    """Every memory returned by ProactiveMemoryReader has shared=False (schema waiver)."""
    from npc_engine.graph.proactive_memory_reader import ProactiveMemoryReader

    rows = _make_rows([
        ("m1", "a memory", 80),
        ("m2", "another memory", 60),
    ])
    session = _make_mock_session(rows)

    reader = ProactiveMemoryReader()
    memories = await reader.get_unshared_memories(session, npc_id="npc_1", k=10)

    assert len(memories) == 2
    for mem in memories:
        assert mem.get("shared") is False, (
            f"Expected shared=False on all memories, got {mem.get('shared')!r}"
        )


# ---------------------------------------------------------------------------
# test_memory_reader_passes_npc_id_and_k_to_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_reader_passes_npc_id_and_k_to_session() -> None:
    """ProactiveMemoryReader passes npc_id and k to session.run()."""
    from npc_engine.graph.proactive_memory_reader import ProactiveMemoryReader

    session = _make_mock_session([])

    reader = ProactiveMemoryReader()
    await reader.get_unshared_memories(session, npc_id="captain_sorn", k=7)

    session.run.assert_awaited_once()
    call_kwargs = session.run.call_args
    # params are either positional or keyword — check the kwargs dict
    params = call_kwargs.kwargs if call_kwargs.kwargs else {}
    if not params:
        # fallback: positional args after the Cypher string
        args = call_kwargs.args
        if len(args) > 1 and isinstance(args[1], dict):
            params = args[1]
    assert params.get("character_id") == "captain_sorn" or "captain_sorn" in str(call_kwargs)
    assert params.get("k") == 7 or 7 in str(call_kwargs)


# ---------------------------------------------------------------------------
# test_memory_reader_returns_empty_list_when_no_rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_reader_returns_empty_list_when_no_rows() -> None:
    """ProactiveMemoryReader returns [] when the character has no memories."""
    from npc_engine.graph.proactive_memory_reader import ProactiveMemoryReader

    session = _make_mock_session([])

    reader = ProactiveMemoryReader()
    memories = await reader.get_unshared_memories(session, npc_id="npc_x", k=5)

    assert memories == []
