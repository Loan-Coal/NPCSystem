# FIX-SEV-24 — GraphRepository facade (engines depend on graph by interface)

**Severity:** LARGE (architecture) · **Decision:** DEC-122 · **Multi-phase** · **Follow-on to SEV-21**

## Problem
After SEV-21 the graph layer owns transactions, but engines still import concrete graph functions and
receive an `AsyncSession` per `run_tick` — 68 engine files reference `neo4j`. The graph layer is therefore
not a swappable boundary: you cannot interpose a cache, swap the DB, or split graph into a microservice
without touching every engine. Goal: engines depend on a small abstraction; the Neo4j implementation owns
the session.

## Port granularity: per graph-DOMAIN repositories (DEC-122, decided 2026-06-15)
Ports are organized by **graph domain** and live together in `engines/ports/<domain>_port.py`; engines
compose the domain Ports they need. Shared readers (`world_state_reader` x8, `relation_reader`,
`player_location_reader`, `character_reader`) become a single shared domain Port reused across engines.

## Pattern (one engine/cluster per commit)
1. **Port Protocol** in `engines/ports/<domain>_port.py`: small, domain-typed methods, **no Neo4j types**.
   The engine imports the Port and depends on it.
2. **Neo4j adapter** in `graph/repositories/<domain>_repository.py`: holds the injected `GraphDB`, opens a
   session per operation (`await graph_db.connect(); async with graph_db.get_session() as session: …`),
   delegates to existing query/writer functions, and (for multi-write atomic ops) uses
   `transaction_coordinator.run_in_tx`. Conforms to the Port **structurally** (no import of the engine Port —
   keeps graph from importing engines).
3. **Engine**: take the Port via `__init__` (DIP); replace direct graph calls with `self._<repo>.method(...)`;
   drop the `session` usage. Keep `run_tick(..., **_)` so the scheduler's `session=` kwarg is accepted and
   ignored during migration.
4. **Composition root** (`api/dependencies*.py`): construct the adapter from `get_graph_db()` and inject it;
   mypy verifies structural conformance here.
5. **Tests**: engine tests mock the Port (no session); add an adapter unit test with a fake `GraphDB`.

## Migrated slices
- **need** (DONE, `c96476e`): `engines/ports/need_port.NeedGraphPort` +
  `graph/repositories/need_repository.Neo4jNeedRepository`; `NeedDecayEngine` migrated. (Port relocated from
  `engines/need/need_graph_port.py` → `engines/ports/` when the shared package was established.)
- **mood** (DONE, `55f0b83`): `MoodGraphPort` + `Neo4jMoodRepository`; `MoodContagionEngine` migrated.
- **clique** (DONE, `3539faa`): `GroupGraphPort` + `Neo4jGroupRepository`; `CliqueFormationEngine` migrated.
- **skill** (DONE, `6fa83e3`): `SkillGraphPort` + `Neo4jSkillRepository`; `SkillProgressionEngine` migrated
  (added the first behavioral unit test — was construction-only).
- **routine** (DONE, `46b7e58`): `RoutineGraphPort` + `Neo4jRoutineRepository`; `RoutineEngine` migrated
  (folds `record_departure` from the location-history domain).
- **succession** (DONE, `81b0feb`): `PoliticalGraphPort` + `Neo4jPoliticalRepository`; `SuccessionEngine`
  migrated (extracted `_grant_to_successor` to stay under R006; ratcheted baseline 143->142).
- **agenda** (DONE, `df6dd0e`): **reuses** the political port/adapter (extended with 3 agenda methods);
  `AgendaEngine` migrated — the per-graph-domain payoff (one repository, two engines).
- **story_pacing** (DONE, `5c2c9b9`): `StoryPacingGraphPort` + the **shared** `WorldStateGraphPort`
  (`get_world_state`/`upsert_world_state`, reusable by the ~8 world-state consumers) + their adapters.
- **treaty** (DONE, `7ab17a8`): `TreatyGraphPort` + `Neo4jTreatyRepository` (extracted `_count_active_violations`
  for R006); added a behavioral test (was construction-only).
- **oath** (DONE, `58c6fca`): `PledgeGraphPort` + `Neo4jPledgeRepository` (mirrors treaty; `_count_violations`).
- **memory_consolidation** (DONE, `c988521`): `MemoryConsolidationGraphPort` + `Neo4jMemoryConsolidationRepository`
  (single-domain port spanning belief/memory/witness reads + the Memory write; engine drops `graph_db`/session,
  fan-out helper renamed `_consolidate_bounded`). Wave 1 first checkbox.
- **chapter** (DONE, `e167a53`): `ChapterGraphPort` + `Neo4jChapterRepository` (chapter_queries x5 +
  chapter_writer x3 + faction_queries `get_faction_standings_summary`) **reusing the shared `WorldStateGraphPort`**
  for the world_state read; engine injects both ports, `run_tick(*, tick_id, **_)` swallows `session=`; extracted
  `_transition_chapter` for R006 (baseline 142->141) and named the link-severity magic number.

- **military** (DONE, `4fc8b08`): `MilitaryGraphPort` + `Neo4jMilitaryRepository` (military_queries x3 +
  military_control_writer x4 + military_writer x2). CLUSTER: the graph calls live in the two module-level
  service functions, so the port is injected as the FIRST positional arg of `resolve_battles` /
  `process_resource_yield` (+ their private helpers); `MilitaryEngine` holds the port and forwards it,
  `run_tick(*, tick_id=0, **_)` swallows `session=`. Repointed the SEV-04 `_emit_battle_event` delegation
  guard to the port. Wave 1 complete.

- **shared-read-ports** (DONE, `ebdb72c`): `RelationReadPort` + `PlayerLocationReadPort` + `CharacterReadPort`
  (`engines/ports/`) and their `Neo4jRelationReadRepository`/`Neo4jPlayerLocationReadRepository`/
  `Neo4jCharacterReadRepository` adapters (`graph/repositories/`, session-per-call, delegate to
  RelationReader / PlayerLocationReader / character_reader.get_npc_ids). Adapters+tests only — NOT wired into
  any engine yet; reputation/player_model/director/proactive_dialogue slices inject these to drop their
  per-tick reader construction. Tests: `tests/unit/test_shared_read_repositories.py`.

- **emotion** (DONE, `cdeffc1`): `EmotionGraphPort` (write-through, no session) + `Neo4jEmotionRepository`
  (holds its own stateless `EmotionGraphWriter`, session-per-call). `EmotionUpdater` now takes the port as
  `writer=` and dropped `session` from `apply_dialogue_mood`/`apply_event_shock`/`_write_through`; the dialogue
  call-site dropped `session=` (gossip already passed none). Not a tick engine, so no ignored-kwarg test —
  added `test_emotion_repository.py` (adapter + session-free updater write-through). Wave 2 second checkbox.

- **knowledge_learning** (DONE, `ecf9441`): `KnowledgeGraphPort` (find_conflicting_belief + write_belief,
  incl. `is_deception`/`deception_goal_id` kwargs so the deception slice REUSES it) + `Neo4jKnowledgeRepository`
  (session-per-call). `KnowledgeExtractionEngine` now constructor-injects the port and `process(*, npc_id,…)`
  dropped the `session` param; dialogue call-site dropped it. Engine was previously UNWIRED (only built in tests),
  so added `get_knowledge_extraction_engine()` in `dependencies_stores.py` (re-exported via dependency_singletons),
  wired into `build_dialogue_handler` (gated by `KNOWLEDGE_LEARNING_ENABLED`, default False — inert). Factory placed
  in dependencies_stores because dependencies.py is at the R001 300-line cap. Tests: `test_knowledge_repository.py`
  (adapter) + rewrote `test_knowledge_extraction_engine.py` to mock the port.

- **deception** (DONE, `5e95d8c`): **reuses** `KnowledgeGraphPort.write_belief` (no new port/adapter);
  `DeceptionEngine` constructor-injects `knowledge_repo` and `plant_belief(*, …)` dropped the `session` arg.
  Engine is UNWIRED (future caller — no api factory added). Test mocks the port. Wave 2 complete.

- **reputation** (DONE, `644c183`): NEW `ReputationGraphPort` (write: `apply_trust_nudge`) +
  `Neo4jReputationRepository`; `ReputationEngine` injects `RelationReadPort` (reads) + `ReputationGraphPort`
  (replacing the `apply_nudge_fn` callable + per-tick `AsyncSession`); `run_tick(player_id, npc_ids, **_)`.
  `ReputationTickAdapter` injects `CharacterReadPort` (sessionless `get_npc_ids()`), `run_tick(tick_id, **_)`,
  and DROPPED `relation_reader_factory` + the `engine._reader` per-tick mutation. Factory wires all 3 repos
  from `get_graph_db()` (repo imports moved to module top to keep `get_reputation_engine` under R006).
  Wave 3 first checkbox; `engines/reputation/` is neo4j-free.

- **player_model** (DONE, `aa06a0b`): NEW `PlayerModelGraphPort` (`upsert_player_model`) +
  `Neo4jPlayerModelRepository`; `PlayerModelTick` injects the shared `RelationReadPort` +
  `PlayerLocationReadPort` (replacing per-tick `RelationReader(session)` + `location_reader(session)`) and the
  new write port; `run_tick(tick_id, **_)` (no session), `_update_pair` dropped its session/reader params.
  Factory `get_player_model_tick` wires all 3 repos from `get_graph_db()` (local imports). Updated the
  integration test to build the real adapters from a `GraphDB`. Wave 3 second checkbox; `engines/player_model/`
  is neo4j-free.

- **director** (DONE, `368ea27`): NO new port — `DirectorTick` injects the shared `RelationReadPort` +
  `PlayerLocationReadPort` (replacing per-tick `RelationReader(session)` + `location_reader(session)` calls);
  `_decide_for_pair` dropped its session/reader params. `run_tick(session, tick_id)` KEEPS the session and
  forwards it ONLY to `event_handler.run_tick(session=…)` — director is NOT yet session-free and intentionally
  retains the `neo4j.AsyncSession` import until the `events` slice lands. Factory `get_director_tick` wires the
  two read adapters from `get_graph_db()`. Wave 3 third checkbox.

**19 domains migrated, 18 ports + 18 adapters** (+3 shared read ports/adapters; director reuses them, no new port). Shared ports built: political (succession+agenda),
WorldState (story_pacing + chapter — first cross-domain reuse). R006 watch: every tick engine's `run_tick` grew by the `**_` docstring +
multi-line repo calls; extract a helper when it crosses 40 lines (succession, treaty, oath did).
- Tests pattern: `test_<engine>.py` mocks the Port; `test_<domain>_repository.py` covers the adapter with a fake `GraphDB`.

## What ONE `/fix-next` pass does (one `SEV-24 ·` checkbox in INDEX.md)
1. **Pick** the first unchecked `SEV-24 ·` line in `INDEX.md` (waves are ordered easy→hard; respect them).
2. **Discover** that domain's specifics yourself (don't trust this brief blindly — code moves):
   `grep -rn "from npc_engine.graph\|AsyncSession" src/npc_engine/engines/<domain>/` for the graph surface;
   `grep -rn "<EngineClass>(" src/npc_engine/api/` for the construction factory;
   `grep -rn "<engine>.run_tick\|<EngineClass>" tests/` for the test + scheduler call.
3. **Implement** per the Pattern above (port → adapter → engine → wire → tests). Reuse an existing port if the
   domain already has one (e.g. political, world_state). Keep `(session,…)` on any graph function untouched —
   only the *engine* stops holding a session.
4. **Verify** `make check` + the touched tests. Add a `run_tick(session=object(), …)` "ignored-kwarg" test.
   If `run_tick` crossed 40 lines (R006), extract a named helper. If a `test_sev04_*` delegation guard patched
   the old module-level graph fns, repoint it to the injected port.
5. **Tick** the box `[ ]`→`[x]` in INDEX.md, append the commit hash to "Migrated slices" here, update the
   INDEX carry-forward note if you introduced a reusable port. **Commit** `feat(SEV-24): <domain> via repository`.

## Remaining slices — per-domain notes (confirm against code per step 2)
**Wave 1 — clean singletons:**
- `memory_consolidation` — `memory_consolidation_engine` (tick; already imports `GraphDB`). Graph: belief_queries
  `get_beliefs_for_character`, memory_queries `get_memories_for_character`, memory_service `create_memory`,
  witnessed_queries `get_undisclosed_witnesses`. Spans 3 read domains + memory write → one
  `MemoryConsolidationGraphPort` covering exactly its calls. Factory: `dependencies_advanced/progression.py`.
- `chapter` — `chapter_engine` (LLM tick, has `__init__(llm…)`). Graph: faction_queries
  `get_faction_standings_summary`, chapter_queries, chapter_writer, **world_state_reader `get_world_state` →
  reuse `WorldStateGraphPort`**. Factory: `progression.py get_chapter_engine`.
- `military` — CLUSTER: `military_engine.run_tick` delegates to `engines/military/military_battle_service.resolve_battles`
  + `military_resource_service.process_resource_yield`; those hold the graph calls (military_queries,
  military_control_writer). Give a `MilitaryGraphPort`, inject into the two services, `military_engine` injects +
  passes it (or the services take it directly). Factory: `politics.py get_military_engine`.

**Wave 2 — shared read-ports + light consumers:**
- `shared-read-ports` — build `RelationReadPort` (`relation_reader.RelationReader.get_relation_scalars`,
  `get_relation_phase_row`), `PlayerLocationReadPort` (`player_location_reader.PlayerLocationReader.get_collocated_pairs`,
  `get_player_idle_ticks`), `CharacterReadPort` (`character_reader.get_npc_ids`) + their `Neo4j*Repository`
  adapters (session-per-call). These REPLACE the per-tick `RelationReader(session)` / reader-factory pattern in
  reputation/player_model/director. Ship this checkbox as ports+adapters+tests only (no engine yet), OR fold into
  the first consumer — your call; either way later slices just inject them.
- `emotion` — `emotion_updater` (optional `EmotionGraphWriter` + `session` per method). `EmotionGraphPort.write_emotion`;
  adapter wraps `graph/emotion_writer`. Drop `session` from `apply_dialogue_mood`/`apply_event_shock`/`_write_through`;
  **update call-sites in `dialogue_handler` + `gossip_handler` to drop the `session=` arg** (small edits, those
  engines keep their own session).
- `knowledge_learning` — `knowledge_extraction_engine` (belief_queries `find_conflicting_belief` + knowledge_writer
  `write_belief`). Caller(s) drop the session arg.
- `deception` — `deception_engine` (`write_belief`; method takes session). Caller: dialogue. Smallest.

**Wave 3 — entangled:**
- `reputation` — `reputation_engine(config, relation_reader, apply_nudge_fn)` + `reputation_tick_adapter`
  (passes a per-tick `relation_reader_factory(session)` and mutates `engine._reader`). Inject `RelationReadPort` +
  `CharacterReadPort`; the nudge write (`reputation_nudge.apply_trust_nudge`) becomes a port method. Delete the
  reader-factory + `_reader` mutation. Factory: `dependencies_engines.get_reputation_engine`.
- `player_model` — `player_model_tick` (PlayerLocationReader + RelationReader + player_model_writer
  `upsert_player_model`/`get_player_model`). Reuse RelationReadPort + PlayerLocationReadPort + a
  `PlayerModelGraphPort`.
- `director` — `director_tick` (read-ports as above) BUT it also calls `event_handler.run_tick(session=…)`.
  Migrate its *reads* to the ports; **keep receiving `session` and pass it to event_handler** until the `events`
  slice lands (so director is not fully session-free yet — note this in the commit; do not delete its session param).
- `planning` — `goal_former` + `goal_former_adapter` + `action_selector`. Graph: need_queries
  `get_needs_for_character`/`get_satisfying_location_for_need`, goal_service `create_goal`, goal_targets_writer,
  character_reader, world_state_reader (reuse WorldStateGraphPort + CharacterReadPort). Multi-port slice.
- `economy` — `trade_engine` (currency_writer/item_writer/pricing_queries). **Per-request route factory**, not a
  singleton — build the adapter in the route's `Depends` factory.
- `agenda-others` — `intent_formation_engine` + `conversation_intent_service` (the non-`agenda_engine` files).
- `interaction`/`investigation`/`proactive_dialogue`/`relationship` — one slice each; standard pattern.
- `memory` — `MemoryEngine` is constructed inline in 5+ places (clock route, memories route module-level `_engine`,
  `dialogue_handler.__init__`, `quest_lifecycle_engine` fallback) + `get_memory_engine()` factory. Add
  `MemoryGraphPort` (create_memory + the two decays), make `get_memory_engine()` the single source, replace every
  inline `MemoryEngine()` with it; inject `memory_engine` into dialogue_handler/quest via their construction sites.

**Wave 4 — `run_in_tx` coordinators / large clusters:** `events` (`event_handler` owns a `run_in_tx` unit-of-work
→ the port exposes ONE atomic method whose adapter runs `run_in_tx` internally, no tx leaks out), then
`faction_politics`, `scheming`, `idempotency`, and the big `gossip`/`dialogue`/`quest`/`quest_generation` clusters
(each its own multi-slice effort — sub-split as needed; tick its INDEX box only when the whole domain is neo4j-free).

## Final step (last checkbox, only after every domain is migrated)
Remove `session` from the `BaseEngine.run_tick` protocol and `tick_scheduler.advance()`; drop the now-unused
`**_`/`session=None` swallowers in migrated engines. Confirm
`grep -rn "from neo4j\|AsyncSession\|AsyncTransaction" src/npc_engine/engines/` → empty. Close DEC-122.

## Verification
- `grep -rn "AsyncSession\|AsyncTransaction\|from neo4j" src/npc_engine/engines/` shrinks toward empty.
- Per slice: `make check` (lint/rules/layers/docstrings/type) + unit suite green.
- `make demo-seed && make demo-run ARGS=--dry-run` smoke after larger batches.

## Blast radius
~68 engine files + their composition-root factories. **Large — phase by engine domain across many sessions.**
Realizes DEC-122 and the engine/graph decoupling goal behind SEV-21.
