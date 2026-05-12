# Next Session Instructions

## Phase 3 — World Depth. Feature 3.5 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.4 as DONE (committed), add Feature 3.5 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1–3.4 ✅, 3.5 IN_PROGRESS.

---

## Feature 3.5 — Goals on characters

Read `project/ROADMAP.md` lines 508–535 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** NPCs without goals are purely reactive. Explicit goals give dialogue
natural hooks, make gossip stickier when goal-relevant, and provide quest
generation anchors. Goals are static descriptors in 3.5 — a goal pursuit engine
is deferred to a later feature.

### Architecture decisions (read before coding)

- **Node**: `Goal` with fields `id`, `description` (freeform), `urgency` (0–100),
  `status` (enum: `active`, `achieved`, `abandoned`), `created_at_game_time` (JSON),
  `target_id` (optional str, references another node).
- **Edge**: `(:Character)-[:PURSUES]->(:Goal)`.
- Schema YAML files:
  - `type_registry/base_nodes/goal.yaml`
  - `type_registry/base_edges/pursues.yaml`
- `graph/goal_queries.py` — Cypher strings for create, get, update status.
- `graph/goal_service.py` (≤150 lines) — `create_goal`, `get_goals_for_character`,
  `update_goal_status`.
- `retrieval/context_builder.py` — include active goals in Tier A (priority 87,
  just below beliefs at 88). Fetch top-k active goals only (status="active").
- Admin route `api/routes/goals.py` — `POST /v1/admin/goals/{character_id}`,
  `GET /v1/admin/goals/{character_id}`, `PATCH /v1/admin/goals/{goal_id}/status`.
  Wire into `main.py` at admin_prefix following the beliefs route pattern.
- **Gossip relevance**: add goal-alignment factor to gossip pair selection
  in `engines/gossip/pair_selector.py`. When an NPC has an active goal whose
  `target_id` matches a node known to the other NPC, increment their pair score.
  Keep this as a small additive bonus (not a multiplier) so it doesn't dominate.

### Steps

1. **Schema YAMLs**:
   - `type_registry/base_nodes/goal.yaml` — `id`, `description`, `urgency` (int,
     0–100), `status` (str), `created_at_game_time` (str), `target_id` (str,
     required: false).
   - `type_registry/base_edges/pursues.yaml` — `src_type: character`,
     `dst_type: goal`, no extra fields.

2. **`graph/goal_queries.py`** — Cypher strings + `get_goals_for_character`
   read accessor. Order by urgency DESC, filter by status when provided.

3. **`graph/goal_service.py`** (≤150 lines):
   - `create_goal(session, *, character_id, description, urgency, game_time, target_id=None) -> str`
   - `get_goals_for_character(session, *, character_id, k, status_filter="active") -> list[dict]`
   - `update_goal_status(session, *, goal_id, new_status) -> None`

4. **`retrieval/context_builder.py`** — after beliefs, fetch active goals for
   the NPC (k=3) and include as Tier A at priority 87. Keep existing memories
   and beliefs unchanged.

5. **`api/routes/goals.py`** — three endpoints: create, list, patch status.
   Wire into `main.py` following the beliefs route pattern.

6. **`engines/gossip/pair_selector.py`** — add goal-alignment bonus: for each
   candidate pair, if either NPC has an active goal whose `target_id` is a node
   the other NPC knows, add +10 to their pair affinity score. This requires
   fetching active goals per NPC during pair selection — use a new helper
   `get_goals_for_character` from `graph/goal_service.py`. Keep the change
   minimal: one extra query per pair candidate is acceptable; bail early if no
   active goals.

7. **Unit tests** `tests/unit/test_goal_service.py`:
   - Happy path: create goal → returns UUID.
   - Get active goals: returns list sorted by urgency descending.
   - Get goals with status filter: filters correctly.
   - Update status: modifies status on existing node.
   - No-goals case: returns empty list.

8. **E2E scenario** `e2e/scenarios/scenario_goals.py`:
   - Seed character.
   - Create two goals (one active, one achieved).
   - Fetch active goals, assert one returned.
   - Update status of active goal to achieved.
   - Fetch again, assert empty.
   - Cleanup.

### Definition of done (3.5)
- Schema YAMLs exist in `type_registry/base_nodes/` and `type_registry/base_edges/`.
- `graph/goal_service.py` passes all unit tests.
- `retrieval/context_builder.py` includes active goals in Tier A.
- Admin routes exist and are wired.
- Gossip pair selector includes goal-alignment bonus.
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: goal nodes (Phase 3.5)`

---

## After 3.5 is committed — update this file for Feature 3.6

When Feature 3.5 is committed and `pytest tests/ -q` is green, rewrite this
file to target Feature 3.6 — Items and ownership.

Read `project/ROADMAP.md` lines 536+ before writing 3.6 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3.5 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.5, log a new ISSUES.md entry describing the
blocking scenario and get approval before fixing.
