# NPC Engine — Full Codebase + Demo Review: Consolidated Findings

**Date:** 2026-06-13 · **Branch:** munich-demo · **HEAD:** 327180a
**Mode:** 9-lens parallel review (engines + demo)
**Prior review:** `project-harness/archive/review-2026-06-03/FINAL_REVIEW_FINDINGS.md` (2026-06-04)
**Evidence:** `project-harness/review-fixes/evidence/L1..L9.md`

> Regression-aware: re-verifies the 2026-06-04 fixes AND hunts new issues. The high-value delta this
> run is the **new scheme/intrigue feature surface (F1.6 / F2.3 / G2.2)** landed since the prior review.

---

## 1. Verdict

**The tree is bootable and green — no CRITICAL.** L9 ran the full stack: `make check` GREEN, mypy 0
errors across 469 files, `make test` 2141 passed / 0 failed, `make test-demo` 1081 passed, coverage
86.6%, `docker-compose config` valid, the prior CRITICAL (deleted `game_schema.yaml`) is committed and
bakes into the image. The demo is standalone (zero `src/` imports) with win **and** lose reachable.

**It is not release-clean.** The new scheme feature shipped with a debt cluster: a graph **write outside
any transaction** (L2-05) plus a non-atomic two-transaction advance path (L2-07/08), untyped status
strings (L3-08), and an opaque API envelope that discards the typed graph output (L3-09/15). Separately,
two prior "Fix now" items **regressed/never landed** (`from __future__` annotations, eval `sys.path`),
residual **error-message leakage** persists in 3 route sites (L1-08 / L8-02), and a 6-function graph
writer (`investigation_service.py`) is **0% tested** with raw `CREATE` writes (L4-09). All are bounded
fixes; none block boot. The only RED command is the known Windows-only U+2192 console crash (ISSUE-100).

## 2. Severity counts

| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 0 | — |
| HIGH | 8 | L2-05, L3-08, L3-09, L3-10, L3-11, L4-09, L5-01, L5-02, L8-02 *(9 raw; L3-11 reclassified MED in backlog)* |
| MEDIUM | ~17 | L1-08, L1-10, L1-12, L2-06, L2-07, L2-08, L3-12, L3-13, L3-14, L3-15, L4-08, L4-10, L4-11, L4-13, L5-03, L6-01, L6-03, L7-01-R, L8-01 |
| LOW | ~14 | L1-09, L1-11, L1-13, L2-09, L2-10, L2-11, L4-12, L4-14, L6-02, L6-04, L6-05, L7-02-R…L7-08, L9-10 |

Prior-SEV regression status (L8): **16 HOLDS · 7 PARTIAL · 2 REGRESSED** (L3-05, L4-06).

## 3. Systemic patterns (root-cause clusters)

1. **New-feature debt: schemes landed without the engine's own disciplines.** The single richest
   cluster. Transaction safety (L2-05 bare `session.run` write; L2-07/08 non-atomic advance + sub-writers
   owning tx), typing (L3-08 status not `Literal`; L3-13 covert props `dict`; L3-09/15 route discards the
   typed `SchemeWithSteps` via `.model_dump()` into `OkEnvelope[dict[str,Any]]`), and a test gap
   (L4-08 `mark_scheme_discovered` untested). The *core* scheme tick/reader code is 100% covered — the
   debt is concentrated at the writer + route boundaries.
2. **"DONE" overstated persists — 2 regressed, several partial.** L3-05 (138/469 files still miss
   `from __future__ import annotations`, called "a ruff one-liner") and L4-06 (5 eval files still inject
   `sys.path`) were "Fix now" and never landed. L1-02 redaction (PARTIAL — 2 newer routes leak), L4-02
   seed-log guard (still asserted-not-measured), L4-03 runner coverage (still excluded) all partial.
3. **Asserted-not-measured, again inside the guards.** L4-02/L8-01: `test_secret_propagation_logs_seed`
   injects `caplog` but never queries it — passes even if the log call is deleted. L4-10: `location_graph`
   route 422 guards are 0%-covered while the underlying query module has 16 tests. L4-12: intrigue panel
   tests assert crash-safety only.
4. **Boundary typing still half-done at the contract surface.** `response_model=` is now 147/147 (L3-01
   resolved), but 130/147 wrap `OkEnvelope[dict[str,Any]]` — opaque to every OpenAPI client — and
   `mypy --strict` (not the current gate) surfaces 274 errors. The contract a studio consumes is typed at
   the route decorator but `Any` in the payload.
5. **OCP seams mostly landed; residual closed Literals/if-chains remain.** Big wins since prior review:
   distortion registry, `location_writer.py`, LLM backend validator, `EmotionModelProtocol` all FIXED.
   Residuals are closed Literals/factories (distortion `REGISTRY_KEYS` frozen at import, emotion + TTS
   factories, mood-label table) — roadmap pre-work, not blocking.

## 4. Triage table

Legend: **Fix now** = bounded, this backlog · **Log** = ISSUES.md, defer · **Decide** = needs human call.
Severity uses CRITICAL/HIGH/MEDIUM/LOW (L2/L7 SEV-n mapped 2→HIGH,3→MED,4→LOW; L6 P2→MED,P3→LOW).

| id | sev | title | lens | disposition | SEV |
|----|-----|-------|------|-------------|-----|
| L2-05 | HIGH | `mark_scheme_discovered` WRITE via bare `session.run`, no tx | L2 | Fix now | SEV-01 |
| L2-07 | MED | scheme advance splits mint-Event + link-step across 2 tx (orphan risk) | L2 | Fix now | SEV-01 |
| L2-08 | MED | scheme sub-writers own their transactions (session-ownership) | L2 | Fix now | SEV-01 |
| L4-08 | MED | `mark_scheme_discovered` has no unit test | L4 | Fix now | SEV-01 |
| L1-08 | MED | `require_node` echoes URL `node_type` in 404 detail | L1 | Fix now | SEV-02 |
| L8-02 | HIGH | `locations.py:88` `str(exc)` + `economy.py:129` `node_id` leak (L1-02 gap) | L8 | Fix now | SEV-02 |
| L3-08 | HIGH | scheme `status: str\|None` no `Literal`; `"active"` hardcoded in Cypher | L3 | Fix now | SEV-03 |
| L3-15 | MED | schemes route `.model_dump()` discards typed `SchemeWithSteps` | L3 | Fix now | SEV-03 |
| L3-13 | MED | `build_covert_event_props` returns `dict[str,Any]` across boundary | L3 | Fix now | SEV-03 |
| L3-10 | HIGH | `knowledge_state` `"knows"`/`"rumor"` hardcoded at 4 sites, no `Literal` | L3 | Fix now | SEV-04 |
| L4-09 | HIGH | `investigation_service.py` 0% covered — 6 raw-`CREATE` writers, no tests | L4 | Fix now | SEV-05 |
| L3-05 | MED | 138/469 files miss `from __future__ import annotations` (REGRESSED) | L3/L8 | Fix now | SEV-06 |
| L3-11 | MED | `base_engine.run_tick -> dict` bare type-arg | L3 | Fix now | SEV-06 |
| L4-06 | MED | 5 eval test files inject `sys.path` (REGRESSED) | L4/L8 | Fix now | SEV-07 |
| L4-02 | MED | seed-log guard `caplog` injected but never queried (asserted-not-measured) | L4/L8 | Fix now | SEV-07 |
| L4-13 | MED | `evals/runner.py` 24% covered, excluded from gate | L4 | Fix now | SEV-07 |
| L4-10 | MED | `location_graph` route 422 guards 0% covered | L4 | Fix now | SEV-08 |
| L1-12 | MED | `.env` `LOG_LEVEL=DEBUG` no staging/prod gate | L1 | Fix now | SEV-09 |
| L2-09 | LOW | `check_layers` misses intra-rank + silently skips unranked `observability` | L2 | Fix now | SEV-10 |
| L6-02 | LOW | `ARCHITECTURE.md` prompt-path doc drift | L6 | Fix now | SEV-11 |
| L6-04 | LOW | `right_panel.py` docstring missing INTRIGUE tab | L6 | Fix now | SEV-11 |
| L6-05 | LOW | `game_controller.py` docstring lists non-existent dependency | L6 | Fix now | SEV-11 |
| L7-07 | LOW | `CliqueFormationEngine` magic numbers (70/10/50) not in config | L7 | Fix now | SEV-12 |
| L4-11 | MED | `schedule_queries.py` 24% covered | L4 | Log | ISSUE-101 |
| L4-12 | LOW | intrigue board panel tests crash-safety only | L4 | Log | ISSUE-102 |
| L5-03 | MED | 135 module docstrings carry stale auto-detected placeholder | L5 | Log | ISSUE-103 |
| L7-02-R..L7-06 | LOW | OCP residuals (emotion/TTS factory, mood table, llm `__init__`, step kind) | L7 | Log | ISSUE-104 |
| L2-11 | LOW | `dependencies_engines.py` past DEC-076 400-line cap | L2 | Log | ISSUE-105 |
| L4-14 | LOW | `asyncio.iscoroutinefunction` DeprecationWarnings | L4 | Log | ISSUE-106 |
| L6-01 | MED | no cross-session e2e test for persistent memory | L6 | Log | ISSUE-107 |
| L6-03/L9-10 | LOW | demo-run `--dry-run` Windows U+2192 crash | L6/L9 | Log (exists) | ISSUE-100 |
| L1-10/L1-06 | MED | `IDEMPOTENCY_ENFORCE_HEADER=false` advisory-only in staging/prod | L1 | Decide | DEC-111 |
| L1-13 | LOW | move `system_v1_router` under `admin_prefix` (interface change) | L1 | Decide | DEC-112 |
| L3-14 | MED | `mypy --strict` = 274 errors; current gate non-strict | L3 | Decide | DEC-113 |
| L3-09 | HIGH | 130/147 routes `OkEnvelope[dict[str,Any]]` opaque (full scope) | L3 | Decide | DEC-114 |
| L2-06 | MED | `dependencies_advanced.py` second composition root | L2 | Decide | DEC-115 |
| L2-10 | LOW | covert summary template outside `prompts/` | L2 | Decide | DEC-116 |
| L5-01/L5-02 | HIGH | 15 functions >40 lines (`advance()` 373, depth 7) ungated | L5 | Decide | DEC-117 |
| L4-09b | HIGH | `investigation_service` raw `CREATE` vs `MERGE` dedup semantics | L4 | Decide | DEC-118 |
| L2-01/L2-03 | HIGH | session-ownership systemic (14+ graph sub-writers own tx) | L2 | Decide | DEC-119 |
| L7-01-R | MED | `DistortionType` Literal + frozen `REGISTRY_KEYS` | L7 | Decide | DEC-120 |
| L7-08 | LOW | fat `LLMClientProtocol` (ISP split before SDK freeze) | L7 | Decide | DEC-121 |

**Fix-now SEVs: 12 (SEV-01…SEV-12). Decide: 11 (DEC-111…121). Log: 7 (ISSUE-101…107).**

See `review-fixes/INDEX.md` for the ordered backlog and `review-fixes/FIX-SEV-*.md` for per-item briefs.
