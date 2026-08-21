"""
Module: retrieval_runner
Layer: evals (evaluation harness)
Purpose: Loads labeled retrieval cases from evals/cases/retrieval_demo.json, calls the
         retrieval stack in-process (EmbeddingIndex + graph KNOWS_ABOUT query) for each
         (npc_id, query) pair, computes precision@k / recall@k / MRR, and prints a
         summary table. Requires a running Neo4j + populated embedding index (make demo-seed).
Dependencies: evals.engine_adapter (sole gateway to npc_engine), evals.retrieval_matchers
Used by: make eval-retrieval (python -m evals.retrieval_runner)

NOTE: This runner hits Neo4j and the embedding index when invoked from make eval-retrieval.
      For unit tests, the pure metric functions in evals.retrieval_matchers are tested in
      isolation without any I/O (tests/unit/test_retrieval_eval.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from evals import engine_adapter
from evals.retrieval_matchers import mrr, precision_at_k, recall_at_k
from evals.retrieval_summary import (
    RetrievalSummary,
    format_retrieval_summary_lines,
    summarize_retrieval,
    write_retrieval_metrics,
)

_CASES_PATH = Path(__file__).parent / "cases" / "retrieval_demo.json"
_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Case schema (Pydantic v2)
# ---------------------------------------------------------------------------


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
    vector_results = await embedding_index.search(query=query, top_k=k)
    ranked: list[str] = [r["id"] for r in vector_results]

    # Append KNOWS_ABOUT event IDs (graph-sourced, not vector-ranked)
    known_event_ids = await engine_adapter.known_event_ids(session=graph_session, npc_id=npc_id)
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


async def _main(gen_dir: Path | None = None, retrieval_profile: str = "default") -> int:
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

    # Bootstrap settings and stack via the sanctioned adapter (keeps this module src-free).
    embedding_index, driver = await engine_adapter.build_retrieval_stack()

    # Smoke-check Neo4j connectivity
    try:
        await driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: Cannot connect to Neo4j at {engine_adapter.neo4j_uri()}: {exc}\n"
            "Run `docker-compose up -d && make demo-seed` first. Note that the neo4j\n"
            "service sits on the compose `internal` network, so its declared 7687 port\n"
            "is NOT published to the host — run this eval inside the app container:\n"
            "  docker compose exec app python -m evals.retrieval_runner",
            file=sys.stderr,
        )
        return 1

    results = await run_eval(cases=cases, embedding_index=embedding_index, driver=driver)
    _print_summary(results)
    retrieval_summary = summarize_retrieval(results)
    for line in format_retrieval_summary_lines(retrieval_summary):
        print(line)
    _persist_metrics(retrieval_summary, gen_dir, retrieval_profile)
    return 0


def _persist_metrics(
    retrieval_summary: RetrievalSummary, gen_dir: Path | None, retrieval_profile: str
) -> None:
    """Write retrieval_metrics.json when a generation dir was given, and say so.

    A no-op without --gen-dir, which keeps the old print-only behaviour available; the
    message is printed on success so a run never leaves the operator guessing whether the
    numbers were persisted or only displayed.
    """
    if gen_dir is None:
        return
    written = write_retrieval_metrics(
        retrieval_summary, gen_dir=gen_dir, retrieval_profile=retrieval_profile
    )
    print(f"Wrote {written}")


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point wrapping the async retrieval eval.

    Exists so the module presents the same ``main(argv) -> int`` contract as every
    other evals entry point, which is what ``python -m evals retrieval`` dispatches to.
    This runner takes no options today; any argument is rejected rather than ignored.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:]. Must be empty.
    Returns:
        0 on success, 1 on connectivity/setup failure, 2 on unexpected arguments.
    """
    parser = argparse.ArgumentParser(
        prog="python -m evals retrieval",
        description="Retrieval precision@k / recall@k / MRR over the annotated cases.",
    )
    # Without --gen-dir the numbers are printed and lost, which is why retrieval quality
    # could not be trended or A/B'd before this flag existed.
    parser.add_argument("--gen-dir", type=Path, default=None, help="Dir to write retrieval_metrics.json into.")
    parser.add_argument("--retrieval-profile", default="default", help="Profile measured under; recorded for attribution.")
    parsed = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return asyncio.run(_main(parsed.gen_dir, parsed.retrieval_profile))


if __name__ == "__main__":
    sys.exit(main())
