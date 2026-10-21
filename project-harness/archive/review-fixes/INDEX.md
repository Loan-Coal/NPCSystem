# Remediation backlog — full review 2026-09-07

> **SUPERSEDED 2026-09-08 by the T programme in `project-harness/ROADMAP.md`.** Do not work from
> this file directly; it is history. Every Fix-now SEV here maps to a roadmap task — SEV-02 through
> T7.1, SEV-03 through T7.2, and SEV-07 through T7.3, which was added on 2026-09-09 after an
> adversarial review found it had been dropped in translation. `ROADMAP.md` is canonical for what to
> work on next. See `project-harness/roadmap-review/FINDINGS.md` for the mapping.

**Source:** `project-harness/REVIEW_FINDINGS.md` (68 findings; 5 CRITICAL, 17 HIGH, 27 MEDIUM, 16 LOW)
**Branch:** `remediation-2026-08` · **Review HEAD:** `8d30a3e1` · **Tree was clean at review time**
**Evidence:** `project-harness/review-fixes/evidence/L*.md`

## Carry-forward notes
<!-- ≤10 lines. /fix-next and /fix-parallel append here. Starts empty. -->
- (empty)

---

## How to read this

15 **Fix now** items, grouped into dependency blocks A–F. Blocks A–D are the model-contention and
demo-breakage work and should go first — they contain every CRITICAL.

**9 items are blocked pending your decision** (§Decide below); they are NOT in the checklist and must not
be started. **35 items were dispositioned Log** and live in `ISSUES.md` as ISSUE-301…ISSUE-335, not here.

Two cautions that apply across blocks:
- `make check` is green and **executes zero real Cypher**, and the only demo gate is `--dry-run`. Passing
  the gates does not mean a fix works. For anything in blocks A, B or C, verify by running the demo live.
- The app image is **not** bind-mounted. Rebuild before any before/after measurement.

---

## Block A — the demo is unusable (do first, unblocks all live verification)

- [ ] **SEV-01** — WS slot leak: `_release_ws_slot` never runs, so the cap exhausts after 5 turns
      (deps: none · files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py`, `tests/unit/api/`)
      🔴 CRITICAL. Kills `make demo-run` at ACT 6 **and** the interactive UI after 5 dialogue turns.
      Everything else in this backlog that needs a live demo is blocked behind it.

## Block B — model contention (the small-model cluster; SEV-02 → SEV-03 → SEV-04 in order)

- [ ] **SEV-02** — `TICK_LLM_CALLS_PER_MINUTE_MAX` counts ticks, gates 2/5 engines, absent in `game_driven`
      (deps: none · files: `src/npc_engine/scheduler/`, `src/npc_engine/engines/base_engine.py`, `config.py`)
      🔴 CRITICAL. Contains the cheapest real win in the review: extending `skip_llm_engines` to the three
      quest triggers is ~5 lines and takes load-shedding from 25% to 100% coverage. Do that step first.
- [ ] **SEV-03** — quest triggers multiply to 40+ sequential model calls per tick, uncapped across 3 engines
      (deps: SEV-02 · files: `src/npc_engine/engines/quest_generation/`, `engines/quest/*trigger*.py`)
      🔴 CRITICAL. Shares a mechanism with SEV-02; land SEV-02's shared budget first or you fix it twice.
- [ ] **SEV-04** — no queue, priority or admission control in front of the single resident model
      (deps: SEV-02, SEV-03 · files: `src/npc_engine/engines/llm/`)
      🔴 CRITICAL. The structural fix. SEV-02 and SEV-03 reduce the load; this one arbitrates it.

## Block C — interactive latency (independent of B, parallelisable)

- [ ] **SEV-05** — no startup warm-up: the demo's opening line costs 20.1s end-to-end
      (deps: none · files: `src/npc_engine/main.py` or `setup/`, `engines/llm/ollama_adapter.py`)
      Cheapest user-visible win in the report. `keep_alive` fixes the *second* cold load, not the first.
- [ ] **SEV-06** — `max_tokens: 512` vs "1–3 sentences"; nothing structurally caps `npc_response`
      (deps: none · files: `src/npc_engine/engines/dialogue/llm_config.yaml`, `dialogue/dialogue_models.py`)
      **Free**: touches config + schema, NOT the prompt, so `dialogue_prompt_hash` is unchanged and eval
      comparability survives. Decode dominates and scales with output tokens — this is a real lever.
- [ ] **SEV-07** — gossip tick costs 24.25s: full corpus reconciliation per propagated pair, serial loop
      (deps: none · files: `src/npc_engine/engines/gossip/`, `engines/embedding_refresh.py`)
      Largest measured stall in the system, and it has zero LLM calls, so no LLM budget will ever shed it.

## Block D — unbounded work at the API boundary

- [ ] **SEV-08** — `delta_ticks: 1000` runs 27 engines 1000× in one request, one lock, stale snapshot
      (deps: none · files: `src/npc_engine/api/routes/` clock route, `config.py`)
- [ ] **SEV-09** — `/ws/dialogue` has no throughput rate limit; `BaseHTTPMiddleware` can't see WS scope
      (deps: SEV-01 (same file) · files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py`, `api/rate_limit.py`)
      Sequence after SEV-01 to avoid conflicting edits in the same handler.

## Block E — make the failures visible (these are why the CRITICALs survived every gate)

- [ ] **SEV-10** — per-engine declared timeouts are dead config for 4 of 5 engines
      (deps: none · files: `src/npc_engine/engines/*/llm_config.yaml`, `engines/llm_runtime_config.py`)
- [ ] **SEV-11** — auth wiring on the production `create_app()` has no regression test
      (deps: none · files: `tests/unit/api/`, `src/npc_engine/main.py`)
- [ ] **SEV-12** — `engine_status` is read by nothing and cannot express "starved"
      (deps: none · files: `src/npc_engine/engines/` status store, `api/routes/admin/`)
      Directly addresses §3.2: 17 of 27 engines inert with every `last_error` null.
- [ ] **SEV-14** — `arm_probe.py` / `arm_probe_report.py` at 0% coverage
      (deps: none · files: `evals/arm_probe*.py`, `tests/unit/evals/`)
      The measurement-integrity tool is itself unmeasured.
- [ ] **SEV-15** — no test pins tick execution order
      (deps: none · files: `src/npc_engine/scheduler/tick_scheduler.py`, `tests/unit/scheduler/`)
      Cheap. Every read-after-write dependency in `evidence/L13.md` §A.2 is currently breakable silently.

## Block F — ledger truth

- [ ] **SEV-13** — amend DEC-273: its constants are contradicted on 3 of 5 claims
      (deps: SEV-05 (re-measure after warm-up lands) · files: `project-harness/DECISIONS.md`)
      Documentation only, but DEC-273 is 3 days old and already being cited. Amend, do not retract — the
      mechanism holds, the numbers do not. Also archive ISSUE-273 (fixed, still open) while here.

---

## 🔒 Decide — blocked pending your approval, do NOT start

| # | Finding | The call you need to make |
|---|---|---|
| D1 → **DEC-274** | L6-01≡L9-02 🔴 | Demo auto-loses in 3s. Fix shape: seed the armies apart (honest), gate `military` cadence, or latch the legion lose path (hides it). Touches seed data + DECISIONS. |
| D2 → **DEC-276** | L13-01 | Seed writes no `:Schedule`/`FOLLOWS_SCHEDULE`. Add the edges (revives `routine` + 4 starved engines) or document the demo as scheduleless. Seed-data change → ask-gate. |
| D3 → **DEC-276** | L13-02 | 28 orphan `:Need` nodes, no `HAS_NEED`. Add edges (revives 2 dead engines) and re-scope ISSUE-210 off "cosmetic". Seed-data change → ask-gate. |
| D4 → **DEC-275** | L2-02 | 34/44 ports fail the repo's own DIP rule. Collapse ~30 to concrete injection, or record a deliberate waiver in DECISIONS if they pre-stage the Kùzu swap. Public-interface change → ask-gate. |
| D5 → **DEC-277** | L12-11 / L12-02 | Prompt edits for `facial_expression`/`mood_update` guidance and the Rule 8×2 conflict. **Each changes `dialogue_prompt_hash` and breaks eval comparability.** Timing is yours. |
| D6 → **DEC-277** | L12-14 | `dialogue_prompt_hash` covers the whole `prompts/` tree. Re-scoping is an `evals/` semantics change — existing recorded hashes would not reproduce. Needs its own DECISIONS entry. |
| D7 → **DEC-278** | L4-03 | Is the CI `integration-tests` job actually required for merge? Undeterminable locally. Decides whether "zero real Cypher in `make check`" is a local-only gap or fully open. |
| D8 → **DEC-279** | L10-01/02/03 | Delete set: 7 delete-candidate engines, `DeceptionEngine`/`SchemingEngine`, vaporware `currency`. Also: which side of the political-engine duplication is canonical, Engine class or graph service? |
| D9 → **DEC-280** | L9-08 + L2-01≡L7-05 | (a) Add a `demo-run-live` nightly target — brushes DEC-224 (retire-a-gate-to-add-one); read as a new *target*, not a new `make check` gate — confirm. (b) `TraitReadPort`: implement `Neo4jTraitReadRepository` or delete the dead port. |

---

## Suggested execution

```
/fix-parallel   → SEV-05, SEV-06, SEV-07, SEV-08, SEV-10, SEV-11, SEV-12, SEV-14, SEV-15
                  (independent, disjoint file sets)
/fix-next       → SEV-01, then SEV-09  (same file, must serialise)
/fix-next       → SEV-02 → SEV-03 → SEV-04  (strict order, shared mechanism)
/fix-next       → SEV-13  (after SEV-05 lands, so the re-measurement is real)
```
