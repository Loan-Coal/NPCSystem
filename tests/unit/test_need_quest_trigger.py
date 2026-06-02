"""
Tests for engines.quest_generation.need_quest_trigger and
graph.need_quest_queries.

Covers:
- No needs below threshold → 0 quests, no generate() calls
- NPC with need below threshold, no existing draft → quest created
- NPC already has draft quest → generation skipped (idempotency)
- Multiple NPCs with low needs → one quest per NPC
- Same NPC appears twice in need list → only one quest generated
- generate() raises ValueError (pacing suppression) → graceful skip
- DEFAULT_NEED_THRESHOLD constant value
- Custom threshold accepted by constructor
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.quest_generation.need_quest_trigger import (
    DEFAULT_NEED_THRESHOLD,
    NeedQuestTrigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generated_quest(quest_id: str = "quest-001") -> MagicMock:
    q = MagicMock()
    q.quest_id = quest_id
    return q


def _need_row(
    character_id: str = "mira_innkeeper",
    kind: str = "supply",
    level: int = 20,
    need_id: str = "need-001",
) -> dict:
    return {
        "character_id": character_id,
        "kind": kind,
        "level": level,
        "need_id": need_id,
        "decay_rate": 2,
    }


# ---------------------------------------------------------------------------
# No needs below threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_needs_returns_zero_quests() -> None:
    session = AsyncMock()
    engine = AsyncMock()

    with patch(
        "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
        new_callable=AsyncMock,
        return_value=[],
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=1)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# NPC with critical need, no existing draft → quest created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_critical_need_creates_quest() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-1")

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=[_need_row("mira_innkeeper", "supply", 10)],
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=5)

    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-1"]
    engine.generate.assert_awaited_once_with(
        session,
        quest_giver_id="mira_innkeeper",
    )


# ---------------------------------------------------------------------------
# NPC already has draft quest → idempotency skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_existing_draft_skips_generation() -> None:
    session = AsyncMock()
    engine = AsyncMock()

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=[_need_row("mira_innkeeper", "supply", 10)],
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=5)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []
    engine.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Multiple NPCs with low needs → one quest per NPC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_multiple_npcs_create_multiple_quests() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.side_effect = [
        _make_generated_quest("q-10"),
        _make_generated_quest("q-11"),
    ]

    needs = [
        _need_row("mira_innkeeper", "supply", 10, "n-1"),
        _need_row("aldric_merchant", "hunger", 15, "n-2"),
    ]

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=needs,
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=7)

    assert result["quests_created"] == 2
    assert set(result["quest_ids"]) == {"q-10", "q-11"}


# ---------------------------------------------------------------------------
# Same NPC appears twice (two low needs) → only one quest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_same_npc_twice_creates_one_quest() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-20")

    needs = [
        _need_row("mira_innkeeper", "supply", 10, "n-1"),
        _need_row("mira_innkeeper", "hunger", 5, "n-2"),
    ]

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=needs,
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=8)

    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-20"]
    engine.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# generate() raises ValueError (pacing suppression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_generate_value_error_is_skipped() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.side_effect = ValueError("Quest generation suppressed by pacing engine")

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=[_need_row("mira_innkeeper", "supply", 10)],
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=9)

    assert result["quests_created"] == 0
    assert result["quest_ids"] == []


# ---------------------------------------------------------------------------
# Mixed: one NPC has draft, one does not
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_mixed_draft_and_fresh_npc() -> None:
    session = AsyncMock()
    engine = AsyncMock()
    engine.generate.return_value = _make_generated_quest("q-30")

    needs = [
        _need_row("mira_innkeeper", "supply", 10, "n-1"),
        _need_row("aldric_merchant", "hunger", 15, "n-2"),
    ]

    async def _has_draft(session, character_id: str) -> bool:
        return character_id == "mira_innkeeper"

    with (
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.get_all_needs_below_threshold",
            new_callable=AsyncMock,
            return_value=needs,
        ),
        patch(
            "npc_engine.engines.quest_generation.need_quest_trigger.has_draft_quest",
            side_effect=_has_draft,
        ),
    ):
        trigger = NeedQuestTrigger(generation_engine=engine)
        result = await trigger.run_tick(session=session, tick_id=10)

    assert result["quests_created"] == 1
    assert result["quest_ids"] == ["q-30"]
    engine.generate.assert_awaited_once_with(
        session,
        quest_giver_id="aldric_merchant",
    )


# ---------------------------------------------------------------------------
# Constants and constructor
# ---------------------------------------------------------------------------


def test_default_need_threshold_is_reasonable() -> None:
    assert DEFAULT_NEED_THRESHOLD == 30


def test_constructor_accepts_custom_threshold() -> None:
    engine = AsyncMock()
    trigger = NeedQuestTrigger(generation_engine=engine, threshold=50)
    assert trigger._threshold == 50
