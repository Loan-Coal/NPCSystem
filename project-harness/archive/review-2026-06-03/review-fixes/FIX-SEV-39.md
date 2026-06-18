# FIX-SEV-39 — Targeted tests for worst-covered risk modules

**Severity:** LOW · **Confidence:** Confirmed · **Effort:** L
**Category:** testing · **Absorbs:** GRAPH-10, TEST-06, TEST-07

## Problem
Five high-risk modules are critically under-covered:
- `retrieval/graph_rag.py` — 17% coverage (full-scan MATCH, magic weights `0.5/0.3/0.2` and `365.0/72.0`, in-function `import json`)
- `pair_selector.py` — 22% (RNG-seeded pair selection — determinism rule path untested)
- `idempotency/neo4j_store.py` — 26% (replay contract)
- `modifier_bounds_validator.py` — 40% (mutation safety)
- `relation_delta_writer.py` — 29% (Neo4j write path)
No eval scenario exercises `delta_ticks=1`, `delta_ticks=1000`, or idempotency replay.

## Steps

### `tests/unit/test_graph_rag_coverage.py`
- Happy path: mock Neo4j session returning seed results; assert scoring formula produces expected ranking.
- Extract the magic weights (`0.5/0.3/0.2`, `365.0/72.0`) to `config.py` as `RAG_RECENCY_WEIGHT`, `RAG_TRUST_WEIGHT`, `RAG_RELEVANCE_WEIGHT`, `RAG_RECENCY_DAYS_SOFT`, `RAG_RECENCY_DAYS_HARD` — test uses config values not literals.
- Document the label-less `MATCH (seed)` full-scan in `ISSUES.md` as ISSUE-NNN (do not fix here — it is a correctness concern that may interact with SEV-04).

### `tests/unit/test_pair_selector_coverage.py`
- Same-seed run × 2 → identical pair ordering (determinism).
- Different seed → different ordering (randomness).
- Assert log output contains the seed value (observability rule).

### `tests/unit/test_idempotency_neo4j_store_coverage.py`
- First call with key K: stored and original response returned.
- Second call with key K: stored response returned, no re-execution.
- Call after TTL expiry: treated as fresh (mock clock to advance past TTL).

### `tests/unit/test_modifier_bounds_validator_coverage.py`
- Value within bounds → no exception.
- Value at each boundary (min, max) → no exception.
- Value one unit outside each boundary → raises `ModifierBoundsError` (verify error class name in `utils/errors.py`).

### `tests/unit/test_relation_delta_writer_coverage.py`
- Happy-path write: mock session, assert correct Cypher called with right params.
- Source node not found → raises a typed domain error (not bare `Exception`).
- Target node not found → raises a typed domain error.

### Integration: add clock boundary cases
In `tests/integration/test_clock.py` (create if absent):
- `delta_ticks=1` → processes exactly 1 tick.
- `delta_ticks=1000` → accepted (not rejected by validation).
- Idempotency replay: same request twice with same idempotency key → second returns cached response without re-executing.

## Verification
- `pytest --cov=src/npc_engine/retrieval/graph_rag --cov-fail-under=70 tests/unit/test_graph_rag_coverage.py` — passes
- Each new test file individually passes.
- `make test` green overall.

## Blast radius
Test-only except: `graph_rag.py` gets magic weights extracted to `config.py` (small prod change, no behavior change).
