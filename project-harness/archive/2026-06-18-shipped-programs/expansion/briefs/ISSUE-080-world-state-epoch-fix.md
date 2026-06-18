# ISSUE-080 — Force-patch world_state epoch in demo-seed

**Goal / rationale:** `make demo-seed` uses skip-if-exists logic (`_seed_node`), so a drifted
`world_state.epoch` (e.g. `age_of_peace`) is never overwritten and every war-premise eval case
runs against wrong world state, producing phantom failures. P1 — blocks the entire eval battery.

**First slice (worker scope):** In `demo_game/seed.py`, replace the skip-if-exists `_seed_node`
call for `world_state` with a `client.patch_node` call that always force-PATCHES the `epoch` and
`active_conditions` fields. Add a `_force_patch_world_state` helper function that is always called
regardless of whether the node already exists.

**Current state (verified):**
- `demo_game/seed.py:915`: `_tally(_seed_node(client, "world_state", build_world_state_payload("war", ["northern_war"])))`
- `_seed_node` at line 224: checks `client.get_node(...)` first and returns `"skipped"` if it exists.
- `client.patch_node(node_type, node_id, properties)` at `demo_game/client.py:433` — always-SET via
  `PATCH /v1/graph/nodes/{node_type}/{node_id}` with `{"properties": {...}}`. Returns the updated node.
- `build_world_state_payload("war", ["northern_war"])` returns a dict with `epoch`, `active_conditions`
  and all other required fields.

**Files:**
- EDIT `demo_game/seed.py` — add `_force_patch_world_state(client)` helper (< 20 lines); call it just
  after line 915 regardless of whether `_seed_node` created or skipped the world_state node.
  The `_seed_node` call can remain for initial creation; `_force_patch_world_state` guarantees the
  critical fields are always correct even if the node was skipped.

**Graph/API surface:** None — `patch_node` uses the existing `PATCH /v1/graph/nodes/` route.

**Architecture fit:** Pure demo_game layer, no `src/npc_engine` changes. Additive helper.

**Test plan:**
Write `tests/unit/test_seed_world_state_patch.py` FIRST:
- Mock `EngineClient.get_node` to return an existing node dict (simulating skip path).
- Mock `EngineClient.patch_node` to capture args.
- Call `_force_patch_world_state(mock_client)`.
- Assert `patch_node` was called once with `("world_state", "world", ...)` containing `epoch="war"` and `active_conditions=["northern_war"]`.
Run: `pytest tests/unit/test_seed_world_state_patch.py -q`

**Done when:** The test above is green AND `make demo-seed` always produces `epoch=war` even when
world_state already exists as `age_of_peace` (verified by running the seed against a live engine
with a drifted world_state, or by inspection of the patch_node call log).
