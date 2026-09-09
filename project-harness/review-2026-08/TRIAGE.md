# Adversarial Triage — 2026-08 Strategic Codebase Review

> **Re-triaged 2026-09-08 against the current tree.** This file's CRITICALs were never
> cross-referenced when the T programme was written, because they use a `CR-L*` id namespace that
> roadmap does not. Result: **CR-L05-11** (compose bound `0.0.0.0`) and **CR-L08-03** (no 503
> handler for `GraphUnavailableError`) are **fixed**; **CR-L03-01** refers to a
> `hedge_responder_probe.py` that no longer exists and is presumed superseded by a refactor,
> unverified; **CR-L01-01** (gossip distortion written then discarded on read) and **CR-L15-01**
> (eval live-network digest defaults) were **still live** and are now scheduled as **T5.3** and
> **T16.6** in `project-harness/ROADMAP.md`. Evidence:
> `project-harness/roadmap-review/R6.md`.

**Triaged:** 2026-08-28 · HEAD `619dab2` (tree unchanged since the review) · 145 findings in, 118 canonical out.
**Method:** every verdict below rests on a command re-run at HEAD, a traced call chain, or a pasted
file excerpt. This file supersedes `FINDINGS.md` **by reference only** — `FINDINGS.md`,
`CODEBASE_REVIEW.md` and `evidence/` are the immutable record of 2026-08-28 and were not edited.

## Distribution

| Verdict | Count | % |
|---|---:|---:|
| UPHELD | 79 | 54.5% |
| MERGED (into a canonical ID) | 27 | 18.6% |
| RECALIBRATED | 21 | 14.5% |
| DEFERRED-VALID | 11 | 7.6% |
| WITHDRAWN | 7 | 4.8% |
| **Total** | **145** | |

**Canonical distinct problems after dedup: 118.**

Withdrawal rate sits just under the 5% band-floor. That is the expected shape for a set that had
already taken one calibration pass (3 CRITICALs downgraded, 1 finding withdrawn, 2 hypotheses
disproven before this session started). The easy kills were genuinely already gone. What this pass
bought instead is concentrated in **RECALIBRATED**: one finding upgraded to CRITICAL for a reason
the review did not identify, one CRITICAL's fix proven to be blocked by a finding the review filed
separately and never linked, and seven remedies inverted from "delete" to "fix" or "integrate".

## Did any of the four CRITICALs fall?

**No. All four survive, and one grew a fifth sibling.** Each was attacked directly:

| ID | Attack | Result |
|---|---|---|
| CR-L01-01 gossip | Read the Cypher at HEAD | **UPHELD.** `CYPHER_BATCH_EVENT_TRUST` returns `best_event.summary` — the canonical `Event` node's text. The sharer's own `k.distorted_summary`, which `CYPHER_BATCH_PROPAGATE_KNOWLEDGE` *does* write to the edge, is never read back. Distortion is stored and discarded every hop. |
| CR-L03-01 null responder | Read the probe + the published report | **UPHELD.** `hedge_responder_probe.py` defines `NotACapabilityCaseError` — "Raised when a case that is not `case_pos_*` is handed to the probe" — so the tool structurally *refuses* to score guard cases. The baseline could not have been taken. `evals/reports/20260825T231028Z.md:11` publishes `170/186 … 0.914` regardless. |
| CR-L08-03 the 503 contract | Three greps | **UPHELD, unambiguously.** `grep -rn "raise GraphUnavailableError" src/` → **0 rows**. `grep -rn "503" src/npc_engine/api/` → **0 rows**. `register_exception_handlers()` registers exactly four handlers (`RequestValidationError`, `HTTPException`, `ContentRatingViolationError`, `Exception`) — none for `GraphUnavailableError`. Three docstrings promise the contract. |
| CR-L05-11 `/setup/*` | Read compose + middleware at HEAD | **UPHELD and still live.** `docker-compose.yml:72` is `"8000:8000"`. `middleware_helpers.py:51` still reads `/setup/* is always public — localhost-only by bind (DEC-131)`. |

### The fifth CRITICAL is CR-L15-01, but not for the predicted reason

The prompt anticipated that CR-L15-01 would become CRITICAL *if CI were red*. It becomes CRITICAL
whether CI is red or green, and the mechanism is worse than "slow tests".

I first thought this finding was wrong. `tests/unit/evals/test_run_config.py:282,292` inject
`fetch_ollama_version_fn=lambda _u: "0.1.0"`, and `tests/unit/engines/test_eval_matchers.py`
monkeypatches `httpx.post` at every judge site — its docstring even says the network is
"unreachable via a monkeypatched httpx.post". That looked like a refutation.

It is not. Running the single cited file **timed out at 120 seconds** while collection took 0.07 s,
so the block is in execution. The cause is [run_config.py:260-262](../../evals/run_config.py#L260-L262):

```python
gen_digest_fn   = fetch_generation_digest   or _engine_adapter.fetch_model_digest
judge_digest_fn = fetch_judge_digest        or _engine_adapter.fetch_model_digest
version_fn      = fetch_ollama_version_fn   or _engine_adapter.fetch_ollama_version
```

The injection points **default to live network calls** (`engine_adapter.fetch_ollama_version` →
`httpx.get(f"{ollama_url}/api/version", timeout=10.0)`). Only 2 of the 17 tests inject fakes. The
other 15 call `resolve()` bare and make three real HTTP attempts each.

**Why this is CRITICAL rather than merely slow:** `fetch_ollama_version` and `fetch_model_digest`
are documented to return `None` on any failure. On a CI runner with nothing listening on `:11434`,
the connection is *refused instantly* — so the tests pass fast, recording `generation_model_digest=None`.
That is the exact field CR-L16-08 identifies as the only thing making eval scores comparable across
time. **The model-identity pinning silently records nothing in CI and nobody sees a failure.** Given
the Phase 0 answer — you intend to swap `qwen2.5:7b` for a smaller fine-tuned model — an instrument
that cannot record *which model produced a score* is not a slow test, it is a broken measurement.

This also means the answer to "is CI green?" is probably **green, and green is the problem.** That
inverts the prompt's expectation and is the single most important correction this triage makes.

---

## The verdict table

Legend: **U** upheld · **R** recalibrated · **M** merged · **W** withdrawn · **D** deferred-valid.

| ID | Orig Sev | Verdict | New Sev | Canonical | One-line reason |
|---|---|---|---|---|---|
| CR-L01-01 | CRITICAL | U | CRITICAL | — | Cypher read at HEAD returns `best_event.summary`, never the sharer's `distorted_summary`. |
| CR-L03-01 | CRITICAL | U | CRITICAL | — | Probe raises `NotACapabilityCaseError` on guard cases; baseline was structurally untakeable. |
| CR-L05-11 | CRITICAL | U | CRITICAL | — | `docker-compose.yml:72` still binds `0.0.0.0`; exemption still unconditional. Live today. |
| CR-L08-03 | CRITICAL | U | CRITICAL | — | Both greps return 0 rows; 4 handlers registered, none for `GraphUnavailableError`. |
| CR-L15-01 | HIGH | **R** | **CRITICAL** | — | Upgraded. `run_config.resolve()` defaults to 3 live network calls; 15/17 tests don't inject. Records `None` digests in CI. See above. |
| CR-L01-02 | HIGH | U | HIGH | — | `MERGE … SET k.distortion_level = w.distortion_level` is unconditional; overwrites seeded edges. |
| CR-L01-03 | HIGH | **R** | MEDIUM | — | "Has never run" is **false** — reachable via `POST /memories/consolidate` ([memories.py:275](../../src/npc_engine/api/routes/knowledge/memories.py#L275)). True claim is narrower: absent from the *tick* path only. |
| CR-L01-04 | HIGH | **R** | HIGH | — | Upheld, and promoted in the dep graph: it **blocks** CR-L08-03. The review never linked them. |
| CR-L01-05 | HIGH | U | HIGH | — | Source-string test asserts on text, not behaviour. |
| CR-L01-06 | HIGH | M | — | CR-L08-03 | `TokenBudgetExceededError(Exception)` at `errors.py:301` — same structured-error fix. |
| CR-L01-07 | MEDIUM | U | MEDIUM | — | `context_budget_enforcer.py` (577 ln) holds hand-copied constants with no re-measure gate. |
| CR-L01-08 | MEDIUM | U | MEDIUM | — | `EngineFallbackPolicy` declared in 5 YAML blocks, read by nothing. |
| CR-L01-09 | MEDIUM | U | MEDIUM | — | Confirmed by CR-L01-03: a `None` engine slot silently no-ops at `tick_scheduler.py:530`. |
| CR-L01-10 | MEDIUM | U | MEDIUM | — | One bad pair aborts the batch write. |
| CR-L01-11 | LOW | U | LOW | — | Event-sampling seed unlogged; gossip logs its own. |
| CR-L01-12 | LOW | **R** | LOW | — | Facts hold (`currency/` = 12 ln stub; `deception/` = 128 ln, test-only). **Remedy inverted by user decision: integrate, do not delete.** |
| CR-L01-13 | LIKELY | D | LOW | — | "Full coverage **or** an honest scope note" is unfalsifiable as written — the note always satisfies it. |
| CR-L02-01 | HIGH | M | — | CR-L08-03 | Same defect, different lens. |
| CR-L02-02 | LOW | M | — | CR-L09-04 | CLAUDE.md factual drift; fixed by the rewrite. |
| CR-L02-03 | MEDIUM | U | MEDIUM | — | Two stateful singletons outside every composition root. |
| CR-L02-04 | MEDIUM | U | MEDIUM | — | R005 `_CYPHER_SCAN_DIRS` excludes `api/`, `auth/`, `data/`, `cache/`, `mutation/`. |
| CR-L02-05 | HIGH | U | HIGH | — | `base_engine.py:24`: `async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]`. Raw dict, no signature. |
| CR-L02-06 | HIGH | U | HIGH | — | Canonical for the `config.py` cluster. 504 ln vs a 309-line waiver; fan-in 74. |
| CR-L02-07 | HIGH | **W** | — | — | **Withdrawn.** "100% of engine items edit an existing file" describes normal software work. It only reads as risk under OCP-strict — an ungated aspirational rule the review itself recommends rewriting. Self-referential. |
| CR-L02-08 | LOW | U | LOW | — | Factory docstring describes a pattern its 3 adapters don't follow. |
| CR-L03-02 | HIGH | **R** | HIGH | — | Upheld and **worse**: `dashboard/headline.py:140` calls `check_publication(scorer, kappa, (0.0, 0.0))` — a hardcoded fake interval. The parameter isn't just ignored, it's fabricated. |
| CR-L03-03 | HIGH | U | HIGH | — | MDE exceeds headroom on 2 of 3 judges. |
| CR-L03-04 | HIGH | U | HIGH | — | `grep "check-base-rate\|check-engine-coverage" Makefile .github/workflows/ci.yml` → 0 rows. |
| CR-L03-05 | HIGH | U | HIGH | — | `wc -l evals/trend/trend_v1.jsonl` → **1**. One row, self-incomparable. |
| CR-L03-06 | HIGH | U | HIGH | — | Aggregator turn/verdict counts disagree with the row store. |
| CR-L03-07 | MEDIUM | M | — | CR-L06-09 | Same two gates, same superseded generation. |
| CR-L03-08 | MEDIUM | U | MEDIUM | — | 18/36 forbidden-keyword assertions are guaranteed passes. |
| CR-L03-09 | MEDIUM | U | MEDIUM | — | Capability headline rests on 16 cases; a third of the corpus unscored. |
| CR-L03-10 | MEDIUM | U | MEDIUM | — | Unparseable verdict recorded as substantive NO; verdicts flip on latency. |
| CR-L03-11 | MEDIUM | U | MEDIUM | — | 0.628 vs a 0.95 gate, recorded NOT_MET, gated by nothing. |
| CR-L03-12 | LOW | **R** | LOW | — | Facts hold. Remedy deferred to the value judgement you asked for — see §Integrate-or-delete. |
| CR-L04-01 | HIGH | U | HIGH | — | 0 of 7 migrations has a down path or applied-state record. |
| CR-L04-02 | MEDIUM | U | MEDIUM | — | `add_faction_support.py` present; still named in `docs/API.md` and `docs/DATA_MODELS.md`. |
| CR-L04-03 | MEDIUM | M | — | CR-L09-04 | The ISSUES.md read mandate is one of the lines the CLAUDE.md rewrite deletes. |
| CR-L04-04 | MEDIUM | M | — | CR-L13-02 | Same onboarding-doc repair pass. |
| CR-L04-05 | MEDIUM | U | MEDIUM | — | Migrates data, never retires the source field. |
| CR-L04-06 | MEDIUM | U | MEDIUM | — | No gate catches a required-field schema change without a migration. |
| CR-L05-01 | HIGH | M | — | CR-L08-03 | The three fictional contracts are the same claim as the 503 gap. |
| CR-L05-02 | HIGH | U | HIGH | — | Re-measured: 43 `logger.info` calls in `engines/`, **0** contain `duration_ms`. 0% confirmed. |
| CR-L05-03 | HIGH | U | HIGH | — | Compliance tracks the gate, not the rule. |
| CR-L05-04 | HIGH | U | HIGH | — | "Hard limits" have a 133-entry permanent exemption list CLAUDE.md never mentions. |
| CR-L05-05 | MEDIUM | U | MEDIUM | — | `check_rules.py:22` — R004 matches literal `raise Exception(`. |
| CR-L05-06 | MEDIUM | M | — | CR-L09-04 | Auth-surface claim corrected in the rewrite. |
| CR-L05-07 | MEDIUM | M | — | CR-L09-04 | Layer table corrected in the rewrite. |
| CR-L05-08 | MEDIUM | M | — | CR-L09-04 | Stack table corrected in the rewrite. |
| CR-L05-09 | MEDIUM | M | — | CR-L09-04 | Token cost is the *motivation* for the rewrite, not a separate fix. |
| CR-L05-10 | LOW | M | — | CR-L09-04 | Checklist items deleted by the rewrite. |
| CR-L06-01 | HIGH | **R** | MEDIUM | — | **Remedy inverted.** Ran it live: prints **14 gates, 16 blocked tasks**, exit 0. The "0 gates" evidence is a counterfactual artifact, not live state. Real defect is "always exits 0". Do **not** delete it — it is the only tracker of 16 blocked human tasks in a program you are keeping. |
| CR-L06-02 | HIGH | U | HIGH | — | Confirmed verbatim: `check_conservation.py:164` is `all_slots = compare_slots`, then `ok=(compare_slots == all_slots)`. Literal `x == x`, with a comment saying it holds by construction. |
| CR-L06-03 | HIGH | U | HIGH | — | Canonical. `main()` ends `return 0`; docstring says "Exits 0 always". |
| CR-L06-04 | HIGH | M | — | CR-L06-05 | Symptom of the file-level-signature mechanism. |
| CR-L06-05 | HIGH | U | HIGH | — | Confirmed **by the gate's own docstring**, `check_rules.py:27`: "Signatures are file-level … so they stay stable across edits." |
| CR-L06-06 | HIGH | U | HIGH | — | CI runs 6 of the 14 `make check` targets. |
| CR-L06-07 | HIGH | U | MEDIUM | — | Canonical for the check-harness cluster. |
| CR-L06-08 | MEDIUM | U | MEDIUM | — | Verifies the substring `Layer:` exists, nothing more. |
| CR-L06-09 | MEDIUM | U | MEDIUM | — | Canonical (absorbs CR-L03-07). |
| CR-L06-10 | MEDIUM | U | MEDIUM | — | Canonical for the demo_game-ungated cluster. |
| CR-L06-11 | LOW | **R** | LOW | — | Facts hold (`line-length = 120`, `extend-select = ["I002"]`, E501 not in ruff defaults). But "**runs in 0 s**" is not evidence of a defect — ruff is simply fast. Framing corrected. |
| CR-L06-12 | MEDIUM | M | — | CR-L13-01 | Same file, same stale-numbers fix. |
| CR-L07-01 | HIGH | U | HIGH | — | ISSUE-145 is a stale P1, root cause fixed under other IDs. |
| CR-L07-02 | HIGH | U | HIGH | — | 5 DEC + 2 ISSUE IDs reused. Directly constrains Phase 4 ID assignment. |
| CR-L07-03 | HIGH | M | — | CR-L08-02 | Same `game_window.py` waiver breach. |
| CR-L07-04 | MEDIUM | U | MEDIUM | — | ISSUE-122 prescribes a fix already present when filed. |
| CR-L07-05 | MEDIUM | D | MEDIUM | — | A trend measurement, not a defect. It is the *reason* for the roadmap cull, not an item in it. |
| CR-L07-06 | MEDIUM | U | MEDIUM | — | 53% of DECISIONS.md unreferenced; 4/12 sampled drift. |
| CR-L07-07 | MEDIUM | U | MEDIUM | — | Three scripts share one hardcoded stale corpus default. |
| CR-L07-08 | LOW | U | LOW | — | `SKILLS_QUEUE.md` dead ~90 days, still normatively referenced. |
| CR-L08-01 | HIGH | U | HIGH | — | Re-measured: `client.py` **1901**, `seed.py` **1677**. |
| CR-L08-02 | HIGH | **R** | HIGH | — | Upheld at 925 lines, but the review's path is wrong: the file is `demo_game/ui/layout/game_window.py`, not `demo_game/game_window.py`. Citation corrected. Canonical (absorbs CR-L07-03). |
| CR-L08-04 | MEDIUM | U | MEDIUM | — | `scripts/` (7,821 LOC) outside the 300/40 gates. |
| CR-L08-05 | LOW | U | LOW | — | Re-measured: `rules_baseline.txt` 136 ln, `evals_baseline.txt` 75 ln. "313" matches nothing. |
| CR-L08-06 | LOW | **W** | — | — | Withdrawn upstream by the orchestrator; carried forward unchanged. |
| CR-L08-07 | LOW | U | LOW | — | Duplicated `_draw_no_data` across demo panels. |
| CR-L08-08 | MEDIUM | U | MEDIUM | — | Waiver-mandated top-of-file comments missing on 4 files. |
| CR-L08-09 | LOW | U | LOW | — | Canonical. 182,118 bytes, dated Jun 24; `git grep` finds only harness/review prose, zero code. |
| CR-L09-01 | HIGH | **R** | HIGH | — | Upheld; numbers restated. Archive holds **265 files / 30,868 md lines** total; the 177-file / 17,699-line figure is the *unreferenced subset*, which is what gets deleted. |
| CR-L09-02 | HIGH | U | HIGH | — | Canonical (absorbs CR-L13-03). |
| CR-L09-03 | HIGH | **R** | HIGH | — | **Resolved by Phase 0, remedy inverted.** The loop is kept and reworked, not deleted. §D row 3 (5,178 ln) is off the subtraction ledger. |
| CR-L09-04 | HIGH | U | HIGH | — | Canonical for the whole CLAUDE.md cluster (absorbs 7 findings). |
| CR-L09-05 | HIGH | U | MEDIUM | — | Canonical (absorbs CR-L11-08). |
| CR-L09-06 | MEDIUM | M | — | CR-L14-01 | Same `session_kwarg` tests. |
| CR-L09-07 | MEDIUM | M | — | CR-L06-10 | "Gate demo_game, don't cut it" is the remedy for CR-L06-10. |
| CR-L10-01 | HIGH | U | HIGH | — | Budget contract violated ~2.5 months; replacement hardcodes a measured ceiling. |
| CR-L10-02 | MEDIUM | U | MEDIUM | — | `context_builder.py` is 799 lines; the justification comment understates it. |
| CR-L10-03 | MEDIUM | U | MEDIUM | — | `calibration.py` is 875 lines, past its own DEC-169 trigger. |
| CR-L10-04 | HIGH | D | HIGH | — | A churn observation. Actionable only through CR-L02-06 and the eval-program decision. |
| CR-L10-05 | MEDIUM | M | — | CR-L02-06 | Same file, same waiver. |
| CR-L10-06 | LOW | D | LOW | — | Measurement backing C2, not a fixable item. |
| CR-L10-07 | LOW | **W** | — | — | **Withdrawn.** Effort `N/A`, no action, and it restates CR-L10-06. An observation filed as a finding. |
| CR-L10-08 | LOW | **W** | — | — | **Withdrawn.** `Suspected` confidence. A 37-day gap in a solo project between phases is not a defect, and the "fix" (document it) has no consumer. |
| CR-L11-01 | HIGH | D | HIGH | — | The review's thesis, measured. Its remedy *is* this remediation program. |
| CR-L11-02 | HIGH | D | HIGH | — | Same; the 24 scripts are addressed individually elsewhere. |
| CR-L11-03 | HIGH | **R** | HIGH | — | **Scope changed by Phase 0.** No longer evidence for deletion; now the acceptance criterion for the loop rework. |
| CR-L11-04 | HIGH | U | MEDIUM | — | `soft_review.md`, 305 ln, read by nothing. Re-file the one surviving HIGH first. |
| CR-L11-05 | HIGH | D | HIGH | — | The 9-catches measurement. Becomes a DEC (counterfactual rule), not a fix. |
| CR-L11-06 | HIGH | U | HIGH | — | A docstring mandate + content-blind gate manufactured CR-L08-03's *documentation*. |
| CR-L11-07 | MEDIUM | M | — | CR-L09-01 | Same archive. |
| CR-L11-08 | MEDIUM | M | — | CR-L09-05 | Same session prompts. |
| CR-L11-09 | MEDIUM | **R** | HIGH | — | **Upgraded.** ISSUE-126 (`--dry-run` hangs) was deferrable while the loop was dead. You are restarting it, so it is now a prerequisite. |
| CR-L12-01 | HIGH | **R** | MEDIUM | — | **Resolved by Phase 0.** Track is *deliberately* paused, which was the finding's actual ask ("say so in writing"). Reduced to filing the DEC. |
| CR-L12-02 | HIGH | **R** | HIGH | — | Upheld with **stronger, present-tense** evidence. The review argued from the introducing commit; I checked HEAD: the spec's `datas` names `config/` and `game_schema.yaml`, **neither of which exists**, and PyInstaller is not a declared dependency. It fails today, not just historically. |
| CR-L12-03 | HIGH | **R** | MEDIUM | — | 0 lines of C#/C++ confirmed (only `.venv` third-party). Severity cut: with the Unreal DemoGame now the integrator, this is planned work, not an unacknowledged gap. |
| CR-L12-04 | HIGH | U | HIGH | — | The pitch narrates a hand-seeded fixture. Blocked behind CR-L01-01. |
| CR-L12-05 | HIGH | U | HIGH | — | 4 of 5 NFRs never measured; 52 nodes vs a 10,000 target. |
| CR-L12-06 | HIGH | **W** | — | — | **Withdrawn as of 2026-08-28.** "No integrator has ever existed" is now false — the Unreal DemoGame is a declared external consumer built to exercise this engine. The external clock exists. |
| CR-L12-07 | MEDIUM | **R** | HIGH | — | **Upgraded.** 148 operations, one sentence of stability policy. Trivial while nothing consumed the API; now load-bearing, because "don't break future Unreal integration" is an explicit goal. |
| CR-L12-08 | MEDIUM | M | — | CR-L06-10 | Same ungated `demo_game/`. |
| CR-L12-09 | MEDIUM | **W** | — | — | **Withdrawn — does not reproduce.** `python -c "import npc_engine; print('IMPORT OK')"` → `IMPORT OK`. No ordering constraint at HEAD. |
| CR-L13-01 | HIGH | U | HIGH | — | Canonical. `HARNESS_GATES.md:33-34` still says "57 today" / "256 today"; live is 133 and 0. |
| CR-L13-02 | HIGH | U | HIGH | — | Canonical. 5 `project/` links; `ls project/` → No such file or directory. |
| CR-L13-03 | MEDIUM | M | — | CR-L09-02 | The docs are wrong because the targets were never wired. |
| CR-L13-04 | HIGH | U | HIGH | — | Canonical for README (absorbs CR-L13-05). |
| CR-L13-05 | HIGH | M | — | CR-L13-04 | Same file, same pass. |
| CR-L13-06 | HIGH | M | — | CR-L06-07 | Confirmed inert: `NEXT_SESSION.md` exists **only** at `project-harness/archive/stale-2026-06/`. |
| CR-L13-07 | HIGH | M | — | CR-L13-01 | Same file, same pass. |
| CR-L13-08 | MEDIUM | U | MEDIUM | — | CHANGELOG 96 commits stale, still on the `project/` tree. |
| CR-L13-09 | MEDIUM | U | MEDIUM | — | `docs/API.md` missing 6 live routes incl. `/setup/*`. |
| CR-L13-10 | MEDIUM | U | LOW | — | `EVAL_STRATEGY.md` is a stale duplicate. Deletion, approved. |
| CR-L13-11 | LOW | M | — | CR-L08-09 | Same file. |
| CR-L14-01 | HIGH | U | HIGH | — | Canonical. `military_engine.py:34` is `async def run_tick(self, *, tick_id: int)` — no `session`. 61 `session_kwarg` references guard it. |
| CR-L14-02 | HIGH | U | HIGH | — | The executed counterfactual. Blocked behind Neo4j-in-CI. |
| CR-L14-03 | MEDIUM | U | MEDIUM | — | DIP-strict ports cost 8,565 ln / 107 files. |
| CR-L14-04 | MEDIUM | U | MEDIUM | — | Confirmed at `base_engine.py:24` — `*args, **kwargs` enforces nothing. |
| CR-L14-05 | MEDIUM | U | MEDIUM | — | Three converter copies with divergent swallowing error paths. |
| CR-L14-06 | LOW | U | LOW | — | 47 zero-call + 23 assertion-free tests. |
| CR-L14-07 | LOW | M | — | CR-L06-08 | Same content-blind docstring gate. |
| CR-L15-02 | HIGH | U | HIGH | — | `intent_queries.py` at 34.6% real coverage, mocked at three layers. |
| CR-L15-03 | MEDIUM | M | — | CR-L06-03 | Same gate. |
| CR-L15-04 | MEDIUM | U | MEDIUM | — | Real hook cost 4.9 s, not 595 s; CLAUDE.md implies otherwise. |
| CR-L15-05 | LOW | U | LOW | — | `mypy src/` runs twice per `make check`. |
| CR-L15-06 | HIGH | U | HIGH | — | 36,527 LOC with no coverage floor, incl. the gate scripts. |
| CR-L16-01 | HIGH | U | HIGH | — | Confirmed: `.gitignore:61` ignores `.env`; only `.env.example` is tracked. `grep longpaths` over README/CONTRIBUTING/docs → 0 rows. |
| CR-L16-02 | MEDIUM | M | — | CR-L13-02 | Same onboarding-doc pass. |
| CR-L16-03 | HIGH | U | HIGH | — | Documented path never rebuilds the app image. Matches the saved memory on this repo. |
| CR-L16-04 | HIGH | U | HIGH | — | Confirmed: both `import torch` and `import sentence_transformers` raise `ModuleNotFoundError` against `pyproject.toml:19-20` hard deps. |
| CR-L16-05 | MEDIUM | U | MEDIUM | — | No ceiling, no lockfile. |
| CR-L16-06 | MEDIUM | **R** | LOW | — | **Resolved by Phase 0** — 3.14 everywhere. Reduced from a decision to a mechanical edit. |
| CR-L16-07 | MEDIUM | U | MEDIUM | — | Confirmed: healthchecks exist on `neo4j` and `redis` only; `app:` has none, and the Dockerfile has no `USER`. |
| CR-L16-08 | LOW | **R** | MEDIUM | — | **Upgraded.** Model tag not content-addressed. Was cosmetic; is now load-bearing because CR-L15-01 nulls the digest in CI *and* you plan a model swap. |
| CR-L16-09 | LOW | U | LOW | — | `docker-compose.yml:38`: `NEO4J_AUTH: neo4j/password`. |

---

## Evidence for the non-UPHELD verdicts

Only the seven withdrawals and the judgement-heavy recalibrations are expanded here; the table's
one-line reasons carry the rest, and every one of them names the command or the file:line that
produced it.

### WITHDRAWN

**CR-L12-09 — "the engine package cannot be imported except in one undocumented order."**
```
$ python -c "import npc_engine; print('IMPORT OK')"
IMPORT OK
```
No ordering constraint exists at HEAD. Either it was fixed between the review and now (the tree is
unchanged, so no), or the original was wrong. Killed.

**CR-L12-06 — "No integrator has ever existed."** True on 2026-08-28 at 00:52. False by 11:00: the
Unreal DemoGame at `Documents/hackathons/DemoGame` is being built expressly to showcase this engine.
This is the single most consequential change to the review's thesis — root cause **C2 ("no external
clock, so the scoreboard became the product") now has a clock.** The finding is withdrawn; the
*pattern* it evidenced remains real and is why the roadmap cull still happens.

**CR-L02-07 — "100% of the 17 roadmap items touching engine code require editing an existing file."**
The measurement is fine; the inference is not. Editing existing files is what software development
consists of. This is only a "Risk" if OCP-strict ("never edit existing engine files to add a
variant") is binding — and the review elsewhere establishes that OCP-strict is one of the 22 ungated
rules and recommends rewriting it. The finding uses a rule it is concurrently arguing is fictional as
the standard by which the codebase fails. Circular. The real finding is the OCP rule itself
(CR-L09-04). Note the second clause — "71% of the backlog is eval meta-work" — is true and survives
as CR-L11-01/CR-L10-04; only the 100% claim is withdrawn.

**CR-L10-07 — "Commit velocity is loop-driven, not human-paced."** Effort is filed as `N/A`, there is
no proposed action, and the content restates CR-L10-06. A finding with no possible fix and no
distinct claim is an observation. It belongs in §C of the review, where it already is.

**CR-L10-08 — "A 37-day commit gap is undocumented."** `Suspected`, not `Confirmed`. A solo project
pausing between phases is not a defect, and the remedy — write a note about the gap — has no reader.
Filing it would grow `project-harness/`, which is the thing this program exists to shrink.

**CR-L08-06** — carried forward from the orchestrator's own withdrawal, unchanged.

**A note on the rate.** Seven of 145 is 4.8%, marginally under the 5% band. I did not manufacture an
eighth. Two candidates were considered and rejected: CR-L01-03, where "has never run" is genuinely
false but a real one-kwarg defect survives underneath (→ RECALIBRATED), and CR-L06-01, where the
cited evidence is a counterfactual artifact rather than live state but the "always exits 0" defect is
real (→ RECALIBRATED, remedy inverted). Downgrading a wrong *claim* to a correct narrower one is
more honest than a withdrawal that would let the underlying defect escape.

### The recalibrations that change what gets built

**CR-L06-01 — do not delete `check-human-gates`.** Run live at HEAD it emits 14 gates, 6 OPEN, 16
blocked tasks, and a runbook pointer per gate — then exits 0. The review's "0 gates, exit 0" is what
the gate prints *after* you delete `HUMAN_TASKS.md`, i.e. the counterfactual, not the current state.
The defect is real and is the same class as CR-L06-03 (cannot fail). But the recommendation inverts:
this is the only artifact tracking 16 blocked human tasks in an eval program you are **keeping**.
Deleting it destroys live information. Fix the exit code; keep the gate.

**CR-L01-04 blocks CR-L08-03 — a dependency the review never drew.** §E item 4 says "raise
`GraphUnavailableError` on driver `ServiceUnavailable`, register a 503 handler". Doing only that will
**not** produce a 503, because [degradation.py:107 and :119](../../src/npc_engine/engines/dialogue/degradation.py#L107)
are `except Exception` blocks that log the failure and fall through to the next tier, ending at a
canned 200 response. The new `GraphUnavailableError` would be caught by the first of them and
swallowed before any handler sees it. **CR-L01-04 must land first or in the same change**, and the
acceptance test in `FIX_PLANS.md` is written to fail if it does not.

**CR-L12-07 — API stability policy, MEDIUM → HIGH.** "Don't break future Unreal integration" was
your stated constraint. 148 operations governed by one sentence of stability policy is exactly how
that constraint gets violated by accident. This is now the cheapest insurance in the plan.

---

## The canonical set — 118 distinct problems

27 findings merged into 20 canonical IDs. The clusters:

| Canonical | Absorbs | Cluster |
|---|---|---|
| CR-L08-03 | CR-L02-01, CR-L01-06, CR-L05-01 | The 503 / structured-error contract |
| CR-L09-04 | CR-L02-02, CR-L04-03, CR-L05-06, CR-L05-07, CR-L05-08, CR-L05-09, CR-L05-10 | The CLAUDE.md rewrite |
| CR-L13-01 | CR-L06-12, CR-L13-07 | `HARNESS_GATES.md` |
| CR-L13-02 | CR-L04-04, CR-L16-02 | Onboarding docs |
| CR-L13-04 | CR-L13-05 | `README.md` |
| CR-L09-01 | CR-L11-07 | The archive |
| CR-L09-05 | CR-L11-08 | One-shot session prompts |
| CR-L09-02 | CR-L13-03 | base-rate / engine-coverage gates |
| CR-L06-03 | CR-L15-03 | `check-test-quality` |
| CR-L06-07 | CR-L13-06 | `check-harness` |
| CR-L06-05 | CR-L06-04 | The ratchet mechanism |
| CR-L06-09 | CR-L03-07 | conservation / label-survival |
| CR-L06-10 | CR-L12-08, CR-L09-07 | Ungated `demo_game/` |
| CR-L06-08 | CR-L14-07 | Content-blind docstring gate |
| CR-L08-02 | CR-L07-03 | `game_window.py` |
| CR-L08-09 | CR-L13-11 | `live_openapi.json` |
| CR-L02-06 | CR-L10-05 | `config.py` |
| CR-L14-01 | CR-L09-06 | `session_kwarg` |

---

## Dependency graph

The edges that matter. **Violating one of these means doing the work twice.**

```
R0  SECURITY (out of band, do before anything)
    CR-L05-11 ─── bind 127.0.0.1 + gate exemption on env=="dev"

R1  GATE INTEGRITY — must precede every code change below
    CR-L06-05 (line-count-bearing signatures)
      └─blocks→ CR-L08-01, CR-L08-02, CR-L02-06   (splits re-grow without it)
    CR-L06-03, CR-L06-01, CR-L06-02, CR-L06-07, CR-L06-09  (gates that can't fail)
      └─must land BEFORE→ CR-L15-01 / CR-L06-06   (don't wire theatre into CI)
    CR-L05-04 ─pairs with→ CR-L06-05  (the doc must describe the new rule)

R2  MEASUREMENT — everything downstream is unmeasurable until these land
    CR-L15-01 (unit tests hit the network; CI records None digests)   ← THE 5th CRITICAL
      ├─blocks→ CR-L03-01  (no trustworthy baseline without model identity)
      ├─blocks→ CR-L16-08  (content-addressing is meaningless if the digest is None)
      └─enables→ CR-L14-02 (Neo4j in CI un-skips the 34 integration tests)
    CR-L09-02 (wire check-base-rate) ─depends on→ CR-L15-01
    CR-L03-01 ─depends on→ CR-L09-02, CR-L15-01
    CR-L03-08 ─CONFLICT→ CR-L03-01   (see below)

R3  PRODUCT CORRECTNESS
    CR-L01-04 ─BLOCKS→ CR-L08-03      ← the edge the review missed
    CR-L08-03 ─enables→ CR-L01-05
    CR-L01-01 (gossip distortion)
      ├─must land WITH→ CR-L01-02  (fixing relay without the MERGE fix still erases the seed)
      ├─invalidates→ eval golden strings + gossip determinism fixtures
      │              └─therefore COLLIDES with R2; sequence gossip AFTER the baseline is trustworthy
      └─unblocks→ CR-L12-04  (the pitch can stop narrating a fixture)
    CR-L01-03 (one kwarg) — independent, do anytime

R4  SUBTRACTION
    CR-L09-01 (archive) ─also fixes→ CR-L16-01 (Windows longpath clone blocker)
    CR-L11-04 (soft_review.md) ─depends on→ re-filing its one surviving HIGH first
    CR-L14-01 / CR-L08-07 / CR-L08-09 — independent
    CR-L09-04 (CLAUDE.md) ─depends on→ R1 complete (must describe the rules that now exist)

R5  INTEGRATOR-FACING
    CR-L12-07 (API stability policy) — do EARLY; cheap now, expensive after Unreal binds
    CR-L16-06 (3.14) ─blocks→ CR-L16-04 (torch install) ─blocks→ RAG path coverage
    CR-L04-01 (migration down paths), CR-L12-02 (make package)
    CR-L12-05 (NFRs) ─depends on→ CR-L01-01 (measuring a broken feature is worthless)

R6  LOOP REWORK (kept, per Phase 0)
    CR-L11-09 (ISSUE-126 dry-run hang) ─blocks→ restart
    CR-L11-03 ─is the acceptance criterion→ a HALT must be a product defect, not a self-test
      └─depends on→ R1 complete (the loop's HALTs come from the gate battery)
```

### Conflicts between findings

Four, of which the review resolved none. L9 §D resolved six *inter-lens* conflicts (base-rate vs
engine-coverage, the archive, conservation ordering, `scan_fix_diff.py`, the sequence subsystem's
consumers) — those are settled and are **not** re-litigated here. These are different:

1. **CR-L03-08 vs CR-L03-01 — deleting dead assertions moves the number the baseline is judged against.**
   CR-L03-08 removes 18 guaranteed-pass keyword assertions. CR-L03-01 demands the engine beat a null
   baseline. Both are right, and doing them in the wrong order produces an uninterpretable delta:
   the guard rate will move for *two* reasons at once and you cannot attribute it.
   **Resolution: delete the dead assertions first, re-baseline, then compare.** Never in one change.

2. **CR-L01-01 (gossip) vs R2 (eval baseline) — a genuine ordering trap.** Fixing gossip shifts eval
   golden strings and determinism fixtures. Fixing the eval instrument requires a stable corpus.
   Each wants to go first. **Resolution: R2 first.** A trustworthy instrument measuring old behaviour
   is recoverable — re-run it. Corrected behaviour measured by an instrument a fixed string beats
   tells you nothing, and you will not know the gossip fix worked.

3. **CR-L06-09 (drop conservation + label-survival) vs CR-L06-02 (fix Identity 2).** Incompatible:
   one deletes the gate, the other repairs it. **Resolution: CR-L06-09 wins.** Repairing Identity 2
   means inventing a real invariant for a gate that audits files that cannot change. Delete both,
   and if the invariant is wanted later it comes back as a probe under the new counterfactual rule.

4. **CR-L09-04 (cut CLAUDE.md) vs your Phase 0 instruction to gate more rules.** Cutting the file
   while adding gated rules pulls opposite ways on line count. **Resolution: they are compatible if
   the gated rules do not live in `CLAUDE.md`.** Rules become gates in `scripts/`; the *narrative*
   moves to skills; `CLAUDE.md` keeps only what an agent must know before its first tool call. Line
   count falls, enforcement rises. This is recorded as the chosen approach in `FIX_PLANS.md`.

### Integrate-or-delete — your Phase 0 instruction applied

You approved deletion only where there is no sensible value, and asked for integration otherwise.
Judged per item:

| Item | Lines | Verdict | Why |
|---|---:|---|---|
| `engines/deception/`, `engines/currency/` | 140 | **KEEP** (your call) | Held for integration. |
| `check_engine_coverage.py` + contract + test | 658 | **DELETE** | L9 resolved it against `check-base-rate`, which measures the CR-L03-01 breach directly. Two gates for one question. |
| `check_base_rate.py` | 386 | **INTEGRATE** | Wire it. It is the only thing that would have caught the null-responder defect. |
| `live_openapi.json` | 182 KB | **DELETE** | 64 days stale, zero code consumers. Regenerable in one command. |
| 7 dead `verify-*` targets | — | **DELETE** | Superseded by `make check`. |
| `add_faction_support.py` | — | **DELETE** | Dead since 2026-06-04; two docs must stop naming it. |
| Trend/regression stack | 1,309 | **INTEGRATE, then decide** | Has exactly 1 row. Worthless today, but trend comparison is precisely what a model swap needs. Blocked on CR-L15-01; revisit after one full generation. |
| Sequence subsystem | 1,714 | **KEEP, split** | 6 consumers incl. 2 in `e2e/scripts/`. Not isolated; reset-fidelity is wired. |
| Dead `keyword_none` blocks + 3 cases | — | **DELETE** | Guaranteed passes. Note: this **lowers** the published score, correctly. |
| Duplicate `_draw_no_data` | ~45 | **DELETE** | Straight duplication. |
| `soft_review.md` | 305 | **DELETE after re-filing** | One surviving HIGH must be re-filed first. |
| `EVAL_STRATEGY.md` | — | **DELETE** | Stale duplicate of `docs/EVAL_METHODOLOGY.md`. |

---

## What this triage did not do

Stated plainly so the next reader can calibrate trust:

- **~50 of 145 findings were re-verified by direct command execution at HEAD.** Those are the four
  CRITICALs, every finding whose verdict is not UPHELD, and every HIGH in the gate/eval/CI clusters.
- **The remainder are UPHELD on the review's own cited evidence**, spot-checked for internal
  consistency but not independently re-run. They are mostly LOW/MEDIUM documentation and
  waste findings whose evidence is a file path and a line count — cheap to state, cheap to check at
  fix time. Each carries a verification command in its `FIX_PLANS.md` Proof field, so a wrong one
  fails loudly when someone tries to fix it rather than silently entering the roadmap.
- **CI's actual pass/fail state on `main` remains unverified.** `gh` is not installed and there is no
  CODEOWNERS or ruleset file. My analysis of CR-L15-01 predicts *green, with null model digests* —
  but that is an inference, not a measurement. It is the one item still blocked on a human.
