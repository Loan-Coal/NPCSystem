"""
test_degradation.py - Unit tests for graceful dialogue degradation tiers.

Does NOT: call live LLM or Neo4j services.

Dependencies injected: coroutine factories and fake canned YAML directory.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from api.schemas import ActionModel, DialogueResponse, FacialExpressionModel, RelationDeltas
from engines.dialogue.degradation import (
    DEGRADATION_METRIC,
    execute_with_degradation,
)
from utils.metrics import get_counter_value, reset_metrics_registry


def _make_response(text: str = "hello") -> DialogueResponse:
    return DialogueResponse(
        npc_response=text,
        relation_deltas=RelationDeltas(),
        action=ActionModel(),
        facial_expression=FacialExpressionModel(),
    )


async def _ok(text: str = "ok") -> DialogueResponse:
    return _make_response(text)


async def _raises(exc: Exception) -> DialogueResponse:
    raise exc


@pytest.fixture(autouse=True)
def reset_metrics():
    reset_metrics_registry()
    yield


@pytest.fixture()
def canned_dir(tmp_path: Path) -> Path:
    data = {"archetype": "default", "responses": ["I need a moment."]}
    (tmp_path / "default.yaml").write_text(yaml.dump(data), encoding="utf-8")
    guard_data = {"archetype": "guard", "responses": ["Move along."]}
    (tmp_path / "guard.yaml").write_text(yaml.dump(guard_data), encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_full_tier_succeeds(canned_dir: Path) -> None:
    response, level = await execute_with_degradation(
        full_factory=lambda: _ok("full response"),
        graph_only_factory=lambda: _ok("graph only"),
        archetype="default",
        canned_dir=canned_dir,
        full_timeout=5.0,
        graph_only_timeout=5.0,
    )
    assert level == "full"
    assert response.npc_response == "full response"
    assert get_counter_value(DEGRADATION_METRIC, labels={"level": "full"}) == 1.0
    assert get_counter_value(DEGRADATION_METRIC, labels={"level": "graph_only"}) == 0.0


@pytest.mark.asyncio
async def test_llm_timeout_falls_back_to_graph_only(canned_dir: Path) -> None:
    async def full_timeout_factory() -> DialogueResponse:
        await asyncio.sleep(10.0)
        return _make_response()

    response, level = await execute_with_degradation(
        full_factory=full_timeout_factory,
        graph_only_factory=lambda: _ok("graph only response"),
        archetype="default",
        canned_dir=canned_dir,
        full_timeout=0.05,
        graph_only_timeout=5.0,
    )
    assert level == "graph_only"
    assert response.npc_response == "graph only response"
    assert get_counter_value(DEGRADATION_METRIC, labels={"level": "graph_only"}) == 1.0


@pytest.mark.asyncio
async def test_neo4j_error_falls_back_to_canned(canned_dir: Path) -> None:
    neo4j_exc = RuntimeError("Neo4j connection refused")

    response, level = await execute_with_degradation(
        full_factory=lambda: _raises(neo4j_exc),
        graph_only_factory=lambda: _raises(neo4j_exc),
        archetype="guard",
        canned_dir=canned_dir,
        full_timeout=5.0,
        graph_only_timeout=5.0,
    )
    assert level == "canned"
    assert response.npc_response == "Move along."
    assert get_counter_value(DEGRADATION_METRIC, labels={"level": "canned"}) == 1.0


@pytest.mark.asyncio
async def test_canned_falls_back_to_default_archetype(canned_dir: Path) -> None:
    exc = OSError("db down")

    response, level = await execute_with_degradation(
        full_factory=lambda: _raises(exc),
        graph_only_factory=lambda: _raises(exc),
        archetype="unknown_archetype",
        canned_dir=canned_dir,
        full_timeout=5.0,
        graph_only_timeout=5.0,
    )
    assert level == "canned"
    assert response.npc_response == "I need a moment."


@pytest.mark.asyncio
async def test_canned_hardcoded_fallback_when_no_yaml(tmp_path: Path) -> None:
    exc = OSError("db down")

    response, level = await execute_with_degradation(
        full_factory=lambda: _raises(exc),
        graph_only_factory=lambda: _raises(exc),
        archetype="default",
        canned_dir=tmp_path,
        full_timeout=5.0,
        graph_only_timeout=5.0,
    )
    assert level == "canned"
    assert response.npc_response == "I need a moment to think."


@pytest.mark.asyncio
async def test_both_tiers_timeout_falls_back_to_canned(canned_dir: Path) -> None:
    async def slow() -> DialogueResponse:
        await asyncio.sleep(10.0)
        return _make_response()

    response, level = await execute_with_degradation(
        full_factory=slow,
        graph_only_factory=slow,
        archetype="default",
        canned_dir=canned_dir,
        full_timeout=0.05,
        graph_only_timeout=0.05,
    )
    assert level == "canned"
    assert get_counter_value(DEGRADATION_METRIC, labels={"level": "canned"}) == 1.0


@pytest.mark.asyncio
async def test_relation_deltas_are_zero_for_canned(canned_dir: Path) -> None:
    exc = RuntimeError("db down")

    response, level = await execute_with_degradation(
        full_factory=lambda: _raises(exc),
        graph_only_factory=lambda: _raises(exc),
        archetype="default",
        canned_dir=canned_dir,
        full_timeout=5.0,
        graph_only_timeout=5.0,
    )
    assert level == "canned"
    assert response.relation_deltas.trust == 0
    assert response.relation_deltas.fear == 0
    assert response.relation_deltas.affection == 0
