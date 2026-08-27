"""
Module: retrieval_runner
Layer: evals (evaluation harness)
Purpose: Loads labeled retrieval cases from evals/cases/retrieval_demo.json, runs
         TIER-B VECTOR RETRIEVAL plus the graph KNOWS_ABOUT read for each (npc_id, query)
         pair under a named arm, computes precision@k / recall@k / MRR, and prints a
         summary table. Requires a running Neo4j + populated corpus (make demo-seed).
Dependencies: evals.engine_adapter (sole gateway to npc_engine), evals.retrieval_matchers
Used by: make eval-retrieval (python -m evals.retrieval_runner)

WHAT THIS MEASURES, AND WHAT IT DOES NOT (P9)
It measures RETRIEVAL: the ranked node ids the tier-B vector search and the KNOWS_ABOUT
read produce, inside the DEC-209 scope, at the arm's `rag_top_k`. That claim is narrower
than the module's name suggests and it is now the honest one.

It does NOT measure what reaches the model. That would mean calling
`build_serialized_context_with_receipt` and scoring over `item_keys`, and P9 deliberately
did not do it, for three reasons recorded in DEC-213:
  1. At PROMPT_TOKEN_BUDGET 25,888 nothing is dropped (DEC-204, plan review point E), so
     precision-over-what-reached-the-model and precision-over-what-was-ranked are the
     same number today. The repoint would buy nothing until P10's trim makes the budget
     bind, which is exactly where it belongs.
  2. `item_keys` are SLOT keys (`rag:x`, `event:0:npc`, `beliefs`), and the labelled
     fixture is node ids. Tier-A slots such as `beliefs` and `goals` carry no node id at
     all, so scoring over item_keys would silently drop most of tier A from the
     denominator and quietly redefine every historical figure.
  3. It increases evals/ -> src/ coupling that P10 would have to re-verify, inside the
     fence that says no src/ change lands after P9 goes green.

CONSEQUENCE OF THE SCOPE, RECORDED. The labelled cases are dominated by
`northern_war_begins`, an event `captain_sorn` KNOWS_ABOUT. DEC-209 removes known events
from the vector scope on purpose — tier A already carries them — so the vector path can
no longer return the labelled node for those cases. They stay measurable because the
graph read still appends them. The labels were written for a retrieval design the engine
no longer has, and precision numbers from before P9 are not comparable with numbers after
it.

NOTE: This runner hits Neo4j and the embedding index when invoked from make eval-retrieval.
      For unit tests, the pure metric functions in evals.retrieval_matchers are tested in
      isolation without any I/O (tests/unit/test_retrieval_eval.py); the scope and profile
      behaviour is pinned in tests/unit/evals/test_retrieval_runner_scope.py.
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


async def _vector_hits(
    npc_id: str,
    query: str,
    profile: Any,
    embedding_index: Any,
    graph_session: Any,
    known_event_ids: set[str],
) -> list[str]:
    """Return the vector-ranked node IDs, inside the DEC-209 scope.

    The scope is the NPC's 1-hop subgraph, location and faction, MINUS the events it
    already knows. An empty scope means NO vector search — never an unfiltered one.

    Args:
        npc_id: Character node ID.
        query: Player query text.
        profile: The resolved RetrievalProfile this measurement runs under.
        embedding_index: Vector store (must have an async .search).
        graph_session: Active Neo4j AsyncSession.
        known_event_ids: Events the NPC already carries in tier A.

    Returns:
        Ranked node ID strings from the vector store; empty when the arm skips RAG or
        the NPC has no scope.
    """
    if profile.skip_rag:
        return []
    scope = await engine_adapter.rag_scope_ids(session=graph_session, npc_id=npc_id)
    scope = set(scope) - known_event_ids
    if not scope:
        return []
    hits = await embedding_index.search(
        query=query, top_k=profile.rag_top_k, filter_ids=scope
    )
    return [row["id"] for row in hits]


async def _retrieve_ranked_ids(
    npc_id: str,
    query: str,
    k: int,
    profile: Any,
    embedding_index: Any,
    graph_session: Any,
) -> list[str]:
    """Return a ranked list of node IDs for one (npc_id, query) pair.

    Strategy:
    1. Tier-B vector search, scoped and at the PROFILE's rag_top_k (see _vector_hits).
    2. Graph context: KNOWS_ABOUT edges, surfacing events the NPC directly knows. These
       are what the DEC-209 scope deliberately removes from the vector path, and they
       remain here because they genuinely reach the model as tier-A `event:` items.
    3. The NPC's own character node (always tier A).
    4. Deduplicate, preserving rank order.

    `k` is the metric window (precision@k), NOT the retrieval width. Those were the same
    number until P9, which is why `--retrieval-profile wide_rag` could be recorded while
    the harness searched at the case's k.

    Args:
        npc_id: Character node ID.
        query: Player query text.
        k: Metric window from the case; retained for callers that report it.
        profile: The resolved RetrievalProfile this measurement runs under.
        embedding_index: EmbeddingIndex instance (must have .search coroutine).
        graph_session: Active Neo4j AsyncSession.

    Returns:
        Ordered list of node ID strings (most relevant first).
    """
    known_event_ids = await engine_adapter.known_event_ids(
        session=graph_session, npc_id=npc_id
    )
    ranked = await _vector_hits(
        npc_id, query, profile, embedding_index, graph_session, set(known_event_ids)
    )

    # Append KNOWS_ABOUT event IDs (graph-sourced, not vector-ranked)
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
    profile: Any,
) -> list[dict]:
    """Run all retrieval cases under one resolved arm and return per-case metric dicts.

    `profile` is required rather than defaulted. This function took no profile at all
    while `--retrieval-profile` was accepted and written into retrieval_metrics.json, so
    every recorded arm name was a claim about a measurement that never consulted it —
    the exact defect DEC-194 exists to prevent. A default here would let that recur
    silently at the first new call site.

    Args:
        cases: Labeled retrieval cases loaded from the fixture.
        embedding_index: Populated EmbeddingIndex instance.
        driver: Neo4j AsyncDriver for graph queries.
        profile: The resolved RetrievalProfile this measurement runs under.

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
                    profile=profile,
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

    profile = engine_adapter.resolve_retrieval_profile(retrieval_profile)
    print(
        f"Arm: {retrieval_profile}  (rag_top_k={profile.rag_top_k}, "
        f"skip_rag={profile.skip_rag})"
    )
    results = await run_eval(
        cases=cases, embedding_index=embedding_index, driver=driver, profile=profile
    )
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
