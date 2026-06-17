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
- **ACTIVE: SEV-24 (Track D facade)** — `/fix-next` = next unchecked `SEV-24 ·` checkbox; brief `FIX-SEV-24.md` is self-contained. Pattern: `engines/ports/<d>_port.py` Protocol + `graph/repositories/<d>_repository.py` (`GraphDB`, session-per-call) + engine injects port, `run_tick(*,…,**_)`, wired in its dep factory (`dependencies_advanced/{social,politics,progression}.py` or `dependencies_engines.py`). Reuse shared ports `PoliticalGraphPort`/`WorldStateGraphPort`. Add a `run_tick(session=object(),…)` "ignored kwarg" test. SEV-19/15 are BLOCKED until all SEV-24 boxes are checked. scheming DONE (Wave 4): NEW `SchemingGraphPort` (get_active_schemes/upsert_scheme/add_scheme_step/get_all_active_schemes_with_steps/get_npc_location_id/`emit_scheme_step_atomic`) + `Neo4jSchemingRepository`; `SchemeAdvanceTick(settings,registry,scheming_repo=)` + `SchemingEngine(settings,scheming_repo=)` both sessionless. `run_tick(*, tick_id, **_)` swallows `session=`. Factory `get_scheme_advance_tick` (local import) wires repo from `get_graph_db()`. tests rewritten to mock port. idempotency DONE (Wave 4): `IdempotencyStoreProtocol` sessionless (removed `AsyncSession` from all methods); NEW `Neo4jIdempotencyRepository` (graph/repositories/, holds GraphDB, delegates to `Neo4jIdempotencyStore`); `IdempotencyService` drops `graph_db` field (store manages sessions); `service_helpers.py` drops `session` param; `get_idempotency_service` wires `Neo4jIdempotencyRepository`; `get_idempotency_store` factory removed from `dependencies_stores`/`dependency_singletons`/`conftest.py`. 2346 tests, make check GREEN. gossip DONE (Wave 4): NEW `GossipGraphPort` (10 methods: fetch_gossip_pairs/select_batch_event_trust/write_batch_knowledge_propagation/create_rumor/believe_rumor/log_gossip CAS-retry/select_gossip_secret/propagate_secret/get_goals_for_character/fetch_known_node_ids) + `Neo4jGossipRepository`; CAS retry moved from `edge_updater.log_gossip` into adapter; `pair_selector.select_pairs(repo=)` drops session; `GossipHandler(gossip_repo=)` required; `**_` swallows session=. Orphaned: `edge_updater.log_gossip` + `knowledge_propagator.propagate_secret` (ISSUE-113). 2360 tests, make check GREEN. **NEXT: Wave 4 - dialogue cluster (6 files) / quest cluster (12) / quest_generation cluster (10); then Wave 5 drops `session` from `BaseEngine.run_tick`/`tick_scheduler.advance()`.**
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
- [x] SEV-24 · memory — `MemoryEngine`: replace inline `MemoryEngine()` in clock/memories routes + dialogue + quest with `get_memory_engine()`

Wave 4 — `run_in_tx` coordinators / large clusters (domain repo exposes a unit-of-work that runs run_in_tx internally):
- [x] SEV-24 · events — `event_handler` (run_in_tx coordinator)
- [x] SEV-24 · faction_politics (run_in_tx) — `faction_politics_engine` via `FactionPoliticsGraphPort` + `Neo4jFactionPoliticsRepository`
- [x] SEV-24 · scheming · idempotency (one slice each)
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
