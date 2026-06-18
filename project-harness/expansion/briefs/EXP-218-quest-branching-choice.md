# EXP-218 — Quest branching on player choice (DEC-101 `unlocks.on_choice_id`)

**Goal / rationale:** Quest chains auto-unlock the next quest; the player's choice never selects the
branch. Letting a choice pick the successor turns quests into consequence chains. The `unlocks.yaml`
`on_choice_id` field is ALREADY ADDED (DEC-101) — do NOT change the schema.

**First slice (your scope):** A `QuestChainResolver.choose(choice_id, ...)` method that selects the
successor quest whose `UNLOCKS.on_choice_id` matches the player's choice, plus a `POST /quest/{id}/choose`
route to invoke it. Auto-unlock (null `on_choice_id`) behavior is preserved.

**Current state (verified):**
- `src/npc_engine/type_registry/base_edges/unlocks.yaml` — now has `on_choice_id` (optional; null =
  auto-unlock, preserving current behavior). Applied; do not touch.
- `src/npc_engine/engines/quest/quest_chain_resolver.py` — `QuestChainResolver` exists (resolves
  UNLOCKS chains). Add a `choose(quest_id, choice_id, ...)` method that returns/activates the successor
  quest whose `on_choice_id` matches `choice_id`. Reuse the existing UNLOCKS reader; filter by the new field.
- `src/npc_engine/api/routes/quest.py` (or quest_generation route module) — add a `POST /quest/{id}/choose`
  route that calls the resolver. Follow the existing quest-route + auth pattern; cap/validate input.

**Files:**
- EDIT `src/npc_engine/engines/quest/quest_chain_resolver.py` — `choose()` (≤40 lines; reuse the UNLOCKS
  query, filter on `on_choice_id`).
- POSSIBLY EDIT `src/npc_engine/graph/quest_chain_queries.py` — if the UNLOCKS reader needs to return
  `on_choice_id` (extend the projection).
- EDIT or NEW `src/npc_engine/api/routes/quest.py` — `POST /quest/{id}/choose` with a Pydantic request/
  response model, auth via the existing middleware. Register if needed.
- Tests: `tests/unit/test_quest_chain_resolver.py` (choice selects the matching successor; null
  on_choice_id still auto-unlocks) + a route test.

**Graph/API surface:** new `POST /quest/{id}/choose` route; no schema change (field exists). Pydantic models.

**Architecture fit:** closed-edit (resolver + route) + optional query projection. Layer api→engines→graph.
No schema. No LLM in graph/retrieval.

**Test plan (RED first):** `test_choose_selects_matching_successor` + `test_null_choice_auto_unlocks` +
a route happy-path. Watch fail, implement. Run: `pytest tests/unit/test_quest_chain_resolver.py -q`.

**Done when:** a player choice selects the matching successor quest; auto-unlock still works when
`on_choice_id` is null; route + tests green; no schema change.
