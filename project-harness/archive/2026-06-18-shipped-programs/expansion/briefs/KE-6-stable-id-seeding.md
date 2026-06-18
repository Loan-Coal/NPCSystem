# KE-6 — Stable-ID Idempotent Seeding (ISSUE-055)

**Goal / rationale:** Admin creation endpoints auto-generate random UUIDs, making re-seeding
non-idempotent: calling POST `/v1/admin/beliefs/{npc_id}` twice creates two belief nodes with
different IDs. The current workaround is a get-then-skip pass in `api_seeder.py` (and omitted
entirely for beliefs/goals/memories/secrets). The fix: accept an optional `id` field on all
typed creation endpoints; when provided, use MERGE semantics so the same seed run is safe to call
repeatedly. This is the prerequisite for EXP-92 (determinism/replay toggle) and EXP-95
(in-window scenario picker), and it simplifies `demo_game/seed.py` by removing the get-then-skip
boilerplate.

**Enabler for:** EXP-92 (replay toggle), EXP-95 (scenario picker), EXP-87 (location hierarchy
re-seeding). Must land first in any batch that includes those.

**Architecture fit:** Additive change to request schemas (one new optional field per model) +
graph write layer uses `MERGE` when `id` is provided. No layer rule violation; graph writes
live in `graph/`. Seeders are pure callers.

---

## Current state

- `src/npc_engine/api/routes/beliefs.py:34` — `CreateBeliefRequest` has no `id` field.
- `src/npc_engine/api/routes/goals.py:34` — `CreateGoalRequest` has no `id` field.
- `src/npc_engine/api/routes/memories.py:36` — `CreateMemoryRequest` has no `id` field.
- `src/npc_engine/api/routes/secrets.py:33` — `CreateSecretRequest` has no `id` field.
- `src/npc_engine/data/api_seeder.py:200-237` — beliefs/goals/memories/items POST blindly (no
  get-then-skip guard), creating duplicate nodes on re-seed.
- `demo_game/seed.py:253-258` — characters/locations use get-then-skip (`_seed_node`); beliefs
  use `_seed_npc_inner_life` which is idempotent only if the NPC has ≥1 existing BELIEVES edge
  (a brittle heuristic that breaks on partial re-seeds).
- `src/npc_engine/graph/generic_node_service.py:107` — `upsert_node` already accepts payload
  with `id` field and uses MERGE semantics for **node-type** nodes. The inner-life types
  (Belief, Goal, Memory, Secret) do NOT go through this path — they have separate graph writers.

## Files to create / edit

### Step 1 — Request schema changes (no graph touch yet; TDD: write tests first)

- **EDIT `src/npc_engine/api/routes/beliefs.py`** — add `id: str | None = Field(default=None, description="Caller-supplied stable ID. When provided the node is merged (idempotent). When omitted a UUID is auto-generated.")` to `CreateBeliefRequest`.
- **EDIT `src/npc_engine/api/routes/goals.py`** — same for `CreateGoalRequest`.
- **EDIT `src/npc_engine/api/routes/memories.py`** — same for `CreateMemoryRequest`.
- **EDIT `src/npc_engine/api/routes/secrets.py`** — same for `CreateSecretRequest`.

### Step 2 — Graph write layer MERGE support

Each inner-life typed route calls a graph writer to persist the node. Find the writer for each
type and ensure it uses `MERGE (n {id: $id})` when `id` is provided, `CREATE` when absent (auto
UUID via `uuid.uuid4().hex`).

- Locate the writer modules: `grep -rn "def.*write.*belief\|def.*create.*belief" src/npc_engine/graph/`
- Update each writer's `create_*` / `upsert_*` function to accept an optional `node_id: str | None`
  and branch accordingly. Do NOT change the Cypher for any node where `id` was omitted.

### Step 3 — Seeder updates

- **EDIT `src/npc_engine/data/api_seeder.py`** — pass stable IDs for all inner-life items:
  derive IDs deterministically, e.g. `f"bel_{char_id}_{hash(content)[:8]}"` for beliefs.
  Remove the `if belief_exists...` get-then-skip guard (now redundant with MERGE).
- **EDIT `demo_game/seed.py`** — update `_seed_npc_inner_life` to pass stable IDs per item.
  Remove the `if client.get_beliefs(npc_id): skip` heuristic; let MERGE handle idempotency.
- **EDIT `seeds/worlds/seed_village_world.py`** and `seeds/worlds/seed_tavern_world.py`
  — same pattern: pass stable IDs per inner-life item.

### Step 4 — Tests

- **NEW `tests/unit/test_stable_id_seeding.py`** — unit tests for the request schema (id field
  present + optional) and the graph writer MERGE path. No live DB required; use mock session.
- **EDIT `tests/unit/test_beliefs.py`** (and goals/memories/secrets equivalents) — add a
  happy-path test for `POST /v1/admin/beliefs/{npc_id}` with an explicit `id` in the body;
  assert the response node has that `id`. Add a test that posting the same `id` twice returns
  the same node (idempotent).

## Stable-ID derivation convention

Use a deterministic, short, human-readable format so IDs survive diff inspection:

```
Belief:   bel_{npc_id}_{content_hash_8}   e.g. bel_captain_sorn_a1b2c3d4
Goal:     goal_{npc_id}_{n}               e.g. goal_captain_sorn_0
Memory:   mem_{npc_id}_{n}                e.g. mem_mira_innkeeper_0
Secret:   sec_{npc_id}                    e.g. sec_lira_fence
```

Where `n` is the 0-based index within the NPC's list and `content_hash_8` is
`hashlib.sha1(content.encode()).hexdigest()[:8]`.

## Test plan

Write `tests/unit/test_stable_id_seeding.py` FIRST. Confirm it fails, then implement.

```bash
pytest tests/unit/test_stable_id_seeding.py -q
make check
```

After: run `make demo-seed` twice and confirm no duplicate nodes appear in Neo4j.

## Effort: M  |  Value: med  |  Business-fit: med
## Unblocks: EXP-92 (replay toggle), EXP-95 (scenario picker), EXP-87 (location re-seeding)
