"""
test_profile_tier_knobs.py - P8 §8.5: tiers, slots and slot caps as A/B knobs.

The rule that makes these knobs measurable rather than confounding: assembly may vary,
SCHEMA MUST NOT. Every declared slot keeps emitting its empty default when its tier is
switched off, or two arms differ in the SHAPE of the JSON the model sees and the delta
is schema drift rather than content.

Does NOT: execute real Neo4j queries.

Dependencies injected: monkeypatched graph readers, a fake embedding index.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context import ContextItem, build_serialized_context
from npc_engine.retrieval.embedding import VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens
from npc_engine.schema.retrieval_profile_models import RetrievalProfile

from tests.unit.retrieval.test_context_builder import _patch_graph_calls


class FakeIndex:
    def __init__(self, rows: list[VectorSearchResult]) -> None:
        self._rows = rows
        self.calls = 0

    async def search(self, query: str, top_k: int, filter_ids=None) -> list[VectorSearchResult]:
        self.calls += 1
        return self._rows[:top_k]


def _llm_config(profiles: dict[str, RetrievalProfile] | None = None) -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.5",
        compression_prompt_version="v1.5",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30, severity=0.20, proximity=0.20, relation=0.20, quest=0.10,
        ),
        retrieval_profiles=profiles or {},
    )


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=8000,
    )


def _profile(**overrides) -> RetrievalProfile:
    base = dict(
        weight_profile=None, rag_top_k=5, graph_rag_top_k=5, events_limit=5,
        cross_encoder_enabled=False, skip_rag=False,
    )
    base.update(overrides)
    return RetrievalProfile(**base)


def _rag_rows(count: int) -> list[VectorSearchResult]:
    return [
        VectorSearchResult(
            id=f"evt_{index}", score=0.9,
            payload={"id": f"evt_{index}", "summary": f"a retrieved fact {index}"},
        )
        for index in range(count)
    ]


async def _build(monkeypatch, profile: RetrievalProfile, index: FakeIndex) -> dict:
    _patch_graph_calls(monkeypatch)
    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config({"arm": profile}),
        embedding_index=index,
        npc_id="npc_1",
        player_message="what news",
        session_turns=[],
        retrieval_profile="arm",
    )
    return json.loads(serialized)


@pytest.mark.asyncio
async def test_disabling_tier_b_stops_retrieval_without_changing_the_schema(monkeypatch) -> None:
    index = FakeIndex(_rag_rows(4))

    with_b = await _build(monkeypatch, _profile(), FakeIndex(_rag_rows(4)))
    without_b = await _build(monkeypatch, _profile(enabled_tiers={"tier0", "tierA"}), index)

    assert with_b["retrieved_context"], "control arm must actually carry tier B"
    assert without_b["retrieved_context"] == []
    assert index.calls == 0, "a disabled tier must not pay for the retrieval either"
    assert set(with_b) == set(without_b), "schema must be identical across arms"


@pytest.mark.asyncio
async def test_a_disabled_slot_empties_its_key_but_keeps_it(monkeypatch) -> None:
    payload = await _build(monkeypatch, _profile(disabled_slots={"rag:"}), FakeIndex(_rag_rows(4)))

    assert "retrieved_context" in payload
    assert payload["retrieved_context"] == []


@pytest.mark.asyncio
async def test_a_slot_cap_bounds_one_slot_without_bounding_the_others(monkeypatch) -> None:
    """RAG payloads are whole node property dicts.

    'Measure the ceiling' must not mean 'let one slot define it' — `embedding` is
    stripped at serialization by NON_PROMPT_NODE_FIELDS, `biography` is not.
    """
    fat = [
        VectorSearchResult(
            id="evt_fat", score=0.9,
            payload={"id": "evt_fat", "summary": "a very long retrieved account. " * 200},
        )
    ]

    uncapped = await _build(monkeypatch, _profile(), FakeIndex(list(fat)))
    capped = await _build(monkeypatch, _profile(slot_cap_overrides={"rag:": 40}), FakeIndex(list(fat)))

    assert len(json.dumps(capped["retrieved_context"])) < len(json.dumps(uncapped["retrieved_context"]))
    assert capped["npc"]["emotion"] == uncapped["npc"]["emotion"], "other slots untouched"


def test_the_default_profile_enables_every_tier_and_disables_no_slot() -> None:
    """Introducing the knobs must not change the default path."""
    profile = _profile()

    assert profile.enabled_tiers == frozenset({"tier0", "tierA", "tierB", "tierC"})
    assert profile.disabled_slots == frozenset()
    assert profile.slot_cap_overrides == {}


def test_the_knobs_accept_yaml_shaped_input() -> None:
    """A declared arm arrives from llm_config.yaml as lists and dicts, not frozensets."""
    profile = RetrievalProfile(
        weight_profile=None, rag_top_k=5, graph_rag_top_k=5, events_limit=5,
        cross_encoder_enabled=False, skip_rag=False,
        enabled_tiers=["tier0", "tierA"], disabled_slots=["rag:"],
        slot_cap_overrides={"rag:": 400},
    )

    assert profile.enabled_tiers == frozenset({"tier0", "tierA"})
    assert profile.disabled_slots == frozenset({"rag:"})


def test_the_default_profile_caps_the_rag_slot() -> None:
    """P8 §8.5: cap `rag:` even during the unconstrained measurement window.

    Tier B has carried zero items on every run ever recorded, so there is no
    byte-identical default behaviour to preserve — and an uncapped slot whose payload is
    a whole node property dict would define the ceiling P5 exists to measure.
    """
    from npc_engine.schema.retrieval_profile_models import (
        DEFAULT_RAG_SLOT_CAP_TOKENS,
        RAG_SLOT_KEY,
        build_default_profile,
    )

    profile = build_default_profile(rag_top_k=5, cross_encoder_enabled=False)

    assert profile.slot_cap_overrides == {RAG_SLOT_KEY: DEFAULT_RAG_SLOT_CAP_TOKENS}
