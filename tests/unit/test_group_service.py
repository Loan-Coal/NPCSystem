"""
Unit tests for graph.group_service and graph.group_queries.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.group_service import (
    add_member,
    create_group,
    dissolve_group,
    get_groups_for_character_svc,
    get_members_svc,
    remove_member,
)


# ---------------------------------------------------------------------------
# create_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_group_returns_uuid():
    session = AsyncMock()
    group_id = await create_group(
        session,
        name="Test Clique",
        kind="clique",
        cohesion=10,
        is_secret=False,
        formed_at_tick=1,
    )
    assert isinstance(group_id, str) and len(group_id) == 36
    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_create_group_passes_home_location():
    session = AsyncMock()
    await create_group(
        session,
        name="Crew HQ",
        kind="crew",
        cohesion=50,
        is_secret=True,
        formed_at_tick=5,
        home_location_id="loc-abc",
    )
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["home_location_id"] == "loc-abc"


@pytest.mark.asyncio
async def test_create_group_no_home_location_defaults_to_none():
    session = AsyncMock()
    await create_group(
        session,
        name="Fellowship",
        kind="fellowship",
        cohesion=80,
        is_secret=False,
        formed_at_tick=10,
    )
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["home_location_id"] is None


# ---------------------------------------------------------------------------
# add_member / remove_member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member_runs_query_with_correct_params():
    session = AsyncMock()
    await add_member(
        session,
        group_id="g-1",
        character_id="c-1",
        role="member",
        joined_at_tick=2,
        commitment=50,
    )
    session.run.assert_called_once()
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["group_id"] == "g-1"
    assert call_kwargs["character_id"] == "c-1"
    assert call_kwargs["role"] == "member"
    assert call_kwargs["commitment"] == 50


@pytest.mark.asyncio
async def test_remove_member_runs_query():
    session = AsyncMock()
    await remove_member(session, group_id="g-1", character_id="c-1")
    session.run.assert_called_once()
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["group_id"] == "g-1"
    assert call_kwargs["character_id"] == "c-1"


# ---------------------------------------------------------------------------
# dissolve_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dissolve_group_sets_correct_tick():
    session = AsyncMock()
    await dissolve_group(session, group_id="g-1", tick=99)
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["tick"] == 99
    assert call_kwargs["group_id"] == "g-1"


# ---------------------------------------------------------------------------
# get_groups_for_character_svc / get_members_svc (patch query functions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_groups_for_character_returns_list():
    expected = [{"id": "g-1", "name": "Clique", "kind": "clique", "role": "member"}]
    with patch(
        "npc_engine.graph.group_service.get_groups_for_character",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_groups_for_character_svc(session, character_id="c-1")
        mock_fn.assert_called_once_with(session, character_id="c-1", include_dissolved=False)
        assert result == expected


@pytest.mark.asyncio
async def test_get_members_returns_list():
    expected = [{"character_id": "c-1", "character_name": "Alice", "role": "member"}]
    with patch(
        "npc_engine.graph.group_service.get_members",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_members_svc(session, group_id="g-1")
        mock_fn.assert_called_once_with(session, group_id="g-1")
        assert result == expected
