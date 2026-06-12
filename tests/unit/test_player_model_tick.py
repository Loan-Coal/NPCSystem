"""
test_player_model_tick.py - Unit tests for the PlayerModelTick scheduler adapter (F1.4).

Drives run_tick with a fake co-location reader, a monkeypatched RelationReader, and a
captured upsert_player_model so no real Neo4j is touched. Verifies the adapter derives a
player model per co-located pair, persists it, and skips pairs with no RELATES_TO edge.

Dependencies injected: fake location reader; monkeypatched graph reader/writer.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.player_model import player_model_tick as mod
from npc_engine.engines.player_model.player_model_engine import PlayerModelEngine
from npc_engine.utils.errors import RelationEdgeNotFoundError


class _FakeLocationReader:
    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    async def get_collocated_pairs(self, session: Any) -> list[tuple[str, str]]:
        return self._pairs


class _FakeRelationReader:
    """Returns scalars for known pairs; raises for unknown ones (no edge)."""

    def __init__(self, session: Any) -> None:
        self._scalars = {("npc_a", "player_1"): {"trust": 70, "fear": 5, "affection": 20}}

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        key = (src_id, dst_id)
        if key not in self._scalars:
            raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
        return self._scalars[key]


@pytest.mark.asyncio
async def test_run_tick_derives_and_persists_per_pair(monkeypatch) -> None:
    """Each co-located pair with an edge yields one derived + persisted player model."""
    captured: list[dict[str, Any]] = []

    async def _fake_upsert(*, session, npc_id, player_id, perceived_trust, perceived_intent, tick):
        captured.append(
            {"npc_id": npc_id, "player_id": player_id, "perceived_trust": perceived_trust,
             "perceived_intent": perceived_intent, "tick": tick}
        )

    monkeypatch.setattr(mod, "RelationReader", _FakeRelationReader)
    monkeypatch.setattr(mod, "upsert_player_model", _fake_upsert)

    adapter = mod.PlayerModelTick(
        engine=PlayerModelEngine(),
        location_reader=_FakeLocationReader([("npc_a", "player_1")]),
    )
    result = await adapter.run_tick(session=object(), tick_id=12)

    assert len(result["player_models"]) == 1
    # composite trust = 70 + 20 - 5 = 85 (clamped 0..100) -> friendly (>= 60).
    assert captured == [
        {"npc_id": "npc_a", "player_id": "player_1", "perceived_trust": 85,
         "perceived_intent": "friendly", "tick": 12}
    ]


@pytest.mark.asyncio
async def test_run_tick_skips_pairs_without_edge(monkeypatch) -> None:
    """Pairs with no RELATES_TO edge are skipped, not persisted."""
    captured: list[dict[str, Any]] = []

    async def _fake_upsert(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(mod, "RelationReader", _FakeRelationReader)
    monkeypatch.setattr(mod, "upsert_player_model", _fake_upsert)

    adapter = mod.PlayerModelTick(
        engine=PlayerModelEngine(),
        location_reader=_FakeLocationReader([("npc_b", "player_1")]),  # unknown -> no edge
    )
    result = await adapter.run_tick(session=object(), tick_id=3)

    assert result["player_models"] == []
    assert captured == []
