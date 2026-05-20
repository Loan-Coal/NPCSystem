"""
Tests for graph.trait_service and graph.trait_queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.trait_service import add_trait, get_traits_svc, remove_trait


# ---------------------------------------------------------------------------
# add_trait
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_trait_calls_session_run() -> None:
    session = AsyncMock()
    await add_trait(session, character_id="char-1", trait_id="trait-brave", intensity=80)
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["character_id"] == "char-1"
    assert kwargs["trait_id"] == "trait-brave"
    assert kwargs["intensity"] == 80
    assert kwargs["is_secret"] is False


@pytest.mark.asyncio
async def test_add_trait_passes_is_secret_flag() -> None:
    session = AsyncMock()
    await add_trait(
        session,
        character_id="char-2",
        trait_id="trait-coward",
        intensity=60,
        is_secret=True,
    )
    _, kwargs = session.run.call_args
    assert kwargs["is_secret"] is True


@pytest.mark.asyncio
async def test_add_trait_returns_none() -> None:
    session = AsyncMock()
    result = await add_trait(session, character_id="char-1", trait_id="trait-x", intensity=50)
    assert result is None


# ---------------------------------------------------------------------------
# get_traits_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_traits_svc_delegates_to_query() -> None:
    expected = [{"trait_id": "trait-brave", "name": "Brave", "intensity": 80, "is_secret": False}]
    with patch(
        "npc_engine.graph.trait_service.get_traits",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_traits_svc(session, "char-1")
        mock_fn.assert_called_once_with(session, character_id="char-1")
        assert result == expected


@pytest.mark.asyncio
async def test_get_traits_svc_returns_empty_list() -> None:
    with patch(
        "npc_engine.graph.trait_service.get_traits",
        new_callable=AsyncMock,
        return_value=[],
    ):
        session = AsyncMock()
        result = await get_traits_svc(session, "char-nobody")
        assert result == []


# ---------------------------------------------------------------------------
# remove_trait
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_trait_calls_session_run() -> None:
    session = AsyncMock()
    await remove_trait(session, character_id="char-1", trait_id="trait-brave")
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["character_id"] == "char-1"
    assert kwargs["trait_id"] == "trait-brave"


@pytest.mark.asyncio
async def test_remove_trait_returns_none() -> None:
    session = AsyncMock()
    result = await remove_trait(session, character_id="char-1", trait_id="trait-x")
    assert result is None


# ---------------------------------------------------------------------------
# Trait context integration — subgraph_retriever assembles traits into Tier A
# ---------------------------------------------------------------------------


def test_assemble_tier_a_context_includes_top_5_traits() -> None:
    from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context

    traits = [
        {"name": "Brave", "intensity": 90, "is_secret": False},
        {"name": "Clever", "intensity": 75, "is_secret": False},
        {"name": "Greedy", "intensity": 60, "is_secret": True},
        {"name": "Loyal", "intensity": 55, "is_secret": False},
        {"name": "Stubborn", "intensity": 40, "is_secret": False},
        {"name": "Timid", "intensity": 10, "is_secret": False},
    ]
    items = assemble_tier_a_context(
        npc_id="npc-1",
        character_bundle={"character": {"id": "npc-1"}, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
        traits=traits,
    )
    trait_item = next((i for i in items if i.key == "traits"), None)
    assert trait_item is not None
    assert trait_item.priority == 83
    import json
    data = json.loads(trait_item.text)
    assert len(data) == 5
    # Sorted descending by intensity — Timid (10) should be excluded
    names = [d["name"] for d in data]
    assert "Timid" not in names
    assert data[0]["name"] == "Brave"


def test_assemble_tier_a_context_no_traits_skips_item() -> None:
    from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context

    items = assemble_tier_a_context(
        npc_id="npc-1",
        character_bundle={"character": {"id": "npc-1"}, "relations": []},
        events=[],
        location_id=None,
        location_context=None,
        traits=[],
    )
    keys = [i.key for i in items]
    assert "traits" not in keys
