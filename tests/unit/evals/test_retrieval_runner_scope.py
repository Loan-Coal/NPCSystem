"""
Module: tests.unit.evals.test_retrieval_runner_scope
Layer: test (unit)
Purpose: The retrieval eval harness must retrieve the way the ENGINE retrieves — inside
         the DEC-209 scope, at the profile's top-k — or it is not measuring the engine.
Dependencies: pytest; evals.retrieval_runner
Used by: make test (pytest discovery)

WHAT WAS WRONG
`_retrieve_ranked_ids` called `embedding_index.search(query=query, top_k=k)` with NO
`filter_ids`. Post-P8 that is an UNFILTERED SWEEP of the whole vector store — the exact
defect DEC-209 removed from the engine, still live in the instrument measuring it. And
`run_eval` took no profile at all, while `--retrieval-profile` was accepted, recorded into
retrieval_metrics.json, and consulted by nothing: an arm claiming a variant it never ran,
which is precisely what DEC-194 exists to prevent.

Does NOT: hit Neo4j, encode text, or read the case fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

import retrieval_ranking  # noqa: E402
import retrieval_runner  # noqa: E402
from retrieval_runner import RetrievalCase  # noqa: E402

from npc_engine.schema.retrieval_profile_models import RetrievalProfile  # noqa: E402

_NPC = "captain_sorn"
_KNOWN = {"northern_war_begins"}
_SCOPE = {"lira_fence", "vex_spymaster", "northern_war_begins"}


def _profile(**overrides: Any) -> RetrievalProfile:
    base: dict[str, Any] = {
        "weight_profile": None,
        "rag_top_k": 5,
        "graph_rag_top_k": 5,
        "events_limit": 5,
        "cross_encoder_enabled": False,
        "skip_rag": False,
    }
    base.update(overrides)
    return RetrievalProfile(**base)


class _RecordingIndex:
    """Records every search call so the test can assert what the harness asked for."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def search(
        self, *, query: str, top_k: int, filter_ids: Any = None
    ) -> list[dict[str, Any]]:
        self.calls.append({"query": query, "top_k": top_k, "filter_ids": filter_ids})
        return [{"id": "lira_fence"}, {"id": "vex_spymaster"}]


@pytest.fixture
def graph(monkeypatch: pytest.MonkeyPatch):
    """Stub the two graph reads the harness makes; return handles to vary them."""
    state = {"known": set(_KNOWN), "scope": set(_SCOPE)}

    async def fake_known(*, session: Any, npc_id: str) -> set[str]:
        return set(state["known"])

    async def fake_scope(*, session: Any, npc_id: str) -> set[str]:
        return set(state["scope"])

    monkeypatch.setattr(retrieval_ranking.engine_adapter, "known_event_ids", fake_known)
    monkeypatch.setattr(retrieval_ranking.engine_adapter, "rag_scope_ids", fake_scope)
    return state


async def _rank(index: _RecordingIndex, profile: RetrievalProfile, k: int = 5) -> list[str]:
    return await retrieval_ranking.retrieve_ranked_ids(
        npc_id=_NPC,
        query="what do you know about the northern war?",
        k=k,
        profile=profile,
        embedding_index=index,
        graph_session=None,
    )


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_harness_never_searches_the_whole_store(graph) -> None:
    """The defect this module exists for. An unfiltered search over a mixed store ranks
    every Character, Event and Location in the corpus against the query."""
    index = _RecordingIndex()
    await _rank(index, _profile())
    assert index.calls, "the harness did not search at all"
    assert index.calls[0]["filter_ids"] is not None, (
        "the harness searched with filter_ids=None — an unfiltered sweep of the store"
    )


@pytest.mark.asyncio
async def test_the_scope_excludes_events_the_npc_already_knows(graph) -> None:
    """DEC-209: tier B retrieves what tier A cannot reach. An event already carried as a
    tier-A `event:` item must not be re-ranked and charged twice."""
    index = _RecordingIndex()
    await _rank(index, _profile())
    assert _KNOWN.isdisjoint(index.calls[0]["filter_ids"])
    assert set(index.calls[0]["filter_ids"]) == _SCOPE - _KNOWN


@pytest.mark.asyncio
async def test_an_empty_scope_means_no_search_and_never_the_whole_store(graph) -> None:
    """`else None` gave an empty scope the run of the store, and 7 of 22 eval-world NPCs
    know zero events. Empty scope means NO RAG."""
    graph["scope"] = set()
    index = _RecordingIndex()
    ranked = await _rank(index, _profile())
    assert index.calls == []
    assert "lira_fence" not in ranked


# ---------------------------------------------------------------------------
# The profile is consulted, not merely recorded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_harness_searches_at_the_profiles_top_k(graph) -> None:
    """`--retrieval-profile wide_rag` recorded rag_top_k=15 into retrieval_metrics.json
    while searching at the case's k. The recorded arm must be the arm that ran."""
    index = _RecordingIndex()
    await _rank(index, _profile(rag_top_k=15), k=5)
    assert index.calls[0]["top_k"] == 15


@pytest.mark.asyncio
async def test_a_skip_rag_profile_performs_no_vector_search(graph) -> None:
    """The `no_rag` arm's whole mechanism. A harness that searched anyway would report
    the default arm's precision under the no_rag label."""
    index = _RecordingIndex()
    await _rank(index, _profile(skip_rag=True))
    assert index.calls == []


@pytest.mark.asyncio
async def test_graph_known_events_still_reach_the_ranking(graph) -> None:
    """The scope removes known events from the VECTOR path only.

    They remain in the ranked list via the graph read, which is what keeps the labelled
    cases — dominated by `northern_war_begins`, an event captain_sorn KNOWS_ABOUT —
    measurable at all after DEC-209.
    """
    index = _RecordingIndex()
    ranked = await _rank(index, _profile())
    assert "northern_war_begins" in ranked


@pytest.mark.asyncio
async def test_run_eval_takes_the_profile_it_measures_under(graph) -> None:
    """`run_eval(cases, embedding_index, driver)` had no profile parameter, so no caller
    could have passed one even if it wanted to."""

    class _Session:
        async def __aenter__(self) -> Any:
            return None

        async def __aexit__(self, *_a: Any) -> bool:
            return False

    class _Driver:
        def session(self) -> Any:
            return _Session()

    index = _RecordingIndex()
    results = await retrieval_runner.run_eval(
        cases=[
            RetrievalCase(
                id="RET-001", npc_id=_NPC, query="northern war",
                relevant_node_ids=["northern_war_begins"], k=5,
            )
        ],
        embedding_index=index,
        driver=_Driver(),
        profile=_profile(rag_top_k=15),
    )
    assert index.calls[0]["top_k"] == 15
    assert results[0]["id"] == "RET-001"
