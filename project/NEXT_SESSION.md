# Next Session Instructions

## Phase 3 — World Depth. Feature 3.6 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.5 as DONE (committed), add Feature 3.6 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1–3.5 ✅, 3.6 IN_PROGRESS.

---

## Feature 3.6 — Items and ownership

Read `project/ROADMAP.md` lines 536–560 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** Action validation for giving items requires knowing what an NPC
actually owns. This feature adds `Item` nodes and `OWNS` edges so the dialogue
engine's action resolver can check ownership before allowing a `give_item` action.

### Architecture decisions (read before coding)

- **Node**: `Item` with fields `id`, `name`, `description`, `value` (int),
  `rarity` (str), `type` (str), `is_unique` (bool stored as str "true"/"false"),
  `properties` (str, JSON for flexible attributes).
- **Edge**: `(:Character)-[:OWNS {acquired_at}]->(:Item)`.
  The `acquired_at` field is a game-time JSON string.
- Schema YAML files:
  - `type_registry/base_nodes/item.yaml`
  - `type_registry/base_edges/owns.yaml`
- `graph/item_queries.py` — Cypher strings for create, get by id, get by owner.
- `graph/item_service.py` (≤150 lines) — `create_item`, `get_items_for_character`,
  `get_item_by_id`, `transfer_ownership`.
- `retrieval/context_builder.py` — include owned items in Tier A (priority 86,
  just below goals at 87). Fetch all items owned by the NPC (no status filter).
- Admin route `api/routes/items.py` — `POST /v1/admin/items/{character_id}`,
  `GET /v1/admin/items/{character_id}`, `PATCH /v1/admin/items/{item_id}/owner`.
  Wire into `main.py` at admin_prefix following the goals route pattern.
- **Action resolver**: in `engines/dialogue/action_resolver.py`, extend the
  `give_item` action handling to check that the sharer (NPC) owns the item
  before allowing it. If not owned, resolve the action as `ignored` with a
  reason. Keep the change minimal — one ownership check function.

### Steps

1. **Schema YAMLs**:
   - `type_registry/base_nodes/item.yaml` — `id`, `name`, `description`,
     `value` (int), `rarity` (str), `type` (str), `is_unique` (str),
     `properties` (str, JSON).
   - `type_registry/base_edges/owns.yaml` — `src_type: character`,
     `dst_type: item`, `acquired_at` (str, required: false).

2. **`graph/item_queries.py`** — Cypher strings + `get_items_for_character`
   and `get_item_by_id` read accessors.

3. **`graph/item_service.py`** (≤150 lines):
   - `create_item(session, *, character_id, name, description, value, rarity, type_, is_unique, game_time, properties=None) -> str`
   - `get_items_for_character(session, *, character_id) -> list[dict]`
   - `get_item_by_id(session, *, item_id) -> dict | None`
   - `transfer_ownership(session, *, item_id, from_character_id, to_character_id, game_time) -> None`

4. **`retrieval/context_builder.py`** — after goals, fetch owned items for
   the NPC and include as Tier A at priority 86.

5. **`api/routes/items.py`** — three endpoints: create, list, patch owner.
   Wire into `main.py` following the goals route pattern.

6. **`engines/dialogue/action_resolver.py`** — add ownership check for
   `give_item` actions. When the action type is `give_item`, query `get_items_for_character`
   for the NPC and verify the named item is in the list. If not, return
   `ActionType.ignored` (or equivalent no-op). Keep as a small additive check.

7. **Unit tests** `tests/unit/test_item_service.py`:
   - Happy path: create item → returns UUID.
   - Get items: returns list for character.
   - Get item by id: returns item dict or None.
   - Transfer ownership: detaches old OWNS edge, creates new one.
   - No-items case: returns empty list.

8. **E2E scenario** `e2e/scenarios/scenario_items.py`:
   - Seed two characters.
   - Create an item owned by character 1.
   - Fetch items for character 1, assert one returned.
   - Transfer ownership to character 2.
   - Fetch items for character 1, assert empty.
   - Fetch items for character 2, assert one returned.
   - Cleanup.

### Definition of done (3.6)
- Schema YAMLs exist in `type_registry/base_nodes/` and `type_registry/base_edges/`.
- `graph/item_service.py` passes all unit tests.
- `retrieval/context_builder.py` includes owned items in Tier A.
- Admin routes exist and are wired.
- Action resolver checks ownership for `give_item`.
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: item nodes (Phase 3.6)`

---

## After 3.6 is committed — update this file for Feature 3.7

When Feature 3.6 is committed and `pytest tests/ -q` is green, rewrite this
file to target Feature 3.7 — Secrets.

Read `project/ROADMAP.md` lines 563+ before writing 3.7 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3.6 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.6, log a new ISSUES.md entry describing the
blocking scenario and get approval before fixing.
