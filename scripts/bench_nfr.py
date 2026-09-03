#!/usr/bin/env python
"""
Module: bench_nfr
Layer: scripts (dev tooling)
Purpose: Put a number on the non-functional requirements in docs/BUSINESS_REQUIREMENTS.md,
         which have been stated as targets and never once measured (CR-L12-05, R5.5).
Does NOT: gate anything, seed a world, or start the stack.
Dependencies: argparse, json, os, sys, time, pathlib, httpx, neo4j
Dependencies injected: NPC_ENGINE_API_KEY, NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD.
Used by: make bench-nfr

This is a MEASUREMENT, not a ratchet, and is deliberately outside `make check`: a
benchmark that gates turns an unrelated slowdown into a red build, and this repo already
has enough gates that fail for reasons other than the one they name.

Every target it cannot reach is reported as "not measured" with the reason. Inventing a
number for an NFR is worse than admitting the number does not exist — the whole point of
CR-L12-05 is that four targets were stated and none was ever checked.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
GOSSIP_PAIRS_TARGET = 200
GRAPH_NODES_TARGET = 10_000
GOSSIP_ENDPOINT = "/v1/admin/batch/gossip_tick"
CYPHER_COUNT_NODES = "MATCH (n) RETURN count(n) AS nodes"


def _result(name: str, target: str, measured: object, met: bool | None, note: str = "") -> dict[str, Any]:
    """Return one NFR row for the report."""
    return {"nfr": name, "target": target, "measured": measured, "met": met, "note": note}


def measure_gossip_throughput(base_url: str, api_key: str, pairs: int) -> dict[str, Any]:
    """Run one gossip tick at the target pair count and report pairs per second."""
    import httpx

    payload = {"max_pairs": pairs}
    headers = {"Authorization": f"Bearer {api_key}"}
    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url}{GOSSIP_ENDPOINT}", json=payload, headers=headers, timeout=300.0
        )
    except Exception as exc:  # noqa: BLE001 - a benchmark reports failure, never raises
        return _result("gossip tick throughput", f">= {pairs} pairs/tick", None, None, f"request failed: {exc}")
    elapsed = time.perf_counter() - started
    if response.status_code != 200:
        return _result(
            "gossip tick throughput", f">= {pairs} pairs/tick", None, None,
            f"HTTP {response.status_code}: {response.text[:160]}",
        )
    processed = response.json().get("data", {}).get("pairs")
    achieved = isinstance(processed, int) and processed >= pairs
    return _result(
        "gossip tick throughput",
        f">= {pairs} pairs/tick",
        {"requested_pairs": pairs, "processed_pairs": processed, "seconds": round(elapsed, 3)},
        achieved,
        _throughput_note(processed, pairs, elapsed, achieved),
    )


def _throughput_note(processed: object, pairs: int, elapsed: float, achieved: bool) -> str:
    """Explain what the pair count does and does not prove about the target.

    The engine reports how many pairs it actually processed. That, not "the request
    returned 200", is what the target is about: a tick that ran happily on 36 pairs says
    nothing about 200. Calling that success would be exactly the over-claiming CR-L12-05
    exists to correct.
    """
    if isinstance(processed, int) and not achieved:
        return (
            f"engine processed {processed} pairs in {elapsed:.3f}s against a target of {pairs}. "
            "The seeded world does not offer enough eligible pairs, so this is a WORLD-SIZE "
            "limit, not a demonstrated engine limit - the target remains unproven either way."
        )
    return f"engine processed {processed} pairs in {elapsed:.3f}s at max_pairs={pairs}"


def measure_graph_size() -> dict[str, Any]:
    """Count nodes in the graph and compare against the scale target."""
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return _result("knowledge graph size", f">= {GRAPH_NODES_TARGET} nodes", None, None,
                       "NEO4J_PASSWORD not set")
    try:
        with GraphDatabase.driver(uri, auth=(user, password)) as driver:
            with driver.session() as session:
                nodes = session.run(CYPHER_COUNT_NODES).single()["nodes"]
    except Exception as exc:  # noqa: BLE001
        return _result("knowledge graph size", f">= {GRAPH_NODES_TARGET} nodes", None, None,
                       f"connection failed: {exc}")
    return _result("knowledge graph size", f">= {GRAPH_NODES_TARGET} nodes", nodes,
                   nodes >= GRAPH_NODES_TARGET,
                   "seeded demo world, not a scale test" if nodes < GRAPH_NODES_TARGET else "")


def unmeasured_nfrs() -> list[dict[str, Any]]:
    """Return the NFRs this harness deliberately does not claim to measure."""
    return [
        _result("service uptime", "99.5% during active sessions", None, None,
                "not measurable in a dev checkout: needs production observability over time"),
        _result("LLM fallback on timeout", "< 100 ms canned response", None, None,
                "needs a forced LLM timeout (LLM_TIMEOUT_SECONDS near 0) and an app restart; "
                "out of scope for a read-only benchmark"),
    ]


def render(rows: list[dict[str, Any]]) -> str:
    """Return a human-readable report of every NFR row."""
    lines = ["bench-nfr: non-functional requirements", ""]
    for row in rows:
        if row["met"] is None:
            status = "NOT MEASURED"
        else:
            status = "MET" if row["met"] else "NOT MET"
        lines.append(f"  [{status}] {row['nfr']}  (target {row['target']})")
        if row["measured"] is not None:
            # ensure_ascii: engine results carry non-cp1252 characters (e.g. "->" as U+2192)
            # and Windows consoles default to cp1252, which raises UnicodeEncodeError.
            lines.append(f"      measured: {json.dumps(row['measured'], ensure_ascii=True, sort_keys=True)}")
        if row["note"]:
            lines.append(f"      note: {row['note']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Measure what is reachable, report what is not, and write a JSON artifact."""
    parser = argparse.ArgumentParser(description="Measure the stated NFRs (R5.5).")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--pairs", type=int, default=GOSSIP_PAIRS_TARGET)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    api_key = os.environ.get("NPC_ENGINE_API_KEY", "")
    rows: list[dict[str, Any]] = []
    if api_key:
        rows.append(measure_gossip_throughput(args.base_url, api_key, args.pairs))
    else:
        rows.append(_result("gossip tick throughput", f">= {args.pairs} pairs/tick", None, None,
                            "NPC_ENGINE_API_KEY not set; every /v1 route requires a Bearer token"))
    rows.append(measure_graph_size())
    rows.extend(unmeasured_nfrs())

    print(render(rows))
    if args.out is not None:
        args.out.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"\nbench-nfr: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
