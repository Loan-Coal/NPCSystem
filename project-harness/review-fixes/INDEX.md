# Review-Fix Backlog — 2026-06-13 (munich-demo @ 327180a)

## Carry-forward notes
<!-- ≤10 lines. /fix-next and /fix-parallel append running context here. -->
- 2026-06-14 INTEGRATED: SEV-01,03,05,08 (parallel batch 1) + SEV-02, SEV-09, SEV-04, SEV-06 (/fix-next). make check GREEN, 2193 passed, cov 87.05%.
- ENFORCEMENT: ruff `I002` (pyproject `[tool.ruff.lint] extend-select=["I002"]` + isort required-imports) now blocks any non-`__init__.py` src module missing `from __future__ import annotations`. NOTE: ruff EXEMPTS `__init__.py` — those were added manually and are NOT auto-enforced (a new `__init__.py` won't be flagged).
- HARNESS BUG: `isolation:worktree` branched workers off `main` (ea16f74), 454 commits behind munich-demo. **Run remaining SEVs via /fix-next (no worktree) — it operates on munich-demo directly.**
- `common/knowledge_types.py` now holds `KnowledgeState` Literal + `KNOWLEDGE_STATE_KNOWS/RUMOR` — reuse for any new knowledge_state value (do NOT redefine "knows"/"rumor"). Cypher-template literals (event_queries/secret_queries) intentionally stay (data, not Python).
- New module docstrings need `Does NOT:` + `Dependencies injected:` lines (test_architecture_conformance). New files near 300-line config limit → sibling module (see `config_logging_validators.py`).
- 2026-06-14 DONE: all 12 original SEVs + Block G quick wins (SEV-13/22/18) + mediums SEV-20 (investigation MERGE) + SEV-23 (LLM protocol ISP split). make check GREEN, 2211 passed, cov 86.38%.
- SEV-14 NOT a quick win: moving `/v1/system`→`/v1/admin/system` escalates auth to admin scope (prefix-scoped) AND breaks the demo's live `/v1/system/*` polling. See its brief's gotcha; dedicated session.
- SEV-16 is L-effort/route-by-route: 35 files; npc_state/emotion/schemes already typed; many payloads are DYNAMIC engine-aggregate dicts (clock/batch) that should stay `dict[str,Any]`. Do fixed-shape demo-read routes first (player_model/chapters/investigations) à la SEV-03. See brief's scoping finding.
- Remaining Block G: SEV-14 (auth), SEV-16 (route typing, multi-commit); SEV-15/17/19/21 (heavy refactors).
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

Briefs NOT yet written — generate `FIX-SEV-NN.md` before running `/fix-next` on each (or via `/fix-parallel`
step 3). Ordered roughly small→large; SEV-15/19/21 are the heavy refactors. Decisions recorded in `DECISIONS.md`.
- [x] SEV-13 — Hard-raise idempotency in staging/prod (DEC-111)  (deps: none · files: `config_logging_validators.py`-style sibling or `config_validators.py`, `config.py`, tests)
- [ ] SEV-14 — Move `system_v1_router` under `admin_prefix` `/v1/admin/system/*` (DEC-112)  (deps: none · files: `main.py`/router registry, route tests · INTERFACE change)
- [ ] SEV-16 — Type `OkEnvelope[T]` payloads for public/SDK routes (DEC-114)  (deps: none · files: `api/routes/*` public set, payload models)
- [x] SEV-18 — Trace `event.summary`→LLM; move covert template to `prompts/scheming/` if LLM-bound (DEC-116)  (deps: none · files: `covert_event_factory.py`, maybe `prompts/scheming/`)
- [x] SEV-20 — `investigation_service` writers `CREATE`→`MERGE` on stable keys (DEC-118)  (deps: SEV-05 tests · files: `graph/investigation_service.py`, tests)
- [x] SEV-22 — `DistortionType` → `str` + live registry validator; unfreeze `REGISTRY_KEYS` (DEC-120)  (deps: none · files: `gossip_distort.py`, `distortion_strategy.py`, tests)
- [x] SEV-23 — Split `LLMClientProtocol` into generate/structured/stream protocols (DEC-121)  (deps: none · files: `engines/llm/protocols.py`, adapters, dialogue client)
- [ ] SEV-17 — Split `dependencies_advanced.py` into per-engine submodules (DEC-115)  (deps: none · files: `api/dependencies_advanced.py` → submodules; resolves ISSUE-105)
- [ ] SEV-19 — Add R006 40-line gate; refactor `advance`/`dispatch`/`seed`; waive cohesive rest (DEC-117)  (deps: none · files: `scripts/check_rules.py`, `tick_scheduler.py`, `auth/middleware.py`, `data/api_seeder.py`, DECISIONS waivers)
- [ ] SEV-21 — Migrate 14+ graph sub-writers to `AsyncTransaction` params; `graph_writer` coordinates (DEC-119)  (deps: none · files: most of `graph/`, large refactor)
- [ ] SEV-15 — Adopt full `mypy --strict`; fix all 274 errors / 87 files; flip `make type` gate (DEC-113)  (deps: none · files: repo-wide; largest — sub-phase it)

## Log-only (ISSUES.md, no brief)
ISSUE-101 schedule_queries cov · ISSUE-102 intrigue panel behavioral tests · ISSUE-103 135 stale docstrings ·
ISSUE-104 OCP residuals · ISSUE-105 dependencies_engines cap · ISSUE-106 deprecation warnings ·
ISSUE-107 cross-session e2e · ISSUE-100 (existing) Windows dry-run crash.
