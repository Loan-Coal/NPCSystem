"""
Module: retrieval_runner
Layer: evals (evaluation harness)
Purpose: Loads labeled retrieval cases from evals/cases/retrieval_demo.json, calls the
         retrieval stack in-process (EmbeddingIndex + graph KNOWS_ABOUT query) for each
         (npc_id, query) pair, computes precision@k / recall@k / MRR, and prints a
         summary table. Requires a running Neo4j + populated embedding index (make demo-seed).
Dependencies: npc_engine.retrieval.embedding_index, npc_engine.graph, evals.retrieval_matchers
Used by: make eval-retrieval (python -m evals.retrieval_runner)

NOTE: This runner hits Neo4j and the embedding index when invoked from make eval-retrieval.
      For unit tests, the pure metric functions in evals.retrieval_matchers are tested in
      isolation without any I/O (tests/unit/test_retrieval_eval.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from evals.retrieval_matchers import mrr, precision_at_k, recall_at_k
from evals.retrieval_summary import format_retrieval_summary_lines, summarize_retrieval

_CASES_PATH = Path(__file__).parent / "cases" / "retrieval_demo.json"
_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Case schema (Pydantic v2)
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class RetrievalCase(BaseModel):
    """One labeled retrieval evaluation case."""

    id: str
    npc_id: str
    query: str
    relevant_node_ids: list[str]
    k: int
    notes: str = ""


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------


def _node_id_from_key(key: str) -> str:
    """Extract the leaf node ID from a context item key.

    Keys follow the pattern ``prefix:node_id`` (e.g. ``character:mira_innkeeper``,
    ``location:loc_tavern``, ``rag:northern_war_begins``) or bare strings.
    Returns the last colon-separated segment.

    Args:
        key: A ContextItem key string.

    Returns:
        The trailing node ID substring after the last colon, or the full key
        when no colon is present.
    """
    return key.rsplit(":", 1)[-1]


async def _retrieve_ranked_ids(
    npc_id: str,
    query: str,
    k: int,
    embedding_index: Any,
    graph_session: Any,
) -> list[str]:
    """Return a ranked list of node IDs for one (npc_id, query) pair.

    Strategy:
    1. Vector search: call embedding_index.search(query, top_k=k) to get
       semantically ranked items from the vector store.  Item IDs from the
       store directly correspond to the graph node IDs indexed at seed time.
    2. Graph context: query KNOWS_ABOUT edges for the NPC to surface event
       nodes the NPC has direct graph knowledge of.
    3. Append the NPC's own character node ID (always present as Tier A).
    4. Deduplicate while preserving rank order (vector items first, then
       graph items not already in the vector list).

    Args:
        npc_id: Character node ID.
        query: Player query text.
        k: How many top results to retrieve from the vector store.
        embedding_index: EmbeddingIndex instance (must have .search coroutine).
        graph_session: Active Neo4j AsyncSession.

    Returns:
        Ordered list of node ID strings (most relevant first).
    """
    from npc_engine.graph.graph_reader import get_known_event_ids_for_npc

    vector_results = await embedding_index.search(query=query, top_k=k)
    ranked: list[str] = [r["id"] for r in vector_results]

    # Append KNOWS_ABOUT event IDs (graph-sourced, not vector-ranked)
    known_event_ids = await get_known_event_ids_for_npc(session=graph_session, npc_id=npc_id)
    for event_id in sorted(known_event_ids):
        if event_id not in ranked:
            ranked.append(event_id)

    # Append NPC's own character node (always Tier A)
    if npc_id not in ranked:
        ranked.append(npc_id)

    return ranked


# ---------------------------------------------------------------------------
# Core eval loop
# ---------------------------------------------------------------------------


async def run_eval(
    cases: list[RetrievalCase],
    embedding_index: Any,
    driver: Any,
) -> list[dict]:
    """Run all retrieval cases and return per-case metric dicts.

    Args:
        cases: Labeled retrieval cases loaded from the fixture.
        embedding_index: Populated EmbeddingIndex instance.
        driver: Neo4j AsyncDriver for graph queries.

    Returns:
        List of result dicts with keys: id, npc_id, query, p_at_k, r_at_k, mrr_score,
        relevant_node_ids, ranked_ids, k.
    """
    results: list[dict] = []
    async with driver.session() as session:
        for case in cases:
            relevant = set(case.relevant_node_ids)
            try:
                ranked = await _retrieve_ranked_ids(
                    npc_id=case.npc_id,
                    query=case.query,
                    k=case.k,
                    embedding_index=embedding_index,
                    graph_session=session,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("retrieval failed for %s: %s", case.id, exc)
                ranked = []

            p = precision_at_k(ranked, relevant, k=case.k)
            r = recall_at_k(ranked, relevant, k=case.k)
            m = mrr(ranked, relevant)
            results.append({
                "id": case.id,
                "npc_id": case.npc_id,
                "query": case.query,
                "p_at_k": p,
                "r_at_k": r,
                "mrr_score": m,
                "relevant_node_ids": case.relevant_node_ids,
                "ranked_ids": ranked[:case.k],
                "k": case.k,
            })
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_summary(results: list[dict]) -> None:
    """Print a human-readable summary table of retrieval eval results.

    Args:
        results: Per-case result dicts from run_eval().
    """
    header = f"{'ID':<12} {'NPC':<22} {'P@k':>6} {'R@k':>6} {'MRR':>6}  query"
    print("\n" + "=" * 80)
    print("Retrieval Eval — demo world")
    print("=" * 80)
    print(header)
    print("-" * 80)
    for r in results:
        query_short = r["query"][:40]
        print(
            f"{r['id']:<12} {r['npc_id']:<22} "
            f"{r['p_at_k']:>6.3f} {r['r_at_k']:>6.3f} {r['mrr_score']:>6.3f}  {query_short}"
        )
    print("-" * 80)
    avg_p = sum(r["p_at_k"] for r in results) / len(results) if results else 0.0
    avg_r = sum(r["r_at_k"] for r in results) / len(results) if results else 0.0
    avg_mrr = sum(r["mrr_score"] for r in results) / len(results) if results else 0.0
    print(
        f"{'AVERAGE':<12} {'':<22} "
        f"{avg_p:>6.3f} {avg_r:>6.3f} {avg_mrr:>6.3f}"
    )
    print("=" * 80)
    print(f"\nTotal cases: {len(results)}")
    print(f"Mean Precision@k : {avg_p:.3f}")
    print(f"Mean Recall@k    : {avg_r:.3f}")
    print(f"Mean MRR         : {avg_mrr:.3f}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main() -> int:
    """Load cases, build retrieval stack, run eval, print summary.

    Returns:
        Exit code: 0 on success, 1 on connectivity/setup failure.
    """
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT)

    # Load cases
    if not _CASES_PATH.exists():
        logger.error("Cases file not found: %s", _CASES_PATH)
        return 1
    with _CASES_PATH.open(encoding="utf-8") as fh:
        raw_cases = json.load(fh)
    cases = [RetrievalCase(**c) for c in raw_cases]

    # Bootstrap settings and stack
    # Settings requires API_KEY_SECRET; provide a minimal eval default if missing.
    os.environ.setdefault("API_KEY_SECRET", "eval-key-placeholder")
    from npc_engine.config import get_settings
    from npc_engine.graph.db import GraphDB
    from npc_engine.retrieval.embedding_index import EmbeddingIndex
    from npc_engine.retrieval.vector_store_factory import create_vector_store

    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    embedding_index = EmbeddingIndex(
        vector_store=vector_store, model_name=settings.EMBEDDING_MODEL
    )

    graph_db = GraphDB(settings=settings)
    driver = graph_db.driver

    # Smoke-check Neo4j connectivity
    try:
        await driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: Cannot connect to Neo4j at {settings.NEO4J_URI}: {exc}\n"
            "Run `docker-compose up -d && make demo-seed` first.",
            file=sys.stderr,
        )
        return 1

    results = await run_eval(cases=cases, embedding_index=embedding_index, driver=driver)
    _print_summary(results)
    retrieval_summary = summarize_retrieval(results)
    for line in format_retrieval_summary_lines(retrieval_summary):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
