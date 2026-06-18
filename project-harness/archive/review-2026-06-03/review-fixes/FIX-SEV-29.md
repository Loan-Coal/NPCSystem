# FIX-SEV-29 — Batch N+1 graph queries (gossip + embedding reconciler)

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** M
**Category:** performance · **Absorbs:** GRAPH-05, GRAPH-06

## Problem
1. `gossip_handler.py:118-219` issues 2-3 `session.run()` per NPC pair in a loop → N×3 sequential Neo4j round-trips per gossip tick.
2. `retrieval/embedding_reconciler.py:185-219` embeds one node at a time and writes one update per node → 200 sequential encodes + 200 sequential writes per reconciliation cycle.

## Current shape
- `gossip_handler.py:118-219`: `for pair in pairs: result = await session.run(...)` — multiple queries per loop iteration
- `retrieval/embedding_reconciler.py:185-219`: `for node in nodes: vec = await embed(node); await session.run(write_one, id=node.id, vec=vec)`
- `EmbeddingIndexProtocol`: no `embed_batch` method

## Steps

### Gossip handler
1. Read the current queries inside the loop and consolidate into:
   - One `UNWIND $pairs AS pair ...` read query that returns all needed data for all pairs.
   - One `UNWIND $writes AS w MERGE (src)-[r:KNOWS_ABOUT {id: w.id}]->(e) SET r += w.props` write query after Python-side processing.
2. Keep within the existing `async with session:` block; tx ownership unchanged.
3. Remove per-iteration `session.run` calls.

### Embedding reconciler
1. Add `embed_batch(texts: list[str]) -> list[list[float]]` to `EmbeddingIndexProtocol` and all implementations.
2. Collect all nodes needing embedding into a list; call `embed_batch()` once.
3. Write all embeddings in one Cypher:
   ```cypher
   UNWIND $nodes AS n
   MATCH (m {id: n.id})
   SET m.embedding = n.embedding
   ```
4. Update `MockEmbeddingIndex` to implement `embed_batch` (returns `[[0.0]*dim]*len(texts)` by default).

## Verification
- `tests/unit/test_gossip_n_plus_one.py`: spy on `session.run` calls → for N pairs, at most 2 calls total (not N×3).
- `tests/unit/test_embedding_reconciler_batch.py`: spy on `embed` calls → `embed_batch` called once with full list, not N individual calls.
- `make test` passes; no behavior change in gossip output.

## Blast radius
Gossip tick query path; embedding reconciliation cycle; `EmbeddingIndexProtocol` gains one method (all implementations must add it).
