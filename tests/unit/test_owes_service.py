"""
test_owes_service.py - Unit tests for graph.owes_service and graph.owes_queries.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock behaving like an AsyncSession with a transaction."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


# ---------------------------------------------------------------------------
# create_debt — happy path: no error raised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_debt_happy_path():
    session = _make_session()

    from npc_engine.graph.owes_service import create_debt

    await create_debt(
        session,
        debtor_id="char_a",
        creditor_id="char_b",
        kind="favor",
        magnitude="a night's lodging",
        due_by="",
    )

    session.begin_transaction.assert_awaited_once()
    tx = session.begin_transaction.return_value
    tx.run.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_debt — invalid kind raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_debt_invalid_kind_raises():
    session = _make_session()

    from npc_engine.graph.owes_service import create_debt

    with pytest.raises(ValueError, match="kind must be one of"):
        await create_debt(
            session,
            debtor_id="char_a",
            creditor_id="char_b",
            kind="promise",
            magnitude="5 gold",
        )


# ---------------------------------------------------------------------------
# get_debts_for_character — returns list ordered by due_by
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_debts_returns_list_for_character():
    fake_debtor_rows = [
        {"other_id": "char_b", "role": "debtor", "kind": "money", "magnitude": "10", "due_by": "day_1", "status": "pending"},
    ]
    fake_creditor_rows = [
        {"other_id": "char_c", "role": "creditor", "kind": "favor", "magnitude": "help", "due_by": "day_2", "status": "pending"},
    ]
    call_count = 0

    async def _mock_run(query: str, **kwargs):
        nonlocal call_count
        rows = fake_debtor_rows if call_count == 0 else fake_creditor_rows
        call_count += 1

        async def _records():
            for r in rows:
                yield r

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.owes_queries import get_debts_for_character

    results = await get_debts_for_character(session, character_id="char_a")
    assert len(results) == 2
    assert results[0]["due_by"] == "day_1"
    assert results[1]["due_by"] == "day_2"


# ---------------------------------------------------------------------------
# get_debts_for_character — no debts: returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_debts_returns_empty_list_when_none():
    async def _mock_run(*args, **kwargs):
        async def _records():
            return
            yield

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.owes_queries import get_debts_for_character

    results = await get_debts_for_character(session, character_id="char_empty")
    assert results == []


# ---------------------------------------------------------------------------
# get_debts_for_character — k limit is respected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_debts_passes_k_limit_to_query():
    captured: list[dict] = []

    async def _mock_run(query: str, **kwargs):
        captured.append(kwargs)

        async def _records():
            return
            yield

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.owes_queries import get_debts_for_character

    await get_debts_for_character(session, character_id="char_1", k=3)
    assert all(c["k"] == 3 for c in captured)


# ---------------------------------------------------------------------------
# get_debts_for_character_svc — delegates to query layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_debts_svc_delegates_to_query_layer():
    session = MagicMock()
    fake_result = [{"other_id": "char_b", "role": "debtor", "kind": "favor", "magnitude": "x", "due_by": "", "status": "pending"}]

    with patch(
        "npc_engine.graph.owes_service.get_debts_for_character",
        new=AsyncMock(return_value=fake_result),
    ) as mock_get:
        from npc_engine.graph.owes_service import get_debts_for_character_svc

        results = await get_debts_for_character_svc(session, character_id="char_a", k=3)

    mock_get.assert_awaited_once_with(session, character_id="char_a", k=3)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# update_debt_status — happy path: called with correct args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_debt_status_happy_path():
    session = _make_session()

    from npc_engine.graph.owes_service import update_debt_status

    await update_debt_status(
        session,
        debtor_id="char_a",
        creditor_id="char_b",
        status="fulfilled",
    )

    tx = session.begin_transaction.return_value
    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["status"] == "fulfilled"
    assert call_kwargs["debtor_id"] == "char_a"
    assert call_kwargs["creditor_id"] == "char_b"


# ---------------------------------------------------------------------------
# update_debt_status — invalid status raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_debt_status_invalid_status_raises():
    session = _make_session()

    from npc_engine.graph.owes_service import update_debt_status

    with pytest.raises(ValueError, match="status must be one of"):
        await update_debt_status(
            session,
            debtor_id="char_a",
            creditor_id="char_b",
            status="cancelled",
        )
