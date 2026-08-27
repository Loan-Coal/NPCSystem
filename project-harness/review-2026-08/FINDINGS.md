# Findings — Strategic Codebase Review 2026-08

Flat triage table. One row per finding. Appended per lens as workers report.

| ID | Sev | Conf | Kind | Effort | Title | Where |
|----|-----|------|------|--------|-------|-------|
| CR-L10-01 | HIGH | Confirmed | Defect/Risk | M | Token-budget subsystem silently violated its own contract ~2.5 months; replacement gate hardcodes a measured ceiling | `src/npc_engine/retrieval/context/` |
| CR-L10-04 | HIGH | Confirmed | Debt | L | `evals/` package + config/context-retrieval never leave the top-churn decile | `evals/`, `src/npc_engine/config*` |
| CR-L10-02 | MEDIUM | Confirmed | Debt | S | `context_builder.py` file-size justification comment understates the file by 78% | `src/npc_engine/retrieval/context/context_builder.py` |
| CR-L10-03 | MEDIUM | Confirmed | Process | S | `evals/calibration.py` breached its own DEC-169 split trigger with no follow-up decision | `evals/calibration.py` |
| CR-L10-05 | MEDIUM | Confirmed | Debt | M | `config.py` is the single most fix-magnet file (7 fix-of-fix hits), 68% over the 300-line limit, unwaived | `src/npc_engine/config.py` |
| CR-L10-06 | LOW | Confirmed | Process/Waste | S | 30% of the current commit stream is pure process bookkeeping; top-3 all-time churned files are harness markdown | `project-harness/` |
| CR-L10-07 | LOW | Confirmed | Process | N/A | Commit velocity is loop-driven, not human-paced — structural cause of the fix-of-fix pattern | git history |
| CR-L10-08 | LOW | Suspected | Process | S | A 37-day commit gap (W27–W30) is undocumented in ROADMAP/DECISIONS | `project-harness/` |
| CR-L07-01 | HIGH | Confirmed | Defect | S | `ISSUE-145` is a stale P1 whose root cause was already fixed under different IDs | `project-harness/ISSUES.md` |
| CR-L07-02 | HIGH | Confirmed | Debt | S | `DECISIONS.md` and its archive reuse IDs (5 DEC + 2 ISSUE numbers), breaking a ledger cited 352× | `project-harness/DECISIONS.md` |
| CR-L07-03 | HIGH | Confirmed | Defect | M | Two file-size waivers in `DECISIONS.md` silently violated live on main (`game_window.py` 925 vs 350 waived) | `demo_game/game_window.py`, `src/.../quest_lifecycle_engine.py` |
| CR-L07-04 | MEDIUM | Confirmed | Defect | S | `ISSUE-122` prescribes a fix that was already present when the issue was filed | `project-harness/ISSUES.md` |
| CR-L07-05 | MEDIUM | Confirmed | Process | S | Roadmap completion trend is diverging — backlog grows 40% faster than it clears | `project-harness/ROADMAP.md` |
| CR-L07-06 | MEDIUM | Confirmed | Debt | M | 53% of DECISIONS.md is unreferenced outside project-harness; sampled drift rate 4/12 | `project-harness/DECISIONS.md` |
| CR-L07-07 | MEDIUM | Confirmed | Defect | S | Three scripts share one hardcoded stale corpus default; only one is tracked | `scripts/` |
| CR-L07-08 | LOW | Confirmed | Waste | S | `SKILLS_QUEUE.md` dead ~90 days while still normatively referenced | `project-harness/SKILLS_QUEUE.md` |
| CR-L08-03 | **CRITICAL** | Confirmed | Defect | M | Neo4j-unavailable fallback contract unimplemented at all 3 hops; outage returns 500, not 503 (upgraded by orchestrator) | `src/npc_engine/api/errors/exception_handlers.py:113`, `utils/errors.py:54,301` |
| CR-L08-01 | HIGH | Confirmed | Debt | L | `client.py` (1901) / `seed.py` (1677) blew past their DECISIONS-stated ceilings ~2.1× | `demo_game/client.py`, `demo_game/seeds/seed.py` |
| CR-L08-02 | HIGH | Confirmed | Debt | M | `game_window.py` regrew to 925 lines after DEC-032 declared the size problem resolved | `demo_game/game_window.py` |
| CR-L08-04 | MEDIUM | Confirmed | Gap | S | `scripts/` (7,821 LOC) is invisible to the 300-line and 40-line rule gates | `scripts/` |
| CR-L08-08 | MEDIUM | Confirmed | Process | S | Waiver-mandated top-of-file comments missing on the 4 highest-drift oversized files | 4 oversized files |
| CR-L08-05 | LOW | Confirmed | Process | S | The brief's "313 grandfathered violations" matches no live or historical count (real: 133 + 72 = 205) | `scripts/rules_baseline.txt`, `scripts/evals_baseline.txt` |
| CR-L08-06 | LOW | Confirmed | Process | S | ~~`.claude/worktrees/` "9 stale" claim false~~ — WITHDRAWN by orchestrator; 9 existed at review start, reaped mid-run | `.claude/worktrees/` |
| CR-L08-07 | LOW | Confirmed | Waste | S | Duplicated `_draw_no_data` empty-state helper across demo_game UI panels | `demo_game/` |
| CR-L08-09 | LOW | Confirmed | Waste | S | `live_openapi.json` is a stale (2026-06-24), unreferenced, git-tracked 182KB artifact | `live_openapi.json` |
| CR-L06-01 | HIGH | Confirmed | Defect | S | Delete `check-human-gates` — passes with the feature it guards deleted (`0 gates`, exit 0) | `scripts/check_human_gates.py` |
| CR-L06-02 | HIGH | Confirmed | Defect | S | `check_conservation` Identity 2 was rewritten into `x == x` under the label of a bug fix | `scripts/check_conservation.py` |
| CR-L06-03 | HIGH | Confirmed | Waste | S | `check-test-quality` cannot fail — `main()` returns 0 unconditionally | `scripts/check_test_quality.py` |
| CR-L06-04 | HIGH | Confirmed | Debt | M | Rules ratchet is a floor: 7.8 years to zero on src; evals baseline growing (59→72 in 17 days) | `scripts/rules_baseline.txt`, `scripts/evals_baseline.txt` |
| CR-L06-05 | HIGH | Confirmed | Defect | M | `check-rules` signatures are file-level, so grandfathered files grow unbounded (`client.py` +481 lines while green) | `scripts/check_rules.py` |
| CR-L06-06 | HIGH | Confirmed | Gap | S | CI runs 6 of 14 gates; the 8 skipped include the only two with a documented catch on main | `.github/workflows/ci.yml` |
| CR-L06-07 | MEDIUM | Confirmed | Waste | S | Delete `check-harness` — its only hard check is unreachable behind `lint` | `scripts/check_harness_honesty.py` |
| CR-L06-08 | MEDIUM | Confirmed | Risk | S | `check-docstrings` verifies the substring `Layer:` exists, not that it says anything | `scripts/docstring_audit.py` |
| CR-L06-09 | MEDIUM | Confirmed | Waste | S | Drop `check-conservation` and `check-label-survival` — both audit files that cannot change | `scripts/` |
| CR-L06-10 | MEDIUM | Confirmed | Gap | S/L | 36,961 lines of `demo_game/` sit outside every gate except two file-shape rules (256 mypy errors) | `demo_game/` |
| CR-L06-11 | LOW | Confirmed | Risk | M | `make lint` enables 60 of 929 ruff rules and runs in 0 s (`E501` off despite `line-length=120`) | `pyproject.toml` |
| CR-L06-12 | LOW | Confirmed | Process | S | `HARNESS_GATES.md` states a mypy baseline that has been zero for twelve weeks | `project-harness/HARNESS_GATES.md` |
| CR-L13-01 | HIGH | Confirmed | Defect | S | `HARNESS_GATES.md` debt numbers wrong in both directions (57 vs 133; 256 vs 0), 85 days undrifted (downgraded from CRITICAL) | `project-harness/HARNESS_GATES.md:33-34` |
| CR-L13-02 | HIGH | Confirmed | Defect | S | `CONTRIBUTING.md` quickstart broken: seed command absent, 5 links to a `project/` dir that doesn't exist (downgraded from CRITICAL) | `CONTRIBUTING.md` |
| CR-L13-03 | HIGH | Confirmed | Defect | S | Three eval-gate docs advertise `make check-base-rate` / `check-engine-coverage` — neither target exists | `docs/CASE_SET_POLICY.md`, `CAPABILITY_CASES.md`, `ENGINE_EVAL_COVERAGE.md` |
| CR-L13-04 | HIGH | Confirmed | Defect | S | `README.md` "Key files" table points at a source layout that no longer exists | `README.md` |
| CR-L13-05 | HIGH | Confirmed | Defect | S | `README.md` "What's next" describes finished or archived work as open TODOs | `README.md` |
| CR-L13-06 | HIGH | Confirmed | Defect | S | `check_harness_honesty.py` H3 reads an archived file — permanently inert regardless of ISSUES.md | `scripts/check_harness_honesty.py` |
| CR-L13-07 | HIGH | Confirmed | Debt | S | `HARNESS_GATES.md` "one command" table lists 5 of the 14 gates `make check` runs | `project-harness/HARNESS_GATES.md` |
| CR-L13-08 | MEDIUM | Confirmed | Debt | S/M | `CHANGELOG.md` 96 commits / 13 days stale, still points at the pre-rename `project/` tree | `CHANGELOG.md` |
| CR-L13-09 | MEDIUM | Confirmed | Gap | S | `docs/API.md` missing the 6 newest live routes, including an undocumented `/setup/*` surface | `docs/API.md` |
| CR-L13-10 | MEDIUM | Confirmed | Debt | S | `EVAL_STRATEGY.md` is a 3-month-old uncorrected duplicate of `docs/EVAL_METHODOLOGY.md` | `project-harness/EVAL_STRATEGY.md` |
| CR-L13-11 | LOW | Confirmed | Debt | S | Root `live_openapi.json` 64 days stale vs the running server (merges with CR-L08-09) | `live_openapi.json` |
| CR-L03-01 | **CRITICAL** | Confirmed | Defect | L | A null responder (one fixed string) beats the engine on the guard battery — 0.949 vs 0.897; the published 0.914 is not a measurement | `evals/`, `evals/reports/20260825T231028Z.md:11` |
| CR-L03-02 | HIGH | Confirmed | Defect | M | `check_publication` ignores the interval it is handed and `evals/report.py` never calls it at all | `evals/scorer_trust_policy.py:84-94`, `evals/report.py` |
| CR-L03-03 | HIGH | Confirmed | Defect | S/L | Two of three judges cannot resolve any physically possible effect (MDE 17.25pp / 29.01pp vs 5.9pp / 8.0pp headroom) | `evals/mde.py` |
| CR-L03-04 | HIGH | Confirmed | Waste | S | 1,522 LOC of the newest gate layer is reachable from no `make` target and no CI job | `evals/`, `Makefile` |
| CR-L03-05 | HIGH | Confirmed | Waste | S/L | The trend/regression stack has never made a comparison; its sole row is already incomparable | `evals/trend_*.py` |
| CR-L03-06 | HIGH | Confirmed | Defect | M | Headline aggregator reports 78 turns for 789 verdict rows and 5 hallucinations for 28 | `evals/` aggregator |
| CR-L03-07 | MEDIUM | Confirmed | Defect | S | Two of the four eval gates in `make check` audit a superseded generation | `scripts/check_conservation.py`, `check_label_survival.py` |
| CR-L03-08 | MEDIUM | Confirmed | Defect | M | Half the guard battery's forbidden-keyword assertions are guaranteed passes (18/36) | `evals/cases/` |
| CR-L03-09 | MEDIUM | Confirmed | Gap | M | A third of the corpus has never been scored; capability headline rests on 16 cases, 6 hedge-passable | `evals/cases/` |
| CR-L03-10 | MEDIUM | Confirmed | Defect | S | Judge verdicts flip on wall-clock latency; an unparseable verdict is recorded as a substantive NO | `evals/matchers.py` |
| CR-L03-11 | MEDIUM | Confirmed | Risk | M | Reproducibility measured at 0.628 against a 0.95 gate, recorded NOT_MET, gated by nothing | `evals/` |
| CR-L03-12 | LOW | Confirmed | Waste | S/L | Subtraction: the sequence subsystem has produced no measurement (808 LOC + 227 doc lines) | `evals/sequence*`, `docs/SEQUENCE_*` |
| CR-L16-01 | HIGH | Confirmed | Gap | S | Fresh clone cannot boot on Windows without two undocumented fixes (git longpaths, `.env` copy) | `README.md`, `.gitignore`, `docker-compose.yml` |
| CR-L16-03 | HIGH | Confirmed | Process | S | Documented day-to-day path never rebuilds the app image; `boot-check` staleness detector exists but nothing documented invokes it | `Makefile`, `docker-compose.yml` |
| CR-L16-04 | HIGH | Confirmed | Defect | S | `torch`/`sentence-transformers` are hard deps but absent from the 3.14 dev venv — embedding/RAG path unexercised locally | `pyproject.toml` |
| CR-L16-02 | MEDIUM | Confirmed | Debt | S | Three mutually contradictory setup docs (README vs CONTRIBUTING vs compose header) | `README.md`, `CONTRIBUTING.md` |
| CR-L16-05 | MEDIUM | Confirmed | Risk | M | No dependency ceiling anywhere and no lockfile — 7 open-range, 1 unpinned, unreproducible builds | `pyproject.toml`, `demo_game/requirements.txt` |
| CR-L16-06 | MEDIUM | Confirmed | Debt | M | Two incompatible Python targets: Docker/mypy on 3.11, CI/README on 3.14 | `Dockerfile`, `mypy.ini`, `.github/workflows/ci.yml` |
| CR-L16-07 | MEDIUM | Confirmed | Risk | S | `app` container runs as root with no healthcheck | `Dockerfile`, `docker-compose.yml` |
| CR-L16-08 | LOW | Confirmed | Risk | S | Ollama model tag is not content-addressed — eval scores not provably comparable across time | `docker-compose.yml`, `evals/` |
| CR-L16-09 | LOW | Confirmed | Risk | S | Neo4j ships the documented default credential pair | `docker-compose.yml` |
| CR-L15-01 | HIGH | Confirmed | Defect | S | "Unit" tests make real unmocked calls to Ollama/live API — 51% of `make test` is network I/O; CI declares no such services (downgraded from CRITICAL pending CI check) | `tests/unit/evals/test_run_config.py`, `evals/matchers.py` |
| CR-L15-06 | HIGH | Confirmed | Gap | M | 36,527 LOC (29% of non-test surface) carry no coverage floor — including the gate scripts that enforce everything else | `scripts/`, `e2e/`, `demo_game/` |
| CR-L15-02 | HIGH | Confirmed | Gap | M | `intent_queries.py` real coverage 34.6%; every caller mocks its 12 functions at three layers, no integration backstop | `src/npc_engine/graph/.../intent_queries.py` |
| CR-L15-03 | MEDIUM | Confirmed | Process | S | `check-test-quality` cannot fail `make check` regardless of findings (merges with CR-L06-03) | `scripts/check_test_quality.py` |
| CR-L15-04 | MEDIUM | Confirmed | Process | S | `make check`'s 595s is not the per-commit gate — the real hook cost is ~4.9s | `.pre-commit-config.yaml`, `project-harness/CLAUDE.md` |
| CR-L15-05 | LOW | Confirmed | Waste | S | `mypy src/` runs twice per `make check` under two mechanisms | `Makefile` |
| CR-L01-01 | **CRITICAL** | Confirmed | Defect | M | Gossip distortion does not compound across hops — the signature demo feature is a no-op, proven live | `src/npc_engine/graph/.../gossip_batch_queries.py:29-47` |
| CR-L01-02 | HIGH | Confirmed | Defect | M | Gossip `MERGE ... SET` overwrites existing KNOWS_ABOUT edges — running the world erases the seeded demo | `gossip_batch_queries.py` |
| CR-L01-03 | HIGH | Confirmed | Defect | S | `memory_consolidation_engine` never passed to `get_tick_scheduler()` — has never run | `api/dependencies_engines/__init__.py:138-162` |
| CR-L01-04 | HIGH | Confirmed | Defect | M | Two bare `except Exception` in the degradation ladder turn a Neo4j outage into a canned 200, making the 4xx handler unreachable | `degradation.py:107,119`, `api/.../dialogue.py:97` |
| CR-L01-05 | HIGH | Confirmed | Gap | S | Source-string test "guards" the retrieval-profile 4xx without exercising it | `tests/` |
| CR-L01-06 | HIGH | Confirmed | Defect | S | Delete `TokenBudgetExceededError` or make the budget path actually fail (merges with CR-L08-03) | `utils/errors.py:301`, `docs/PROMPT_DESIGN.md:91` |
| CR-L01-07 | MEDIUM | Confirmed | Risk | M | The new budget guard is frozen against hand-copied constants with no re-measurement gate | `context_budget_enforcer.py` |
| CR-L01-08 | MEDIUM | Confirmed | Debt | S/M | `EngineFallbackPolicy` — five engines declare a degradation policy nothing reads | `engines/`, 5 YAML blocks |
| CR-L01-09 | MEDIUM | Confirmed | Risk | S | No composition-root assertion that every tick engine slot is filled (27 registered, 4 tested) | `api/dependencies_engines/` |
| CR-L01-10 | MEDIUM | Confirmed | Defect | M | Gossip side effects do not survive one bad pair | `engines/gossip/` |
| CR-L01-11 | LOW | Confirmed | Gap | S | Event-sampling RNG seed not logged (gossip already does) — violates the strict seed-logging rule | `engines/` |
| CR-L01-12 | LOW | Confirmed | Waste | S | Delete `engines/currency/` (12 LOC) and `engines/deception/` (128 LOC) — zero production callers | `engines/currency/`, `engines/deception/` |
| CR-L01-13 | LOW | Likely | Gap | S/L | Six engine contracts need either full coverage or an honest scope note | `src/npc_engine/engines/` contracts |
| CR-L02-01 | HIGH | Confirmed | Gap | M | `GraphUnavailableError` is dead code — Neo4j-outage→503 contract does not exist (merges into CR-L08-03) | `api/errors/exception_handlers.py`, `utils/errors.py:54` |
| CR-L02-05 | HIGH | Confirmed | Debt | XL | "No raw dict crossing a boundary" violated at the two most central interfaces — `BaseEngine.run_tick()` (29 impls), `LLMClientProtocol.generate_structured()`; 145 functions | `engines/`, `graph/`, `retrieval/` |
| CR-L02-07 | HIGH | Confirmed | Risk | N/A | Of the 17 roadmap items touching engine code, **100% require editing an existing file**; 71% of the backlog is eval meta-work | `project-harness/ROADMAP.md` |
| CR-L02-03 | MEDIUM | Confirmed | Defect | M | Two stateful singletons built outside every composition-root file; one a bare global dict under a module-level lock | `src/npc_engine/` |
| CR-L02-04 | MEDIUM | Confirmed | Gap | S | `check-rules` R005 (Cypher-leak) never scans `api/`, `auth/`, `data/`, `cache/`, `mutation/` | `scripts/check_rules.py` |
| CR-L02-06 | MEDIUM | Confirmed | Risk | L | `config.py` fan-in 74 — widest blast radius in the repo, 12× the next non-leaf module, with a stale 309-line waiver | `src/npc_engine/config.py` |
| CR-L02-02 | LOW | Confirmed | Process | S | CLAUDE.md's stack table claims "no OpenAI adapter ships today" — false since six weeks before its last edit | `project-harness/CLAUDE.md` |
| CR-L02-08 | LOW | Confirmed | Debt | S | The LLM factory's extension-point docstring describes a pattern the 3 shipped adapters don't follow | `engines/llm/factory` |
| CR-L04-01 | HIGH | Confirmed | Gap | M | 0 of 7 migrations has a down path or applied-state record; no written recovery procedure for a bad customer schema change | `scripts/migrations/` |
| CR-L04-03 | HIGH | Confirmed | Process | S | CLAUDE.md's literal "every session reads ISSUES.md" costs ~35K tokens / ~2.5h if honored — so it is silently ignored | `project-harness/CLAUDE.md` |
| CR-L04-02 | MEDIUM | Confirmed | Waste | S | `add_faction_support.py` dead since 2026-06-04; two docs still tell operators to run it | `scripts/migrations/add_faction_support.py` |
| CR-L04-04 | MEDIUM | Confirmed | Defect | S | README's "Migration scripts" line names two files that do not exist anywhere in the repo | `README.md` |
| CR-L04-05 | MEDIUM | Confirmed | Debt | S | `migrate_faction_strings.py` migrates data but never retires the field it migrates away from | `scripts/migrations/migrate_faction_strings.py` |
| CR-L04-06 | MEDIUM | Confirmed | Gap | M | No gate catches a required-field schema change shipped without a migration | `scripts/`, `type_registry/` |
| CR-L05-11 | **CRITICAL** | Confirmed | Defect | S | `/setup/*` auth exemption rests on a localhost bind `docker-compose.yml` does not provide — unauthenticated remote read of a plaintext API key | `auth/middleware_helpers.py`, `docker-compose.yml:72`, `api/routes/setup/setup.py:97` |
| CR-L05-01 | HIGH | Confirmed | Process | S/L | Delete or implement the three strict contracts whose machinery does not exist in `src/` | `project-harness/CLAUDE.md` |
| CR-L05-02 | HIGH | Confirmed | Waste | S/M | The 4-field engine-log mandate has 0% compliance across 118 call sites | `project-harness/CLAUDE.md`, `src/npc_engine/engines/` |
| CR-L05-03 | HIGH | Confirmed | Process | S | Compliance tracks the gate, not the rule — 100/100/28/66 across one docstring format; ungated `demo_game/` scores higher than gated `src/` | `scripts/docstring_audit.py` |
| CR-L05-04 | HIGH | Confirmed | Process | S/M | The 300-line and 40-line "hard limits" are floors with permanent exemption lists, and CLAUDE.md never says so | `project-harness/CLAUDE.md` |
| CR-L05-05 | MEDIUM | Confirmed | Gap | S | R004 matches a string never written in 967 commits and misses both real violations inside the file its rule names | `scripts/check_rules.py`, `utils/errors.py` |
| CR-L05-06 | MEDIUM | Confirmed | Risk | S/M | "Auth on all routes except `GET /health`" understates the unauthenticated surface by four classes | `project-harness/CLAUDE.md`, `auth/` |
| CR-L05-07 | MEDIUM | Confirmed | Defect | S | The layer model omits two real ranked packages; its dependency table is not what `check-layers` enforces | `project-harness/CLAUDE.md`, `scripts/check_layers.py` |
| CR-L05-08 | MEDIUM | Confirmed | Debt | S | The stack table is 18 days from its last edit and already wrong in three places | `project-harness/CLAUDE.md` |
| CR-L05-09 | MEDIUM | Confirmed | Waste | M | 9,150 tokens of mandatory preamble per session, ~1.8M to date, for a rule set that is 22/28 ungated | `project-harness/CLAUDE.md` |
| CR-L05-10 | LOW | Confirmed | Defect | S | Three pre-merge checklist items instruct sessions to satisfy things that do not exist | `project-harness/CLAUDE.md` |
| CR-L12-01 | HIGH | Confirmed | Risk | S/XL | The product roadmap was deferred to a side file on 2026-07-31; all 8 active ROADMAP programs are eval/harness | `project-harness/UNREAL_DEFERRED.md:3-7`, `ROADMAP.md` |
| CR-L12-02 | HIGH | Confirmed | Defect | M | `make package` has never been buildable — the PyInstaller spec references two paths absent at its own introducing commit | `packaging/`, `Makefile` |
| CR-L12-03 | HIGH | Confirmed | Gap | L | Unity and Unreal are named target clients; there are 0 lines of C# or C++ in the tree | `docs/BUSINESS_REQUIREMENTS.md`, `packaging/` |
| CR-L12-04 | HIGH | Confirmed | Risk | S/M | The pitch narrates a hand-seeded fixture as a working engine | `docs/DEMO_SCRIPT.md:147` |
| CR-L12-05 | HIGH | Confirmed | Gap | M | Four of five NFRs never measured; graph target off by 190× (52 nodes vs 10,000), throughput 10× untested | `docs/BUSINESS_REQUIREMENTS.md` |
| CR-L12-06 | HIGH | Confirmed | Risk | S/L | No integrator has ever existed; nothing in the repo supplies an external definition of "done" | whole tree |
| CR-L12-07 | MEDIUM | Confirmed | Debt | S | The HTTP contract has 148 operations and one sentence of stability policy | `docs/API.md` |
| CR-L12-08 | MEDIUM | Confirmed | Risk | S/M | `demo_game/`'s 1,116 tests are gated by nothing, while CI-gated code imports it | `demo_game/`, `.github/workflows/ci.yml` |
| CR-L12-09 | MEDIUM | Confirmed | Defect | S | The engine package cannot be imported except in one undocumented order | `src/npc_engine/__init__.py` |
| CR-L11-01 | HIGH | Confirmed | Process | M/L | The process machinery is now larger than the product (1.01:1 static) and outgrew it 8.7:1 over the last 200 commits | `project-harness/`, `scripts/`, `evals/` |
| CR-L11-02 | HIGH | Confirmed | Waste | M | 24 gate/loop scripts — 4,500 lines, 54% of the machinery — produced no downstream decision in 967 commits | `scripts/` |
| CR-L11-03 | HIGH | Confirmed | Waste | S/M | Every overnight-loop HALT was the harness tripping over its own self-tests; not one was a product defect | `scripts/loop_gates.py`, `project-harness/OVERNIGHT_LOOP.md` |
| CR-L11-04 | HIGH | Confirmed | Waste | S | `soft_review.md`'s ~60 loop-generated findings are read by nothing; one is still an open HIGH in this review | `project-harness/soft_review.md` |
| CR-L11-05 | HIGH | Confirmed | Process | M | In 967 commits the gate battery has **one** behaviour catch, made by a probe no gate runs | `scripts/`, `probe_context_ceiling.py` |
| CR-L11-06 | HIGH | Confirmed | Defect | S/M | The docstring rule plus a content-blind gate manufactured one of this review's CRITICALs | `project-harness/CLAUDE.md`, `scripts/docstring_audit.py` |
| CR-L11-07 | MEDIUM | Confirmed | Waste | S | 175 archived files / 16,724 lines are named nowhere outside the archive | `project-harness/archive/` |
| CR-L11-08 | MEDIUM | Confirmed | Waste | S | Fourteen single-use session prompts and handoffs are committed as permanent project records | `project-harness/` |
| CR-L11-09 | MEDIUM | Confirmed | Debt | S/M | The loop's first night burned 11.45h on ISSUE-126, still open; the loop has been dead 13 days | `scripts/expand_loop.py`, `ISSUE-126` |
| CR-L14-02 | HIGH | Confirmed | Waste | L | Gutting 105 of 180 repository methods to constants broke only the layer's own passthrough tests — graph reads are unguarded by `make check` | `graph/*_repository.py`, `tests/integration` |
| CR-L14-01 | HIGH | Confirmed | Defect | S | 15 `session_kwarg` tests + 49 docstring lines guard a parameter that no longer exists | `tests/unit/engines/test_military_engine.py:109`, `engines/military/military_engine.py:34` |
| CR-L14-03 | MEDIUM | Confirmed | Debt | L | The DIP-strict ports seam costs 8,565 lines / 107 files to move calls from engines to query functions | `src/npc_engine/engines/ports/` |
| CR-L14-04 | MEDIUM | Confirmed | Risk | M | `BaseEngine` types 33 scheduler parameters and enforces no signature — mypy stays clean with an incompatible engine | `engines/base_engine.py:24` |
| CR-L14-05 | MEDIUM | Confirmed | Defect | S | Three copies of the Neo4j→native converter with divergent error paths, each silently swallowing around a call to itself | `context_builder_helpers.py:41`, `graph_reader.py:212` |
| CR-L14-06 | LOW | Confirmed | Waste | S | 47 zero-call tests and 23 assertion-free tests; 12 restate a constant's own definition | `tests/` |
| CR-L14-07 | LOW | Confirmed | Process | S | The docstring mandate is enforced by a gate that never reads a function docstring | `scripts/docstring_audit.py` |
| CR-L09-01 | HIGH | Confirmed | Waste | S | Delete the 177 unreferenced archive files (17,699 lines) — also fixes the Windows clone blocker | `project-harness/archive/` |
| CR-L09-02 | HIGH | Confirmed | Process | S | Resolve the escalated gate conflict: wire `check-base-rate` (386 ln), delete `check-engine-coverage` (658 ln) | `scripts/`, `Makefile` |
| CR-L09-03 | HIGH | Confirmed | Debt | S/M | Decide the overnight loop's status — 5,178 lines carried 13 days with no owner | `scripts/`, `project-harness/OVERNIGHT_LOOP.md` |
| CR-L09-04 | HIGH | Confirmed | Waste | M | Cut `CLAUDE.md` 476 → 248 — highest-leverage line-for-line subtraction, ~2,600 tokens off every session | `project-harness/CLAUDE.md` |
| CR-L09-05 | MEDIUM | Confirmed | Waste | S | Delete the 12 one-shot session prompts (2,791 ln) and `.gitignore` the pattern | `project-harness/` |
| CR-L09-06 | MEDIUM | Confirmed | Defect | S | Delete the 15 `session_kwarg` tests and 76 phantom docstring lines — a live trap, not cosmetic debt | `tests/`, `engines/military/` |
| CR-L09-07 | MEDIUM | Confirmed | Risk | S/M | Do **not** subtract `demo_game/` — gate it; it is the eval program's fixture generator | `demo_game/`, `.github/workflows/ci.yml` |
