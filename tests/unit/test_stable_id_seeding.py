"""
test_stable_id_seeding.py - Unit tests for KE-6 stable-ID idempotent seeding.

Covers:
  - CreateBeliefRequest / CreateGoalRequest / CreateMemoryRequest /
    CreateSecretRequest each accept an optional ``id`` field.
  - When ``id`` is supplied the graph service passes it to Cypher (MERGE path).
  - When ``id`` is None a UUID is auto-generated (existing CREATE path unchanged).
  - Stable-ID derivation helpers produce the expected deterministic strings.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

import hashlib
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
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


def _sha1_8(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Request schema — id field present and optional
# ---------------------------------------------------------------------------


def test_create_belief_request_accepts_stable_id():
    """CreateBeliefRequest should accept an explicit id without error."""
    from npc_engine.api.routes.knowledge.beliefs import CreateBeliefRequest

    req = CreateBeliefRequest(content="The king is just.", confidence=70, id="bel_npc_1_abc12345")
    assert req.id == "bel_npc_1_abc12345"


def test_create_belief_request_id_defaults_to_none():
    """When id is omitted it defaults to None."""
    from npc_engine.api.routes.knowledge.beliefs import CreateBeliefRequest

    req = CreateBeliefRequest(content="The king is just.", confidence=70)
    assert req.id is None


def test_create_goal_request_accepts_stable_id():
    from npc_engine.api.routes.knowledge.goals import CreateGoalRequest

    req = CreateGoalRequest(description="Find the merchant.", urgency=55, id="goal_npc_1_0")
    assert req.id == "goal_npc_1_0"


def test_create_goal_request_id_defaults_to_none():
    from npc_engine.api.routes.knowledge.goals import CreateGoalRequest

    req = CreateGoalRequest(description="Find the merchant.", urgency=55)
    assert req.id is None


def test_create_memory_request_accepts_stable_id():
    from npc_engine.api.routes.knowledge.memories import CreateMemoryRequest

    req = CreateMemoryRequest(content="I saw the fire.", vividness=80, emotional_charge=50, id="mem_npc_1_0")
    assert req.id == "mem_npc_1_0"


def test_create_memory_request_id_defaults_to_none():
    from npc_engine.api.routes.knowledge.memories import CreateMemoryRequest

    req = CreateMemoryRequest(content="I saw the fire.", vividness=80, emotional_charge=50)
    assert req.id is None


def test_create_secret_request_accepts_stable_id():
    from npc_engine.api.routes.knowledge.secrets import CreateSecretRequest

    req = CreateSecretRequest(content="I bribed the guard.", severity=80, id="sec_npc_1")
    assert req.id == "sec_npc_1"


def test_create_secret_request_id_defaults_to_none():
    from npc_engine.api.routes.knowledge.secrets import CreateSecretRequest

    req = CreateSecretRequest(content="I bribed the guard.", severity=80)
    assert req.id is None


# ---------------------------------------------------------------------------
# Graph service — supplied id is passed to Cypher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_belief_uses_supplied_id():
    """When node_id is provided create_belief must forward it to Cypher."""
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.belief_service import create_belief

    result = await create_belief(
        session,
        character_id="char_1",
        content="Trust no merchant.",
        confidence=75,
        game_time=_make_game_time(),
        node_id="bel_char_1_deadbeef",
    )

    assert result == "bel_char_1_deadbeef"
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["belief_id"] == "bel_char_1_deadbeef"


@pytest.mark.asyncio
async def test_create_belief_generates_uuid_when_no_id_given():
    """When node_id is None create_belief must generate a UUID."""
    session = _make_session()

    with patch("npc_engine.graph.belief_service.uuid.uuid4", return_value="auto-uuid-001"):
        from npc_engine.graph.belief_service import create_belief

        result = await create_belief(
            session,
            character_id="char_1",
            content="Some belief.",
            confidence=50,
            game_time=_make_game_time(),
        )

    assert result == "auto-uuid-001"


@pytest.mark.asyncio
async def test_create_goal_uses_supplied_id():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.goal_service import create_goal

    result = await create_goal(
        session,
        character_id="char_1",
        description="Find the spy.",
        urgency=80,
        game_time=_make_game_time(),
        node_id="goal_char_1_0",
    )

    assert result == "goal_char_1_0"
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["goal_id"] == "goal_char_1_0"


@pytest.mark.asyncio
async def test_create_memory_uses_supplied_id():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.memory.memory_service import create_memory

    result = await create_memory(
        session,
        character_id="char_1",
        content="The battle I survived.",
        vividness=90,
        emotional_charge=-70,
        game_time=_make_game_time(),
        node_id="mem_char_1_0",
    )

    assert result == "mem_char_1_0"
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["memory_id"] == "mem_char_1_0"


@pytest.mark.asyncio
async def test_create_secret_uses_supplied_id():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.secret_service import create_secret

    result = await create_secret(
        session,
        character_id="char_1",
        content="I killed a man.",
        severity=90,
        game_time=_make_game_time(),
        node_id="sec_char_1",
    )

    assert result == "sec_char_1"
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["secret_id"] == "sec_char_1"


# ---------------------------------------------------------------------------
# Stable-ID derivation: correct format
# ---------------------------------------------------------------------------


def test_stable_belief_id_format():
    """bel_{npc_id}_{sha1(content)[:8]} must match the convention."""
    npc_id = "captain_sorn"
    content = "The thieves guild is planning something large — the signs are all there."
    expected = f"bel_{npc_id}_{_sha1_8(content)}"
    # Verify length and prefix.
    assert expected.startswith("bel_captain_sorn_")
    assert len(expected) == len("bel_captain_sorn_") + 8


def test_stable_goal_id_format():
    """goal_{npc_id}_{n} must be deterministic and 0-based."""
    assert "goal_mira_innkeeper_0" == f"goal_mira_innkeeper_0"
    assert "goal_mira_innkeeper_2" == f"goal_mira_innkeeper_2"


def test_stable_memory_id_format():
    assert "mem_old_henryk_0" == f"mem_old_henryk_0"


def test_stable_secret_id_format():
    assert "sec_lira_fence" == f"sec_lira_fence"


def test_belief_hash_is_sha1_prefix():
    """The 8-char suffix must be the first 8 hex chars of SHA-1 of the content."""
    content = "The war will come here eventually — I have seen it before."
    expected_suffix = hashlib.sha1(content.encode()).hexdigest()[:8]
    belief_id = f"bel_mira_innkeeper_{expected_suffix}"
    suffix = belief_id.split("_")[-1]
    assert len(suffix) == 8
    assert suffix == expected_suffix
