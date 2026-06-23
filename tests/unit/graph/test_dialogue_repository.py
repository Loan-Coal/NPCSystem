"""
test_dialogue_repository.py - Unit tests for Neo4jDialogueRepository.

Verifies session-per-call pattern and first-contact retry logic.
Does NOT: connect to a real Neo4j instance. Uses a fake GraphDB and session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.repositories.dialogue_repository import Neo4jDialogueRepository
from npc_engine.utils.errors import RelationEdgeNotFoundError


class _FakeSession:
    """Lightweight fake AsyncSession."""

    def __init__(self) -> None:
        self.run = AsyncMock()


class _FakeGraphDB:
    """Fake GraphDB that yields a fresh _FakeSession each call."""

    def __init__(self, session: _FakeSession | None = None) -> None:
        self._session = session or _FakeSession()
        self.connect = AsyncMock()
        self.sessions_opened: int = 0

    @asynccontextmanager
    async def get_session(self):
        self.sessions_opened += 1
        yield self._session


@pytest.fixture()
def fake_db() -> _FakeGraphDB:
    return _FakeGraphDB()


@pytest.fixture()
def repo(fake_db: _FakeGraphDB) -> Neo4jDialogueRepository:
    return Neo4jDialogueRepository(fake_db)


# ---------------------------------------------------------------------------
# get_npc_archetype
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_npc_archetype_opens_one_session(repo, fake_db) -> None:
    with patch("npc_engine.graph.repositories.dialogue_repository.get_npc_archetype", AsyncMock(return_value="guard")):
        result = await repo.get_npc_archetype("captain_sorn")
    assert result == "guard"
    assert fake_db.sessions_opened == 1


# ---------------------------------------------------------------------------
# get_npc_voice_descriptor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_npc_voice_descriptor_opens_one_session(repo, fake_db) -> None:
    with patch("npc_engine.graph.repositories.dialogue_repository.get_npc_voice_descriptor", AsyncMock(return_value="deep")):
        result = await repo.get_npc_voice_descriptor("captain_sorn")
    assert result == "deep"
    assert fake_db.sessions_opened == 1


# ---------------------------------------------------------------------------
# get_world_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_world_state_opens_one_session(repo, fake_db) -> None:
    world_stub = MagicMock()
    with patch("npc_engine.graph.repositories.dialogue_repository._get_world_state", AsyncMock(return_value=world_stub)):
        result = await repo.get_world_state("world")
    assert result is world_stub
    assert fake_db.sessions_opened == 1


# ---------------------------------------------------------------------------
# apply_relation_deltas — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_relation_deltas_happy_path(repo, fake_db) -> None:
    from npc_engine.engines.dialogue.dialogue_models import RelationDeltas

    deltas = RelationDeltas(trust=3, affection=0)
    with patch("npc_engine.graph.repositories.dialogue_repository.apply_relation_delta", AsyncMock()) as mock_write:
        await repo.apply_relation_deltas(
            npc_id="mira_innkeeper",
            player_id="player_1",
            relation_deltas=deltas,
            cause_id="test",
            tick_id=1,
            settings=MagicMock(),
        )
    mock_write.assert_awaited_once()
    assert fake_db.sessions_opened == 1


# ---------------------------------------------------------------------------
# apply_relation_deltas — first-contact retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_relation_deltas_first_contact_retry(repo) -> None:
    """On RelationEdgeNotFoundError: ensure_relation_edge + retry apply_relation_delta."""
    from npc_engine.engines.dialogue.dialogue_models import RelationDeltas

    deltas = RelationDeltas(trust=5, affection=0)
    apply_calls: list[str] = []

    async def _apply_delta(**_kwargs):
        if not apply_calls:
            apply_calls.append("first")
            raise RelationEdgeNotFoundError(src_id="mira_innkeeper", dst_id="player_1")
        apply_calls.append("retry")

    with patch("npc_engine.graph.repositories.dialogue_repository.apply_relation_delta", side_effect=_apply_delta), \
         patch("npc_engine.graph.repositories.dialogue_repository.ensure_relation_edge", AsyncMock()) as mock_ensure:
        await repo.apply_relation_deltas(
            npc_id="mira_innkeeper",
            player_id="player_1",
            relation_deltas=deltas,
            cause_id="test",
            tick_id=1,
            settings=MagicMock(),
        )

    assert apply_calls == ["first", "retry"], "Expected one initial failure then one retry"
    mock_ensure.assert_awaited_once()


# ---------------------------------------------------------------------------
# set_routine_override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_routine_override_opens_one_session(repo, fake_db) -> None:
    with patch("npc_engine.graph.repositories.dialogue_repository._set_routine_override", AsyncMock()) as mock_set:
        await repo.set_routine_override(character_id="mira_innkeeper", location_id="home", expires_at_tick=50)
    mock_set.assert_awaited_once_with(
        session=fake_db._session,
        character_id="mira_innkeeper",
        location_id="home",
        expires_at_tick=50,
    )
    assert fake_db.sessions_opened == 1
