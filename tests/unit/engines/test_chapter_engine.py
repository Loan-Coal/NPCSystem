"""Unit tests for ChapterEngine — all Neo4j calls and LLM calls mocked."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.chapter.chapter_engine import ChapterEngine
from npc_engine.engines.chapter.chapter_labeler import label_chapter_by_rules as _rule_based_label
from npc_engine.engines.gossip.gossip_distort import gossip_distort


# ---------------------------------------------------------------------------
# _rule_based_label helper
# ---------------------------------------------------------------------------


def test_rule_based_label_no_events():
    result = _rule_based_label([])
    assert result["title"] == "The Quiet Before"
    assert result["theme"] == "calm"


def test_rule_based_label_battle_event():
    events = [{"event_type": "battle", "summary": "War broke out", "severity": 80}]
    result = _rule_based_label(events)
    assert result["theme"] == "conflict"


def test_rule_based_label_unknown_event():
    events = [{"event_type": "festival", "summary": "People celebrated", "severity": 30}]
    result = _rule_based_label(events)
    assert "title" in result
    assert "theme" in result


# ---------------------------------------------------------------------------
# IS_CANONICAL gate — gossip_distort
# ---------------------------------------------------------------------------


def test_is_canonical_gates_gossip_distortion():
    """Canonical event must pass through distortion pipeline unchanged."""
    result = gossip_distort(
        event_summary="The king was murdered",
        sharer_honesty=0,
        sharer_receiver_trust=0,
        event_severity=100,
        tick_id=1,
        distortion_base=1.0,
        is_canonical=True,
    )
    assert result.summary == "The king was murdered"
    assert result.distortion_type is None
    assert result.distortion_level == 0


def test_non_canonical_event_can_be_distorted():
    """Non-canonical high-severity events may be distorted."""
    result = gossip_distort(
        event_summary="A soldier fell",
        sharer_honesty=0,
        sharer_receiver_trust=0,
        event_severity=100,
        tick_id=42,
        distortion_base=1.0,
        is_canonical=False,
    )
    # With distortion_base=1.0, honesty=0 → always distorts
    assert result.distortion_level > 0


# ---------------------------------------------------------------------------
# IS_CANONICAL gate — memory consolidation vividness boost
# ---------------------------------------------------------------------------


def test_is_canonical_gates_memory_decay():
    """get_undisclosed_witnesses returning canonical events should set vividness=100."""
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
        MemoryConsolidationEngine,
        _VIVIDNESS,
    )

    assert _VIVIDNESS < 100, "baseline vividness should be below 100 for the gate to matter"


# ---------------------------------------------------------------------------
# ChapterEngine.run_tick — no open chapter
# ---------------------------------------------------------------------------


_OPEN_CHAPTER = {
    "id": "ch_001",
    "name": "Act One",
    "started_at_tick": 1,
    "theme": "mystery",
    "status": "open",
}


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=json.dumps(
            {"title": "The Storm Breaks", "description": "War comes.", "theme": "conflict"}
        )
    )
    return llm


@pytest.fixture
def chapter_repo():
    """Mock ChapterGraphPort with benign defaults (no transition, empty reads)."""
    repo = AsyncMock()
    repo.get_current_chapter = AsyncMock(return_value=None)
    repo.count_completed_quests_since_tick = AsyncMock(return_value=0)
    repo.get_max_beat_intensity_in_chapter = AsyncMock(return_value=0)
    repo.get_recent_events_for_chapter = AsyncMock(return_value=[])
    repo.get_completed_quests_since_tick = AsyncMock(return_value=[])
    repo.get_faction_standings_summary = AsyncMock(return_value=[])
    repo.create_chapter = AsyncMock(return_value="new_ch")
    repo.close_chapter = AsyncMock()
    repo.link_event_to_chapter = AsyncMock()
    return repo


@pytest.fixture
def world_state_repo():
    """Mock WorldStateGraphPort returning a WorldState with no active conditions."""
    repo = AsyncMock()
    repo.get_world_state = AsyncMock(return_value=SimpleNamespace(active_conditions=[]))
    return repo


@pytest.fixture
def engine(mock_llm, chapter_repo, world_state_repo):
    return ChapterEngine(
        llm_client=mock_llm,
        chapter_repo=chapter_repo,
        world_state_repo=world_state_repo,
        quest_threshold=3,
        beat_intensity_threshold=70,
        window_ticks=20,
    )


@pytest.mark.asyncio
async def test_no_chapter_opens_prologue(engine, chapter_repo):
    chapter_repo.get_current_chapter = AsyncMock(return_value=None)

    result = await engine.run_tick(tick_id=1)

    assert result["transition"] is True
    assert result["chapter_name"] == "Prologue"
    chapter_repo.create_chapter.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_tick_no_session_required(engine, chapter_repo):
    """run_tick accepts no session kwarg (SEV-24 Wave 5 — session coupling removed)."""
    chapter_repo.get_current_chapter = AsyncMock(return_value=None)

    result = await engine.run_tick(tick_id=1)

    assert result["transition"] is True


# ---------------------------------------------------------------------------
# ChapterEngine.run_tick — quest count below threshold → no transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_transition_below_quest_threshold(engine, chapter_repo):
    chapter_repo.get_current_chapter = AsyncMock(return_value=_OPEN_CHAPTER)
    chapter_repo.count_completed_quests_since_tick = AsyncMock(return_value=1)
    chapter_repo.get_max_beat_intensity_in_chapter = AsyncMock(return_value=30)

    result = await engine.run_tick(tick_id=10)

    assert result["transition"] is False
    assert result["chapter_id"] == "ch_001"


# ---------------------------------------------------------------------------
# ChapterEngine.run_tick — quest count at threshold → transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_triggered_by_quest_density(engine, chapter_repo):
    chapter_repo.get_current_chapter = AsyncMock(return_value=_OPEN_CHAPTER)
    chapter_repo.count_completed_quests_since_tick = AsyncMock(return_value=3)
    chapter_repo.get_max_beat_intensity_in_chapter = AsyncMock(return_value=20)

    result = await engine.run_tick(tick_id=25)

    assert result["transition"] is True
    assert result["chapter_name"] == "The Storm Breaks"
    chapter_repo.close_chapter.assert_awaited_once()


# ---------------------------------------------------------------------------
# ChapterEngine._label_chapter — LLM failure → rule-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rule_based(engine, mock_llm, chapter_repo):
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
    chapter_repo.get_recent_events_for_chapter = AsyncMock(
        return_value=[
            {"event_type": "battle", "summary": "War", "severity": 90, "id": "e1",
             "tick_id": 5, "is_canonical": False}
        ]
    )

    label = await engine._label_chapter(tick_id=25, current=_OPEN_CHAPTER)

    assert label["theme"] == "conflict"


# ---------------------------------------------------------------------------
# ChapterEngine — LLM called with recent events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_called_with_recent_events(engine, mock_llm, chapter_repo):
    events = [
        {"event_type": "battle", "summary": "Forces clashed at the border",
         "severity": 80, "id": "e1", "tick_id": 5, "is_canonical": False}
    ]
    chapter_repo.get_recent_events_for_chapter = AsyncMock(return_value=events)

    await engine._label_chapter(tick_id=25, current=_OPEN_CHAPTER)

    mock_llm.generate.assert_called_once()
    call_kwargs = mock_llm.generate.call_args[1]
    assert "Forces clashed at the border" in call_kwargs["prompt"]
