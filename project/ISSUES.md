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
