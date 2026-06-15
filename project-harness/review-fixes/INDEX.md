# Review-Fix Backlog — 2026-06-13 (munich-demo @ 327180a)

## Carry-forward notes
<!-- ≤10 lines. /fix-next and /fix-parallel append running context here. -->
- 2026-06-14 INTEGRATED: SEV-01,03,05,08 (parallel batch 1) + SEV-02, SEV-09, SEV-04, SEV-06 (/fix-next). make check GREEN, 2193 passed, cov 87.05%.
- ENFORCEMENT: ruff `I002` (pyproject `[tool.ruff.lint] extend-select=["I002"]` + isort required-imports) now blocks any non-`__init__.py` src module missing `from __future__ import annotations`. NOTE: ruff EXEMPTS `__init__.py` — those were added manually and are NOT auto-enforced (a new `__init__.py` won't be flagged).
- HARNESS BUG: `isolation:worktree` branched workers off `main` (ea16f74), 454 commits behind munich-demo. **Run remaining SEVs via /fix-next (no worktree) — it operates on munich-demo directly.**
- `common/knowledge_types.py` now holds `KnowledgeState` Literal + `KNOWLEDGE_STATE_KNOWS/RUMOR` — reuse for any new knowledge_state value (do NOT redefine "knows"/"rumor"). Cypher-template literals (event_queries/secret_queries) intentionally stay (data, not Python).
- New module docstrings need `Does NOT:` + `Dependencies injected:` lines (test_architecture_conformance). New files near 300-line config limit → sibling module (see `config_logging_validators.py`).
- REMAINING: SEV-11 (docs), SEV-12 (clique magic numbers).
- caplog gotcha: `utils/logging.py` sets propagate=False, so pytest `caplog` (root) misses engine logs once logging is configured — capture on the engine logger directly (see test_sev22 secret-seed test).
- Decide items (DEC-111…121) BLOCKED pending human approval — do not start via /fix-next.

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
- [ ] SEV-12 — Clique engine magic numbers → `config.py` keys  (deps: none · files: `engines/.../clique_formation_engine.py`, `config/config.py`)

### Block F — Docs (independent, trivial)
- [ ] SEV-11 — Doc/docstring drift: ARCHITECTURE prompt path, right_panel INTRIGUE, game_controller dep  (deps: none · files: `docs/ARCHITECTURE.md`, `demo_game/ui/right_panel.py`, `demo_game/game_controller.py`)

## Blocked — pending human approval (Decide)
These are **not** in the checklist above. See `DECISIONS.md` DEC-111…121 stubs. Do not start until resolved:
- DEC-111 idempotency advisory-vs-raise · DEC-112 system router prefix (interface) · DEC-113 mypy --strict
  adoption · DEC-114 full envelope typing (130 routes) · DEC-115 second composition root · DEC-116 covert
  template prompt-boundary · DEC-117 40-line function gate vs waive · DEC-118 investigation MERGE-vs-CREATE
  · DEC-119 session-ownership broad refactor · DEC-120 DistortionType Literal-vs-str · DEC-121 LLM protocol ISP split.

## Log-only (ISSUES.md, no brief)
ISSUE-101 schedule_queries cov · ISSUE-102 intrigue panel behavioral tests · ISSUE-103 135 stale docstrings ·
ISSUE-104 OCP residuals · ISSUE-105 dependencies_engines cap · ISSUE-106 deprecation warnings ·
ISSUE-107 cross-session e2e · ISSUE-100 (existing) Windows dry-run crash.
