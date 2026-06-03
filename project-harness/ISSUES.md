# Issues Log

Persistent issues log. Read at the start of every session. Updated whenever
work is deferred or completed.

Rules:
- Never reuse IDs.
- Never delete entries. Mark as `[FIXED]` instead.
- Severity: P1 (blocking) | P2 (annoying) | P3 (nice-to-fix).
- New issues get the next monotonic ID.

---

## Open

## [FIXED] ISSUE-050: test_put_world_state_success asserts id=="world" but client uses "world_demo"
**Found:** 2026-06-03, during S7.2 test run
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/test_client.py:479`
**Description:** `test_put_world_state_success` asserts `kwargs["json"]["properties"]["id"] == "world"` but `put_world_state` in `client.py` hardcodes `"world_demo"` (changed by ISSUE-044 fix). The test was not updated when the ID changed.
**Why deferred:** Test failure is pre-existing, not blocking S7.2. Single-line fix.
**To fix:** Change the assertion in `test_put_world_state_success` to `"world_demo"`.
**Fixed:** 2026-06-03, S7.3 — changed assertion to `"world_demo"` in `demo_game/tests/test_client.py:479`.

## [FIXED] ISSUE-049: Give Item action always gives first inventory item — no player choice
**Found:** 2026-06-02, during S4.2 review
**Severity:** P2 (annoying)
**Where:** `demo_game/quest_trade_controller.py` — `handle_give_item` / give-item flow
**Description:** When the player clicks `[Give Item]`, the first item in the player's inventory was given automatically without prompting the player to choose.
**Fixed:** 2026-06-02, S4.2 — added give mode to `InventoryPanelWidget` (clickable rows + Cancel button); added `start_item_pick` to `RightPanelRenderer` (switches to INVENTORY tab, wraps callbacks to restore ACTIONS tab on completion or cancel); removed `get_player_first_item` from `RightPanelRenderer`; updated `game_window.py` callback and event routing. DEC-047 added for right_panel.py line-count exception. 17 new tests.

## [FIXED] ISSUE-048: game_controller.py exceeds 300-line hard limit
**Found:** 2026-06-02, during S3.4
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/game_controller.py` (was 520 lines after S4.1)
**Fixed:** 2026-06-02, S4.2 — extracted `demo_game/action_workers.py` (96 lines) with all worker functions; extracted `demo_game/quest_trade_controller.py` (283 lines) with all quest/trade/give-item handlers. `game_controller.py` is now 297 lines.

---

## [FIXED] ISSUE-035: reputation_dialogue_tone_001 eval fails — merchant archetype doesn't express warmth toward allied player
**Found:** 2026-05-27, during eval repair sprint
**Severity:** P2 (annoying)
**Where:** `evals/cases/reputation_dialogue_tone.yaml`, `prompts/system_v1.yaml` (or equivalent NPC voice prompt)
**Description:** Reputation context is correctly injected (hero_player has standing=80 "allied" with tw_merchants; threshold=20). However `tw_merchant` still responded in a purely transactional tone ("No nonsense, just business") even to an allied player. The tone_judge expects warmth/privilege but a mercantile-archetype NPC produced professional efficiency instead.
**Fixed:** 2026-06-02, S0.5 — chose Option B (strengthen prompt). Rule 2 "allied" bullet in `system_v1.yaml` now mandates three explicit tone shifts even when VOICE_DESCRIPTOR is clipped/transactional: (a) warm/respectful address, (b) skip price caveats, (c) express genuine eagerness. Rule 8 updated to clarify VOICE_DESCRIPTOR governs style only, not mandatory behavioral rules. Removed `skip_until_implemented: true` from eval case. PROMPT_VERSION bumped to `stage_b_v2.6`.

---

## [FIXED] ISSUE-031: Military engine run_tick is a stub
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/military/military_engine.py`
**Description:** `MilitaryEngine.run_tick` returns `{"skipped": True}` with no logic. Battle resolution, resource yield, and depletion tracking are not implemented.
**Why deferred:** User confirmed military tick logic should be deferred; engine is wired for future expansion.
**To fix:** Implement battle resolution (opposing armies at same location → strength comparison, CONTROLS/OCCUPIES edge updates), resource yield (PRODUCES → faction.treasury per tick), and depletion tracking (ResourceNode.depletion decrement).
**Fixed:** 2026-06-03, S6.5 — added `military_battle_service.py` (battle resolution: strength compare, set_controls_location, remove_controls_location, damage, battle Event); added `military_resource_service.py` (resource yield + depletion decrement); added 4 write helpers to `military_writer.py`; replaced stub `military_engine.py` with real orchestration. 21 new tests.

---

## [FIXED] ISSUE-032: OathEngine.check_pledge_violations returns empty list
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/oath/oath_engine.py`
**Description:** Violation scan stub returns `[]` unconditionally. Pledgers whose recent actions conflict with their pledge are never flagged.
**Why deferred:** Violation detection requires cross-referencing PARTICIPATED_IN and WITNESSED edges against pledge semantics — non-trivial scope for initial implementation.
**To fix:** For each active pledge, query pledger's PARTICIPATED_IN and WITNESSED edges since `sworn_at_tick`; check action_type against pledge_type; call `break_pledge` on violation and generate high-severity EVENT.
**Fixed:** 2026-06-03, S2.3 — extracted `pledge_violation_service.py` with `check_pledge_violations()`, `_VIOLATION_ACTIONS`, `_VIOLATION_ROLES`, Cypher queries `CYPHER_GET_WITNESSED_VIOLATIONS`/`CYPHER_GET_PARTICIPATED_VIOLATIONS`, and `_emit_violation_event()`. `oath_engine.run_tick` now queries all active pledgers (not just expiring ones) and calls `check_pledge_violations` for each. Returns `violated_pledges` count. 10 new unit tests.

---

## [FIXED] ISSUE-033: Treaty tribute condition checking does not verify payment
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/treaty_service.py:check_treaty_conditions_mechanical`
**Description:** Tribute conditions detect when payment is due (tick % interval == 0) but do not verify whether payment was actually made. All tribute conditions are flagged as due without checking faction treasury.
**Why deferred:** Payment verification requires faction treasury write operations not yet implemented in this layer.
**To fix:** Query faction treasury, verify amount >= condition.amount, deduct on payment, and only flag as violation if treasury insufficient.
**Fixed:** 2026-06-02, S2.4 — added `check_tribute_payment()` to `treaty_service.py`; reads faction treasury via `get_faction_treasury()`, auto-deducts via `deduct_faction_treasury()`, returns violation only if treasury < required. Updated `check_treaty_conditions_mechanical` to call it; added `_find_payer_faction` helper to identify payer from BOUND_BY parties. Wired condition checks into `TreatyEngine.run_tick` via new `get_all_active_treaty_ids()` query. 8 new unit tests added.

---

## [FIXED] ISSUE-034: SATISFIES_NEED src_type is multi-type (Item or Location)
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/type_registry/base_edges/satisfies_need.yaml`
**Description:** SATISFIES_NEED should accept both Item and Location as source nodes, but the type registry YAML format only supports a single string for `src_type`. Current implementation uses `location` as src_type; Item→Need satisfaction is not schema-registered.
**Why deferred:** Registry extension to support multi-type src_type requires changes to `registry.py` edge model validation — out of scope for Phase 7 L.
**To fix:** Either (a) add an `item_satisfies_need.yaml` edge type for Item→Need, or (b) extend registry to accept `src_type: [location, item]` list syntax.
**Fixed:** 2026-06-01, S0.3 — extended `BaseEdgeTypeDocument.src_type` to `str | list[str]`; `RuntimeEdgeTypeDefinition.src_type` to `str | tuple[str, ...]`; added `resolve_src_label_expr()` helper for Neo4j label-union Cypher; updated validation to check membership; updated `satisfies_need.yaml` to `src_type: [location, item]`.


## [FIXED] ISSUE-022: LLMCache key in demo_game/run.py excludes prompt content
**Found:** 2026-05-24, during P2 iteration
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/run.py` — `LLMCache` key computation (`sha256("{npc_id}:{player_input}")`)
**Description:** The cache key is derived from `npc_id` and `player_input` only. Any change
to `system_v1.yaml`, `npc_voices.yaml`, or the context serialization code does not bust the
cache. After a prompt or code change, stale cached responses continue to be served silently
under `make demo-run ARGS=--cached`. This also means the cache can be poisoned if `make demo-run`
is run before Ollama is up — the engine returns canned "I need a moment to think" strings
which get written to cache as valid LLM responses.
**Why deferred:** Cache busting is a manual step in the S2.8 iteration loop. A
prompt-aware key (e.g. including a hash of the rendered prompt string, or
`PROMPT_VERSION`) would automate this but requires changing how the demo runner
threads prompt state into the cache layer.
**To fix:** Include `PROMPT_VERSION` from `prompt_builder.py` in the cache key:
`sha256("{npc_id}:{player_input}:{PROMPT_VERSION}")`. This automatically invalidates
all cached responses when the prompt version is bumped.
**Fixed:** 2026-06-01, S0.3 — imported `PROMPT_VERSION` from `prompt_builder` in `run.py`; updated `LLMCache._key()` to include it.

## [FIXED] ISSUE-021: test_gossip_propagates_after_clock_advance is trivially true
**Found:** 2026-05-22, during P2.5 planning
**Severity:** P3 (nice-to-fix)
**Where:** `e2e/scenarios/scenario_demo_game_judge.py::test_gossip_propagates_after_clock_advance`
**Description:** The `northern_war_begins` Event node is seeded by `demo_game/seed.py` and
is always present in the graph. `GET /v1/graph/nodes/Event` will return it regardless of
whether a clock advance triggers gossip propagation. The test functions as a basic engine
sanity check (state intact after advance_clock) but does not prove that gossip actually ran.
**Why deferred:** A stronger test (e.g., count KNOWS_ABOUT edges before/after advance, or
check per-NPC belief updates) may be flaky if the gossip engine requires multiple ticks to
propagate knowledge. The war-dialogue test (test 1) is the substantive LLM judge gate for P2.5.
**To fix:** Replace with a two-step test: (1) GET KNOWS_ABOUT edge count before advance,
(2) advance clock, (3) assert edge count increased. OR check that a specific non-captain_sorn
NPC has acquired a new belief mentioning war after the advance.
**Fixed:** 2026-06-01, S0.3 — replaced LLM-judge event-ID check with before/after `KNOWS_ABOUT` edge count assertion (advances 10 ticks, verifies count_after > count_before).

## [FIXED] ISSUE-025: system_v1.yaml Rules 2–7 had dead context key references
**Found:** 2026-05-24, during P2.1 audit
**Severity:** P2 (annoying — rules were silently no-ops; NPC emotion/reputation/goals ignored)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` — Rules 2, 3, 4, 5, 6, 7
**Description:** Five rules referenced paths that do not exist in the serialized context:
`context.player_reputation` (should be `context.reputation`),
`context.npc.emotion.current_mood` (→ `context.emotion.current_mood`),
`context.npc.profile` (→ `context.character`),
`context.npc_known_events` (→ `event:N:npc_id` keyed items),
`context.recent_session_turns` (→ `context.session`),
`context.npc.goals` (→ `context.goals`).
The LLM never saw these fields under the referenced paths so all six behavioral
rules — reputation gating, emotion coloring, persona anchoring, event knowledge,
session continuity, goal surfacing — were effectively no-ops.
**Fixed:** 2026-05-24, P2.3 — all six references corrected in `system_v1.yaml`.

## [FIXED] ISSUE-024: PROMPT_TOKEN_BUDGET hardcoded at 8000 while Ollama context was 4096
**Found:** 2026-05-24, during P2 context debugging
**Severity:** P2 (annoying — engine was building 8000 tokens of context that Ollama silently truncated)
**Where:** `src/npc_engine/config.py` — `PROMPT_TOKEN_BUDGET` field; `src/npc_engine/.env.example`
**Description:** `PROMPT_TOKEN_BUDGET` was left at 8000 (a Mixtral 32K-era value) while the
Ollama instance was configured with a 4096 token context window. The context builder assembled
up to 8000 tokens of NPC context that Ollama then silently truncated on input. NPCs appeared to
have full context in logs but the LLM received a truncated version, causing inconsistent behavior.
**Fixed:** 2026-05-24, P2 — added `OLLAMA_CONTEXT_LENGTH: int = 4096` to `config.py` as the
single source of truth; added `_derive_prompt_token_budget` model_validator that sets
`PROMPT_TOKEN_BUDGET = OLLAMA_CONTEXT_LENGTH - 1200` when not explicitly overridden; updated
`.env.example` to document the derivation.

## [FIXED] ISSUE-023: Event ContextItems had priority below traits/groups/rumors
**Found:** 2026-05-24, during P2.6 iteration (Henryk giving generic response)
**Severity:** P2 (annoying — NPC-specific knowledge events truncated for socially-rich NPCs)
**Where:** `src/npc_engine/retrieval/subgraph_retriever.py` — `assemble_tier_a_context` event loop
**Description:** Event ContextItems were assigned `priority=80 - index`. Traits (83),
group memberships (82), and believed rumors (81) all ranked higher. For NPCs like
`old_henryk` who have multiple social associations, the token budget filled before
reaching the NPC's KNOWS_ABOUT events. The result was a completely generic response
with no reference to the war — as if the NPC had no relevant event knowledge.
**Fixed:** 2026-05-24, P2.6 — priority raised to `89 - index` (above all social context tiers).

## [FIXED] ISSUE-019: 20 pre-existing test failures — `consume()` missing on mock Neo4j result objects
**Found:** 2026-05-21, during P2.1 scaffold (confirmed pre-existing via git stash comparison)
**Severity:** P2 (test coverage gap — affected functions work in prod but are undertested)
**Where:** `tests/unit/test_belief_service.py`, `test_generic_graph_service.py`,
           `test_reputation_queries.py`, `test_world_reader.py`, and others
**Description:** Multiple test mock stubs (e.g. `_FakeResult`, `_SessionStub`, `_FakeSession`)
do not implement `consume()` on their result objects. The production code calls
`await result.consume()` after reading records to properly drain the Neo4j cursor.
The mocks were written before `consume()` calls were added, so they now raise
`AttributeError`. These tests fail consistently in the full `pytest tests/` suite.
`make test` count: 20 failed, 951 passed, 17 skipped (988 total). This contradicts
the NEXT_SESSION.md claim of "964/965" which was likely written counting only passing
test files rather than the full suite.
**Why deferred:** Not blocking Phase 2 — production paths work correctly (consume()
only affects the test stubs). Fixing requires updating mock objects in ~5 test files.
**To fix:** Add a `consume()` async no-op method to each affected mock result class,
e.g. `async def consume(self): pass`. Files to update: `test_belief_service.py`,
`test_generic_graph_service.py`, `test_reputation_queries.py`, `test_world_reader.py`,
and any others in the failing set.
**Fixed:** 2026-05-21 — added `async def consume(self) -> None: pass` to `_ResultStub`/`_FakeResult`
classes in `test_generic_graph_service.py`, `test_reputation_queries.py`, `test_world_reader.py`,
`test_reputation_writer.py`, `test_faction_queries.py`, `test_item_writer_v14.py`,
`test_currency_writer_v14.py`; refactored inline async generators in `test_belief_service.py`
into `_R` wrapper classes with `__aiter__` and `consume`.

## [FIXED] ISSUE-017: Unregistered graph type returns HTTP 500 (plain text) instead of 404/422
**Found:** 2026-05-21, during P2.0 smoke-test
**Severity:** P2 (annoying — misleading error for API consumers)
**Where:** `src/npc_engine/api/routes/graph.py` → `list_nodes` / `list_edges` handlers
**Description:** Requesting a node or edge type not registered in the type registry
(e.g. `GET /v1/graph/nodes/WorldEvent`) returns HTTP 500 with a plain-text
"Internal Server Error" body. The root cause is a `dataclasses.FrozenInstanceError`
in `get_db_session`: when `RegistryPayloadValidationError` (a frozen dataclass) is
raised inside the `async with graph_db.get_session()` block, Python 3.11's
`contextlib.__aexit__` tries to set `exc.__traceback__`, which fails on the frozen
dataclass and masks the original error with a second exception.
**Why deferred:** Not blocking Phase 2 — all required types exist under their
correct names (documented in `phase2_demo_game/decisions.md` DEC-P2-03). A proper
fix requires either making `RegistryPayloadValidationError` non-frozen or catching
it in the route handler before the session context manager unwinds.
**To fix:** Catch `RegistryPayloadValidationError` (and similar registry errors)
in `list_nodes` / `list_edges` route handlers before the DB session context exits,
or make the exception class inherit from a non-frozen base. Return 422 with a JSON
body matching the existing error envelope format.
**Fixed:** 2026-05-21 — wrapped `service.list_nodes()` and `service.list_edges()` calls in
`src/npc_engine/api/routes/graph.py` with `try/except RegistryPayloadValidationError` raising
`graph_error_to_http(error)`, matching the existing pattern in POST/PATCH handlers. Added
regression tests `test_list_nodes_unknown_type_returns_422` and
`test_list_edges_unknown_type_returns_422` in `tests/unit/test_graph_warning_pipeline.py`.

## [FIXED] ISSUE-018: subphases.md uses wrong graph type names (WorldEvent, TRUSTS, FEARS, HAS_BELIEF, HAS_GOAL)
**Found:** 2026-05-21, during P2.0 smoke-test
**Severity:** P2 (would cause P2.2/P2.4 code to target non-existent endpoints)
**Where:** `project/roadmap3/phase2_demo_game/subphases.md` — P2.2 and P2.4 steps
**Description:** The subphases plan refers to type names that are not registered in
the type registry. Actual registered equivalents:
`WorldEvent` → `Event`; `WorldState` (capital S) → `world_state` (lowercase);
`TRUSTS` → `STANDS_WITH`; `FEARS` → `OPPOSES`; `HAS_BELIEF` → `BELIEVES`;
`HAS_GOAL` → `PURSUES`.
**Why deferred:** Correction is captured in `phase2_demo_game/decisions.md`
DEC-P2-03. The subphases.md document is a planning artefact; correcting all
inline references now would risk churn. P2.2 and P2.4 implementations will use
the correct names directly.
**To fix:** When Phase 2 is done, do a single pass over `subphases.md` to replace
the planned names with the actual names so the document is accurate for reference.
**Fixed:** 2026-05-21 — replaced all wrong type names in `project/roadmap3/phase2_demo_game/subphases.md`
(11 occurrences: WorldEvent→Event, WorldState→world_state, TRUSTS→STANDS_WITH, FEARS→OPPOSES,
HAS_BELIEF→BELIEVES, HAS_GOAL→PURSUES) and 1 occurrence in `README.md` (WorldState→world_state).
`decisions.md` left intact — it intentionally documents the mapping for historical reference.

## [FIXED] ISSUE-016: test_gossip_rumor_integration mock collision — KeyError 'secret_id'
**Found:** 2026-05-18, during Phase 5 full-suite run
**Severity:** P2 (annoying — 1 failing test)
**Where:** `tests/unit/test_gossip_rumor_integration.py::test_knows_about_still_created_alongside_rumor`
**Description:** `trust_record.__getitem__` lambda only maps `"trust"` → 5; when the gossip
handler reuses the same mock for the secret query, `secret_record["secret_id"]` raises
`KeyError: 'secret_id'`. The test mock setup leaks into the secret-propagation branch.
**Why deferred:** Pre-existing before Phase 5; not introduced by this session's changes.
**To fix:** Give the secret query its own distinct mock result with `secret_id` and `severity` keys.
**Fixed:** 2026-05-19 — added `patch("...gossip_handler.random") as mock_random` with
`mock_random.random.return_value = 1.0` in `test_knows_about_still_created_alongside_rumor`
to suppress the secret-propagation branch, matching the pattern already used in
`test_gossip_handler_calls_propagate_always`.

## [FIXED] ISSUE-011: `.env` NEO4J_URI is container DNS — migration script breaks if `.env` is sourced
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P3 (nice-to-fix)
**Where:** `.env` line 1 (`NEO4J_URI=bolt://neo4j:7687`), `scripts/migrations/add_faction_support.py`
**Description:** `.env` sets `NEO4J_URI=bolt://neo4j:7687` (container hostname). If a user
sources `.env` into the shell before running the migration script from outside Docker,
the Neo4j connection fails — `neo4j` hostname is only resolvable inside the Docker network.
The migration script already defaults to `localhost:7687` via `os.getenv()`, but the trap
is invisible unless documented.
**Why deferred:** Documentation-only fix; no code change required.
**To fix:** Documented in `docs/API.md` under "Migration script" section. Optionally add a
prominent comment in `.env` warning against sourcing it for outside-Docker tooling.
**Fixed:** 2026-05-19 — added inline comment to `.env` on the `NEO4J_URI` line:
`# Docker container hostname — do NOT source this file from the host`.

## [FIXED] ISSUE-004: edge_updater.py — no-any-return from dump_json
**Found:** 2026-05-06, during Phase 1.2 (faction-aware gossip)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/edge_updater.py:45`
**Description:** `dump_json()` returns `Any`, so `return dump_json(...)` on a function
declared `-> str` triggers `mypy [no-any-return]`. Pre-existing before Phase 1.
**Why deferred:** Not introduced by Phase 1 changes; low risk.
**To fix:** Add `cast(str, dump_json(...))` on the return line, or annotate `dump_json` as `-> str`.
**Fixed:** 2026-05-19 — `dump_json` in `common/json_utils.py` is already annotated `-> str`; the mypy error is not reproducible. No code change required.

## [FIXED] ISSUE-005: adjust_reputation_for_event not wired to event engine
**Found:** 2026-05-06, during Phase 1.3 planning
**Severity:** P3 (nice-to-fix)
**Where:** Future `src/npc_engine/graph/reputation_writer.py` (Phase 1.3)
**Description:** `adjust_reputation_for_event` will be implemented in 1.3 but the
event engine wiring that calls it (e.g., killing a faction member → -20 reputation)
is out of scope for Phase 1. The function will exist but never be triggered automatically.
**Why deferred:** Requires engine changes belonging to a later phase.
**To fix:** Wire in a future event-processing phase that calls `adjust_reputation_for_event`
based on event type + target faction membership.
**Fixed:** 2026-05-19 — added optional `faction_id`/`reputation_delta` fields to `EventTemplate`
and `event.yaml`; wired `adjust_reputation_for_event` in `EventHandler.run_tick` for all characters
at the event location when the template carries these fields; added 5 unit tests in
`test_event_reputation_wiring.py`; annotated 3 event templates (`evt_05_keep_drill`,
`evt_10_guard_desertion`, `evt_06_tax_riot`) with faction/delta values.

## [FIXED] ISSUE-006: character.faction string field not migrated to MEMBER_OF edges
**Found:** 2026-05-06, during Phase 1.1 (faction nodes)
**Severity:** P3 (nice-to-fix)
**Where:** Existing Character nodes with a `faction` string property
**Description:** The migration script only adds the Faction node uniqueness constraint.
Pre-existing `character.faction` string fields are not converted to MEMBER_OF edges,
since that mapping is game-data-specific.
**Why deferred:** Needs operator-supplied mapping of faction name strings to Faction node IDs.
**To fix:** Provide a game-specific migration that reads character.faction, resolves it to
a Faction node ID, and creates the MEMBER_OF edge.
**Fixed:** 2026-05-19 — created `scripts/migrations/migrate_faction_strings.py`; finds
unmigrated Characters, validates all referenced Faction nodes exist (fails fast if any are
missing), creates MEMBER_OF edges; supports `--dry-run` flag.

## [FIXED] ISSUE-015: FactionPoliticsEngine CAUSED_BY retrofit deferred
**Found:** 2026-05-18, during Phase 4.2 (CAUSED_BY retrofit)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/faction_politics/faction_politics_engine.py`
**Description:** EventHandler and QuestGenerationEngine are wired with CAUSED_BY edges.
FactionPoliticsEngine is not — it calls `set_standing()` but the triggering event has no
dedicated graph node to link as `effect_node_id`. A `FactionStandingEvent` node type is
needed before this can be retrofitted cleanly.
**Why deferred:** Requires a new node schema and migration; out of Phase 4 scope.
**To fix:** Define `FactionStandingEvent` node type in the type registry, write it during
`set_standing()`, then add `record_causation(session, effect_node_id=..., cause_event_id=...)`.
**Fixed:** 2026-05-18, Phase 5.3 — `FactionStandingEvent` node and `faction_history_service`
created; `faction_politics_engine` now calls `record_standing_change` after each `set_standing`,
with `cause_event_id` and `cause_rule_id` written for full traceability. tick_id passed through.

## [FIXED] ISSUE-014: WAS_AT `arrived_at_tick` uses current tick as approximation
**Found:** 2026-05-18, during Phase 4.1 (WAS_AT edge)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/routine/routine_engine.py` — `record_departure` call site
**Description:** `arrived_at_tick` is set to `tick_id` (the departure tick) because LOCATED_AT
edges do not store an arrival tick. The true arrival time is unknown at departure time.
`tick_duration` is consequently always 0.
**Why deferred:** Tracking arrival tick requires writing it when `update_character_location`
runs; that is a separate schema addition.
**To fix:** Add `arrived_at_tick: int` to the LOCATED_AT edge schema; write it in
`update_character_location`; read it back in the routine engine before calling `record_departure`.
**Fixed:** 2026-05-18, Phase 5 — added `arrived_at_tick` to `CYPHER_GET_SCHEDULED_CHARACTERS`
and `CYPHER_UPDATE_LOCATED_AT`; `update_character_location` now accepts and writes the tick;
`routine_engine` reads `current_arrived_at_tick` from the row with fallback to `tick_id`.

## [FIXED] ISSUE-013: `how_long_ago` has no defined bucket for 7–27 day distances
**Found:** 2026-05-11, during Phase 3.1 (time_utils.py)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/world/time_utils.py` — `how_long_ago`
**Description:** The ROADMAP spec defines buckets for 0, 1, 2–6, 28, and >28 days but omits
7–27. Current implementation extends "a few days ago" to cover 2–27. See DECISIONS.md entry.
**Why deferred:** Spec ambiguity; not blocking any feature.
**To fix:** Agree on wording (e.g., "a week or two ago") and add a 7–27 bucket in time_utils.
**Fixed:** 2026-05-19 — split bucket: 2–6 → "a few days ago" (unchanged), 7–27 → "a few weeks ago"
(new); updated docstring and added `test_how_long_ago_few_weeks` unit test in
`test_world_time_service.py`.

---

## Closed

## [FIXED] ISSUE-012: `time_of_day`, `year`, `season`, `day` not persisted before Phase 3.1
**Found:** 2026-05-11, during Phase 3.1 (world_writer.py audit)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/world/world_writer.py`, `src/npc_engine/engines/events/event_handler.py`
**Description:** Both `CYPHER_MERGE_WORLD_STATE` constants omitted `time_of_day` from their SET
clauses; the new `year`, `season`, `day` fields were also absent. Time fields were never written
to the graph, so they reset to defaults on each server restart.
**Why deferred:** Pre-existing; discovered during 3.1 schema update.
**To fix:** Add all four time fields to both SET clauses and their `session.run()` call sites.
**Fixed:** 2026-05-11, Phase 3.1 — world_writer.py and event_handler.py updated.

## [FIXED] ISSUE-010: `seed.py` seeds via direct Neo4j, not the external API
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (misses client-parity)
**Where:** `src/npc_engine/data/seed.py` (deleted)
**Description:** `make seed` connected directly to Neo4j via Bolt, bypassing the API
entirely. Breaks if Neo4j port is restricted and doesn't exercise the public API surface.
**To fix:** New `src/npc_engine/data/api_seeder.py` seeds via HTTP API. Old `seed.py` and
`seed_queries.py` deleted. Makefile `seed:` target replaced by `seed-api:`.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-009: `scenario_reputation_drift.py` calls non-existent `POST /v1/admin/characters/`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking scenario)
**Where:** `e2e/scenarios/scenario_reputation_drift.py`
**Description:** Character creation called `POST /v1/admin/characters/` which does not exist.
Characters must be created via `POST /v1/graph/nodes/Character` with `{"properties": {...}}`.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-008: `conftest.py` default API key does not match dev `.env`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:42`
**Description:** Default `NPC_API_KEY` was `eval-key-change-me`; dev key is
`local_dev_secret_change_this_2026`. Scenarios failed with 401 without explicit env export.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-007: `conftest.py` uses `X-API-Key` header instead of `Authorization: Bearer`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:48`
**Description:** httpx default header was `X-API-Key: {key}`. The middleware only accepts
`Authorization: Bearer <token>` — all scenario requests returned 401.
**Fixed:** 2026-05-11, api-based-seeding task — changed to `Authorization: Bearer {api_key}`.

## [FIXED] ISSUE-001: top_p and stop_sequences stored but not forwarded to adapters
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/llm/factory.py`, all adapter `generate`/`stream` call sites
**Description:** `EngineModelConfig.llm` declares `top_p` and `stop_sequences` fields
(required by ROADMAP 0.4 schema), but none of the LLM adapters accept these parameters.
The values are stored in config but silently ignored when building generation calls.
**Why deferred:** Adapters need interface updates (protocol + all implementations). Not
blocking — default adapter behaviour is acceptable for current backends.
**To fix:** Add `top_p: float` and `stop_sequences: list[str]` to `LLMClientProtocol.generate`
and `stream` signatures; update all adapters; forward from `DialogueLLMClient`.
**Fixed:** 2026-05-06, stability_refactor — added optional `top_p`/`stop_sequences` to all
three protocol methods; updated OllamaAdapter (forwarded to `options`), MistralAdapter
(forwarded to payload), MockLLMAdapter (accepted, ignored); `DialogueLLMClient` stores and
forwards both params; `DialogueHandler` passes them from `engine_model_config.llm`.

---

## [FIXED] ISSUE-002: currency_engine contract name vs economy/ directory mismatch
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/contracts/currency_engine.yaml`,
`src/npc_engine/engines/economy/`
**Description:** `_engine_dir_from_contract_name("currency_engine")` → `"currency"`,
but the actual engine directory is `engines/economy/`. If `currency_engine` ever
gains `uses_llm: true`, `get_config("currency")` will look in the wrong directory.
Currently `uses_llm: false` so there is no runtime failure.
**Why deferred:** Not blocking today. Renaming the directory requires touching imports.
**To fix:** Either rename the contract to `economy_engine` or rename the directory to
`engines/currency/` and update all imports. Coordinate with any planned economy feature work.
**Fixed:** 2026-05-06, stability_refactor — renamed `engines/economy/` → `engines/currency/`;
updated `__init__.py` docstring. No import changes needed (directory was empty stub).

---

## [FIXED] ISSUE-003: OLLAMA_MODEL in Settings is superseded by per-engine model declaration
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/config.py` (`OLLAMA_MODEL` field),
`src/npc_engine/engines/llm/factory.py` (`create_llm_client`)
**Description:** `Settings.OLLAMA_MODEL` was the global model name used by the Ollama
adapter. The new `create_llm_client_for_engine` reads the model from `engine_config.llm.model`
instead, making `OLLAMA_MODEL` redundant for all engines that use the new factory path.
`OLLAMA_MODEL` is still read by the legacy `create_llm_client` function which remains for
backward compat.
**Why deferred:** Removing it requires auditing all remaining callers of `create_llm_client`
and may affect tests that construct Settings with this field.
**To fix:** After all call sites migrate to `create_llm_client_for_engine`, remove
`OLLAMA_MODEL` from `config.py` and delete the legacy `create_llm_client` function.
**Fixed:** 2026-05-06, stability_refactor — confirmed zero callers of `create_llm_client`;
removed `create_llm_client`, `BACKEND_BUILDERS`, and all private `_create_*` helpers from
`factory.py`; removed `OLLAMA_MODEL` and `LLM_BACKEND` from `config.py`; rewrote
`test_llm_factory.py` to target `create_llm_client_for_engine`.

---

## [FIXED] ISSUE-020: `emotion` field in DialogueTurn mapped from `mood_update`, not a first-class engine field
**Found:** 2026-05-22, during P2.3 implementation
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/dialogue.py:parse_dialogue_response`
**Description:** The P2.3 spec requested extracting an `emotion` field from
`POST /v1/dialogue` responses, but `DialogueResponse` has no `emotion` field.
`parse_dialogue_response` maps `DialogueTurn.emotion` from `mood_update: str | None`,
with a fallback to `facial_expression["type"]`. This is semantically close but not
identical to a dedicated emotion field.
**Why deferred:** The engine has no plans to add a dedicated `emotion` field. The
current mapping is good enough for demo badge display and does not affect correctness.
**To fix:** If the engine adds a dedicated top-level `emotion` field, update
`parse_dialogue_response` to read it directly and remove the fallback logic.
**Fixed:** 2026-06-01, S0.3 — added `emotion: str | None` to `DialogueResponse` with `model_validator` deriving it from `mood_update`; updated `parse_dialogue_response` to read `raw.get("emotion")` directly.

---

## [FIXED] ISSUE-035: `tone_judge` matcher is stubbed — all tone/voice evals silently skip
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-26 (R1.1)
**Severity:** P1 (blocking eval expansion)
**Where:** `evals/matchers.py`
**Description:** The `tone_judge` matcher returned `(True, "SKIP")` unconditionally. Every eval case checking voice or tone reported a false pass.
**Fix:** Replaced stub with synchronous Ollama HTTP call in `_eval_tone_judge`. Reads `judge_prompt` (falls back to `description`) from expectation YAML. Returns `(True/False, reasoning)`. Config via `JUDGE_OLLAMA_URL`, `JUDGE_MODEL`, `JUDGE_TIMEOUT_SECONDS` env vars.

---

## [FIXED] ISSUE-036: NPC voice is a YAML lookup, not a graph property — prompt is not NPC-agnostic
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-27 (R1.4)
**Severity:** P1 (architectural)
**Where:** `src/npc_engine/engines/dialogue/prompt_builder.py:31–44`, `src/npc_engine/prompts/dialogue/npc_voices.yaml`
**Description:** `_get_voice(npc_id)` looked up voice in a hardcoded YAML file. New NPCs without an entry got `_default` — a generic descriptor that produced undifferentiated responses. Every new NPC required a YAML edit. The dialogue prompt was not truly NPC-agnostic.
**Fix:** Added `voice_descriptor: { type: str, required: false }` to `character.yaml`. Pulled it in `get_character_with_relations()`. Included in serialized context. Updated `prompt_builder.py` to read from context instead of YAML. Updated all seed scripts to set `voice_descriptor` on Character nodes. Deprecated `npc_voices.yaml`.

---

## [FIXED] ISSUE-037: No negative test cases — behavioral constraints are untested
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-26 (R1.2)
**Severity:** P1 (coverage gap)
**Where:** `evals/cases/`
**Description:** All existing eval cases tested "should contain X". No cases tested "should NOT contain X" (e.g., NPC should not mention events they don't KNOWS_ABOUT, hostile NPCs should not offer help). Critical behavioral guards (knowledge guard Rule 5, reputation gate Rule 2) had no test coverage.
**Fix:** Added `keyword_none` matcher to `evals/matchers.py` and created 10 negative eval cases (`evals/cases/case_neg_*.yaml`) covering: knowledge hallucination, voice bleed, role bleed, gossip framing, and self-incrimination. All 17/17 eval cases pass.

---

## [FIXED] ISSUE-038: Existing eval cases reference unseeded NPCs
**Found:** 2026-05-26, during R1.1 implementation
**Fixed:** 2026-05-27 (R1.3)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_001_grieving_elder.yaml`, `evals/cases/case_002_suspicious_guard.yaml`, `evals/cases/reputation_dialogue_tone.yaml`
**Description:** NPCs `elder_1`, `guard_1`, `blacksmith_npc` were not seeded in the default dev setup. All expectations in these cases (including the now-live `tone_judge`) failed at the API-call level rather than exercising matcher logic.
**Fix:** Created `seeds/world/seed_village_world.py` (vw_ prefix) and `seeds/world/seed_tavern_world.py` (tw_ prefix). Updated cases: `elder_1`→`vw_elder` (location `vw_village_square`), `guard_1`→`vw_guard` (location `vw_gate`), `blacksmith_npc`→`tw_merchant`. All three cases now have `requires_world:` set. Run `make seed-village-world` + `make seed-tavern-world` before `make eval`.

---

## [FIXED] ISSUE-039: Voice eval cases require demo-seed with no enforcement
**Found:** 2026-05-26, during R1.1 implementation
**Fixed:** 2026-05-27 (R1.3)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_voice_captain_sorn.yaml`, `evals/cases/case_voice_mira_innkeeper.yaml` (and all demo-seed-dependent cases)
**Description:** `captain_sorn` and `mira_innkeeper` were only present after `make demo-seed`. Running `python evals/runner.py` on a fresh server silently failed these cases with no hint that seeding was needed.
**Fix:** Added `requires_world` field to eval case YAML (e.g. `requires_world: demo`). `runner.py` now prints a `[WARN]` line with the exact seed command to stderr whenever a case with `requires_world` fails at the API level. Added `requires_world: demo` to all 13 demo-seed-dependent cases. New tavern/village cases use `requires_world: tavern` and `requires_world: village` respectively.

---

## [FIXED] ISSUE-040: Demo seed tests assert upsert_edge.call_count == 0 but _seed_edge always upserts
**Found:** 2026-05-27, during R1.4 test run
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/test_seed.py:252–255` (`test_seed_all_skips_existing_edges`) and `:302–305` (`test_seed_all_created_is_zero_when_all_exist`)
**Description:** `_seed_edge` is documented to "always write the latest properties" and always returns "created". These two tests assert that `upsert_edge` is never called and that `created == 0` when all nodes exist — incompatible with the current implementation. Pre-existing: both tests fail on the baseline commit before R1.4.
**Why deferred:** Pre-existing; tests don't gate the eval path. No functional regression.
**To fix:** Either (a) update the tests to assert actual edge upsert counts, or (b) add skip-if-exists logic to `_seed_edge` and keep the tests as written.
**Fixed:** 2026-06-01, S0.3 — verified `_seed_edge` already has skip-if-exists logic; both tests were already passing. Also fixed 3 related pre-existing failures (`test_seed_quests_*`) caused by the seeder switching from LLM generation to deterministic `post_quest_offer` path.

---

## ISSUE-041: Demo seed creates WorldState id="ws_main" but world_reader defaults to id="world"
**Found:** 2026-05-27, during R2.2 eval investigation
**Severity:** P2 (annoying)
**Where:** `seeds/worlds/seed_demo_world.py` (`_WORLD_STATE_ID = "ws_main"`), `src/npc_engine/world/world_reader.py:37` (`world_id: str = "world"`)
**Description:** The demo seed created a WorldState node with `id="ws_main"` but `get_world_state()` queried for `id="world"` by default. The demo world's epoch and active_conditions were therefore never read by the context builder — all dialogue requests received a default empty WorldState. Rule 1 epoch constraints never fired for demo world NPC queries.
**Fixed:** 2026-05-27, pre-Phase 3 cleanup — changed `_WORLD_STATE_ID = "world"` in `seeds/worlds/seed_demo_world.py`. Both the seed and reader now use `"world"` as the canonical WorldState id. Logged as DEC-022.

---

## [FIXED] ISSUE-042: faction_gossip_distortion eval case has no runnable endpoint
**Found:** 2026-05-27, during pre-Phase 3 eval coherence review
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/faction_gossip_distortion.yaml`, `evals/runner.py`
**Description:** `faction_gossip_distortion_001` targets a gossip distortion calculation endpoint that does not exist in the API. It has no `input` field so the eval runner auto-skips it with "SKIP: no 'input' field — case targets a non-dialogue endpoint". The case documents the expected gossip distortion logic and probabilities, but cannot be exercised by the current runner.
**Why deferred:** The gossip engine exists but has no dedicated eval endpoint. The case is valuable documentation.
**To fix:** Expose a `/v1/gossip/distort` endpoint (or similar) and extend the runner to POST to it when the case has a non-dialogue `endpoint` field. Alternatively, convert to a unit test against `GossipEngine.distort()`.
**Fixed:** 2026-06-01, S0.3 — deleted `faction_gossip_distortion.yaml`; added 3 unit tests to `tests/unit/test_gossip_distort.py` covering hostile-faction distortion, level range, and canonical-event bypass.

---

## [FIXED] ISSUE-044: Multi-world WorldState conflict — single id="world" is last-seed-wins
**Found:** 2026-05-27, during eval failure investigation
**Severity:** P2 (annoying)
**Where:** `seeds/worlds/seed_demo_world.py`, `seeds/worlds/seed_village_world.py`, `world_reader.py`
**Description:** All seed worlds write their WorldState to `id="world"`. Village seed sets `epoch="age_of_peace"` + `active_conditions=["crop_blight"]`; demo seed sets `epoch="war"` + `active_conditions=["northern_war"]`. Last seed run wins. Running `make seed-village-world` after `make demo-seed` causes demo world eval cases that depend on war epoch (`case_voice_captain_sorn_001`, `case_pos_mira_gossip_hedging`) to fail silently.
**Why deferred:** Mitigation: run `make demo-seed` last before `make eval`. Proper fix requires WorldState ID refactor.
**To fix:** Either (a) prefix WorldState IDs per world (`id="world_demo"`, `id="world_village"`) and extend `world_reader` to accept a configurable ID via eval case `seed` block, or (b) add a per-eval-run world-state setup POST before running cases.
**Fixed:** 2026-06-01, S0.4 — added `WORLD_ID: str = "world_demo"` to `Settings`; changed `demo_game/seed.py` `_WORLD_STATE_ID` to `"world_demo"`, `seed_village_world.py` to `"world_village"`; fixed `world_reader.py` fallback to return `WorldState(id=world_id)`; threaded `world_id` through all 8 `get_world_state` call sites (context_builder, dialogue_handler, event_handler ×2, clock route, quest_generation_engine, story_pacing_engine, tick_scheduler, chapter_engine). Configure per-world reads via `WORLD_ID` in `.env`.

---

## [FIXED] ISSUE-045: game_window.py line count exceeds DEC-024 ~450 soft limit
**Found:** 2026-05-28, during S3.4
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/ui/game_window.py` (~460 lines after S3.4)
**Description:** DEC-024 set a ~450-line soft limit for `game_window.py` (exempt from the 300-line hard limit). S3.4 adds ~24 lines, bringing the total to ~460.
**Why deferred:** Phase 4 `DialoguePanel` / `GraphPanel` refactor is the natural moment to extract rendering logic into separate panel classes. Splitting mid-session (between S3.4 and S3.5) would be artificial churn.
**To fix:** During Phase 4, extract `_draw_left_panel` helpers and/or the graph/sidebar draw branches into dedicated panel classes (`DialoguePanel`, `GraphPanel`, `SidebarPanel`). Each class gets its own file under `demo_game/ui/`.
**Fixed:** 2026-06-01, S0.3 — extracted thread/poller orchestration, queue dispatch, and quest/trade callbacks into new `demo_game/game_controller.py` (389 lines). `game_window.py` reduced from 624 → 260 lines.

---

## [FIXED] ISSUE-043: requires_world is a soft advisory warn, not a hard skip
**Found:** 2026-05-27, during pre-Phase 3 eval coherence review
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py:91–103`
**Description:** When a request fails and the case has `requires_world`, the runner prints a `[WARN]` hint but still marks the expectation FAIL. There is no explicit SKIP for "server is up but world not seeded" vs "server is down". A CI run with the wrong seed state produces unexplained failures rather than a clear skip with a seed-world instruction.
**Why deferred:** Current behavior is informative enough for manual runs. CI is not yet set up with per-world seed fixtures.
**To fix:** If the response is a 4xx with an NPC-not-found body, auto-skip all expectations and emit a clear SKIP reason rather than a FAIL. Or add a pre-flight `GET /v1/graph/nodes/Character/{npc_id}` check and skip if the NPC is absent.
**Fixed:** 2026-06-01, S0.3 — added pre-flight `GET /v1/graph/nodes/Character/{npc_id}` check in `evals/runner.py`; returns hard SKIP (passed=True, skipped=True) with seed command hint when NPC is absent (HTTP 404).

---

## [FIXED] ISSUE-046: GET /v1/economy/price endpoint not yet verified against running engine
**Found:** 2026-05-29, during S4.4 trade price implementation
**Severity:** P2 (annoying)
**Where:** `demo_game/client.py` — `get_item_price()`, `demo_game/ui/left_panel.py` — `set_trade_price()`
**Description:** `get_item_price()` calls `GET /v1/economy/price?item_type=spice&character_id=aldric_merchant`. The endpoint was assumed to exist from the plan; it has not been tested against a live engine. If the route is absent or has a different schema, the trade overlay will silently show nothing (non-fatal, error caught), but the demo feature won't function.
**Why deferred:** Required live engine + seeded Item node. Verification is a 5-minute manual check — deferred to pre-demo run.
**To fix:** Start engine + `make demo-seed`, then `curl "http://localhost:8000/v1/economy/price?item_type=spice&character_id=aldric_merchant"`. If 404: check route in `src/npc_engine/api/` and update the URL. If schema differs: update `get_item_price()` to match actual response shape.
**Fixed:** 2026-06-02, S2.4 — verified statically: `economy_router` is registered at `admin_prefix` (`/v1/admin`) with its own `/economy` prefix, so the route is `GET /v1/admin/economy/price`. `demo_game/client.py:get_item_price()` already calls exactly `/v1/admin/economy/price`. No code change needed.

---

## [FIXED] ISSUE-047: Multiple stale demo test expectations after API path + seeder changes
**Found:** 2026-06-01, during S0.3 (discovered while running `make test-demo`)
**Severity:** P2 (test suite not green)
**Where:** `demo_game/tests/test_client.py`, `demo_game/tests/test_seed.py`, `demo_game/tests/test_right_panel.py`
**Description:** Several tests expected outdated API paths and function signatures accumulated since the demo was extended. 5 client tests expected `/v1/quests/generate`, `/v1/quests/{id}`, `/v1/economy/price` but the client moved to `/v1/admin/` prefixed routes. `post_quest_offer` grew 3 new required args (objectives, item_rewards, currency_reward). 3 seed tests expected LLM-based quest generation but seeder switched to deterministic `post_quest_offer`. 2 right panel tests expected 4 enum values but `RightPanel` grew to 6.
**Fixed:** 2026-06-01, S0.3 — updated all stale test expectations to match current implementation; `test_seed_quests_*` and `test_seed_all_calls_quest_generation` rewritten to test `post_quest_offer` deterministic path; `test_right_panel_enum_has_four_values` → `_has_six_values`; `test_cycle_tab_wraps_back_to_graph` cycle count derived from `len(list(RightPanel))`.

---

<!--
Template for a new issue:

## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 | P2 | P3
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.

When fixed, change the heading to:
## [FIXED] ISSUE-NNN: <short title>
And add:
**Fixed:** YYYY-MM-DD, in <commit/task>
-->
