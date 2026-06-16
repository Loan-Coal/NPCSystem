# Review-Fix Backlog — 2026-06-13 (munich-demo @ 327180a)

## Carry-forward notes
<!-- ≤10 lines. /fix-next and /fix-parallel append running context here. -->
- ENFORCEMENT: ruff `I002` (pyproject `[tool.ruff.lint] extend-select=["I002"]` + isort required-imports) now blocks any non-`__init__.py` src module missing `from __future__ import annotations`. NOTE: ruff EXEMPTS `__init__.py` — those were added manually and are NOT auto-enforced (a new `__init__.py` won't be flagged).
- HARNESS BUG: `isolation:worktree` branched workers off `main` (ea16f74), 454 commits behind munich-demo. **Run remaining SEVs via /fix-next (no worktree) — it operates on munich-demo directly.**
- `common/knowledge_types.py` now holds `KnowledgeState` Literal + `KNOWLEDGE_STATE_KNOWS/RUMOR` — reuse for any new knowledge_state value (do NOT redefine "knows"/"rumor"). Cypher-template literals (event_queries/secret_queries) intentionally stay (data, not Python).
- New module docstrings need `Does NOT:` + `Dependencies injected:` lines (test_architecture_conformance). New files near 300-line config limit → sibling module (see `config_logging_validators.py`).
- 2026-06-14/15 DONE: all 12 original SEVs + Block G quick wins (SEV-13/22/18) + mediums SEV-20/23/17. make check GREEN, 2216 passed, cov 86.39%.
- SEV-17: `dependencies_advanced` is now a PACKAGE (`politics.py`/`social.py`/`progression.py` + re-exporting `__init__`). Add a NEW advanced-engine factory to the matching submodule and to `__init__.__all__` — do NOT recreate a flat file. ISSUE-105's `dependencies_engines.py` (512 lines) is UNTOUCHED — apply the same split if a SEV reopens it.
- SEV-14 DONE: system observability now `/v1/admin/system/{engines,config,metrics,events}` (admin-scoped). The demo AND dashboard keys were ALREADY admin-scoped (both call other `/v1/admin/*`), so no key change — only URL repointing (demo client, dashboard `js/api.js`, world_poller/run_scenes docstrings). `/health`+`/readiness` stay public (separate `system_router`). Mount-path regression lives in `test_v1_route_versioning.py`.
- SEV-16 is L-effort/route-by-route: 35 files; npc_state/emotion/schemes already typed; many payloads are DYNAMIC engine-aggregate dicts (clock/batch) that should stay `dict[str,Any]`. Do fixed-shape demo-read routes first (player_model/chapters/investigations) à la SEV-03. See brief's scoping finding.
- **ACTIVE: SEV-24 (Track D facade)** — `/fix-next` = next unchecked `SEV-24 ·` checkbox; brief `FIX-SEV-24.md` is self-contained. Pattern: `engines/ports/<d>_port.py` Protocol + `graph/repositories/<d>_repository.py` (`GraphDB`, session-per-call) + engine injects port, `run_tick(*,…,**_)`, wired in its dep factory (`dependencies_advanced/{social,politics,progression}.py` or `dependencies_engines.py`). Reuse shared ports `PoliticalGraphPort`/`WorldStateGraphPort`. Add a `run_tick(session=object(),…)` "ignored kwarg" test. SEV-19/15 are BLOCKED until all SEV-24 boxes are checked. SEV-14/16/17/20/21/22/23 done. Wave 1 DONE (memory_consolidation/chapter/military). Wave 2 shared-read-ports DONE: `RelationReadPort`/`PlayerLocationReadPort`/`CharacterReadPort` (engines/ports/) + `Neo4jRelationReadRepository`/`Neo4jPlayerLocationReadRepository`/`Neo4jCharacterReadRepository` (graph/repositories/) — adapters only, no engine wired yet; later Wave 2/3 slices (emotion/reputation/player_model/director) INJECT these instead of constructing `RelationReader(session)`/reader-factories. Adapter test pattern in `tests/unit/test_shared_read_repositories.py`. emotion+knowledge DONE. `KnowledgeGraphPort` (find_conflicting_belief + write_belief, incl. `is_deception`/`deception_goal_id` kwargs) + `Neo4jKnowledgeRepository` — **deception slice REUSES this port's `write_belief`** (don't make a new belief port). `KnowledgeExtractionEngine(knowledge_repo=port)` now constructor-injects + `process(*, npc_id,…)` (no session); dialogue call-site dropped session; engine NOW wired via `get_knowledge_extraction_engine()` (dependencies_stores, re-exported in dependency_singletons) into `build_dialogue_handler`, gated by `KNOWLEDGE_LEARNING_ENABLED` (default False). NOTE: engine factories belong in `dependencies_stores.py`, NOT `dependencies.py` (it's at the 300-line R001 cap). deception DONE (Wave 2). reputation DONE (Wave 3 first): NEW `ReputationGraphPort` (write: `apply_trust_nudge`) + `Neo4jReputationRepository`; `ReputationEngine` injects `RelationReadPort`+`ReputationGraphPort` (no session, no `apply_nudge_fn` callable), `run_tick(player_id, npc_ids, **_)`; `ReputationTickAdapter` injects `CharacterReadPort` (get_npc_ids() sessionless), `run_tick(tick_id, **_)`, dropped relation_reader_factory/`_reader` mutation. Factory `get_reputation_engine` wires all 3 repos from `get_graph_db()`; repo imports moved to module top (R006). player_model DONE (Wave 3): `PlayerModelTick` now injects RelationReadPort+PlayerLocationReadPort (shared adapters) + NEW `PlayerModelGraphPort` (`upsert_player_model`) / `Neo4jPlayerModelRepository`; `run_tick(tick_id, **_)` (no session), `_update_pair` lost session/reader args. `get_player_model_tick` wires all 3 repos from `get_graph_db()` (local imports). director DONE (Wave 3): `DirectorTick` injects RelationReadPort+PlayerLocationReadPort (shared adapters); `run_tick(session, tick_id)` KEEPS session — forwarded to `event_handler.run_tick(session=…)` only (events not migrated). planning DONE (Wave 3): NEW `PlanningGraphPort` (`get_needs_for_character`/`get_satisfying_location_for_need`/`create_goal`/`create_goal_targets_edge`/`move_character`) + `Neo4jPlanningRepository`; `GoalFormer(planning_repo=)` + `ActionSelector(planning_repo=)` (both sessionless, no None defaults now); `GoalFormerAdapter` injects goal_former+action_selector+CharacterReadPort+WorldStateGraphPort, `run_tick(*, tick_id, **_)`. Factory `get_goal_formation_engine` wires all from `get_graph_db()`. economy DONE (Wave 3): NEW `EconomyGraphPort` (pricing-context reads + `transfer_item_atomic`/`transfer_currency_atomic`) + `Neo4jEconomyRepository`; `TradeEngine(pricing_engine=, economy_repo=)`, `evaluate_offer(...)` dropped session (extracted `_compute_fair_price`/`_execute_transfers` for R006); route `/trade` dropped its session Depends. GOTCHA: `get_trade_engine` is now PER-REQUEST (no `@lru_cache`) — removed its `.cache_clear()` from BOTH `tests/conftest.py` AND `src/npc_engine/main.py` (+ their now-unused imports). agenda-others DONE (Wave 3 last): NEW `IntentGraphPort` (trigger reads get_npc_location/get_player_location/get_unmet_needs/get_witnessed_events/get_unresolved_goals + queue writes `enqueue_intent(intent,*,settings)`/`expire_old_intents(*,cutoff_tick)`) + `Neo4jIntentRepository` (session-per-call); `score_intents(intent_repo,…)` takes the port as 1st positional arg (military-cluster pattern, sessionless); `IntentFormationEngine(location_reader=PlayerLocationReadPort, intent_repo=IntentGraphPort)`, `run_tick(tick_id,**_)`; factory wires both from `get_graph_db()` (reuses `Neo4jPlayerLocationReadRepository`). investigation DONE: NEW `InvestigationGraphPort` (6 read fns: evidence/witnesses/suspects/deductions/contradicting_rumors/alibi_window) + `Neo4jInvestigationRepository`; `InvestigationEngine(investigation_repo=)` sessionless (route `investigations.py` dropped its `get_db_session` Depends; engine + `_detect_alibi_contradictions` dropped session). Factory `get_investigation_engine` (in `dependencies_advanced/progression.py`). GOTCHA next slices: `scheme_detection_tick` lives in `engines/investigation/` but uses scheme_reader/scheme_writer → it belongs to the Wave-4 `scheming` domain port, NOT investigation. `relationship` (`apply_phase_transition`) is called ONLY by the UNMIGRATED `dialogue_handler` (Wave 4, still holds session) — migrating it means injecting a phase port into dialogue_handler. `proactive_dialogue` = `proactive_tick_adapter` (reuses shared `PlayerLocationReadPort`) + `proactive_engine` (check_trigger/generate_line take session → bigger). proactive_dialogue DONE: NEW `ProactiveMemoryReadPort` (get_unshared_memories) + `Neo4jProactiveMemoryReadRepository`; `ProactiveDialogueEngine` now injects ProactiveMemoryReadPort (memory_service) + shared `PlayerLocationReadPort` (location_service) — its old local `MemoryServiceProtocol`/`LocationServiceProtocol` DELETED; `check_trigger(npc_id,player_id,tick_id)`/`generate_line(trigger)` dropped session. `ProactiveDialogueTick` injects PlayerLocationReadPort, `run_tick(tick_id,**_)`, helpers `_collect_candidates`/`_generate_and_enqueue` dropped session. Factory `get_proactive_dialogue_engine` wires both repos from `get_graph_db()` (removed now-unused PlayerLocationReader/ProactiveMemoryReader top imports). `engines/proactive_dialogue/` neo4j-free. relationship DONE: `phase_transition_applier.apply_phase_transition` now takes (RelationReadPort, RelationPhaseWritePort) as leading positional args (free-fn cluster pattern), no session; REUSES shared `RelationReadPort.get_relation_phase_row` for the read + NEW `RelationPhaseWritePort`/`Neo4jRelationPhaseWriteRepository` for the write. `dialogue_handler` (Wave-4, keeps session for deltas) holds the two ports as optional `relation_reader`/`relation_phase_writer` kwargs, guarded call. `engines/relationship/` neo4j-free. GOTCHA: `dependencies.py` is AT the 300-line R001 cap — wired net-zero by bundling the ports + existing knowledge_engine into NEW `get_dialogue_graph_ports()` (in dependencies_stores, re-exported via dependency_singletons) and `**`-splatting it in `build_dialogue_handler` (replaced the `knowledge_engine=` line + swapped the import name). Reuse this splat-factory trick for the next dialogue_handler injection. interaction DONE (Wave 3, sub-split): NEW `InteractionGraphPort` (2 quest reads `get_quest_state`/`get_active_quest_for_player` + 5 verification counts) + `Neo4jInteractionRepository` (session-per-call). `quest_verifier` is now neo4j-free — the 4 Verifier classes + `verify_objectives` take the port (positional 1st arg) instead of session. `quest_handler` free-fns: `handle_propose_quest(repo=…)` is session-free; `handle_claim_completion`/`handle_give_item_as_quest_claim` take `repo` for reads but KEEP `session` (director-style) to forward to the still-session-based `QuestLifecycleEngine.update_objective`/`evaluate_completion` (Wave-4). Route `/interaction` adds `Depends(get_interaction_graph_repo)` (new `@lru_cache` factory in `dependencies_engines.py`, re-exported via dependency_singletons), still passes `session` for the engine forward. NOTE for Wave-4 quest cluster: when QuestLifecycleEngine migrates, drop the leftover `session` from these two handlers + the route. NEXT: Wave 3 `memory` (replace inline `MemoryEngine()` in clock/memories routes + dialogue + quest with `get_memory_engine()`) — last Wave-3 box before Wave 4.
- caplog gotcha: `utils/logging.py` sets propagate=False, so pytest `caplog` (root) misses engine logs once logging is configured — capture on the engine logger directly (see test_sev22 secret-seed test).

## Fix-now backlog (ordered, dependency-blocked)

### Block A — Scheme feature debt (new-code, highest value; independent files, parallelizable within block)
- [x] SEV-01 — Scheme writer transaction safety + test  (deps: none · files: `graph/scheme_writer.py`, `engines/scheming/scheme_advance_tick.py`, `tests/unit/`)
- [x] SEV-03 — Scheme typing: `SchemeStatus` Literal + typed route payload + covert-props model  (deps: none · files: `graph/scheme_reader.py`, `engines/scheming/covert_event_factory.py`, `api/routes/schemes.py`, models)

### Block B — Security / error-leakage (independent)
- [x] SEV-02 — Residual error-message leakage in 3 route sites + extend redaction guard test  (deps: none · files: `api/route_helpers.py`, `api/routes/locations.py`, `api/routes/economy.py`, `tests/.../test_route_error_redaction.py`)
- [x] SEV-09 — Staging/prod gate for `LOG_LEVEL` (mirror L1-04 validator)  (deps: none · files: `config/config_validators.py`, `config/config.py`, tests)

### Block C — Typing / fixed-sets (independent)
- [x] SEV-04 — `KnowledgeState` Literal (brief sites were off; real sites: knowledge_propagator x2, gossip_handler, + consolidated prompt_builder/gossip_spread_service named dups)  (files: `common/knowledge_types.py` NEW, `engines/gossip/knowledge_propagator.py`, `engines/gossip/gossip_handler.py`, `engines/dialogue/prompt_builder.py`, `graph/gossip_spread_service.py`)
- [x] SEV-06 — `base_engine.run_tick` return type-arg + ruff `from __future__` autofix (138 files; ruff I002 now enforces)  (files: `pyproject.toml` ruff I002, `engines/base_engine.py`, 138 src files)

### Block D — Test efficacy (independent)
- [x] SEV-05 — `investigation_service.py` tests (6 writers, happy+failure)  (deps: none · files: `tests/integration/`, `tests/unit/` — NOTE MERGE-vs-CREATE is DEC-118, test current CREATE behavior)
- [x] SEV-07 — Eval test hygiene: dropped 5 `sys.path.insert` blocks (pythonpath already covers evals), made seed-log guard real (captures on engine logger; propagate=False), added `--cov=runner` to gate. runner HTTP loop coverage → ISSUE-110  (files: 5 eval test files, `test_sev22_rng_determinism.py`, `Makefile`)
- [x] SEV-08 — `location_graph` route 422 guard tests  (deps: none · files: `tests/.../test_location_graph_route.py`)

### Block E — Tooling / architecture hygiene (independent)
- [x] SEV-10 — `check_layers.py`: ranked `observability`=1 + `find_unranked_packages` guard (unranked code package now fails, not silent-skip; scripts/prompts exempt)  (files: `scripts/check_layers.py`, `tests/unit/test_check_layers.py`)
- [x] SEV-12 — Clique engine magic numbers → `config.py` keys (CLIQUE_AFFECTION_THRESHOLD/INITIAL_COHESION/STALE_AGE_TICKS read from injected settings)  (files: `engines/clique/clique_formation_engine.py`, `config.py`, 2 clique tests)

### Block F — Docs (independent, trivial)
- [x] SEV-11 — Doc/docstring drift: ARCHITECTURE prompt path → `src/npc_engine/prompts/`, right_panel +INTRIGUE, game_controller dropped bogus `npc_engine.engines.interaction`  (files: `docs/ARCHITECTURE.md`, `demo_game/ui/right_panel.py`, `demo_game/game_controller.py`)

## Block G — Resolved-decision backlog (DEC-111…121 → SEV-13…23, decided 2026-06-14)

All 11 briefs written (`FIX-SEV-13…23.md`, format-verified). Decisions recorded in `DECISIONS.md`.
**`/fix-next` ordering:** the live checklist below holds only items a single `/fix-next` pass can finish.
Items needing a decision or multiple commits are parked in the two subsections AFTER it so `/fix-next`
does not stop on them — promote one into the checklist when you're ready to drive it.

### Ready for `/fix-next` (single-pass, in order)
- [x] SEV-17 — Split `dependencies_advanced.py` into per-engine submodules (DEC-115)  (deps: none · files: `api/dependencies_advanced/` package: politics/social/progression; ISSUE-105 only PARTLY addressed — `dependencies_engines.py` still 512 lines)

### Done (DEC-111…121 quick wins + mediums)
- [x] SEV-13 — Hard-raise idempotency in staging/prod (DEC-111)  (`ec2bf6a`)
- [x] SEV-18 — Covert summary traced as NOT LLM-bound; documented (DEC-116)  (`7185425`)
- [x] SEV-20 — `investigation_service` writers `CREATE`→`MERGE` on stable id (DEC-118)  (`5717449`)
- [x] SEV-22 — `DistortionType` → `str` + live registry validator (DEC-120)  (`2cd8c8b`)
- [x] SEV-23 — Split `LLMClientProtocol` into generate/structured/stream (DEC-121)  (`eab1726`)
- [x] SEV-14 — Move `system_v1_router` → `/v1/admin/system/*` (DEC-112). Resolved (Option A, admin scope):
  demo + dashboard keys were already admin-scoped, so URL-repoint only — no key/scope change needed.
- [x] SEV-16 — Type `OkEnvelope[T]` payloads for all client/SDK-consumed routes (DEC-114). 5 tiers: rewires
  (relationship/player_model), fixed-shape reads (chapters/investigations), politics/social lists
  (beliefs/goals/items/memories/pledges/treaties/factions/reputation), gossip/economy/quest-gen, system
  engines/events. Dynamic engine-aggregates (clock/batch/interaction/quest-lifecycle/graph-generic/config/
  metrics) stay `dict[str,Any]` by decision (inline-commented). Regression lock:
  `tests/unit/test_typed_payload_contract.py`.

### ACTIVE TRACK — SEV-24 (Track D / GraphRepository facade). `/fix-next` does ONE checkbox below per pass.
DEC-122, follow-on to SEV-21. **The brief `FIX-SEV-24.md` is self-contained** (recipe + per-domain notes +
gotchas) — a fresh `/fix-next` reads only it + the cited engine files. **Clear context between waves.**
Convention per slice: `engines/ports/<domain>_port.py` (Protocol, no neo4j types) +
`graph/repositories/<domain>_repository.Neo4j<Domain>Repository` (holds `GraphDB`, session-per-call) + engine
injects the port via `__init__`, `run_tick(*, …, **_)` swallows the scheduler `session=`, wired in the engine's
dep factory. Tests: engine mocks the Port, adapter gets a fake-`GraphDB` test. Watch R006 (extract a helper if
`run_tick` crosses 40 lines); update any SEV-04 delegation guard to the port.
**Done (15 slices):** need, mood, clique, skill, routine, succession, agenda, story_pacing, treaty, oath,
memory_consolidation, chapter (`ChapterGraphPort` = chapter reads/writes + faction standings; **reuses shared
`WorldStateGraphPort`** for world_state; extracted `_transition_chapter` to keep run_tick under R006),
military (`MilitaryGraphPort` injected into the two SERVICES `resolve_battles`/`process_resource_yield`, which
now take the port as first arg; engine holds the port + `run_tick(*, tick_id=0, **_)`)
(+ shared `PoliticalGraphPort`, `WorldStateGraphPort`). `make check` green, 2282 tests.

Wave 1 — clean singletons (scheduler-only callers; smallest blast radius):
- [x] SEV-24 · memory_consolidation — `memory_consolidation_engine` (belief/memory/witnessed reads + create_memory)
- [x] SEV-24 · chapter — `chapter_engine` (LLM tick; reuse `WorldStateGraphPort` for its world_state read)
- [x] SEV-24 · military — cluster: `military_engine` + `military_battle_service` + `military_resource_service`

Wave 2 — shared read-ports + light consumers (build the readers once, reuse after):
- [x] SEV-24 · shared-read-ports — `RelationReadPort` + `PlayerLocationReadPort` + `CharacterReadPort` (+ adapters)
- [x] SEV-24 · emotion — `emotion_updater` write-through; drop the `session` arg at its dialogue/gossip call-sites
- [x] SEV-24 · knowledge_learning — `knowledge_extraction_engine` (belief reads + write_belief; callers drop session)
- [x] SEV-24 · deception — `deception_engine` (write_belief; caller: dialogue drops session)

Wave 3 — entangled (session-coupled readers / wide construction):
- [x] SEV-24 · reputation — `reputation_engine` + `reputation_tick_adapter` (reuse RelationReadPort; drop reader-factory)
- [x] SEV-24 · player_model — `player_model_tick` (reuse RelationReadPort + PlayerLocationReadPort)
- [x] SEV-24 · director — `director_tick` (reuse the read-ports; KEEP passing session to event_handler until events migrates)
- [x] SEV-24 · planning — `goal_former` + `goal_former_adapter` + `action_selector`
- [x] SEV-24 · economy — `trade_engine` (per-request route factory, not a singleton)
- [x] SEV-24 · agenda-others — `intent_formation_engine` + `conversation_intent_service`
- [x] SEV-24 · investigation — `investigation_engine` (query-only; `InvestigationGraphPort`)
- [x] SEV-24 · proactive_dialogue — `proactive_engine` + `proactive_tick_adapter`
- [x] SEV-24 · relationship — `phase_transition_applier` (reuse RelationReadPort + new RelationPhaseWritePort; injected into dialogue_handler)
- [x] SEV-24 · interaction — `quest_handler`/`quest_verifier` (overlaps the Wave-4 quest cluster; sub-split)
- [ ] SEV-24 · memory — `MemoryEngine`: replace inline `MemoryEngine()` in clock/memories routes + dialogue + quest with `get_memory_engine()`

Wave 4 — `run_in_tx` coordinators / large clusters (domain repo exposes a unit-of-work that runs run_in_tx internally):
- [ ] SEV-24 · events — `event_handler` (run_in_tx coordinator)
- [ ] SEV-24 · faction_politics (run_in_tx) · scheming · idempotency (one slice each)
- [ ] SEV-24 · gossip cluster (8 files) · dialogue cluster (6) · quest cluster (12) · quest_generation cluster (10)

Wave 5 — finalize:
- [ ] SEV-24 · drop `session` from `BaseEngine.run_tick` + `tick_scheduler.advance()`; confirm
  `grep -rn "from neo4j\|AsyncSession" src/npc_engine/engines/` → empty; close DEC-122 / FIX-SEV-24 / this INDEX.

### After Track D (deps: all SEV-24 boxes checked) — drive incrementally, own session each
- [x] SEV-21 — Graph sub-writers → caller-owned transactions via `transaction_coordinator.run_in_tx` (DEC-119, 6
  family commits). `begin_transaction(` only in the coordinator; no engine opens a tx; `(session,…)` signatures kept.
- [ ] SEV-19 — R006 40-line gate + refactor `advance`(373)/`dispatch`/`seed`; waive cohesive rest (DEC-117).
  One function per commit. **deps: SEV-24 complete** (advance/dispatch are reshaped by the facade first).
- [ ] SEV-15 — Adopt full `mypy --strict`; fix all 274 errors / 87 files; flip `make type` (DEC-113).
  Sub-phase by package. **deps: SEV-24 complete** (types land on the final repo-injected engine shape).

## Log-only (ISSUES.md, no brief)
ISSUE-101 schedule_queries cov · ISSUE-102 intrigue panel behavioral tests · ISSUE-103 135 stale docstrings ·
ISSUE-104 OCP residuals · ISSUE-105 dependencies_engines cap · ISSUE-106 deprecation warnings ·
ISSUE-107 cross-session e2e · ISSUE-100 (existing) Windows dry-run crash.
