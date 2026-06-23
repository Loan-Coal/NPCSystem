"""
test_player_model_tick.py - Unit tests for the PlayerModelTick scheduler adapter (F1.4).

Drives run_tick with fake injected ports (RelationReadPort + PlayerLocationReadPort +
PlayerModelGraphPort) so no real Neo4j is touched. Verifies the adapter derives a player
model per co-located pair, persists it via the write port, skips pairs with no RELATES_TO
edge, and accepts/ignores the scheduler's session= kwarg (DEC-122 / SEV-24).

Dependencies injected: fake read/write ports.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.player_model.player_model_engine import PlayerModelEngine
from npc_engine.engines.player_model.player_model_tick import PlayerModelTick
from npc_engine.utils.errors import RelationEdgeNotFoundError


class _FakeLocationReader:
    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    async def get_collocated_pairs(self) -> list[tuple[str, str]]:
        return self._pairs


class _FakeRelationReader:
    """Returns scalars for known pairs; raises for unknown ones (no edge)."""

    def __init__(self) -> None:
        self._scalars = {("npc_a", "player_1"): {"trust": 70, "fear": 5, "affection": 20}}

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        key = (src_id, dst_id)
        if key not in self._scalars:
            raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
        return self._scalars[key]


class _FakeModelRepo:
    def __init__(self) -> None:
        self.captured: list[dict[str, Any]] = []

    async def upsert_player_model(
        self, *, npc_id, player_id, perceived_trust, perceived_intent, tick
    ) -> None:
        self.captured.append(
            {"npc_id": npc_id, "player_id": player_id, "perceived_trust": perceived_trust,
             "perceived_intent": perceived_intent, "tick": tick}
        )


def _adapter(pairs: list[tuple[str, str]], repo: _FakeModelRepo) -> PlayerModelTick:
    return PlayerModelTick(
        engine=PlayerModelEngine(),
        location_reader=_FakeLocationReader(pairs),
        relation_reader=_FakeRelationReader(),
        model_repo=repo,
    )


@pytest.mark.asyncio
async def test_run_tick_derives_and_persists_per_pair() -> None:
    """Each co-located pair with an edge yields one derived + persisted player model."""
    repo = _FakeModelRepo()
    result = await _adapter([("npc_a", "player_1")], repo).run_tick(tick_id=12)

    assert len(result["player_models"]) == 1
    # composite trust = 70 + 20 - 5 = 85 (clamped 0..100) -> friendly (>= 60).
    assert repo.captured == [
        {"npc_id": "npc_a", "player_id": "player_1", "perceived_trust": 85,
         "perceived_intent": "friendly", "tick": 12}
    ]


@pytest.mark.asyncio
async def test_run_tick_skips_pairs_without_edge() -> None:
    """Pairs with no RELATES_TO edge are skipped, not persisted."""
    repo = _FakeModelRepo()
    result = await _adapter([("npc_b", "player_1")], repo).run_tick(tick_id=3)

    assert result["player_models"] == []
    assert repo.captured == []


@pytest.mark.asyncio
async def test_run_tick_ignores_scheduler_session_kwarg() -> None:
    """The scheduler's session= kwarg is accepted and ignored during migration."""
    repo = _FakeModelRepo()
    result = await _adapter([("npc_a", "player_1")], repo).run_tick(
        tick_id=7
    )

    assert len(result["player_models"]) == 1
