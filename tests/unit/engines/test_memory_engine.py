"""
test_memory_engine.py - Unit tests for MemoryEngine.

Covers:
- create_from_arousal: high-arousal path (memory created) and below-threshold skip.
- create_from_semantic_triggers: keyword-hit path (memory created) and mundane skip.

Does NOT: connect to Neo4j. The MemoryGraphPort is replaced with a recording fake.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.world.time_utils import TimePoint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeMemoryRepo:
    """Records create_memory calls and returns a configurable memory id."""

    def __init__(self, memory_id: str = "mem-fake") -> None:
        self._memory_id = memory_id
        self.create_calls: list[dict[str, Any]] = []

    async def create_memory(self, **kwargs: Any) -> str:
        self.create_calls.append(kwargs)
        return self._memory_id

    async def decay_all_vividness(self) -> int:
        return 0

    async def decay_all_vividness_weighted(self, *, base_decay: int, charge_divisor: int) -> int:
        return 0


def _make_game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


# ---------------------------------------------------------------------------
# create_from_arousal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_arousal_high_arousal_creates_memory():
    repo = _FakeMemoryRepo(memory_id="mem-arousal-001")
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_arousal(
        character_id="npc_1",
        arousal=80,
        content="A fierce battle erupted in the square",
        game_time=_make_game_time(),
    )
    assert result == "mem-arousal-001"
    assert len(repo.create_calls) == 1


@pytest.mark.asyncio
async def test_create_from_arousal_low_arousal_returns_none():
    repo = _FakeMemoryRepo()
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_arousal(
        character_id="npc_1",
        arousal=40,
        content="Someone walked past the tavern",
        game_time=_make_game_time(),
    )
    assert result is None
    assert repo.create_calls == []


# ---------------------------------------------------------------------------
# create_from_semantic_triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_fires_on_keyword():
    repo = _FakeMemoryRepo(memory_id="mem-001")
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_semantic_triggers(
        character_id="npc_1",
        content="The king ordered an execution at dawn",
        emotional_charge=10,
        game_time=_make_game_time(),
    )
    assert result == "mem-001"
    assert len(repo.create_calls) == 1


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_skips_mundane():
    repo = _FakeMemoryRepo()
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_semantic_triggers(
        character_id="npc_1",
        content="The merchant sold bread in the market",
        emotional_charge=5,
        game_time=_make_game_time(),
    )
    assert result is None
    assert repo.create_calls == []


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_case_insensitive():
    """Keyword match must be case-insensitive."""
    repo = _FakeMemoryRepo(memory_id="mem-002")
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_semantic_triggers(
        character_id="npc_2",
        content="Reports of BETRAYAL spread across the city",
        emotional_charge=20,
        game_time=_make_game_time(),
    )
    assert result == "mem-002"
    assert len(repo.create_calls) == 1


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_uses_semantic_vividness():
    """Memory must be formed with _SEMANTIC_VIVIDNESS (60), not the arousal vividness (80)."""
    repo = _FakeMemoryRepo(memory_id="mem-003")
    engine = MemoryEngine(memory_repo=repo)
    await engine.create_from_semantic_triggers(
        character_id="npc_3",
        content="A plague swept through the northern villages",
        emotional_charge=15,
        game_time=_make_game_time(),
    )
    assert repo.create_calls[0]["vividness"] == 60


@pytest.mark.asyncio
async def test_create_from_semantic_triggers_forwards_emotional_charge():
    """The emotional_charge passed in must reach create_memory unchanged."""
    repo = _FakeMemoryRepo(memory_id="mem-004")
    engine = MemoryEngine(memory_repo=repo)
    await engine.create_from_semantic_triggers(
        character_id="npc_4",
        content="The coup toppled the old regime at midnight",
        emotional_charge=42,
        game_time=_make_game_time(),
    )
    assert repo.create_calls[0]["emotional_charge"] == 42


# ---------------------------------------------------------------------------
# EXP-211: subject_player_id population
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_tagged_with_subject_player_id():
    """When a player_id is supplied to create_from_arousal, it must be forwarded to
    create_memory as subject_player_id so the memory is player-scoped."""
    repo = _FakeMemoryRepo(memory_id="mem-p001")
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_arousal(
        character_id="npc_1",
        arousal=85,
        content="The player revealed a shocking secret",
        game_time=_make_game_time(),
        player_id="player_hero",
    )
    assert result == "mem-p001"
    assert repo.create_calls[0].get("subject_player_id") == "player_hero", (
        "subject_player_id must be forwarded to create_memory when player_id is given"
    )


@pytest.mark.asyncio
async def test_memory_without_player_id_has_no_subject_player_id():
    """When player_id is not supplied, subject_player_id must be absent (None) in create_memory."""
    repo = _FakeMemoryRepo(memory_id="mem-p002")
    engine = MemoryEngine(memory_repo=repo)
    await engine.create_from_arousal(
        character_id="npc_2",
        arousal=90,
        content="The dragon attacked the village",
        game_time=_make_game_time(),
    )
    assert repo.create_calls[0].get("subject_player_id") is None, (
        "subject_player_id must be None when no player_id is given"
    )


# ---------------------------------------------------------------------------
# EXP-212: compute_salience
# ---------------------------------------------------------------------------


def test_compute_salience_forgettable_below_threshold():
    """A memory with low recall_count, low vividness, low charge is forgettable."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=5, emotional_charge=5, recall_count=0)
    assert salience < settings.MEMORY_FORGET_THRESHOLD, (
        "Memory with low vividness/charge/recall should be below forget threshold"
    )
    assert is_forgettable(
        salience=salience,
        never_forget=False,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    ), "Low-salience memory with never_forget=False should be forgettable"


def test_never_forget_memory_not_forgettable():
    """A memory with never_forget=True must never be forgettable, regardless of salience."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=0, emotional_charge=0, recall_count=0)
    assert not is_forgettable(
        salience=salience,
        never_forget=True,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    ), "A never_forget memory must never be marked forgettable"


def test_high_salience_memory_not_forgettable():
    """A memory with high vividness and charge must exceed the threshold."""
    from npc_engine.engines.memory.memory_engine import compute_salience, is_forgettable
    from npc_engine.config import Settings

    settings = Settings(API_KEY_SECRET="npc_dev_secret_2026_alpha")  # type: ignore[call-arg]
    salience = compute_salience(vividness=90, emotional_charge=80, recall_count=10)
    assert salience >= settings.MEMORY_FORGET_THRESHOLD, (
        "High vividness/charge/recall memory must exceed forget threshold"
    )
    assert not is_forgettable(
        salience=salience,
        never_forget=False,
        threshold=settings.MEMORY_FORGET_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# EXP-214: create_from_commitment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_commitment_sets_kind():
    """create_from_commitment must call create_memory with kind='commitment'."""
    repo = _FakeMemoryRepo(memory_id="mem-commit-001")
    engine = MemoryEngine(memory_repo=repo)
    result = await engine.create_from_commitment(
        character_id="npc_sorn",
        content="Player promised to deliver the scroll by dawn",
        game_time=_make_game_time(),
        player_id="player_hero",
    )
    assert result == "mem-commit-001"
    assert repo.create_calls[0]["kind"] == "commitment", (
        "create_from_commitment must pass kind='commitment' to create_memory"
    )


@pytest.mark.asyncio
async def test_create_from_commitment_sets_subject_player_id():
    """create_from_commitment must forward player_id as subject_player_id."""
    repo = _FakeMemoryRepo(memory_id="mem-commit-002")
    engine = MemoryEngine(memory_repo=repo)
    await engine.create_from_commitment(
        character_id="npc_sorn",
        content="Player swore to protect the village",
        game_time=_make_game_time(),
        player_id="player_hero",
    )
    assert repo.create_calls[0].get("subject_player_id") == "player_hero"


@pytest.mark.asyncio
async def test_create_from_commitment_uses_full_vividness():
    """Commitment memories must be formed at maximum vividness (100)."""
    repo = _FakeMemoryRepo(memory_id="mem-commit-003")
    engine = MemoryEngine(memory_repo=repo)
    await engine.create_from_commitment(
        character_id="npc_sorn",
        content="I will help you recover the artefact",
        game_time=_make_game_time(),
        player_id="player_hero",
    )
    assert repo.create_calls[0]["vividness"] == 100, (
        "Commitment memories must be formed with vividness=100 (they are never forgotten)"
    )
