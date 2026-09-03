"""
test_rag_scope_safety.py - The four P8 §8.1 safety tests for tier-B retrieval.

Pins DEC-209: the RAG filter is a SCOPE (the NPC's 1-hop subgraph, its location and
its faction, MINUS the events it already knows), never a whitelist and never an
unfiltered sweep, and filtering happens BEFORE ranking.

Does NOT: execute real Neo4j queries or run a real sentence encoder.

Dependencies injected: monkeypatched graph readers, a fake embedding index.
"""

import json

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.context import build_serialized_context
from npc_engine.retrieval.context import ContextItem
from npc_engine.retrieval.embedding import InMemoryVectorStore, VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens

from tests.unit.retrieval.test_context_builder import _patch_graph_calls


_KNOWN_EVENT_ID = "evt_known"
_SCOPE_EVENT_ID = "evt_in_scope"
_OUT_OF_SCOPE_ID = "evt_stranger"


class ScopedFakeIndex:
    """Fake embedding index that filters BEFORE it ranks, as DEC-209 requires."""

    def __init__(self, rows: list[VectorSearchResult]):
        self._rows = rows
        self.calls: list[frozenset[str] | None] = []

    async def search(self, query: str, top_k: int, filter_ids=None) -> list[VectorSearchResult]:
        self.calls.append(None if filter_ids is None else frozenset(filter_ids))
        rows = self._rows if filter_ids is None else [r for r in self._rows if r["id"] in filter_ids]
        return rows[:top_k]


def _llm_config() -> LLMConfig:
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
    )


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
        PROMPT_TOKEN_BUDGET=8000,
    )


def _rag_row(node_id: str) -> VectorSearchResult:
    return VectorSearchResult(
        id=node_id,
        score=0.9,
        payload={"id": node_id, "summary": f"summary of {node_id}", "severity": 50},
    )


def _known_event_item() -> ContextItem:
    return ContextItem(
        key="event:0:npc_1",
        text=json.dumps({"id": _KNOWN_EVENT_ID, "summary": "the thing I saw"}),
        tier="tierA",
        priority=89,
    )


def _patch_scope(monkeypatch, *, scope_ids: set[str], known_ids: set[str]) -> None:
    """Patch the RAG scope reader and the known-event reader together.

    They are patched as a pair on purpose: the scope is defined relative to the known
    set (DEC-209 subtracts one from the other), so setting either alone describes a
    world state that cannot occur.
    """

    async def fake_scope(session, *, npc_id):
        return set(scope_ids)

    async def fake_known(session, npc_id):
        return set(known_ids)

    monkeypatch.setattr("npc_engine.retrieval.context.context_graph_readers.get_rag_scope_ids_for_npc", fake_scope)
    monkeypatch.setattr("npc_engine.retrieval.context.context_graph_readers.get_known_event_ids_for_npc", fake_known)


async def _build(monkeypatch, index, *, tier_a_items=None) -> dict:
    serialized = await build_serialized_context(
        session=None,  # type: ignore[arg-type]
        settings=_settings(),
        llm_config=_llm_config(),
        embedding_index=index,
        npc_id="npc_1",
        player_message="what news",
        session_turns=[],
    )
    return json.loads(serialized)


@pytest.mark.asyncio
async def test_a_rag_hit_never_appears_in_npc_known_events(monkeypatch) -> None:
    _patch_graph_calls(monkeypatch, tier_a_items=[_known_event_item()])
    _patch_scope(monkeypatch, scope_ids={_SCOPE_EVENT_ID}, known_ids={_KNOWN_EVENT_ID})
    index = ScopedFakeIndex(rows=[_rag_row(_SCOPE_EVENT_ID)])

    payload = await _build(monkeypatch, index)

    whitelist = json.dumps(payload["npc_known_events"])
    assert _SCOPE_EVENT_ID not in whitelist
    assert _SCOPE_EVENT_ID in json.dumps(payload["retrieved_context"])


@pytest.mark.asyncio
async def test_an_npc_with_no_known_events_gets_no_rag_results_at_all(monkeypatch) -> None:
    """An empty scope means NO RAG, never 'all of it'.

    The NPC here knows nothing and neighbours nothing, so its scope is empty. The old
    `else` branch handed that NPC an unfiltered sweep of the whole store — 7 of 22 NPCs
    in the eval world, retrieving other characters' profiles as if they were their own.
    """
    _patch_graph_calls(monkeypatch)
    _patch_scope(monkeypatch, scope_ids=set(), known_ids=set())
    index = ScopedFakeIndex(rows=[_rag_row(_OUT_OF_SCOPE_ID)])

    payload = await _build(monkeypatch, index)

    assert payload["retrieved_context"] == []
    assert index.calls == [], "an empty scope must not reach the vector store at all"


@pytest.mark.asyncio
async def test_a_rag_hit_is_never_an_event_the_npc_already_knows(monkeypatch) -> None:
    """Tier B must carry what tier A structurally cannot, or it is charged twice."""
    _patch_graph_calls(monkeypatch, tier_a_items=[_known_event_item()])
    _patch_scope(
        monkeypatch,
        scope_ids={_KNOWN_EVENT_ID, _SCOPE_EVENT_ID},
        known_ids={_KNOWN_EVENT_ID},
    )
    index = ScopedFakeIndex(rows=[_rag_row(_KNOWN_EVENT_ID), _rag_row(_SCOPE_EVENT_ID)])

    payload = await _build(monkeypatch, index)

    assert index.calls == [frozenset({_SCOPE_EVENT_ID})]
    retrieved = json.dumps(payload["retrieved_context"])
    assert _SCOPE_EVENT_ID in retrieved
    assert _KNOWN_EVENT_ID not in retrieved


@pytest.mark.asyncio
async def test_a_filtered_search_over_a_mixed_store_returns_top_k_of_the_filtered_set() -> None:
    """Filtering must precede ranking.

    Rank-then-filter over a mixed store returns 0-1 rows: the top-k is consumed by the
    high-scoring majority the filter then discards. Ten in-scope items ranked below
    twenty out-of-scope ones must still yield a full top_k=5.
    """
    store = InMemoryVectorStore()
    for index in range(20):
        await store.upsert(f"out_{index}", [1.0, 0.0], {"kind": "out"})
    in_scope = set()
    for index in range(10):
        item_id = f"in_{index}"
        in_scope.add(item_id)
        await store.upsert(item_id, [0.5, 0.5], {"kind": "in"})

    results = await store.search(query_vector=[1.0, 0.0], top_k=5, filter_ids=in_scope)

    assert len(results) == 5
    assert {row["id"] for row in results} <= in_scope
