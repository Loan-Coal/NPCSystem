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
- Remaining Block G: SEV-16 (route typing, multi-commit); SEV-15/19/21 (heavy refactors). SEV-14/17 done.
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

### Multi-phase — NOT a single `/fix-next` pass (drive incrementally / its own session)
Each brief says to sub-phase; `/fix-next` does one item→one commit, so these would over-reach in one go.
- [ ] SEV-19 — R006 40-line gate + refactor `advance`(373)/`dispatch`/`seed`; waive cohesive rest (DEC-117).
  One function per commit.
- [x] SEV-21 — Migrate 14+ graph sub-writers to caller-owned transactions (DEC-119). 6 writer-family commits
  (relation, currency/item, character-knowledge, faction/reputation, quest/schedule, player-model): each
  sub-writer now runs its writes via `transaction_coordinator.run_in_tx` instead of `session.begin_transaction()`.
  `begin_transaction(` now appears only in `transaction_coordinator.py`; no engine opens a transaction. Public
  `(session, …)` signatures preserved (engine call-sites untouched; full session removal is the Track-D facade).
- [ ] SEV-15 — Adopt full `mypy --strict`; fix all 274 errors / 87 files; flip `make type` (DEC-113).
  Sub-phase by package.

## Log-only (ISSUES.md, no brief)
ISSUE-101 schedule_queries cov · ISSUE-102 intrigue panel behavioral tests · ISSUE-103 135 stale docstrings ·
ISSUE-104 OCP residuals · ISSUE-105 dependencies_engines cap · ISSUE-106 deprecation warnings ·
ISSUE-107 cross-session e2e · ISSUE-100 (existing) Windows dry-run crash.
