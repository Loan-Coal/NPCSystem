# delta_log Cap and Eviction Policy — Options

## Current State

`delta_log` is a JSON string stored directly on each `RELATES_TO` edge (`r.delta_log`).

Every dialogue turn writes via `write_delta_log()` in `graph/delta_log_writer.py`:
1. The Cypher query in `graph_writer.py` fetches the whole string (`RETURN coalesce(r.delta_log, '[]')`).
2. The string is parsed, a new entry appended, then the whole list is re-serialized to JSON and written back.
3. `append_delta()` in `mutation/delta_log_manager.py` caps to `max_entries = settings.RELATION_WINDOW_SIZE` via `combined_log[-max_entries:]`.

**So Option A already exists in code** — the question is whether to raise the cap, document it more explicitly, or replace the storage model.

Each `RelationDeltaEntry` has: `tick_id` (int), `cause_id` (str UUID), `deltas` (dict of up to 3 ints), `timestamp` (ISO string). Estimated ~200 bytes per entry.

---

## Option A — Fixed-size FIFO list on the edge (current approach, tighten cap)

**What changes:** Make the cap explicit and configurable as a separate setting (`DELTA_LOG_MAX_ENTRIES`, default 50), independent from `RELATION_WINDOW_SIZE` (which controls validation window, typically smaller). Document the cap in ARCHITECTURE.md.

**Read path:** One property read in the RELATES_TO fetch Cypher. Already in the hot path.

**Write path:** Fetch → parse → append → serialize → write. Already happening; a cap of 50 means max ~10KB per edge.

### Impact / Effort / Risk
- **Impact:** Low. Formalizes existing behavior. The JSON blob stays on the edge.
- **Effort:** Minimal — add `DELTA_LOG_MAX_ENTRIES` to config, thread it into `apply_relation_delta`, update docs.
- **Risk:** Low.

### Pros
- Zero schema migration needed (the property already exists).
- Read latency: zero overhead — value already fetched in the RELATES_TO query.
- Write latency: already pays the full round-trip; cap prevents growth.
- Deterministic gossip replay works within the window (last 50 entries).
- No extra graph hops on read.

### Cons
- History beyond N entries is permanently lost — no replay past the cap.
- JSON string serialization/deserialization on every write is slightly wasteful.
- 50 entries × ~200 bytes = ~10KB per edge. With 10K NPCs and dense relations, the edge property store grows proportionally.
- If `RELATION_WINDOW_SIZE > DELTA_LOG_MAX_ENTRIES`, the mutation validator could try to read a window larger than what's stored.

---

## Option B — Separate `DeltaEvent` node per delta

**What changes:** Each delta write creates a new `(:DeltaEvent)` node linked to the relation: `(:Character)-[:RELATES_TO {edge_id}]->(:Character)` and `(:DeltaEvent {edge_id, tick_id, ...})`. No cap; full history queryable.

Requires adding a stable `edge_id` property to each RELATES_TO edge (e.g., `src_id + ":" + dst_id`), and a new `DeltaEvent` label.

### Impact / Effort / Risk
- **Impact:** High. Schema change, new node label, new Cypher queries, migration needed.
- **Effort:** High. New node type in registry, new writer, new reader, migration, embedding reconciler exclusion.
- **Risk:** Medium. More moving parts; integration tests would require updates.

### Pros
- Unbounded history — full audit log, complete gossip determinism replay.
- History is queryable (e.g., "show all trust changes for this pair").
- No JSON string serialization overhead.
- Edge property stays small (no delta_log blob).

### Cons
- Every dialogue turn now writes a new node (extra transaction work).
- Reading the last N deltas for validation requires an extra graph hop + ORDER BY + LIMIT query.
- Read latency on dialogue: replaces one property read with one extra Cypher query.
- Graph node count grows: with 100 dialogue turns per NPC pair, 1000 pairs → 100K DeltaEvent nodes.
- Migration: existing delta_log JSON strings would need to be parsed and exploded into DeltaEvent nodes.
- Schema evolution: adding fields to DeltaEvent requires a migration.

---

## Option C — Hybrid: last K inline on edge + full history archived

**What changes:** Keep the last K=10 deltas as a JSON string on the edge for fast validation reads. Additionally, every delta write also appends a `DeltaEvent` node for full history. The edge property serves as a cache; DeltaEvent is the archive.

### Impact / Effort / Risk
- **Impact:** High. Same schema additions as Option B, plus dual-write logic.
- **Effort:** Highest. Two code paths must stay in sync; cache coherence must be maintained.
- **Risk:** Medium-High. Dual-write drift is a subtle bug class.

### Pros
- Validation window reads from fast inline cache (no extra hop for the last K entries).
- Full history available for replay/audit.
- Best latency on the hot dialogue path.

### Cons
- Most code to maintain.
- If K < RELATION_WINDOW_SIZE, validation still needs to query DeltaEvent nodes for the remainder.
- Dual-write failure modes: if the DeltaEvent write fails but the edge write succeeds (or vice versa), the record is inconsistent.
- Migration from current state: hardest of the three.

---

## Recommendation

**Option A with an explicit, documented cap.**

Rationale:
- The current code already implements Option A correctly — `append_delta()` with `max_entries` is already FIFO and bounded.
- For a solo prototype where gossip replay debugging is occasional, losing entries beyond 50 is an acceptable trade-off. The last 50 entries spans many real-play sessions.
- The read latency win of keeping the data on the edge is real: every dialogue turn reads this field, and adding a graph hop (Options B/C) would visibly increase latency.
- Option B is the right answer when you need full auditability at scale, but that's a post-prototype concern.

**Concrete action (when you pick Option A):**
1. Add `DELTA_LOG_MAX_ENTRIES: int = 50` to `config.py`.
2. Pass it to `apply_relation_delta` → `append_delta(max_entries=settings.DELTA_LOG_MAX_ENTRIES)` instead of `settings.RELATION_WINDOW_SIZE`.
3. Update `DATA_MODELS.md` to document the cap.
4. No migration needed (existing edge values are already bounded by `RELATION_WINDOW_SIZE`; the new cap applies going forward).

**Wait for me to pick an option before implementing.**
