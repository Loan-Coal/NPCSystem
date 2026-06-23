"""
test_item_service.py - Unit tests for graph.item_service and action_resolver ownership check.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.world.time_utils import TimePoint


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


def _make_game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=5, time_of_day="morning")


# ---------------------------------------------------------------------------
# create_item — happy path: returns UUID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_item_returns_uuid_string():
    session = _make_session()
    with patch("npc_engine.graph.economy.item_service.uuid.uuid4", return_value="item-uuid-001"):
        from npc_engine.graph.economy.item_service import create_item

        item_id = await create_item(
            session,
            character_id="char_1",
            name="Iron Sword",
            description="A simple iron sword.",
            value=50,
            rarity="common",
            type_="weapon",
            is_unique=False,
            game_time=_make_game_time(),
        )

    assert item_id == "item-uuid-001"
    session.begin_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_item_passes_correct_params_to_cypher():
    session = _make_session()
    tx = session.begin_transaction.return_value

    with patch("npc_engine.graph.economy.item_service.uuid.uuid4", return_value="item-uuid-002"):
        from npc_engine.graph.economy.item_service import create_item

        await create_item(
            session,
            character_id="char_2",
            name="Golden Ring",
            description="A ring of legend.",
            value=500,
            rarity="legendary",
            type_="misc",
            is_unique=True,
            game_time=_make_game_time(),
        )

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["item_id"] == "item-uuid-002"
    assert call_kwargs["name"] == "Golden Ring"
    assert call_kwargs["value"] == 500
    assert call_kwargs["is_unique"] == "true"
    assert call_kwargs["character_id"] == "char_2"


# ---------------------------------------------------------------------------
# get_items_for_character — returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_for_character_returns_list():
    fake_records = [
        {"id": "i1", "name": "Iron Sword", "description": "A sword.", "value": 50,
         "rarity": "common", "type": "weapon", "is_unique": "false", "properties": ""},
        {"id": "i2", "name": "Health Potion", "description": "Heals HP.", "value": 10,
         "rarity": "common", "type": "consumable", "is_unique": "false", "properties": ""},
    ]

    async def _mock_run(*args, **kwargs):
        async def _records():
            for r in fake_records:
                yield r

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.economy.item_queries import get_items_for_character

    results = await get_items_for_character(session, character_id="char_1")
    assert len(results) == 2
    assert results[0]["name"] == "Iron Sword"


# ---------------------------------------------------------------------------
# get_item_by_id — returns dict or None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item_by_id_returns_item_dict():
    fake_record = {"id": "i1", "name": "Iron Sword", "description": "A sword.", "value": 50,
                   "rarity": "common", "type": "weapon", "is_unique": "false", "properties": ""}

    result_mock = AsyncMock()
    result_mock.single = AsyncMock(return_value=fake_record)

    session = MagicMock()
    session.run = AsyncMock(return_value=result_mock)

    from npc_engine.graph.economy.item_queries import get_item_by_id

    item = await get_item_by_id(session, item_id="i1")
    assert item is not None
    assert item["name"] == "Iron Sword"


@pytest.mark.asyncio
async def test_get_item_by_id_returns_none_when_not_found():
    result_mock = AsyncMock()
    result_mock.single = AsyncMock(return_value=None)

    session = MagicMock()
    session.run = AsyncMock(return_value=result_mock)

    from npc_engine.graph.economy.item_queries import get_item_by_id

    item = await get_item_by_id(session, item_id="nonexistent")
    assert item is None


# ---------------------------------------------------------------------------
# get_items_for_character — empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_returns_empty_list_when_none():
    async def _mock_run(*args, **kwargs):
        async def _records():
            return
            yield

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.economy.item_queries import get_items_for_character

    results = await get_items_for_character(session, character_id="char_empty")
    assert results == []


# ---------------------------------------------------------------------------
# transfer_ownership — calls detach then attach Cypher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transfer_ownership_calls_detach_and_attach():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.economy.item_service import transfer_ownership

    await transfer_ownership(
        session,
        item_id="i1",
        from_character_id="char_1",
        to_character_id="char_2",
        game_time=_make_game_time(),
    )

    assert tx.run.await_count == 2
    first_kwargs = tx.run.call_args_list[0].kwargs
    second_kwargs = tx.run.call_args_list[1].kwargs
    assert first_kwargs["character_id"] == "char_1"
    assert first_kwargs["item_id"] == "i1"
    assert second_kwargs["character_id"] == "char_2"
    assert second_kwargs["item_id"] == "i1"


# ---------------------------------------------------------------------------
# check_give_item_ownership — action resolver ownership check
# ---------------------------------------------------------------------------


def test_give_item_allowed_when_npc_owns_item():
    from npc_engine.engines.dialogue.action_resolver import check_give_item_ownership
    from npc_engine.engines.dialogue.dialogue_models import ActionModel

    action = ActionModel(type="give_item", target_id="player_1", parameters={"item_name": "Iron Sword"})
    owned = [{"id": "i1", "name": "Iron Sword"}]

    result = check_give_item_ownership(action, owned)
    assert result.type == "give_item"


def test_give_item_ignored_when_npc_does_not_own_item():
    from npc_engine.engines.dialogue.action_resolver import check_give_item_ownership
    from npc_engine.engines.dialogue.dialogue_models import ActionModel

    action = ActionModel(type="give_item", target_id="player_1", parameters={"item_name": "Magic Staff"})
    owned = [{"id": "i1", "name": "Iron Sword"}]

    result = check_give_item_ownership(action, owned)
    assert result.type == "none"
    assert result.parameters.get("ignored_reason") == "npc_does_not_own_item"


def test_non_give_item_actions_pass_through_unchanged():
    from npc_engine.engines.dialogue.action_resolver import check_give_item_ownership
    from npc_engine.engines.dialogue.dialogue_models import ActionModel

    action = ActionModel(type="speak", target_id=None, parameters={"text": "Hello"})
    result = check_give_item_ownership(action, [])
    assert result.type == "speak"


# ---------------------------------------------------------------------------
# create_item — boundary value and type edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_item_value_zero():
    """value=0 is accepted without error."""
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.economy.item_service import create_item

    await create_item(
        session,
        character_id="char_1",
        name="Worthless Trinket",
        description="Nobody wants this.",
        value=0,
        rarity="common",
        type_="misc",
        is_unique=False,
        game_time=_make_game_time(),
    )

    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["value"] == 0


@pytest.mark.asyncio
async def test_create_item_not_unique_serializes_false_string():
    """is_unique=False must be serialized as the string 'false' for the Cypher query."""
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.economy.item_service import create_item

    await create_item(
        session,
        character_id="char_1",
        name="Common Blade",
        description="Mass produced.",
        value=10,
        rarity="common",
        type_="weapon",
        is_unique=False,
        game_time=_make_game_time(),
    )

    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["is_unique"] == "false"


# ---------------------------------------------------------------------------
# get_items_for_character_svc — delegates to query layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_svc_delegates_to_query_layer():
    session = MagicMock()
    fake_items = [{"id": "i1", "name": "Sword", "value": 50}]

    with patch(
        "npc_engine.graph.economy.item_service.get_items_for_character",
        new_callable=AsyncMock,
        return_value=fake_items,
    ) as mock_get:
        from npc_engine.graph.economy.item_service import get_items_for_character_svc

        result = await get_items_for_character_svc(session, character_id="char_1")

    mock_get.assert_awaited_once_with(session, character_id="char_1")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_items_svc_returns_empty_for_character_with_no_items():
    with patch(
        "npc_engine.graph.economy.item_service.get_items_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from npc_engine.graph.economy.item_service import get_items_for_character_svc

        result = await get_items_for_character_svc(MagicMock(), character_id="no_items_char")

    assert result == []
