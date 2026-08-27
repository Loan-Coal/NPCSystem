# CR-L11 — Process-to-output ratio

Lens L11. Branch `eval-ab-context-arms` @ `d46ae42`, 967 commits, 2026-04-15 → 2026-08-27, one
author. Read-only; the only file written is this one.

Dispatched after eleven lenses. Everything Confirmed by CR-L01/02/03/04/06/07/08/10/13/15/16 is
cited, not re-derived. Every number below that is *not* cited to another lens was computed this
session against this HEAD; the commands are pasted.

---

## Required measurements

### 0. Definitions (stated once, used throughout)

| Bucket | Contents | Why |
|---|---|---|
| **Shipped product** | `src/` + `demo_game/` + `seeds/` | what a game studio would license |
| **Product verification** | `tests/` minus `tests/unit/{evals,scripts,harness}` and `tests/integration/evals`, plus `e2e/` | tests of the engine |
| **Process & measurement machinery** | `project-harness/` + `docs/` + `.claude/` + the 44 gate/loop files in `scripts/` + `evals/` + `tests/unit/{evals,scripts,harness}` + `tests/integration/evals` | nothing here ships; all of it exists to observe or govern the work |

`evals/` is counted as machinery, not product, on the evidence of CR-L03: it is an instrument, it
is shipped to nobody, and CR-L03-04 shows 1,522 lines of its newest gate layer are reachable from
no `make` target and no CI job. Historic paths are folded into their successors
(`npc_engine/` → `src/`; `project/`, `project_md_files/`, `refactor/` → `project-harness/`;
`dashboard/`, `reports/` → `evals/`).

Line counts below are tracked-file newline counts, split by extension so they reconcile exactly
with the orchestrator's figures (`src` 68,599 `.py` / 70,656 all-files; `project-harness` 48,988
`.md` / 53,228 all-files — the delta is `.ps1`/`.txt`).

### 1. Harness vs. product — the ratio, four ways

**(a) Static LOC, today.**

```
Process & measurement machinery
  project-harness/            53,228   (48,988 .md + 4,240 .ps1/other)
  docs/                        5,507
  .claude/                       603
  scripts/ gate+loop (44 files) 8,363
  evals/                      20,638   (20,141 .py + 497 .md)
  tests of the above          18,984   (tests/unit/{evals,scripts,harness} + tests/integration/evals)
                             -------
                             107,323

Shipped product
  src/                        68,599
  demo_game/                  36,961
  seeds/                       1,125
                             -------
                             106,685
```

> **107,323 : 106,685 — ratio 1.01 : 1.**
> The process and measurement machinery is now *larger than the entire shipped product*.

Narrower cut, for anyone who rejects counting `evals/`: harness prose + gate scripts alone
(67,701 lines) is 96% the size of the whole `src/` engine, and `project-harness/`'s markdown
(48,988) is bigger than all of `demo_game/` (36,961).

**(b) LOC written, full history** — `git log --numstat`, lines *added*, effort-weighted (code 1.0,
markdown prose 0.35, on the reasoning that prose is cheaper per line to author than code):

| | added | weighted |
|---|---|---|
| evals/ | 81,812 | 81,812 |
| gate/loop scripts | 9,282 | 9,282 |
| harness-facing tests | 19,781 | 19,781 |
| harness prose (`project-harness`+`docs`+`.claude`) | 86,709 | 30,348 |
| **process total** | | **141,223** |
| src+demo_game+seeds | 196,900 | 196,900 |
| engine-facing tests | 79,649 | 79,649 |
| e2e + misc | 27,537 | 27,537 |
| **product total** | | **304,086** |

> **Process share of lifetime authorship: 31.7%.** At prose weight 1.0 it is 39.4%. The
> conclusion is insensitive to the weight: **roughly a third of everything ever written here was
> process machinery.**

**(c) LOC written, last 200 commits** — same method:

```
process : 68,482 (evals) + 5,939 (gate scripts) + 16,625 (harness tests) + 8,727 (prose ×0.35)  =  99,773
product : 11,452 (src+demo+seeds) + 10,628 (engine tests) + 1,831 (e2e+misc)                    =  23,911
```

> **Process share of recent authorship: 80.7%** (82.9% at prose weight 1.0).
> Raw, unweighted, machinery-added vs product-added: **99,355 : 11,452 = 8.68 : 1.**

**(d) Churn, file-touches** — `git log --name-only`, bucketed:

| Window | harness prose+gate scripts | + `evals/` | product | narrow ratio | wide ratio |
|---|---|---|---|---|---|
| full 967 commits | 1,850 | 2,433 | 4,448 | 0.42 : 1 | 0.55 : 1 |
| last 200 commits | 361 | 753 | 181 | **1.99 : 1** | **4.16 : 1** |

**Commit participation** (a commit counts once):

```
FULL 967       touch product= 504 (52%)   NO product file at all= 440 (46%)
LAST 200       touch product=  42 (21%)   NO product file at all= 158 (79%)
SINCE 2026-08-01 (233)  touch product= 44 (19%)   NO product file at all= 189 (81%)
```

**Plain answer to the question the brief asks.** Yes. The harness is the main product. Four
independent measures agree: it is larger in absolute lines (1.01:1), it absorbed 8.7× more written
lines than the engine over the last 200 commits, it is touched twice as often per commit, and
**81% of every commit since 2026-08-01 does not modify a single line of shipped product.** The
NPC engine is now a fixture that the measurement apparatus is built around.

### 2. Harness machinery that has produced no downstream decision — **the centrepiece**

Method: for each script, (i) read its module docstring for its declared output and consumer,
(ii) `grep` `Makefile`, `.github/workflows/`, `.claude/`, `scripts/`, `project-harness/`,
(iii) `git log --grep` for every commit naming it, then **exclude commits that modify the script
itself** (those are authorship, not use), then read the surviving commits to see whether the
script's *output* is given as the reason for the change. Gate names appearing in commit bodies as
`"lint, type, check-rules, check-test-quality all green"` attestations were counted as **not** a
decision — that is a signature, not a finding.

| Script | LOC | Emits | Who reads it | A decision it caused |
|---|---|---|---|---|
| `expand_loop.sh` | 681 | `.loop-logs/`, `human_verification.md` | the operator | 140 commits in its life; **3 touched `src/`** (§5) |
| `loop_gates.py` | 135 | HALT/AUTOFIX specs | `classify_gate_failure` | **none found** — all 12 classifications were harness self-tests (§5) |
| `classify_gate_failure.py` | 73 | `CLASSIFICATION=…` lines | `expand_loop.sh` | **none found (product)** |
| `gate_baseline.py` | 169 | `.loop-state/gate_baseline.json` (1 file, 260 B, mtime 2026-08-15) | 3 sibling scripts | loop-internal only |
| `gate_attribution.py` | 74 | exit code | `expand_loop.sh` | loop-internal only — 11 "committed with a pre-existing red gate" entries |
| `gate_confirm.py` | 74 | exit code | `expand_loop.sh` | **none found** — its 2 confirmed regressions were *"Committed anyway as visible debt"* (`human_verification.md:262,270`) |
| `scan_fix_diff.py` | 120 | gate-gaming verdict | `expand_loop.sh` | **none found** — 0 mentions in 967 commit messages, 0 in DECISIONS/ISSUES, no output artifact on disk |
| `loop_clock.py` / `loop_compat.sh` / `loop.config.sh` | 396 | stop deadline, portability shims | `expand_loop.sh` | loop-internal only |
| `roadmap_cursor.py` + `_roadmap_cursor_core.py` | 498 | roadmap slice / tick | loop + `/expand-linear-next` | harness-internal only; its own tripwire test caused **8 of 12** loop HALTs |
| `check_human_gates.py` | 293 | `HUMAN GATES OK (0 gates)` | `make check` | **none found** — CR-L06-01 proved it green with the feature deleted |
| `check_test_quality.py` | 265 | findings list | `make check` | **none found** — `main()` can only `return 0` (CR-L06-03) |
| `check_conservation.py` | 327 | 4 identities | `make check` | **none found** — the one commit citing it (`9c907a9b`) fixed *the checker's own bugs*: *"Root cause was in the checker script, not evals/compare.py"* |
| `check_label_survival.py` | 83 | survival count | `make check` | **none found** — prints "528 unlabelled rows" and exits 0 (CR-L06 §2) |
| `check_harness_honesty.py` | 125 | H1/H2/H3 | `make check` | **none found** — H3 reads an archived file (CR-L13-06); no `--strict` is ever passed |
| `check_base_rate.py` + `base_rate_contract.py` | 386 | base-rate band verdict | *nothing* | **never run** — no `make` target (CR-L03-04) |
| `check_engine_coverage.py` + `engine_coverage_contract.py` | 424 | coverage-taxonomy verdict | *nothing* | **never run** — no `make` target (CR-L03-04) |
| `record_trend_and_gate.py` | 168 | trend row + regression verdict | `Run-EvalHarness.ps1` | **none found** — `trend_v1.jsonl` has 1 row and it is already incomparable (CR-L03-05) |
| `mutation_probe.py` | 211 | surviving-mutant list | `make check-mutations` (not in `make check`) | **none found** |
| `hedge_responder_probe.py` | 297 | null-responder pass rate | `make hedge-probe` | **measured, nothing changed** — it produced the number CR-L03-01's CRITICAL rests on, and no commit in 967 acted on it |
| `seed_reproduction_probe.py` | 271 | A/B seed reproduction | `make seed-probe` | **none found** |
| `oracle_labeller` `oracle_adjudicate` `oracle_matrix` `mock_labeller` `mock_adjudicate` `build_label_order` `migrate_panel_judged` | 1,248 | labelling scaffolding | eval verbs | **none found** — a third of the corpus has never been scored (CR-L03-09) |
| `check_dead_keywords.py` | 177 | dead-keyword work-list | `make check-dead-keywords` | **YES** — `8cc68f3b` "resolve case-set contradictions — EVAL-P20.1", 5 code files |
| `check_layers.py` | 192 | violation list | `make check`, CI | **YES, once** — `a397661` "relation_phase_writer no longer imports engines"; plus 3 at introduction (`d24f442`) |
| `check_rules.py` + baselines | 460 | ratcheted violations | `make check`, CI, pre-commit | **YES, form only** — `1feef1a` R002 print removal; ratchet runs backwards on `evals/` (CR-L06-04) |
| `docstring_audit.py` | 83 | missing-docstring list | `make check` | **YES, form only** — and content-blind: `"""Layer: banana"""` passes (CR-L06 §4) |
| `mypy_ratchet.py` + `mypy_evals_ratchet.py` | 166 | baseline compare | `make check` | **YES, form only** — 256→0 burn-down |
| `probe_context_ceiling.py` | 263 | measured per-NPC context cost | `make probe-ceiling` | **YES — the only product-behaviour catch by any harness script.** `4078c37` → `5a35a33` (3 defects) → `96d83eb` `fix(config)`: budget 1,062 tokens against three NPCs needing 995–1,151 |
| `probe_inner_life.py` | 231 | 8-NPC observability | `make probe-inner-life` | partial — ISSUE-216 logged; no product fix traced |

> **24 scripts, 4,500 lines — 54% of the 8,363-line gate/loop machinery — have no downstream
> decision traceable to their output in 967 commits.**
> Five more (`check_rules`, `check_layers`, `docstring_audit`, the two mypy ratchets) have catches,
> all of them *form*: an import direction, a `print()`, a missing docstring, a type annotation.
> **Exactly one script in the whole apparatus has ever caused a change to runtime behaviour**, and
> it is `probe_context_ceiling.py`, written 15 days ago and not wired into any gate.

### 3. Cost accounting

Assumptions, stated so they can be argued with:

1. Author-effort ∝ lines added, code weighted 1.0 and markdown prose 0.35 (§1b). Sensitivity is
   reported at weight 1.0 too; the conclusion does not turn on it.
2. Gate *execution* time is negligible and I say so against the brief's framing. CR-L15-04 is
   right: the per-commit gate is the pre-commit hook at ~4.9 s, not `make check` at 595 s.
   967 × 4.9 s = **1.3 h** of hook time lifetime; `make check` run once per roadmap phase
   (~40 phases) = **6.6 h**. The 595 s number is real but it is not where the money went.
   **The cost of this process is authorship and reading, not execution.**
3. Session context tax, from CR-L04: 9,149 tokens auto-loaded before any work; 44,495 if
   CLAUDE.md:268's *"Every session reads it"* mandate for the 1,799-line `ISSUES.md` is honoured.
   Against a 200K window that is 4.6% / 22.3% of the budget spent before the first file is opened.
   Over the 61 real loop sessions + an estimated ~260 interactive sessions (65 active days × 4)
   ≈ 321 sessions: **2.9 M tokens** of mandatory context at the literal-compliance floor, **14.3 M**
   if the ISSUES mandate is honoured.
4. Per-task human tax, from CR-L04's walked measurement: a one-paragraph docstring fix takes
   1.1 h in realistic practice and 3.4 h under literal CLAUDE.md compliance, of which **72% is
   reading two markdown files**. Step 8 — the only step that touches the product — is 5 minutes.

| Measure | Lifetime | Last 200 commits |
|---|---|---|
| Weighted lines authored on process machinery | **31.7%** (39.4% @ prose 1.0) | **80.7%** (82.9%) |
| Commits touching no product file | 46% | 79% (81% since 2026-08-01) |
| Test suite devoted to the machinery, not the engine | 23.6% of `tests/` (18,984 / 80,324) | 61% of test lines added |
| Logged issues about machinery vs product | 109 machinery (49%) vs 80 product (36%) of 221 parsed issues | — |
| Marginal per-task process tax (CR-L04) | 66–72% of task wall-clock | — |

> **Estimate: ~32–39% of total project effort has gone into process and measurement machinery
> rather than the shipped engine, and ~81% of effort since 2026-08-01 has.** Three independent
> proxies (weighted lines, commit participation, issue subject matter) land in the same place.

### 4. Did the process catch anything?

**4a. The three CRITICALs — which mechanism should have caught each, and why it didn't.**

| CRITICAL | Nominal owner | Why it was blind |
|---|---|---|
| **Gossip distortion chain is a no-op** (CR-L01-01) — `gossip_batch_queries.py:29-47` relays `best_event.summary`, never `k.distorted_summary` | `test-cov` (80% floor, 4,048 tests) and the 30 eval cases mentioning gossip/rumour | Coverage measures *execution*, not *assertion*: the query line runs on every tick and the wrong column is never asserted. CR-L01's own fix sketch says the two-hop test must be *added* — it does not exist. `check-test-quality`, the gate whose entire job is vacuous-assertion detection, **cannot fail** (`check_test_quality.py:261`). And the eval battery cannot discriminate: CR-L03-01 shows a canned hedge scores 0.949 on it. The demo looks correct only because the chain is hand-seeded at `demo_game/seeds/seed.py:957-980`. |
| **A null responder beats the engine** (CR-L03-01) — hedge 0.949 vs engine 0.897 | `hedge_responder_probe.py` — the *exact right instrument*, in-repo since 2026-08 | `hedge_responder_probe.py:71-76` raises `NotACapabilityCaseError` on any guard case, so the null baseline was never once computed for the 78-case battery that produces the published headline. The instrument exists, is correct, and was pointed away from the number it would have falsified. `check_base_rate.py` (216 lines), which would flag a 0.949 base rate, **has no `make` target** (CR-L03-04). |
| **Documented Neo4j→503 fallback does not exist** (CR-L02-01) — `GraphUnavailableError` has zero raise sites | `check-docstrings` + CLAUDE.md's "Document the fallback in the function docstring" (strict) | **The process manufactured this defect.** The rule requires the docstring; the gate verifies a docstring is *present* and is content-blind — `"""Layer: banana\nPurpose: """` passes with 0 findings (CR-L06 §4). Four files therefore carry a compliant docstring asserting a contract no code implements. Writing the sentence is what the process rewards; implementing it is not checked by anything. |

The pattern is one thing three times: **the harness checks the artifact of compliance, not the
behaviour the artifact claims.** All three CRITICALs were found in this review by direct
inspection in hours, against a repo that had already run 14 gates on every phase for three months.

**4b. Genuine catches in 967 commits.**

A genuine catch = a gate or probe went red/produced a number, and that caused a fix to code that
was not the gate itself or its baseline. Enumerated from CR-L06's per-gate history plus my own
`git log --grep` pass over every gate name:

| # | Commit | Mechanism | What it caught | Class |
|---|---|---|---|---|
| 1 | `d24f442` 2026-06-04 | `check_layers` at introduction | 3 upward imports | architecture |
| 2 | `a397661` | `check_layers`, ongoing | `relation_phase_writer` importing `engines` | architecture |
| 3 | `1feef1a` | `check_rules` R002 | `print()` calls | form |
| 4 | `1fcc3fe` | `check_docstrings` | docstring format | form |
| 5 | `9ee2e73` | mypy ratchet | 256 → 0 annotations | form |
| 6 | `94844ce` | `lint`, widening to `evals/` | *"exactly ONE violation: E402"* | form |
| 7 | `8cc68f3b` | `check_dead_keywords` | guaranteed-pass keywords in the case set | eval corpus |
| 8 | `4661c3c` | `make eval-arm-probe` gate 4 | two A/B arms declared above their supply | eval config |
| 9 | `96d83eb` | `probe_context_ceiling` | shipped token budget (1,062) below three NPCs' real context (995–1,151) | **product behaviour** |

> **Nine catches in 967 commits. Exactly one (`96d83eb`) is a defect in shipped runtime behaviour,
> and it was found by a probe written 15 days ago that no gate runs.** Two are architectural. Four
> are formatting. Two are inside the eval instrument.

The counter-evidence is equally clean. `96d83eb`'s own commit body explains why the standing gate
could not have found it:

> *"`PROMPT_TOKEN_BUDGET` is DERIVED as `window - PROMPT_WINDOW_OVERHEAD_TOKENS`, so
> `TestShippedDefaultsAreCoherent` — which asserts the reserves sum to no more than the window — is
> satisfied by construction at EVERY window size."*

A test that passes by construction. That is the same failure mode as `check_conservation`'s
Identity 2 (`x == x`, CR-L06-02), `check_test_quality`'s unconditional `return 0`, and
`check-human-gates`' `OK (0 gates)`. And `9c907a9b` — the single commit citing `check_conservation`
as a cause — reads *"Root cause was in the checker script, not evals/compare.py"*: the gate's one
appearance in the fix record is as the bug.

### 5. The overnight loop specifically

**First, a correction to the brief.** The loop cannot explain W24. `git log --diff-filter=A` puts
`OVERNIGHT_LOOP.md`, `OVERNIGHT_LOOP_PLAN.md`, `loop_gates.py`, `classify_gate_failure.py`,
`expand_loop.sh`, `roadmap_cursor.py` and `.claude/commands/expand-linear-next.md` all at
`8810284`, **2026-08-01**. The 261-commit W24 (2026-06-09 → 06-14) and the 107-commit day
(2026-06-12) predate the loop by seven weeks; they were interactive sessions, and CR-L10 §3 already
establishes their shape.

**The loop's actual operational life**, from `project-harness/.loop-logs/` (444 files, gitignored,
present on disk) and `human_verification.md`:

```
active nights: 2026-08-02 … 2026-08-15   (last log 2026-08-15 10:00; one stray 2026-08-27)
wall-clock span across those nights: 76.5 h
task session logs: 375  →  314 are DRY-RUN stubs, 61 are real sessions
real-session outcomes:  25 TASK_COMPLETE · 18 PHASE_COMPLETE
                        11 TASK_COMPLETE_BASELINE_RED · 2 TASK_COMMITTED_REGRESSION
```

The 314 dry-run stubs are one night: 2026-08-02, 302 identical files for the same task
`EVAL-P0.2` across 11.45 hours. That is **ISSUE-126** — *"`expand_loop.sh --dry-run` never
terminates"* — and it is still open at `ISSUES.md:709`, 26 days later.

**What the loop produced**, `git log --name-only --since=2026-08-02 --until=2026-08-16`:

```
commits in window: 140
file-touches:  evals 275 · project-harness 208 · tests 150 · gate scripts 26 · src 24 · docs 13 · e2e 3
commits touching src/ or demo_game/ or seeds/:  3 / 140  (2%)
  5bfa528  feat(llm): optional generation seed + prompt determinism fix — EVAL-P20.0
  9cb09c9  feat(retrieval): context budget starvation fix + drop instrumentation — RET-P0
  0af873c  feat(evals): single-source prompt version via llm_config.yaml (EVAL-P1.2)
commits that are `chore(loop): checkpoint night-shift reports`:  29 / 140  (21%)
```

> **76.5 hours of unattended sessions across 10 nights produced 140 commits, of which 3 touched
> the shipped engine and 29 were the loop committing its own logs.** Zero touched `demo_game/`.
> The loop worked exactly as designed. It was pointed at a roadmap that was 100% eval-harness
> construction, so it built eval harness — competently, and for ten nights straight.

**Every HALT was self-inflicted.** All 12 `CLASSIFICATION=HALT` entries in
`human_verification.md`, with the failing test named:

| Failing test | HALTs |
|---|---|
| `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire` | 8 |
| `tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case` | 4 |
| `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue` | 2 |
| `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_parses_and_verifies_clean` | 2 |
| `tests/unit/scripts/test_check_human_gates.py::test_the_loop_is_never_handed_a_task_behind_a_closed_gate` | 1 |
| (1 further entry: `UNATTRIBUTED`, coverage) | 1 |

**Not one HALT names a test in `src/` or `demo_game/`.** Every night the loop stopped, it stopped
because the roadmap parser could not parse the roadmap, or the eval-coverage self-test tripped, or
the human-gate checker's own test failed. `86254cb` — *"re-snapshot roadmap fence tripwire… asserted
a pending-task-id snapshot that went stale"* — is a re-baseline, not a catch.

`soft_review.md` (305 lines, 13 phase reviews, ~60 findings, `REVIEW_MODEL=haiku`) is the loop's
other output. Its findings were read by nobody: `grep -rn "soft_review"` across
`project-harness/`, `docs/`, `.claude/` returns only `OVERNIGHT_LOOP.md:63` describing it and this
review's own churn tables. Zero ISSUE entries, zero DEC entries cite it. Its final finding —
*"`from evals.scorer_trust_policy import check_publication` … will fail at runtime"* — is still
live today as CR-L03-02 (HIGH).

### 6. Compounding vs. one-shot

Method: for every `.md` under `project-harness/`, count commits touching it
(`git log --format=%H -- <file>`), and count occurrences of its basename anywhere in the tracked
tree minus self-references.

```
project-harness .md files: 246   loc = 48,988
written in exactly ONE commit and never touched again:   234 files   30,403 loc  (62% of all lines)
basename referenced nowhere else in the repo:            140 files    9,939 loc
BOTH write-once AND unreferenced:                        140 files    9,939 loc  (138 in archive/)
```

The archive specifically:

```
project-harness/archive/: 215 .md files, 29,167 loc  (60% of all harness markdown)
never named outside archive/ or the review dir: 175 files, 16,724 loc  (81%)
```

And outside the archive, a family of one-shot session artifacts committed as permanent project
records — `PROMPT_P26_INTEGRATION.md` (290), `PROMPT_P25_TRACK_B_CASES.md` (185),
`PROMPT_P25_TRACK_A_TOOLING.md` (168), `PROMPT_P23_UNBLOCK.md` (162), `PROMPT_P25_GOLDEN_SET.md`
(125), `HANDOFF_TRACK_A.md` (412), `HANDOFF_TRACK_B.md` (327), `EVAL_P25_TO_P31_PLAN.md` (510),
`EVAL_P20_TO_P24_UNBLOCK_PLAN.md` (367), `OVERNIGHT_LOOP_PLAN.md` (384),
`eval_roadmap_session_prompt.md` (199), `SEED_REPRODUCTION_AND_ISSUE_165_BRIEF.md` (213),
`MORNING_HANDOFF_COMBINED.md` (82), `MORNING_HANDOFF_PHASE1.md` (39):

```
non-archive harness .md written in exactly ONE commit: 17 files / 3,627 lines
  of which the prompt/handoff/plan family:             14 files / 3,463 lines
```

**Genuinely compounding** — read on every session or by many others: `CLAUDE.md` (476 lines, 12
commits), `ROADMAP.md` (4,188 / 220), `ISSUES.md` (1,799 / 148), `DECISIONS.md` (6,891 / 138),
`PATTERNS.md` (139 / 4). That is **5 files, 13,493 lines** carrying the compounding value — 28% of
harness markdown — and even they have known rot: 53% of the 219 DECs are never cited outside
`project-harness/` (CR-L07-06), and the roadmap backlog is diverging (CR-L07-05).

> **~72% of harness markdown (35,495 of 48,988 lines) is write-once. 20,187 lines of it
> (16,724 archived + 3,463 session prompts) are also read-never.**

---

## Findings

### [CR-L11-01] The process machinery is now larger than the product, and outgrew it 8.7:1 over the last 200 commits

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** §1. Static: process machinery 107,323 lines vs shipped product 106,685 — **1.01:1**. Lines added, last 200 commits (`git log --numstat`, bucketed): machinery 99,355 vs product 11,452 — **8.68:1**. Commit participation: `NO product file at all = 158/200 (79%)` and `189/233 (81%)` since 2026-08-01. Weighted authorship share: 31.7% lifetime, 80.7% recent. Corroborated independently by issue subject matter — of 221 issues parsed from `ISSUES.md` + `archive/ISSUES_RESOLVED.md`, 109 (49%) are about the measurement/process machinery vs 80 (36%) about `src/` + `demo_game/`.
- **Cost of inaction:** The engine is not being developed. `demo_game/` received **8 file-touches in the last 200 commits** and 0 in the loop's entire life; CR-L10 shows `src/` churn collapsing from 1,563 (last 500) to 172 (last 200). The apparatus is self-sustaining: 71% of unchecked roadmap items are eval-harness meta-work, so the next 200 commits will look like the last. There is no date at which this self-corrects — it is already 26 weeks in.
- **Fix sketch:** Declare a hard budget in `ROADMAP.md`: no new harness or eval-instrument phase may be queued while the ratio of product-touching to non-product-touching commits over the trailing 50 commits is below 1:1. Delete the 71% of unchecked roadmap items that are meta-work rather than deferring them.
- **Effort:** M (the decision), L (the backlog cull)
- **Removes:** ~0 directly; unblocks the deletions in CR-L11-07/08
- **Blast radius:** `ROADMAP.md`, the eval program EVAL-P25..P31 (`d46ae42`, queued yesterday).

### [CR-L11-02] 24 gate/loop scripts — 4,500 lines, 54% of the machinery — have produced no downstream decision in 967 commits

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** §2, full table. Method: `git log --grep=<script>` for every script, minus commits that modify the script itself, then read the survivors. Gate names in commit bodies as `"check-rules, check-test-quality all green"` attestations are signatures, not decisions. Zero-mention scripts: `gate_baseline`, `gate_confirm`, `gate_attribution`, `classify_gate_failure`, `loop_gates`, `scan_fix_diff`, `expand_loop` — **0 mentions across 967 commit messages each**. `scan_fix_diff.py` (120 lines) additionally has no output artifact anywhere on disk. `check_base_rate.py`+`base_rate_contract.py` (386) and `check_engine_coverage.py`+`engine_coverage_contract.py` (424) have **no `make` target at all** (`grep -n check_base_rate Makefile` → no match; CR-L03-04). The only commit citing `check_conservation` as a cause (`9c907a9b`) reads *"Root cause was in the checker script, not evals/compare.py"*.
- **Cost of inaction:** 4,500 lines under the 300-line-file rule, the docstring rule and the layer rule, each needing maintenance every time the gate shape changes — `scripts/` is itself invisible to those gates (CR-L08-04), so the machinery is exempt from the rules it enforces. The 8,363-line gate layer is already the fastest-growing part of `scripts/` (+5,939 lines in 200 commits against 151 file-touches lifetime).
- **Fix sketch:** Delete `scan_fix_diff.py`, `mutation_probe.py`, `seed_reproduction_probe.py` and the 7-file mock/oracle labelling scaffolding outright. For `check_base_rate` and `check_engine_coverage`, wire the `make` target this week or delete them — a gate with no invocation is a 424-line comment.
- **Effort:** M
- **Removes:** ~1,950 lines / 11 files immediately (`scan_fix_diff` 120, `mutation_probe` 211, `seed_reproduction_probe` 271, mock/oracle scaffolding 1,248, plus 2 test files); a further 810 if the two never-run gates are deleted rather than wired
- **Blast radius:** `Makefile` targets `check-mutations`, `seed-probe`, `mock-calibrate*`; `tests/unit/scripts/`; CR-L03-04 proposes wiring rather than deleting the two never-run gates — that conflict needs one decision, not two.

### [CR-L11-03] Every overnight-loop HALT was the harness tripping over its own self-tests; not one was a product defect

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** §5. `grep -n "^FAILING " project-harness/human_verification.md` returns 5 distinct test node-ids across 12 HALT entries: `test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire` (8), `test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case` (4), `test_roadmap_cursor.py::test_real_roadmap_end_marker_is_not_repeated_inside_the_queue` (2), `test_roadmap_cursor.py::test_real_roadmap_parses_and_verifies_clean` (2), `test_check_human_gates.py::test_the_loop_is_never_handed_a_task_behind_a_closed_gate` (1). All five test the harness. **No node-id under `tests/unit/{engines,graph,retrieval,api}` appears anywhere in the file.** The whole HALT/AUTOFIX apparatus — `loop_gates.py` (135) + `classify_gate_failure.py` (73) + `gate_baseline.py` (169) + `gate_attribution.py` (74) + `gate_confirm.py` (74) = 525 lines — has therefore never once made a judgement about product code. Its two `TASK_COMMITTED_REGRESSION` verdicts were both overridden: *"Committed anyway as visible debt (scar 6.5)"* (`human_verification.md:262,270`).
- **Cost of inaction:** The loop's safety machinery is calibrated against a signal it has never seen. The first time a loop session does break `src/`, the classifier will be running its first real trial in production, at 3 a.m., unattended — and the recorded precedent (2 of 2 confirmed regressions committed anyway) says it will commit it.
- **Fix sketch:** Either delete the tolerance layer (525 lines) and let any red gate halt the night — the simpler contract, and the one the evidence supports — or, if the loop is repointed at engine work, keep it and first prove it by injecting a deliberate `src/` regression and checking that `gate_confirm` charges it. Do not keep it unproven.
- **Effort:** S (delete) / M (prove)
- **Removes:** ~525 lines / 5 files + `tests/unit/harness/test_loop_gates.py` (144)
- **Blast radius:** `scripts/expand_loop.sh` (4 call sites), `.claude/commands/fix-make-failure.md`, `OVERNIGHT_LOOP.md`.

### [CR-L11-04] `soft_review.md`'s ~60 loop-generated findings are read by nothing, and one of them is still an open HIGH in this review

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `project-harness/soft_review.md`, 305 lines, 13 phase reviews at `REVIEW_MODEL=claude-haiku-4-5` (`scripts/loop.config.sh:REVIEW_MODEL`), each producing ~5 findings. `grep -rn "soft_review" --include=*.md project-harness/ docs/ .claude/` returns **only** `OVERNIGHT_LOOP.md:63` (which describes the file) and this review's own churn tables. Zero citations in `ISSUES.md`, `DECISIONS.md`, or any commit message. The file's last finding — *"`from evals.scorer_trust_policy import check_publication` … Will fail at runtime with `ModuleNotFoundError`"* — describes the same module CR-L03-02 reports today as HIGH: *"`check_publication` ignores the interval it is handed, and the report generator never calls it."* The loop found it, wrote it down, committed it, and nobody read the file.
- **Cost of inaction:** Every future loop night spends a 600 s haiku session per phase (`REVIEW_SESSION_TIMEOUT=600`) generating findings into a file with no reader, and appends them to a tracked artifact that grows monotonically. Worse, its existence creates the appearance of a review step that is not happening.
- **Fix sketch:** Set `SOFT_REVIEW_ENABLED=0` and delete `soft_review.md`. If per-phase review is wanted, the only version worth keeping is one that writes findings into `ISSUES.md` in the logged-issue format the project already reads — replacing the soft-review lane, not adding to it.
- **Effort:** S
- **Removes:** 305 lines / 1 file, plus the `SOFT_REVIEW_*` config and call path in `expand_loop.sh`
- **Blast radius:** `scripts/loop.config.sh`, `scripts/expand_loop.sh`, `OVERNIGHT_LOOP.md:63`.

### [CR-L11-05] In 967 commits the gate battery has one behaviour catch, and it was made by a probe no gate runs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** §4b, 9 catches enumerated with SHAs. Two architectural (`d24f442`, `a397661`, both `check_layers`), four form (`1feef1a` print, `1fcc3fe` docstring format, `9ee2e73` mypy, `94844ce` one E402), two inside the eval instrument (`8cc68f3b`, `4661c3c`), and one product-behaviour defect: `96d83eb` `fix(config): the shipped window derives a budget smaller than the context it assembles`, found by `scripts/probe_context_ceiling.py` — which is invoked only by `make probe-ceiling` and is in neither `make check` nor CI. That commit's own body states why the standing test could not find it: *"`TestShippedDefaultsAreCoherent` … is satisfied by construction at EVERY window size."* Structurally identical to `check_conservation` Identity 2 = `x == x` (CR-L06-02), `check_test_quality`'s unconditional `return 0` (CR-L06-03), and `check-human-gates` → `OK (0 gates)` (CR-L06-01). CR-L06 §4 independently establishes **6 of 14 gates fail a counterfactual and 5 of 14 can print a problem and exit 0**.
- **Cost of inaction:** `make check` is 595 s of green that certifies formatting. Everyone downstream — the loop's `GATE_CHECK_CMD`, the pre-merge checklist in `CLAUDE.md`, every commit body's "all green" attestation — treats it as evidence of correctness. It has never been that. The three CRITICALs in this review all passed it.
- **Fix sketch:** Stop growing the gate battery and start growing the probe set: probes measure the engine against reality and have a 1-for-1 catch record; gates check file shape and have a 0-for-967 behaviour record. Concretely — move `probe-ceiling`, `probe-inner-life` and `hedge-probe` into a `make measure` target run once per phase, and delete the five gates CR-L06 shows cannot fail from `make check`.
- **Effort:** M
- **Removes:** ~1,093 lines from `make check`'s surface (see CR-L06-01/03/07/09), 0 net new
- **Blast radius:** `Makefile:200`, `HARNESS_GATES.md`, `scripts/loop_gates.py`'s `AUTOFIX_CHECK_SPECS`, every commit-body attestation template.

### [CR-L11-06] The docstring rule plus a content-blind gate manufactured one of this review's CRITICALs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `project-harness/CLAUDE.md` "Engine boundary fallback contracts **(strict)**: … Document the fallback in the function docstring." Four files then document *"Fallback: Neo4j unavailable → raises `GraphUnavailableError`"* — `engines/military/military_battle_service.py`, `engines/military/military_resource_service.py`, `engines/ports/dialogue_graph_port.py`, `graph/political/pledge_violation_service.py` — while `grep -rn "raise GraphUnavailableError" src/npc_engine` returns zero raise sites (CR-L02-01, Confirmed). `check-docstrings` verifies only that the substring `Layer:` is present: CR-L06 §4 executed `docstring_audit.audit` against `"""Layer: banana\nPurpose: """` and got **0 findings**. The rule creates the obligation to assert the contract; the gate confirms the assertion exists; nothing anywhere checks the contract. This is the same shape as CR-L08-03 (two error classes documenting an unimplemented fallback) and CR-L01-08 (`EngineFallbackPolicy` declared by five engines and read by nothing).
- **Cost of inaction:** Documentation that is enforced-for-presence and unenforced-for-truth is worse than none: a reader, an eval author, and a future licensee all take the docstring as a specification. A live Neo4j outage returns a flat 500 with no retryable signal, and the four docstrings will still say otherwise.
- **Fix sketch:** Delete the "document the fallback in the docstring" clause from `CLAUDE.md`, or make it verifiable — a gate that asserts every docstring naming `raises X` has a matching `raise X` in the module's call graph. Prefer deleting the clause: a rule whose only observable effect is a false claim should not survive.
- **Effort:** S (delete the clause) / M (make it checkable)
- **Removes:** 1 CLAUDE.md rule + 4 false docstring claims
- **Blast radius:** `project-harness/CLAUDE.md`, the four docstrings, and CR-L02-01's fix (which should be sequenced first or together).

### [CR-L11-07] 175 archived files / 16,724 lines are named nowhere outside the archive

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** §6. `git ls-files project-harness/archive` → 215 tracked `.md`, 29,167 lines — **60% of all harness markdown**. Cross-referencing every basename against `git grep -o -E '[A-Za-z0-9_.-]+\.md'` over the tree excluding `project-harness/archive/` and `project-harness/review-2026-08/`: **175 files (16,724 lines, 81%) are never named**. 138 of them (9,450 lines) were also written in exactly one commit and never modified. Inbound links to `archive/` from live harness docs total 23 references from 6 files (`ROADMAP.md` 12, `DECISIONS.md` 5, `CLAUDE.md` 2, `ISSUES.md` 2, `HANDOFF_TRACK_B.md` 1, `PROMPT_P26_INTEGRATION.md` 1) — those 23 references are the entire live surface of a 29,167-line directory.
- **Cost of inaction:** Every `git grep` across `project-harness/` returns hits from 29,167 lines of superseded prose, which is exactly the search an agent runs at session start. It is also 60% of the markdown that makes `project-harness/` look like the largest thing in the repo — the archive is inflating the very number CR-L11-01 reports.
- **Fix sketch:** Delete the 175 unreferenced archive files in one commit. Git retains them; that is what git is for. Keep the 40 that something still links to. `ISSUES_RESOLVED.md` stays — DEC-130 requires it and `ISSUES.md` links it.
- **Effort:** S
- **Removes:** **16,724 lines / 175 files**
- **Blast radius:** None found — by construction nothing names them. Verify once more at deletion time against `project-harness/review-2026-08/` (excluded from my scan because this review cites archived files by name).

### [CR-L11-08] Fourteen single-use session prompts and handoffs are committed as permanent project records

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** §6. `PROMPT_P26_INTEGRATION.md` (290 lines, 1 commit), `PROMPT_P25_TRACK_B_CASES.md` (185/1), `PROMPT_P25_TRACK_A_TOOLING.md` (168/1), `PROMPT_P25_GOLDEN_SET.md` (125/1), `PROMPT_P23_UNBLOCK.md` (162/1), `HANDOFF_TRACK_A.md` (412/1), `HANDOFF_TRACK_B.md` (327/2), `EVAL_P25_TO_P31_PLAN.md` (510/1), `EVAL_P20_TO_P24_UNBLOCK_PLAN.md` (367/1), `OVERNIGHT_LOOP_PLAN.md` (384/1), `eval_roadmap_session_prompt.md` (199/1), `SEED_REPRODUCTION_AND_ISSUE_165_BRIEF.md` (213/1), `MORNING_HANDOFF_COMBINED.md` (82/1), `MORNING_HANDOFF_PHASE1.md` (39/1) — **14 files, 3,463 lines, each written in exactly one commit and never touched again.** `PROMPT_P26_INTEGRATION.md` and `eval_roadmap_session_prompt.md` are additionally referenced by nothing at all. An untracked fifteenth, `PROMPT_CODEBASE_REVIEW_2026-08.md`, is the only one currently outside git — and it is the one being used.
- **Cost of inaction:** Growing at ~5 files per program (EVAL-P20..P24 produced 2, EVAL-P25..P31 produced 5 in `d46ae42`+`b9717ef` alone, two days ago). Each is a prompt whose task is finished; none is a project record. They are also mined by `git grep` as if they were current policy — CR-L04-02 already documents two docs telling operators to run a script dead since 2026-06-04.
- **Fix sketch:** `.gitignore` the `PROMPT_*`, `HANDOFF_*` and `MORNING_HANDOFF_*` patterns and delete the 14 tracked files; a session prompt belongs in the scratchpad, not the repo. Keep the two *plan* documents that `ROADMAP.md` links (`EVAL_P25_TO_P31_PLAN.md`, `EVAL_P20_TO_P24_UNBLOCK_PLAN.md`) only if the roadmap actually cites them; otherwise fold their content into `ROADMAP.md`, which is already the file people read.
- **Effort:** S
- **Removes:** **3,463 lines / 14 files** (2,586 if both plan docs are kept)
- **Blast radius:** `ROADMAP.md` and `DECISIONS.md` cross-links — check the 22 inbound `archive/` refs and any `PROMPT_`/`HANDOFF_` refs before deleting.

### [CR-L11-09] The loop's first night burned 11.45 hours on ISSUE-126, which is still open, and the loop has been dead for 13 days

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `project-harness/.loop-logs/` — 302 of the 375 task session logs share the date 2026-08-02 and are byte-identical stubs for one task: `DRY-RUN: would run claude with prompt: /expand-linear-next --auto --single-task --phase EVAL-P0 --task EVAL-P0.2` / `AUTO_STATUS: DRY_RUN`, spanning 11.45 h (first-to-last mtime). This is exactly `ISSUE-126: expand_loop.sh --dry-run never terminates (its own usage block advertises the hanging form)`, filed 2026-08-02 and still at `project-harness/ISSUES.md:709` — **not** in `archive/ISSUES_RESOLVED.md` — 26 days later. Last loop log: `gate-EVAL-P13-1786778419.log`, mtime **2026-08-15 09:25**. `.loop-state/gate_baseline.json`, mtime 2026-08-15 09:38. In the 13 days since, `project-harness/` took **15,588 further added lines** across 87 commits (`git log --numstat --pretty=format: --since=2026-08-16 -- project-harness/ ':!project-harness/review-2026-08/*'` → 15,588; this review's own evidence directory is excluded and does not change the figure), while 39 of those 87 commits touched `src/`/`demo_game/`/`seeds/` — the harness kept growing, faster than ever, after the thing it was built to drive stopped running.
- **Cost of inaction:** 681 lines of `expand_loop.sh` plus 1,268 lines of supporting machinery are being carried, documented and tested for a system that last ran 13 days ago and whose documented dry-run mode still hangs. Anyone restarting it will hit ISSUE-126 on their first `--dry-run` — the form its own usage block at `expand_loop.sh:55-59` advertises.
- **Fix sketch:** Decide the loop's status explicitly in `DECISIONS.md`: retired, or restarted against an engine-work roadmap. If retired, delete `expand_loop.sh`, `loop_clock.py`, `loop_compat.sh`, `loop.config.sh`, `OVERNIGHT_LOOP.md`, `OVERNIGHT_LOOP_PLAN.md`, `human_verification.md`, `soft_review.md` and `.claude/commands/expand-linear-next.md` together. If restarted, fix ISSUE-126 first — it is a 3-line change (mark the task in the dry-run path so the queue advances).
- **Effort:** S (fix ISSUE-126) / M (the retirement decision)
- **Removes:** ~2,930 lines / 9 files + tests, if retired
- **Blast radius:** `.claude/commands/expand-parallel.md`, `Run-OvernightCombined.ps1`, `HUMAN_TASKS.md`, `ROADMAP.md`'s `LOOP:QUEUE` fence grammar and the `roadmap_cursor` tests that assert it.

---

## Subtraction summary

| Item | Files | Lines | Overlap with another lens |
|---|---|---|---|
| CR-L11-07 unreferenced archive | 175 | 16,724 | none |
| CR-L11-08 one-shot session prompts | 14 | 3,463 | none |
| CR-L11-04 `soft_review.md` | 1 | 305 | none |
| CR-L11-09 loop retirement (if taken) | 9 + tests | ~2,930 | none |
| CR-L11-03 HALT/AUTOFIX tolerance layer | 5 + 1 test | ~669 | subset of CR-L11-09 |
| CR-L11-02 no-decision probes/scaffolding | 11 | ~1,950 | CR-L03-04 proposes *wiring* 810 of these instead |
| **Total, non-overlapping** | **~210** | **~24,673** | |

Nothing in this lens proposes a new mechanism. CR-L11-05's `make measure` is a rename of three
existing `make` targets and is paired with deleting five gates; CR-L11-04's replacement is
"write into `ISSUES.md`", a file that already exists and is already read.
