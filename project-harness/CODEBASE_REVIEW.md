# Strategic Codebase Review — NPC Engine, 2026-08

**Reviewed:** 2026-08-27/28 · branch `eval-ab-context-arms` · HEAD `d46ae42` · 967 commits · 16 lenses · 145 findings
**Deliverable:** this file. Per-lens evidence in `project-harness/review-2026-08/evidence/CR-L##.md`. Triage table in `project-harness/review-2026-08/FINDINGS.md`.

| | CRITICAL | HIGH | MEDIUM | LOW | total |
|---|---:|---:|---:|---:|---:|
| Findings | **4** | 63 | 55 | 23 | **145** |

Effort profile: 80 × S (<2h), 34 × M (<1d), 7 × L, 1 × XL, rest split. **The great majority of this review is small work.**

---

## §A — Verdict

**This codebase is well-built and pointed at the wrong target.** The engineering is genuinely good: 68,218 lines of `src/npc_engine/` with a layer model that provably holds (an injected `graph`→`api` import turns `check-layers` red), mypy at zero for twelve weeks, transaction ownership intact, 87.86% coverage over 4,048 tests, healthy file decomposition (median `graph/` file 103 lines), and — checked twice — no secrets anywhere in the tree or its history. This is not a mess. That matters, because the rest of this verdict is harsh, and it is not harsh about craft.

It is harsh about **direction and about verification**. Four CRITICALs, each traced end to end or executed live. The signature feature does not work: gossip distortion never compounds across hops, because `gossip_batch_queries.py:29-47` returns the canonical event summary rather than the sharer's distorted one — the demo looks right only because the chain is hand-seeded, and running the world *erases* the seed. The instrument that would have caught that is itself broken: a null responder emitting one fixed string scores **0.949** on the guard battery against the engine's **0.897**, and no scorer's agreement interval excludes chance. The documented Neo4j→503 fallback contract does not exist at any of its three hops (`grep -rn "503" src/npc_engine/api/` returns nothing). And `/setup/*` is unauthenticated in every environment on a "localhost is the trust boundary" assumption that the shipped `docker-compose.yml` falsifies by binding `0.0.0.0` — exposing an endpoint that reads back a plaintext API key. Meanwhile the tree has no integrator, has never had one, `make package` has never once been buildable, there are zero lines of C# or C++ for the two named target clients, and the knowledge graph holds 52 nodes against a stated 10,000 minimum.

The single most important thing to change is **what supplies the definition of "done"**. With no integrator, the eval harness became the only scoreboard — so the project optimised the scoreboard. The machinery is now larger than the product it measures (107,323 : 106,685 lines) and grew 8.7:1 against it over the last 200 commits; 24 gate/loop scripts totalling 4,500 lines have produced no downstream decision in 967 commits; and in those 967 commits the entire gate battery caught **one** defect in shipped runtime behaviour — found by a probe no gate runs. The 14 green gates are not evidence of health: 6 of 14 fail a counterfactual and 5 can print a problem and exit 0. The proof is L14's executed experiment — gutting 105 of 180 graph repository methods to return constants left `mypy` clean and broke only that layer's own passthrough tests. **You can replace the graph read layer with stubs and keep 14 green gates, 4,048 passing tests, and 87.86% coverage.** Fix the four CRITICALs (all S or M), name an integrator and a date, and delete the ~22,000 lines of zero-risk machinery. Do not add another gate.

---

## §B — The numbers

The factual spine. Every row was measured this run unless marked.

### Size and shape

| Measure | Value | Lens |
|---|---|---|
| `src/npc_engine/` | **68,218** py LOC / 627 files | §0 |
| `tests/` | 80,324 / 544 | §0 |
| `demo_game/` | 36,961 / 186 | §0 |
| `evals/` | 20,141 / 292 | §0 |
| `project-harness/` | **48,988 markdown lines** / 253 files (224 archived) | §0 |
| `scripts/` · `e2e/` · `docs/` | 7,821 · 7,597 · 5,507 | §0 |
| Real product/demo/eval LOC split | **54% / 29% / 16%** (brief said 26/47/25 — wrong) | §0 |
| `graph/` file size median / p90 / over 300 | 103.5 / 218 / **1 file** | L4 |
| `engines/` file size median / p90 / over 300 | 68 / 209 / 6 files | L4 |

### Process vs. product

| Measure | Value | Lens |
|---|---|---|
| Machinery : product, static LOC | **1.01 : 1** (107,323 : 106,685) | L11 |
| Machinery : product, lines added last 200 commits | **8.68 : 1** | L11 |
| Churn full history (file-touches) | 0.55 : 1 | L11 |
| Churn last 200 commits | **4.16 : 1** | L11 |
| Last-200 touches: evals / tests / harness / src / **demo_game** | 392 / 321 / 289 / 172 / **8** | §0 |
| Commits touching zero code, last 200 | **60 (30%)** | L10 |
| Gate/loop scripts with no downstream decision | **24 scripts, 4,500 lines (54% of machinery)** | L11 |
| Genuine gate catches in 967 commits | **9** — of which shipped-behaviour defects: **1** | L11 |
| Mandatory context preamble | 36,595 chars ≈ **9,150 tokens** = 4.6% of 200k; ≈**1.77M tokens** to date | L5 |
| If the "every session reads ISSUES.md" mandate were honoured | 44,495 tokens / ~2.5 h per session | L4 |
| Total lifetime gate *execution* time | **under 8 hours** — the cost is authorship and reading, not running | L11 |

### Gates

| Measure | Value | Lens |
|---|---|---|
| `make check` targets | **14** (brief assumed 13; an earlier draft of §0 said 15) | L6 |
| `make check` wall-clock | **595 s (9m55s)**; 94% is the two coverage runs | orch. |
| Other 12 gates combined | **33 s** over a 68k-LOC tree | orch. |
| Gates failing a counterfactual | **6 of 14** | L6 |
| Gates that can print a problem and exit 0 | **5 of 14** | L6 |
| Gates CI actually runs | **6 of 14** — the 8 skipped include the only two ever red on main | L6 |
| Grandfathered violations | **205** (133 rules + 72 evals); 102 × R006, 31 × R001 | L6/L8 |
| Ratchet burn-down | src 1.43/month → **7.8 years to zero**; evals baseline *grew* 59→72 in 17 days | L6 |
| `.mypy_baseline` | **0** since 2026-06-04 (`HARNESS_GATES.md` still says 256) | orch. |
| `demo_game/` under gates | outside all but 2 file-shape rules; **256 mypy errors**; 1,116 tests in 9.25 s, run by nothing | L6 |
| Non-test LOC under **no** coverage floor | **36,527** (29% of surface), incl. the gate scripts themselves | L15 |

### Tests

| Measure | Value | Lens |
|---|---|---|
| `make test` | 4,048 passed / 36 skipped, 333 s | L15 |
| `make test-cov` | 18,341 statements, **87.86%** (floor 80) | orch. |
| `make test-cov-evals` | 5,993 statements, **79.76%** (floor 75) | orch. |
| `make test-demo` | 1,116 passed, 12.1 s | L15 |
| Import-only coverage inflation | **under 2%** — the coverage is real | L15 |
| Flaky tests across 2 full runs | **0** | L15 |
| Share of `make test` that is real network I/O | **~51% (169 s)** — "unit" tests calling live Ollama/API | L15 |
| Counterfactual: gut 105 of 180 repo methods | mypy clean; **66 failures, all the layer's own passthrough tests** | L14 |
| Integration tests without `NEO4J_URI` | **9 passed, 34 skipped** — which is what `make check` runs | L14 |
| Real per-commit hook cost | **4.9 s** (not 595 s) | L15 |

### Eval validity

| Measure | Value | Lens |
|---|---|---|
| **Null responder vs engine, guard battery** | **0.949 vs 0.897** (published claim: 0.914) | L3 |
| Judge/human agreement | tone κ=0.849 **[−0.010, 1.000]**; refusal κ=0.247 [−0.123, 0.703]; affirms 0.530 [0.000, 1.000] | L3 |
| Scorers whose interval excludes chance | **0 of 4** | L3 |
| MDE vs headroom | affirms 17.25pp vs 5.9pp; refusal 29.01pp vs 8.0pp — **cannot resolve any possible effect** | L3 |
| Base rate, YAML guard cases | **1.000** | L3 |
| Policy claims checked / diverged | **131 / 38** | L3 |
| Newest gate layer reachable from no `make` target | **1,522 LOC** | L3 |
| Eval-validity gates in CI | **0** | L3 |
| Leakage (judge vs generator) | **clean** — genuinely enforced | L3 |
| Reproducibility | 0.628 against a 0.95 gate, recorded NOT_MET, gated by nothing | L3 |

### Documentation and backlog

| Measure | Value | Lens |
|---|---|---|
| `docs/` claims checked / false / unverifiable | **74 / 29 / 3** (39% false) | L13 |
| `CLAUDE.md` claims checked / false / unverifiable | **109 / 26 / 6** | L5 |
| `CLAUDE.md` strict-rule census | 8 live · 3 dead · 10 aspirational · **7 theatre**; 5 gated, 22 ungated | L5 |
| Docstring compliance, gated fields vs ungated | **100% / 100% vs 66% / 28%**; ungated `demo_game/` scores **81%** — higher than gated `src/` | L5 |
| Engine-log 4-field mandate compliance | **0% across 118 call sites** | L5 |
| Open issues / real P1s / P1s that block | **67 / 7 / 4** (brief said ~23 P1s) | L7 |
| Issue age median / max | 10 d / 79 d | L7 |
| DECs total / reused IDs / never referenced outside harness | 219 / 5 / **53%** | L7 |
| Roadmap now vs 8 weeks ago | 210 done/65 open vs 119/28 — **backlog growing 40% faster than it clears**; last week 0 done, +25 added | L7 |
| Unchecked roadmap items that are eval meta-work | **71% (46 of 65)** | L2 |
| Of the 17 touching engine code, requiring edits to existing files | **100%** | L2 |

### Product and ops

| Measure | Value | Lens |
|---|---|---|
| Integrators, pilots, design partners, external contributors | **0, ever** | L12 |
| Active roadmap programs that are eval/harness | **8 of 8** | L12 |
| Lines of C# / C++ for the two named target clients | **0** | L12 |
| `make package` | **has never been buildable** — spec references paths absent at its own introducing commit | L12 |
| Graph nodes vs the 10,000 NFR | **52** (0.5%, off by 190×) | L12 |
| Gossip throughput vs 200 pairs/tick | never benchmarked; largest `max_pairs` anywhere = 20 | L12 |
| LLM fallback vs 100 ms | **0.687 ms** median (n=21) — met | L12 |
| Engine fallbacks traced / wired / unwired | **18 / 4 / 14** | L1 |
| Engines registered on tick path | 27 (`memory_consolidation` absent — has never run) | L1 |
| Fresh clone boots? | **No** — needs `core.longpaths` + a `.env` that only exists as `.env.example` | L16 |
| Deps pinned / ranged / unpinned; lockfile | 13 / 7 / 1; **no lockfile** | L16 |
| Secrets in tree or full git history | **none** | L16 |
| Copyleft exposure | `pygame-ce` LGPL, confined to `demo_game/`, absent from the licensed engine | L16 |
| Python target | **Docker/mypy 3.11 vs CI/README 3.14** — two incompatible targets | L16 |
| Time to first useful change (new contributor) | ~1.1 h realistic; 3.4 h at literal CLAUDE.md compliance | L4 |
| Files touched for one plausible feature | **20** | L4 |
| Migrations with a down path or applied-state record | **0 of 7** | L4 |

---

## §C — Systemic patterns

Five root causes. Each has three or more findings behind it; duplicates across lenses are merged here and not double-counted.

### C1 — The artifact satisfies the check while the behaviour is absent

*The review's central pattern.* Contributing: CR-L01-01, CR-L01-05, CR-L03-01, CR-L05-03, CR-L06-01/02/03/07/08, CR-L08-03, CR-L11-06, CR-L13-06, CR-L14-01/02/04, CR-L15-01.

The repo's own history named this failure — "asserted-not-measured" — and then reproduced it at every level. A docstring promises `GraphUnavailableError` and nothing raises it. A gate prints `HUMAN GATES OK (0 gates)`. `check_conservation`'s Identity 2 was rewritten into `x == x` **in a commit labelled a bug fix**. `check_harness_honesty`'s H3 reads a file that was archived and never restored. 15 tests guard a `session` parameter that no longer exists. And the whole graph read layer can be stubbed out without any gate noticing.

The mechanism is consistent and worth naming precisely: **the check binds to the artifact's form, not to the behaviour the artifact stands for.** `docstring_audit.py` verifies the substring `Layer:` exists — so `src/` scores 100% on the two fields it checks and 28% on one it does not, while *ungated* `demo_game/` scores 81%, higher than the gated tree. Compliance tracks the gate, never the rule. That is why 22 of 28 strict rules are ungated and effectively fictional, and why one of this review's CRITICALs was, as L11 puts it, *manufactured* by a docstring mandate plus a content-blind gate.

The cure is not more gates. It is **counterfactual testing as the acceptance criterion for a gate**: a gate earns its place only if someone has deleted the thing it guards and watched it go red. L6 ran that test on all 14 and 6 failed.

### C2 — No external clock, so the scoreboard became the product

Contributing: CR-L11-01/02/03/05, CR-L12-01/02/03/06, CR-L02-07, CR-L07-05, CR-L10-06, CR-L03-04.

There is no integrator and never has been. Nothing outside the repo defines "done", so the eval harness supplied one — and the project optimised it. The consequences are all measured: machinery outgrew product 8.68:1 over 200 commits; 8 of 8 active roadmap programs are eval work; 71% of unchecked items are eval meta-work; the product program was moved to a side file the loop cannot see 28 days ago; `demo_game/` was touched 8 times in 200 commits; `make package` has never worked. L9's counterfactual is the sharpest statement of it: a `src/` + `tests/` + thin-README version of this project would have worse architecture and no eval science — *but it would have a shipping demo and an integrator*, because the harness's largest single effect was supplying a substitute definition of done.

This is also why CR-L03-01 is the most expensive defect in the tree. When the scoreboard is the only clock, a scoreboard that ranks a fixed string above the engine misdirects everything downstream of it.

### C3 — Ratchets that became floors

Contributing: CR-L06-04/05, CR-L08-01/02, CR-L05-04, CR-L07-03, CR-L13-01.

The ratchet design was sound and it worked once — 57 down to 38 in a day. Then it stopped. 205 grandfathered violations remain; src debt retires at 1.43/month (7.8 years to zero) while the evals baseline *grew* 59 to 72 in 17 days. The reason is mechanical and fixable: **`check-rules` signatures are file-level**, so a grandfathered file grows without limit — `demo_game/client.py` gained 481 lines while the gate stayed green, and is now 1,901 lines against a DECISIONS-stated ceiling of 900. `game_window.py` regrew to 925 after DEC-032 declared the size problem "resolved". Three waivers are silently violated live on main. `CLAUDE.md` calls these "hard limits" and never mentions the permanent exemption list.

Note what this pattern is *not*. Two lenses independently exonerate the 300-line rule: median `graph/` file is 103 lines, only 28 of 627 files sit in the 250–299 band. The fragmentation blamed on it is actually caused by **DIP-strict**, which mandates a Protocol per interface and produced 8,565 lines across 107 files — 44 ports, 14 with one caller, 10 with one method. **Keep the line limit; rewrite the Protocol rule to require 2+ implementors or 3+ callers.**

### C4 — Documentation drifts because nothing reads it back

Contributing: CR-L13-01 through 11, CR-L05-08, CR-L04-02/04, CR-L07-02/06, CR-L16-02, CR-L02-02, CR-L08-09.

39% of checked `docs/` claims are false; 26 of 109 `CLAUDE.md` claims are false. The pattern is that documents assert *state* — counts, baselines, "implemented", file paths — and no process ever compares the assertion to reality. `HARNESS_GATES.md`, whose entire purpose is catching silent debt drift, has both its headline numbers wrong in opposite directions (57 vs 133; 256 vs 0) and has not been touched in 85 days. `CONTRIBUTING.md` points five links at a `project/` directory that does not exist. Three eval docs advertise `make` targets that were never wired. Two docs still instruct operators to run a migration dead since June.

The honesty gate built for exactly this is inert: all three of its checks are structurally unable to fire. The cheap fix is not a better gate — it is to **stop putting drifting numbers in prose** and cite the file instead.

### C5 — Decisions that were individually sound and jointly unsafe

Contributing: CR-L05-11, CR-L16-01/03/06/07, CR-L04-01/06, CR-L12-09.

The `/setup/*` CRITICAL is the archetype and worth understanding as a class, not an incident. DEC-131 exempted setup routes from auth *because* the loopback bind was the trust boundary — reasonable. A separate change published `8000:8000` in compose, binding `0.0.0.0` — also reasonable. DEC-131 also accepted a plaintext API key on disk *because* of the same boundary — reasonable given its premise. No mechanism ever rechecked the premise, so three sound decisions compose into an unauthenticated remote read of a secret. The same shape appears in Docker/mypy targeting 3.11 while CI and the README mandate 3.14; in a staleness detector (`boot-check`) that exists but which no documented path invokes; and in 7 migrations with no down path and no applied-state record, shipped toward customers who would run them on their own data.

---

## §D — Subtraction ledger

From L9, which deduplicated the other lenses' proposals and verified each with a reference check. **Grand total ≈ 34,531 lines / ~296 files.** Zero-risk ~22,156 (~208 files) · low-risk ~1,525 (~14) · needs-a-decision ~10,850 (~74).

| # | What | Lines | Files | Risk | What breaks | Verdict |
|---|---|---:|---:|---|---|---|
| 1 | Unreferenced `project-harness/archive/` markdown | 17,699 | 177 | none | nothing (177 unref / 38 ref, measured) | **delete now** — also fixes the Windows clone blocker |
| 2 | One-shot session prompts / handoffs (2 kept, ROADMAP links them) | 2,791 | 12 | none | nothing | **delete now** + `.gitignore` the pattern |
| 3 | Overnight-loop bundle | 5,178 | 18 | med | the loop, if restarted | **delete after** a DECISIONS entry retires it |
| 4 | `CLAUDE.md` 476 → 248 | 228 | — | low | nothing; ~2,600 tokens off every session | **delete now** |
| 5 | `*_delegates` tests + passthrough repo bodies | ~2,070 | — | med | net *loss* until Neo4j is in CI | **delete after** Neo4j runs in CI |
| 6 | Trend/regression stack (1 row, already incomparable) | 1,309 | 7 | med | nothing today | **delete after** one full-corpus generation decides it |
| 7 | Sequence subsystem (keep reset-fidelity — it is wired) | 1,714 | — | med | 6 consumers incl. 2 `e2e/scripts/` | **delete after** the split |
| 8 | Mock/oracle labelling scaffolding | 1,248 | — | low | oracle trio is live | mock half **delete**; oracle **keep** |
| 9 | `check_engine_coverage` + contract + test | 658 | 3 | none | nothing (no `make` target) | **delete now** |
| 10 | Single-caller `engines/ports/` Protocols | ~552 | 10 | low | nothing | **delete after** the DIP rule is rewritten |
| 11 | `live_openapi.json` (182 KB, 64 days stale) | — | 1 | none | zero consumers, verified | **delete now** |
| 12 | `engines/deception/` + `engines/currency/` | ~140 | 5 | none | zero production callers | **delete now** (needs approval) |
| 13 | 15 `session_kwarg` tests + 76 phantom docstring lines | ~226 | — | none | nothing — they guard a deleted parameter | **delete now** |
| 14 | 7 dead `verify-*` Makefile targets | — | — | none | nothing | **delete now** |
| 15 | 4 theatre gates out of `make check` | — | — | low | nothing they were catching | **delete now** |
| 16 | Dead `keyword_none` expectation blocks + 3 `moderation_everyone_*` cases | — | 3 | none | guaranteed passes | **delete now** |
| 17 | `check_conservation` Identity 2 (`x == x`) | — | — | none | nothing | **delete now** |
| 18 | `add_faction_support.py` (dead since 2026-06-04) | — | 1 | none | nothing; 2 docs must stop naming it | **delete now** |
| 19 | 3 abandoned policy docs | — | 3 | none | nothing | **delete now** |
| 20 | `soft_review.md` (~60 findings read by nothing) | 305 | 1 | none | one finding survives as an open HIGH here | **delete now**, after re-filing that one |
| 21 | `EVAL_STRATEGY.md` (3-month-old duplicate of `EVAL_METHODOLOGY.md`) | — | 1 | none | nothing | **delete now** |
| 22 | Duplicate `_draw_no_data` helpers | ~45 | — | none | nothing | **delete now** |
| 23 | **46 eval-meta roadmap items** | — | — | high | the current program | **decide** — the only row that changes the ratio |

**Calibration, stated plainly:** 94% of the ledger is machinery. Executing all of it moves harness:product from 1.01:1 to ~0.78:1 and **does not fix the underlying problem**. Only row 23 does.

**Three things not to delete, despite looking like waste.** (1) The engine half of `tests/` (~61,300 lines) — import-only inflation is under 2%, and a mismatched `run_tick` was caught by an engine unit test when mypy, `BaseEngine` and every gate missed it. (2) `demo_game/` — it was repurposed as the eval program's fixture generator (`Makefile:627`), and three CI-gated tests import it; **gate it (+9 s), don't cut it**. (3) `check_layers` and the mypy gates — two of the few that pass a counterfactual, holding 2 of the 9 real catches. Culling the battery must not take the parts that aren't theatre. L9's coda is worth keeping: the ~1,200-line probe set is the thing to *grow*, since it holds the only shipped-behaviour catch in 967 commits.

**Conflicts resolved** (so you act once, not twice): the escalated `check_base_rate` / `check_engine_coverage` question splits — **wire** `check-base-rate` (386 lines; it measures the very breach under CR-L03-01), **delete** `check_engine_coverage` (658). On the archive, L11's deletion wins over L8's caveat. On `check_conservation`/`check_label_survival`, L6 first (out of `make check`), then L3's repoint when wiring into `make eval-generate` — order matters. Two corrections carried forward: `scan_fix_diff.py` is not standalone (`expand_loop.sh:387`) so it goes with the loop bundle, and the sequence subsystem is not isolated (6 consumers).

---

## §E — Do this next

Ten items, ordered by impact ÷ effort.

| # | Do | Why | Effort | Closes |
|---|---|---|---|---|
| 1 | Bind `127.0.0.1:8000:8000` and gate the `/setup/*` auth exemption on `env == "dev"` as `/docs` already is | Unauthenticated remote read of a stored plaintext API key, today | **S** | CR-L05-11, CR-L05-06 |
| 2 | Print the null-responder baseline beside every published eval number, and stop citing the guard rate until it clears | The headline metric currently ranks a fixed string above the engine | **S** | CR-L03-01, CR-L03-02 |
| 3 | Make gossip relay the sharer's `distorted_summary`, and stop the batch write clobbering seeded edges | The signature demo feature is a no-op and running the world erases the demo | **M** | CR-L01-01, CR-L01-02, CR-L12-04 |
| 4 | Raise `GraphUnavailableError` on driver `ServiceUnavailable`, register a 503 handler, make `TokenBudgetExceededError` structured | A studio cannot tell "retry" from "your request is broken" | **M** | CR-L08-03, CR-L02-01, CR-L01-06, CR-L05-01 |
| 5 | Delete rows 1, 2, 4, 9, 11–22 of §D | ~22,000 zero-risk lines; also unblocks `git clone` on Windows | **M** | CR-L09-01/04/05/06, CR-L11-04/07/08, CR-L08-09, CR-L01-12 |
| 6 | Remove the 4 theatre gates from `make check`; make `check-rules` signatures line-count-bearing so grandfathered files cannot grow | 5 gates can exit 0 while reporting problems; `client.py` grew 481 lines while green | **S** | CR-L06-01/03/05/07/09, CR-L15-03 |
| 7 | Put Neo4j and Ollama services in CI, add `test-demo` and `demo_game` mypy to it | 34 integration tests skip in the run that gates merges; 36,527 LOC has no floor | **M** | CR-L14-02, CR-L15-01/06, CR-L06-06/10, CR-L12-08 |
| 8 | Fix `HARNESS_GATES.md`, `CONTRIBUTING.md`, `README.md`; delete numbers from prose and cite the files | 39% of doc claims are false, including onboarding that cannot work | **S** | CR-L13-01 through 05/07, CR-L16-02, CR-L04-04 |
| 9 | Cut `CLAUDE.md` 476 → 248: delete the 3 fictional contracts, the 0%-compliance log mandate, the ISSUES.md read mandate; rewrite DIP to 2+ implementors; keep the 300-line rule | 22 of 28 strict rules are ungated; the file has never had a line removed | **M** | CR-L05-01/02/04/09/10, CR-L04-03, CR-L14-03 |
| 10 | Give the 7 migrations a down path and an applied-state record | Zero recovery procedure exists for a customer-side schema change | **M** | CR-L04-01, CR-L04-06 |

### Decide — these need a human, and little below the line moves without them

1. **Is CI green on `main`?** Five minutes in the Actions tab. `make test-cov` runs in a job with no Ollama or Neo4j service, so either it is red and unnoticed (making CR-L15-01 the fifth CRITICAL) or those tests take a different path in CI than locally. Branch protection is also unverifiable locally — `gh` is not installed, there is no CODEOWNERS or ruleset file, and `HARNESS_GATES.md` has listed "mark these CI jobs required" as open since June. **Do this one first.**
2. **Name an integrator and a date.** This is row 23 of §D and the root of C2. Everything else is rearrangement until an external clock exists.
3. **Is the B2B product track paused or active?** The current state — 12 unchecked items in a side file the loop cannot see, 0 commits in 28 days — is the worst of both. Restore one product program to `ROADMAP.md` or say in writing that it is paused.
4. **Is the overnight loop retired or restarted?** 5,178 lines carried 13 days with no owner; `ISSUE-126` (its `--dry-run` hangs; it burned 11.45 h on night one) is open 26 days.
5. **Which Python is the target** — Docker/mypy 3.11 or CI/README 3.14?
6. **Rotate the wizard API key** if port 8000 has ever been reachable off-box.
7. **Approve deletion of ~200 files** — CLAUDE.md requires human approval to delete files the session did not create.
8. **Precedence between `project-harness/CLAUDE.md` (300 lines / 40-line functions) and the user-level `rules/common/coding-style.md` (800 / under 50)** — they load together with no stated ordering.
9. **Should the demo be shown to any external audience before item 3 lands?**

---

## Appendix — copy-pasteable stubs

These are **proposals**. Per the review's own terms, no entry was written into `ISSUES.md` or `DECISIONS.md`. Pick your own next free IDs — L7 found 5 DEC numbers and 2 ISSUE numbers already reused, so check both `ISSUES.md` and `archive/ISSUES_RESOLVED.md` before assigning.

```markdown
## ISSUE-NNN: /setup/* is unauthenticated off-box because compose binds 0.0.0.0
**Found:** 2026-08-27, during the 2026-08 strategic codebase review
**Severity:** P1 (blocking)
**Where:** auth/middleware_helpers.py (setup exemption), docker-compose.yml:72, api/routes/setup/setup.py:97
**Description:** The /setup/* auth exemption is unconditional in every env. DEC-131 justifies it
by a 127.0.0.1 bind, but docker-compose publishes "8000:8000" which binds 0.0.0.0 (verified:
`docker port npcsystem-app-1` -> 0.0.0.0:8000). GET /setup/config returns a wizard config that
DEC-131 documents as storing a plaintext cloud API key. POST /setup/config accepts a
schema-hidden config_dir query param that mkdir -p's and writes as root.
**Why deferred:** not deferred — see CR-L05-11, fix is S.
**To fix:** bind 127.0.0.1:8000:8000; gate the exemption on env == "dev" as /docs already is;
drop or restrict config_dir; supersede DEC-131. Rotate the key if port 8000 was ever reachable.

## ISSUE-NNN: gossip distortion does not compound across hops
**Found:** 2026-08-27, during the 2026-08 strategic codebase review
**Severity:** P1 (blocking)
**Where:** src/npc_engine/graph/gossip/gossip_batch_queries.py:29-47
**Description:** The relay returns best_event.summary (the canonical Event node) rather than the
sharer's own distorted_summary, so every hop distorts the original. Verified live: lira_fence
learned from mira_innkeeper's 27-word account but holds "The northern armies", an omission of
the canonical 7-word summary. Separately the MERGE...SET overwrites existing KNOWS_ABOUT edges:
old_henryk, seeded at distortion_level 70, reads distortion_level 0 at tick 600.
**Why deferred:** not deferred — see CR-L01-01/02.
**To fix:** relay the sharer's distorted_summary; make the write preserve existing distortion.
Expect gossip determinism fixtures and eval golden strings to shift.

## ISSUE-NNN: the guard battery is beaten by a fixed string
**Found:** 2026-08-27, during the 2026-08 strategic codebase review
**Severity:** P1 (blocking)
**Where:** evals/, evals/reports/20260825T231028Z.md:11, hedge_responder_probe.py:71-76
**Description:** A null responder emitting one hard-coded sentence scores 74/78 = 0.949 across
the YAML guard cases and the ah_demo_* fixture, with the three LLM-judge verdicts measured live.
The engine scores 70/78 = 0.897. The published claim is "Guard 170/186, 0.914". The baseline had
never been taken because hedge_responder_probe.py refuses to score guard cases. No scorer's
agreement interval excludes chance.
**Why deferred:** not deferred — see CR-L03-01.
**To fix:** print the null baseline beside every published number; stop citing the guard rate
until it clears its baseline; wire check-base-rate.

## ISSUE-NNN: the Neo4j-unavailable fallback contract is unimplemented at every hop
**Found:** 2026-08-27, during the 2026-08 strategic codebase review
**Severity:** P2 (annoying)
**Where:** utils/errors.py:54,301; api/errors/exception_handlers.py:113-120
**Description:** CLAUDE.md declares (strict) "Neo4j unavailable -> raise GraphUnavailableError ->
API 503". `grep -rn "raise GraphUnavailableError" src/` returns 0; so does
`grep -rn "503" src/npc_engine/api/`. Raw neo4j.exceptions.Neo4jError propagates instead
(declared in 11+ graph docstrings) and the catch-all handler returns HTTP 500. Of 18 engine
fallbacks traced, 4 are wired and 14 are not. TokenBudgetExceededError subclasses bare Exception.
**Why deferred:** not deferred — see CR-L08-03 / CR-L01-06 / CR-L02-01.
**To fix:** raise on driver ServiceUnavailable/SessionExpired, register a 503 handler, make the
error structured — or delete the claim from CLAUDE.md and the 11 docstrings.
```

```markdown
## DEC-NNN: a gate must pass a counterfactual before it joins `make check`
**Date:** 2026-08-28
**Context:** The 2026-08 review ran a delete-the-guarded-thing counterfactual against all 14 gates
in `make check`. Six failed: check-human-gates (prints "0 gates", exit 0), check-test-quality
(main() can only return 0), check-conservation (Identity 2 is x == x), check-harness (its only
hard check sits behind a lint that runs first), check-label-survival (inputs cannot change), and
check-docstrings (verifies the substring "Layer:" exists, nothing more). In 967 commits the whole
battery produced 9 real catches, of which exactly 1 was a defect in shipped runtime behaviour —
and that one came from a probe no gate runs.
**Decision:** A gate may be added to `make check` only with a recorded counterfactual: the commit
adding it must show the gate red with the guarded behaviour removed. Existing gates that fail this
are removed rather than repaired. New verification effort goes into probes, not gates.
**Consequences:** 4 gates leave `make check`. `check_layers` and the mypy gates stay — they pass.

## DEC-NNN: rules-baseline signatures become line-count-bearing
**Date:** 2026-08-28
**Context:** rules_baseline.txt signatures are file-level, so a grandfathered file may grow without
limit. demo_game/client.py gained 481 lines while the gate stayed green and now stands at 1,901
against a DECISIONS-stated ceiling of 900; game_window.py regrew to 925 after DEC-032 declared the
problem resolved. Live baseline is 133 entries retiring at 1.43/month — 7.8 years to zero — while
the evals baseline grew 59 to 72 in 17 days.
**Decision:** Grandfathered R001/R006 entries record the line count at grandfathering; the gate
fails if a grandfathered file exceeds its recorded size. Waivers carry an explicit ceiling.
**Consequences:** Three currently-violated waivers must be re-waived at their real sizes or split.

## DEC-NNN: DIP requires a Protocol only at 2+ implementors or 3+ callers
**Date:** 2026-08-28
**Context:** DIP-strict as written mandates a Protocol per interface. It produced engines/ports/ at
8,565 lines across 107 files — 44 Protocols, 14 with a single caller, 10 with a single method. The
review measured file-size distributions to test whether the 300-line rule caused the fragmentation
and found it did not (median graph/ file 103 lines; 28 of 627 files in the 250-299 band). The
Protocol rule is the cause.
**Decision:** A Protocol is required only where there are 2+ implementors or 3+ callers. The
300-line and 40-line limits are retained unchanged — two lenses independently exonerated them.
**Consequences:** ~552 lines of single-caller ports become deletable; more if the seam is collapsed.
```

> Synthesis (§A–§E) is above. What follows is the baseline and the sixteen
> lens reports, in the order they reported. Each lens's findings were appended
> live as it finished; the synthesis was written last.

---

## §0 — Baseline

| Item | Value |
|---|---|
| Date | 2026-08-27 |
| Branch | `eval-ab-context-arms` |
| HEAD | `d46ae42f71fc15586c145a0c8467e6cb8a296fb2` |
| Commits on HEAD | 967 |
| First commit | `74b05a4` 2026-04-15 |
| Last commit | `d46ae42` 2026-08-27 |
| Working tree | Effectively clean — one untracked file: `project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md` (this review's own prompt). All other new work under `evals/`, `scripts/`, `tests/`, `project-harness/` is committed and in scope. |

### LOC by top-level directory (tracked files only, `git ls-files`)

| Directory | Tracked files | Python LOC | Markdown LOC | All-text LOC |
|---|---:|---:|---:|---:|
| `src/npc_engine/` | 760 (627 `.py`, 124 `.yaml`) | **68,218** | 31 | 70,194 |
| `tests/` | 544 | **80,324** | 0 | 80,324 |
| `evals/` | 292 | **20,141** | 497 | 49,536 |
| `demo_game/` | 186 | **36,961** | 0 | 36,966 |
| `project-harness/` | 253 | 0 | **48,988** | 48,988 |
| `scripts/` | 53 | 7,821 | 0 | 8,962 |
| `e2e/` | 51 | 7,597 | 0 | 7,597 |
| `docs/` | 22 | 0 | 5,507 | 5,507 |
| `seeds/` | 4 | 1,125 | 0 | 1,125 |
| `prompts/` (eval judges) | 7 | 0 | 0 | 157 |

**Correction to the review brief's own numbers.** The brief states
`src/npc_engine/` = 20.4k LOC, `demo_game/` = 37k, `evals/` = 19.4k, and an
LOC split of "engine 26% / demo 47% / evals 25%". Measured, `src/npc_engine/`
is **68,218 Python LOC** — 3.3× the briefed figure. The real product/demo/eval
split is **54% / 29% / 16%**. The brief's split understates the engine by half
and was probably taken from a stale count. Lenses were told to measure, not to
inherit these figures.

`src/npc_engine/` internals, by Python LOC:

| Package | LOC | Files |
|---|---:|---:|
| `graph/` | 22,598 | 200 |
| `engines/` | 20,014 | 219 |
| `api/` | 10,239 | 86 |
| `retrieval/` | 5,498 | 36 |
| `type_registry/` | 1,452 | 13 |
| `schema/` | 1,240 | 16 |
| `scheduler/` | 1,190 | 7 |
| `setup/` | 1,139 | 9 |
| `data/` | 717 | 4 |
| `utils/` | 680 | 4 |
| `auth/` | 675 | 6 |
| `scripts/` | 530 | 4 |
| `world/` `services/` `common/` `mutation/` `cache/` | 855 | 19 |

### Live-check capability this run

| Service | State | Consequence for evidence |
|---|---|---|
| Docker | Up (`npcsystem-app-1` up 2h, `npcsystem-neo4j-1` up 2 days, healthy) | Container-level checks possible |
| API `http://127.0.0.1:8000/health` | **200** | L3/L16 live API checks possible |
| Ollama `http://127.0.0.1:11434/api/tags` | **200** | LLM-dependent evals runnable |
| Neo4j HTTP `:7474` | **Not published to host** (only `8000/tcp` is mapped) | Host-side Cypher/browser checks impossible; graph reachable only from inside the app container |
| Python (host) | see L16 | — |

So "Confirmed" is achievable this run for L6, L15, L16 and for the LLM-dependent
parts of L3. Host-side direct-Neo4j checks are not.

### Prior art read

`project-harness/archive/review-2026-06-03/` (the SEV-nn review that produced the
gate suite), `project-harness/HARNESS_GATES.md`, `project-harness/CLAUDE.md`,
`docs/BUSINESS_REQUIREMENTS.md`, `README.md`, `Makefile` (693 lines, 101 targets).

`make check` as defined today (`Makefile:200`) is **14** targets, not the 13 the brief
assumes. (An earlier draft of this header said 15; L6 recounted it and is right.)

```
check: lint check-rules check-evals-rules check-layers check-docstrings type \
       type-evals check-harness check-human-gates check-test-quality \
       check-conservation check-label-survival test-cov test-cov-evals
```

---

## Per-lens findings

_(appended live as lenses report)_

---

## L10 — Churn risk

# CR-L10 — Churn risk

Repo: NPC Engine, branch `eval-ab-context-arms`, HEAD `d46ae42`, 967 commits, 2026-04-15 → 2026-08-27.
Method: `git log --name-only` over the last 200 / last 500 / full history, piped through `sort | uniq -c`;
a custom pass over `git log --reverse --name-only` for fix-of-fix adjacency. All commands below were run
against this exact HEAD; outputs are pasted verbatim (line-wrapped only where noted).

## Required measurements

### 1. Top-25 churned files — last 200 commits vs last 500 commits

`git log -N --name-only --pretty=format: | grep -v '^$' | sort | uniq -c | sort -rn | head -25`

**Last 200** (body attribution in parens):

| # | Touches | File | Body |
|---|---|---|---|
| 1 | 84 | project-harness/ROADMAP.md | harness |
| 2 | 57 | project-harness/ISSUES.md | harness |
| 3 | 53 | project-harness/DECISIONS.md | harness |
| 4 | 31 | Makefile | root |
| 5 | 25 | project-harness/archive/ISSUES_RESOLVED.md | harness |
| 6 | 20 | project-harness/human_verification.md | harness |
| 7 | 13 | tests/unit/harness/test_roadmap_cursor.py | tests |
| 8 | 12 | src/npc_engine/retrieval/context/context_builder.py | src |
| 9 | 11 | project-harness/soft_review.md | harness |
| 10 | 11 | project-harness/Run-OvernightCombined.ps1 | harness |
| 11 | 10 | evals/summary.py | evals |
| 12 | 10 | evals/compare.py | evals |
| 13 | 10 | evals/calibration.py | evals |
| 14 | 9 | src/npc_engine/config/llm_config.yaml | src |
| 15 | 9 | evals/__main__.py | evals |
| 16 | 8 | project-harness/HUMAN_TASKS.md | harness |
| 17 | 8 | evals/run_config.py | evals |
| 18 | 8 | evals/engine_adapter.py | evals |
| 19 | 8 | evals/calibration_records.py | evals |
| 20 | 6 | tests/unit/scripts/test_run_eval_harness.py | tests |
| 21 | 6 | tests/unit/evals/test_compare.py | tests |
| 22 | 6 | tests/unit/engines/test_eval_summary.py | tests |
| 23 | 6 | scripts/Run-EvalHarness.ps1 | scripts |
| 24 | 6 | scripts/evals_baseline.txt | scripts |
| 25 | 6 | evals/label_import.py | evals |

Body attribution, last 200 (file-touches, not commits): **evals 392, tests 321, harness 289, src 172,
scripts 50, root 40, docs 22, demo 8**.

**Last 500** (top 25):

| # | Touches | File | Body |
|---|---|---|---|
| 1 | 162 | project-harness/ROADMAP.md | harness |
| 2 | 93 | project-harness/ISSUES.md | harness |
| 3 | 90 | project-harness/DECISIONS.md | harness |
| 4 | 51 | project-harness/review-fixes/INDEX.md | harness |
| 5 | 43 | project-harness/review-fixes/FIX-SEV-24.md | harness |
| 6 | 41 | project-harness/archive/ISSUES_RESOLVED.md | harness |
| 7 | 41 | Makefile | root |
| 8 | 34 | scripts/rules_baseline.txt | scripts |
| 9 | 30 | project-harness/DEMO_BUILD_LOOP.md | harness |
| 10 | 27 | src/npc_engine/graph/repositories/__init__.py | src |
| 11 | 26 | src/npc_engine/retrieval/context/context_builder.py | src |
| 12 | 26 | src/npc_engine/engines/ports/__init__.py | src |
| 13 | 26 | src/npc_engine/api/dependencies_engines.py | src |
| 14 | 26 | project-harness/human_verification.md | harness |
| 15 | 19 | tests/unit/harness/test_roadmap_cursor.py | tests |
| 16 | 16 | src/npc_engine/config.py | src |
| 17 | 15 | project-harness/soft_review.md | harness |
| 18 | 13 | src/npc_engine/engines/dialogue/dialogue_handler.py | src |
| 19 | 13 | project-harness/REVIEW_FINDINGS.md | harness |
| 20 | 12 | src/npc_engine/scheduler/tick_scheduler.py | src |
| 21 | 12 | src/npc_engine/graph/repositories/quest_generation_repository.py | src |
| 22 | 11 | src/npc_engine/api/dependencies.py | src |
| 23 | 11 | project-harness/Run-OvernightCombined.ps1 | harness |
| 24 | 11 | evals/summary.py | evals |
| 25 | 11 | evals/calibration.py | evals |

Body attribution, last 500: **src 1563, tests 1162, harness 783, evals 456, demo 344, scripts 106,
root 55, docs 33, dotclaude 6**.

Note the inversion: in the last 500 commits `src` dominates churn (1563); in the last 200 `evals`
overtakes it (392 vs 172) and `src` churn collapses — the project's recent activity has shifted almost
entirely off product code and onto the eval harness plus its own process files.

### 2. Fix-of-fix chains

Definition used: a commit whose subject starts `fix` that touches a file also touched by an earlier
`fix`-subject commit within the preceding 5 commits (linear history order, `git log --reverse`).

- All files (incl. harness docs): **77 chain commits** out of 161 total `fix`-subject commits.
  Worst 5 files: `project-harness/review-fixes/INDEX.md` (91 shared-file hits), `REVIEW_FINDINGS.md` (67),
  `ISSUES.md` (29), `Run-OvernightCombined.ps1` (20), `DECISIONS.md` (19). These are almost entirely the
  review-remediation bookkeeping docs being touched by every fix commit in a SEV-batch, not code churn.
- **Code-only** (`src/`, `tests/`, `evals/`, `demo_game/`, `scripts/`, `seeds/`): **41 chain commits**.
  Worst 5 code files: `src/npc_engine/config.py` (7), `scripts/rules_baseline.txt` (6),
  `tests/unit/scripts/test_run_eval_harness.py` (4), `scripts/Run-EvalHarness.ps1` (4),
  `demo_game/game_controller.py` (3).

Most code-only chains are same-day SEV-remediation batches (e.g. `9ee2e73` SEV-14 → `e72cf0be` SEV-05 →
`0f83453c` SEV-06, all same session) rather than a fix regressing another fix. `config.py` is the
exception worth tracking — see CR-L10-01.

### 3. Velocity by ISO week

`git log --format=%ad --date=format:%G-W%V | sort | uniq -c`

```
     14 2026-W16
      1 2026-W17
      1 2026-W18
     17 2026-W19
     26 2026-W20
     27 2026-W21
     32 2026-W22
    164 2026-W23
    261 2026-W24
    131 2026-W25
     60 2026-W26
      9 2026-W31
     78 2026-W32
     65 2026-W33
     21 2026-W34
     60 2026-W35
```

**W24 = 261, verified real.** All 261 commits fall within calendar dates 2026-06-09 → 2026-06-14 (6 days).
Several land in the same clock-minute (e.g. 4 commits at `2026-06-09 11:42`), which is consistent with an
unattended commit loop, not a rounding artifact.

**W27–W30 gap, verified real.** Last commit before the gap: `1e1f20f` on 2026-06-24 (W26). First commit
after: `f678dd4` on 2026-07-31 (W31) — a 37-day span with zero commits. No entry in ROADMAP.md or
DECISIONS.md explains the pause; work resumes in W31 directly on the eval-harness track (`DEC-146..150`).

### 4. Subsystems that have never stabilised

Metric: a file in the top decile of touch-count in **both** the last-200 window (top 62 of 617 unique
files) and the last-500 window (top 232 of 2324 unique files). Intersection = 62 files; filtering out
harness markdown and test files, the surviving product code is:

- **The entire `evals/` package**: `__main__.py`, `adjudicate.py`, `calibration.py`,
  `calibration_records.py`, `compare.py`, `dashboard/app.py`, `engine_adapter.py`, `eval_records.py`,
  `generate_runner.py`, `judge_runner.py`, `label_export.py`, `label_import.py`, `label_merge.py`,
  `matchers.py`, `paired_stats.py`, `retrieval_runner.py`, `run_config.py`, `runner.py`, `summary.py`,
  `trend_store.py` — 20 of roughly 25 top-level eval modules.
- **The prompt-window/config subsystem**: `src/npc_engine/config.py`, `src/npc_engine/config_prompt_window.py`,
  `src/npc_engine/config/llm_config.yaml`.
- **The context-retrieval subsystem**: `src/npc_engine/retrieval/context/context_builder.py`,
  `src/npc_engine/retrieval/embedding/corpus.py`.
- **The dialogue engine**: `src/npc_engine/engines/dialogue/dialogue_handler.py`.

These four areas are named because they are the only non-harness, non-test code that never drops out of
the top 10% churn band across either window — see CR-L10-01..04.

### 5. Harness-vs-product churn ratio (last 200 commits)

Commits touching **only** `project-harness/`, `docs/`, or `.claude/` (zero code files):

```
total commits (last 200): 200
harness/docs/.claude-only commits: 60
ratio: 0.30
```

**30% of the last 200 commits touch no code at all.**

### 6. Author/session pattern and commit-type ratio

- **Single author** for all 967 commits: `Lohann Colle <lohanncolle2022@gmail.com>`.
- Commits land on only **65 distinct calendar days** across a 135-day span (2026-04-15 → 2026-08-27).
  Busiest single day: **107 commits on 2026-06-12**; next busiest 68 (06-11), 61 (06-04), 49 (06-23).
- 967 commits occupy only 839 distinct clock-minutes — ~13% of commits share a minute with another
  commit, corroborating burst/loop-driven authorship rather than steady manual pacing.
- Conventional-commit type counts, full history: `feat 355, docs 206, fix 159, chore 82, refactor 68,
  test 22` (plus ~40 non-conforming subjects). **docs+chore = 288 vs feat+fix = 514** → ratio 0.56:1
  (36% process-labeled vs 64% product-labeled by commit-type prefix — healthier than the raw file-touch
  ratio in measurement 5, because one `docs(harness)` commit often bundles a large ROADMAP/ISSUES rewrite).

---

## Findings

### [CR-L10-01] The token-budget subsystem was silently violating its own core contract for ~2.5 months, and the fix that closed it still relies on a hardcoded ceiling

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect (historical, closed at HEAD) / Risk (forward, still open)
- **Evidence:** `git show d2ffd97` (2026-08-26, `fix(config): the model was seeing 2,050 tokens of a 7,100-token prompt`): "Logging it showed prompt_eval_count = 2050 on all seven dialogue turns... the real prompt is ~7,100 tokens and the model had been seeing under 30% of it." One day later, `git show 96d83eb` (2026-08-27, `fix(config): the shipped window derives a budget smaller than the context it assembles`) states the first fix's own regression test, `TestShippedDefaultsAreCoherent` (`tests/unit/config/test_config_prompt_window.py:65`), "is satisfied by construction at EVERY window size" because the budget is derived, not measured — "the configuration that ships would have dropped tier-A items on mira_innkeeper, aldric_merchant and lira_fence." `tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py:45` now hardcodes `MEASURED_ROSTER_CEILING_TOKENS = 1151` from one probe run. This directly contradicts CLAUDE.md's "Token budget enforced (strict)" rule, which requires `context_builder.py` to raise `TokenBudgetExceededError` rather than silently truncate — none was raised; the truncation happened one layer down, at the Ollama `num_ctx` clamp, invisible to the token-budget check entirely.
- **Cost of inaction:** The new gate pins today's measured ceiling as a literal constant against a system (`context_builder.py`, prompt templates, tier weights) that churns constantly (measurement 4). The next feature that adds an item to tier A/B/C without re-running `make probe-ceiling` reproduces exactly this failure mode with no compile-time or CI signal, because the "coherence" check still only verifies internal arithmetic, not real usage.
- **Fix sketch:** Turn the probe into a CI step that re-measures the roster ceiling and fails if the shipped budget doesn't clear it by a margin, instead of trusting a constant re-entered by hand each time someone notices the gap.
- **Effort:** M
- **Blast radius:** `src/npc_engine/config.py`, `config_prompt_window.py`, `context_builder.py`, `make eval-*` gates, ISSUE-209 and ISSUE-225 (both still open in `project-harness/ISSUES.md:1408,1738`).

### [CR-L10-02] context_builder.py's own file-size justification comment understates the file by 78% and is unmaintained

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Evidence:** `src/npc_engine/retrieval/context/context_builder.py:9` reads "NOTE: This file exceeds the 300-line limit (currently ~448 lines)." `git blame -L 9,9` dates that line to commit `60e7a7e3`, 2026-06-17. `wc -l src/npc_engine/retrieval/context/context_builder.py` → 799 lines today, +351 lines (+78%) since the comment was written. `git log --oneline --since=2026-06-17 -- src/npc_engine/retrieval/context/context_builder.py` lists 27 commits touching the file since, including at least 7 `fix(retrieval):` commits (tier-A/B/C budget and starvation bugs).
- **Cost of inaction:** The comment is the only pointer to the DEC-016 exception; anyone trusting it underestimates the file's real size by nearly 2x and has no signal that the exception's premise ("~464 lines, one cohesive async pipeline") has been stretched across three more feature waves (A/B retrieval arms, second-hop events, quest state).
- **Fix sketch:** Regenerate the line count in the docstring (or replace the literal number with "see `wc -l`") and add a DEC-016 follow-up entry recording the current size and whether the split-avoidance rationale still holds at 799 lines.
- **Effort:** S
- **Blast radius:** Documentation only; no behavior change.

### [CR-L10-03] evals/calibration.py breached its own DEC-169 split trigger with no follow-up decision

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Evidence:** `project-harness/DECISIONS.md:3078-3087` (DEC-169, dated 2026-08-12): "Future trigger: Split into `evals/bootstrap.py` + `evals/calibration.py` if the file grows beyond 800 lines." `wc -l evals/calibration.py` → 875 lines today. `git log --oneline --since=2026-08-12 -- evals/calibration.py` shows 2 further commits (`e2b1e3f`, `049721e`) added after the decision, with no corresponding DECISIONS.md entry addressing the crossed threshold.
- **Cost of inaction:** The file's own docstring (line 11-14) still claims the pre-trigger rationale ("all functions form a single coherent calibration pipeline"); the self-imposed governance check exists but nothing enforces it, so the pattern from CR-L10-02 repeats — a size exception silently outlives its own stated boundary.
- **Fix sketch:** Either execute the DEC-169 split now (extract bootstrap internals into `evals/bootstrap.py`) or write a DEC-169 follow-up explicitly re-raising the trigger to a new number with a stated reason.
- **Effort:** S (decision) / M (actual split)
- **Blast radius:** `evals/calibration.py`, `tests/unit/evals/test_calibration.py`, `make eval-calibrate`.

### [CR-L10-04] The evals/ package and the config/context-retrieval subsystem never leave the top-churn decile

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Measurement 4 above — the intersection of top-decile files in the last-200 window (top 62/617) and last-500 window (top 232/2324) is dominated by 20 of `evals/`'s ~25 top-level modules plus `config.py`, `config_prompt_window.py`, `llm_config.yaml`, `context_builder.py`, `retrieval/embedding/corpus.py`, and `dialogue_handler.py`. No other product subsystem (graph writers, mutation, world, scheduler) appears in this intersection at all.
- **Cost of inaction:** These are exactly the files CR-L10-01 through 03 document as having shipped a defect (config/context) or crossed a governance line (calibration.py) — the churn-persistence metric is not incidental, it is the leading indicator that flagged both real problems before they were found by other means. Continued churn here without a stabilization checkpoint (freeze + regression suite + explicit "done" criterion) means the next silent-truncation-class bug in this area is a when, not an if.
- **Fix sketch:** After the current EVAL-P25..P31 arm work lands, declare a stabilization window for `evals/` core modules and the prompt-window subsystem: no new features, only the measured-ceiling CI gate (CR-L10-01) and any DEC-169-triggered split (CR-L10-03), then re-check this same top-decile metric next review to see if it actually drops out.
- **Effort:** L
- **Blast radius:** Eval harness release cadence (`EVAL-P*` roadmap items), any in-flight A/B context-arm work on this branch.

### [CR-L10-05] config.py is the single most fix-magnet file in the codebase

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Evidence:** Measurement 2 — `src/npc_engine/config.py` leads the code-only fix-of-fix ranking with 7 shared-file hits. `git log --reverse --format='%ad|%h|%s' -- src/npc_engine/config.py` shows 51 total commits, spanning `SEV-14` (mypy), `SEV-27` (structured-output retry), `SEV-35` (delta_ticks bound unification), `SEV-19/20/21` (security cluster), and the two Aug 26-27 token-budget fixes (CR-L10-01) — five independent review/fix waves converging on one file across 4 months.
- **Cost of inaction:** `config.py` is 504 lines (68% over the 300-line hard limit) with no DECISIONS.md exception recorded (unlike `context_builder.py`'s DEC-016 or `evals/calibration.py`'s DEC-169) — it accreted past the limit without ever triggering the documented exception process, so there's no record anyone made a deliberate call to keep it as one file.
- **Fix sketch:** Either split by concern (LLM/runtime settings vs. security/bound constants vs. derived-budget logic) or add the missing DECISIONS.md exception entry so future churn is at least a tracked decision rather than an omission.
- **Effort:** M
- **Blast radius:** Every module that imports `Settings` (broad — `api/`, `engines/`, `retrieval/`, `graph/` all read config).

### [CR-L10-06] 30% of the current commit stream is pure process bookkeeping, and the top-3 all-time churned files are all harness markdown

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process / Waste
- **Evidence:** Measurement 5: 60/200 (30%) of the most recent commits touch only `project-harness/`, `docs/`, or `.claude/`. Measurement 1: `ROADMAP.md` (162 touches/500), `ISSUES.md` (93), `DECISIONS.md` (90) are the three most-touched files in the repo's history, ahead of every source file.
- **Cost of inaction:** Not itself harmful — CLAUDE.md mandates this bookkeeping — but it means git-blame/churn tooling pointed at this repo without body filtering will misidentify the harness as the highest-risk subsystem, burying the real signal (CR-L10-04's evals/config cluster) under expected process noise.
- **Fix sketch:** Any future churn dashboard or `make check-layers`-style tool should exclude `project-harness/`, `docs/`, `.claude/` by default, matching the body split already used in this report.
- **Effort:** S
- **Blast radius:** Tooling only, no code.

### [CR-L10-07] Commit velocity is loop-driven, not human-paced, which is the structural cause of the fix-of-fix pattern

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** Measurement 6/3: single author, 967 commits across only 65 distinct calendar days; 261 commits inside ISO week 2026-W24 (6 calendar days, verified by date-filtering the log — see measurement 3); 107 commits on one day (2026-06-12); ~13% of commits share a clock-minute with another commit. `project-harness/Run-OvernightCombined.ps1` and the `/expand-linear-next` skill in this repo's own `.claude/` config exist specifically to run unattended overnight loops.
- **Cost of inaction:** At this velocity, a single review pass cannot precede every commit — which is the exact precondition for CR-L10-01's "fix that immediately needed a second fix" and for the SEV-cluster batches in measurement 2. This is a structural explanation, not a new defect.
- **Fix sketch:** No action item beyond what CR-L10-04 already proposes (a stabilization checkpoint) — flagged here so the fix-of-fix numbers in this report aren't read as a code-quality signal in isolation.
- **Effort:** N/A (context)
- **Blast radius:** N/A

### [CR-L10-08] A 37-day commit gap (W27-W30) is undocumented in ROADMAP.md/DECISIONS.md

- **Severity:** LOW
- **Confidence:** Suspected
- **Kind:** Process
- **Evidence:** Measurement 3 — last commit before gap `1e1f20f` (2026-06-24), first commit after `f678dd4` (2026-07-31), verified by direct date inspection of the log. No ROADMAP.md/DECISIONS.md entry found (grep for the date range) explaining the pause or recording state-on-pause.
- **Cost of inaction:** Unconfirmed — the resumed work (EVAL harness track, DEC-146..150) appears coherent with what was in flight before the gap, so there's no direct evidence of lost context. Flagged only because a project whose CLAUDE.md mandates exhaustive DECISIONS.md logging has no entry for its own longest pause.
- **Fix sketch:** If gaps like this recur, a one-line ROADMAP.md/DECISIONS.md note on resume ("picking up after N days, last state was X") would remove the need to reconstruct context from raw git log next time.
- **Effort:** S
- **Blast radius:** None (documentation only).

---

## Severity summary

| Severity | Count | IDs |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 2 | CR-L10-01, CR-L10-04 |
| MEDIUM | 3 | CR-L10-02, CR-L10-03, CR-L10-05 |
| LOW | 3 | CR-L10-06, CR-L10-07, CR-L10-08 |

---

## L7 — Backlog health

# CR-L07 — Backlog health

Scope: `project-harness/ISSUES.md`, `DECISIONS.md`, `ROADMAP.md`, `HUMAN_TASKS.md`,
`SKILLS_QUEUE.md`, `PATTERNS.md`, `archive/ISSUES_RESOLVED.md`, and the other planning docs.
Repo at HEAD `d46ae42`, branch `eval-ab-context-arms`, 2026-08-27.

## Required measurements

### 1. Open-issue age distribution

Extracted every `**Found:**` date from `project-harness/ISSUES.md` (67 real entries — the raw
`grep -c "^## ISSUE-"` gives 68, but one match is the literal `## ISSUE-NNN: <short title>`
template line in the "how to log an issue" section, not a real issue).

```
n = 67, median age = 10 days, max age = 79 days, min age = 0 days
By month: 2026-06 → 4 issues, 2026-08 → 63 issues
```

| Age bucket | Count |
|---|---:|
| 0–7 days | 31 |
| 8–14 days | 14 |
| 15–30 days | 12 |
| 31–60 days | 5 |
| 61–90 days | 5 |

The backlog is heavily skewed young (median 10 days) — consistent with a burst of review
activity in the last two weeks, not with a long-neglected queue. The five 61–90-day outliers
are `ISSUE-083` (79d, P3, actively tracked with two dated updates — legitimately deferred, not
neglected), `ISSUE-092` (79d, P3, explicitly deferred to a future engine phase), `ISSUE-122`
(63d, P2 — see CR-L07-04, this one is neglected because it's wrong, not because it's hard),
`ISSUE-085` (79d, P3, `datetime.utcnow()` deprecation), and the `[WONTFIX]` `ISSUE-051` (86d,
never archived — see CR-L07-08).

### 2. P1 severity-inflation check

`grep -c '\*\*Severity:\*\* P1'` → **8**, but one hit is again the `ISSUE-NNN` template. **7 real
open P1s.** (The review brief's stated "~23 P1" does not match the file — see note below.)

| ID | Blocking? | Justification |
|---|---|---|
| ISSUE-155 | **Yes** | `verdict_sources.load_unified_rows` dedup bug corrupts every headline number computed via `summarize_from_dir`, still live in code. |
| ISSUE-156 | **Yes** | `_bucket_expectation` undercounts hallucination failures in the published headline metric, still live. |
| ISSUE-141 | **Yes** | `refusal_judge` chance-level agreement is cited as still-unresolved by the later `ISSUE-184` (2026-08-18, kappa 0.23/0.28) — invalidates any gate that trusts that judge. |
| ISSUE-176 | **Yes** | `check_conservation.py` still hardcodes the stale `k3_73e6c36` gen-dir as of this review (confirmed at `scripts/check_conservation.py:34-36`) — the `make check-conservation` gate audits nothing current. |
| ISSUE-129 | **Soft** | Judge-disagreement is a measurement-validity finding, not a runtime break; nothing currently gates on it. |
| ISSUE-171 | **No** | Pure governance/process gap (loop-queue moves lack a mechanical DEC-entry check) — no runtime or build breakage today. |
| ISSUE-145 | **No — stale** | Root cause fully diagnosed and fixed under `ISSUE-163`/`ISSUE-197` (both `[FIXED]`, archived); the fix is live in code (`context_score_extractors.py:228`, `NPC_SELF_STATE_KEYS`). See CR-L07-01. |

**Ratio: 4/7 (57%) currently block something concrete; 3/7 do not** (1 soft/credibility-only, 1
pure-process, 1 stale/already-fixed). See CR-L07-01, CR-L07-05.

### 3. DECs superseded / contradicted / never implemented (sampled)

**Sampling method:** stratified every-10th unreferenced-in-code DEC ID (n=12, IDs
002/013/026/045/062/074/086/113/132/151/173/200) out of 113 DEC numbers never grepped in
`src/`, `evals/`, `tests/`, `scripts/`, `demo_game/`, `seeds/`, `e2e/` — each checked against
current code.

| DEC | Verdict | Evidence |
|---|---|---|
| DEC-074 | **Stale, confirmed** | Waived `game_window.py` at 350 lines with "No further growth ... without a real extraction." File (now `demo_game/ui/layout/game_window.py`) is **925 lines** (2.6×) — verified with `wc -l`. No later DEC re-authorizes this. |
| DEC-086 | **Stale, confirmed** | Waived `quest_lifecycle_engine.py` at 305 lines, "Next editor must split before adding anything new." File (`src/npc_engine/engines/quest/quest_lifecycle_engine.py`) is **383 lines** — verified with `wc -l`. No follow-up DEC. |
| DEC-002 | Likely stale | `military_engine.py:34` `run_tick` now calls `resolve_battles`/`process_resource_yield`, contradicting DEC-002's "stub" description; no DEC documents the replacement. |
| DEC-132 | Likely never implemented | Decision named Kùzu evaluation + per-stage latency instrumentation as gated next steps; no `kuzu` import anywhere under `src/`, no dialogue-turn latency breakdown found. |
| DEC-013, 026, 045, 062, 113, 151, 173, 200 | Confirmed still accurate | Each checked against its named file/behavior and matches current code (e.g. DEC-113 → `pyproject.toml:77` `strict = true`; DEC-151 → all 10 named loop scripts exist). |

At n=12, 4/12 (33%) sampled DECs are stale or unimplemented. Extrapolated (not measured) over
113 unreferenced DECs this would be a meaningful fraction, but the true rate is unverified beyond
this sample — reported as **Likely**, not Confirmed, at the aggregate level.

### 4. Roadmap burn rate

Checked/unchecked (`- [x]` / `- [ ]`) line counts from `project-harness/ROADMAP.md` at the git
commit in effect at each weekly boundary (`git show <sha>:project-harness/ROADMAP.md`):

| Date | Commit | Checked | Unchecked | Total |
|---|---|---:|---:|---:|
| 2026-07-02 | d0f473d | 119 | 28 | 147 |
| 2026-07-09 | d0f473d | 119 | 28 | 147 |
| 2026-07-16 | d0f473d | 119 | 28 | 147 |
| 2026-07-23 | d0f473d | 119 | 28 | 147 |
| 2026-07-30 | d0f473d | 119 | 28 | 147 |
| 2026-08-06 | 427dd43 | 134 | 35 | 169 |
| 2026-08-13 | efbe7ce | 196 | 44 | 240 |
| 2026-08-20 | bdaa55b | 210 | 40 | 250 |
| 2026-08-27 | b9717ef | 210 | 65 | 275 |

Four flat weeks (07-02→07-30, zero roadmap commits), then a burst. **Arithmetic:** over the
active 8-week window, checked items grew 119→210 (+91, ≈11.4/week average) but total items grew
147→275 (+128) — the backlog is growing 40% faster than it's being cleared. The most recent week
(08-20→08-27) shipped **zero** newly-checked items while unchecked grew by 25 (+63%). An ETA
computed from the 8-week average (65 unchecked ÷ 11.4/week ≈ **5.7 weeks**) assumes no further
scope growth, which the last week's data directly contradicts — **no honest single-number ETA is
supportable**; the trend is currently diverging, not converging.

### 5. Counts

| Item | Count |
|---|---:|
| Open issues (real, excl. template) | 67 |
| — of which P1 | 7 (raw grep: 8, minus 1 template) |
| — of which P2 | 32 |
| — of which P3 | 30 |
| `[WONTFIX]` left un-archived in ISSUES.md | 2 (`ISSUE-051`, `ISSUE-138`) |
| Resolved-archive issues (`[FIXED]`) | 155 |
| Duplicate IDs within the archive itself | 2 (`ISSUE-035`, `ISSUE-056`, each used for two unrelated fixes) |
| DECISIONS.md `## DEC-` headings | 219 |
| — unique DEC numbers | 214 (5 numbers reused: 051, 052, 058, 073, 116 — 116 is an intentional "outcome" follow-up, the other 4 are true collisions) |
| DEC IDs referenced anywhere in `src/evals/tests/scripts/demo_game/seeds/e2e` | 101 unique (47%) |
| DEC IDs never referenced outside `project-harness/` | 113 unique (53%) |
| ROADMAP.md checked / unchecked | 210 / 65 (275 total) |

### 6. Duplicate / near-duplicate issues

- **`ISSUE-145` vs `ISSUE-163`** — true duplicate-by-supersession: `ISSUE-163` was opened
  "verifying the `ISSUE-145` fix end to end," found the real root cause, and was `[FIXED]`.
  `ISSUE-145` was never closed or cross-referenced. See CR-L07-01.
- **`ISSUE-171` / `ISSUE-173`** — same family (mechanical enforcement of process/queue
  discipline gaps), filed on the same day, not literal duplicates but overlapping remediation.
- **`ISSUE-219`/`ISSUE-220`/`ISSUE-221`/`ISSUE-222`** and **`ISSUE-224`/`ISSUE-225`** — clusters
  of related-but-distinct retrieval-probe defects found on the same day (P9, P10 sessions); not
  duplicates, but indicate one investigation session reliably produces 3-5 tickets, which is
  useful context for the burn-rate divergence in §4.
- **ID collisions** (`DEC-051/052/058/073`, `ISSUE-035/056` in archive) are a structural
  duplication problem distinct from content duplication — see CR-L07-02.

---

## Findings

### [CR-L07-01] `ISSUE-145` is a stale P1 whose root cause was already fixed under different IDs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect (in the backlog process, not the engine)
- **Evidence:** `ISSUE-145` (`project-harness/ISSUES.md`, found 2026-08-10, still P1 "blocking...
  FOR HAND REVIEW") describes the exact defect that `[FIXED] ISSUE-163`
  (`project-harness/archive/ISSUES_RESOLVED.md:2697`) explicitly opened to verify ("Found:
  2026-08-14, during RET-P0 (verifying the ISSUE-145 fix end to end)") and root-caused: NPC
  self-state items (`beliefs`, `memories`, `top_need`) were scored at the graph horizon by
  `_infer_proximity_hops`, losing the tier-A budget. That fix is live: `src/npc_engine/retrieval/context/context_score_extractors.py:228`
  now special-cases `NPC_SELF_STATE_KEYS` with `SELF_STATE_PROXIMITY_HOPS`. The companion budget
  cause was separately `[FIXED]` as `ISSUE-197`. `ISSUE-145` itself carries no update note, no
  `[FIXED]` marker, and no cross-reference to either fix.
- **Cost of inaction:** Anyone triaging "open P1s" (7 total) counts a defect that is
  substantially resolved, inflates the perceived blocking-issue count by ~14%, and risks
  duplicate investigation of an already-closed root cause.
- **Fix sketch:** Re-verify `ISSUE-145`'s original repro (`GET /v1/admin/debug/retrieval`) against
  current code; if it now returns non-empty, mark `[FIXED] ISSUE-145 (superseded by ISSUE-163/197)`
  and move it to the archive per the CLAUDE.md issue-lifecycle rule.
- **Effort:** S (<2h)
- **Blast radius:** None — pure bookkeeping; does not touch running code.

### [CR-L07-02] `DECISIONS.md` and the archive reuse IDs, breaking the citation ledger

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Four DEC numbers head two unrelated decisions each: `DEC-051`
  (`DECISIONS.md:543` "S10.3 correct rumor marks..." vs `DECISIONS.md:1011` "run_scenes.py
  accepted over 300-line hard limit"), `DEC-052` (`:553` vs `:1018`), `DEC-058` (`:1036` vs
  `:1069`), `DEC-073` (`:457` vs `:1150`). The archive has the same pattern: `ISSUE-035`
  (`archive/ISSUES_RESOLVED.md:280` vs `:749`) and `ISSUE-056` (`:883` vs `:1197`) each label two
  unrelated fixes. `DEC-NNN` is cited 352 times across `src/evals/tests/scripts/...` — any citation
  of one of the 4 collided IDs is now ambiguous to a reader without opening `DECISIONS.md`.
- **Cost of inaction:** A future session citing e.g. "per DEC-073" in a commit message or code
  comment is unverifiable without manual disambiguation; this compounds every time the file grows.
- **Fix sketch:** Renumber the second occurrence of each collided ID to the next free number,
  add a one-line "renumbered from DEC-NNN, see DEC-MMM" pointer at the old anchor, and grep for
  any in-code reference to the renumbered ID to update it.
- **Effort:** S (<2h)
- **Blast radius:** Any code comment or doc citing the renumbered ID (grep first — none currently
  reference `DEC-051`/`052`/`058`/`073` per the code-reference scan in §5, so blast radius is
  effectively zero for this repo today).

### [CR-L07-03] Two file-size waivers in `DECISIONS.md` are silently violated, live on main

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `DEC-074` (`DECISIONS.md`) waived `game_window.py` at 350 lines with "No further
  growth should be allowed without a real extraction." Current file
  `demo_game/ui/layout/game_window.py` is **925 lines** (`wc -l`, verified) — 2.6× the waiver, no
  follow-up DEC. `DEC-086` waived `quest_lifecycle_engine.py` at 305 lines, "Next editor must
  split before adding anything new." Current `src/npc_engine/engines/quest/quest_lifecycle_engine.py`
  is **383 lines** (`wc -l`, verified) — 25% over, no follow-up DEC. Neither file's module
  docstring carries a justifying comment referencing the current size, as CLAUDE.md's own file-limit
  rule requires ("write a justifying comment at the top... and add an entry to DECISIONS.md").
- **Cost of inaction:** The 300-line hard limit is stated in `project-harness/CLAUDE.md` as
  "not a suggestion... violating it is a bug" — these two files are currently in that state with
  no paper trail, so the rule is unenforced exactly where it says it is strictest.
- **Fix sketch:** Either split `game_window.py` (a `RenderLayer`/poller-registry extraction is
  already named as the intended relief valve in `DEC-074`) or write the new waiving DEC
  acknowledging the current size; same for `quest_lifecycle_engine.py`.
- **Effort:** M (<1d) for the DEC-only path; L for an actual split.
- **Blast radius:** `game_window.py` is the demo's central event-loop coordinator (imported by
  `demo_game.__main__`); a split touches all poller wiring. `quest_lifecycle_engine.py` split
  touches the quest engine's public surface.

### [CR-L07-04] `ISSUE-122` prescribes a fix that was already present when the issue was filed

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect (in the ticket, not the code)
- **Evidence:** `ISSUE-122` (found 2026-06-25) claims `docker-compose.yml`'s `app` service "has
  no restart policy" and prescribes adding `restart: on-failure` plus
  `depends_on: neo4j: condition: service_healthy`. `git show ae3dc78:docker-compose.yml` — the
  commit in effect on the issue's own found-date — already contains both:
  `restart: on-failure:5` and `depends_on: { neo4j: { condition: service_healthy } }`. Both are
  still present in the current `docker-compose.yml:78-80`. The line has been present continuously
  since it was first added at `4dc797a` (2026-05-05), a month before the issue was filed.
- **Cost of inaction:** The ticket has sat open 63 days; anyone who picks it up to "fix" it will
  find nothing to do and waste time re-diagnosing the real cause (most likely the stale
  non-bind-mounted app image noted separately in session memory) instead of the compose file.
- **Fix sketch:** Re-diagnose against the actual failure mode (stale image / build-not-rebuilt),
  correct or close `ISSUE-122`, and re-file against the real cause if still reproducible.
- **Effort:** S (<2h)
- **Blast radius:** None — documentation-only correction.

### [CR-L07-05] Roadmap completion trend is diverging, not converging

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** See §4 table. Checked items: 119→210 over 8 weeks (+91). Total items (checked +
  unchecked): 147→275 (+128). The most recent week added 25 new unchecked items and 0 new checked
  ones. A backlog that grows 40% faster than it clears, and just posted a zero-completion week,
  cannot support a single honest "N weeks to done" estimate.
- **Cost of inaction:** Any roadmap status reported upward (e.g. "5.7 weeks to zero") using the
  naive average will be wrong in the direction of false confidence, exactly when the trend just
  inverted.
- **Fix sketch:** Report burn rate as a range bracketing both the historical average and the
  most recent week (roughly 0–11/week), and flag scope growth explicitly in `ROADMAP.md`'s own
  status header rather than only tracking checked/unchecked counts.
- **Effort:** S (<2h)
- **Blast radius:** None — reporting change only.

### [CR-L07-06] Over half of DECISIONS.md is unreferenced outside project-harness, and a sample shows real drift

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Debt
- **Evidence:** 113 of 214 unique DEC numbers (53%) never appear in `src/`, `evals/`, `tests/`,
  `scripts/`, `demo_game/`, `seeds/`, or `e2e/` (grep, see §5). A stratified n=12 sample of these
  unreferenced IDs found 2 confirmed-stale waivers (CR-L07-03) and 2 further likely-stale/
  unimplemented decisions (`DEC-002`, `DEC-132`) — a 33% stale rate in the sample. Not all 113 are
  expected to have code references (many are pure process/meta decisions), so the 53% figure is
  not itself a defect count, but the sampled stale rate suggests the file needs a re-validation
  pass, not just growth.
- **Cost of inaction:** DECISIONS.md is meant to let "future maintainers judge edge cases without
  re-deriving the rationale" (its own header) — a maintainer trusting a stale entry will make the
  wrong call.
- **Fix sketch:** A single pass re-verifying line-count waivers (`DEC-*.*-line*` entries are
  mechanically checkable with `wc -l`) would catch the cheapest class of drift; extend the n=12
  sample before trusting the 53% figure as a defect rate.
- **Effort:** M (<1d) for the mechanical line-count pass alone.
- **Blast radius:** None — audit only.

### [CR-L07-07] Three scripts share one hardcoded stale corpus default; only one is tracked

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `ISSUE-176` tracks `scripts/check_conservation.py:34-36`'s hardcoded
  `_DEFAULT_GEN_DIR = .../k3_73e6c36`. The identical pattern exists, untracked, in
  `scripts/check_dead_keywords.py:35` and `scripts/check_label_survival.py:27` (both hardcode
  the same `k3_73e6c36` path as a default gen-dir). `ISSUE-186` independently documents that
  `k3_73e6c36`'s own metadata (`harness_version`, `seed`) is null and structurally unfit as a
  baseline — three separate `make check` gates default to auditing it.
- **Cost of inaction:** Fixing only `ISSUE-176`'s named file leaves two gates
  (`check-dead-keywords`, `check-label-survival`) silently auditing the same stale, metadata-null
  corpus after any regeneration.
- **Fix sketch:** Factor the default gen-dir resolution into one shared helper (e.g. "latest
  gen-dir under `evals/generations/`") and have all three scripts call it instead of each
  hardcoding the literal.
- **Effort:** S (<2h)
- **Blast radius:** Three `make check` gate scripts; low risk, mechanical.

### [CR-L07-08] `SKILLS_QUEUE.md` is dead for ~90 days while still normatively referenced

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git log -1 --format=%ad -- project-harness/SKILLS_QUEUE.md` → `2026-05-29`.
  `project-harness/CLAUDE.md:306` still tells contributors that undecided questions "go in
  `DECISIONS.md` or `SKILLS_QUEUE.md`." In the same ~90-day window, `DECISIONS.md` grew by over
  100 entries and `PATTERNS.md` was touched as recently as 2026-08-22. No `DECISIONS.md` entry
  documents deprecating or superseding `SKILLS_QUEUE.md` (`grep -in SKILLS_QUEUE
  project-harness/DECISIONS.md` → no hits).
- **Cost of inaction:** Low — but the file misleads a new contributor into thinking it's an
  active queue, and its 13 recorded skill-opportunity entries (last dated 2026-05-27) are aging
  out of relevance unreviewed.
- **Fix sketch:** Either resume using it, or add one `DECISIONS.md` entry retiring it and update
  the `CLAUDE.md:306` pointer.
- **Effort:** S (<2h)
- **Blast radius:** None.

---

## Other planning docs — live vs abandoned (by last git touch)

| File | Last touch | Status |
|---|---|---|
| `EVAL_STRATEGY.md` | 2026-05-28 | Abandoned (91 days) |
| `SKILLS_QUEUE.md` | 2026-05-29 | Abandoned (90 days) — see CR-L07-08 |
| `HARNESS_GATES.md` | 2026-06-03 | Abandoned (85 days) |
| `BATCH5_RESPONSE_MODEL.md` | 2026-06-04 | Abandoned (84 days) |
| `eval_roadmap_session_prompt.md`, `UNREAL_DEFERRED.md` | 2026-07-31 | Explicitly deferred / one-shot prompt, not live |
| `OVERNIGHT_LOOP_PLAN.md` | 2026-08-01 | Likely superseded by `OVERNIGHT_LOOP.md` (2026-08-09) |
| `EVAL_P20_TO_P24_UNBLOCK_PLAN.md`, `PROMPT_P23_UNBLOCK.md` | 2026-08-15/18 | Phase-complete artifacts; roadmap has moved to `EVAL_P25_TO_P31_PLAN.md` |
| `MORNING_HANDOFF_PHASE1.md` | 2026-08-18 | Likely superseded by `MORNING_HANDOFF_COMBINED.md` (2026-08-26) |
| `HUMAN_TASKS.md`, `human_verification.md`, `soft_review.md` | 2026-08-15 | Referenced by name in `ROADMAP.md`'s HUMAN GATE mechanism; still live |
| `PATTERNS.md` | 2026-08-22 | Live |
| `MORNING_HANDOFF_COMBINED.md`, `HANDOFF_TRACK_A/B.md`, `EVAL_P25_TO_P31_PLAN.md`, `PROMPT_P25_*`, `PROMPT_P26_INTEGRATION.md`, `ISSUES.md`, `DECISIONS.md`, `ROADMAP.md` | 2026-08-26/27 | Live, current session set |

`project-harness/` itself carries **48,988 lines of Markdown across 253 tracked files** (measured
by the sibling synthesis file `project-harness/CODEBASE_REVIEW.md` at time of writing) against
68,218 Python LOC in `src/npc_engine/` — a planning-to-code ratio worth noting for whoever owns
process overhead, though sizing that tradeoff is outside this lens's scope.

**Note on the review brief's own numbers:** the brief states "~68 open, ~23 P1" — the real counts
are 67 open / **7 P1** (raw grep before excluding the template line: 68/8). The brief's P1 count
is off by more than 3×; treat any other un-verified count in review tooling with the same
skepticism applied here.

---

## L8 — Code debt

# CR-L08 — Code debt (oversized files, duplication, dead code, orphans)

Branch `eval-ab-context-arms`, HEAD `d46ae42`. Read-only review.

## Required measurements

### 1. Grandfathered rule-baseline violations

Live gate run:

```
$ python scripts/check_rules.py
check-rules: OK - no new violations (133 grandfathered).
$ python scripts/check_rules.py --evals
check-evals-rules: OK - no new violations (72 grandfathered).
```

`scripts/rules_baseline.txt` (src + demo_game, 133 rows):

| Rule | Count | Top 5 files |
|---|---|---|
| R001 file-size | 31 | `demo_game/client.py`, `demo_game/seeds/seed.py`, `demo_game/ui/layout/game_window.py`, `src/npc_engine/retrieval/context/context_builder.py`, `src/npc_engine/scheduler/tick_scheduler.py` |
| R006 fn-length | 102 | `graph/graph_writer.py` (3), `engines/quest/quest_lifecycle_engine.py` (3), `engines/llm/ollama_adapter.py` (3), `engines/interaction/trade_handler.py` (3), `engines/gossip/gossip_handler.py` (3) |

`scripts/evals_baseline.txt` (evals, 72 rows):

| Rule | Count | Top 5 files |
|---|---|---|
| R001 file-size | 7 | `evals/calibration.py`, `evals/compare.py`, `evals/summary.py`, `evals/matchers.py`, `evals/anti_hallucination_runner.py` |
| R002 print | 20 | (spread across `evals/__main__.py`, `adjudicate.py`, `arm_probe.py`, `arm_probe_report.py`, `arm_supply.py`, ≤1 each) |
| R003 swallow | 3 | `evals/__main__.py`, `evals/dashboard/app.py`, `evals/dashboard/detail.py` |
| R006 fn-length | 42 | `evals/case_drafts.py` (4), `evals/summary.py` (3), `evals/scenario_adapters_extra.py` (3), `evals/label_import.py` (3), `evals/runner.py` (2) |

**Combined total tracked by the two ratchet files: 205 (133 + 72).**

**The review brief's "313 total" and "57 in the rules baseline" are both wrong for the current tree.**
- 313: not found anywhere as a live or historical count. `git log` over `scripts/rules_baseline.txt`'s last 20 revisions shows the file has stayed in the 133–137 range; it never held 313 rows, and 313 + evals' 72 doesn't reach it either. Unverifiable — treat as stale/incorrect.
- 57: real, but historical and superseded. `project-harness/DECISIONS.md:1996` (DEC-140, 2026-06-22): *"ISSUE-053 originally tracked '57 grandfathered check-rules violations'... Those clusters are now fully cleared... What remains is only R001... and R006."* DEC-140 explicitly redefines "done" and reports the baseline at 137→136 immediately after — i.e. the brief is quoting the pre-redefinition count from over two months ago, not the current 133.

### 2. Oversized files (non-test .py > 300 lines)

Method: `find <body> -name "*.py" | wc -l` per file, excluding paths under any `tests/` dir, `test_*.py`, or `*_test.py`. **40 files** across src/demo_game/evals/scripts (tests/ exempted per CLAUDE.md, see §6).

| Body | Oversized files |
|---|---|
| demo_game | 18 |
| src | 13 |
| evals | 7 |
| scripts | 2 (not gated at all — see CR-L08-04) |

Top 15:

| Lines | File | Waived in DECISIONS.md? |
|---|---|---|
| 1901 | `demo_game/client.py` | Yes — DEC-034 (waived at 680, "grow to ~750 by end of Phase 4") |
| 1677 | `demo_game/seeds/seed.py` | Yes — DEC-033 (waived at 671, limit "~800") |
| 925 | `demo_game/ui/layout/game_window.py` | Stale — DEC-032/074 waived at 350; nothing since |
| 875 | `evals/calibration.py` | No DECISIONS entry found |
| 799 | `src/npc_engine/retrieval/context/context_builder.py` | Yes — DEC-016 (waived at ~464) |
| 654 | `demo_game/runners/run_scenes.py` | Via DEC-049 (split rationale, no line ceiling stated) |
| 630 | `src/npc_engine/scheduler/tick_scheduler.py` | Yes — DEC-042 (waived at ~480) |
| 627 | `demo_game/runners/run.py` | Via DEC-049 |
| 618 | `demo_game/ui/layout/right_panel.py` | Yes — DEC-047 (waived at ~405) |
| 577 | `src/npc_engine/retrieval/context/context_budget_enforcer.py` | Yes — DEC-073 (waived at 323, "do not grow further") |
| 559 | `evals/compare.py` | No DECISIONS entry found |
| 556 | `demo_game/game_controller.py` | Not individually named in DEC-140's catalog |
| 541 | `evals/summary.py` | No DECISIONS entry found |
| 517 | `demo_game/ui/layout/left_panel.py` | Yes — DEC-036 (waived at 322, "may reach ~340") |
| 509 | `evals/matchers.py` | Yes — DEC-145 (waived at 474) |

**Waiver drift** (stated waiver line count vs. actual today) is severe for several files — see CR-L08-01/02/03.

### 3. Dead code estimate

Method: `vulture` (installed into project venv for this scan only, no source touched) at `--min-confidence 60`, cross-checked by hand with `grep -rn` for every candidate before calling it dead — vulture alone is unreliable here because FastAPI route handlers, Pydantic `@field_validator`s, and `Protocol` methods are only ever called through framework/decorator machinery it can't see, so its raw "unused function" hits (193 across src) are **>90% false positives** (route handlers, config validators). Confirmed dead code required an explicit grep showing zero call/construct sites outside the definition, its own tests-that-mock-it, and docstrings.

Confirmed dead (2 items, both exception classes with a documented contract that no code path implements):
1. `src/npc_engine/utils/errors.py:53` `GraphUnavailableError` — cited in 4 docstrings as the fallback for "Neo4j unavailable" (`engines/military/military_battle_service.py:59`, `military_resource_service.py:47`, `engines/ports/dialogue_graph_port.py:73`, `graph/political/pledge_violation_service.py:86`) but `grep -rn "raise GraphUnavailableError" src/` returns **zero** hits. The only place it's raised is `tests/unit/engines/test_investigation_service.py`, which injects it via a mock session (`_make_failing_session(exc)`) rather than exercising a real conversion from a Neo4j driver error.
2. `src/npc_engine/utils/errors.py:301` `TokenBudgetExceededError` — the exact contract CLAUDE.md cites ("`context_builder.py` raises `TokenBudgetExceededError`"), but `context_budget_enforcer.py` raises `ContextBudgetError` (5 raise sites, lines 78/88/151/321) instead; `grep -rn "TokenBudgetExceededError" src/` finds only the class definition. It also doesn't inherit `StructuredNPCSystemError` like its siblings, breaking the "custom exception hierarchy" rule on its own terms. 12 lines dead, imported-but-unused by one test (`tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`).

Likely-dead subsystem (not individually re-verified per function, flagged as a cluster): `graph/political/*` (7 unused-function hits: `political_agenda_writer.py`, `political_leverage_writer.py` x2, `political_queries.py` x5, `political_title_writer.py` x2) and `graph/military/military_writer.py` (5 unused-function hits: `create_army`, `create_resource_node`, `link_resource_node`, `move_army`, `link_army_to_commander`) — these read as complete graph-writer layers for game features with no api/routes or engines/ caller found in the same vulture pass. Not individually confirmed by grep in this pass (time-boxed); flagged as **Suspected**, worth a dedicated grep-per-symbol pass.

LOC estimate: only the 2 Confirmed items (~15 lines) are safe to state as a number. The Suspected political/military cluster, if genuinely orphaned, would be several hundred LOC across ~7 files — not counted in the total below because unconfirmed.

### 4. Duplication

Method: `ast.parse` over src/demo_game/evals (test dirs excluded), grouped `FunctionDef`/`AsyncFunctionDef` names appearing in >1 file, then hand-diffed the plausible ones (Protocol/impl pairs and the mandated `_work(tx)` transaction-coordinator closure pattern — DEC-119/SEV-21 — are expected repeats, not duplication, and were excluded).

Confirmed near/exact duplicates:
1. `demo_game/ui/boards/faction_board.py:193` `_draw_no_data(surface, font, text, clr, rect)` vs `demo_game/ui/panels/retrieval_panel.py:210` `_draw_no_data(...)` — **byte-identical 38-line body**, `diff` shows exactly one word differs ("centred" vs "centered" in the docstring).
2. `demo_game/ui/panels/player_model_panel.py:160` `_draw_no_data(self, surface, rect)` vs `demo_game/ui/panels/scheme_board_panel.py:144` `_draw_no_data(self, surface, rect)` — identical 7-line bodies (blit a centered message), differ only in docstring wording ("no data" vs "no schemes").

`_draw_no_data` exists in 5 sibling `demo_game/ui/{boards,panels}/*.py` files total (2 in the free-function form, 2 in the method form, 1 divergent — `memory_panel.py` has its own word-wrap variant). No shared base class or helper module for panel "empty state" rendering exists despite the repeated pattern.

### 5. Orphaned artifacts

| Artifact | Size | Last modified/committed | Tracked in git? |
|---|---|---|---|
| `p04_ah.log`, `p04_eval.log`, `p04_gen.log`, `p04_judge_mixtral.log`, `p04_judge_qwen14b.log`, `p04_retrieval.log` (6 files) | 4.8KB–46KB (75KB total) | Aug 5–6, 2026 | No — `git check-ignore -v` confirms all 6 match `.gitignore:51 *.log` |
| `live_openapi.json` | 178KB | Last **committed** 2026-07-31 (`f678dd4`), not touched since | **Yes**, tracked. `grep -rln live_openapi` finds it referenced only in 3 planning docs, zero code/CI consumers, zero Makefile target that regenerates it. `paths` count = 128 vs 136 live `@router.*` decorators today — already drifted from the source it claims to document. |
| `.claude/worktrees/` | 0 bytes | n/a | The brief's "9 stale worktrees" claim is **false for this checkout** — the directory exists but is empty (`find .claude/worktrees -maxdepth 2` returns only the dir itself), and `git worktree list` shows only the main worktree. |
| `project-harness/archive/` | 3.1MB, 224 `.md` files (brief said 215 — close, off by 9) | Spans 2026-05 (oldest: `review-2026-06-03/review-evidence/final/L2-architecture.md`) to **today** (`ISSUES_RESOLVED.md`, actively appended per the CLAUDE.md issue-close workflow) | Mixed — `review-2026-06-03/review-evidence/` is gitignored (`.gitignore:75`); the rest is tracked. Not uniformly "orphaned": `ISSUES_RESOLVED.md` is a live, canonical, actively-written file per CLAUDE.md's own process; the other ~223 files are frozen historical snapshots. |
| root `__pycache__/` | small (3 `.pyc` for `conftest.py` across 3 interpreter versions incl. a stray `cpython-314-pytest-8.4.2` from an old pytest) | Aug 18, 2026 | No — gitignored (`.gitignore:5`) |
| `transcripts/` (top level) | 5.5MB, 598 files | oldest May 11, newest current | No — gitignored (`.gitignore:44`), 0 tracked |
| `e2e/transcripts/` | 148KB, 1 file | Aug 6 | No — gitignored (`.gitignore:24`), 0 tracked |
| `dashboard/` | 56KB (index.html + css/js) | Jun 18, 2026 | Tracked (not checked further — out of scope for this pass beyond noting its age: untouched for ~10 weeks) |

### 6. Test-to-source ratio, oversized tests

| Body | Source LOC | Test LOC | Ratio (test/source) |
|---|---|---|---|
| `src/npc_engine` | 68,218 | 65,572 (`tests/` total 80,324 minus `tests/unit/evals` 14,752) | 0.96 |
| `evals` | 20,141 | 14,752 (`tests/unit/evals`, 89 files) | 0.73 |
| `demo_game` | 21,109 (non-test) | 15,852 (`demo_game/tests`, 87 files) | 0.75 |

Test files > 300 lines: **41** under `tests/` + **11** under `demo_game/tests` = 52 total, all exempt from R001 by the CLAUDE.md test carve-out. Spot-checked the two largest (`tests/unit/engines/test_anti_hallucination_runner.py`, 663 lines / 19 test functions; `tests/unit/retrieval/test_context_builder.py`, 639 lines / 12 test functions, ≈53 lines/test) — size tracks the genuine complexity of the module under test (`context_builder.py` is itself the largest oversized src file at 799 lines) rather than looking like padding or copy-pasted setup. No evidence in this sample that the test exemption is being used to hide complexity; not exhaustively checked across all 52.

---

## Findings

### [CR-L08-01] `client.py` and `seed.py` blew through their own DECISIONS-stated growth ceilings by 2–3x, unactioned

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** DEC-034 (`project-harness/DECISIONS.md:885`) waives `demo_game/client.py` at 680 lines with an explicit limit: *"If client.py exceeds ~900 lines, extract a QuestClient and EconomyClient mixin."* Actual today: `demo_game/client.py` = **1901 lines** (`wc -l`), 2.1x the stated trigger, no follow-up DECISIONS entry. DEC-033 (`DECISIONS.md:914`) waives `demo_game/seeds/seed.py` at 671 lines with limit *"If seed.py grows past ~800 lines, extract helpers into `demo_game/_seed_helpers.py`."* Actual today: **1677 lines**, 2.1x the stated trigger. Compounding this, `seed.py`'s own module docstring (lines 11-12) says the sibling split into `seed_npc_data.py` was done "to keep this file under the 300-line limit" — a claim false by 5.6x for the file the docstring is written in.
- **Cost of inaction:** Both files keep absorbing every new demo feature (client.py is the single HTTP surface for every engine endpoint; seed.py is the single world-seeding entrypoint) with no split boundary in force — the next contributor has no signal that the previously-agreed limit was already passed, twice.
- **Fix sketch:** Action the DEC-034 mixin extraction (QuestClient/EconomyClient) and the DEC-033 `_seed_helpers.py` extraction now that both stated thresholds are exceeded; update the seed.py docstring to stop asserting a false 300-line claim.
- **Effort:** L
- **Removes:** 0 lines (extraction, not deletion) — but resolves ~3,578 lines of file-size debt across the two files
- **Blast radius:** `client.py` is imported by every demo runner/scenario/poller; a mixin split changes only internal organization if `EngineClient` still exposes the same methods, but touches the most-imported file in `demo_game/`.

### [CR-L08-02] `game_window.py` regrew past its "resolved" split to 925 lines with no waiver since 350

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** DEC-032 (`DECISIONS.md:873`) split `game_window.py` specifically to fix repeat overruns, targeting *"thin `GameWindow`: pygame event loop, thread ownership... (~150 lines)"* and concluding *"File sizes stay within 300-line limit without exceptions."* DEC-074 one week later already found it back at 350 lines. `grep -n "game_window" project-harness/DECISIONS.md` shows no entry after DEC-074 (2026-06-05) addressing further growth. Actual today: `demo_game/ui/layout/game_window.py` = **925 lines** — 2.6x the last documented waiver, 6.2x the post-split target the split was supposed to guarantee.
- **Cost of inaction:** The file is currently the largest undocumented overrun in the repo; whatever DEC-032 split apart (thread ownership vs rendering) has plausibly re-merged, since nothing tracks what grew.
- **Fix sketch:** Read the current file to identify what's been added since DEC-074 (likely more UI wiring); either extract it to a fourth renderer/coordinator file per the DEC-032 pattern, or write the DEC-140-style top-of-file waiver comment this file currently lacks.
- **Effort:** M
- **Removes:** 0 (needs a real split or a documented waiver, not deletion)
- **Blast radius:** Central demo UI file; any split touches the pygame event loop all panels depend on.

### [CR-L08-03] Two error classes document a fallback contract that no code path implements

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `src/npc_engine/utils/errors.py:53` `GraphUnavailableError` is named as the Neo4j-unavailable fallback in 4 docstrings (`engines/military/military_battle_service.py:59`, `military_resource_service.py:47`, `engines/ports/dialogue_graph_port.py:73`, `graph/political/pledge_violation_service.py:86`) and in this repo's own CLAUDE.md example ("Neo4j unavailable → raise `GraphUnavailableError`"), but `grep -rn "raise GraphUnavailableError" src/` returns nothing — it is never raised by production code, only injected via mock in `tests/unit/engines/test_investigation_service.py:164` to test that it *propagates*, not that anything *produces* it. `src/npc_engine/utils/errors.py:301` `TokenBudgetExceededError` is the exact class CLAUDE.md's prompt-hygiene rule names, but `context_budget_enforcer.py` raises `ContextBudgetError` at all 5 of its raise sites instead — `TokenBudgetExceededError` is never raised anywhere in `src/`.
- **Cost of inaction:** A real Neo4j outage today propagates whatever the neo4j driver raises (e.g. `ServiceUnavailable`) straight to the caller uncaught and untyped, not the documented, structured `GraphUnavailableError` → 503 contract the docstrings and CLAUDE.md promise operators.
- **Fix sketch:** Either wrap the driver's connectivity exceptions into `GraphUnavailableError` at the graph-session boundary (the actual fix CLAUDE.md's contract implies), or delete both classes and correct the 4 docstrings + CLAUDE.md's example if the contract was abandoned deliberately.
- **Effort:** M
- **Removes:** ~15 lines if abandoned; 0 if implemented (adds a wrapper instead)
- **Blast radius:** Every graph-session call site if the wrap is added at a shared boundary (e.g. `transaction_coordinator.py`); low blast radius if just deleting the two dead classes and 4 docstring lines.

### [CR-L08-04] `scripts/` is invisible to the 300-line and 40-line rule gates entirely

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `scripts/check_rules.py:112-113,148` — `_iter_py` is only ever called with `"src/npc_engine"`, `"demo_game"`, and (for `--evals`) `"evals"`. `scripts/` and `tests/` are never scanned for R001/R006. Live measurement: `scripts/check_conservation.py` = 327 lines, `scripts/_roadmap_cursor_core.py` = 311 lines — both over the 300-line limit CLAUDE.md states as universal, both absent from `rules_baseline.txt`, and neither can ever trip `check-rules` because the scanner doesn't look there.
- **Cost of inaction:** `scripts/` (the harness's own gate/automation code) can grow arbitrarily large with zero ratchet, including scripts that themselves enforce the very rule they're exempt from.
- **Fix sketch:** Add `"scripts"` to the `_iter_py` roots in `check_rules.py`'s R001/R006 passes and run `--update-baseline` once to grandfather the 2 current offenders.
- **Effort:** S
- **Removes:** 0 lines; adds 2 files to the baseline
- **Blast radius:** None — purely additive to the gate's scan scope.

### [CR-L08-05] Review brief's "313 grandfathered violations" figure does not match any live or historical count

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `python scripts/check_rules.py` → "133 grandfathered"; `--evals` → "72 grandfathered"; combined 205. `git log` over the last 20 revisions of `scripts/rules_baseline.txt` shows a range of 133-137 rows, never near 313, and no combination with `evals_baseline.txt` (max 75 rows ever, per `wc -l`) reaches it either.
- **Cost of inaction:** Downstream lenses or the synthesized review report may repeat "313" as ground truth, undermining the credibility of the whole codebase-debt narrative.
- **Fix sketch:** Correct the figure to 205 (133 rules + 72 evals) wherever "313" is cited in `project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md` and any synthesized findings doc.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** Documentation only.

### [CR-L08-06] `.claude/worktrees/` claim of "9 stale worktrees" is false for this checkout

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `find .claude/worktrees -maxdepth 2` returns only the directory itself (empty); `git worktree list` shows exactly one worktree (the main checkout at `d46ae42`).
- **Cost of inaction:** Same as CR-L08-05 — a false orphan claim propagating into the synthesized report.
- **Fix sketch:** Drop the ".claude/worktrees" line item from the brief, or re-verify on whichever machine produced the "9" figure (possibly true on a different contributor's local checkout, but not reproducible here).
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** Documentation only.

### [CR-L08-07] Duplicated `_draw_no_data` empty-state helper across demo_game UI panels

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `demo_game/ui/boards/faction_board.py:193` and `demo_game/ui/panels/retrieval_panel.py:210` — identical 38-line `_draw_no_data(surface, font, text, clr, rect)` free function (`diff` shows a 1-word docstring spelling difference only). Separately, `demo_game/ui/panels/player_model_panel.py:160` and `demo_game/ui/panels/scheme_board_panel.py:144` — identical 7-line method form.
- **Cost of inaction:** A future change to how "no data" states render (e.g. a new empty-state icon) needs to be hand-applied in 4+ places; two already drifted apart in styling (free-function word-wrap version vs. plain-centered method version).
- **Fix sketch:** Extract one `draw_no_data(surface, font, text, clr, rect)` free function into `demo_game/ui/panel_helpers.py` (or similar shared module) and have all 5 panels call it.
- **Effort:** S
- **Removes:** ~45 lines (net, after adding one shared function)
- **Blast radius:** 5 UI panel files; visual-only, low risk.

### [CR-L08-08] Waiver-mandated top-of-file comments missing on the 4 highest-drift oversized files

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CLAUDE.md: *"If a split would be artificial, write a justifying comment at the top of the file."* DEC-140 promises this for 5 named files and confirmed present in all 5 (`api_seeder.py`, `intent_queries.py`, `quest_lifecycle_engine.py`, `prompt_builder.py`, `gossip_handler.py`). But `head -25` on the 4 files with the worst waiver-vs-actual drift shows no such comment: `src/npc_engine/config.py` (DEC-077, waived at 309, actual 504), `demo_game/ui/layout/game_window.py` (DEC-074, waived at 350, actual 925), `demo_game/client.py` (DEC-034, waived at 680, actual 1901), `src/npc_engine/retrieval/context/context_budget_enforcer.py` (DEC-073, waived at 323 with "do not grow further," actual 577).
- **Cost of inaction:** A contributor opening any of these 4 files has no in-file signal that the size is already a known, aging exception well past its last-agreed number — they'd need to grep DECISIONS.md and notice the line count no longer matches.
- **Fix sketch:** Add the one-line `DEC-0xx waiver, see DECISIONS.md` header CLAUDE.md requires to each of the 4 files; costs under 10 minutes total.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** None — comment-only addition.

### [CR-L08-09] `live_openapi.json` is a stale, unreferenced, git-tracked generated artifact

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** Tracked in git, last commit `f678dd4` (2026-07-31). `grep -rln live_openapi` across the repo finds it named only in 3 planning docs — zero code, zero CI, zero Makefile target reads or regenerates it. `python -c "json.load(...)"` shows 128 `paths` vs. 136 live `@router.*` route decorators counted today — it has already drifted from the API surface its filename claims to capture.
- **Cost of inaction:** Anyone who finds this file and trusts it (e.g. a partner studio doing API discovery) gets a wrong, ~4-week-stale contract with no generator to refresh it.
- **Fix sketch:** Delete the file, or add a `make openapi-dump` target plus a `.gitignore` entry so it's generated on demand instead of committed.
- **Effort:** S
- **Removes:** 182KB / 1 file
- **Blast radius:** None found — no consumer.

---

## Summary of counts

- Grandfathered rule violations (live, confirmed): **205** (133 `rules_baseline.txt` + 72 `evals_baseline.txt`) — not 313, not 57 (see CR-L08-05).
- Oversized non-test files (>300 lines, live count): **40** (18 demo_game, 13 src, 7 evals, 2 scripts — the last 2 invisible to the gate, CR-L08-04).
- Confirmed dead code: 2 classes, ~15 lines (CR-L08-03). A larger `graph/political/*` + `graph/military/military_writer.py` cluster is Suspected, not confirmed.
- Confirmed duplication: 2 near/exact-identical function pairs, ~45 lines removable (CR-L08-07).
- Orphaned artifacts: 6 gitignored log files (75KB, not tracked — low concern), 1 tracked stale JSON (182KB, CR-L08-09), `.claude/worktrees/` claim falsified (CR-L08-06), `project-harness/archive/` mostly-frozen-but-partly-live (224 md files, 3.1MB).

### Orchestrator addendum to CR-L08-03 — the fallback contract is broken at every hop, and it is worse than L8 reported

L8 marked this HIGH on the strength of "the classes are never raised". The
orchestrator traced the full chain and confirms three independent breaks, which
together make this the review's strongest CRITICAL candidate. All **Confirmed**.

`project-harness/CLAUDE.md` states, under *Error handling*, marked **(strict)**:

> **Engine boundary fallback contracts** (strict): LLM timeout → serve
> `fallback_responses.json`; Neo4j unavailable → raise `GraphUnavailableError` →
> API 503.

Hop 1 — nothing raises it:

```
$ grep -rn "raise GraphUnavailableError" src/ | wc -l
0
$ grep -rn "raise TokenBudgetExceededError" src/ | wc -l
0
```

The only occurrences of `GraphUnavailableError` outside `utils/errors.py` are
**docstrings promising the behaviour**, e.g.
`src/npc_engine/engines/military/military_battle_service.py:59`,
`src/npc_engine/engines/military/military_resource_service.py:47`,
`src/npc_engine/graph/political/pledge_violation_service.py:86`,
`src/npc_engine/engines/ports/dialogue_graph_port.py:73`.

Hop 2 — what actually propagates is the raw driver exception. At least 11
graph-layer docstrings declare `Raises: neo4j.exceptions.Neo4jError` directly
(`src/npc_engine/graph/intrigue/scheme_reader.py:167,199,233,280`,
`src/npc_engine/graph/character/player_model_writer.py:96,137`,
`src/npc_engine/graph/relations/relation_phase_reader.py:67`, …). A third-party
driver exception crossing `graph/` → `engines/` → `api/` is itself a layer leak
the layer gate does not model.

Hop 3 — the API maps it to **500, not 503**.
`src/npc_engine/api/errors/exception_handlers.py:113-120` registers exactly four
handlers: `RequestValidationError` → 422, `HTTPException` → passthrough,
`ContentRatingViolationError` → 422, and `Exception` → `_internal_error_handler`.
There is no handler for `GraphUnavailableError`, none for `Neo4jError`, and none
for `ServiceUnavailable`. So a Neo4j outage returns
`{"error": {"code": "internal_error", "message": "internal error"}}` with status
**500** (`exception_handlers.py:68-86`).

Also: `TokenBudgetExceededError` is declared as
`class TokenBudgetExceededError(Exception)` at
`src/npc_engine/utils/errors.py:301` — a bare `Exception` subclass, not a
`StructuredNPCSystemError`, in direct violation of the same file's
*Custom exception hierarchy (strict)* rule, in the one module that rule is about.

**Why this is the headline.** A licensable game-engine middleware with a stated
99.5%-uptime NFR gives its integrators no way to distinguish "backend is down,
retry with backoff" (503) from "your request is malformed, do not retry" (500).
Unity and Unreal clients written against `docs/API.md` will retry-storm or
hard-fail on the wrong signal. And all 15 gates are green with this in place:
`check-layers`, `check-rules`, `check-docstrings` and 4,048 passing tests do not
see it, because the docstrings *say* the right thing and no gate compares a
docstring's `Raises:` clause to what the code raises.

- **Severity:** CRITICAL (upgraded from L8's HIGH)
- **Confidence:** Confirmed (traced end to end, all three hops)
- **Kind:** Defect
- **Cost of inaction:** The first integrator to run against a flapping Neo4j
  gets 500s and no retry signal. Discovered at integration time, by the customer.
- **Fix sketch:** Wrap graph-session acquisition to raise `GraphUnavailableError`
  on `neo4j.exceptions.ServiceUnavailable`/`SessionExpired`, register a handler
  mapping it to 503, and make `TokenBudgetExceededError` a `StructuredNPCSystemError`.
- **Effort:** M
- **Blast radius:** `graph/` session helpers, `api/errors/exception_handlers.py`,
  the ~11 docstrings that already promise this, `docs/API.md` error table.

### Orchestrator correction to CR-L08-06 — the worktrees existed at review start

L8 reports `.claude/worktrees/` empty and calls the brief's "9 stale worktrees"
false. That is right *now* and wrong *then*. At 22:58 on 2026-08-27, before any
lens was dispatched, the orchestrator ran `ls -1 .claude/worktrees/` and got nine
directories: `agent-a0919b9e6b10ea989`, `agent-a47986289913959ae`,
`agent-a522606fb41ed18eb`, `agent-a658cae366de64081`, `agent-a96ffb4d129e05af9`,
`agent-ac442d1f1c61ce295`, `agent-ad7b46ac7701be0ac`, `agent-ade05c3d9b7b187de`,
`agent-afce5ea1fac4cca9a`. By 23:01 the directory was empty (`du -sh` = 8.0K,
`git worktree list` shows only the main checkout). They were reaped mid-review by
tooling, not by a human. The brief's claim was accurate; treat CR-L08-06 as
withdrawn and CR-L08-05's "313" correction as the only surviving brief-figure
challenge. `.claude/` is gitignored (`.gitignore:58`), so none of this was ever
tracked.

---

## L6 — Gate efficacy vs. gate theatre

# CR-L06 — Gate efficacy vs. gate theatre

Lens L6. Branch `eval-ab-context-arms`, HEAD `d46ae42`, 2026-08-27. Read-only.
All mutation experiments were run against **copies in the scratchpad**; nothing in the repo was modified.

---

## Required measurements

### 0. `make check` is **14** targets, not 15

`Makefile:200` —

```
check: lint check-rules check-evals-rules check-layers check-docstrings type type-evals \
       check-harness check-human-gates check-test-quality check-conservation \
       check-label-survival test-cov test-cov-evals
```

Counted: 14. The orchestrator brief says "15 targets" and then lists these same 14. Correcting the
denominator matters because every "N of 15 gates" claim downstream is off by one.

### 1. Per-gate efficacy history

| # | Gate | Added (commit, date) | Script commits | Ever blocked something? | Verdict |
|---|------|---------------------|----------------|------------------------|---------|
| 1 | `lint` | `b390a07` 2026-06-03 | n/a (ruff) | Yes — `1feef1a` "R002 print removal"; ISSUE-169 records lint-scope reds | **gates (thin)** — 60 of 929 ruff rules enabled |
| 2 | `check-rules` | `b390a07` 2026-06-03 | 3 | Yes — `4b13b8b`, `1fcc3fe`, `c2e3eab` are gate-repair commits | **gates, with a hole** (§4, CR-L06-05) |
| 3 | `check-evals-rules` | `3ab66da` 2026-08-10 | (shares `check_rules.py`) | Yes — ISSUE-169 "`make check-evals-rules` AND `make type-evals` are both red on main"; `dafae39`, `c2e3eab` | **gates, but the ratchet runs backwards** (§3) |
| 4 | `check-layers` | `d24f442` 2026-06-04 | 3 | Yes — `a397661` "graph writer takes phase as str (layer fix)" | **gates** (counterfactual verified, §4) |
| 5 | `check-docstrings` | `38f7e87` 2026-06-04 | 3 | Yes — `1fcc3fe` "docstring format" | **form-only / tautological on content** (§4) |
| 6 | `type` | `b390a07` 2026-06-03 | n/a | Yes — 256→0 burn-down, `9ee2e73` 2026-06-04 | **gates** |
| 7 | `type-evals` | `3ab66da` 2026-08-10 | 1 | Yes — ISSUE-169; `c2e3eab` "evals types" | **gates** (baseline now 0 ⇒ effectively a hard gate) |
| 8 | `check-harness` | `b390a07` 2026-06-03 | 2 | **No.** Its only hard check (H1) needs `lint` red — and `lint` runs *first* in `make check` and in the CI job, so the build is already dead | **tautological** |
| 9 | `check-human-gates` | `b88e95b` 2026-08-10 | 1 | **No.** Grammar-only; exits 0 with zero gates present (proven, §4) | **tautological** |
| 10 | `check-test-quality` | `32b2b10` 2026-08-10 | 1 | **Impossible.** `main()` ends `return 0` unconditionally | **decorative** |
| 11 | `check-conservation` | `1f1be1e` 2026-08-10, wired `ea47583` 2026-08-12 | 4 | Identity 2 **cannot** fail (proven, §4). Identities 1/3 read an artifact committed **once**, 2026-08-09, never changed | **tautological (I2) / inert (I1, I3)** |
| 12 | `check-label-survival` | `e2b1e3f` 2026-08-17 | 1 | **No.** Compares two committed files; `outputs.jsonl` unchanged since 2026-08-09, `labels_v1.jsonl` since 2026-08-14 | **decorative inside `make check`** |
| 13 | `test-cov` | pre-existing | n/a | Yes | **gates** (338 s; 7.86 pts of slack) |
| 14 | `test-cov-evals` | `3ab66da` 2026-08-10 | n/a | Yes — `c2e3eab` "a coverage scope leak" | **gates** (224 s; 4.76 pts of slack) |

Tally: **6 gate, 2 gate-with-a-hole, 3 tautological, 2 decorative, 1 form-only.**

### 2. Gates that can exit 0 while reporting problems

| Gate | Exit-code logic | Reports and still passes? |
|---|---|---|
| `check-test-quality` | `check_test_quality.py:249-261` — `return 0` (line 261) is the only return in `main()` | **Yes, always** |
| `check-harness` | `check_harness_honesty.py:101,114` — `failed = failed or args.strict`; the Makefile passes no `--strict` | **Yes** — H2/H3 print `WARN` and exit 0 |
| `check-rules` / `check-evals-rules` | `check_rules.py:222-223` — prints "*N* baselined violation(s) resolved", then falls through to `return 0` | **Yes** — resolved debt is reported and never locked in |
| `check-label-survival` | Exit reflects `is_frozen` only; it printed **"New (unlabelled) rows in the candidate transcript: 528"** and exited 0 | **Yes** — 528 of 921 transcript rows unlabelled is green |
| `check-conservation` | Identity 4 is a hard-coded `DEFERRED` string, never evaluated (`check_conservation.py:246-251`) | **Yes** — 1 of 4 identities is printed prose |

**Count: 5 of the 14 gates in `make check` can print a problem and exit 0.**
(`check-dead-keywords`, also `return 0` always, is at least honest about it — and it is *not* in `make check`.)

### 3. Ratchet direction — is debt shrinking?

`scripts/rules_baseline.txt`, per-commit totals (`git show <h>:scripts/rules_baseline.txt | grep -c '^R'`):

```
2026-06-03 b390a07   57   (initial)
2026-06-04 8e65631  154   (+116 R006 grandfathered in one commit)
2026-06-24 3950f90  136
2026-08-26 a46b6e5  133   (HEAD)
```

Arithmetic:

- **Phase 1**, 2026-06-04 → 2026-06-24: 154 → 136 = 18 retired / 20 days = **0.90/day**.
- **Phase 2**, 2026-06-24 → 2026-08-26: 136 → 133 = 3 retired / 63 days = **0.048/day = 1.43/month**.
- Extrapolating Phase 2 honestly: 133 ÷ 1.43 = **93 months ≈ 7.8 years to zero.**
- Across the 62 commits touching the file there were **+30 additions** after the initial jump (`adbfe48` +7, `a17fb60` +7, `d89c9b0` +5, …). The file has been *added to* on 20 separate commits.

`scripts/evals_baseline.txt` — nobody had audited this. Composition: R001×7, R002×20, R003×3, R004×0, R006×42 = **72**.

```
2026-08-10 3ab66da  59
2026-08-12 fb2e46d  57
2026-08-12 dc11c6b  58
2026-08-21 dafae39  70   (+12)
2026-08-27 c2e3eab  71
2026-08-27 267a9ac  72   (HEAD)
```

**+13 in 17 days = +0.76/day.** It diverges; there is no extrapolation to zero. `Makefile:114` still says
"59 grandfathered (EVAL-P15.4)" — stale by 13. Note R002 (`print()`, "never `print()`, use logging") has
**20 grandfathered files in `evals/`** — that rule is dead there.

Combined grandfathered debt **133 + 72 = 205**. Net movement over the last 8 weeks: **−3 src, +13 evals = +10.**

> **Verdict: this is a floor, not a ratchet.** It stops debt growing in the files nobody is editing, and mints
> a fresh baseline every time a new area is brought under the gate.

### 4. Tautology hunt — counterfactuals

| Gate | Counterfactual | Result | Verified how |
|---|---|---|---|
| `check-human-gates` | Delete every `#### HUMAN GATE` block from `ROADMAP.md` | **STILL GREEN** — `HUMAN GATES OK (0 gates)`, exit 0 | **Executed** (`ROADMAP_FILE=` override on a scratchpad copy) |
| `check-conservation` I2 | Delete 340 of 345 rows from `judged.jsonl`, then all of them | **STILL GREEN** — "compare reads all **0** unique record_ids OK" | **Executed** (`--gen-dir` scratchpad copy) |
| `check-conservation` I1/I3 | Change nothing (input frozen since 2026-08-09) | Same answer forever; only I3 fires, and only if *both* verdict files are emptied | **Executed** |
| `check-test-quality` | Add 100 `pytest.raises(Exception)` blocks | **STILL GREEN** — `main()` returns 0 regardless | Read (`check_test_quality.py:249-261`); Confidence **Likely** |
| `check-docstrings` | Write `"""Layer: banana\nPurpose: \n"""` | **STILL GREEN** — 0 findings | **Executed** (imported `docstring_audit.audit` on a scratchpad tree) |
| `check-layers` | Inject `from npc_engine.api import routes` into a `graph/` file | **GOES RED** — `layer violation: 'graph' (rank 2) imports 'api' (rank 6)` | **Executed** (imported `check_layers.find_violations`) |
| `check-harness` | Delete `ISSUES.md` entirely | H1 needs `lint` red or a non-zero mypy baseline; both are clean ⇒ still green | Read (`check_harness_honesty.py:82-93`); Confidence **Likely** |
| `check-label-survival` | Change nothing | Green forever; both inputs are committed files unchanged since the gate was wired | **Executed** + `git log` |

**Gates failing the counterfactual: `check-human-gates`, `check-conservation` (I2), `check-test-quality`,
`check-docstrings`, `check-harness`, `check-label-survival` — 6 of 14.**

### 5. CI reality

`.github/workflows/ci.yml` (151 lines) runs, of the 14 `make check` gates:

| In CI | Not in CI |
|---|---|
| `lint`, `check-rules`, `check-layers`, `type`, `check-harness` (step literally named "advisory"), `test-cov` | `check-evals-rules`, `check-docstrings`, `type-evals`, `check-human-gates`, `check-test-quality`, `check-conservation`, `check-label-survival`, `test-cov-evals` |

**6 of 14 in CI; 8 gates are local-only.** Two of those eight (`check-evals-rules`, `type-evals`) are exactly
the ones `ISSUES.md:275` records as *having actually been red on main* — the gates with a demonstrated catch
rate are the ones CI does not run.

`HARNESS_GATES.md:66-70` still carries the open manual step **"Mark these CI jobs *required* for merge in
GitHub branch-protection."** Branch protection is a GitHub-side setting with no in-repo representation; there
is no `CODEOWNERS` and no ruleset file, and `gh` is not installed on this machine
(`bash: gh: command not found`). **Whether it was ever configured is not determinable locally**, and neither
is CI red-on-main history. This needs a human to check the GitHub settings page.

`HARNESS_GATES.md` is stale in two further places: line 34 `.mypy_baseline` "(256 today)" — it has been `0`
since `9ee2e73`, 2026-06-04 — and line 78 "`type-ratchet` forces the 256 count monotonically toward 0", but
`make check` runs plain `type`, never `type-ratchet`.

### 6. The other Makefile targets

| Measure | Value |
|---|---|
| Total targets | **100** (not 101) |
| `make -n <target>` exits 0 | **100 / 100** |
| Targets referencing a script/module file that does not exist | **0** |

Method: extracted every target with `^([A-Za-z0-9_.-]+):(?!=)`, ran `make -n` on each, then resolved every
`*.py` / `*.sh` / `*.ps1` / `*.spec` path token in the Makefile against the filesystem. This is a **negative
result** — the Makefile is not rotted. The 86 non-gate targets are eval verbs, demo runners and seven
`verify-v13` / `verify-v14-p0..p5` aggregates. The `verify-*` set is dead *as gates* (nothing invokes them;
they are subsets of what `check` already runs) but nothing is broken. ISSUE-127 ("No gate catches Makefile
`-m <module>` targets that rot after a package move") is currently a hypothetical, not a live defect.

### 7. What `make check` does not look at

`demo_game/` — **183 files, 36,961 lines, 35% of the non-test tree**:

| Gate | Covers `demo_game/`? |
|---|---|
| `lint` (`ruff check src/ evals/`) | No |
| `type` (`mypy src/`), `type-evals` (`mypy evals/`) | No |
| `check-docstrings` (`src/npc_engine` + `evals`) | No |
| `check-layers` (`src/npc_engine` only) | No |
| `check-test-quality` (`_TESTS_ROOT = <repo>/tests`) | No — `demo_game/tests/` is elsewhere |
| `test-cov` (`--cov=npc_engine,matchers,summary,runner`) | No |
| `check-rules` | **Partly** — R001 and R007 only; R002/R003/R004/R006 apply to `src` only (`check_rules.py:106-137`; `_CYPHER_SCAN_DIRS` at line 54 also omits `api/`, `auth/`, `data/`, `cache/`, `mutation/`) |

Measured consequences:

```
demo_game: files=183 loc=36961

$ python -m mypy demo_game/
Found 256 errors in 45 files (checked 183 source files)

$ python -m pytest demo_game/tests/ -q
1116 passed, 30 warnings in 9.25s
```

1,116 passing tests in **9.25 s**, and `make test-demo` is in neither `make check` nor CI — while
`check-conservation` (1 s, tautological) and `check-label-survival` (1 s, inert) are.

---

## Findings

### [CR-L06-01] Delete `check-human-gates` from `make check` — it passes with the feature it guards deleted

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_human_gates.py:153-171` + `:277-284` — `--verify` calls `verify_gates` (defined at line 153), whose body is `for gate in gates: ...`; with no gates the finding list is empty and it prints OK. Executed against a scratchpad copy of `ROADMAP.md` with every `HUMAN GATE` line stripped:
  ```
  $ python scripts/check_human_gates.py --verify
  HUMAN GATES OK (14 gates)          EXIT=0
  $ ROADMAP_FILE=<scratchpad>/roadmap_nogates.md python scripts/check_human_gates.py --verify
  HUMAN GATES OK (0 gates)           EXIT=0
  ```
  It is a markdown grammar linter with no floor on the population it lints, and it never checks that a gate is *respected* — only that its four fields parse.
- **Cost of inaction:** The overnight loop's only "not yet" mechanism (DEC-164) can be deleted, renamed, or reformatted past the `#### HUMAN GATE` regex and `make check` still calls the repo healthy — precisely the failure DEC-164 exists to prevent. It fails silently the first time someone reflows `ROADMAP.md`; there have been 42 commits to that file since 2026-08-10.
- **Fix sketch:** Drop it from `make check` and keep it as the per-task `--check` hook `scripts/expand_loop.sh` already calls, or add a `--min-gates N` floor so a vanished gate set is red. Prefer the first — the grammar has never once been wrong in 42 roadmap commits.
- **Effort:** S
- **Removes:** 1 target name from `Makefile:200`; the 293-line script stays for `--check`.
- **Blast radius:** `make check` −1 s; `scripts/expand_loop.sh --check` unaffected.

### [CR-L06-02] `check_conservation` Identity 2 was rewritten into `x == x` under the label of a bug fix

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_conservation.py:164` sets `all_slots = compare_slots`, and line 169 returns `ok=(compare_slots == all_slots)`. The in-file comment admits it: *"'all slots the aggregators can see' and 'slots compare reads' are the same population by construction."* Before `9c907a9` (2026-08-16, *"fix(eval): check_conservation.py's own bugs, not the aggregators (ISSUE-172)"*) the same function read:
  ```python
  compare_slots = len(judged_rids)
  all_slots     = len(judged_rids | det_rids)      # two genuinely different populations
  ```
  Executed on a scratchpad copy with all 345 `judged.jsonl` rows deleted:
  ```
  Identity 2 [OK]: compare reads all 0 unique record_ids OK
  ```
  `pct_unread` is dead too — always `0.0`. The tautology is pinned into the suite: `tests/unit/scripts/test_check_conservation.py:190-191` asserts `compare_slots == 307` **and** `all_slots == 307`.
- **Cost of inaction:** Identity 2 is the only check that would notice an aggregator silently dropping a verdict source — the exact bug class ISSUE-172 was filed about. Any future `compare.py` / `summary.py` refactor that stops joining `deterministic_judged.jsonl` ships green.
- **Fix sketch:** Restore the pre-`9c907a9` computation — read both verdict files independently for `all_slots`, take `compare_slots` from what `compare.py` actually consumes. If nobody will own that, delete Identity 2 and its report block rather than leave a green line that means nothing.
- **Effort:** S
- **Removes:** ~30 lines if deleted (`Identity2Report`, `_check_identity_2`, its report block, 2 test assertions).
- **Blast radius:** `tests/unit/scripts/test_check_conservation.py`, the printed report format.

### [CR-L06-03] `check-test-quality` cannot fail — `main()` returns 0 unconditionally

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `scripts/check_test_quality.py:249-261` — the only `return` in `main()` is `return 0` (line 261); there is no branch on `findings`. Its own module docstring says *"Exits 0 always (report-only until EVAL-P15.4)"* while `Makefile:181` says *"Wired into make check as of EVAL-P15.4"*. It was wired in and never armed. One commit, `32b2b10` (2026-08-10), never changed since. Current run: `check-test-quality: 0 issues found.` — 3 s over 544 test files / 80,324 lines on every `make check`.
- **Cost of inaction:** 3 s per `make check` buys a green line that would stay green if all four anti-vacuous patterns reappeared across the whole suite, and inflates the green-gate count used to declare health.
- **Fix sketch:** One line — `return 1 if findings else 0`. The scan currently reports zero issues, so arming it costs nothing today. If nobody will own the `# quality-ok:` waivers, delete the target from `make check` instead.
- **Effort:** S
- **Blast radius:** `tests/unit/scripts/test_check_test_quality.py` may assert the exit code; future test additions would need waivers.

### [CR-L06-04] The rules ratchet is a floor: 7.8 years to zero on `src`, and the evals baseline is growing

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Per-commit totals from `git show <h>:scripts/rules_baseline.txt | grep -c '^R'`: 154 (`8e65631`, 2026-06-04) → 136 (`3950f90`, 2026-06-24) → 133 (`a46b6e5`, 2026-08-26). Phase-2 rate = 3 / 63 days = 1.43/month ⇒ **133 ÷ 1.43 ≈ 93 months ≈ 7.8 years**. Meanwhile `scripts/evals_baseline.txt` went 59 (2026-08-10) → **72** (2026-08-27) — **+0.76/day, diverging** — and `Makefile:114` still claims "59 grandfathered". 20 of those 72 are R002 (`print()`), so the "never `print()`" rule is dead in `evals/`. Combined standing debt 205; net movement over 8 weeks **+10**.
- **Cost of inaction:** "the debt can only ever shrink — it can never silently grow" (`check_rules.py:10-14`) is false as written and is cited in `HARNESS_GATES.md` as evidence of health. Every new area brought under the gate mints a fresh baseline, so violating lines grow alongside checked lines.
- **Fix sketch:** Put an expiry on baseline entries — record the grandfathering commit and fail entries older than N months — or have `check-rules` enforce a per-quarter retirement quota. At minimum make `check-evals-rules` refuse a net increase (fail when `len(current) > len(baseline)`, not only on new signatures).
- **Effort:** M
- **Blast radius:** Every `make check` run; both baseline files; the `HARNESS_GATES.md` claims.

### [CR-L06-05] `check-rules` signatures are file-level, so grandfathered files grow without limit — `demo_game/client.py` gained 481 lines while green

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `check_rules.py:22-25` (rule table) and `:82` — R001's signature is `R001|<path>` and R006's is `R006|<path>::<Qualified.name>`, both deliberately without line numbers (*"so it stays stable across edits that keep the function over-limit"*). Measured at HEAD against the baseline commit `8e65631`:
  ```
  R001 baselined: 31 | grew since 8e65631: 12
    +481  (1420->1901)  demo_game/client.py
    +348  ( 157-> 505)  demo_game/game_end_checker.py
    +207  ( 297-> 504)  src/npc_engine/config.py
    +168  ( 137-> 305)  src/npc_engine/engines/dialogue/prompt_builder.py
    +158  ( 312-> 470)  src/npc_engine/engines/dialogue/dialogue_handler.py
  R006 (all 102 still over 40 lines):
    124 -> 166  scheduler/tick_scheduler.py::TickScheduler.__init__
    111 -> 144  main.py::lifespan
     61 ->  96  engines/gossip/gossip_distort.py::gossip_distort
  ```
  `config.py` (297) and `prompt_builder.py` (137) were **under** the 300-line limit at `8e65631` — they crossed it later and were then added to the baseline. Separately, `check_rules.py:205-206`: when a baselined violation is resolved the gate *prints* it and returns 0, so the win is locked in only if a human remembers `make check-rules-update`; until then the stale signature is a free pass back over the limit.
- **Cost of inaction:** The 300-line and 40-line rules are unenforced in exactly the 133 places that most need them. `demo_game/client.py` is a 1,901-line file that `make check` calls compliant.
- **Fix sketch:** Store the measured magnitude alongside each signature (`R001|path|1420`, `R006|path::name|124`) and fail when the current value exceeds the recorded one — a ratchet on size, not just on identity.
- **Effort:** M
- **Blast radius:** Both baseline files regenerate with sizes; `check_rules.py` `_load_baseline` / `_write_baseline`; `tests/unit/scripts/test_check_rules.py`.

### [CR-L06-06] CI runs 6 of 14 gates, and the 8 it skips include the only two with a documented catch on main

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `.github/workflows/ci.yml:29-46` (`static-analysis`) runs `lint`, `check-rules`, `check-layers`, `type`, `check-harness`; `ci.yml:88-92` runs `test-cov`. Absent from all 151 lines: `check-evals-rules`, `check-docstrings`, `type-evals`, `check-human-gates`, `check-test-quality`, `check-conservation`, `check-label-survival`, `test-cov-evals`. `project-harness/ISSUES.md:275` — *"ISSUE-169: `make check-evals-rules` AND `make type-evals` are both red on main"* — names two of those eight as having genuinely caught a red state. `Makefile:197` claims *"the single canonical health gate. Same command locally and in CI"*; it is not the same command. `HARNESS_GATES.md:66-70` still lists **"Mark these CI jobs required for merge in GitHub branch-protection"** as an open manual step; no `CODEOWNERS`, no ruleset file, `gh` not installed — so **whether branch protection exists is not determinable locally.**
- **Cost of inaction:** `make check` and CI mean different things, so a branch can be green in CI and red locally on eight gates. If branch protection was never set (currently unknown), even the six CI gates are advisory and anything merges.
- **Fix sketch:** Replace the five `static-analysis` steps with a single `run: make check` so CI and local are the same command by construction. Separately, have a human confirm branch protection on GitHub and record the answer in `HARNESS_GATES.md`.
- **Effort:** S for the workflow edit; the branch-protection question needs a human
- **Blast radius:** CI wall time rises to ~10 min per push; `CLAUDE.md` requires human approval before touching CI config.

### [CR-L06-07] Delete `check-harness` from `make check` — its only hard check is unreachable behind `lint`

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `scripts/check_harness_honesty.py:82-93` — H1, the only failing path, fires when `not _lint_clean()` **or** `_mypy_baseline_count() > 0`. `cat .mypy_baseline` → `0` (and `.mypy_evals_baseline` → `0`), so that arm is dead. The other arm needs `ruff check src/ evals/` red — but `lint` is the **first** prerequisite of `make check` (`Makefile:200`) and the **first** step of the CI `static-analysis` job (`ci.yml:29`), so the build is already failed before this runs. H2/H3 print `WARN` and do `failed = failed or args.strict` (lines 112, 122); the Makefile passes no `--strict`, and the CI step is literally named "Harness honesty (advisory)". Current output: `check-harness: OK - 67 open ticket(s); debt is tracked, docs consistent.`
- **Cost of inaction:** 1 s and one of the "14 green" for a check with no reachable failure mode — and it creates the impression that doc-vs-gate contradictions are caught. They are not: `HARNESS_GATES.md:34` has claimed "256 today" for a baseline that has read `0` since 2026-06-04, and this is the gate that was supposed to notice.
- **Fix sketch:** Either pass `--strict` in the Makefile so H2/H3 become real failures, or drop the target from `check` and keep it as a pre-commit advisory. Given H1 is structurally unreachable, `--strict` is the only version worth keeping.
- **Effort:** S
- **Removes:** 1 target name from `Makefile:200` if dropped.
- **Blast radius:** `--strict` would immediately red on any untracked `.py` under `evals/`, `tests/`, or `src/` while `ROADMAP.md` says "complete" — that is the point, but expect a first-run failure (there is one such file right now: `project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md` is `.md` so it does not trip H2, but the pattern is live).

### [CR-L06-08] `check-docstrings` verifies that the substring `Layer:` exists, not that it says anything

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `scripts/docstring_audit.py:43-46` is a pure substring test: `for field in ["Layer:", "Purpose:"]: if field not in docstring`. Executed against a scratchpad file whose whole docstring is `"""\nLayer: banana\nPurpose: \n"""`:
  ```
  docstring_audit on 'Layer: banana' + empty Purpose: []
  ```
  Zero findings. Nothing checks that `Layer:` names one of the 18 packages in `check_layers.LAYER_RANK`, that `Purpose:` is non-empty, or that `Dependencies:` / `Used by:` — both mandated by `CLAUDE.md` — are present at all. The single content guard is one hard-coded string, `PLACEHOLDER_PURPOSE_TEXT = "(auto-detected — review)"` (line 29), left from `scripts/migrate_docstrings.py`.
- **Cost of inaction:** The docstring rule is `CLAUDE.md`'s stated remedy for the `__init__.py` debugging incident, and it currently guarantees only that six bytes appear in a string literal. A file whose declared `Layer:` diverges from the layer `check-layers` enforces passes forever.
- **Fix sketch:** Cross-check the declared `Layer:` value against `check_layers.LAYER_RANK` for files under `src/npc_engine/`, and require at least one non-whitespace character after `Purpose:`. Both are about ten lines inside `_check_file`.
- **Effort:** S
- **Blast radius:** Would immediately red on any file whose `Layer:` was stamped by `migrate_docstrings.py`; expect a burn-down before it can be armed.

### [CR-L06-09] Drop `check-conservation` and `check-label-survival` from `make check` — both audit files that cannot change

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** Both default to the same frozen artifact: `check_conservation.py:34-36` `_DEFAULT_GEN_DIR = .../generations/k3_73e6c36`; `check_label_survival.py:23-28` `_DEFAULT_TRANSCRIPT = .../k3_73e6c36/outputs.jsonl`. That file has **one** commit in its whole history:
  ```
  evals/generations/k3_73e6c36/outputs.jsonl:  1 commit,  last 2026-08-09
  evals/calibration/labels_v1.jsonl:           3 commits, last 2026-08-14
  ```
  `check-conservation` was wired 2026-08-12 and `check-label-survival` 2026-08-17 — neither has ever seen its primary input change. `check-label-survival` also prints `New (unlabelled) rows in the candidate transcript: 528` (528 of 921 rows unlabelled) and exits 0, and stamps the run `legacy_pre_p18_1 (not comparable to any real run)`. ISSUE-176 already logs the hardcoded gen dir; ISSUE-186 records that `k3_73e6c36` cannot even serve as an A/B baseline arm. `Makefile:173-175` says it outright: *"Run before spending a regeneration or a labelling pass"* — a manual pre-flight tool, wired into every health run.
- **Cost of inaction:** 2 s per run for two guaranteed-green lines, and two entries on the "everything is green" list that describe eval-pipeline health while measuring an 18-day-old snapshot.
- **Fix sketch:** Remove both target names from `Makefile:200` and invoke them from the eval-regeneration path (`make eval-generate` / `eval-judge`) where a *new* artifact is the input. Keep the scripts.
- **Effort:** S
- **Removes:** 2 target names from `Makefile:200`.
- **Blast radius:** `make check` −2 s; nothing else consumes these targets.

### [CR-L06-10] 36,961 lines of `demo_game/` sit outside every gate except two file-shape rules

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** Scopes, quoted from the recipes: `lint` = `ruff check src/ evals/` (`Makefile:99`); `type` = `mypy src/` (`Makefile:102`); `type-evals` = `mypy evals/`; `check-docstrings` audits `src/npc_engine` + `evals` (`docstring_audit.py:64-67`); `check-layers` scans `REPO_ROOT/src/npc_engine` (`check_layers.py:179`); `check-test-quality` scans `<repo>/tests` (`check_test_quality.py:29`), and `demo_game/tests/` is not under it; `test-cov` = `--cov=npc_engine --cov=matchers --cov=summary --cov=runner` (`Makefile:53`). Only `check_rules.py:113` and `:135` touch `demo_game`, and only for R001 and R007. Measured:
  ```
  demo_game: files=183 loc=36961
  $ python -m mypy demo_game/       → Found 256 errors in 45 files (checked 183 source files)
  $ python -m pytest demo_game/tests/ -q → 1116 passed, 30 warnings in 9.25s
  ```
  `make test-demo` exists (`Makefile:605`) and is in neither `make check` nor CI.
- **Cost of inaction:** 35% of the non-test tree — including the demo the project is judged on, and `client.py` at 1,901 lines — has zero type checking, zero lint, zero docstring enforcement and no coverage floor. Its 1,116 tests run only when someone remembers, so a demo regression reaches a live demo unnoticed.
- **Fix sketch:** Add `test-demo` to `make check` — 9.25 s against a 595 s baseline (1.5%), and all 1,116 tests pass today. Extend `lint` to `demo_game/` next. Defer `mypy demo_game/` behind a ratchet; 256 errors is a burn-down, not a same-day gate change.
- **Effort:** S for `test-demo` + `lint`; L for the mypy ratchet
- **Blast radius:** `make check` +9 s; a `demo_game` test failure would newly block `make check`.

### [CR-L06-11] `make lint` enables 60 of 929 ruff rules and runs in 0 s

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `pyproject.toml:64-73` sets only `line-length = 120` and `extend-select = ["I002"]`, so the effective set is ruff's default (`E4`, `E7`, `E9`, `F`) plus one import rule. `ruff check --show-settings` reports **60** enabled rules; `ruff rule --all` lists **929** available. `E501` is not enabled — turning it on alone reports `177 line-too-long`, so the configured `line-length = 120` is decorative. `--select B,S,ARG,SIM` reports **321 errors** including `3× S324 hashlib-insecure-hash-function`, `3× S603 subprocess-without-shell-equals-true`, `2× S310 suspicious-url-open-usage`.
- **Cost of inaction:** `lint` is presented as one of the 14 gates and is effectively pyflakes; its 0-second runtime reads as efficiency but is a scope signal. The eight `S` findings are the class of thing that should be triaged before shipping middleware to studios.
- **Fix sketch:** Add `B` (bugbear) and `SIM` behind the existing baseline pattern, and hand-triage the eight `S` findings rather than enabling `S` wholesale. Leave `E501` off — 177 findings for no defect value.
- **Effort:** M
- **Blast radius:** ~30 fixable findings across `src/` and `evals/`; needs a `noqa` or baseline pass first.

### [CR-L06-12] `HARNESS_GATES.md` states a mypy baseline that has been zero for twelve weeks

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `project-harness/HARNESS_GATES.md:34` — *"`.mypy_baseline` — grandfathered mypy error count (256 today)"* — and line 78 — *"**SEV-14** (type debt) → `type-ratchet` forces the 256 count monotonically toward 0."* `cat .mypy_baseline` → `0`, unchanged since `9ee2e73` (2026-06-04), and `make check` runs `type`, never `type-ratchet`. Same class of staleness at `Makefile:113` ("59 grandfathered" vs. 72 actual) and `pyproject.toml:80` ("Current baseline: 16 errors" vs. 0 actual). `check_harness_honesty.py` — the gate whose stated purpose is *"Fail when … the docs claim a clean state the gates contradict"* — is green on all three.
- **Cost of inaction:** A reviewer reading `HARNESS_GATES.md` concludes there are 256 outstanding type errors when there are none, and that the evals ratchet holds 59 entries when it holds 72 and is growing.
- **Fix sketch:** Correct the three numbers; better, have `check_harness_honesty.py` parse the counts out of the docs and diff them against the live baseline files — that is the one hard check it could perform that `lint` does not already cover.
- **Effort:** S
- **Blast radius:** Docs only, unless the parse-and-compare check is added.

---

## L13 — Truth-in-documentation

> **Orchestrator severity calibration.** L13 filed CR-L13-01 and CR-L13-02 as
> CRITICAL. Both are downgraded to **HIGH** here. The review's rubric reserves
> CRITICAL for "ships broken, loses data, leaks secrets, or the project's core
> claim is false", and §8 warns explicitly against CRITICAL inflation. Both
> findings are doc-only, **Effort: S**, and L13's own **Blast radius** line for
> CR-L13-01 reads "None — doc-only edit". A stale number in a status document is
> a serious credibility defect — it is why they are HIGH and not MEDIUM — but it
> does not ship broken. The evidence and the analysis below stand unchanged; only
> the severity label is adjusted. The two counts in the returned summary
> ("2 CRITICAL, 6 HIGH") therefore read **0 CRITICAL, 8 HIGH** in the synthesis.
>
> Two L13 findings also overlap other lenses and are merged in §C, not double-counted:
> CR-L13-06 (H3 inert) with CR-L06-07 (`check-harness` tautological), and
> CR-L13-11 (`live_openapi.json` stale) with CR-L08-09 (same file, unreferenced).

# CR-L13 — Truth-in-documentation

Scope: all 22 files in `docs/`, plus `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, and
the named-state `project-harness/*.md` files (`HARNESS_GATES.md`, `ROADMAP.md`,
`EVAL_STRATEGY.md`, `HANDOFF_TRACK_A.md`, `HANDOFF_TRACK_B.md`, `MORNING_HANDOFF_*.md`).
`project-harness/CLAUDE.md` is L5's — noted where relevant, not scored here.

Repo state: branch `eval-ab-context-arms`, HEAD `d46ae42`, live API server reachable at
`http://127.0.0.1:8000`.

## Required measurements

### 1. Claims checked / false / unverifiable

**Method:** extracted every quantitative claim (number, threshold, path, command name)
and every state claim ("X is implemented/gated/stale") from the in-scope docs by targeted
grep + manual reading, then verified each by: running the command, reading the
referenced source file, or diffing against the live API. Full `make check` was also run
to completion (twice — see §2/§6) rather than assumed. 74 discrete claims were checked;
the sample concentrates on the docs that make the most decision-relevant claims
(HARNESS_GATES.md, CONTRIBUTING.md, README.md, CASE_SET_POLICY.md/CAPABILITY_CASES.md/
ENGINE_EVAL_COVERAGE.md, API.md, CHANGELOG.md, EVAL_STRATEGY.md, ROADMAP.md header) since
those are where a false number changes a decision; the remaining docs (ARCHITECTURE.md,
DATA_MODELS.md, ENGINES.md, etc.) were spot-checked for path/command validity only.

| Metric | Count |
|---|---|
| Claims checked | 74 |
| Claims FALSE | 29 |
| Claims unverifiable (historical, not re-derivable without git archaeology) | 3 |

**Claims false — table:**

| Doc:line | Claim | Measured truth | How measured |
|---|---|---|---|
| `project-harness/HARNESS_GATES.md:33` | "`scripts/rules_baseline.txt` — grandfathered CLAUDE.md rule violations (**57** today)" | File has **133** violation entries (136 lines − 3 comment-header lines); `make check-rules` itself reports "133 grandfathered" | `wc -l scripts/rules_baseline.txt`; ran `python scripts/check_rules.py` → `check-rules: OK - no new violations (133 grandfathered).` |
| `project-harness/HARNESS_GATES.md:34` | "`.mypy_baseline` — grandfathered mypy error count (**256** today)" | File contains **`0`** | `cat .mypy_baseline` → `0` |
| `project-harness/HARNESS_GATES.md:11` | "`make check` = `lint + check-rules + type-ratchet + check-harness + test-cov(80% floor)`" | Actual `check:` recipe (Makefile:200) has **14** deps: `lint check-rules check-evals-rules check-layers check-docstrings type type-evals check-harness check-human-gates check-test-quality check-conservation check-label-survival test-cov test-cov-evals`. It depends on `type` (plain `mypy src/`, Makefile:101-102), not `type-ratchet` (Makefile:122-123, a separate target `make check` never calls) | `grep -n "^check:" Makefile`; `grep -n "^type:\|^type-ratchet:" -A2 Makefile` |
| `docs/CASE_SET_POLICY.md:94` | "Measured and gated by `scripts/check_base_rate.py` (`make check-base-rate`)" | `make check-base-rate` does not exist as a target | `make check-base-rate` → `make: *** No rule to make target 'check-base-rate'.  Stop.` |
| `docs/CAPABILITY_CASES.md:69` | "`make check-engine-coverage` fails when a unit exists with no classification row" | Target doesn't exist | `make check-engine-coverage` → `make: *** No rule to make target 'check-engine-coverage'.  Stop.` |
| `docs/ENGINE_EVAL_COVERAGE.md:4` | "Gated by `scripts/check_engine_coverage.py` (`make check-engine-coverage`)" | Same target, same failure | Same command, same output |
| `project-harness/EVAL_STRATEGY.md:152` | "`make eval-full`" (Running the Full Eval Suite) | Target doesn't exist | `make eval-full` → `make: *** No rule to make target 'eval-full'.  Stop.` |
| `docs/ARCHITECTURE.md:677` | Quick-start snippet: `make seed` | Target doesn't exist (real ones are `seed-api`, `seed-probe`, `seed-village-world`, `seed-tavern-world`, `demo-seed`) | `make seed` → `make: *** No rule to make target 'seed'.  Stop.` |
| `project-harness/EVAL_STRATEGY.md:158` | `python seeds/world/seed_tavern_world.py` | Path is `seeds/worlds/seed_tavern_world.py` (plural) | `ls seeds/worlds/seed_tavern_world.py` exists; `seeds/world/` does not |
| `project-harness/EVAL_STRATEGY.md:116` | `seeds/world/run_eval_world.py` | Path does not exist anywhere in the repo (not even under `seeds/worlds/`) | `find . -iname run_eval_world.py` → no result |
| `CONTRIBUTING.md:39,44,49` | "All tests must be green... See `project/CLAUDE.md` § 'Pre-merge checklist'"; "Read `project/CLAUDE.md` before writing any code" | `project/` directory does not exist; canonical path is `project-harness/CLAUDE.md` | `ls project/` → No such file or directory |
| `CONTRIBUTING.md:56` | "anything you notice but do not fix goes in `project/ISSUES.md`" | Path is `project-harness/ISSUES.md` | Same |
| `CONTRIBUTING.md:57,71` | "write a `project/DECISIONS.md` entry" | Path is `project-harness/DECISIONS.md` | Same |
| `CONTRIBUTING.md:30` | `python -m npc_engine.scripts.seed` (graph seeding step) | Module does not exist | `python -m npc_engine.scripts.seed` → `No module named npc_engine.scripts.seed`; only `demo_game/seeds/seed.py` and `seeds/worlds/*` exist |
| `CHANGELOG.md:8` | "recorded in `project/STATUS.md`" | Path does not exist | `ls project/` fails |
| `CHANGELOG.md:35` | "`project/STATUS.md` — added project health snapshot header" | Same | Same |
| `CHANGELOG.md:36` | "`project/PATTERNS.md` — added Common Anti-Patterns section" | Path is `project-harness/PATTERNS.md` | Same |
| `CHANGELOG.md:36,40` | "migrated from `docs/LLM_GENERATION_GUIDE.md`" / "Removed: `docs/LLM_GENERATION_GUIDE.md`" | File does not exist at that path (never re-verified after the project/→project-harness/ rename) | `find . -iname LLM_GENERATION_GUIDE.md` → no result |
| `CHANGELOG.md:41` | "`project/proposals/WRITE_PATH_CONVERGENCE_P0.md` — moved to `archive/`" | Path does not exist | `ls project/proposals/` fails |
| `CHANGELOG.md:42` | "`project/proposals/refactor.md` — moved to `archive/`" | Same | Same |
| `README.md:77` | `[npc_engine/main.py](npc_engine/main.py)` | Path is `src/npc_engine/main.py` | `ls npc_engine/main.py` fails; `ls src/npc_engine/main.py` succeeds |
| `README.md:78` | `[npc_engine/config.py](npc_engine/config.py)` | Path is `src/npc_engine/config.py` | Same pattern |
| `README.md:79` | `[npc_engine/engines/dialogue/]` | Path is `src/npc_engine/engines/dialogue/` | Same |
| `README.md:80` | `[npc_engine/type_registry/]` | Path is `src/npc_engine/type_registry/` | Same |
| `README.md:81` | `[npc_engine/retrieval/]` | Path is `src/npc_engine/retrieval/` | Same |
| `README.md:84` | `[tests/scenarios/]` | Path doesn't exist; real e2e scenario dir is `e2e/scenarios/` (per project-harness/CLAUDE.md's own test-layout section and the `scenarios` Makefile recipe) | `ls tests/scenarios/` fails; `grep -n "^scenarios:" -A2 Makefile` shows `pytest e2e/scenarios/` |
| `README.md:85` | `[proposals/]` (Design proposals) | Path doesn't exist at root; real path is `project-harness/proposals/` | `ls proposals/` fails |
| `README.md:38` | "`tone_judge` matcher is a stub; wire in LLM-as-judge" | `_eval_tone_judge` in `evals/matchers.py:272` is a working YES/NO LLM-judge call using `prompts/eval/tone_judge.yaml`, not a stub | Read `evals/matchers.py:196,272-290`; `prompts/eval/tone_judge.yaml` is a real 25-line judge prompt template |
| `README.md:34` | "`dialogue_handler.py` currently passes `archetype=\"default\"` to the canned tier; wire in a lightweight graph lookup" | `dialogue_handler.py:220,384` already does the graph lookup: `archetype = await self._dialogue_repo.get_npc_archetype(request.npc_id) or "default"` — "default" is only the fallback | `grep -n archetype src/npc_engine/engines/dialogue/dialogue_handler.py` |
| `README.md:32,33` | "`proposals/prompt_inventory.md` is ready, awaiting approval"; "Pick one of the three options in `proposals/delta_log_options.md`" | Both files are filed under `project-harness/archive/stale-2026-06/` by the project's own archival process — not pending, not even at the path named | `find . -iname delta_log_options.md -o -iname prompt_inventory.md` |

**Notable TRUE claims** (included to show the check was not one-sided): `docs/API.md`
rate-limit defaults (50 req/s, burst 100) match `config.py:250-251` exactly; the
`[0.55, 0.85]` base-rate band in `docs/CASE_SET_POLICY.md:92` matches
`scripts/base_rate_contract.py:32-33` exactly; `docs/ENGINE_EVAL_COVERAGE.md`'s "18 of 44
units qualify" and "tested by `tests/unit/scripts/test_check_engine_coverage.py`" are both
true (script re-run gives 44/44, 18 dialogue_observable; test file exists, 15/15 pass);
CI's "Python pinned to 3.14" (`HARNESS_GATES.md:60`) is true across all 5 job definitions
in `.github/workflows/ci.yml`; ROADMAP.md's "`make check` GREEN" (line 6) is **Confirmed**
— a full `make check` run completed with exit code 0 (1007 passed, 1 skipped, 79.76%
eval coverage against a 75% floor, 80% floor met on the main suite).

**Unverifiable (3):** `HARNESS_GATES.md:5`'s "2026-06-03 review surfaced (38 lint, 254
type errors, 11 oversized files, silent CI)" and `ROADMAP.md:4`'s "SEV backlog... fully
drained (47/47)" and "EXP-201..230... fully shipped" describe historical/aggregate states
at a past commit that would require checking out and re-running tooling against dozens of
historical revisions to re-derive — not attempted given scope.

### 2. `scripts/check_harness_honesty.py`

Read in full (`scripts/check_harness_honesty.py`, 106 lines). Ran both modes:

```
$ python scripts/check_harness_honesty.py
check-harness: OK - 67 open ticket(s); debt is tracked, docs consistent.
(exit 0)

$ python scripts/check_harness_honesty.py --strict
check-harness: OK - 67 open ticket(s); debt is tracked, docs consistent.
(exit 0)
```

**`--strict` currently flags nothing, and cannot, structurally, today:**

- **H1** (lint red / mypy baseline>0 without a covering ISSUE) never fires: `ruff check
  src/ evals/` returns "All checks passed!" and `.mypy_baseline` is `0`.
- **H3** (ISSUES.md has open tickets but NEXT_SESSION.md claims none) is **dead code**:
  `NEXT_SESSION.md` is read via `_read()`, which returns `""` for a missing file — and
  `project-harness/NEXT_SESSION.md` does not exist (it only exists at
  `project-harness/archive/stale-2026-06/NEXT_SESSION.md`). The regex can never match an
  empty string, so this check has not fired, and cannot fire, regardless of what's in
  ISSUES.md, until someone recreates that file.
- **H2** (ROADMAP says "complete" while new `.py`/`.yaml` files sit untracked under
  `evals/`, `tests/`, `src/`) is live in principle (ROADMAP.md does contain "complete" 28
  times) but `git status --porcelain` currently shows zero untracked files matching that
  filter — only three untracked `.md` files, which the check ignores by extension.

**Conclusion:** the honesty gate is advisory by design (per its own docstring) and today
is *also* a no-op in practice — none of its three checks are in a state where they could
fail, one of them (H3) cannot fail at all until a file that was moved to `archive/` is
restored to its original path. `--strict` changes zero behavior against the current tree.

### 3. Documented `make` targets vs Makefile (100 real targets, 693 lines)

| Doc | Target mentioned | Exists? |
|---|---|---|
| `docs/ARCHITECTURE.md:676` | `install` | Yes |
| `docs/ARCHITECTURE.md:677` | `seed` | **No** |
| `docs/ARCHITECTURE.md:678` | `run` | Yes |
| `docs/API.md` | `seed-api`, `smoke`, `scenarios` | Yes (all 3) |
| `docs/CAPABILITY_CASES.md:69` | `check-engine-coverage` | **No** |
| `docs/CAPABILITY_CASES.md:173,188` | `seed-village-world`, `seed-tavern-world` | Yes |
| `docs/CAPABILITY_CASES.md:53,135` / `docs/REASONING_DIMENSIONS.md:201` | `hedge-probe` | Yes |
| `docs/CASE_SET_POLICY.md:74` | `check-dead-keywords` | Yes |
| `docs/CASE_SET_POLICY.md:94` | `check-base-rate` | **No** |
| `docs/DATA_MODELS.md:207` | `check-contracts` | Yes |
| `docs/DEMO.md`, `docs/DEMO_SCRIPT.md` | `eval-llm-demo`, `demo-seed`, `demo`, `demo-video`, `demo-run` | Yes (all) |
| `docs/ENGINE_EVAL_COVERAGE.md:4,99` | `check-engine-coverage` (**No**), `eval-arm-probe` (Yes) | mixed |
| `docs/SCORER_TRUST_POLICY.md:5` | `eval-calibrate` | Yes |
| `README.md` | `demo-seed`, `demo`, `test`, `eval` | Yes (all) |
| `CONTRIBUTING.md:39-41` | `test`, `eval`, `smoke` | Yes (all) |
| `CHANGELOG.md:19` | `seed-probe` | Yes |
| `project-harness/CLAUDE.md` | 12 targets (`demo-seed`, `demo`, `demo-run`, `test`, `test-demo`, `eval-llm-demo`, `demo-village`, `demo-tavern`, `seed-village-world`, `seed-tavern-world`, `eval-report`, `demo-snapshot`, `check-layers`) | Yes (all 13) |
| `project-harness/HARNESS_GATES.md` | `lint`, `check-rules`, `type-ratchet`, `test-cov`, `check-harness`, `check-contracts`, `check-rules-update`, `type-ratchet-update` | Yes (all exist as targets — the doc's *bug* is that `check` doesn't call `type-ratchet`, not that `type-ratchet` is missing) |
| `project-harness/EVAL_STRATEGY.md:152` | `eval-full` | **No** |
| `project-harness/EVAL_STRATEGY.md:155` | `eval-llm-demo` | Yes |
| `project-harness/HANDOFF_TRACK_A.md:290` | `check-base-rate` (self-documented as "not in `make check`, by design, until EVAL-P26.2") | **No** target, but doc is honest about it being unwired — contrast with `docs/CASE_SET_POLICY.md` and `docs/CAPABILITY_CASES.md`, which present the same command with no such caveat |
| `project-harness/HANDOFF_TRACK_A.md:309` | `review-cases` (explicitly "the ... recipe **proposed** ... is library-only") | **No** — but framed as a proposal, not a claim, so not counted as false |

**Summary:** of the make targets actually asserted as *currently runnable* (not
"proposed"/"planned"), **4 are dangling**: `seed`, `check-engine-coverage`,
`check-base-rate` (asserted twice, in `docs/CASE_SET_POLICY.md` and
`docs/CAPABILITY_CASES.md`/`docs/ENGINE_EVAL_COVERAGE.md`), `eval-full`. Everything else
sampled across the ~30 docs checked resolved to a real target.

### 4. Dangling file paths

Extracted every `src/docs/evals/tests/scripts/project-harness/seeds/prompts/demo_game/e2e`
path with a file extension (`.py .md .yaml .yml .json`) from the in-scope docs (293 unique
paths) and tested each with a filesystem check.

**42 raw misses**, of which **13 are genuine current-state lies** (listed in the claims
table above: `project/*` × 8 in CONTRIBUTING.md/CHANGELOG.md, `npc_engine/*` × 5 in
README.md, plus `tests/scenarios/`, `proposals/`, `seeds/world/*` × 2,
`docs/LLM_GENERATION_GUIDE.md`). The remaining ~29 are **not** doc bugs: they are
`project-harness/ROADMAP.md` and `project-harness/HANDOFF_TRACK_A.md` items phrased as
future work ("create `tests/unit/evals/test_arm_spec.py`") inside a roadmap/handoff
document, which is the correct place to name a file that doesn't exist yet. Confirms the
task hint — `project-harness/CLAUDE.md` is not the only doc carrying a stale-path
self-correction; `README.md` and `CONTRIBUTING.md` carry several **uncorrected** ones.

### 5. `docs/API.md` vs live API

Live server confirmed reachable: `curl http://127.0.0.1:8000/openapi.json` → HTTP 200,
132 paths. Extracted 120 route mentions from `docs/API.md` (after excluding `/*`-glob
prose fragments like `` `/v1/admin/*` ``, which are section headers, not routes) and
diffed both directions, normalizing `{param}` names.

| Direction | Count | Detail |
|---|---|---|
| Documented but absent from the live route table | 0 real (2 raw hits were false positives: `/v1/graph/nodes/Character` is a doc example instantiating the generic `/v1/graph/nodes/{node_type}` route which *is* live; `/v1/ws/dialogue` is a real WebSocket route confirmed in `src/npc_engine/api/routes/dialogue/dialogue_ws.py` — FastAPI's `/openapi.json` never lists WebSocket routes by design, so this is not a doc bug) | — |
| Live but undocumented in `docs/API.md` | **6** | `/setup/config`, `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate` (all 4 also absent from the committed `live_openapi.json` snapshot — added since 2026-06-24), plus `/v1/admin/factions/{faction_id}/standings/{p}` (a second-param variant of the documented single-param route) and `/v1/admin/schedules/character/{p}/at` (doc only shows the `location/{location_id}/at` sibling) |

`docs/API.md` explicitly disclaims completeness ("the full interactive contract... is
always served live at `/docs`... this document is the curated guide," line 15-16), which
mitigates severity — this is an incomplete curated guide, not a doc asserting a false
closed set.

### 6. `CHANGELOG.md` maintenance

- **Last touched:** 2026-08-14 (commit `5bfa528`). HEAD is `d46ae42`, dated 2026-08-27.
- **96 commits** have landed since, including feature commits that would normally warrant
  an entry: `d7b7c8b feat(evals): the golden-set instrument`, `72594dd feat(evals):
  measure observability before authoring`, `96d83eb fix(config): the shipped window
  derives a budget smaller than the context it assembles`, `4078c37 feat(scripts):
  measure what context assembly COSTS`.
- **No dated/versioned entries exist at all** — the entire file is one `## [Unreleased]`
  section; there are no git tags (`git tag -l` → empty) and no evidence a "release" has
  ever been cut, so the "Keep a Changelog" format claim is structurally true but the
  practice of *releasing* (moving Unreleased to a dated version) has never happened.
- Every path referenced under the current Unreleased section that begins `project/` is
  dangling (see claims table) — the changelog was not updated when `project/` became
  `project-harness/`.

## Findings

### [CR-L13-01] HARNESS_GATES.md's own debt numbers are the wrong sign in both directions

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `project-harness/HARNESS_GATES.md:33` claims "`scripts/rules_baseline.txt`
  ... (57 today)" — actual is 133 (`wc -l` minus 3 header lines; `make check-rules` prints
  "133 grandfathered"). `HARNESS_GATES.md:34` claims "`.mypy_baseline` ... (256 today)" —
  actual is `0` (`cat .mypy_baseline`). The whole doc's stated purpose (line 3-6) is "the
  lint/type/rule/coverage debt... can never silently grow again" — the debt these two
  numbers describe silently changed (rules debt +133%, mypy debt to zero) and the doc,
  whose entire reason to exist is catching exactly that drift, was never updated. Doc has
  not been touched since its creation commit `b390a07` (2026-06-03) — 85 days of drift.
- **Cost of inaction:** Anyone deciding whether to invest more in type-safety cleanup
  reads "256 mypy errors" and either wastes time confirming it's stale or budgets against
  a number that's already zero; anyone auditing rule-violation burn-down sees "57" and
  believes the codebase is closer to clean than it is (133, 2.3x worse).
- **Fix sketch:** Regenerate both numbers from `wc -l scripts/rules_baseline.txt` and
  `cat .mypy_baseline` and either hardcode-and-date them or replace with "see the file" —
  given they visibly drift, prefer removing the specific numbers from prose entirely.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only edit.

### [CR-L13-02] CONTRIBUTING.md's contributor quickstart is broken in two ways a first-time contributor cannot self-diagnose

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CONTRIBUTING.md:30` tells a new contributor to seed the graph with
  `python -m npc_engine.scripts.seed` — running it gives `No module named
  npc_engine.scripts.seed` (confirmed by execution; no such module exists anywhere in the
  repo). `CONTRIBUTING.md:44,49,56,57,71` tell the contributor to read `project/CLAUDE.md`
  (the "authoritative rules file") and log to `project/ISSUES.md` /
  `project/DECISIONS.md` — the `project/` directory does not exist at all (`ls project/`
  fails); the real, canonical location per the project's own rule
  (`project-harness/CLAUDE.md`'s "Project management files — canonical locations"
  section) is `project-harness/`.
- **Cost of inaction:** A brand-new contributor following this file top-to-bottom hits a
  dead command and five dead links to the rules file they were told is mandatory reading
  before writing any code — the exact failure mode CONTRIBUTING.md exists to prevent.
- **Fix sketch:** Replace `python -m npc_engine.scripts.seed` with the real seeding path
  (`make demo-seed` or the `seeds/worlds/` scripts per `project-harness/CLAUDE.md`);
  global find/replace `project/CLAUDE.md` → `project-harness/CLAUDE.md` (and the two
  other `project/*.md` references) in this file.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only edit; no code path depends on this text.

### [CR-L13-03] Two eval-gate docs advertise `make` targets that were never wired into the Makefile

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `docs/CASE_SET_POLICY.md:94` ("Measured and gated by
  `scripts/check_base_rate.py` (`make check-base-rate`)"), `docs/CAPABILITY_CASES.md:69`,
  and `docs/ENGINE_EVAL_COVERAGE.md:4` ("Gated by `scripts/check_engine_coverage.py`
  (`make check-engine-coverage`)") all present a bracketed `make` invocation as the way to
  run the gate. Both fail identically: `make: *** No rule to make target
  'check-base-rate'.  Stop.` and the same for `check-engine-coverage`. The underlying
  Python scripts do exist and work when invoked directly
  (`python scripts/check_engine_coverage.py` → correct 44-unit table). Contrast:
  `project-harness/HANDOFF_TRACK_A.md:290` names the same `check-base-rate` gap but is
  explicit that it's "not in `make check`, by design, until EVAL-P26.2" — the two docs in
  scope carry no such caveat, so a reader of `docs/` alone has no way to know the
  parenthetical command is aspirational.
- **Cost of inaction:** Whoever tries to actually run either gate as documented — e.g. to
  check a case-authoring PR against the base-rate contract — gets a bare Make error with
  no pointer to the real invocation.
- **Fix sketch:** Add both as real (even if advisory, matching `check_base_rate.py`'s own
  `advisory`-mode docstring) Makefile targets, or drop the `(make ...)` parenthetical from
  all three doc lines and give the `python scripts/...` invocation instead.
- **Effort:** S (<2h)
- **Blast radius:** Makefile edit is additive only if targets are added; zero blast radius
  if the fix is doc-only.

### [CR-L13-04] README.md's "Key files" table points at a source layout that no longer exists

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md:77-85` links `npc_engine/main.py`, `npc_engine/config.py`,
  `npc_engine/engines/dialogue/`, `npc_engine/type_registry/`, `npc_engine/retrieval/`,
  `tests/scenarios/`, and `proposals/` — 7 of 10 rows. All 7 are dead: the source moved
  under `src/npc_engine/` (confirmed live at `src/npc_engine/main.py` etc.), the E2E
  scenario dir is `e2e/scenarios/` (per the `scenarios` Makefile recipe,
  `pytest e2e/scenarios/`), and design proposals live at `project-harness/proposals/`.
  `git log` shows README.md was last touched 2026-08-17 in a commit unrelated to this
  table, and the table's own prior fix commit (`e7c265e`, "SEV-34 fix stale README Quick
  Start") only fixed the Quick Start section below it, not this table.
- **Cost of inaction:** A reader using the README as a map of the codebase (its stated
  purpose) gets 7 broken links out of 10, with no signal that the whole file predates a
  layout migration.
- **Fix sketch:** Prefix the five `npc_engine/...` links with `src/`, change
  `tests/scenarios/` → `e2e/scenarios/`, change `proposals/` → `project-harness/proposals/`.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-05] README.md "What's next" describes finished or archived work as open TODOs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md:38` — "`tone_judge` matcher is a stub; wire in LLM-as-judge" —
  but `evals/matchers.py:272` (`_eval_tone_judge`) is a real, wired YES/NO LLM-judge call
  driven by `prompts/eval/tone_judge.yaml` (a genuine 25-line judge-prompt template used
  by both `evals/matchers.py` and `e2e/helpers/llm_judge.py`). `README.md:34` — "wire in a
  lightweight graph lookup to pick the right archetype YAML" — but
  `dialogue_handler.py:220,384` already does exactly that:
  `archetype = await self._dialogue_repo.get_npc_archetype(request.npc_id) or "default"`.
  `README.md:32-33` present `proposals/prompt_inventory.md` and
  `proposals/delta_log_options.md` as live, pending-approval design docs — both are filed
  under `project-harness/archive/stale-2026-06/`, i.e. the project's own process already
  closed them out.
- **Cost of inaction:** A reader (contributor, evaluator, licensing prospect reading the
  README as a maturity signal) undercounts what's actually built and may re-propose or
  re-implement work that already shipped.
- **Fix sketch:** Delete all four bullet points from "What's next"; regenerate the section
  from the current `project-harness/ROADMAP.md` "Next" line instead of hand-maintaining a
  second, independent TODO list.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-06] `check_harness_honesty.py`'s H3 check references a file that was archived, making it permanently inert

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_harness_honesty.py:23` sets
  `NEXT_SESSION = REPO_ROOT / "project-harness" / "NEXT_SESSION.md"`; `_read()` (line 30)
  returns `""` when the path is missing. `find . -iname NEXT_SESSION.md` shows the only
  copy lives at `project-harness/archive/stale-2026-06/NEXT_SESSION.md`. The H3 regex
  (`_NO_OPEN_ISSUES_RE`, line 26) can only match non-empty text, so it can never fire
  against `""`. Ran both `python scripts/check_harness_honesty.py` and `--strict`; both
  print identical output ("OK - 67 open ticket(s)...") and exit 0 — confirming H3 (and,
  independently, H1 and H2, per §2 above) contribute nothing to either mode today.
- **Cost of inaction:** The `--strict` flag documented as making warnings "fail too"
  (module docstring, line 15) currently cannot demonstrate that behavior on this repo —
  anyone relying on `--strict` in CI to catch a genuine "docs say no open issues" drift
  gets silent pass-through.
- **Fix sketch:** Either restore `project-harness/NEXT_SESSION.md` as a maintained file
  the H3 check can act on, or remove the dead H3 branch and its module-docstring
  reference to it.
- **Effort:** S (<2h)
- **Blast radius:** Touches `make check-harness` / `check-harness` CI job; low risk since
  it's advisory-only today regardless.

### [CR-L13-07] HARNESS_GATES.md's "one command" table is missing 9 of the 14 gates `make check` actually runs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `HARNESS_GATES.md:11` states `make check` = `lint + check-rules +
  type-ratchet + check-harness + test-cov(80% floor)` — 5 components, and the gates table
  below it (lines 19-26) lists 6 rows total (adding Contracts). The real `check:` recipe
  (`Makefile:200`) has 14 dependencies: `lint check-rules check-evals-rules check-layers
  check-docstrings type type-evals check-harness check-human-gates check-test-quality
  check-conservation check-label-survival test-cov test-cov-evals`. Undocumented in the
  gates table: `check-evals-rules`, `check-layers`, `check-docstrings`, `type-evals`,
  `check-human-gates`, `check-test-quality`, `check-conservation`, `check-label-survival`,
  `test-cov-evals` (75% floor on `evals/`, distinct from the 80% floor on the main suite).
  Also the doc names `type-ratchet` as the type gate, but `check` calls `type` (plain
  `mypy src/`, hard-fail) — `type-ratchet` (`scripts/mypy_ratchet.py`) is a separate target
  `make check` never invokes.
- **Cost of inaction:** A developer reading this table as the authoritative description of
  what `make check` enforces will not know 9 real, currently-passing gates exist, and will
  misdescribe the type gate's actual mechanism (hard-fail vs. ratchet) to anyone who asks.
- **Fix sketch:** Regenerate the table from `grep '^check:' Makefile`'s dependency list;
  either document all 14 or explicitly scope the doc to "the gates added in this PR" with
  a pointer to the Makefile for the current full list.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only; the underlying `make check` behavior (confirmed GREEN
  via a full run, exit 0, 1007 passed / 1 skipped) is unaffected.

### [CR-L13-08] CHANGELOG.md is 96 commits and 13 days stale, and still points at the pre-rename `project/` tree

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Last touched `5bfa528` (2026-08-14); HEAD `d46ae42` (2026-08-27) is 96
  commits later, including `feat` commits (`d7b7c8b`, `72594dd`, `96d83eb`, `4078c37`)
  that CONTRIBUTING.md's own commit-type taxonomy would expect logged. Every path under
  the live `## [Unreleased]` section prefixed `project/` (`project/STATUS.md`,
  `project/PATTERNS.md`, `project/proposals/*`, plus `docs/LLM_GENERATION_GUIDE.md`) is
  dangling — none of those paths exist post the `project/` → `project-harness/` rename.
  No git tags exist and no dated version section has ever been added, despite the file's
  "Keep a Changelog" header claim.
- **Cost of inaction:** Progressively less useful as a change-history artifact; a reader
  trying to correlate a shipped fix with its changelog entry finds nothing for the last
  13 days of work.
- **Fix sketch:** Fix the dangling `project/*` paths in the existing entries (they're
  historically describing real events, just at the wrong now-renamed path); add entries
  for the 96 missing commits or explicitly deprecate the file with a pointer to
  `git log` / `project-harness/ROADMAP.md` if it's not going to be kept current.
- **Effort:** S (<2h) for the path fixes; M (<1d) to backfill 96 commits' worth of entries.
- **Blast radius:** None.

### [CR-L13-09] `docs/API.md` is missing the 6 newest live routes, including a whole undocumented `/setup/*` surface

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** Live `/openapi.json` (132 paths, fetched from the running server) vs. 120
  normalized route mentions extracted from `docs/API.md`: `/setup/config`,
  `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate`
  (none of which appear in the doc, and none appear in the 2026-06-24 committed
  `live_openapi.json` snapshot either — genuinely new surface), plus two undocumented
  parameter variants of already-documented routes
  (`/v1/admin/factions/{faction_id}/standings/{p}`,
  `/v1/admin/schedules/character/{p}/at`). Severity is capped at MEDIUM because
  `docs/API.md:15-16` explicitly disclaims being the complete contract and points readers
  at the live `/openapi.json` as source of truth — this is an incomplete guide, not a
  false "this is everything" claim.
- **Cost of inaction:** A game-client integrator reading only the curated guide won't know
  the `/setup/*` config-validation endpoints or the vector-store admin/debug routes exist.
- **Fix sketch:** Add a "Setup" and a "Vector store" row/section covering the 4 genuinely
  new routes; add the two missing parameter variants to their existing route rows.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-10] EVAL_STRATEGY.md is a 3-month-old, uncorrected duplicate of docs/EVAL_METHODOLOGY.md

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `project-harness/EVAL_STRATEGY.md` last touched 2026-05-28 (commit
  `82a22af`), while `docs/EVAL_METHODOLOGY.md`, `docs/CASE_SET_POLICY.md`, and the whole
  EVAL-P## program have been built out and actively edited through 2026-08-27. It still
  references `seeds/world/seed_tavern_world.py` and `seeds/world/run_eval_world.py`
  (actual: `seeds/worlds/`, and `run_eval_world.py` doesn't exist anywhere) and
  `make eval-full` (doesn't exist). No banner marks it superseded or historical, and no
  in-scope doc cross-references it as deprecated.
- **Cost of inaction:** A reader who finds this file before `docs/EVAL_METHODOLOGY.md`
  (alphabetically or via search) gets three broken commands/paths and an eval strategy
  description that predates the current base-rate/case-adversary/golden-set machinery
  entirely.
- **Fix sketch:** Add a one-line "superseded by docs/EVAL_METHODOLOGY.md, kept for
  historical rubric text only" banner at the top, or move it into
  `project-harness/archive/` alongside the other stale-2026-06 files it's contemporary with.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-11] Root `live_openapi.json` snapshot is 64 days stale relative to the running server

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Committed `live_openapi.json` (repo root) is dated 2026-06-24 (file mtime)
  and has 128 paths; the live server's `/openapi.json` has 132 (the same 4 new routes
  identified in CR-L13-09: `/setup/config`, `/setup/validate`,
  `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate`). Nothing in the
  in-scope docs treats this file as authoritative (docs/API.md correctly points at the
  live endpoint instead), so this is a stale committed artifact rather than a doc lying to
  a reader — flagged LOW because its only real risk is someone diffing against it by hand
  and drawing a wrong conclusion.
- **Cost of inaction:** Low — an occasional false negative/positive in an ad hoc API diff.
- **Fix sketch:** Either regenerate it as part of a pre-commit/CI step, or delete it if
  nothing consumes it programmatically (check for consumers before removing).
- **Effort:** S (<2h)
- **Blast radius:** Check whether any test or script reads this file before deleting it.

---

## L3 — Metrics & eval validity

# CR-L03 — Metrics & eval validity

Lens L3 of the 16-lens review. Branch `eval-ab-context-arms`, HEAD `d46ae42`, audited 2026-08-27.
Read-only. Every number below was produced by a command run in this session or traced to a
`file:line`. Neo4j is not published to the host, so no host-side Cypher was attempted; nothing in
this lens required it.

**Verdict in one line:** the eval instrument is unusually well-reasoned and unusually honest about
its own limits, and the single number the product is sold on — the anti-hallucination guard rate —
is **beaten by a fixed string**. That is a CRITICAL.

---

## Required measurements

### 1. Judge↔human agreement rate

**Measured, and it is the one thing in this repo that is genuinely instrumented.** Human ground
truth exists: `evals/calibration/labels_v1.jsonl`, 393 adjudicated rows.

```
$ python -m evals calibrate
Loaded 393 rows; 393 adjudicated.
Family-wise disclosure: 8 simultaneous intervals (4 scorer(s) × 2 axes).
  Nominal: 95% per-interval CI (α=0.050). FWER: 1−0.95^8 = 0.337.
```

| scorer | n rows | n clusters | Cohen's κ | 95% cluster-bootstrap CI | policy tier | CI excludes chance (κ=0)? |
|---|---:|---:|---:|---|---|---|
| `tone_judge` | 135 | 45 | **0.849** | **[−0.010, 1.000]** | PUBLISHABLE | **no** |
| `affirms_judge` | 135 | 45 | 0.530 | [0.000, 1.000] | REFUSED (restricted) | **no** |
| `anti_hallucination_grounded` | 48 | 16 | 1.000 | undefined at boundary | published | **undefined** |
| `refusal_judge` | 75 | 25 | 0.247 | [−0.123, 0.703] | REFUSED (hidden) | **no** |

**Not one of the four scorers has a κ interval that excludes chance agreement.** Two are refused
outright by the project's own policy. The one that is published (`tone_judge`, κ = 0.849) has a
lower bound of −0.010.

Provenance caveats, all confirmed:

- There is exactly **one human rater** (`pre_labeller_model == "human-lohann"` on 393/393 rows;
  `human_labeller == ""` on 393/393). `pre_label == human_verdict` on **393/393** rows, so the
  "secondary axis" is the rater compared to themselves. The harness detects this and refuses to
  print a number for it (`evals/calibration_records.py:49-58`) — correct behaviour, and it means
  **inter-human agreement is unmeasured and unmeasurable from the shipped artifact**.
- `evals/calibration/oracle/labels_oracle.jsonl` is 21 rows of `pre_labeller_model:
  "oracle-matrix-v1"`, all with `human_verdict: null` — rule-based, not a second rater.
  `evals/calibration/mock_labels.jsonl` (920 rows) is random and stamped `mock-random-v1`.
  `evals/synthetic_label_guard.py` correctly refuses to let either overwrite the real file.
- The labels describe generation `k3_73e6c36` (`gen_id` on 393/393 rows), **not** the current
  `k3_77688e7_regen1`. See CR-L03-05.
- 393 of 921 rows in that generation are labelled. `make check-label-survival` prints
  `New (unlabelled) rows in the candidate transcript: 528` and still exits 0 / `FROZEN`.

**What the judge scores are therefore worth:** `tone_judge` and `anti_hallucination_grounded`
verdicts are usable as *evidence* on a single-scorer scope; `affirms_judge` and `refusal_judge`
verdicts are, by the repo's own `docs/SCORER_TRUST_POLICY.md`, not quotable at all — and they are
quoted anyway, inside the composite guard rate (CR-L03-02).

### 2. Base rate per case set — what a null system scores

The null system used is `scripts/hedge_responder_probe.CANNED_HEDGE`: one fixed string, no graph,
no LLM, no memory. Judge verdicts for it were **measured live** against `mixtral:8x7b` this session
(`refusal_judge` → PASS, guard tone rubric → PASS, guard lore rubric → PASS after
`matchers._eval_affirms_judge`'s polarity inversion at `evals/matchers.py:324-327`). Deterministic
kinds were scored through the shipped `matchers.evaluate`; AH-fixture grounding was scored through
the shipped `any(sub.lower() in text.lower())` at `evals/anti_hallucination_runner.py:80-83`.

| case set | n | **null-system base rate** | engine (measured, `k3_77688e7_regen1`) | gate / threshold | verdict |
|---|---:|---:|---:|---|---|
| Guard — `case_adv_*` + `case_neg_*` (YAML) | 37 cases / 222 slots | **1.000** (37/37, 222/222) | — | none | **measures nothing** |
| Guard — `ah_demo_*` (JSON fixture) | 41 cases | **0.902** (37/41) | — | none | measures nothing |
| **Guard battery, combined** | **78 cases** | **0.949 (74/78)** | **0.897 (70/78)** | none | **null beats engine** |
| Capability `case_pos_*` (expectation slots) | 46 slots | 0.130 (6/46) | — | hedge rate < 0.30 | gate met |
| Capability `case_pos_*` (cases that ran) | 16 cases | **0.375** (6/16 hedge-passable) | 0.625 [0.386, 0.815] | none | floor ≈ measurement |
| `schema` | 186 rows | 1.000 | 1.000 | band [0.55, 0.85] | constant |
| `min_length` | 111 rows | 1.000 | 1.000 | band | constant |
| `in_set` | 18 rows | 1.000 | 1.000 | band | constant |
| `range` | 9 rows | 1.000 | 1.000 | band | constant |
| `keyword_none` | 207 rows / 36 exprs | 0.889 bland text; **18/36 exprs are guaranteed passes** | 0.957 | band | 50% inert |
| `keyword_any` | 51 rows | 0.080 | 0.647 | band | **the only informative family** |

Supporting measurements:

```
$ python scripts/check_base_rate.py evals/generations/k3_77688e7_regen1
  ALL  n=975  rate=0.943  above_band          (target band [0.55, 0.85], mode: advisory)
  9 of 10 families out of band; 4 families flagged "<- CONSTANT: no variance to move"
```

```
$ make hedge-probe
  capability: 6/46  rate 0.130  (gate: < 0.30)   verdict: GATE MET
  cases the hedge passed: case_pos_aldric_trade_disruption, case_pos_captain_sorn_war_knowledge,
    case_pos_mira_gossip_hedging, case_pos_mira_war_gossip_tokens,
    case_pos_old_henryk_war_rumor_tokens, case_pos_world_blight_guard
```

All six hedge-passable cases are among the 16 that produced the published capability rate.

Dead-keyword measurement, recomputed against the **newest** 975-response corpus (the shipped
`scripts/check_dead_keywords.py` reads the stale one):

```
keyword_none expectations: 36   fully-dead (guaranteed pass): 18 = 50.0%
keywords total: 264            dead: 210 = 79.5%
```

### 3. n and statistical power for every numeric eval gate

Computed with the repo's own model, `evals/mde.py`, at its own recorded discordance
(`implied_discordance_rate(mde=0.064, n_pairs=78)` → p_d = 0.0407) and its own recorded per-criterion
Fleiss κ (`evals/mde.py:93-97`). `headroom` = 1 − measured base rate: the largest true effect that
is physically possible on that family.

| gate / metric | code | n | threshold | observed MDE | **true MDE** (κ-corrected) | headroom | can it ever fire? |
|---|---|---:|---|---:|---:|---:|---|
| guard rate regression | `regression_gate.check_regression` | **78** | `cand.ci_high < base.rate` | 6.4 pp | 6.4–28.4 pp | 10.3 pp | only for `tone_judge` slots |
| capability rate regression | same | **16** | same | — | — | 37.5 pp | no (CI width 0.43) |
| `tone_judge` arm effect | `mde.arm_pairing_mde` | 135 | — | 4.86 pp | **4.86 pp** | 7.4 pp | marginally |
| `affirms_judge` arm effect | same | 135 | — | 4.86 pp | **17.25 pp** | 5.9 pp | **no** |
| `refusal_judge` arm effect | same | 75 | — | 6.53 pp | **29.01 pp** | 8.0 pp | **no** |
| inconclusive-rate gate | `DEFAULT_MAX_INCONCLUSIVE_RATE = 0.20` | 103 | > 0.20 | — | — | measured 0.000 | yes |
| instrument gate (panel κ) | `instrument_gate.py:125` | 345 items | `cand.ci_high < base.kappa` | — | — | CI [0.413, 0.733] | yes, but no baseline |
| base-rate band | `base_rate_contract.py:32-33` | 975 | [0.55, 0.85] | — | — | measures 0.943 | **advisory, exits 0** |
| hedge gate | `hedge_responder_probe.py:53` | 46 | < 0.30 | — | — | measures 0.130 | yes |
| seed reproduction | `evals/seed_reproduction.json` | 145 | ≥ 0.95 | — | — | measures 0.628 | **NOT_MET, ungated** |
| scorer trust | `scorer_trust_policy.py:74` | 48–135 | κ ≥ 0.60 (point est.) | — | — | — | yes, ignores CI |

`docs/STATISTICS_POLICY.md`'s own requirements versus what the code does:

| STATISTICS_POLICY claim | code | verdict |
|---|---|---|
| "2 × S simultaneous bootstrap intervals" per run; FWER 0.337 at 4 scorers | report prints `8 simultaneous intervals (4 scorer(s) × 2 axes)` then prints `N/A (single rater)` for all four secondary axes | **only 4 intervals exist**; the disclosed family size and Holm α* = 0.0063 are both wrong (conservative, but the disclosure is false) |
| bootstrap resamples case **clusters**, not rows | `evals/calibration.py:469` resamples clusters | correct |
| no pooled κ across scorers is printed | one matrix per scorer, confirmed in output | correct |
| slot-level cherry-picking unsupported; use case-level McNemar | `paired_stats.mcnemar_exact` exists and is used | correct |
| `BOOTSTRAP_RESAMPLES = 2000` | `evals/calibration.py:41` | correct |

The policy never sets a minimum n and defers that to `EVAL_STRATEGY.md`
(`docs/SCORER_TRUST_POLICY.md:75`), which `project-harness/CODEBASE_REVIEW.md:683` records as
**"Abandoned (91 days)"**. Sample-size adequacy therefore has no owner anywhere in the repo — which
is why the table above had to be computed here for the first time.

### 4. Leakage — case authoring vs scoring

Traced end to end. **Substantially clean**, with two documented residuals.

| path | shares a model? | shares a prompt? | shares an author? | evidence |
|---|---|---|---|---|
| judge vs generator | **enforced separate** — `JudgeModelCollisionError` raised at import | no | n/a | `evals/judge_config.py:114-127`; generation `qwen2.5:7b`, judge `mixtral:8x7b` |
| judge panel vs generator | one seat (`qwen2.5:14b`) is the **same family** as `qwen2.5:7b` | no | n/a | `evals/judge_config.py:38-44`, `:141-165` (warns, allows) |
| case adversary vs judge | **no** — adversary is Claude Opus via manual paste; judges are local Ollama | no | no | `prompts/eval/case_adversary.yaml:6-10`; `evals/case_adversary.py:36-42` |
| case adversary vs labeller | both Claude Opus, but different prompts and different objects (cases vs responses); the module states the boundary explicitly | no | yes (both Opus) | `evals/case_adversary.py:20-25`; `evals/calibration/OPUS_LABEL_PROMPT.md` |
| case adversary vs echo-resistance test | **shares the scorer and the reference hedge** (`hedge_responder_probe.score_case`, `CANNED_HEDGE`) | n/a | n/a | `evals/case_adversary.py:69-73` — declared deliberate, so the adversary cannot certify a case the ratchet would fail |
| human labeller vs case author | the 393 human verdicts and the case YAML were both produced in this repo by the same maintainer + agent | — | yes | unavoidable at this team size; **not** mitigated anywhere |

Measured check of the same-family concern (does `qwen2.5:14b` go easy on `qwen2.5:7b` output?):

| pair | n | raw agreement | Cohen's κ |
|---|---:|---:|---:|
| `llama3.1:8b` vs `mixtral:8x7b` | 345 | 0.945 | 0.531 |
| `llama3.1:8b` vs `qwen2.5:14b` | 345 | 0.942 | 0.495 |
| `mixtral:8x7b` vs `qwen2.5:14b` | 345 | 0.957 | 0.693 |

Per-judge pass rate: `llama3.1:8b` 0.954, `mixtral:8x7b` 0.922, `qwen2.5:14b` 0.925. The
same-family seat is **not** measurably more lenient. No leniency leakage detected. The
`mixtral`/`qwen14b` pair is the most-agreeing pair, which under 2-of-3 consensus does give those
two an effective veto over `llama3.1:8b` — worth watching, not a finding today.

### 5. Every policy document: does the code do what it says?

**131 normative claims checked, 38 diverge.** Full per-doc tables below; the load-bearing ones are
in the findings.

| doc | claim | implemented? | divergence at |
|---|---|---|---|
| SCORER_TRUST_POLICY | "Report generators **must** call `check_publication` before including a scorer's rate in any output" | **NO** | `evals/report.py:1-16` imports `summary` + `retrieval_summary` only; no call site outside `calibration.py` / `dashboard/headline.py` |
| SCORER_TRUST_POLICY | policy is "encoded as a function so no report path can bypass it programmatically" | **NO** | the only path that writes the published report bypasses it |
| SCORER_TRUST_POLICY | κ tiers 0.40 / 0.60 | YES | `evals/scorer_trust_policy.py:22-23` |
| EVAL_METHODOLOGY §3 | "the trust policy consults **the interval**, not just the point estimate" | **NO** | `evals/scorer_trust_policy.py:84-94` — `interval` is a parameter and is never read; `dashboard/headline.py:140` passes a fabricated `(0.0, 0.0)` |
| EVAL_METHODOLOGY §5 | "the report substitutes the EVAL-P11.1 refusal message in place of the rate" | **NO** | same — `report.py` has no refusal path |
| EVAL_METHODOLOGY §5 | no rule covers a **composite** rate built from 4 scorers of mixed tier | **GAP** | guard rate 0.897 mixes `tone_judge`+`affirms_judge`(REFUSED)+`refusal_judge`(REFUSED)+deterministic |
| EVAL_METHODOLOGY anti-metric | "The LLM judge is a single model… A second judge was considered (DEC-143) but **not implemented**" | **STALE** | a 3-model panel ships: `judge_config.py:38-44`, `evals/judge_panel.py`, `run_status.json:judge_panel` |
| EVAL_METHODOLOGY §4 | quotes `evaluated_cases = total_cases - skipped_cases` | STALE | actual `evals/summary.py:199` is `len(guard)+len(cap)+len(excluded)` |
| CASE_SET_POLICY | base-rate band "measured and gated by `scripts/check_base_rate.py` (`make check-base-rate`)" | **NO** | `make check-base-rate` does not exist; `grep -n base-rate Makefile` → no match |
| CASE_SET_POLICY | advisory "is a declared parameter, not a disabled check" | PARTIAL | true of the exit code; false in effect — no target, no CI, never run |
| CASE_SET_POLICY | measured table (0.949, 4 constant families) | YES | reproduced exactly this session |
| CAPABILITY_CASES | "`make check-engine-coverage` fails when a unit exists with no classification row" | **NO** | target absent from the Makefile |
| CAPABILITY_CASES | echo/hedge resistance enforced by `test_capability_echo_resistance.py` | YES | file present, ratchet real |
| REGRESSION_POLICY | the whole gate | **VACUOUS** | `evals/trend/trend_v1.jsonl` holds **1 row**, already incomparable (below) |
| REGRESSION_POLICY | quotes `refusal_judge` κ 0.225 / `affirms_judge` 0.282 | **inconsistent** | calibration prints 0.247 / 0.530; panel Fleiss prints 0.422 / 0.519. Three different κ for the same scorer circulate in the docs |
| STATISTICS_POLICY | family size = 2 × S | **NO** | S secondary axes are all `N/A (single rater)`; 4 intervals exist, 8 are disclosed |
| SEQUENCE_STATS_POLICY | "Cochran's Q … Not yet shipped — EVAL-P14" | STALE | shipped at `evals/sequence_order_effect.py:70-96` |
| SEQUENCE_STATS_POLICY | order-effect check runs at FULL fidelity as a diagnostic | **NO** | `evals/sequence_rates.py:158-160` computes it only when some scenario is PARTIAL |
| SEQUENCE_STATS_POLICY | "p-value below 0.05 is reported as a significant order effect" | **NO** | no 0.05 constant anywhere; p is printed raw and never classified |
| SEQUENCE_STATS_POLICY | §4.3 FULL-fidelity warning block | **NO** | string does not exist in `evals/sequence_*.py` |
| SEQUENCE_STATS_POLICY | fidelity read per repetition from a live receipt | **NO** | `evals/sequence_reset.py:75-85` re-emits one static tuple from `evals/reset_fidelity.json` k times |
| SEQUENCE_STATS_POLICY | trend alert suppressed at PARTIAL | **NO (unenforced)** | no `fidelity` reference in `trend_store.py` / `trend_row_builder.py` / `regression_gate.py` |
| RELEVANCE_WEIGHTS | `RelevanceWeights` lives in `npc_engine/schema/llm_config_models.py` | **NO** | it is `src/npc_engine/schema/context_config_models.py:59`; doc link broken |
| RELEVANCE_WEIGHTS | default shipped in `config/llm_config.yaml` | **NO** | path is `src/npc_engine/config/llm_config.yaml` |
| RELEVANCE_WEIGHTS | balanced default 0.20/0.20/0.15/0.20/0.15/0.10 | **STALE-NUMBER** | `src/npc_engine/config/llm_config.yaml:51-56` → recency **0.30**, proximity **0.20**, quest **0.10**, `explicit` absent |
| RELEVANCE_WEIGHTS | active weights logged at startup in the quoted form | PARTIAL | `src/npc_engine/main.py:149` logs the model object |
| RELEVANCE_WEIGHTS | tie-break `score DESC, node_type ASC, node_id ASC` | PARTIAL | 4th key `item.key` at `context_relevance_engine.py:95-102` |
| REASONING_DIMENSIONS | `evals/runner.py` keys off `case_pos_` | **NO** | no `case_pos` string in `evals/runner.py`; only guard prefixes at `:37` |
| REASONING_DIMENSIONS | D1 `relevant_node_ids` "names **the one** grounded node" | **NO** | all 8 `case_pos_evk_*` list 3 ids |
| REASONING_DIMENSIONS | D1 coverage: each of KNOWS_ABOUT/BELIEVES/REMEMBERS/PURSUES ≥ 1 evk per world | **NO** | zero `case_pos_evk_*` grounded in `KNOWS_ABOUT` in any world; demo world has zero evk cases |
| REASONING_DIMENSIONS | all five "Coverage rule" clauses | **UNENFORCED** | `tests/unit/evals/test_capability_coverage.py:26-50` is an NPC-id ratchet; contains no dimension prefix |
| REASONING_DIMENSIONS (via `variance_scorer.py:9`) | `make variance-score` | **NO** | target absent |
| ENGINE_EVAL_COVERAGE | "Gated by `scripts/check_engine_coverage.py` (`make check-engine-coverage`)" | **NO** | target absent; gate not in `make check` |
| ENGINE_EVAL_COVERAGE | 18 dialogue_observable / 16 state_observable / 10 not_observable of 44 | YES (re-measured, exit 0) | `scripts/check_engine_coverage.py` |
| ENGINE_EVAL_COVERAGE | `quest` → `active_quest` pinned and used by Rule 11 | **CONTRADICTED in-code** | `src/npc_engine/retrieval/context/context_slots.py:146-147` says "Pinned at 89 and never serialized" |
| RESET_FIDELITY | "the Wilson interval at `evals/sequence_runner.py:160` … computed unconditionally today" | **STALE** | that line is `k=k,`; gating landed at `evals/sequence_fidelity.py:117`; ISSUE-143 is `[FIXED]` |
| RESET_FIDELITY | every measured number (PARTIAL, 10 survivors, 6 unobservable, 56 ms median) | YES | `evals/reset_fidelity.json` matches row-for-row |

### 6. Determinism / reproducibility

| question | answer | evidence |
|---|---|---|
| is the generation seeded? | yes, and the seed is recorded | `evals/generations/k3_77688e7_regen1/meta.json` → `"seed": 20260814`, `"temperature": 0.15`, `"top_p": 0.95` |
| same seed → same output? | **no — 62.8%** | `evals/seed_reproduction.json`: `rate_records 0.6276`, `gate 0.95`, `verdict "NOT_MET"` |
| same output → same judge score? | **no** | three identical `matchers._run_binary_judge` calls at `temperature 0.0`: `True (24.4 s)`, `True (30.6 s)`, `None/infra_failure (32.8 s, ReadTimeout)` |
| does the judge request carry a seed? | **no** | `evals/matchers.py:248` — `"options": {"num_predict": 80, "temperature": _JUDGE_TEMPERATURE}`; no `seed` key |
| is model version recorded? | **partially** | `meta.json` records `generation_model`, `judge_model`, `ollama_version`, `git_sha`, `dialogue_prompt_hash` — but `"generation_model_digest": null` and `"judge_model_digest": null`, so an `ollama pull` silently changes the instrument |
| is unseeded `random` used in scoring? | **no** | every `random.Random(...)` in `evals/` is explicitly seeded: `calibration.py:469` (seed 42), `kappa_stats.py:167` (seed 20260818), `label_sampling.py:93` (caller-supplied) |
| are repetitions stable? | **no, and it is recorded** | `run_status.json` → `repeat_flips: {records_with_flips: 19, n_records: 115}` — 16.5% of records flip verdict across k=3 |

---

## Findings

### [CR-L03-01] The guard battery is beaten by a fixed string — the anti-hallucination number is not a measurement

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** A null responder — `scripts/hedge_responder_probe.CANNED_HEDGE`, one hard-coded
  sentence, no knowledge graph, no LLM, no memory — was scored through the **shipped** scorers.
  Deterministic kinds via `matchers.evaluate`; the three LLM-judged kinds via live
  `matchers._run_binary_judge` against `mixtral:8x7b` this session (`refusal_judge` → PASS, guard
  tone rubric → PASS, guard lore rubric → PASS after the polarity inversion at
  `evals/matchers.py:324-327`); AH-fixture grounding via the shipped
  `any(sub.lower() in text.lower())` at `evals/anti_hallucination_runner.py:80-83`.

  ```
  guard cases (case_adv_* + case_neg_*): 37   null-system case pass rate: 37/37 = 1.000
  kind                n  null_pass    rate
  affirms_judge      45         45   1.000
  keyword_none       66         66   1.000
  min_length         37         37   1.000
  schema             37         37   1.000
  tone_judge         37         37   1.000
  ALL SLOTS         222        222   1.000

  AH fixture (ah_demo_*): 41 cases (25 refusal, 16 grounded)
    refusal cases passed by the hedge: 25/25 (refusal_judge measured live)
    grounded cases passed by the hedge: 12/16
    -> 37/41 = 0.902

  COMBINED GUARD BATTERY (78 cases): null = 74/78 = 0.949
  ```

  The engine, measured on the same 78 cases from the newest committed generation
  (`summary.summarize_from_dir(evals/generations/k3_77688e7_regen1)`): `guard_passes 70`,
  `guard_rate 0.8974`. The published headline is `evals/reports/20260825T231028Z.md:11` —
  "Guard (adv + neg + ah_demo_*) | 170/186 | 0.914 95% CI [0.8478–0.9530]".

  **A fixed string scores 0.949. The engine scores 0.897.** The guard battery does not
  discriminate the engine from a scripted shrug; it ranks the shrug higher.

  The project has the right instrument for exactly this and pointed it at the wrong battery:
  `scripts/hedge_responder_probe.py:71-76` (`NotACapabilityCaseError`) **refuses** to score a guard
  case, so the null baseline has only ever been measured for the 16-case capability battery — never
  for the 78-case battery that produces the published number.
- **Cost of inaction:** the product's central external claim ("persistent memory, no
  hallucination — 91.4% on adversarial turns") is false as a claim about the engine, and any studio
  that runs its own null baseline will find this in an afternoon. Every A/B, every prompt change and
  every roadmap decision taken against the guard rate since 2026-06 was taken against noise.
- **Fix sketch:** lift the `case_pos_` restriction in `hedge_responder_probe` so the probe scores the
  guard battery too, and add the null rate to the report beside the engine rate — a rate whose null
  baseline is not printed alongside it should not be printed. Then rebuild the guard battery so its
  expectations can fail: replace the 18 fully-dead `keyword_none` lists and the three constant
  families with assertions a hedge cannot satisfy.
- **Effort:** L
- **Blast radius:** `evals/cases/case_neg_*.yaml`, `case_adv_*.yaml`, `anti_hallucination_demo.json`,
  `evals/report.py`, `evals/summary.py`, the README's headline number, and every trend row.

### [CR-L03-02] `check_publication` ignores the interval it is handed, and the report generator never calls it

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `evals/scorer_trust_policy.py:65-94` — `check_publication(scorer, kappa, interval)`
  branches only on `kappa`; `interval` is stored in the refusal and never read. `docs/EVAL_METHODOLOGY.md`
  §3 states "the trust policy (§5) consults the interval, not just the point estimate."
  `evals/dashboard/headline.py:140` passes `(0.0, 0.0)` — a fabricated interval — because it makes no
  difference. Consequence, from `python -m evals calibrate`: `tone_judge` at κ = 0.849 with
  **95% CI [−0.010, 1.000]** is graded PUBLISHABLE; its interval does not exclude chance.

  Separately, `docs/SCORER_TRUST_POLICY.md` says "Report generators **must** call `check_publication`
  before including a scorer's rate in any output." `evals/report.py:1-16` imports only `summary` and
  `retrieval_summary`; `grep -rn check_publication evals/` returns call sites in
  `calibration.py:718,759` and `dashboard/headline.py:140` and nowhere else. The file that writes
  `evals/reports/*.md` — the published artefact — has no policy path at all, and it prints a guard
  rate composed of `affirms_judge` (REFUSED, restricted) and `refusal_judge` (REFUSED, hidden).
- **Cost of inaction:** the one mechanism that exists to stop an untrustworthy number reaching a
  report does not sit on the path to the report. Every published guard/capability rate is
  unchecked, today.
- **Fix sketch:** make `check_publication` refuse when `interval[0] < HIDDEN_THRESHOLD` regardless of
  the point estimate, and add a composite rule — a rate compounded from scorers of mixed tier
  inherits the lowest tier. Call it from `evals/report.py` before the guarantee table is rendered.
- **Effort:** M
- **Blast radius:** `evals/report.py`, `evals/summary.py` formatting, `dashboard/headline.py`, the
  shipped reports, `docs/SCORER_TRUST_POLICY.md`.

### [CR-L03-03] The judged half of the battery cannot resolve any effect that is physically possible

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** computed with the repo's own `evals/mde.py` at its own recorded inputs
  (`implied_discordance_rate(mde=0.064, n_pairs=78)` → p_d = 0.0407; κ from `evals/mde.py:93-97`):

  ```
  criterion             kappa    n   obs_MDE_pp  true_MDE_pp
  tone_judge            1.000  135        4.86         4.86
  affirms_judge         0.282  135        4.86        17.25
  refusal_judge         0.225   75        6.53        29.01
  ```

  Against the measured base rates in the same generation (`scripts/check_base_rate.py`): `affirms_judge`
  0.941 → **5.9 pp of headroom** against a 17.25 pp true MDE; `refusal_judge` 0.920 → **8.0 pp of
  headroom** against a 29.01 pp true MDE. Two of the three LLM judges cannot detect any improvement
  that is arithmetically possible on their own family. `tone_judge`'s κ = 1.000 is not reassurance:
  `evals/mde.py:99-102` records that it comes from "unanimous 135/135 — that is a statement about
  variance to move, not about the criterion being well designed."
- **Cost of inaction:** every A/B arm the current branch (`eval-ab-context-arms`) is built to run
  will return "no significant difference" whatever the engine does, and that null result will be
  read as evidence about the engine. Ten-hour paired generations for a foregone conclusion.
- **Fix sketch:** `evals/mde.py` already computes this; wire it into a preflight that refuses to
  start a paired generation whose `true_mde_pp` exceeds `1 − base_rate` for the criterion, and print
  the refusal with the two numbers. Then fix the inputs (harder cases, more n) rather than the gate.
- **Effort:** S to wire the preflight; L to fix the inputs.
- **Blast radius:** `evals/arm_probe*.py`, `scripts/Run-EvalHarness.ps1`, the EVAL-P25..P31 plan.

### [CR-L03-04] 1,522 lines of the newest gate layer are reachable from no `make` target and no CI job

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:**
  ```
  $ for t in check-engine-coverage review-cases check-base-rate check-variance; do
        grep -qE "^$t:" Makefile && echo "$t EXISTS" || echo "$t MISSING"; done
  check-engine-coverage    MISSING from Makefile
  review-cases             MISSING from Makefile
  check-base-rate          MISSING from Makefile
  check-variance           MISSING from Makefile
  ```
  Each is named as its own entry point by the code or the docs it belongs to:
  `scripts/check_base_rate.py:12` ("Used by: `make check-base-rate`"),
  `docs/CASE_SET_POLICY.md` base-rate section, `docs/ENGINE_EVAL_COVERAGE.md:3-4`,
  `evals/case_adversary.py:14` ("Used by: `make review-cases`"), `evals/variance_scorer.py:9`
  (`make variance-score`). Line counts: `check_base_rate.py` 216 + `base_rate_contract.py` 170 +
  `check_engine_coverage.py` 272 + `engine_coverage_contract.py` 152 + `case_adversary.py` 292 +
  `case_adversary_contract.py` 174 + `variance_scorer.py` 246 = **1,522**.

  Worse, `.github/workflows/ci.yml` runs `make lint`, `check-rules`, `check-layers`, `type`,
  `check-harness`, `test-v13-*`, `test-cov*`, `check-contracts`, `check-contract-sync`,
  `test-v14-*` — and **not one eval-validity gate**: no `check-conservation`, no
  `check-label-survival`, no `check-test-quality`, no `check-evals-rules`, no `type-evals`, no
  `check-dead-keywords`. `make check` itself is never invoked by CI.
- **Cost of inaction:** 20,141 lines of instrument, zero of it enforced on any commit. The gates
  written in the last three commits will rot before they are ever run; the base-rate breach
  (0.943 vs [0.55, 0.85]) is already invisible.
- **Fix sketch:** add the four missing targets, add the eval gates to `make check`, and add a
  single `make check` step to `ci.yml`. Flip `DEFAULT_ENFORCEMENT` to `BLOCKING` only after
  EVAL-P26 as `scripts/base_rate_contract.py:42` already says.
- **Effort:** S
- **Blast radius:** `Makefile`, `.github/workflows/ci.yml`. Expect CI to go red immediately —
  that is the point.

### [CR-L03-05] The trend/regression stack has never made a comparison, and its sole row is already incomparable

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -l evals/trend/trend_v1.jsonl` → **1**. `docs/REGRESSION_POLICY.md` specifies a
  baseline walk-back, a `ComparabilityKey`, a one-sided CI rule, three exit codes and a separate
  instrument verdict; `evals/regression_gate.py` + `instrument_gate.py` + `baseline_selection.py` +
  `comparability.py` + `trend_store.py` + `trend_row_builder.py` = **1,141 lines**, plus
  `scripts/record_trend_and_gate.py` (168). With one row there is nothing to compare, so
  `select_baseline` refuses (exit 2) unless `--allow-no-baseline` is passed.

  And the one row is already dead:
  ```
  $ python -c "... run_config.resolve_harness_version(cases_dir=evals/cases, ...)"
  current harness_version:   21dcfa8dbc86
  trend row harness_version: f22f61a5d877
  comparable: False
  ```
  Adding the 30 case files on 2026-08-27 changed the hash, so the next run will refuse against the
  only baseline that exists.

  Related provenance defect: `evals/trend_row_builder.py:184-199` builds every row's
  `scorer_kappas` from `labels_path: Path = LABELS_FILE` — the one global labels file — with no
  check that the labels describe the row's generation. The row for `k3_77688e7_regen1` carries κ
  measured on `k3_73e6c36` outputs (`labels_v1.jsonl` `gen_id` on 393/393 rows;
  `golden_set_version` `e8b1c745c1e3` vs the run's `6871ce3e686b`). A reader takes those κ as this
  run's instrument reliability; they are not.
- **Cost of inaction:** 1,309 lines of a gate that has produced no verdict in six weeks and cannot
  produce one until two runs land under one `harness_version`. Meanwhile the κ printed beside every
  run's rates describes a different run.
- **Fix sketch:** either (a) land two comparable runs immediately and keep the stack, or (b) delete
  it and re-derive it when there is a cadence that produces comparable runs. Independently, make
  `_scorer_kappas` refuse (or record `None`) when the labels' `gen_id` ≠ the row's `gen_id`.
- **Effort:** S for the `gen_id` guard; M–L for the decision.
- **Removes:** ~1,309 lines / 7 files, if (b).
- **Blast radius:** `scripts/Run-EvalHarness.ps1` steps 7–8, `docs/REGRESSION_POLICY.md`, DEC-191/194/197.

### [CR-L03-06] The headline aggregator still reports 78 turns for 789 verdict rows and 5 hallucinations for 28

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `summary.summarize_from_dir(evals/generations/k3_77688e7_regen1)` returns
  `guard_turns 78`, `guard_passes 70`, `hallucination_failures 5`. Counting the same directory's
  verdict files directly:
  ```
  total verdict rows: 975
  guard rows: 789
  guard failures by kind (all k=3 reps):
    affirms_judge 8, keyword_none 9, refusal_judge 6, anti_hallucination_grounded 5, tone_judge 2
  ```
  So the denominator is understated by a factor of ~10 (ISSUE-155: `verdict_sources.load_unified_rows`
  dedups on bare `record_id`, collapsing k=3), and the hallucination tally counts only
  `affirms_judge`+`keyword_none` post-dedup, excluding `refusal_judge` and
  `anti_hallucination_grounded` (ISSUE-156, `evals/summary.py:19-24`, `:253-276`). Both are logged
  **P1 (blocking)**, found 2026-08-12, still open 15 days later.

  This is not a dormant bug: `evals/trend_row_builder.py:184` calls `summarize_from_dir`, so the
  corrupted numbers are exactly what the trend row and the regression gate consume. The same
  battery is meanwhile published with three different denominators — 78 (`summarize_from_dir`),
  186 (`evals/reports/20260825T231028Z.md:11`, the live runner path), and 789 (raw rows) — and two
  different failure counts, 5 and 8.
- **Cost of inaction:** the guard rate's Wilson CI is computed at n=78 instead of n=234–789, so it
  is 1.7–3× wider than it should be, which compounds CR-L03-03 — the regression gate is made even
  less able to fire by an arithmetic bug. `make check-conservation` does not catch it because it
  audits case counts on a superseded generation (below).
- **Fix sketch:** fix ISSUE-155 and ISSUE-156 together as their own entries instruct, then add a
  conservation identity asserting `guard_turns == guard_cases × k` and a second asserting the three
  publication paths agree on the denominator.
- **Effort:** M
- **Blast radius:** `evals/verdict_sources.py`, `evals/summary.py`, every trend row, `compare.py`,
  `scripts/check_conservation.py`.

### [CR-L03-07] Two of the four eval gates in `make check` audit a superseded generation

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_conservation.py:35-37` hardcodes
  `_DEFAULT_GEN_DIR = .../evals/generations/k3_73e6c36`; `scripts/check_dead_keywords.py:31-37`
  hardcodes the same corpus. `make check-label-survival` prints
  `gen-dir …k3_73e6c36 predates EVAL-P18.1's harness_version field`. The current generation is
  `k3_77688e7_regen1` (2026-08-25). All three pass green against 2026-08-08 data.

  The conservation report also prints a false identity:
  ```
  Identity 1 [OK]: guard_cases + capability_cases == total_cases
    78 guard + 7 capability = 94 OK
  ```
  78 + 7 ≠ 94. The internal check is correct (`scripts/check_conservation.py:135` includes
  `excluded`), but the rendered line at `:236-240` omits the `excluded` term, so the audit's own
  output states an arithmetic falsehood. ISSUE-176 logs the hardcoded path; the misprinted identity
  is not logged.
- **Cost of inaction:** the canonical health gate certifies a snapshot nobody runs against, and the
  one line a reader would check is wrong on its face — which trains readers to skim it.
- **Fix sketch:** default both scripts to the newest generation directory (or require `--gen-dir`),
  and render the `excluded` term in Identity 1's line.
- **Effort:** S
- **Blast radius:** `scripts/check_conservation.py`, `scripts/check_dead_keywords.py`,
  `scripts/check_label_survival.py`, `make check` output.

### [CR-L03-08] Half the guard battery's forbidden-keyword assertions are guaranteed passes

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** recomputed against the **newest** 975-response corpus using the shipped
  `evals/keyword_matching.contains_keyword`:
  ```
  keyword_none expectations: 36   fully-dead (guaranteed pass): 18 = 50.0%
  keywords total: 264            dead: 210 = 79.5%
  fully dead: case_adv_aldric_black_market, case_adv_captain_sorn_guild_smuggling,
    case_adv_leading_betrayal, case_adv_mira_aldric_trade_figures,
    case_neg_aldric_no_military_orders, case_neg_aldric_no_threats,
    case_neg_aldric_no_troop_knowledge, case_neg_aldric_no_war_outcome,
    case_neg_captain_sorn_no_gossip_frame, case_neg_captain_sorn_no_warmth,
    case_neg_lira_no_noble_succession, case_neg_mira_no_court_politics,
    case_neg_mira_no_guild_secrets, case_neg_mira_no_tactical_details,
    case_neg_old_henryk_no_war_timeline, moderation_everyone_01/02/03
  ```
  `make check-dead-keywords` reports the same shape (237 dead terms) and **exits 0**; the Makefile
  comment at `:167-170` describes it as "a work-list", and ISSUE-157 has deferred triage of ~200 of
  them since 2026-08-14.

  The three `moderation_everyone_*` cases are the clearest instance: they forbid `gore`, `torture`,
  `pornography`, `mutilate`, `beheading`, `explicit`, `adult content` — none of which a fantasy-tavern
  NPC on `qwen2.5:7b` has ever emitted in 975 sampled responses. They are 100% pass by construction
  and contribute three rows to every base rate.
- **Cost of inaction:** these 18 expectations are the mechanism behind CR-L03-01's 1.000 null rate on
  the YAML guard set. Until they can fail, adding cases only raises Pe and lowers κ further.
- **Fix sketch:** retire any `keyword_none` list with zero corpus hits, or replace it with a
  `tone_judge`/`affirms_judge` assertion the model can actually violate. Wire
  `check-dead-keywords` to fail (not report) once triaged, pointed at the newest corpus.
- **Effort:** M
- **Removes:** ~18 expectation blocks; 3 case files (`moderation_everyone_*`) are pure subtraction.
- **Blast radius:** `evals/cases/*.yaml`, `check_dead_keywords`, every base-rate table in the docs.

### [CR-L03-09] A third of the case corpus has never been scored, and the capability headline rests on 16 cases of which 6 are hedge-passable

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** 92 cases on disk; 30 (32.6%) appear in no generation. All 30 are the `case_pos_evk_*`
  / `_cause_` / `_prov_` / `_var_` files dated 2026-08-27 — the "30 harder cases" from the last two
  commits. Newest generation `k3_77688e7_regen1` (2026-08-25) contains 103 case ids of which 16 are
  `case_pos_*`.

  The capability headline over the 16 that did run is `capability_rate 0.625`,
  `95% CI [0.386, 0.815]` (`summary.summarize_from_dir`). `make hedge-probe` names six cases a
  knowledge-free canned hedge already passes, and **all six are among those 16** — a 0.375 floor
  (ISSUE-146). A measurement of 0.625 with a CI reaching down to 0.386 sits essentially on its own
  null floor.
- **Cost of inaction:** the 30 new cases are the fix for exactly this and produce no number; the
  battery they were meant to replace continues to generate the published capability rate. Authoring
  ahead of measuring is how the last four weeks of eval work produced no change in what is known.
- **Fix sketch:** run one generation over the full 92-case set before authoring anything further;
  publish the capability rate only over cases the hedge probe cannot pass.
- **Effort:** M (one generation run)
- **Blast radius:** a new `gen_id`, a second trend row (which incidentally unblocks CR-L03-05).

### [CR-L03-10] Judge verdicts flip on wall-clock latency, and an unparseable verdict is recorded as a substantive NO

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** three identical calls to `matchers._run_binary_judge` at `temperature 0.0`, same
  text, same criteria, this session:
  ```
  0 score= True   ''                24.4 s
  1 score= True   ''                30.6 s
  2 score= None   'infra_failure'   32.8 s
    binary_judge_infra_failure model=mixtral:8x7b timeout_s=30.0 error=ReadTimeout('timed out')
  ```
  `evals/judge_config.py:DEFAULT_JUDGE_TIMEOUT_S = 30.0` sits inside the latency distribution of the
  default judge on this machine, so whether a record is scored or dropped depends on machine load.
  The request also carries no `seed` (`evals/matchers.py:245-249`).

  Separately, `evals/matchers.py:151-157`: a reply that does not begin `YES`/`NO` returns
  `(False, "unparseable verdict")` — a **fail**, not an inconclusive. `_run_binary_judge`'s own
  docstring promises `score=None` for anything that is not a real verdict; a garbled model reply
  breaks that contract silently and lands in the pass rate as a substantive NO.
- **Cost of inaction:** a run's guard rate depends on how busy the box was. `run_status.json`
  records `repeat_flips: 19/115 records` at k=3, some fraction of which is this rather than model
  sampling.
- **Fix sketch:** raise the default timeout above the measured p99 for the configured judge (or
  measure it at preflight and refuse), pass `"seed"` in the Ollama options, and route unparseable
  replies to `score=None` with one bounded retry.
- **Effort:** S
- **Blast radius:** `evals/judge_config.py`, `evals/matchers.py`, `evals/judge_panel.py`, and the
  inconclusive-rate gate's threshold.

### [CR-L03-11] Reproducibility is measured at 0.628 against a 0.95 gate, recorded NOT_MET, and gated by nothing

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `evals/seed_reproduction.json` — `"rate_records": 0.6276`, `"rate_calls": 0.625`,
  `"n_records": 145`, `"gate": 0.95`, `"verdict": "NOT_MET"`, `"measured_at": "2026-08-14"`,
  `"generation_model_digest": null`, `"ollama_version": "0.32.9"`. The current generation records
  `"ollama_version": "0.32.15"` — the runtime moved and the measurement was not repeated.
  `grep -rn seed_reproduction Makefile .github/workflows/` finds no gate.

  `docs/EVAL_METHODOLOGY.md` §3 cites a *different* number for the same property — DEC-176's
  "byte-identical reproduction as low as **4.2%** at `max_tokens=512`". Both are quoted as measured;
  neither is reconciled with the other.
- **Cost of inaction:** with 37% of records differing between two runs at a fixed seed, the
  6.4 pp effects the regression gate is tuned for are inside the reproduction noise. Any before/after
  measurement on this harness is a single noisy draw presented as a value.
- **Fix sketch:** re-measure under the current `ollama_version`, record the model digest (not
  `null`), and either raise `k` until the per-record CI is narrower than the gate's MDE or state
  plainly in the report that single-run deltas are not evidence.
- **Effort:** M
- **Blast radius:** `evals/seed_reproduction.json`, `scripts/seed_reproduction_probe.py`,
  `docs/EVAL_METHODOLOGY.md` §3, the MDE preflight from CR-L03-03.

### [CR-L03-12] Subtraction: the sequence subsystem has produced no measurement, and its policy doc describes a different program

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Waste
- **Evidence:** `evals/sequence_fidelity.py` + `sequence_order_effect.py` + `sequence_rates.py` +
  `sequence_records.py` + `sequence_reset.py` + `sequence_runner.py` = **808 lines**, wired to
  `make eval-sequence` (`Makefile:461`). `find . -name "*sequence*" -not -path "*/tests/*" -not -name "*.py"`
  returns only mypy cache entries — **no committed artifact**, no report, no trend field. Seven of the
  18 normative claims in `docs/SEQUENCE_STATS_POLICY.md` diverge (see the table above), including
  three describing behaviour that does not exist (the FULL-fidelity diagnostic, the 0.05
  significance rule, the §4.3 warning block) and one where the "live per-repetition receipt" is a
  static tuple re-read from `evals/reset_fidelity.json` (`evals/sequence_reset.py:75-85`).
  `docs/REASONING_DIMENSIONS.md` records dimension D5 (multi-round coherence, `case_seq_*`) as
  "declared only — no file exists"; 0 such cases exist. The subsystem's consumer has not been built.
- **Cost of inaction:** 808 lines plus a 227-line policy doc that must be maintained, reviewed and
  kept honest by `check-harness`, in exchange for zero decisions. It will drift further from the doc
  every month.
- **Fix sketch:** either author the `case_seq_*` battery in EVAL-P27 and commit a sequence artifact,
  or move both the module set and the policy doc to `archive/` and re-derive them when D5 is
  actually being measured.
- **Effort:** S to archive; L to complete.
- **Removes:** ~808 lines / 6 files + 227 doc lines, if archived.
- **Blast radius:** `make eval-sequence`, `docs/RESET_FIDELITY.md` cross-references,
  `evals/scenario_adapters*.py`, `evals/world_map.py`.

---

## What is genuinely good here, for calibration

This lens is required to be sceptical, so the counterweight belongs in writing. Several things in
`evals/` are better than most production eval harnesses:

- The judge≠generator invariant is **enforced at import** with a typed exception, per panel seat
  (`evals/judge_config.py:114-165`), not asserted in a docstring.
- The single-rater tautology was detected by the harness itself and it **refuses to print a
  fabricated agreement number** for it (`evals/calibration_records.py:49-58`, and the four
  `N/A (single rater)` lines in the calibration output).
- The κ bootstrap resamples **case clusters**, not rows, with a stated √k justification
  (`docs/STATISTICS_POLICY.md` §2c, `evals/calibration.py:469`).
- The FWER disclosure is printed unprompted on every calibration run.
- `evals/mde.py` is a genuinely unusual artefact: a module whose whole job is to tell you a planned
  experiment is pointless before you spend ten hours on it, with its weakest assumption (κ as a
  proxy for Youden's J) named in the docstring as the weakest link.
- `evals/synthetic_label_guard.py` prevents mock/oracle labels from ever overwriting human verdicts.
- The dead-keyword, hedge-responder and base-rate instruments each measure the right thing. The
  failure in this report is almost entirely that they are pointed at the wrong battery, are advisory,
  or are unreachable — not that they are wrong.

The problem is not that this project cannot measure. It is that the measurements it already has
say the battery is inert, and nothing consumes them.

---

## L16 — Operational & dependency risk

# CR-L16 — Operational & Dependency Risk

Lens: L16. Branch `eval-ab-context-arms` @ `d46ae42`. Windows 11, Git Bash + PowerShell.
Live stack: `npcsystem-app-1`, `npcsystem-neo4j-1` (untouched throughout — verified running
at end of session). All destructive/build tests were run against an isolated clone in
`%TEMP%\...\scratchpad\freshclone\NPCSystem` under compose project `npcfreshtest`, on
remapped port 18000, torn down and deleted at the end (`docker compose down -v`, `docker rmi
npcfreshtest-app`, `rm -rf`).

## Required measurements

### 1. Fresh clone boot (actually attempted, not simulated)

| # | Documented step (README.md Quick Start) | Worked as written? | Gap found |
|---|---|---|---|
| 0 | (implicit) `git clone` | **NO** | Windows `MAX_PATH`: `git clone` aborts with `Filename too long` on `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-*.md` (15+ paths). Fixed only by `git config core.longpaths true`, which the repo tells no one to set (`git grep -il longpath` → 0 hits in tracked files). |
| 0b | (implicit) provide `.env` | **NO** | `docker-compose.yml:76` declares `env_file: - .env`; only `.env.example` is tracked (`.gitignore:38-40`). `docker compose config` on a truly fresh clone fails immediately: `env file ...\.env not found`. README never says `cp .env.example .env`; that step exists only in `CONTRIBUTING.md`, a different document with a different (contradictory) setup path. |
| 1 | `docker-compose up -d` | **YES, once 0/0b fixed** | After `core.longpaths=true` + `cp .env.example .env`, `docker compose up -d --build` succeeded end-to-end: image built (2.02 GB), neo4j reached healthy, app answered `GET /health` → `{"status":"ok","version":"dev"}`. |
| 2 | `make demo-seed` | Not exercised | Requires `API_KEY_SECRET` alignment with `.env` and a Windows `make`; out of time budget once (1) proved the documented path is two undocumented steps short. |
| 3 | `make demo` | Not exercised (pygame window) | — |
| 4 | `make test` | Not exercised | — |
| 5 | `make eval` | Not exercised | — |

**Result: 5 documented Quick Start lines; step 0 (clone) and step 1 (`docker-compose up -d`)
both fail as written on this platform; 2 undocumented fixes are required before step 1 ever
runs.** Time to a working stack once the fixes were known: ~90 s (build) + ~15 s (neo4j
healthy) after the two blockers were resolved by hand.

Command evidence (paths redacted to `<clone>`):
```
$ git clone <repo> <clone>
error: unable to create file project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-208-retrieval-explainer-panel.md: Filename too long
...(15 similar)...
fatal: unable to checkout working tree

$ git config --global --get core.longpaths   # (empty — not set on this machine)

$ git -c core.longpaths=true clone <repo> <clone>   # succeeds

$ docker compose config
env file <clone>\.env not found: CreateFile <clone>\.env: The system cannot find the file specified.

$ cp .env.example .env && docker compose up -d --build
...
Container npcfreshtest-app-1 Started

$ curl http://127.0.0.1:18000/health
{"success":true,"data":{"status":"ok","version":"dev"},"meta":null}
```

`CONTRIBUTING.md` documents a **third, incompatible** setup path: `docker run -p 7687:7687
neo4j:5` (bypassing `docker-compose.yml` entirely) plus `python -m npc_engine.scripts.seed`,
which does not exist (`src/npc_engine/scripts/` contains only `check_contracts.py`,
`guard_contract_test_sync.py`, `manual_system_test_v14.ps1`, `simulate_world_flow.py` —
confirmed by directory listing). It also points at `project/CLAUDE.md`, which does not exist
(`project-harness/CLAUDE.md` does). Three onboarding documents (README, CONTRIBUTING,
docker-compose.yml's own header comment on ISSUE-131) describe three different, mutually
inconsistent ways to start Neo4j.

### 2. Python 3.14 exposure

Dockerfile (`Dockerfile:1`) is `FROM python:3.11-slim`; `mypy.ini:2` pins `python_version =
3.11`; `pyproject.toml:5` says `requires-python = ">=3.11"`. But `README.md:43` and
`CONTRIBUTING.md:5` say `Python 3.14+`, and `.github/workflows/ci.yml` sets
`python-version: "3.14"` in **every** job (5 occurrences). CI therefore lints, type-checks
(mypy configured for 3.11 syntax rules but *executed* under 3.14), and tests the whole suite
on a Python the production Docker image never runs.

Local dev venv actually in use (`.venv`, Python 3.14.2) confirmed via `pip list`:

| Package | Pinned (pyproject) | Installed in 3.14 venv | Requires-Python (pinned release) | 3.14 verdict |
|---|---|---|---|---|
| fastapi | ==0.116.1 | 0.116.1 | >=3.8 (no 3.14 classifier) | Installs, untested-on-3.14 by upstream |
| uvicorn[standard] | ==0.35.0 | 0.35.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| pydantic | ==2.12.1 | 2.12.1 | >=3.9, **3.14 classifier present** | OK |
| pydantic-settings | ==2.11.0 | 2.11.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| PyYAML | ==6.0.2 | 6.0.2 | >=3.8 (no 3.14 classifier), has C ext (libyaml) | Installs, untested |
| types-PyYAML | unpinned | 6.0.12.20260408 | n/a (stub-only) | n/a |
| neo4j | ==5.28.2 | 5.28.2 | >=3.7 (no 3.14 classifier) | Installs, untested |
| redis | ==5.2.1 | 5.2.1 | >=3.8 (no 3.14 classifier) | Installs, untested |
| httpx | ==0.28.1 | 0.28.1 | >=3.8 (no 3.14 classifier) | Installs, untested |
| sentence-transformers | >=2.6.0 (unbounded) | **NOT INSTALLED** | — | **BLOCKS** — see below |
| torch | >=2.0.0 (unbounded) | **NOT INSTALLED** | — | **BLOCKS** — see below |
| pytest | ==8.4.2 | 8.4.2 | >=3.9, 3.14 classifier present | OK |
| pytest-asyncio | ==1.2.0 | 1.2.0 | >=3.9, 3.14 classifier present | OK |
| pytest-cov | ==6.3.0 | 6.3.0 | >=3.9 (no 3.14 classifier) | Installs, untested |
| ruff | ==0.13.0 | 0.13.0 | >=3.7 (Rust binary, no ext build) | OK |
| mypy | ==1.18.2 | 1.18.2 | >=3.9, 3.14 classifier present | OK |

**Confirmed defect, not merely a version-lag risk**: the checked-in, hard (non-optional)
dependencies `torch>=2.0.0` and `sentence-transformers>=2.6.0` (`pyproject.toml:15-16`) are
**absent** from the maintainer's own 3.14 dev venv:
```
$ .venv/Scripts/python.exe -m pip show torch
WARNING: Package(s) not found: torch
$ .venv/Scripts/python.exe -c "import torch"
ModuleNotFoundError: No module named 'torch'
```
Every call site that imports them is a lazy import guarded only at call time, not at process
start (`src/npc_engine/retrieval/embedding/sentence_encoder.py:33,36`,
`src/npc_engine/retrieval/embedding/cross_encoder_reranker.py:28`), so the RAG/embedding path
(a stated core feature — README "Embedding reconciler ✅") is silently unexercised by anyone
running the documented dev venv, and will only fail the first time embedding code actually
runs. A `pip download --no-deps torch` dry run (network, no install) shows a `cp314-win_amd64`
wheel for `torch==2.13.0` *does* exist as of this session's date, so the gap is a stale/never-
completed local install, not (currently) a hard PyPI wall — but nothing pins a wheel-tested
`torch`/`sentence-transformers` version, so this is one silent transitive bump away from
reappearing when a wheel is later pulled.

**3.13-downgrade / 3.15-upgrade blockers**: none of the pinned packages declare an upper Python
bound, so nothing in the manifest *forbids* either move — but `torch`/`sentence-transformers`
have no floor pin either, so either move re-resolves to whatever the latest matching wheel is
at install time, with no record of what was actually validated.

### 3. Unpinned dependencies

| Manifest | Total deps | Exact-pinned (`==`) | Open range (`>=`, no ceiling) | Fully unpinned (no spec) |
|---|---|---|---|---|
| `pyproject.toml` (main + `[dev]`) | 16 | 13 | 2 (`sentence-transformers`, `torch`) | 1 (`types-PyYAML`) |
| `demo_game/requirements.txt` | 5 | 0 | 5 (`httpx`, `pydantic-settings`, `pygame-ce`, `networkx`, `matplotlib`) | 0 |
| **Combined** | **21** | **13 (62%)** | **7 (33%)** | **1 (5%)** |

**No lockfile of any kind** exists — confirmed by `find . -iname "requirements*.txt"` (only
`demo_game/requirements.txt`, itself unpinned) and absence of `poetry.lock`, `uv.lock`,
`Pipfile.lock`, or a hash-pinned `requirements.txt` anywhere in the tree. Even the 13
exact-pinned top-level packages have **zero transitive pins** — `fastapi==0.116.1` pulls
`starlette`, `pydantic_core`, etc. at whatever version resolves *today*. Rebuilding the image
from a commit six months old will silently resolve different `torch`, `sentence-transformers`,
`pygame-ce`, `networkx`, `matplotlib`, and every transitive dependency of every package —
there is no way to reproduce a specific past build byte-for-byte.

### 4. Single-LLM SPOF (`qwen2.5:7b` via Ollama)

- **Configured model, traced**: `src/npc_engine/engines/dialogue/llm_config.yaml:3-4` →
  `backend: ollama`, `model: qwen2.5:7b`. Matches README/CONTRIBUTING's documented model.
- **Live Ollama** (`GET /api/tags`, confirmed): `llama3.1:8b`, `cyoa-lora:latest`,
  `qwen2.5:7b`, `qwen2.5:14b`, `mixtral:8x7b` — the configured tag is present; no drift found
  between config and running server.
- **Fallback contract, traced end to end and CONFIRMED wired** (contrary to a naive read of
  "sibling lens confirmed the Neo4j half is unimplemented" — the dialogue LLM half is real):
  `dialogue_handler.py:179` → `DialogueLLMClient(fallback_path=settings.LLM_FALLBACK_PATH, ...)`
  → `llm_client.py:107-113`: `except LLMTimeoutError` / `except LLMRequestError` both call
  `self._fallback_with_metrics(...)` → `_load_fallback_dialogue()` →
  `json.loads(Path(self._fallback_path).read_text())` reading
  `src/npc_engine/data/fallback_responses.json` (file exists, confirmed present on disk).
  Also wired on `stream_text()` (`llm_client.py:~230`, same exception pair).
- **Coverage gap**: `grep -rl "fallback_path\|LLMTimeoutError" src/npc_engine/engines/{chapter,proactive_dialogue,quest_generation,memory_consolidation}` finds it only in `proactive_dialogue` and `quest_generation`; `chapter` and `memory_consolidation` have **no** matching hit, i.e. no traced timeout-fallback path in this pass — not confirmed broken (needs a targeted repro), so reported as Suspected, not Critical.
- **Model-tag mutability**: Ollama tags (`qwen2.5:7b`) are **not content-addressed** — a
  `docker exec ... ollama pull qwen2.5:7b` re-pull can silently swap the underlying weights
  the tag points to. `llm_config.yaml` records only the tag string, never a digest. Any two
  eval runs months apart that both say "qwen2.5:7b" are not provably the same model.

### 5. Secrets

- Working tree `git grep` (API-key/AWS-key/private-key/password patterns) across all tracked
  files: **0 hits** outside test fixtures and `.env.example` placeholders.
- `git log --all -p -S"sk-"` / `-S"AKIA"` / `-S"BEGIN ... PRIVATE KEY"`: **0 real matches**
  (only unrelated doc content containing the substring "sk-" as part of prose; no key-shaped
  strings; one `git log` diff-scan error on an unrelated orphaned `~$esting.docx` blob in this
  machine's local git-blob temp cache, not part of the repo history).
- `.env` was **never committed**: `git log --all --oneline -- .env` → empty. `.env.demo`
  likewise empty. `.gitignore:38-41` covers `*.env`, `.env.*`, with an explicit
  `!.env.example` carve-out — correctly scoped.
- All `API_KEY_SECRET=` values found in history (`git log --all -p -S"API_KEY_SECRET="`) are
  clearly-fake dev/test placeholders: `"npc_dev_secret_2026_alpha"`,
  `"local_dev_secret_change_this_2026"`, `"test-api-key-secret-ci"`. **No live secret found,
  in working tree or history.**
- `docker-compose.yml:34` ships `NEO4J_AUTH: neo4j/password` — the Neo4j-documented default
  credential pair, unchanged. Not a leaked secret (it's a public, well-known default), but it
  is the literal shipped default in a file every clone gets. Neo4j has no host port mapping
  (by design, per the file's own header comment, EVAL-P20.3a/ISSUE-131), so today this is not
  externally reachable — but the credential is real and would matter the moment anyone adds a
  host port mapping (e.g. copying the `demo-snapshot` "run inside app container" pattern to a
  quick local hack, or a future prod compose file inheriting this default uncritically).

### 6. Licence conflicts

`pip-licenses` run against the actual 3.14 dev venv (`piplicenses --format=markdown`):

| Package | Licence | Confined to |
|---|---|---|
| **pygame-ce 2.5.7** | **GNU LGPL** | `demo_game/` only (`demo_game/requirements.txt`) |
| numpy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | transitive (via sentence-transformers/matplotlib) |
| everything else (fastapi, uvicorn, pydantic\*, neo4j, redis, httpx, PyYAML, matplotlib, networkx, tiktoken, etc.) | MIT / BSD / Apache-2.0 / PSF | — |

**Only copyleft package found: `pygame-ce`, LGPL.** Per `CLAUDE.md`'s own architecture table,
`demo_game/` has "zero imports from `src/`" and is explicitly the pygame demo UI, not the
licensed engine. `docs/BUSINESS_REQUIREMENTS.md` describes the licensed product as "a plugin
for both Unity and Unreal Engine games" exposing "a clean HTTP + WebSocket API" — i.e. the
`src/npc_engine` FastAPI service, which does not import pygame-ce anywhere (`pyproject.toml`
main dependencies list has no pygame reference; it lives solely in
`demo_game/requirements.txt`). **No copyleft package is inside the artefact that gets licensed
to game studios**, on current evidence. Flagging as LOW/Process rather than HIGH: the risk is
that nothing in the repo *enforces* this separation (no test, no CI check, no packaging
manifest excludes `demo_game/` from a hypothetical "engine" distribution build) — it currently
holds only because no packaging step exists yet that bundles the two together.

### 7. Image/runtime hygiene

| Check | Result |
|---|---|
| Runs as root? | **YES** — no `USER` directive in `Dockerfile`; `docker exec npcsystem-app-1 id` → `uid=0(root) gid=0(root) groups=0(root)` |
| Healthcheck on `app` service? | **NO** — `docker-compose.yml` has `healthcheck:` blocks only for `neo4j` (line 43) and `redis` (line 58); the `app` service (lines ~62-83) has none, despite `GET /health` existing and being polled externally by `boot_check.py` |
| `restart` policy on `app`? | `restart: on-failure:5` (present) |
| `BUILD_SHA` actually used for staleness detection? | **Partially.** `Dockerfile:24-26` bakes `ARG BUILD_SHA=dev` → `ENV BUILD_SHA` and `/health` reports it as `version`. `make boot-check` (`Makefile:45-46`) *does* pass `BUILD_SHA=$(git rev-parse --short HEAD)` and forces `--build`. But the currently-running `npcsystem-app-1` reports `"version":"dev"` — proving it was **not** started via `make boot-check`, but via a plain `docker-compose up -d` / `up -d --build` (`make demo`, `make demo-seed`'s prerequisite, and the README Quick Start all say exactly `docker-compose up -d`, none pass `BUILD_SHA`). So the staleness detector exists and works when invoked, but no documented day-to-day command path invokes it — `version: "dev"` is what everyone actually sees, always. |
| Is the running image actually stale right now? | **NO, checked and confirmed fresh** — despite the image being built at `2026-08-27T19:09:21Z` and commit `96d83eb` (touching `src/npc_engine/config.py`) landing later at `19:23:00Z`, a live `md5sum` diff of `config.py`, `config_prompt_window.py`, `main.py`, and `dialogue_handler.py` between host and `docker exec` shows **byte-identical** content (working-tree edit predates both the commit and the build, at `19:02:07Z`). This particular container is current; the finding is about the *process*, not this instant. |
| Reproducible build? | **NO** — see §3 (no lockfile, no transitive pins); `Dockerfile:12` even installs CPU-only `torch` via a separate untagged index step before the pinned-but-unbounded `sentence-transformers`/`torch` resolve in `pip install -e .` |

## Findings

### [CR-L16-01] Fresh clone cannot boot on Windows without two undocumented fixes

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `git clone` of HEAD on this Windows 11 machine fails with `error: unable to
  create file project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-208-retrieval-explainer-panel.md: Filename too long` (15 similar paths) unless
  `git config core.longpaths true` is set first (`git config --global --get core.longpaths`
  returns empty on this machine). Separately, `docker-compose.yml:76` requires `env_file:
  - .env`, but only `.env.example` is tracked (`.gitignore:38-40`); `docker compose config`
  on a fresh clone fails with `env file ...\.env not found`. README.md's Quick Start
  (`README.md:42-54`) contains neither fix. Both were reproduced and then fixed in an isolated
  clone (`compose project npcfreshtest`, port 18000), after which `docker compose up -d --build`
  succeeded and `/health` returned 200.
- **Cost of inaction:** Every new Windows contributor or evaluator hits a dead stop at `git
  clone`, then a second dead stop at the very first documented command, with an error message
  that does not point at either root cause.
- **Fix sketch:** Add `git config core.longpaths true` (or shorten the offending
  `project-harness/archive/...` paths / split them across shorter directories) and add `cp
  .env.example .env` as an explicit Quick Start line in README.md, matching what
  CONTRIBUTING.md already does for its (different) path.
- **Effort:** S (<2h)
- **Blast radius:** Onboarding docs only; no code change required for the `.env` half, a
  one-line git-config note or repo-relative path shortening for the long-path half.

### [CR-L16-02] Three mutually contradictory setup docs (README vs CONTRIBUTING vs compose header)

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `README.md:42-48` says `docker-compose up -d` then `make demo-seed`.
  `CONTRIBUTING.md:20-30` says `pip install -e .[dev]`, `docker run -p 7474:7474 -p 7687:7687
  -e NEO4J_AUTH=neo4j/password neo4j:5`, `uvicorn npc_engine.main:app --reload`, then `python -m
  npc_engine.scripts.seed` — a module that does not exist (`src/npc_engine/scripts/` contains
  only `check_contracts.py`, `guard_contract_test_sync.py`, `manual_system_test_v14.ps1`,
  `simulate_world_flow.py`, confirmed by directory listing). CONTRIBUTING.md also references
  `project/CLAUDE.md`, which does not exist (`project-harness/CLAUDE.md` does — confirmed with
  `ls`). `docker-compose.yml`'s own header comment documents *why* Neo4j has no host port
  mapping (EVAL-P20.3a/ISSUE-131) — directly contradicting CONTRIBUTING's raw `docker run -p
  7687:7687` instruction, which assumes host-reachable Bolt.
- **Cost of inaction:** A contributor following CONTRIBUTING.md verbatim hits an
  `ImportError`/`ModuleNotFoundError` on the seed step and a wrong mental model of how Neo4j
  networking works in this repo.
- **Fix sketch:** Delete CONTRIBUTING.md's `Setup`/`Running the server` sections and point to
  the README Quick Start as the single source of truth, or update its module path and
  `project/` → `project-harness/` reference.
- **Effort:** S (<2h)
- **Blast radius:** Documentation only.

### [CR-L16-03] Documented day-to-day path never rebuilds the app image; staleness detector exists but is unused by it

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `Makefile:45-46` (`boot-check`) is the only target that passes `BUILD_SHA=$(git
  rev-parse --short HEAD)` with `--build`. `demo:` (`Makefile:571-573`), `demo-seed`, and the
  README/Quick-Start's own `docker-compose up -d` all start the stack **without** `--build` and
  without `BUILD_SHA`. The live container `npcsystem-app-1` right now reports
  `{"version":"dev"}` via `/health` — proving normal operation never exercises the SHA-based
  staleness check `e2e/scripts/boot_check.py` implements. If a developer edits `src/` and then
  runs `make demo` (the documented demo path), the container keeps serving the pre-edit image
  with no visible signal — `version` stays `"dev"` whether the image is one hour or one month
  old.
- **Cost of inaction:** Exactly the failure mode the maintainer's own memory note already
  flagged: a live before/after measurement (an eval run, a demo recording, a bug
  reproduction) silently runs stale code, and nothing in the tool's own output distinguishes
  stale from fresh.
- **Fix sketch:** Make `demo`/`demo-seed`/`demo-run` depend on `boot-check` (or on a
  lighter `docker compose up -d --build` with `BUILD_SHA` set), or have `/health` refuse to
  report a bare `"dev"` and instead always compute a content hash of the installed package at
  startup.
- **Effort:** S (<2h) — wire existing `boot-check` target as a prerequisite of `demo`/`demo-seed`.
- **Blast radius:** `Makefile` demo targets only; no application code changes.

### [CR-L16-04] `torch` and `sentence-transformers` are hard dependencies but absent from the maintainer's own 3.14 dev venv

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `pyproject.toml:15-16` lists `sentence-transformers>=2.6.0` and
  `torch>=2.0.0` as unconditional (non-optional) `[project.dependencies]`. In the repo's own
  `.venv` (Python 3.14.2, the version CI and README/CONTRIBUTING mandate):
  `python -m pip show torch` → `WARNING: Package(s) not found: torch`;
  `python -c "import torch"` → `ModuleNotFoundError: No module named 'torch'`. Same for
  `sentence_transformers`. These are imported (lazily, at call time, not at process start) by
  `src/npc_engine/retrieval/embedding/sentence_encoder.py:33,36` and
  `src/npc_engine/retrieval/embedding/cross_encoder_reranker.py:28` — the embedding/RAG path
  the README lists as a shipped feature ("Embedding reconciler ✅").
- **Cost of inaction:** Anyone running unit tests or the API server out of this venv gets a
  silent gap: embedding/RAG code paths are never exercised locally and only fail the first time
  they're hit (e.g. in Docker, where the Dockerfile does separately `pip install torch` via the
  CPU wheel index — so the container is fine; only the bare local venv is affected). A
  contributor debugging retrieval issues locally will get an opaque `ModuleNotFoundError`
  instead of the real bug.
- **Fix sketch:** Re-run `pip install -e .[dev]` in the tracked dev venv (or document that the
  venv must be rebuilt after any `pyproject.toml` dependency change), and add a `make
  check-venv` sanity import check.
- **Effort:** S (<2h)
- **Blast radius:** Local dev environment only; Docker image already installs these correctly.

### [CR-L16-05] No dependency ceiling anywhere and no lockfile — unreproducible builds

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** Of 21 total declared dependencies across `pyproject.toml` and
  `demo_game/requirements.txt`, 13 are exact-pinned, 7 use an open `>=` range with no ceiling
  (`sentence-transformers`, `torch`, and all 5 of `demo_game/requirements.txt`'s deps), and 1
  (`types-PyYAML`) has no version specifier at all. No `poetry.lock`, `uv.lock`,
  `Pipfile.lock`, or hash-pinned `requirements.txt` exists anywhere in the tree (`find . -iname
  "requirements*.txt"` returns only the unpinned `demo_game/requirements.txt`). Even the 13
  exact-pinned top-level packages carry zero transitive pins.
- **Cost of inaction:** A build from a commit six months old will silently resolve whatever
  `torch`/`sentence-transformers`/`pygame-ce`/`networkx`/`matplotlib`/transitive-dependency
  versions are current *then*, not what was validated *at that commit*. A regression bisect
  across old commits cannot trust that the dependency tree, not the code, is the variable that
  changed.
- **Fix sketch:** Add upper bounds to the 7 ranged deps, pin `types-PyYAround`, and generate a
  lockfile (`pip-compile` / `uv lock`) checked into the repo.
- **Effort:** M (<1d)
- **Blast radius:** Build tooling only; touches `Dockerfile`'s pip install layer caching
  strategy (lockfile becomes the new cache key).

### [CR-L16-06] Two incompatible Python-version targets: Docker/mypy on 3.11, CI/README on 3.14

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `Dockerfile:1` → `FROM python:3.11-slim`; `mypy.ini:2` →
  `python_version = 3.11`; `pyproject.toml:5` → `requires-python = ">=3.11"`. Meanwhile
  `.github/workflows/ci.yml` sets `python-version: "3.14"` in all 5 jobs, and
  `README.md:43`/`CONTRIBUTING.md:5` both say "Python 3.14+". CI therefore lints, type-checks,
  and runs the full test suite under 3.14 while the artefact that actually ships (the Docker
  image) runs 3.11.
- **Cost of inaction:** A 3.14-only stdlib/typing behaviour difference that CI is green on
  could behave differently — or not be exercised at all — in the production container, and
  vice versa; mypy is configured for 3.11 syntax rules while actually invoked under a 3.14
  interpreter in CI, an unverified combination.
- **Fix sketch:** Pick one target. If the shipped image is 3.11 (as Dockerfile says), run CI on
  3.11 too, or explicitly document why the demo (`pygame-ce`, no 3.14 wheel for classic
  `pygame`) needs 3.14 while the engine ships on 3.11, and gate CI on both.
- **Effort:** M (<1d) — requires deciding the real target, not just a config edit.
- **Blast radius:** CI workflow, `Dockerfile` base image, `mypy.ini` — a real compatibility
  decision, not a mechanical fix.

### [CR-L16-07] `app` container runs as root with no healthcheck

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `Dockerfile` has no `USER` directive at any layer;
  `docker exec npcsystem-app-1 id` → `uid=0(root) gid=0(root) groups=0(root)`.
  `docker-compose.yml` has `healthcheck:` blocks for `neo4j` (line 43) and `redis` (line 58)
  but none for `app`, despite `GET /health` existing and being polled externally by
  `e2e/scripts/boot_check.py` and `restore-with-app-stopped`'s own curl loop
  (`Makefile:657-660`) — the exact probe a compose-native healthcheck would replace.
- **Cost of inaction:** A container-escape bug in any dependency (torch, PyYAML's C extension,
  Pillow) runs as root inside the container by default; `docker compose`/orchestrators cannot
  use `depends_on: condition: service_healthy` on `app` the way they already do on `neo4j`.
- **Fix sketch:** Add `USER app` after installing dependencies (before `COPY src/`, adjusting
  file ownership), and add a `healthcheck:` block on `app` reusing the existing `/health`
  endpoint the Makefile already polls.
- **Effort:** S (<2h)
- **Blast radius:** `Dockerfile` (needs a non-root user + chown of `/app`), `docker-compose.yml`.

### [CR-L16-08] Ollama model tag is not content-addressed — eval scores are not provably comparable across time

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Risk
- **Evidence:** `src/npc_engine/engines/dialogue/llm_config.yaml:3-4` records only
  `backend: ollama`, `model: qwen2.5:7b` — a mutable tag, not a digest. Live `GET
  /api/tags` confirms the tag currently resolves to a running `qwen2.5:7b`, but nothing in
  the repo records or checks a model digest/hash anywhere a generation record is written
  (not found in this pass; scoped search only).
  `docs/EVAL_METHODOLOGY.md`/`evals/` were not audited for a digest-pinning mechanism in this
  lens — reported as Likely, not Confirmed, pending that check.
- **Cost of inaction:** A `docker exec ... ollama pull qwen2.5:7b` re-pull between two eval
  runs both labelled "qwen2.5:7b" can silently swap the weights being scored, invalidating any
  before/after comparison that assumes model identity.
- **Fix sketch:** Record the Ollama model digest (`ollama show qwen2.5:7b --modelfile` or the
  `/api/show` digest field) alongside every generation record.
- **Effort:** S (<2h)
- **Blast radius:** `evals/` generation-record schema; additive field only.

### [CR-L16-09] Neo4j ships with the documented default credential pair

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `docker-compose.yml:34` → `NEO4J_AUTH: neo4j/password`, Neo4j's own
  documented default. Currently contained by network isolation (`internal: true`, no host
  port mapping — confirmed by the file's own header comment and by this session's `docker ps`
  showing no `7474`/`7687` host binding). No secret leak — this is a public, well-known
  default, not a credential someone else can see — but it is the literal value every clone
  gets, with nothing forcing it to change before any future compose variant adds a host port.
- **Cost of inaction:** The moment anyone (a demo tweak, a debugging session, a different
  compose profile) republishes Neo4j's port without also changing this default, it is
  immediately exploitable.
- **Fix sketch:** Generate a random password at `docker-compose up` time via a `.env`-sourced
  variable with no shipped default, or add an explicit comment in `docker-compose.yml` warning
  against ever publishing Neo4j's port without changing it first.
- **Effort:** S (<2h)
- **Blast radius:** `docker-compose.yml`, `.env.example`.

## Not investigated / needs a human decision

- Whether `chapter` and `memory_consolidation` engines have a working LLM-timeout fallback —
  no matching `fallback_path`/`LLMTimeoutError` hit found in this pass (Suspected only, not
  traced end to end; see §4).
- Whether `evals/` records an Ollama model digest anywhere (CR-L16-08 is Likely, not Confirmed).
- `make demo-seed` / `make demo` / `make test` / `make eval` were not exercised end-to-end in
  the fresh-clone test (time-boxed after the clone/`.env` blockers alone proved the finding);
  a follow-up session could complete the walkthrough now that both blockers are known.
- Whether `demo_game/`'s LGPL (`pygame-ce`) exposure is acceptable long-term depends on a
  packaging decision (does a future "licensed engine" distribution ever bundle `demo_game/`?)
  that only the maintainer can make — currently the two are cleanly separated by the existing
  layer rule, but nothing mechanically enforces that separation into a packaged artefact.

---

## L15 — Test economics

> **Orchestrator severity calibration + a corroborating fact L15 did not have.**
> L15 filed CR-L15-01 as CRITICAL. It is recorded here as **HIGH**, and the
> reasoning matters, because the fact that would make it CRITICAL is exactly the
> one nobody in this review can check locally.
>
> Corroboration first. `.github/workflows/ci.yml` runs `make test-cov` (line 92)
> in a job that declares **no `services:` block at all** — no Ollama container, no
> Neo4j container. So the tests L15 traced making real `httpx` calls to
> `:11434` and `:8000` have no server to talk to in CI. That means one of two
> things is true, and they have different severities:
>
> - **(a)** CI's `test-cov` job is red or has been red, and nobody noticed because
>   — per CR-L06-06 — branch protection is unverified and CI may not be required
>   for merge. That is CRITICAL.
> - **(b)** Those tests degrade gracefully when the connection is refused, in
>   which case they exercise a *different code path* in CI than locally, and the
>   87.86% coverage figure is environment-dependent — the same number means two
>   different things depending on where it was produced. That is HIGH.
>
> Neither this lens nor L6 could distinguish (a) from (b): `gh` is not installed
> on this machine and CI run history is not reachable. Recording the finding at
> **HIGH** is the honest floor. **This is the single highest-value question a
> human can answer in five minutes** — open the Actions tab, look at whether
> `test-cov` is green on `main`, and this either stays HIGH or becomes the
> review's third CRITICAL. It is item 1 on the "decide" list in §E.

# CR-L15 — Test economics

Branch `eval-ab-context-arms`, HEAD `d46ae42`. Read-only review. Neo4j is not
published to the host (only port 8000 is mapped) — no host-side direct-Neo4j
checks were possible or attempted; nothing below depended on one.

## Required measurements

### 1. Wall-clock

| Target | Result | Elapsed |
|---|---|---|
| `make check` (orchestrator's baseline, reused) | 15 targets, all exit 0 | 595s (9m55s) |
| `make test` (`pytest tests/ -q`) — ran live | **4048 passed, 36 skipped**, 2299 warnings | `333.01s` reported by pytest / `338s` shell wall-clock |
| `make test-demo` (`pytest demo_game/tests/ -q`) — ran live | **1116 passed** | `12.12s` reported by pytest / `18s` shell wall-clock |

```
$ pytest demo_game/tests/ -q
1116 passed, 30 warnings in 12.12s
$ pytest tests/ -q --durations=25
4048 passed, 36 skipped, 2299 warnings in 333.01s (0:05:33)
```

### 2. Slowest 20/25 — `tests/`

```
27.21s  tests/unit/engines/test_eval_runner_loop.py::test_run_case_keyword_none_fails_when_keyword_present
18.02s  tests/unit/evals/test_run_config.py::test_editing_a_judge_criteria_changes_harness_version
17.98s  tests/unit/evals/test_run_config.py::test_readme_in_cases_does_not_change_harness_version
17.84s  tests/unit/evals/test_run_config.py::test_golden_set_version_changes_when_a_case_changes
8.96s   tests/unit/evals/test_run_config.py::test_git_sha_is_seven_chars
8.89s   tests/unit/evals/test_run_config.py::test_run_config_fields_from_minimal_yaml
8.88s   tests/unit/evals/test_run_config.py::test_resolve_reads_dialogue_llm_config
8.87s   tests/unit/evals/test_generate_runner_k.py::test_gen_dir_run_records_a_non_null_run_config
8.85s   tests/unit/evals/test_run_config.py::test_resolve_seed_is_none_when_config_omits_it
8.80s   tests/unit/evals/test_run_config.py::test_resolve_with_custom_retrieval_profile
8.77s   tests/unit/evals/test_run_config.py::test_run_config_is_frozen
8.75s   tests/unit/evals/test_run_config.py::test_resolve_reads_seed_from_dialogue_llm_config
8.71s   tests/unit/evals/test_run_config.py::test_resolve_reads_prompt_version
8.15s   tests/unit/evals/test_generate_runner_k.py::test_gen_dir_run_resolves_config_before_generating
7.95s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_starts_reconciler_task
6.45s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_cancels_reconciler_task_on_shutdown
6.40s   tests/unit/conformance/test_sev15_type_gate.py::test_mypy_exits_zero
6.39s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_is_skipped_when_the_flag_is_off
6.36s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_that_reads_nothing_logs_at_error
6.36s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_finishes_before_the_reconciler_task_starts
6.11s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_closes_graph_db_when_startup_fails_after_connect
6.05s   tests/unit/scripts/test_record_trend_and_gate.py::test_explicit_baseline_gen_id_is_gated_against
4.72s   tests/unit/scripts/test_run_eval_harness.py::test_harness_accepts_a_custom_base_url_and_still_fails_loudly
4.62s   tests/unit/scripts/test_record_trend_and_gate.py::test_stable_kappa_still_exits_zero
4.49s   tests/unit/scripts/test_record_trend_and_gate.py::test_kappa_drop_exits_three_not_one
```

**What they're actually doing** — traced, not guessed:
- Rank 1 (27.21s) and ranks 2–14 (13 tests, ~133s combined) are **real, unmocked `httpx` calls to Ollama (`:11434`) and/or the live engine API (`:8000`)**, not CPU/setup cost. Full trace in CR-L15-01. Re-ran the single slowest test file twice in isolation to confirm this is not a fluke: `26.52s` then `26.19s` (`pytest tests/unit/engines/test_eval_runner_loop.py -q --durations=5`, both runs).
- Rank 17 (`test_mypy_exits_zero`, 6.40s) shells out to a **second, independent `mypy src/` subprocess** inside the test suite — duplicate of `make type`'s own 7s (CR-L15-05).
- The `test_main_reconciler_lifespan.py` cluster (5 tests, ~33s) drives real `asyncio` background-task lifecycles with `asyncio.sleep`-paced polling in the reconciler; legitimate async-integration cost, not flakiness or network — not investigated further (in budget, not in scope of the two defects above).
- `demo_game/tests/` slowest is `0.73s` (`test_dry_run_completes_through_act8_on_cp1252_stdout`); every other demo test is sub-0.6s. **1116 passed in 9.77s** pytest-reported. No network/DB dependency found — clean, fast unit suite.

### 3. Flakiness

Two independent full runs of `tests/` (durations run and the later coverage run, different flag sets, ~6 minutes apart) both produced **4048 passed, 36 skipped, 0 failed** — no differing outcome between runs. Re-ran the single slowest file twice in isolation (above) with consistent ~26.5s timing both times — the slowness is deterministic real-network latency, not a flake.

A third instrumented run (`--cov-context=test`, to build the per-test coverage map for §4) crashed with a `pytest-cov`/`coverage.py` **INTERNALERROR** (`sqlite3.OperationalError: no such table: context`) on this Windows/Python 3.14 combination — a tooling incompatibility in the `--cov-context` sqlite writer, not a test-suite defect. It surfaced no test failures before crashing; abandoned in favor of the grep-based method for §4 (as the task brief allows).

Grep for the usual flake sources:
```
time.sleep(              : tests/unit/retrieval/test_dialogue_context_cache.py:71 (1.1s, TTL-expiry test — deliberate, harmless)
                          : demo_game/tests/pollers/test_gold_poller.py:132,148 (0.01s/0.001s)
                          : demo_game/tests/scenarios/test_sandbox_loop.py:30,44,48,62 (0.1-0.2s)
datetime.now()/utcnow()  : 2 files (test_route_clock_tick.py, test_dialogue_handler_clock_tick.py) — both clock-tick tests, not time-of-day dependent
random.* unseeded        : 0 hits
pytest-randomly / xdist  : not installed (pip list confirms only pytest, pytest-asyncio, pytest-cov) — test order is deterministic file/declaration order, so no ordering-dependence risk from randomization
```
No flake source found beyond the deliberate, bounded `time.sleep`s above (worst case ~1.5s total across the whole suite) — the real cost driver is the *reproducible* real-network dependency in §2/CR-L15-01, not flakiness.

### 4. Coverage: real vs. import-only — 10 largest `src/npc_engine/` modules

Method: ran `pytest tests/ -q --cov=npc_engine --cov-report=json` live (4048 passed, 36 skipped, 339.16s — reconciles exactly with the orchestrator's baseline, see §6) and cross-referenced each module's statement/coverage numbers against which test files reference it and whether those tests call its own functions or patch them out at a higher layer.

| Module (stmts) | Coverage % | Tests naming it | Verdict |
|---|---|---|---|
| `retrieval/context/context_builder.py` (298 stmt) | 94.3% | `test_context_builder.py` (639 lines) + `test_context_builder_helpers_phase6.py` + 15 more | **Real** |
| `scheduler/tick_scheduler.py` (187 stmt) | 93.0% | `test_tick_scheduler_engine_isolation.py`, `test_tick_scheduler_llm_skip.py` (22 test fns) | **Real** |
| `retrieval/context/context_budget_enforcer.py` (148 stmt) | 96.6% | `test_context_budget_enforcer_v14.py` + 4 more | **Real** |
| `config.py` (229 stmt) | 99.1% | No dedicated `Settings`-validator test file; `Settings(...)` is constructed 76× across the suite purely for DI wiring (API_KEY_SECRET etc.), which happy-path-executes all 15 `@field_validator` + 5 `@model_validator` bodies as a side effect. Only 1 test (`test_config_prompt_window.py`) deliberately exercises a validator's *reject* branch. | **Mixed** — statements execute, but 14 of ~20 validators have their pass/fail decision logic verified nowhere; the 2 missing lines (474, 491) are almost certainly the untested raise branches |
| `engines/dialogue/dialogue_handler.py` (167 stmt) | 94.6% | `test_dialogue_handler_clock_tick.py`, `test_dialogue_handler_fallback_v14.py`, `test_tts_dialogue_handler.py` + 11 more | **Real** |
| `engines/gossip/gossip_handler.py` (111 stmt) | 96.4% | 7 dedicated files (`test_gossip_determinism.py`, `_distort`, `_emotion_wiring`, `_event_selection`, `_n_plus_one`, `_rumor_integration`, `_spread_service`) | **Real** |
| `utils/errors.py` (167 stmt) | 98.8% | `test_errors.py`, `test_errors_machinery.py` + 59 more | **Real** |
| `engines/quest/quest_lifecycle_engine.py` (98 stmt) | 85.7% | `test_quest_lifecycle_engine.py`, `test_quest_lifecycle_engine_v14.py` (13 test fns) | **Real** |
| `engines/quest_generation/quest_generation_engine.py` (135 stmt) | 87.4% | `test_quest_generation_engine.py` (unit, 11 fns) + `tests/contract/test_quest_generation_engine.py` | **Real** |
| `graph/intent/intent_queries.py` (78 stmt) | **34.6%** | `test_intent_repository.py` (4 tests) | **Gap — mock-shielded, not import-only.** See CR-L15-02: every test that references this module's 12 functions (`test_intent_repository.py`, `test_intent_queue_writer.py`, `test_intent_queue_reader.py`) `patch()`es them out at the caller's import site before invoking the wrapper. No integration/contract test picks up the slack. |

**Quantified answer to "what fraction of 87.86% is import-only":** among the 10 largest modules — the highest-leverage sample, since a fake-coverage problem would show up here first — **zero** show the "high-%-but-never-called" pattern the brief hypothesized. The two real defects found are different in kind: one module is *honestly low* (`intent_queries.py`, 34.6%, dragging the average down, not up) and one is *high via an untested side channel* (`config.py`'s validators, executed as DI-wiring fallout rather than intentional test design — 2 known-untested lines, negligible in isolation). Broadening to the population of trivial `__init__.py`/`Protocol`-stub files (many at 1 statement, 100% covered by nothing more than being imported anywhere) adds at most another ~30-40 statements of true "exists because it was imported" coverage — under 0.3% of the 17,796 `npc_engine` total. **Honest estimate: import-only inflation is small, under ~2% of the headline number** — the 87.86% is mostly real, modulo the separate and much larger validity problem in §6/CR-L15-01 (coverage whose *underlying test run* depends on live infra being reachable).

### 5. Cost per commit

Measured directly (warm caches, this machine):

```
$ time ruff check src/                        # pre-commit hook `ruff`      → 0.257s
$ time ruff format --check src/               # pre-commit hook `ruff-format` (would-be) → 0.293s
$ time python scripts/check_rules.py          # pre-commit hook `check-rules` (always_run) → 1.287s
$ time python scripts/check_harness_honesty.py# pre-commit hook `check-harness` (always_run) → 0.497s
$ time python scripts/mypy_ratchet.py         # pre-push hook `mypy-ratchet` → 2.566s
```

`.pre-commit-config.yaml` (read directly): commit hooks = `ruff`, `ruff-format`, `check-rules`, `check-harness`; **only** `mypy-ratchet` is `stages: [pre-push]`. **`make check` (including `test-cov`/`test-cov-evals`) is not a hook at all** — nothing in `.pre-commit-config.yaml` invokes it, and `.github/workflows/ci.yml` doesn't run it as one job either (it splits the 15 targets across 4 parallel jobs: `static-analysis`, a 3-way `v13-tests` matrix, `coverage-gate`, `v14-p4-gates`).

- **Actual git-enforced cost**: commit ≈ 2.33s, +push ≈ 2.57s → **≈ 4.9s per commit+push**, measured.
- **967 commits × real enforced cost** ≈ 967 × 4.9s ≈ **4,738s ≈ 1.3 hours total**, to date.
- **Orchestrator's requested model** ("assume `make check` runs once per commit"): 967 × 595s = 575,395s = **159.8 hours ≈ 6.66 days** of serial wall-clock.
  - Sanity check against the busiest real day: `git log --format='%ad' --date=short | sort | uniq -c | sort -rn` → **2026-06-12: 107 commits** (matches the brief's "max 107/day" exactly). 107 × 595s = 63,665s = **17.68 hours inside one 24-hour day** — physically incompatible with also writing 107 commits' worth of code that day. This is strong (if indirect) evidence that `make check` in its full 595s form is **not** run once per commit in practice; it is a task/phase-boundary gate (`/expand-next`'s "make check gating" per phase), not a per-commit one. See CR-L15-04.

### 6. `--cov` scope

Reconciled precisely by re-running coverage and inspecting the JSON (`coverage.json`, `files` map):

```
npc_engine files measured:            616   17,796 statements, 15,605 covered → 87.69%
evals/matchers.py + summary.py + runner.py:  545 statements, 337 covered
combined (== `make test-cov`'s scope):     18,341 statements  → 86.92%  (orchestrator's baseline run: 87.86% — 616 files is a big surface, ~1pt run-to-run drift is plausible non-determinism, not investigated further)
```

**The "18,341 vs 68,218-LOC `src/`" tension is fully explained, not a scope defect.** All 616 measured `npc_engine` files are real; nothing is silently excluded (`pyproject.toml`'s `[tool.coverage.run] source = ["src/npc_engine", "evals"]` instruments the whole tree, independent of which `--cov=` flags pytest-cov is given). The low statement:LOC ratio (17,796/67,331 measured-file LOC = **26.4%**, max observed anywhere in the tree is 59%) is a direct, measured consequence of this repo's own mandatory-docstring rule: every one of ~40 trivial `__init__.py` files is 100% covered at 1 statement / 13-14 lines (one paragraph of required package docstring, no code), and Protocol/port stub files (`dialogue_context_port.py`: 4 stmt / 68 lines) are similarly docstring-heavy. This is a real, if unusually low, ratio — not a hidden-package bug.

**`evals/` is also fully measured**: 110/110 `.py` files under `evals/` appear in the coverage JSON (0 missing) — the same 5,993-statement, 79.76%-adjacent figure recurs identically whether measured via the full `tests/` run or the narrow `test-cov-evals` target, because the same 110 files are the only ones any test imports either way.

**What genuinely has zero coverage floor** — confirmed via `grep -n "cov=" Makefile` (4 lines total: `test-cov`, `test-cov-v13`, `test-cov-full-report` [non-gating], `test-cov-evals`; none mention `scripts`, `e2e`, or `demo_game`):

| Body | LOC | Coverage floor? |
|---|---|---|
| top-level `scripts/` (48 files — `check_rules.py`, `check_layers.py`, `mypy_ratchet.py`, `check_test_quality.py`, etc.) | 7,821 | **None.** Tested by 17 files under `tests/unit/scripts/`, but no `--cov=scripts` anywhere, ever. |
| `e2e/` | 7,597 | **None.** Runs via `pytest e2e/scenarios` (in `testpaths`) but never appears in a `--cov=` flag. |
| `demo_game/` non-test code | 21,109 (36,961 total − 15,852 test) | **None.** `make test-demo` is `pytest demo_game/tests/ -q` — no `--cov` flag, no floor, not even a report. |

**Total shipped/tooling LOC under no coverage floor at all: 7,821 + 7,597 + 21,109 = 36,527 LOC**, against 88,359 LOC that does carry an enforced floor (68,218 `src` @ 80% + 20,141 `evals` @ 75%) — **~29% of the codebase's non-test surface ships with zero coverage enforcement**, including the very meta-scripts (`scripts/`) that enforce every other rule in this document.

---

## Findings

### [CR-L15-01] "Unit" tests in the eval harness make real, unmocked network calls to Ollama and the live API

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `evals/run_config.py:250-288` — `resolve_run_config()` defaults `fetch_generation_digest`/`fetch_judge_digest`/`fetch_ollama_version_fn` to `engine_adapter.fetch_model_digest`/`fetch_ollama_version` (`evals/engine_adapter.py:83-129`, real `httpx.post`/`httpx.get` to `DEFAULT_JUDGE_URL = "http://localhost:11434"`, `evals/judge_config.py:30`) and always calls `corpus_fields(fetch_corpus_fingerprint)` (`evals/engine_adapter.py:246-274`, real `httpx.get` against the live engine API). `tests/unit/evals/test_run_config.py` calls `resolve_run_config(...)` in 11 of its tests **without** passing any of the 4 injectable fakes (confirmed by grep — only 2 tests in the file pass `fetch_generation_digest=`/`fetch_judge_digest=`/`fetch_ollama_version_fn=`, and *none* ever overrides `fetch_corpus_fingerprint`). Separately, `evals/matchers.py:252` (`_eval_binary_judge`) does a real `httpx.post(f"{_JUDGE_URL}/api/generate", ...)`; `tests/unit/engines/test_eval_runner_loop.py:145` names a case `"case_neg_x"`, which matches `runner._GUARD_PREFIXES` (`evals/runner.py:38`), auto-injecting a `tone_judge` expectation (`evals/runner.py:104-111`) that is evaluated for real. Root `tests/conftest.py:1-4` states as its contract: *"Does NOT: connect to Neo4j, call LLM services, or modify production data."* — directly contradicted. Reproduced twice: `pytest tests/unit/engines/test_eval_runner_loop.py -q --durations=5` → 26.52s then 26.19s for the one affected test, both runs, consistent with `DEFAULT_JUDGE_TIMEOUT_S = 30.0` (`evals/judge_config.py:31`) minus real generation time. Summed real-network cost across the identified tests in the `tests/ -q --durations=25` run: ~124.6s (`test_run_config.py`, 11 tests) + ~17.0s (`test_generate_runner_k.py`, 2 tests) + 27.2s (`test_eval_runner_loop.py`, 1 test) ≈ **169s of the 333s total `make test` wall-clock (≈51%)**.
- **Cost of inaction:** Every `make test` / `make test-cov` / `make test-cov-evals` run is silently contingent on Ollama and the API being reachable at fixed default URLs. If either is down (a very plausible CI state — CI's `coverage-gate` job in `.github/workflows/ci.yml` never starts Ollama or docker-compose), these tests still "pass" today because every fetch function catches its own exception and returns `None`/`score=None` (`evals/engine_adapter.py`'s `except` blocks), but the wall-clock and the actual code path exercised (success vs. `except`) differ per-environment — meaning the coverage percentage attributed to `run_config.py`, `engine_adapter.py`, and `matchers.py`'s judge path is not a fixed property of the code, it is a property of whatever infrastructure happened to be running when the suite last executed. That is the CRITICAL-tier "coverage number used to make decisions that is not a valid measurement" the review brief called out by name.
- **Fix sketch:** Give every call site in `test_run_config.py`/`test_generate_runner_k.py` the same `fetch_*` fake-injection pattern the file's own two mocked tests already use; rename `test_eval_runner_loop.py`'s guard-prefixed case id to something outside `_GUARD_PREFIXES` (or explicitly assert on the injected `tone_judge` guard and mock `matchers.evaluate`). No production code changes needed — `resolve_run_config()` already has the injection seams.
- **Effort:** S (<2h) — mechanical, seams already exist.
- **Blast radius:** `tests/unit/evals/test_run_config.py`, `test_generate_runner_k.py`, `tests/unit/engines/test_eval_runner_loop.py` only. Fixing this removes ~169s (~28%) from `make test`'s 595s-inclusive `make check` budget and ~169s×2 (paid again inside `make test-cov-evals`, since `test_run_config.py` is under `tests/unit/evals/`) from the combined gate.

### [CR-L15-02] `intent_queries.py`'s real query logic is unverified — every caller mocks it out three layers deep

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `src/npc_engine/graph/intent/intent_queries.py` defines 12 public async functions (`get_npc_location`, `get_player_location`, `get_unmet_needs`, `get_witnessed_events`, `get_unresolved_goals`, `count_npc_pending_intents`, `get_lowest_score_pending`, `delete_intent_by_id`, `merge_pending_intent`, `get_pending_for_player`, `mark_intent_delivered`, `expire_stale_intents` — `intent_queries.py:118-338`). Measured coverage: 78 statements, 27 covered = **34.6%** (vs. 85.7-99.1% for the other 9 largest `src/npc_engine/` modules — see §4 table). `tests/unit/graph/test_intent_repository.py` (4 tests) `patch()`es `get_npc_location`, `get_witnessed_events`, `enqueue_intent`, `expire_old_intents` at `npc_engine.graph.repositories.intent_repository.*` before calling the repository wrapper — the real function bodies never run (test names are literally `test_*_delegates`). `tests/unit/engines/test_intent_queue_writer.py` and `test_intent_queue_reader.py` do the same at `intent_queue_writer`/`intent_queue_reader`'s import sites for the remaining 8 functions. `grep -rl "intent_queries\|intent_repository\|IntentRepository" tests/integration tests/contract` → no matches — no integration test exists to exercise the real Cypher-adjacent logic either.
- **Cost of inaction:** A bug in any of these 12 functions' actual query construction or result-shape handling (e.g. a wrong Cypher parameter, an off-by-one in `expire_stale_intents`'s cutoff comparison, a KeyError in `get_unresolved_goals`'s row parsing) has zero chance of being caught by the unit suite and no integration test as a backstop.
- **Fix sketch:** Add a real (Neo4j-test-DB) integration test per CLAUDE.md's own rule ("Functions touching Neo4j have integration tests against a real test DB, not mocks") for at minimum the 4 write-path functions (`merge_pending_intent`, `delete_intent_by_id`, `mark_intent_delivered`, `expire_stale_intents`) where a query-construction bug would silently corrupt state.
- **Effort:** M (<1d)
- **Blast radius:** New test file(s) under `tests/integration/`; no production code change required.

### [CR-L15-03] `check-test-quality` cannot fail `make check` regardless of what it finds

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `scripts/check_test_quality.py:7` (module docstring): *"Exits 0 always (report-only); gate wired into make check in EVAL-P15.4."* Confirmed in code: `main()` (`scripts/check_test_quality.py:250,261`) `return 0` unconditionally regardless of findings; `sys.exit(main())` at line 265 therefore always exits 0. Ran it live: `check-test-quality: 0 issues found.` (0.0s of real work today, 3s per the orchestrator's `make check` timing table — the gap is process-startup/AST-walk overhead across `tests/`, not analysis work).
- **Cost of inaction:** The Makefile target and the review's own framing present `check-test-quality` alongside 14 real gates ("15 targets, all exit 0") as if a violation would block `make check`. It cannot. If someone adds a `BARE_EXCEPTION_RAISES`/`VACUOUS_MOCK_NOT_CALLED` pattern tomorrow, `make check` stays green and nobody is notified except by reading stdout.
- **Fix sketch:** Either flip it to `sys.exit(1)` on any non-waived finding (now that the codebase already sits at 0 findings, this is a safe, immediate ratchet), or rename the Makefile target/docs to make its advisory-only nature explicit so it isn't miscounted as an enforcement gate.
- **Effort:** S (<2h)
- **Blast radius:** `scripts/check_test_quality.py`, `tests/unit/scripts/test_check_test_quality.py` (must assert the new exit code), `Makefile` comment at line ~180-183.

### [CR-L15-04] `make check`'s 595s is not the actual per-commit gate — the real one is ~5s

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Process
- **Evidence:** `.pre-commit-config.yaml` (full file read) wires only `ruff`, `ruff-format`, `check-rules`, `check-harness` to `git commit` and only `mypy-ratchet` to `git push` (`stages: [pre-push]`); none of `test`, `test-cov`, `test-cov-evals`, `check-layers`, `type-evals`, etc. are hooked at all. `.github/workflows/ci.yml` runs the 15 targets across 4 separate jobs, never `make check` as one invocation. Measured actual hook cost: 2.33s (commit) + 2.57s (push) ≈ 4.9s. Arithmetic check against `git log`-derived real commit rate: the busiest real day (`2026-06-12`, 107 commits, confirmed via `git log --format='%ad' --date=short | sort | uniq -c | sort -rn`) would require 107 × 595s = 17.68 hours of serial `make check` time inside one 24-hour day if it ran once per commit — not physically compatible with also writing that many commits.
- **Cost of inaction:** Nothing breaks today, but any future process document or automation that assumes "`make check` runs on every commit, so it costs `commits × 595s`" will overstate real gate-time spent by roughly 3 orders of magnitude (159.8h modeled vs. ~1.3h actually spent in git hooks) and will misallocate effort trying to speed up a gate that is not, in fact, the commit-path bottleneck.
- **Fix sketch:** If `make check` is meant to run once per task/phase (matching `/expand-next`'s "make check gating" language), document that explicitly next to the pre-merge checklist in `project-harness/CLAUDE.md` rather than leaving "before declaring a task done, run this checklist" ambiguous about frequency.
- **Effort:** S (<2h) — documentation only.
- **Blast radius:** `project-harness/CLAUDE.md` pre-merge-checklist section.

### [CR-L15-05] `mypy src/` runs twice per `make check` under two different mechanisms

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `tests/unit/conformance/test_sev15_type_gate.py:13-22` (`test_mypy_exits_zero`) shells out via `subprocess.run([sys.executable, "-m", "mypy", "src/", "--no-error-summary"], ...)` inside the pytest run — measured at 6.40s in the `tests/ -q --durations=25` run. `make type` (a separate, dedicated Makefile target) already runs the equivalent `mypy` invocation as its own `make check` step, measured by the orchestrator at 7s. Both are part of the same `make check` invocation (the conformance test runs inside `make test`/`test-cov`, which is also a `make check` target).
- **Cost of inaction:** ~6-7s of pure duplication per `make check` run — small in isolation, but a second, independent implementation of "mypy must be 0" means the two can silently diverge (different `mypy` invocation flags, different CWD) without anyone noticing until one fails and the other doesn't.
- **Fix sketch:** Either drop `test_mypy_exits_zero` (the dedicated `make type` target already gates this) or have it invoke the exact same code path `make type` uses (e.g. shell out to `make type` or import a shared helper) so there is one source of truth for "how do we check mypy".
- **Effort:** S (<2h)
- **Removes:** ~10 lines / 1 file (if dropped)
- **Blast radius:** `tests/unit/conformance/test_sev15_type_gate.py` only.

### [CR-L15-06] 36,527 LOC of shipped/tooling code — including the gate scripts themselves — carry no coverage floor

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `grep -n "cov=" Makefile` → exactly 4 lines (`test-cov`, `test-cov-v13`, `test-cov-full-report`, `test-cov-evals`), none referencing `scripts`, `e2e`, or `demo_game`. `make test-demo` recipe (`Makefile:604-605`) is `pytest demo_game/tests/ -q` — no `--cov` flag at all. Measured: top-level `scripts/` (48 files, tested by 17 files under `tests/unit/scripts/` but never gated) = 7,821 LOC; `e2e/` = 7,597 LOC; `demo_game/` non-test code = 36,961 − 15,852 (its own test LOC) = 21,109 LOC. Total = **36,527 LOC with zero enforced coverage floor**, against 88,359 LOC (`src` 68,218 @ 80% + `evals` 20,141 @ 75%) that does have one — **~29% of the codebase's shipped non-test surface**.
- **Cost of inaction:** `scripts/` is not incidental — it contains `check_rules.py`, `check_layers.py`, `mypy_ratchet.py`, `check_test_quality.py`, `check_harness_honesty.py`: the very enforcement mechanisms this whole review's "make check = 15 targets, all exit 0" baseline depends on. A regression in one of those scripts that makes it silently pass (a false "OK") would not itself be caught by any coverage floor, only by whatever ad hoc unit tests happen to exist for it.
- **Fix sketch:** Add `--cov=scripts` to whichever target already runs `tests/unit/scripts/` (it currently runs inside plain `make test`); add a `--cov` flag (even a low bar, e.g. 50%, ratcheted up over time) to `make test-demo`, matching the existing `test-cov`/`test-cov-evals` pattern.
- **Effort:** M (<1d) — mechanical Makefile change plus whatever floor-miss cleanup surfaces once the number is first measured.
- **Blast radius:** `Makefile` (`test-demo`, and whichever target covers `tests/unit/scripts/`); CI workflow if it should also gate on it.

---

## Pre-merge checklist (this review task)

- [x] Read-only — no source file edited, created, or deleted (only this evidence file written)
- [x] No commit made
- [x] Every claim above is file:line, a pasted live command + output, or a traced call chain
- [x] Severities follow the brief's calibration (invalid coverage number → CRITICAL; slow-but-not-behavior-changing suite → not escalated past MEDIUM)
- [x] Neo4j-host-access limitation stated up front; nothing below required it

---

## L1 — Engines

# CR-L01 — Engines lens (engines/, services/, retrieval/, graph/, scheduler/)

Branch `eval-ab-context-arms`, HEAD d46ae42. Live API at `http://127.0.0.1:8000` used for
read-only confirmation (auth: `Authorization: Bearer $API_KEY_SECRET`; the `X-API-Key`
header is *not* accepted — `auth/api_key.py:23`). No file in the repo was modified.

---

## Required measurements

### 1. Fallback contract wired at the call site?

**Selection method.** The 5 engines CLAUDE.md names (dialogue, gossip, emotion, quest, tick
scheduler) + the 8 largest `engines/` subpackages by LOC excluding `ports/` (protocols only)
+ 5 tick engines chosen to span LLM-calling / graph-only / service-delegating shapes. 18 rows.

**Not reached at depth (21 packages, 4,462 LOC):** agenda, clique, currency, deception,
director (partial only), economy, faction_politics, idempotency, investigation,
knowledge_learning, memory, mood, need, oath, planning, player_model, relationship, routine,
scheming, story_pacing, succession, treaty, tts.

CLAUDE.md's two contracts: **(G)** Neo4j unavailable → `GraphUnavailableError` → API 503;
**(L)** LLM timeout → serve `fallback_responses.json`.

Baseline facts, re-verified this session:

```
$ grep -rn "raise GraphUnavailableError" src/           → 0
$ grep -rn "except.*GraphUnavailableError" src/         → 0
$ grep -rn "raise TokenBudgetExceededError" src/        → 0
$ grep -rn "503" src/npc_engine/api/ --include=*.py     → 0
```

| # | Engine (LOC) | Documented fallback (quoted) | Wired at call site? | Verdict |
|---|---|---|---|---|
| 1 | dialogue (1917) | `llm_client.py:85` "Returns a deterministic fallback dict on LLMTimeoutError, LLMRequestError" | **G:** no — `degradation.py:107,119` bare `except Exception` turns a Neo4j outage into a canned 200. **L:** yes — `dialogue_handler.py:179` → `llm_client.py:102,105,246` → `_load_fallback_dialogue` | L wired, G **inverted** |
| 2 | gossip (1265) | none declared | `gossip_handler.run_tick` has no graph `except`; `_run_side_effects:333` `except Exception: LOGGER.exception(...); raise` → swallowed by `tick_scheduler.py:239` | unwired |
| 3 | quest / lifecycle (1264) | `quest_lifecycle_engine.py:93` "Best-effort — skips on error." | `:105 except Exception:` warn + `return` — only for commitment memory. Graph errors elsewhere propagate to `api/errors/exception_handlers.py:122` catch-all → **500** | unwired (G) |
| 4 | emotion (815) | none declared | `emotion_updater.py:167` `if self._writer is not None:` — a missing writer silently no-ops the graph write-through | unwired |
| 5 | tick scheduler (1190) | `tick_scheduler.py:224` "logs `tick_engine_error`, records the error, and returns None … without killing the loop" | wired at `:239-246` and `:386-389` — **this is the only fallback in the tick path, and it is a catch-all** | wired, but see F-10 |
| 6 | interaction (1176) | none declared | `quest_handler.py:158` `except Exception: _logger.warning("update_objective failed …")` — objective silently not advanced | unwired |
| 7 | llm adapters (1140) | `openai_adapter.py:12` "on timeout raises LLMTimeoutError; on transport/parse failure raises LLMRequestError" | raises correctly (`ollama_adapter.py:105,173,259`); **only 2 files in all of `engines/` catch these** (`dialogue/llm_client.py`, `quest_generation/quest_generation_engine.py`) | raise wired, catch 2/N |
| 8 | quest_generation (1139) | `:284` docstring absent; code returns `{}` | `:284 except (LLMTimeoutError, LLMRequestError): return {}` and `:324 → return default_description`. Does **not** use `fallback_responses.json` | partially wired, silent |
| 9 | proactive_dialogue (779) | `proactive_engine.py:187` "LLMTimeoutError: If the LLM backend times out." | `proactive_tick_adapter.py` contains **zero** `except` — propagates to `_run_engine_safe` → swallowed | unwired |
| 10 | events (405) | none declared | no `except`; `run_tick` also `return {"created": 0}` at `event_handler.py:171` with no log | unwired |
| 11 | chapter (381) | `chapter_engine.py:274` "LLM chapter labeling failed … using rule-based fallback" | wired: `:272 except Exception:` → `label_chapter_by_rules(...)`. Does not use `fallback_responses.json` | wired (own corpus) |
| 12 | reputation (381) | `reputation_engine.py:114` "skip silently if edge missing or standing too low" | `:121,:155,:164 except RelationEdgeNotFoundError: return` — three silent exits | wired-as-silent |
| 13 | military (413) | `military_battle_service.py:59` "**Fallback: Neo4j unavailable → raises GraphUnavailableError (propagated to engine).**" | **Nothing raises `GraphUnavailableError` anywhere in `src/`.** `military_engine.py` has no `except`. The promised exception cannot occur | **unwired — docstring is fiction** |
| 14 | military resources | `military_resource_service.py:47` same sentence | same | **unwired — fiction** |
| 15 | memory_consolidation (236) | `:137` "LLM error during consolidation … skipping" | `:137 except Exception: return None`; `:153` swallows the witnessed query. **Engine is never wired into the scheduler at all** — see F-03 | dead on tick path |
| 16 | skill_progression (87) | none | `skill_progression_engine.py:71 except Exception: _LOGGER.exception(...)` — XP silently not awarded | unwired |
| 17 | context assembly (`retrieval/context`) | CLAUDE.md: "`context_builder.py` raises `TokenBudgetExceededError` if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET`" | Never raised. `context_budget_enforcer.py:348 except ContextBudgetError: return []` drops a whole tier; `:366-373` can return an **over-budget** prompt | **unwired — see F-06** |
| 18 | `dialogue_graph_port` (contract surface) | `ports/dialogue_graph_port.py:73` "GraphUnavailableError: If Neo4j is unreachable." | no implementor raises it (`graph/repositories/dialogue_repository.py` lets `neo4j.exceptions.*` through) | **unwired — fiction** |

**Verdict: 18 traced / 4 wired as documented (dialogue-L, tick scheduler, chapter, reputation) /
14 unwired.** Four of the 14 (#13, #14, #17, #18) have docstrings that *promise* behaviour the
codebase cannot produce.

### 2. Engines whose failure path is untested

Method: for each engine in the sample, locate the specific `except`/fallback line, then grep
`tests/` for the log key, the error type, or a failure-injecting mock reaching that branch, and
read the test. A test that asserts a constant, or that would still pass with the fallback
deleted, counts **untested**.

| Engine | Failure branch | Test that drives it | Untested? |
|---|---|---|---|
| dialogue (LLM) | `llm_client.py:102,105` | `tests/unit/engines/test_dialogue_handler_fallback_v14.py` — injects a raising LLM | tested |
| dialogue (graph→canned) | `degradation.py:119` | none drives a graph failure through `handle()`; `test_dialogue_retrieval_profile.py:71` is a **source-string assertion** (F-05) | **untested** |
| tick scheduler isolation | `:239` | `test_tick_scheduler_engine_isolation.py:89-179` (`_ThrowingEngine`) — covers gossip, event, story_pacing, faction_politics only (4 of 27 slots) | 4/27 tested |
| gossip | `_run_side_effects:333` re-raise | grep `create_rumor` failure injection in `tests/` → none | **untested** |
| emotion | `_write_through` writer-None | no test asserts the writer is present in the composition root | **untested** |
| quest lifecycle | `:105` `commitment_memory_skipped_no_world_state` | `grep -rl "commitment_memory_skipped" tests/` → **empty** | **untested** |
| interaction | `quest_handler.py:158` | `grep -rn "update_objective failed" tests/` → none | **untested** |
| quest_generation | `:284,:324` | `test_quest_generation_engine.py` injects LLM errors | tested |
| proactive_dialogue | no branch exists | n/a — nothing to test | **untested (no path)** |
| events | `:171 created:0` | `test_gossip_event_selection.py` covers selection, not the empty-location exit | **untested** |
| chapter | `:272` | `test_chapter_engine.py` asserts `label_chapter_by_rules` | tested |
| reputation | `:121,155,164` | `test_reputation_engine.py` references `RelationEdgeNotFoundError` | tested |
| military | none | n/a | **untested (no path)** |
| memory_consolidation | `:137,:153` | `test_memory_consolidation_engine.py` | tested; **but the engine never runs (F-03)** |
| skill_progression | `:71` | `test_skill_progression_engine.py` — no raising repo | **untested** |
| context budget | `:348 except ContextBudgetError` | `test_context_budget_enforcer_v14.py:375-384` asserts fill_to_budget *raises* only for tier0; nothing asserts the tier-drop path | **untested** |
| context over-budget | `:370 if not droppable: break` | none | **untested** |

**Count: 11 of 17 sampled failure paths are untested** (two of which have no failure path at
all to test). The tick-isolation contract is tested for 4 of 27 engine slots.

### 3. Where a bug would be silent

`except` blocks in `engines/ services/ retrieval/ scheduler/ graph/` whose body contains no
`raise` (mechanical scan, script kept in scratch): **66 sites**. Worst 10 by consequence:

| Rank | Site | Why it is silent | Consequence |
|---|---|---|---|
| 1 | `scheduler/tick_scheduler.py:239` (+`:386`) | catch-all `except Exception` around every one of 27 engines | The entire world simulation can be dead and `POST /v1/clock/advance` still returns **200** with empty per-engine lists. Only `GET /v1/admin/system/engines` reveals it, and only if a store is injected |
| 2 | `retrieval/context/context_budget_enforcer.py:348` | `except ContextBudgetError: return []` | A whole context tier vanishes from the prompt; the NPC just sounds less informed |
| 3 | `retrieval/context/context_budget_enforcer.py:366-373` | `while … if not droppable: break` | Returns an **over-budget** prompt with no error and no metric; Ollama silently truncates it |
| 4 | `engines/dialogue/degradation.py:107` and `:119` | bare `except Exception` twice | Neo4j outage, `RetrievalProfileNotFoundError`, `ContextBudgetError`, and a genuine bug all collapse to the same canned 200 (F-04) |
| 5 | `engines/interaction/quest_handler.py:158` | `except Exception: _logger.warning("update_objective failed …")` | Quest objective never advances; the quest cannot be completed and nothing surfaces |
| 6 | `engines/skill/skill_progression_engine.py:71` | `except Exception: _LOGGER.exception(...)` | XP silently not awarded; progression quietly stops |
| 7 | `engines/quest/quest_lifecycle_engine.py:105` | warn + `return` | Accepted quests form no commitment memory; the NPC has no recollection of the deal |
| 8 | `engines/quest_generation/quest_generation_engine.py:284` | `return {}` | A quest is generated with **empty slots** rather than not generated |
| 9 | `graph/graph_reader.py:214` | `except Exception: return value` | Any coercion failure returns the raw value; malformed graph data reaches the prompt untyped |
| 10 | `retrieval/embedding/embedding_reconciler.py:154` | `except Exception: LOGGER.exception(...); await asyncio.sleep(...)` | The reconciler loops forever on a permanent failure; embeddings drift with no alarm |

**Defaults substituted for missing domain-critical data** (`.get(field, default)` — 30 sites):
`engines/gossip/gossip_handler.py:227 int(sharer.get("honesty", 50))` is the worst: `honesty`
feeds *both* the distortion probability and the SHA-256 seed (`gossip_distort.py:99-112`), so a
Character node missing `honesty` silently changes gossip determinism rather than failing.
`engines/gossip/pair_selector.py:24 character.get("gossipy", 50)` silently equalises pair
ranking. In Cypher, `graph/gossip/gossip_batch_queries.py:46 coalesce(r.trust, 50)` makes "no
RELATES_TO edge" indistinguishable from "neutral trust".

**Empty-list / zero returns indistinguishable from failure:** `event_handler.py:171`
(`created: 0` with no log), `gossip_batch_queries.py:113-114` (`if not pairs: return []`),
`context_budget_enforcer.py:348` (`return []`), `quest_generation_engine.py:284` (`return {}`).

**Silent clamping in probability code:** `gossip_distort.py:76`
(`max(0.0, min(1.0, …))`), `:218` (`min(1.0, probability * hostile_distortion_factor)`),
`:241` (`min(100, max(1, int(probability * 100)))`), `:96` (`min(100, max(1, …))`). Each clamp
is legitimate individually; none logs when it binds, so a mis-tuned
`GOSSIP_DISTORTION_BASE` that saturates to 1.0 for every pair is invisible.

### 4. The LLM-timeout half of the contract

`src/npc_engine/data/fallback_responses.json` **exists** (6 archetype keys + `default`).

```
$ grep -rn "LLM_FALLBACK_PATH\|fallback_responses" src/ --include=*.py
src/npc_engine/config.py:106:    LLM_FALLBACK_PATH: str = "data/fallback_responses.json"
src/npc_engine/config.py:448:    @field_validator("LLM_FALLBACK_PATH")
src/npc_engine/engines/dialogue/dialogue_handler.py:179:            fallback_path=self._settings.LLM_FALLBACK_PATH,
```

**Exactly one call site.** It is genuinely wired: `dialogue_handler.py:179` →
`DialogueLLMClient.__init__` → `llm_client.py:102/105` (`generate_response`), `:246`
(`stream_text`), `:429` (`ValidationError` in `_run_llm_pipeline`). This half of the contract is
real for dialogue.

It is wired for **nothing else**. The other LLM-calling engines have their own private fallback
corpora or none at all:

- `chapter_engine.py:274` → `label_chapter_by_rules` (rule-based, not the JSON).
- `quest_generation_engine.py:284/:324` → `{}` / `default_description`.
- `memory_consolidation_engine.py:137` → `None`.
- `proactive_engine.py:187` documents `LLMTimeoutError` and **nothing catches it**.
- `degradation.py:32-46` reads a *third* corpus (`CANNED_RESPONSES_DIR/*.yaml`) and hardcodes
  `return "I need a moment to think."` at `:46` — byte-identical to
  `fallback_responses.json`'s `default[0]`, maintained in two places.

### 5. Token budget enforcement

`TokenBudgetExceededError` is `class TokenBudgetExceededError(Exception)` at
`utils/errors.py:301` — a bare `Exception`, and **it is imported by nothing**. Across all of
`src/` it is neither raised, caught, nor referenced; the only live mentions are
`docs/PROMPT_DESIGN.md:91` and `project-harness/archive/`.

What the code actually does when the budget is exceeded, on the shipped path
(`context_builder.py:575` → `fill_to_budget_with_report`):

- `context_budget_enforcer.py:213-217` and `:266-269`: non-fitting items are `continue`d — dropped.
- `:348`: `except ContextBudgetError: return []` — a whole compressible tier is dropped.
- `:366-373`: if the *serialized* prompt is still over budget and nothing droppable remains,
  the loop `break`s and returns the over-budget prompt.
- The only surviving raise sites are `enforce_context_budget` (`:74-88`), which the production
  path never calls — `grep` shows callers only in `__init__.py` re-exports and unit tests.

Drops are recorded on a `BudgetFillReport` and attributed by `_attribute_drops` (`:378-405`), so
the data exists — but nothing on the dialogue path raises, logs at WARNING, or fails a turn.

**The 2026-08-27 fix (`96d83eb`) is real, and its guard is a frozen snapshot, not a live check.**
The commit raises `OLLAMA_CONTEXT_LENGTH` 8192 → 12288 (budget 1062 → 5158) and re-sizes tier
ceilings, and the new test compares the shipped default against *measured demand* rather than
against the window — which is a genuine improvement over `TestShippedDefaultsAreCoherent`, whose
`system + budget + output + headers <= window` is satisfied by construction because the budget is
derived as `window - overhead`. Two caveats:

1. `MEASURED_ROSTER_CEILING_TOKENS = 1151` and `MEASURED_TIER_MAXIMA` (`:45-54`) are hand-copied
   constants from one run. Nothing re-measures them. If an engine adds a tier-A slot tomorrow,
   demand rises, the constants do not, and the test still passes while items are dropped again —
   exactly the ~2.5-month failure mode it was written to end.
2. `test_the_derived_budget_is_the_window_minus_the_named_overhead` (`:104-106`) **is
   tautological**: it asserts `_code_default_budget() == window - PROMPT_WINDOW_OVERHEAD_TOKENS`,
   and `_code_default_budget()` is *defined* at `:75` as `max(MIN, window - overhead)`. It
   restates its own helper and can only fail if the 512-token floor binds. The other five
   assertions are substantive.

### 6. Gossip distortion chain correctness

**Seeded and logged?** Yes for distortion: `compute_seed_value` = `int(sha256(f"{summary}|{honesty}|{trust}|{tick_id}")[:8], 16)`
(`gossip_distort.py:99-112`), logged at DEBUG with the probability at `gossip_handler.py:243-251`
and returned in `run_tick`'s `seeds_used`. Secret propagation seeds are logged at
`gossip_handler.py:388-391`. **Event sampling is not**: `event_handler.py:129
rng = self._rng or random.Random(tick_id)` logs nothing, violating the same rule gossip honours.
Pair selection uses no RNG (deterministic sort), so nothing to log there.

**Does 2-hop distortion compound? No — CONFIRMED, live.** Traced chain:
`gossip_handler.py:170` `select_batch_event_trust` →
`graph/repositories/gossip_repository.py:80` →
`graph/gossip/gossip_batch_queries.py:29-47`, which returns `best_event.summary` — the
**canonical `Event` node property** — and never `k.distorted_summary` from the sharer's own
`KNOWS_ABOUT` edge. `gossip_handler.py:257` then feeds `str(row["summary"])` into
`gossip_distort`. The receiver's distorted text is written at `gossip_batch_queries.py:60` and
read back only by `graph_reader.py:33`, `rumor_trace_service.py:27` and
`reputation_queries.py:46` — for *prompt display*, never as a gossip source.

Live proof (read-only, `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=northern_war_begins`):

```json
{"src_id":"captain_sorn",   "knowledge_state":"knows","distortion_level":0,
 "distorted_summary":"The northern armies have crossed the border. We are at war."}
{"src_id":"mira_innkeeper", "distortion_type":"exaggeration","source_character_id":"captain_sorn",
 "learned_at_tick":1,"distortion_level":20,
 "distorted_summary":"A soldier passing through told me the northern armies, the Iron Guard he called them, have moved on the border. …"}
{"src_id":"lira_fence",     "distortion_type":"omission","source_character_id":"mira_innkeeper",
 "learned_at_tick":10,"distortion_level":62,"distorted_summary":"The northern armies"}
{"src_id":"aldric_merchant","distortion_type":"role_swap","source_character_id":"tilda_herbalist",
 "learned_at_tick":600,"distortion_level":74,
 "distorted_summary":"They say the opposite happened: The northern armies have crossed the border"}
{"src_id":"old_henryk",     "source_character_id":"aldric_merchant","learned_at_tick":600,
 "knowledge_state":"knows","distortion_level":0,
 "distorted_summary":"The northern armies have crossed the border"}
```

`lira_fence` learned from `mira_innkeeper`, whose account is the 27-word "A soldier passing
through told me…". Omission halves the words of its input. Lira's stored text is
`"The northern armies"` — exactly `omission("The northern armies have crossed the border")`,
i.e. half of the **canonical 7-word event summary**, not half of Mira's account. Same for
`tilda_herbalist` (learned from `old_henryk`) and for `aldric_merchant`, whose role_swap prefix
sits on the canonical string. Every hop distorts the original.

**Would a test catch distortion becoming a no-op?** Partly, and not the compounding.
`tests/unit/engines/test_gossip_distort.py:48` asserts `distortion_type is not None` for one
hostile input and `:70` asserts the canonical passthrough — but **no test in the repo asserts
`result.summary != event_summary`**. If `exaggeration`/`role_swap`/`timeline_shift` returned
their input unchanged, `test_gossip_distort.py`, `test_gossip_determinism.py` and
`test_gossip_distortion_sev36.py` all still pass; only
`tests/unit/config/test_prefix_loader.py:17` (`"catastrophic" in prefix.lower()`) and the three
`test_distortion_strategy_registry.py` parity tests would catch it, and those test the
strategies in isolation, never through `gossip_distort` or the handler. **No test asserts
multi-hop behaviour at all.**

---

## Findings

### [CR-L01-01] Make gossip distortion compound across hops — today every hop distorts the original event

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** Traced chain: `engines/gossip/gossip_handler.py:170` → `graph/repositories/gossip_repository.py:80` → `graph/gossip/gossip_batch_queries.py:29-47`, which returns `best_event.summary` (the canonical `Event` node) and never `k.distorted_summary`; `gossip_handler.py:257` passes `str(row["summary"])` to `gossip_distort`. Live, read-only: `lira_fence` learned `northern_war_begins` from `mira_innkeeper` (whose stored account is 27 words) yet holds `"The northern armies"` = `omission("The northern armies have crossed the border")` — half of the canonical 7-word summary. `aldric_merchant`'s role_swap prefix likewise sits on the canonical string, not on `tilda_herbalist`'s account. See §6 for the full JSON.
- **Cost of inaction:** The project's signature demo — "gossip mutates as it travels, `captain_sorn` → `mira_innkeeper` → `old_henryk`" — is a claim the engine does not implement. Every NPC in the world holds a single-step distortion of the same source text, so the rumour never drifts, the 2-hop target never sounds different from the 1-hop one, and the differentiating behaviour a studio would license this for does not exist. It is silently wrong today; the demo only looks right because the chain is hand-seeded (`demo_game/seeds/seed.py:957-980`).
- **Fix sketch:** Change `CYPHER_BATCH_EVENT_TRUST` to return `coalesce(k.distorted_summary, e.summary) AS summary` (the pattern `graph/reputation/reputation_queries.py:46` already uses) so the sharer relays *their own* account. Add a test that runs two hops and asserts hop-2 output contains hop-1's distortion marker.
- **Effort:** M
- **Blast radius:** `gossip_batch_queries.py`, the seed derived from `summary` (determinism fixtures in `test_gossip_determinism.py` will shift), `distortion_level` semantics (compounding needs a cap), and the eval golden set if any case pins a distorted string.

### [CR-L01-02] Stop the gossip batch write from overwriting an existing KNOWS_ABOUT edge back to clean `knows`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `graph/gossip/gossip_batch_queries.py:53-62` — `MERGE (receiver)-[k:KNOWS_ABOUT]->(event) SET k.knowledge_state = w.knowledge_state, k.distortion_type = …, k.distorted_summary = …` unconditionally. Nothing in `CYPHER_BATCH_EVENT_TRUST` or `pair_selector.select_pairs` excludes a receiver who already knows the event. Live: `old_henryk` was seeded (`demo_game/seeds/seed.py:968-980`) with `knowledge_state: "rumor"`, `distortion_level: 70`, `"Word reached me the northmen have poured through king's pass, thousands dead. Utterly catastrophic…"`. At tick 600 the live graph reports `{"src_id":"old_henryk","source_character_id":"aldric_merchant","learned_at_tick":600,"knowledge_state":"knows","distortion_level":0,"distorted_summary":"The northern armies have crossed the border"}` — the seeded 2-hop distortion has been erased and replaced with clean canonical knowledge.
- **Cost of inaction:** Running the world *destroys* the demo. The scripted 5-minute scenario (`demo_game/runners/run.py:172,410` queries `old_henryk`) depends on him holding a distorted account; after ~600 ticks he holds the undistorted one. More broadly, knowledge monotonically regresses: any NPC's hard-won rumour is reset to `knows` the next time an undistorted propagation reaches them.
- **Fix sketch:** Guard the write — only overwrite when the incoming `distortion_level` exceeds the stored one, or when no edge exists (`ON CREATE SET` for the distortion fields, `ON MATCH SET` only `learned_at_tick`). Exclude receivers already holding `knowledge_state = 'knows'` in `CYPHER_BATCH_EVENT_TRUST`.
- **Effort:** M
- **Blast radius:** `gossip_batch_queries.py`, `rumor_trace_service.py` traces, the demo cache in `.cache/demo/`, and any eval case that advances the clock before asserting knowledge.

### [CR-L01-03] Wire `memory_consolidation_engine` into the tick scheduler — it has never run

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `api/dependencies_engines/__init__.py:138-162` builds the singleton `TickScheduler` and passes 25 engine slots; `memory_consolidation_engine` is not among them, and `_advanced_engine_kwargs()` (`:110-121`) returns 10 keys that do not include it — even though `get_memory_consolidation_engine()` exists at `api/dependencies_advanced/progression.py:96`. Therefore `tick_scheduler.py:530` `self._memory_consolidation_engine is None` is always true and `_maybe_consolidate_memory` returns immediately, leaving `response["consolidation"]` empty forever. Live confirmation — `GET /v1/admin/system/engines` at tick 598 returns exactly 27 engines (the 22 in `_ordered_tick_engines()` plus story_pacing, routine, chapter, gossip, event) and **`memory_consolidation` is absent from the list**.
- **Cost of inaction:** `docs/ENGINES.md` lists memory consolidation as step 6 of the tick order and the engine has its own contract YAML, prompt, LLM config and port. NPCs never consolidate dialogue into long-term memory autonomously; only the manual `POST /v1/admin/memories/consolidate/{npc_id}` route (`api/routes/knowledge/memories.py:275`) reaches it. This has presumably been true for the whole life of the engine and nothing surfaced it, because an unwired slot is silently `None`.
- **Fix sketch:** Add `memory_consolidation_engine=get_memory_consolidation_engine()` to `get_tick_scheduler()`, plus `consolidation_advance_interval` from settings. Add a test asserting every `BaseEngine | None` parameter of `TickScheduler.__init__` is supplied by the composition root.
- **Effort:** S
- **Blast radius:** Adds an LLM call to the tick path — check `skip_llm_engines` and tick latency budgets before enabling by default.

### [CR-L01-04] Narrow the dialogue degradation ladder's two bare `except Exception` blocks

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `engines/dialogue/degradation.py:103-128` — `except Exception` at `:107` (full tier) and `:119` (graph_only tier), both logging a warning and continuing, ending at `:128` with a canned `DialogueResponse` and HTTP **200**. Traced: `resolve_profile_for_turn` raises `RetrievalProfileNotFoundError` (`schema/retrieval_profile_models.py:193`) → `context_builder._validated_profile_for_turn:659` → `_build_dialogue_prompt` → `_run_llm_pipeline` (`dialogue_handler.py:413`) → `_full()` (`:226`) → caught at `degradation.py:107` → `_graph_only()` raises the same → caught at `:119` → canned. The route's handler at `api/routes/dialogue/dialogue.py:97` `except RetrievalProfileNotFoundError` is therefore **unreachable via `handler.handle()`**. The same two blocks convert a Neo4j outage into a canned 200 rather than the documented 503, and swallow `ContextBudgetError` from `context_budget_enforcer.py:74-88`.
- **Cost of inaction:** `utils/errors.py:306-317` states the class exists precisely so that "a run that silently fell back would record a `retrieval_profile` it never actually used, so an A/B arm would claim a variant that never ran — the class of silent divergence the eval programme exists to catch". On this branch (`eval-ab-context-arms`) that is exactly what happens: a typo'd arm name yields canned responses at 200 instead of a 4xx, and the arm looks merely bad rather than broken.
- **Fix sketch:** Re-raise a named allow-list before degrading — `RetrievalProfileNotFoundError`, `ContentRatingViolationError`, `ContextBudgetError`, `NodeNotFoundError` — and catch only `(LLMTimeoutError, LLMRequestError, asyncio.TimeoutError, neo4j.exceptions.Neo4jError)` per tier, mapping the Neo4j case to the documented 503.
- **Effort:** M
- **Blast radius:** Dialogue route status codes (some currently-200 turns become 4xx/503), the eval harness's expectations, and `test_dialogue_handler_fallback_v14.py`.

### [CR-L01-05] Replace the source-string test that "guards" the retrieval-profile 4xx

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `tests/unit/api/test_dialogue_retrieval_profile.py:71-82`:
  ```python
  def test_route_maps_an_unknown_profile_to_4xx() -> None:
      source = Path("src/npc_engine/api/routes/dialogue/dialogue.py").read_text(encoding="utf-8")
      assert "RetrievalProfileNotFoundError" in source
      assert "RETRIEVAL_PROFILE_NOT_FOUND" in source
  ```
  It passes today while the mapping it names is unreachable (CR-L01-04). Deleting the entire degradation-ladder re-raise would not change its result; neither would deleting the `except` clause it points at, as long as the identifier stays somewhere in the file.
- **Cost of inaction:** The one guard on the A/B programme's anti-silent-divergence invariant is green while the invariant is violated. Any future review that greps for "is this tested?" gets a false yes.
- **Fix sketch:** Replace it with a handler-level test: build a `DialogueHandler` with a stub context port that raises `RetrievalProfileNotFoundError`, call `handle()`, and assert the exception escapes rather than returning `degradation_level="canned"`.
- **Effort:** S
- **Removes:** ~12 lines
- **Blast radius:** none until CR-L01-04 lands; the replacement test is RED until then, which is the point.

### [CR-L01-06] Delete `TokenBudgetExceededError` or make the budget path actually fail

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `utils/errors.py:301` `class TokenBudgetExceededError(Exception):` — a bare `Exception`, violating the typed-hierarchy rule, and referenced nowhere in `src/` (`grep -rn "TokenBudgetExceededError" src/` returns only that definition). CLAUDE.md and `docs/PROMPT_DESIGN.md:91` both promise `context_builder.py` raises it. What the shipped path does instead: `context_budget_enforcer.py:213-217` and `:266-269` silently `continue` past items that do not fit; `:348 except ContextBudgetError: return []` drops a whole tier; `:366-373` breaks out of the trim loop and returns an **over-budget** prompt when only pinned/tier-0 items remain. The only raising function, `enforce_context_budget:74-88`, is called by nothing outside `__init__.py` re-exports and unit tests.
- **Cost of inaction:** Two documents and one exception class describe a fail-loud contract the engine does not honour; a reader budgeting prompt work trusts them. Meanwhile an over-budget prompt is handed to Ollama and truncated with no metric — the exact failure mode `96d83eb` spent a session diagnosing at the config level.
- **Fix sketch:** Delete the dead class and correct CLAUDE.md + `docs/PROMPT_DESIGN.md` to describe the real policy (drop-and-report), *and* make `_trim_to_serialized_budget`'s `break` at `:370` emit a WARNING with the overshoot so the undroppable case is observable.
- **Effort:** S
- **Removes:** ~4 lines + 2 doc claims
- **Blast radius:** `utils/errors.py`, CLAUDE.md, `docs/PROMPT_DESIGN.md`.

### [CR-L01-07] Re-measure the context-demand constants the new budget guard is frozen against

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py:45,53` hardcode `MEASURED_ROSTER_CEILING_TOKENS = 1151` and `MEASURED_TIER_MAXIMA = {"tier_a": 857, "tier_b": 96, "tier_c": 145}` from one run on 2026-08-27. Nothing re-derives them. Separately, `:104-106` `test_the_derived_budget_is_the_window_minus_the_named_overhead` asserts `_code_default_budget() == _code_default_window() - PROMPT_WINDOW_OVERHEAD_TOKENS`, and `_code_default_budget()` is *defined* at `:75` as `max(MIN_PROMPT_TOKEN_BUDGET, window - PROMPT_WINDOW_OVERHEAD_TOKENS)` — the assertion restates its own helper and can only fail if the 512 floor binds.
- **Cost of inaction:** The commit message for `96d83eb` correctly identifies that the *previous* guard was satisfied by construction. The replacement is stronger but is a snapshot: the next engine that adds a tier-A slot raises demand past 1151, the constants stay put, the test stays green, and tier-A items are dropped again — the same ~2.5-month silence, rediscovered the same way.
- **Fix sketch:** Make `make probe-ceiling` write its measurement to a checked-in JSON the test reads, and fail the gate when the recorded measurement is older than the last change to `retrieval/context/`. Delete the tautological assertion at `:104-106` or rewrite it to compare against the literal `12288 - 7130`.
- **Effort:** M
- **Blast radius:** the eval probe harness and `make check`.

### [CR-L01-08] Enforce or delete `EngineFallbackPolicy` — five engines declare a degradation policy nothing reads

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/llm_config_models.py:68-75` defines `EngineFallbackPolicy(policy: Literal["graceful_degradation","fail_fast"], tiers: list[str])`, required on every `EngineModelConfig` (`:95`). Five YAMLs declare it: `engines/{chapter,dialogue,memory_consolidation,proactive_dialogue,quest_generation}/llm_config.yaml:14-17`, all `graceful_degradation`. `grep -rn "\.fallback\b\|fail_fast\|graceful_degradation" src/ --include=*.py` finds **no production read** — no branch anywhere consults `config.fallback.policy` or `.tiers`. The only readers are tests, and `tests/integration/test_engine_llm_config_integration.py:167` asserts `config.fallback.policy in ("graceful_degradation","fail_fast")` — true for every valid config by Pydantic construction. Similarly, `EngineTimeoutsMs.canned` and `.deterministic` (`:78-88`) are read nowhere; only `.full` and `.graph_only` reach code (`dialogue_handler.py:248-249`).
- **Cost of inaction:** Setting `policy: fail_fast` on any engine changes nothing. An integrator tuning degradation per engine gets silence. Four fields of validated configuration are ceremony.
- **Fix sketch:** Either make `execute_with_degradation` (and the equivalent path in the other four engines) read `config.fallback.policy`/`.tiers` — which is the natural home for the CR-L01-04 fix — or delete the field and its five YAML blocks.
- **Effort:** M (enforce) / S (delete)
- **Removes:** ~30 lines + 5 YAML blocks if deleted
- **Blast radius:** `llm_config_models.py` is `extra="forbid"`, so deletion requires editing all five YAMLs together.

### [CR-L01-09] Assert at the composition root that every tick engine slot is filled

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** All 26 engine parameters of `TickScheduler.__init__` (`scheduler/tick_scheduler.py:56-81`) are `BaseEngine | None = None`. `_run_tick_body:466-470` runs `if engine is not None:` — a `None` slot produces no log, no status-store entry, and an empty list in the response, which is byte-identical to an engine that ran and found nothing to do. CR-L01-03 is one instance found only by counting the live `GET /v1/admin/system/engines` payload (27 entries) against `_build_empty_response()`'s 29 keys (`:308-339`). No test compares the constructor's optional slots against `get_tick_scheduler()`'s kwargs.
- **Cost of inaction:** The next engine added to `_ordered_tick_engines()` but forgotten in `dependencies_engines/__init__.py` is invisible for months, exactly as memory consolidation was.
- **Fix sketch:** Add a unit test that introspects `inspect.signature(TickScheduler.__init__)` for `BaseEngine | None` parameters and asserts each appears in the kwargs `get_tick_scheduler()` passes; or make the scheduler log `tick_engine_not_wired` once per `None` slot at startup.
- **Effort:** S
- **Blast radius:** none — test-only, unless the log is added.

### [CR-L01-10] Make gossip side effects survive one bad pair

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `engines/gossip/gossip_handler.py:311-375` iterates `distortion_map` **after** `write_batch_knowledge_propagation` has already committed (`:182`). At `:333-335` a `create_rumor`/`believe_rumor` failure is logged and **re-raised**, aborting the whole loop; `tick_scheduler.py:239` then swallows it and discards the return value, so `propagated` and `seeds_used` are lost for the tick. Every pair after the failing one gets no rumour node, no `log_gossip` trust delta (`:354`), no emotion shock (`:341`) and no embedding refresh (`:360`) — while their `KNOWS_ABOUT` edges are already written.
- **Cost of inaction:** A single malformed event leaves the graph in a half-propagated state each tick: knowledge without rumours, and relationship trust that never moves. The `_run_engine_safe` catch-all means the operator sees one `tick_engine_error` line and a `last_error` string, with no indication that N pairs were skipped.
- **Fix sketch:** Move the `try` inside the per-pair loop, count failures, and return them in the tick result dict instead of re-raising; or run the batch write and the side effects in one transaction via `transaction_coordinator.run_in_tx`.
- **Effort:** M
- **Blast radius:** `gossip_handler.run_tick` return shape (`test_gossip_determinism.py` asserts `seeds_used`), and `tick_scheduler`'s `response["gossip"]`.

### [CR-L01-11] Log the event-sampling RNG seed, as gossip already does

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `engines/events/event_handler.py:129` `rng = self._rng or random.Random(tick_id)` — no log line anywhere in `_select_template` or `run_tick`; `grep -n "seed" engines/events/event_handler.py` returns only the docstring word "seeding". Gossip logs both the seed and the probability at `gossip_handler.py:243-251` and returns `seeds_used` in the tick result. `event_handler.py:171` also returns `{"tick_id": …, "created": 0}` when `scoped_locations` is empty, with no log, so "no eligible location" and "template misconfigured" look identical from outside.
- **Cost of inaction:** An event stream that stops generating is undiagnosable without attaching a debugger; live, `event` last ran at tick 580 while the clock is at 598 and there is no record of what it sampled.
- **Fix sketch:** Log `event_rng seed=%d tick=%d template=%s` at DEBUG in `_select_template`, and add a DEBUG line to the empty-`scoped_locations` exit naming the template.
- **Effort:** S
- **Blast radius:** none.

### [CR-L01-12] Delete `engines/currency/` and `engines/deception/` — nothing calls them

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** Mechanical import scan across all of `src/npc_engine`: `currency` and `deception` are the only two of 39 `engines/` subpackages with **zero** external importers. `engines/currency/` is 12 lines — an `__init__.py` whose docstring still reads `Public surface: (list re-exports here)` and contains nothing but `from __future__ import annotations`. `engines/deception/` is 128 lines; `grep -rn "engines.deception" src/ tests/ demo_game/ scripts/ evals/` finds only its own `__init__.py:12` and `tests/unit/engines/test_deception_engine.py:35`. Nothing in `api/`, `scheduler/` or the demo constructs a `DeceptionEngine`.
- **Cost of inaction:** `docs/ENGINES.md` presents ~40 engines as the product's surface; two of them are not connected to anything, which inflates the "40 engines" figure that a scope conversation would start from. Small, but it is the cheapest subtraction available.
- **Fix sketch:** Delete both packages and `test_deception_engine.py`; if deception is roadmap work, move it to a branch and remove the placeholder from the catalog.
- **Effort:** S
- **Removes:** ~140 lines / 5 files
- **Blast radius:** `docs/ENGINES.md` count; deletion requires human approval per CLAUDE.md's "deleting a file you did not create" rule.

### [CR-L01-13] Give the six engine contracts either full coverage or an honest scope note

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Gap
- **Evidence:** `engines/contracts/` holds 6 YAMLs (`chapter`, `currency`, `dialogue`, `memory_consolidation`, `quest`, `quest_generation`) for 39 engine subpackages. `src/npc_engine/scripts/check_contracts.py:36-52` validates the contracts that exist and checks their declared test files resolve; it has no notion of "every engine must have a contract", so the 33 without one are not a gate failure. One of the six (`currency_engine.yaml`) describes a package that is an empty namespace (CR-L01-12). `docs/ENGINES.md:60` tells the reader "Engines that call an LLM declare `uses_llm: true` in their engine contract", which is true of 4 files and false as a general statement.
- **Cost of inaction:** A reader treats the contract system as the engine registry it looks like. It covers 15% of engines and one of its entries is empty.
- **Fix sketch:** Either add a gate requiring one contract per `engines/*/` package with a public `run_tick`/handler, or amend `docs/ENGINES.md` and the `contracts/__init__.py` docstring to say the system covers a named subset and why.
- **Effort:** S (doc) / L (full coverage)
- **Blast radius:** `make check` if the gate is added.

---

## Method notes

- Live reads used: `GET /v1/admin/system/engines`, `GET /v1/clock/state`,
  `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=…`. No writes, no clock advance, no seeding.
- The 66-site silent-`except` census was produced by an AST-free indentation scan over
  `engines/ services/ retrieval/ scheduler/ graph/` flagging every `except` whose block contains
  no `raise`; the script lives in the session scratchpad and is not checked in.
- Neo4j is not published to the host, so all graph facts came through the API.

---

## L2 — Architecture

# CR-L02 — Architecture (branch `eval-ab-context-arms`, HEAD `d46ae42`)

## Required measurements

### 1. Layer violations — seen vs. unseen by the import gate

```
$ make check-layers
.venv/Scripts/python.exe scripts/check_layers.py
check-layers: OK — no layer violations found.

$ make check-rules
.venv/Scripts/python.exe scripts/check_rules.py
check-rules: OK - no new violations (133 grandfathered).
```

| # | Category | Gate that should catch it | Count found | Confidence |
|---|---|---|---|---|
| a | Exception types crossing layers | none (import-graph only) | `neo4j.exceptions.Neo4jError` documented to cross graph→engines in 6 files / 11 mentions (`graph/character/player_model_writer.py:95,136`, `graph/intrigue/scheme_reader.py:166,198,232,279`, `graph/intrigue/scheme_writer.py:85,176`, `graph/relations/relation_phase_reader.py:66`, `graph/relations/relation_phase_writer.py:43`, `engines/relationship/phase_transition_applier.py:60`); traced end-to-end to a bare `except Exception` → HTTP 500 (see CR-L02-01) | Confirmed |
| b | Raw `dict` crossing a module boundary where Pydantic v2 is required | none (no such gate exists) | 145 public functions in `engines/`(67)+`graph/`(72)+`retrieval/`(6) return `-> dict[str, Any]`; includes `BaseEngine.run_tick` (`engines/base_engine.py:24`, 29 concrete implementations) and `LLMClientProtocol.generate_structured` (`engines/llm/protocols.py:73`) | Confirmed (AST-walked, script below) |
| c | Cypher / `session.run` outside `graph/` | `check-rules` R005 | 0 live instances found by manual grep of `api/`, `auth/`, `data/`, `cache/`, `mutation/` (dirs R005 does **not** scan — see CR-L02-04); 0 in the 5 dirs R005 does scan (baseline has 0 R005 entries) | Confirmed 0 today; gate coverage gap is Suspected risk |
| d | Wrong-layer runtime reach into Neo4j/LLM (not import-time) | none | Not found: `transaction_coordinator.py` is the only `begin_transaction()`/`.commit()` caller (see item 4); no engine imports a concrete LLM adapter outside `engines/llm/` (see item 2) | Confirmed |

AST script used for (b):
```python
# walks engines/graph/retrieval/services, ast.parse, counts public (non "_"-prefixed)
# FunctionDef/AsyncFunctionDef whose `returns` unparses to "dict[...]" or "dict"
```
Result: `{'engines': 67, 'graph': 72, 'retrieval': 6}`, `run_tick -> dict` count: 29.

### 2. DIP — engines importing concrete classes instead of protocols

| Scope | N violating | M total | Result |
|---|---|---|---|
| LLM backend only (CLAUDE.md's literal example: "engines import `LLMClientProtocol`, never `MistralAdapter`") | 0 | 7 engine files reference `LLMClientProtocol` | **Holds.** `grep -rln "OllamaAdapter\|OpenAICompatibleAdapter\|MockLLMAdapter" src/npc_engine/engines --include=*.py \| grep -v /engines/llm/` → empty. |
| Engine files importing anything from `graph.*` (broader interpretation; note the layer model explicitly permits `engines → graph`, so this is not itself a rule violation) | 13 | 219 engine .py files | Worst offenders: `engines/dialogue/session_store.py:170,201` (local imports of `write_session_turns`/`read_all_session_turns`, called directly, no port); `engines/dialogue/system_state_context.py:61-62` (same pattern for `get_items_for_character`/`get_active_quest_for_player`); `engines/ports/event_port.py:20` imports `_EventNode`, a `Protocol` **defined inside `graph/event/event_writer.py:20`** rather than owned by the port that consumes it — protocol ownership is on the wrong side of the boundary. The other 10 hits import DTOs (`RelationPhaseRow`, `SchemeRecord`, `IdempotencyRecord`, `ActiveSchemeProgress`) or are re-export shims (`engines/routine/routine_queries.py`, `engines/story_pacing/pacing_queries.py`, both self-documented as scheduled-for-removal back-compat forwarders). |

**"Sole composition root" claim:** false as stated. The composition root is 10 files, not 1: `api/dependencies.py`, `api/dependencies_infra.py`, `api/dependencies_stores.py`, `api/dependencies_advanced/{politics,progression,social}.py`, `api/dependencies_engines/{core,quest,tick_slots}.py`. All 43 importers of `api/dependencies.py` itself are confined to `api/` + `main.py` (`grep -rl "from npc_engine.api.dependencies import" src/npc_engine --include=*.py`), so the *direction* of composition is sound — but two stateful singletons are built entirely outside this file family (see CR-L02-03).

### 3. ROADMAP — do the 65 unchecked items require editing closed modules?

Full read of all 65 `- [ ]` lines in `project-harness/ROADMAP.md` (not sampled — 65 was small enough to do exhaustively), classified by the files each item names or the code it must touch:

| Class | Count | % | Meaning |
|---|---|---|---|
| (a) Pure addition — new file(s) only | 33 | 51% | Almost entirely `evals/`, `docs/`, `prompts/eval/`, `scripts/`, `Makefile`/`README` edits — the EVAL-P8..P31 eval-harness program (46 of the 65 items belong to this program alone) |
| (b) Requires editing an existing production file | 15 | 23% | See list below |
| (c) Requires a schema/graph-wide change | 2 | 3% | `EVAL-P29.1` (edits `src/npc_engine/config/llm_config.yaml` + `src/npc_engine/schema/context_config_models.py`); `OD-Ship-graph` (Kùzu migration touching all of `graph/`, 200 files) |
| (d) Unclear / human-only / no code (live runs, struck items, blocked-behind-gate) | 15 | 23% | e.g. `EVAL-P8.3`, `EVAL-P20.4`, `EVAL-P22.4`, `EVAL-03`/`EVAL-05` (struck) |

**(b) items, named:** `EVAL-P29.2` (edits `engines/dialogue/prompt_builder.py` **and** `engines/dialogue/dialogue_handler.py`, itself labelled "Pays down the existing constructor-injection violation" — confirmed: `prompt_builder.py:29-33` loads YAML at module import time, already logged as `ISSUE-223`); `EVAL-P30.2` (edits `engines/dialogue/dialogue_models.py`, flagged in the roadmap itself as "public interface change with callers outside its module — ask-gate per CLAUDE.md"); `PR-9` (refactors 39 files in `graph/repositories/`); `EVAL-01` (edits `dialogue_handler.py` + `context_builder.py`); `PERF-01/02/03/05/06/07` (all edit existing engine/retrieval/scheduler/config files — `PERF-02` names `context_builder.py:516-534` directly, confirmed to exist at `retrieval/context/context_builder.py`, though the current code at that range is `_build_event_trust_map`/`_drop_withheld_items`, not the graph-read loop the item describes — line-anchor drift over time); `PERF-00` (`setup/stack_launcher.py`); `H-D1`, `H-D2`, `S17.9`, `S21.6` (all edit existing engine/demo files).

**Strategic read:** of the 17 items that touch actual `src/npc_engine` production code (15 (b) + 2 (c)), **zero are pure additions — all 17 require editing an existing file.** The OCP claim ("new backends/distortions/emotion models are added by creating a new file") is not being tested by most of the open backlog, because most of the open backlog (71%, 46/65) is now the eval-harness meta-program, not engine features. Where the backlog *does* touch the engine, it is edit-heavy, not add-only.

### 4. Session/transaction ownership

```
$ grep -rn "begin_transaction(" src/npc_engine --include=*.py
graph/infra/transaction_coordinator.py:43:    tx = await session.begin_transaction()

$ grep -rn "\.commit()" src/npc_engine --include=*.py
graph/infra/transaction_coordinator.py:46:        await tx.commit()

$ grep -rn "AsyncTransaction" src/npc_engine --include=*.py | grep -v graph/infra/transaction_coordinator.py
# 90+ hits, every one is a `tx: AsyncTransaction` parameter on a graph/*_writer.py or
# graph/*_service.py `_work(tx)` closure — none outside graph/, none held as an attribute.
```
**Verdict: holds. Confirmed.** `transaction_coordinator.py` is the only file calling `begin_transaction()`/`.commit()`; no engine holds an `AsyncTransaction`.

### 5. OCP seams — LLM backend pluggability

- Protocol: `engines/llm/protocols.py` (`LLMClientProtocol`).
- Adapters shipped: **3** — `mock_adapter.py` (`MockLLMAdapter`), `ollama_adapter.py` (`OllamaAdapter`), `openai_adapter.py` (`OpenAICompatibleAdapter`, 288 lines, full `generate`/`generate_structured`/`stream`).
- Registry: `engines/llm/factory.py` — a real `dict[str, Callable]` (`_REGISTRY`), `register_backend()`, `registered_backends()` used by config validation instead of a hardcoded `Literal` (confirmed: no `Literal` of backend names found anywhere). `engines/llm/__init__.py` imports `factory` for the registration side effect.
- **To add backend #4 today:** write one new adapter file implementing `LLMClientProtocol`, then add a `_build_x` function + one `register_backend("x", _build_x)` line **inside `factory.py`**. The registry is real and config validation is genuinely open, but the 3 existing backends do not follow factory.py's own documented pattern ("writing an adapter... and calling `register_backend()` at import time" implies the adapter's own module registers itself); all three registrations are centralized in `factory.py`, so one existing file is still touched, not zero.
- **CLAUDE.md accuracy check — FAILS.** `project-harness/CLAUDE.md:22` states "no OpenAI adapter ships today." `git log --diff-filter=A -- src/npc_engine/engines/llm/openai_adapter.py` → added 2026-06-18, fully wired into `factory.py` from day one. `git blame -L 22,22 project-harness/CLAUDE.md` → that exact line was last rewritten **2026-07-31**, six weeks after the adapter shipped. The claim was false at the time it was last edited, not merely stale from disuse.

### 6. Coupling — 15 largest modules, fan-in/fan-out (AST-resolved `npc_engine.*` imports)

| File | LOC | Fan-in | Fan-out | Commits (churn) |
|---|---:|---:|---:|---:|
| `retrieval/context/context_builder.py` | 799 | 1 | 30 | 26 |
| `scheduler/tick_scheduler.py` | 630 | 4 | 10 | 31 |
| `retrieval/context/context_budget_enforcer.py` | 577 | 0 | 2 | — |
| `config.py` | 504 | **74** | 5 | **46** |
| `engines/dialogue/dialogue_handler.py` | 470 | 2 | **34** | 39 |
| `engines/gossip/gossip_handler.py` | 405 | 2 | 12 | — |
| `utils/errors.py` | 389 | 66 | 0 | 14 |
| `engines/quest/quest_lifecycle_engine.py` | 383 | 4 | 10 | — |
| `engines/quest_generation/quest_generation_engine.py` | 368 | 5 | 7 | — |
| `graph/intent/intent_queries.py` | 339 | 3 | 0 | — |
| `data/api_seeder.py` | 326 | 0 | 3 | — |
| `engines/chapter/chapter_engine.py` | 324 | 2 | 6 | — |
| `engines/dialogue/prompt_builder.py` | 305 | 1 | 5 | — |
| `api/dependencies.py` | 296 | 43 | 22 | 26 |
| `config_validators.py` | 295 | 1 | 0 | — |

**Chokepoints (high fan-in AND high-churn):** `config.py` (fan-in 74, 46 commits — the widest blast radius in the repo by 12x over the next candidate, and already flagged elsewhere as the top fix-magnet file, 68% over the 300-line limit with only a stale `DEC-077` waiver for 309 lines, not today's 504) and `engines/dialogue/dialogue_handler.py` (fan-out 34 — imports more of the tree than any other file, 39 commits, itself R001/R006-baselined). `utils/errors.py` (fan-in 66, fan-out 0) is high fan-in but a correct leaf — no churn concern, it's doing its job as the shared exception hierarchy.

---

## Findings

### [CR-L02-01] `GraphUnavailableError` is dead code — the documented Neo4j-outage fallback contract does not exist

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `utils/errors.py:54` defines `GraphUnavailableError` but `grep -rn "raise GraphUnavailableError\|GraphUnavailableError(" src/npc_engine` returns only the class definition itself — zero raise sites anywhere in the tree. Four files (`engines/military/military_battle_service.py`, `engines/military/military_resource_service.py`, `engines/ports/dialogue_graph_port.py`, `graph/political/pledge_violation_service.py`) document "Fallback: Neo4j unavailable → raises GraphUnavailableError" in their docstrings, but none actually raise it. Separately, `neo4j.exceptions.Neo4jError` is documented to propagate from `graph/relations/relation_phase_writer.py` through `engines/relationship/phase_transition_applier.py:60` into `engines/dialogue/dialogue_handler.py:283`; `api/errors/exception_handlers.py:109-120` registers handlers only for `RequestValidationError`, `HTTPException`, `ContentRatingViolationError`, and a catch-all `Exception` → `_internal_error_handler` (line 70) which returns a flat HTTP 500 `{"code": "internal_error"}` for anything untyped, `GraphUnavailableError` included were it ever raised.
- **Cost of inaction:** A live Neo4j outage during a dialogue turn will surface everywhere as a generic 500, indistinguishable from a bug in the requesting code, with no signal to a client or load balancer that the failure is retryable/transient (503 semantics). This is invisible in normal operation and will only be discovered during the first real graph outage.
- **Fix sketch:** Either wire `GraphUnavailableError` at the two or three actual Neo4j call boundaries (session acquisition, `transaction_coordinator.run_in_tx`) and register a `GraphUnavailableError → 503` handler in `exception_handlers.py`, or delete the dead class and the four false docstring claims and rely on the generic 500 deliberately — but the current state (documented contract, unimplemented, unregistered) is worse than either.
- **Effort:** M
- **Blast radius:** `api/errors/exception_handlers.py`, `graph/infra/transaction_coordinator.py` (or wherever the raise is added), the four docstrings that currently lie.

### [CR-L02-02] CLAUDE.md's stack table is factually wrong about a shipped capability, as of its most recent edit

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `project-harness/CLAUDE.md:22` — "no OpenAI adapter ships today." `src/npc_engine/engines/llm/openai_adapter.py` (288 lines) was added `2026-06-18` (`git log --diff-filter=A --format=%ad -- src/npc_engine/engines/llm/openai_adapter.py`) and is wired into `engines/llm/factory.py:24,92-102,107` from that commit. `git blame -L 22,22 project-harness/CLAUDE.md` shows that exact line was last rewritten `2026-07-31 17:48:59 +0200` — six weeks *after* the adapter shipped.
- **Cost of inaction:** Every session (including this review's own orchestrator prompt) that trusts the stack table as ground truth wastes a round-trip verifying something the repo already answers; a reviewer could wrongly credit or discredit the OCP claim based on the stale line.
- **Fix sketch:** Update the line to name the three shipped backends (mock/ollama/openai) and drop the "no OpenAI adapter" claim.
- **Effort:** S
- **Blast radius:** Documentation only.

### [CR-L02-03] Two stateful singletons are built outside every composition-root file, one of them a bare global dict guarded by a module-level lock

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `api/routes/dialogue/dialogue_ws.py:68-69` — `_active_ws_connections: dict[str, int] = {}` and `_ws_connections_lock = asyncio.Lock()` at module scope in a route file, read/written at lines 79 and 89 inside route handlers; never passed through any `dependencies*.py` file. `engines/interaction/dispatch.py:34` — `_trade_handler: SyncTradeHandlerProtocol = MinimalSyncTradeHandler()` at module scope, mutated via `global _trade_handler` in `set_trade_handler()` (lines 37-44), the module's own docstring calling this "Dependencies injected: ... via set_trade_handler" — a hand-rolled service-locator, not constructor injection. `grep -rln "^\s*global " src/npc_engine/engines src/npc_engine/api` finds exactly these 2 files (plus `engines/gossip/strategies/prefix_loader.py`, not stateful).
- **Cost of inaction:** `_active_ws_connections` is genuine cross-request mutable state with no owner and no test-time seam — a concurrency bug here (e.g. a missed lock acquisition on a future edit) won't be caught by anything that exercises `api/dependencies.py`-wired code paths, because this state was never wired through it. `dispatch.py`'s global swap makes trade-handler behavior order-dependent across tests unless every test remembers to reset it.
- **Fix sketch:** Move `_active_ws_connections`/`_ws_connections_lock` into a small class instantiated once in `api/dependencies.py` and injected into the two handlers that use it; replace `dispatch.py`'s `global`/setter pair with constructor-injected `SyncTradeHandlerProtocol`.
- **Effort:** M
- **Blast radius:** `api/routes/dialogue/dialogue_ws.py`, `engines/interaction/dispatch.py`, `api/dependencies.py`, any test currently relying on `set_trade_handler()`.

### [CR-L02-04] `check-rules` R005 (Cypher-leak) never scans `api/`, `auth/`, `data/`, `cache/`, or `mutation/`

- **Severity:** MEDIUM
- **Confidence:** Suspected (a gate coverage gap, not a live violation — verified zero live instances exist today)
- **Kind:** Gap
- **Evidence:** `scripts/check_rules.py:53` — `_CYPHER_SCAN_DIRS = ("engines", "world", "retrieval", "services", "scheduler")`. `api`, `auth`, `data`, `cache`, `mutation` are absent. Confirmed by manual scan: `grep -rniE "\b(MATCH|MERGE|CREATE|DELETE|UNWIND)\b.*\(" src/npc_engine/api src/npc_engine/auth src/npc_engine/data src/npc_engine/cache src/npc_engine/mutation` returns only case-insensitive false positives (`return cls(...)` matching `RETURN`), zero real Cypher. The regex itself is also case-sensitive-uppercase-only for `MATCH|MERGE|CREATE` and misses `DELETE`/`SET`/`UNWIND`/`WHERE`-only fragments and `.run(` on any session variable name other than literally `session`/`tx`.
- **Cost of inaction:** `api` is rank 6, the layer furthest from the DB and the one CLAUDE.md's own layer table says must never touch Neo4j directly — yet it is the one directory group R005 does not defend at all. A future handler that calls `session.run()` directly (e.g. an "quick admin debug query" added under time pressure) would pass CI silently.
- **Fix sketch:** Add `api`, `auth`, `data`, `cache`, `mutation` to `_CYPHER_SCAN_DIRS`; broaden the regex to catch lowercase and the missing keywords/session-var patterns.
- **Effort:** S
- **Blast radius:** `scripts/check_rules.py`, `scripts/rules_baseline.txt` (baseline run needed once to confirm no new hits).

### [CR-L02-05] "No raw `dict` crossing a module boundary" is violated at the two most central interfaces in the engine tree

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/base_engine.py:24` — `async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...`, the structural `Protocol` every tick-driven engine implements; confirmed 29 concrete `run_tick` methods return `dict[str, Any]` (AST count). `engines/llm/protocols.py:73` — `LLMClientProtocol.generate_structured(...) -> dict[str, Any]`, the exact seam CLAUDE.md names for "Structured output validated (strict): all `generate_structured()` output passes through a Pydantic model ... before any field is accessed" — the protocol's own contract is untyped; validation, if it happens, happens after the boundary, not at it. AST walk of `engines/graph/retrieval` (non-test, public functions) totals 145 functions returning `dict[str, Any]`/`dict` (`engines`: 67, `graph`: 72, `retrieval`: 6).
- **Cost of inaction:** The scheduler's dispatch contract and the LLM boundary — the two places a schema regression would be most expensive to debug — have no type contract to catch a shape drift; a bug here surfaces as a `KeyError` deep in a handler rather than a validation error at the boundary.
- **Fix sketch:** This is a large, deliberate trade-off (the docstring at `base_engine.py:16-19` explains engines have differing kwargs), not a quick fix — realistically requires a per-engine result model plus a narrower base protocol, sized as its own roadmap item rather than a spot fix.
- **Effort:** XL
- **Blast radius:** All ~29 tick engines, `scheduler/tick_scheduler.py`, every `LLMClientProtocol` implementation and caller.

### [CR-L02-06] `config.py`'s fan-in (74) is the widest blast radius in the repo, 12x the next non-leaf module, on top of its already-flagged churn/size

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** AST-resolved import graph over the 15 largest files (table above): `config.py` fan-in = 74 vs. the next-highest non-leaf module `api/dependencies.py` at 43 and `engines/quest_generation/quest_generation_engine.py` at 5. Combined with the already-established 46-commit churn and 504-line size (68% over limit, `DEC-077`'s waiver covers only 309 lines) this is a single file that a very large fraction of the tree depends on, changes often, and carries no current size waiver.
- **Cost of inaction:** Any change to `Settings` risks a ripple through 74 files with no compile-time enforcement beyond what mypy catches on field access; the combination of high change frequency and high fan-in is exactly the profile that produces silent cross-module breakage.
- **Fix sketch:** Split `Settings` by concern (LLM/graph/API/eval config) behind narrower accessor objects so most of the 74 importers depend on a slice, not the whole class; already implicitly proposed by `DEC-011`'s earlier `config_validators.py` extraction — extend that precedent.
- **Effort:** L
- **Blast radius:** All 74 current importers of `config.py` — this is why it hasn't been done yet.

### [CR-L02-07] Of the roadmap items that actually touch engine code, 100% require editing an existing file — OCP is not being exercised by the real remaining backlog

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** Full classification of all 65 unchecked `ROADMAP.md` items (table in Required Measurements §3): 46/65 (71%) belong to the eval-harness meta-program (`EVAL-P8..P31`) and are almost entirely new-file additions under `evals/`, `docs/`, `prompts/eval/`; of the 17 items that touch actual `src/npc_engine` production code, all 17 are (b) edit-existing or (c) schema/graph-wide — zero are pure additions. Named examples: `EVAL-P29.2` edits `engines/dialogue/prompt_builder.py` + `engines/dialogue/dialogue_handler.py` to pay down a constructor-injection violation already logged as `ISSUE-223`; `EVAL-P30.2` is explicitly flagged in the roadmap text itself as "public interface change with callers outside its module — ask-gate per CLAUDE.md"; `PR-9` and `OD-Ship-graph` each require touching dozens-to-hundreds of existing `graph/` files.
- **Cost of inaction:** The engine's OCP story ("new backends/distortions are added by creating a new file") is true for LLM backends (confirmed in item 5) but is not what the near-term roadmap will actually exercise — the visible backlog is mostly a separate eval-tooling program, and the few items that do touch the engine are all edits, several explicitly gated on "ask before touching a public interface." A planning read of the roadmap that assumes OCP will keep future engine work additive would be wrong.
- **Fix sketch:** Not a code fix — a planning input: budget engine-facing roadmap work (the 17 items) as edit-and-review work requiring the ask-gate process CLAUDE.md already specifies, not as isolated new-file additions; the eval-harness program (46 items) can continue to be scheduled more lightly since it is genuinely additive.
- **Effort:** N/A (planning finding)
- **Blast radius:** Roadmap sequencing/estimation only; no code touched.

### [CR-L02-08] The LLM factory's own extension-point docstring describes a pattern the 3 shipped adapters don't follow

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/llm/factory.py:10-14` — "add a new local/remote LLM backend by writing an adapter that satisfies `LLMClientProtocol` and calling `register_backend("name", ctor)` at import time, then importing it from `engines/llm/__init__.py`." But `mock_adapter.py`, `ollama_adapter.py`, and `openai_adapter.py` do not call `register_backend` themselves; all three `register_backend(...)` calls live centrally at `factory.py:105-107`, and the three `_build_*` constructor functions also live in `factory.py` (lines 78-102), not beside their adapters.
- **Cost of inaction:** A contributor following the documented extension point literally (adapter file calls `register_backend` itself) will add a backend in a style inconsistent with the 3 that exist, or will discover only by reading `factory.py` that they actually need to edit it too — a minor but real doc/code mismatch in the one file whose docstring is explicitly about OCP.
- **Fix sketch:** Either move each `_build_*` + `register_backend()` call into its own adapter module (matching the docstring) or rewrite the docstring to describe the actual centralized-registration pattern.
- **Effort:** S
- **Blast radius:** `engines/llm/factory.py`, `mock_adapter.py`, `ollama_adapter.py`, `openai_adapter.py` (only if code moves; doc-only fix touches nothing else).

---

## L4 — Maintainability

> **Note on a negative result — record it, it is load-bearing.** The review brief
> hypothesised that the 300-line rule had scattered cohesive logic into shrapnel
> (`graph/` = 22,598 LOC across 200 files, `engines/` = 20,014 across 219). L4
> measured the distributions and **disproved it**: `graph/` median 103.5 lines,
> p90 218, exactly 1 file over 300; `engines/` median 68 (86.5 excluding
> `__init__.py`), p90 209–219, 6 files over 300 — all of which other lenses had
> already flagged for independent reasons. That is healthy domain decomposition,
> not rule-induced fragmentation. The 300-line rule is not the villain here, and
> §C does not treat it as one. L14 was asked the same question from the
> agent-authored-smell angle; where the two disagree, L4's distributions win,
> because they are a census and not a sample.

# CR-L04 — Maintainability

Lens L4. Branch `eval-ab-context-arms` @ `d46ae42`. Windows 11, Git Bash + PowerShell.
Stack live throughout (`npcsystem-app-1`, `npcsystem-neo4j-1`), untouched. Clone/boot
mechanics (git longpaths, `.env`) are already Confirmed by CR-L16 and are cited, not
re-derived. Doc-vs-reality drift in README/CONTRIBUTING is already Confirmed by CR-L13/L16
and is cited only where it feeds a maintainability number this lens owns.

## Required measurements

### 1. Time-to-first-useful-change (walked, not simulated)

Target change: fix `evals/retrieval_runner.py:269-276` (`main`'s docstring lies about its
own CLI — asserts "no options"/"Must be empty" when `--gen-dir` and `--retrieval-profile`
exist) — this is a real, still-open, correctly-scoped P3 (`ISSUES.md:64-77`, `ISSUE-202`),
verified live at `evals/retrieval_runner.py:271-291`.

| # | Step | Documented where | Worked as written? | Time |
|---|---|---|---|---|
| 1 | `git clone` | — (undocumented) | **NO** — Windows `MAX_PATH`; needs `core.longpaths` (CR-L16, Confirmed) | ~1 min once known |
| 2 | `cp .env.example .env` | `CONTRIBUTING.md` only; `README.md` Quick Start omits it entirely | **NO** as README presents it (CR-L16, CR-L16-02, Confirmed) | ~1 min |
| 3 | `docker-compose up -d --build` | `README.md:45` | YES once (1)+(2) fixed — measured by CR-L16: image build + neo4j healthy | ~90 s + ~15 s (CR-L16, cited) |
| 4 | Read root `CLAUDE.md` (1 line) + `project-harness/CLAUDE.md` | auto-loaded every session (`@`-import) | YES, forced | 476 lines / 2,944 words ≈ **20–23 min** at 130 wpm technical reading |
| 5 | Read `project-harness/ISSUES.md` — CLAUDE.md:268-269: *"Every session reads it."* | mandatory, no partial-read clause | Technically possible, practically extreme — see CR-L04-03 | 1,799 lines / 19,080 words / 141,383 chars ≈ **145–150 min** linear read |
| 6 | Read `CONTRIBUTING.md` "Before you commit" | root | Partially broken: `project/CLAUDE.md` (×3), `project/ISSUES.md`, `project/DECISIONS.md` all 404 (`project/` does not exist, confirmed `ls project/` → `No such file or directory`); `python -m npc_engine.scripts.seed` → `ModuleNotFoundError` (confirmed live, real seed path is `python -m demo_game.seeds.seed` per `Makefile:595`) | ~5 min read + ~2 min recovering from the broken command |
| 7 | Find a task | `ISSUES.md` (already open in step 5) | YES — `ISSUE-202` | ~1 min (amortized into step 5) |
| 8 | Edit the docstring | `evals/retrieval_runner.py:271-291` | YES, one-paragraph edit, no behaviour change, matches `ISSUES.md`'s own "To fix" | ~5 min |
| 9 | `make demo-seed` (real seed path) | `Makefile:594-595` | **YES — measured live**: `time make demo-seed` → `real 0m9.161s` (idempotent re-run, `created=101 skipped=71`) | 9.2 s |
| 10 | `make check` (14 targets, pre-merge checklist) | `project-harness/CLAUDE.md` "Pre-merge checklist" | YES (measured elsewhere, cited, not re-run: ~595 s / 94% two coverage runs) | ~10 min |
| 11 | Mark `ISSUE-202` `[FIXED]`, move to `archive/ISSUES_RESOLVED.md` | CLAUDE.md "When you fix an issue" | YES, mechanical | ~5 min |
| 12 | Commit (conventional format) + push | `git-workflow.md` | YES | ~3 min |

**Total, realistic practice** (skim `ISSUES.md` for the one relevant entry via search
rather than reading linearly, as every actual session in this repo's own git history
appears to do — see CR-L04-03): environment fixes (~5 min, one-time) + CLAUDE.md read
(~22 min) + ISSUES.md skim (~3 min) + CONTRIBUTING detour (~7 min) + edit/seed/check/commit
(~28 min) ≈ **1.1 hours**.

**Total, literal CLAUDE.md compliance** (steps 4 and 5 read cover-to-cover as the text
requires, nothing skipped): ~5 min env fixes + 22 min + 148 min + 7 min + 28 min ≈
**3.4 hours**, of which **72%** is reading two markdown files, not writing code.

Either number is dominated by process reading, not the change itself (step 8, the only step
that touches the actual product, is 5 of ~180-330 minutes).

### 2. Files-per-feature — "add a `mood`-like field the dialogue prompt can read"

`character.yaml` already ships `current_mood`/`mood_intensity` (added by
`39fbbb8`/`12c9e5a`, EXP-14), so this is not hypothetical — it is the as-shipped trace,
enumerated by `grep -rl current_mood src/ tests/ docs/`:

| # | File | Role |
|---|---|---|
| 1 | `src/npc_engine/type_registry/base_nodes/character.yaml` | field declaration |
| 2 | `src/npc_engine/graph/emotion/mood_queries.py` | Cypher read/write |
| 3 | `src/npc_engine/graph/infra/embedding_load_queries.py` | embedding-scan projection |
| 4 | `src/npc_engine/graph/infra/embedding_sync_queries.py` | embedding-sync projection |
| 5 | `src/npc_engine/retrieval/context/context_builder.py` | Tier assembly |
| 6 | `src/npc_engine/retrieval/context/context_compression.py` | prompt-budget trimming |
| 7 | `src/npc_engine/retrieval/dialogue_context/dialogue_context_cache.py` | cache key/invalidation |
| 8 | `src/npc_engine/engines/ports/dialogue_context_port.py` | protocol surface |
| 9 | `src/npc_engine/engines/dialogue/dialogue_handler.py` | orchestration |
| 10 | `src/npc_engine/prompts/dialogue/system_v1.yaml` | prompt text itself |
| 11 | `src/npc_engine/data/seed_data.py` | demo seed values |
| 12 | `tests/unit/conformance/test_architecture_conformance.py` | layer conformance |
| 13 | `tests/unit/engines/test_dialogue_handler_fallback_v14.py` | engine unit test |
| 14 | `tests/unit/engines/test_player_relation_context.py` | context unit test |
| 15 | `tests/unit/retrieval/test_context_builder.py` | retrieval unit test |
| 16 | `tests/unit/retrieval/test_context_metrics_observability_v14.py` | observability test |
| 17 | `tests/unit/retrieval/test_context_prompt_hygiene.py` | prompt hygiene test |
| 18 | `tests/unit/retrieval/test_context_serializer_generated.py` | serializer test |
| 19 | `tests/unit/retrieval/test_dialogue_context_cache.py` | cache test |
| 20 | `docs/DATA_MODELS.md` + `docs/ENGINE_EVAL_COVERAGE.md` (2 files, counted as 1 line) | docs |

**20 files** (1 schema + 1 prompt YAML + 9 src + 8 tests + 2 docs). Cross-check with a
second, smaller feature shape — the `GOAL_TARGETS` edge (`d26f1a3` + later wiring) — lands
at **8 files** once fully wired into an engine (`type_registry` yaml, `graph/needs_goals/
goal_targets_writer.py`, `graph/repositories/planning_repository.py`,
`engines/ports/planning_port.py`, `engines/planning/goal_former.py`, `__init__.py`, 2 test
files) — and **0 doc files** (`grep -n GOAL_TARGETS docs/*.md` → no hits; see CR-L04-05).
A field or edge that stops at type_registry + one graph query file, with no dialogue/prompt
surface, is the ~4-8-file floor; one that a player-facing prompt must read is ~20.

### 3. Migration down paths

`scripts/migrations/` actually contains **7** scripts (the review brief's "8" does not match
any count found in the repo — `ls`/`find` both return 7; the number appears nowhere except
`project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md:179` itself).

| Migration | Idempotent? | Down path? | Applied-state tracked? |
|---|---|---|---|
| `add_faction_support.py` | Yes (`CREATE CONSTRAINT … IF NOT EXISTS`) | No | No — **and now dead**, see CR-L04-02 |
| `add_investigation_schema.py` | Yes (same pattern) | No | No |
| `add_phase7_schema.py` | Yes (MERGE/SET) | No | No |
| `add_political_schema.py` | Yes (constraint + count-then-backfill) | No | No |
| `add_social_schema.py` | Yes | No | No |
| `add_strategy_schema.py` | Yes | No | No |
| `migrate_faction_strings.py` | Yes (MERGE), fail-fast on unresolved faction ids | No — and the source field (`Character.faction`) is never removed, so the migration never actually completes (CR-L04-05) | No |

None of the 7 records anywhere that it ran (no migrations table, no `SHOW CONSTRAINTS`
diffing against a manifest, no entry in any doc listing "applied to prod on \<date\>"). The
only cross-check available is manual: `SHOW CONSTRAINTS`/`MATCH … RETURN count()`, run by
hand, against a script's own preconditions.

**If a schema change goes wrong in a customer's deployment, the recovery procedure is: there
is none in writing.** `rollback` appears in the repo only for the in-request Cypher
transaction coordinator (`DECISIONS.md:1416,1454`, request-scoped tx abort-on-exception) —
zero hits for schema-level rollback, backup/restore, or disaster recovery in any `docs/*.md`
or `project-harness/*.md` (checked, not just grepped for "migration"). An operator's only
option today is a full Neo4j volume restore from an external backup this repo does not
document taking.

### 4. Schema evolution

`type_registry/` = 91 YAML files (34 `base_nodes/` + 57 `base_edges/`), not the 124 in the
review brief — verified by `find`. Plus `game_schema.yaml` (`schema_version: "1.0"`, never
incremented — `grep -c schema_version` → 1 literal string, unused as a real version gate).

`node_validator.validate_node_write` (`src/npc_engine/type_registry/node_validator.py:17-33`)
validates **on write only** — it looks up `registry.node_models[node_type]` and calls
`model_cls.model_validate(props)`. There is no read-time re-validation and no migration
trigger. Consequence, traced directly from the code: if a field goes from `required: false`
to `required: true` in an existing `base_nodes/*.yaml`, every **pre-existing** node of that
type that lacks the field is untouched — it simply is not re-validated until something tries
to *write* it again, at which point `pydantic.ValidationError` surfaces at whatever call site
made the write, not at deploy time and not as a migration failure. No gate in
`scripts/check_*.py` (10 checkers enumerated) detects "required field added without an
accompanying migration or a `DECISIONS.md`-documented backfill plan." Of the 91
`base_nodes`/`base_edges` YAML files, only 7 additions across the project's history ever got
a companion migration script (the 7 in `scripts/migrations/`) — the other ~84 were shipped
as `required: false` additions by convention (DECISIONS.md:600 states this explicitly:
*"Making them optional preserves backward compatibility"*), not because tooling enforces it.
Schema evolution here is a **convention**, not a **mechanism**.

### 5. Cohesion/coupling — `graph/` vs `engines/`

| Package | Files | Median lines | Mean | p90 | Max | Files <50 lines | Files >300 lines | Internal (`from npc_engine.X`) import sites |
|---|---|---|---|---|---|---|---|---|
| `graph/` (200 files, 26 subpackages) | 200 | 103.5 | 113.0 | 218 | 339 (`intent/intent_queries.py`, already flagged CR-L15-02) | 48 (24%) | 1 | 270 imports across 89 files (fan-out ≈1.35/file, ≈3.0/importing file) |
| `engines/` (219 files) | 219 | 68 (86.5 excl. `__init__.py`) | 91.4 (108.7 excl.) | 209 (219 excl.) | 470 (`dialogue/dialogue_handler.py`, already flagged CR-L07-03) | 87 (39.7%), 47/178 (26.4%) excl. `__init__.py` | 6 (all already flagged: CR-L07-03, CR-L06/CR-L08 ratchet) | 305 imports across 121 files |

41/219 `engines/` files and 26/200 `graph/` files are `__init__.py` (mandatory per-package
docstrings, CLAUDE.md's own rule) — excluding those, the two packages' size distributions are
close (median 86.5 vs 103.5 lines). **Judgment: 200 and 219 files is domain decomposition by
26 and ~40 subpackages respectively, not 300-line-rule shrapnel** — the under-50-line tail is
explained almost entirely by mandatory `__init__.py` boilerplate, and intra-package import
fan-out (≈1.3-1.4 imports per file) is modest, not a coupling smokescreen. The 7 files over
300 lines are pre-existing grandfathered violations already tracked by other lenses
(CR-L06/L07/L08/L15) — no new finding needed here.

### 6. Agent cold-start cost

| Source | Auto-loaded into every session? | Size |
|---|---|---|
| Root `CLAUDE.md` (`@`-import stub) | Yes | 27 chars |
| `project-harness/CLAUDE.md` | Yes (via the `@`-import) | 20,786 chars / 476 lines |
| User-level `~/.claude/rules/common/*.md` (9 files) + `rules/README.md` | Yes (shown in every session's system context) | 14,938 chars |
| `MEMORY.md` index | Yes | 844 chars |
| **Auto-loaded subtotal** | | **36,595 chars ≈ 9,149 tokens (÷4)** |
| `project-harness/ISSUES.md` (CLAUDE.md:268: *"Every session reads it"*) | Not auto-injected — but self-mandated as the session's own first action | 141,383 chars ≈ **35,346 tokens** |
| **If the mandate is honored literally** | | **≈ 44,495 tokens before any exploration or code is read** |

Against a 200K-token window: auto-loaded content alone is **4.6%**; honoring the ISSUES.md
mandate literally brings mandatory pre-work reading to **≈22.3%** of the budget. Against a
1M-token window the auto-loaded fraction drops to 0.9%, but ISSUES.md is still 35K real
tokens an agent must either spend or silently skip.

---

## Findings

### [CR-L04-01] No migration in `scripts/migrations/` has a down path or applied-state record

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** All 7 files in `scripts/migrations/` read in full. None contains `rollback`/`down`/`revert`/`undo` (`grep -rniE "down|rollback|revert|undo" scripts/migrations/*.py` → 0 hits). No migrations table, manifest, or "applied on \<date\>" record exists anywhere (`grep -rniE "migration.*(log|applied|version|history)"` across `scripts/` and `graph/` → 0 hits). Confirmed by reading every script (see measurement 3 table).
- **Cost of inaction:** This is middleware sold to studios who run it on their own Neo4j data. A bad schema change (wrong constraint, bad backfill value) has no undo — recovery is an out-of-band Neo4j volume restore that is itself undocumented anywhere in `docs/` or `project-harness/`. First customer-side schema incident becomes a support emergency with no runbook.
- **Fix sketch:** Add one `MIGRATIONS.md` (or a section in `docs/API.md`) recording, per script: date applied, environments applied to, and the manual undo Cypher (even "no safe undo, see backup policy" is better than silence). Down paths are optional for pure-additive constraint scripts but mandatory for the field-moving one (`migrate_faction_strings.py`).
- **Effort:** M
- **Blast radius:** Documentation-only; touches no running code.

### [CR-L04-02] `add_faction_support.py` has been fully superseded and dead since 2026-06-04, but two docs still tell operators to run it

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `scripts/migrations/add_faction_support.py:57` creates
  `CREATE CONSTRAINT faction_id_unique IF NOT EXISTS FOR (f:Faction) REQUIRE f.id IS UNIQUE`.
  The identical statement is now issued automatically on **every process startup** by
  `src/npc_engine/graph/infra/schema_bootstrap.py:23-29` (`_CORE_LABELS` includes
  `("Faction", "faction_id_unique")`) via `main.py:166`
  (`await ensure_core_constraints(session=session)`). `git log -S"faction_id_unique"` shows
  this was added in `6b91e4f` ("SEV-10 add core-node uniqueness constraints", 2026-06-04) —
  a month after the migration script (`6cfe763`, 2026-05-06) — with no `DECISIONS.md` entry
  addressing the overlap (`grep -n SEV-10 project-harness/DECISIONS.md` → 0 hits). Yet
  `docs/DATA_MODELS.md:653` and `docs/API.md:490-492` both still present the script as the
  way the constraint gets applied.
- **Cost of inaction:** Operators following the docs run a no-op and may believe they've done
  something the app already guarantees; the doc keeps a false impression of a manual schema
  step alive indefinitely (~3 months and counting as of this review).
- **Fix sketch:** Delete `add_faction_support.py` (or mark it a documented no-op pointing at
  `schema_bootstrap.py`); update the two doc references.
- **Effort:** S
- **Removes:** ~89 lines / 1 file
- **Blast radius:** None — nothing imports or calls this script; it is only ever invoked manually per docs.

### [CR-L04-03] CLAUDE.md's literal "every session reads ISSUES.md" costs ~35K tokens / ~2.5 hours if honored

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `project-harness/CLAUDE.md:268-269`: *"The file `project-harness/ISSUES.md`
  is the persistent issue log. Every session reads it. Every session updates it."* — no
  qualifier permitting a partial read or grep-only pass. `wc -l/-w/-c
  project-harness/ISSUES.md` → 1,799 lines / 19,080 words / 141,383 chars, i.e. **≈35,346
  tokens (chars÷4)** — 6.8× the size of the `CLAUDE.md` that states the rule, and on its own
  ≈17.7% of a 200K-token context budget. At a realistic 130 wpm technical-reading speed that
  is **145-150 minutes** of linear reading before any code is touched (see measurement 1).
- **Cost of inaction:** The instruction is either (a) followed literally, burning ~2.5 hours
  or ~35K tokens of every single session on a file that is 68 open issues of accreted detail,
  most irrelevant to the task at hand, or (b) silently not followed (an agent skims/greps
  instead), which is the practical reality but means the rule as written is fiction — the
  same failure mode CR-L07/CR-L13 already document for other harness claims (stale IDs,
  broken links). Either way the written process and the lived process have diverged.
- **Fix sketch:** Change the instruction to "grep ISSUES.md for the module/file you are about
  to touch" or split it into a short "Open P1s" head section (auto-surfaced) plus a full
  archive-style body that is searched, not read.
- **Effort:** S
- **Blast radius:** Process-only; no code change.

### [CR-L04-04] README's "Migration scripts" line names two files that do not exist anywhere in the repo

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md` "What's done" table: *"Migration scripts (001_remove_current_location_id, 002_remove_event_participants)"*. `find . -iname "001_*" -o -iname "002_remove*"` → no results, in the working tree or `project-harness/archive/`. The actual 7 migrations (`add_faction_support.py` etc.) use a completely different naming scheme and none removes a field.
- **Cost of inaction:** A reader trying to find or run these two referenced migrations cannot — the entry describes work that either never landed under that name or was deleted without updating the table (joins the pattern CR-L13 already documents for this README).
- **Fix sketch:** Replace the two names with the real 7-script list, or drop the parenthetical.
- **Effort:** S
- **Blast radius:** Documentation-only.

### [CR-L04-05] `migrate_faction_strings.py` migrates data but never retires the field it migrates away from

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `scripts/migrations/migrate_faction_strings.py` reads `Character.faction`
  string properties and creates `MEMBER_OF` edges (`CYPHER_CREATE_MEMBER_OF`), but nothing in
  the script, `character.yaml`, or any later commit removes or deprecates the `faction`
  string field — `type_registry/base_nodes/character.yaml` still declares
  `faction: { type: str, required: false }` today. `grep -rl "MEMBER_OF"` shows 10 live `src/`
  call sites plus 2 integration tests still reading the graph through both representations.
  No `docs/DATA_MODELS.md` note or `DECISIONS.md` entry marks the string field deprecated.
- **Cost of inaction:** Two sources of truth for the same relationship persist indefinitely;
  a future writer can set `Character.faction` without creating the edge (nothing enforces
  the two stay in sync post-migration), silently reintroducing the exact drift the migration
  was written to fix.
- **Fix sketch:** Either add a `DECISIONS.md` entry explaining the string field is
  intentionally kept as a display cache (if true), or schedule its removal and mark it
  deprecated in `character.yaml`'s field description now.
- **Effort:** S
- **Blast radius:** `character.yaml` consumers that read `faction` directly (`grep` shows the
  seeders and a few query files) would need the edge-based read path first.

### [CR-L04-06] No gate catches a required-field schema change shipped without a migration

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Gap
- **Evidence:** `node_validator.validate_node_write` (`src/npc_engine/type_registry/node_validator.py:17-33`) validates only at write time, per node, with no batch/startup re-validation of existing graph data. None of the 10 `scripts/check_*.py` gates (`check_base_rate`, `check_conservation`, `check_dead_keywords`, `check_engine_coverage`, `check_harness_honesty`, `check_human_gates`, `check_label_survival`, `check_layers`, `check_rules`, `check_test_quality` — full enumerated list) inspects git diffs of `base_nodes/*.yaml`/`base_edges/*.yaml` for a `required: false → true` transition. Marked Likely rather than Confirmed because it is an absence-of-behavior claim verified by enumerating all 10 gate scripts by name, not by exhaustively reading each one's full body.
- **Cost of inaction:** A future contributor can flip a field to `required: true` (the exact scenario `DECISIONS.md:600` already discusses avoiding) and nothing in `make check` will flag that existing customer graphs now contain invalid nodes until a write path trips a `pydantic.ValidationError` in production.
- **Fix sketch:** A lightweight gate script that diffs `base_nodes|base_edges/*.yaml` for `required` value flips and fails the build unless a matching migration script (or a `DECISIONS.md` entry) is present in the same PR.
- **Effort:** M
- **Blast radius:** New CI gate only; no existing code touched.

---

## Return summary

Severity counts: HIGH 2, MEDIUM 4, LOW 0 (6 findings total).

Top 3: CR-L04-01 (no migration down path / no applied-state tracking, HIGH), CR-L04-03
(CLAUDE.md's literal "every session reads ISSUES.md" costs ~35K tokens / ~2.5h, HIGH),
CR-L04-02 (`add_faction_support.py` dead since 2026-06-04, docs still prescribe it, MEDIUM).

---

## L5 — CLAUDE.md and rules-as-written

# CR-L05 — `CLAUDE.md` and rules-as-written

Lens L5. Branch `eval-ab-context-arms`, HEAD `d46ae42`, 2026-08-28. **Read-only** — no source file
was created, edited or deleted; this evidence file is the only write. Subject:
`project-harness/CLAUDE.md`, 476 lines, auto-loaded into every session via the one-line root
`CLAUDE.md` (`@project-harness/CLAUDE.md`).

Every rule in the file is treated here as a **claim to be tested**, not as a rubric.

---

## Required measurements

### 1. Claims verification — 109 checked / 26 FALSE / 6 unverifiable

**Method.** Walked the file top to bottom and extracted every discrete checkable assertion: the
stack table, all 13 `make` targets, all 13 rows of the file-locations table, the demo-world NPC
table, the 15-package layer block and its 10 explicit rank annotations, the 6 allowed-dependency
rows, the 4 forbidden cross-layer patterns, the code-style/documentation/testing sections, and all
**28** rules marked **(strict)**. Each was verified by running the command, reading the source, or
computing the count. Unverifiable = the rule has no operational definition, not "I did not check".

| Metric | Count |
|---|---|
| Claims checked | **109** |
| Claims **FALSE** | **26** |
| Claims unverifiable | **6** |
| Claims TRUE | 77 |

Two sections verified **100% TRUE and worth keeping verbatim**: the *Key commands* table (13/13 —
`make -n <target>` exits 0 for all 12 targets plus `docker-compose.yml` present) and the *Test
layout* block (`tests/{unit,integration,contract}`, root `conftest.py`, `e2e/{scenarios,scripts}`,
`e2e/transcripts/` gitignored at `.gitignore:24` — all 7 paths exist). All 13 rows of *Key file
locations* resolve. All 10 rank annotations match `scripts/check_layers.py:32-56` exactly.

#### Every FALSE claim, with the measured truth

| # | CLAUDE.md line | Claim | Measured truth | How measured |
|---|---|---|---|---|
| 1 | `:22` | "no OpenAI adapter ships today" | `src/npc_engine/engines/llm/openai_adapter.py` exists (`class OpenAICompatibleAdapter(LLMClientProtocol)`), is registered at `engines/llm/factory.py:107 register_backend("openai", _build_openai)`, and has settings `OPENAI_API_URL`/`OPENAI_API_KEY` at `config.py:114-115` (SHIP-02 / DEC-126) | `find src -iname "*openai*"`; `grep -rn openai src/` |
| 2 | `:23` | "Python 3.14" as the platform | `pyproject.toml:8 requires-python = ">=3.11"`; `mypy.ini:2 python_version = 3.11`. Only `.github/workflows/ci.yml` uses 3.14 (5 jobs). Two of the repo's own config files target 3.11 (concurs CR-L16-06) | `grep -n requires-python pyproject.toml; grep -n python_version mypy.ini` |
| 3 | `:53` | demo seeder = "5 NPCs, 3 locations, **3 factions**" | 5 NPCs OK, 3 locations OK, **4 factions** — `demo_game/seeds/seed.py:896` adds `("iron_legion", "Iron Legion", "military", …)` under `_MILITARY_FACTIONS` | AST/regex scan of `seed.py` |
| 4 | `:57` | "`evals/matchers.py:62-63` resolves `parents[1] / "prompts" / "eval"`" | The resolution is at **`evals/matchers.py:72-73`**. Lines 62-63 today are `score: bool \| None` / `error: str = ""`. This line is the file's **own explicit self-correction, dated 2026-08-10** — it drifted within 17 days | `sed -n '58,75p' evals/matchers.py` |
| 5 | `:86-101` | The layer block enumerates the package set | `check_layers.py` `LAYER_RANK` has **18** entries. CLAUDE.md lists 15 and omits **`observability/` (rank 1)** and **`setup/` (rank 1)**, both real first-level packages in `src/npc_engine/` | `ls src/npc_engine/`; `sed -n '30,56p' scripts/check_layers.py` |
| 6 | `:104` | "Allowed dependencies (**enforced by `make check-layers`**)" followed by 6 explicit rows | The gate enforces a numeric rank ordering (`importer_rank < imported_rank` ⇒ violation, `check_layers.py:117-125`), **not** these rows. Every same-rank (peer) import is green under the gate and absent from the table | Read `check_layers.py`; counterfactual already executed by CR-L06 §4 |
| 7 | `:111` | "`config/common/type_registry/schema/utils` → **nothing**" | **52** intra-`npc_engine` imports originate in those five packages (type_registry 21, schema 18, utils 9, common 4), e.g. `type_registry/base_contract_loader.py:18` → `common.yaml_utils`, `:21` → `utils.errors`. All are rank-1→rank-1 and **all pass `make check-layers`** | `grep -rn "from npc_engine\." src/npc_engine/{config,common,type_registry,schema,utils}/` |
| 8 | `:128` | "Hard limit: **300 lines** of non-test code per file. If you exceed this, split before merging" | **42** non-test `.py` files exceed 300 lines today: src 13, demo_game 18, evals 7, scripts 2, seeds 2. 38 are permanently grandfathered; the 4 in `scripts/`+`seeds/` are scanned by no gate at all. `python scripts/check_rules.py` → `OK - no new violations (133 grandfathered).` | Ran `_iter_py`/`_oversized_functions` from `scripts/check_rules.py` over every tree |
| 9 | `:146` | "Use `from __future__ import annotations` at the top of **every** module" | **96** files lack it: `demo_game` 20/183, `tests` 74/544, `evals` 2/110. `src/npc_engine` is **627/627 compliant** — the only tree mypy covers | AST scan |
| 10 | `:162-172` | Mandatory 5-field module docstring (`Module:/Layer:/Purpose:/Dependencies:/Used by:`) | **176 of 627 (28%)** src files carry all five. Per field: `Layer:` **100%**, `Purpose:` **100%**, `Module:` 65%, `Used by:` 66%, `Dependencies:` **28%**. `scripts/docstring_audit.py:44-48` checks exactly `Layer:` and `Purpose:` — see CR-L05-03 | AST scan of all 627 files |
| 11 | `:255` | "Every public function has at least one happy-path test and one failure test" | 11 of 18 engine failure branches are driven by **no** test (CR-L01 §2, Confirmed); `graph/intent/intent_queries.py`'s real logic is mocked out at every caller (CR-L15-02) | Sibling evidence, Confirmed |
| 12 | `:333` | Pre-merge checklist: "`STATUS.md` (or task tracking file) is updated" | **No `STATUS.md` exists anywhere in the repo.** `find . -name "STATUS.md" -not -path "./.git/*"` → empty. Only `project-harness/archive/STATUS_history_through_2026-05-28.md` | `find` |
| 13 | `:331` | Pre-merge checklist: "…is in `PATTERNS.md`" | Root `PATTERNS.md` does not exist; the file is `project-harness/PATTERNS.md`, and the canonical-locations section at `:262` names only ISSUES/DECISIONS/ROADMAP | `ls` |
| 14 | `:385` | DIP: "engines import `LLMClientProtocol`, never **`MistralAdapter`**" | `MistralAdapter` has **never existed in any `.py` file in 967 commits**. `git log -S "MistralAdapter" --all` → 15 commits, every one a markdown-only edit; `grep -rn Mistral --include=*.py src/ demo_game/ evals/` → 0 | `git log -S`; grep |
| 15 | `:387` | "`api/dependencies.py` is the **sole** composition root for the API layer" | Six composition modules: `dependencies.py` (296 L), `dependencies_infra.py`, `dependencies_stores.py` (7 concrete constructions), `dependency_singletons.py` (122 L), `dependencies_engines/{core,quest,tick_slots}.py`, `dependencies_advanced/{politics,progression,social}.py`. The path is also wrong (`src/npc_engine/api/dependencies.py`) | `ls src/npc_engine/api/ \| grep depend` |
| 16 | `:396` | "no function or method may exceed **40 lines**" | **199** live violations: src 102, evals 42, demo_game 46, scripts 7, seeds 2. 144 grandfathered; **55 are scanned by no gate** (`check_rules._collect` applies `_oversized_functions` only to `src`, line 126) | Ran `_oversized_functions` over every tree |
| 17 | `:399-401` | "No magic numbers… No raw numeric thresholds like `if trust > 50`" | 13 raw numeric comparisons in `engines/` alone, including `engines/emotion/emotion_state.py:51 if arousal >= 70 and valence < -20` — the forbidden shape verbatim | regex scan |
| 18 | `:405-407` | "Pydantic v2 for all data… **No raw `dict` crossing a module boundary**" | **537 of 1,582 (33%)** public functions in `src/npc_engine/` are annotated to return a raw `dict`/`dict[str, …]` | AST scan of return annotations |
| 19 | `:416-418` | "all domain errors are typed exceptions in `utils/errors.py` **with structured fields**" | Violated **inside the named file, twice**: `utils/errors.py:301 class TokenBudgetExceededError(Exception)` and `:345 class ContextBudgetError(Exception)` — neither derives from `NPCSystemError` (`:29`) nor carries a field. Concurs CR-L01/CR-L08 | `grep -n "^class " src/npc_engine/utils/errors.py` |
| 20 | `:421-423` | "Neo4j unavailable → raise `GraphUnavailableError` → API **503**" | `grep -rn "raise GraphUnavailableError" src/` → **0**. `grep -rn "503" src/npc_engine/api/` → **0**. Never true at any point: `git log -S "raise GraphUnavailableError" -- src/` → **0 commits**. 14 of 18 engine fallbacks unwired (CR-L01 §1) | grep + `git log -S` |
| 21 | `:424-425` | "**No try/except around internal invariants**" | `scheduler/tick_scheduler.py:239` (catch-all around all 27 engines), `engines/dialogue/degradation.py:107` and `:119`, `retrieval/context/context_budget_enforcer.py:348` (CR-L01 §3, Confirmed) | Sibling evidence |
| 22 | `:444-445` | "`asyncio.gather()` calls that could spawn unbounded coroutines **must** be capped with `asyncio.Semaphore`" | 6 `asyncio.gather` sites in src; 2 are semaphore-bounded (`intent_formation_engine.py:107`, `memory_consolidation_engine.py:214`). `engines/chapter/chapter_engine.py:230-235` runs **three nested gathers with no semaphore** | `grep -rn "asyncio.gather\|asyncio.Semaphore" src/` |
| 23 | `:451-453` | "Include `npc_id`, `player_id`, `tick`, and `duration_ms` in **all** engine log entries" | **0 of 118** engine log calls carry all four. Only 28 of 118 carry even `npc_id`. Compliance rate **0%** | AST/regex scan of `src/npc_engine/engines/**` for `LOGGER.<level>(` + 400-char kwarg window |
| 24 | `:457-458` | RNG seed logged "for any gossip pair selection, **event sampling**, or distortion probability call" | Gossip logs its seed; event sampling does not (CR-L01-11, Confirmed) | Sibling evidence |
| 25 | `:462-464` | "`context_builder.py` **raises** `TokenBudgetExceededError` if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET`" | Raised **nowhere in `src/`**. The class's only reference outside its own definition is an import in `tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`. The mechanism existed (`f3d1a0a` 2026-06-03, SEV-07) and was **deleted on 2026-06-11** by `45b781d` "delete dead token_budget_enforcer". The rule has described removed code for **78 days**, through 5 subsequent edits of CLAUDE.md | `grep -rn TokenBudgetExceededError`; `git log -S "raise TokenBudgetExceededError"` |
| 26 | `:475-476` | "**every** route except `GET /health` passes through `auth/middleware.py`" | `auth/middleware_helpers.py:66-72` exempts five classes: `/health`, `/readiness`, **`/setup/*` in every env including prod** (covering `POST /setup/validate` and `POST /setup/config`, `api/routes/setup/setup.py:54,97`), and `/docs`,`/redoc`,`/openapi.json`,`/dashboard/*` in dev. The rule names one of five, and the unconditional one is the mutating one | Read `middleware_helpers.py:46-73` |

#### Unverifiable (6) — no operational definition exists, so the rule cannot be tested or enforced

`:381-382` SRP ("every module belongs to exactly one category — data model, reader, writer,
handler/orchestrator, utility, protocol, adapter, or test"); `:384` OCP ("never edit existing engine
files to add a new variant" — requires per-commit intent); `:388-389` ISP ("protocols must be
small" — no threshold); `:390-392` LSP (requires differential mock-vs-real testing that does not
exist); `:414-415` fail-fast ("validate **all** external inputs" — "all" not enumerable);
`:256` "Functions touching Neo4j have integration tests against a **real test DB**" (needs a live
Neo4j; not run in this read-only pass).

---

### 2. Token cost of the mandatory context load

Measured with `wc -c`. Every one of these files is injected before the user's first token — the
project file by `@`-import, the user-level rules and memory by the harness (all appear in this
session's own system-reminder).

| File | Chars | Est. tokens (chars ÷ 4) |
|---|---|---|
| root `CLAUDE.md` | 27 | 7 |
| `project-harness/CLAUDE.md` | **20,786** | **5,197** |
| `~/.claude/rules/common/*.md` (9 files) | 10,628 | 2,657 |
| `~/.claude/rules/README.md` | 4,310 | 1,078 |
| project `memory/MEMORY.md` | 844 | 211 |
| **Total mandatory preamble** | **36,595** | **≈ 9,150** |

- **9,150 tokens ≈ 4.6% of a 200k context**, before a single file is read.
- `project-harness/CLAUDE.md` alone is **5,197 tokens ≈ 2.6%**.

**Strategic number.** 967 commits; **193 session transcripts** exist for this project
(`ls ~/.claude/projects/c--Users-lohan-Documents-hackathons-NPCSystem/*.jsonl | wc -l` → 193),
i.e. ~5 commits per session. At **one** load per session that is **≈ 1.77M tokens** of mandatory
preamble to date, of which **≈ 1.00M** is `project-harness/CLAUDE.md`. This is a **floor**: the
preamble is re-injected on every compaction, and CR-L10-07 establishes the commit stream is
loop-driven (many sessions compact more than once).

The file has only ever grown. Per-commit `wc -l` across the 14 commits that touch it:

```
2026-05-28 82a22af 346
2026-06-01 ccec168 448
2026-06-04 e7c265e 454
2026-06-04 d24f442 464
2026-06-15 59b7e70 468
2026-06-23 c1c7607 475
2026-07-31 b69da87 475
2026-08-10 8c7fdc6 476   <- HEAD
```

**+130 lines in 3 months, 0 lines ever removed.** The 2026-08-10 edit was the `prompts/eval/`
self-correction — which is already stale (FALSE claim #4 above).

---

### 3. Dead rules — never violated in 967 commits

Method: `git log -S "<literal>" --all -- <paths>` for each mechanically searchable rule, plus the
two baseline files, `archive/ISSUES_RESOLVED.md` (155 archived entries) and `ISSUES.md` (68 open).

| Rule | Search | Result |
|---|---|---|
| `:417` "Never `raise Exception("message")`" (gated as **R004**) | `git log -S "raise Exception(" -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. The gate has never had anything to catch |
| `:152` "No wildcard imports" | `git log -S "import *" -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. Ungated |
| `:153` "No relative imports beyond one level" | `git log -S "from .." -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. Ungated |
| `:119` "No HTTP calls between services" | `git log -S "httpx" -- src/npc_engine/services/` | **0 commits, ever.** 0 live. Ungated |
| `:385` DIP `MistralAdapter` example | `git log -S "MistralAdapter" --all` | 15 commits, **all markdown**. The class has never existed in Python |
| `:421-423` `GraphUnavailableError` → 503 | `git log -S "raise GraphUnavailableError" -- src/`; `git log -S "status_code=503" -- src/npc_engine/api/` | **0 and 0.** The contract has never once been implemented |
| `:462-464` `TokenBudgetExceededError` raise | `git log -S "raise TokenBudgetExceededError"` | Added `f3d1a0a` 2026-06-03, **deleted `45b781d` 2026-06-11**. Dead for 78 days |
| `:397` Nesting ≤ 3 | AST | 4 violations in 2,248 src functions (**0.2%**). Ungated but genuinely obeyed |

**Four rules (wildcard imports, deep relative imports, inter-service HTTP, `raise Exception(`) have
zero violations across the entire 967-commit history and are free to delete** — three of them are
enforced by nothing anyway, and the fourth (R004) is a gate that has never fired. **Three more
(`MistralAdapter`, `GraphUnavailableError`→503, `TokenBudgetExceededError`) are dead in the worse
sense: they describe machinery that does not exist.**

---

### 4. Aspirational rules — violated 20+ times

Ranked by live violation count. A rule with three digits of violations is not a rule.

| Rank | Rule | Live violations | What it actually is |
|---|---|---|---|
| 1 | `:405-407` Pydantic v2 / no raw `dict` crossing a boundary | **537** of 1,582 public src functions (33%) | An unstated preference. Nothing measures it; a third of the public surface contradicts it |
| 2 | `:162-172` 5-field module docstring | **451** of 627 src files non-conforming (72%) | A 2-field rule with 3 decorative fields |
| 3 | `:396` Function length ≤ 40 lines | **199** (144 baselined, 55 outside every gate) | A frozen debt register. CR-L06 §3 measures the burn-down at 1.43/month ⇒ **7.8 years to zero** |
| 4 | `:451-453` 4-field engine log entries | **118 of 118** (0% compliance) | A sentence nobody has ever implemented |
| 5 | `:146` `from __future__ import annotations` on every module | **96** files | True in the one tree mypy covers, false everywhere else |
| 6 | `:451` "Never `print()`" | **59 files** — 20 in `evals/` (grandfathered) + 39 of 47 in `scripts/` (ungated) | A src-only rule stated repo-wide. The gate scripts that enforce it violate it |
| 7 | `:128` 300-line file limit | **42** files | A floor with a permanent exemption list |
| 8 | `:399-401` No magic numbers | 13 in `engines/` alone, incl. the forbidden shape verbatim | Advice |
| 9 | `:397` Nesting ≤ 3 | 24 repo-wide (4 in src) | Borderline — genuinely obeyed in src |

---

### 5. Gate coverage of the 28 **(strict)** rules

| # | Strict rule (line) | Gated by | Live violations | Verdict |
|---|---|---|---|---|
| 1 | SRP `:381` | none | unmeasurable | **theatre** |
| 2 | OCP `:384` | none | unmeasurable | **theatre** |
| 3 | DIP `:385-387` | none (mypy is a weak proxy) | 6 composition roots; example class never existed | **aspirational** |
| 4 | ISP `:388` | none | unmeasurable | **theatre** |
| 5 | LSP `:390` | none | unmeasurable | **theatre** |
| 6 | Function length `:396` | `check-rules` **R006** (src+evals only) | 199 | **aspirational** |
| 7 | Nesting `:397` | none | 4 in src | **live** |
| 8 | No magic numbers `:399` | none | 13+ | **aspirational** |
| 9 | Pydantic v2 / no raw dict `:405` | none | 537 | **aspirational** |
| 10 | Enums/Literal `:408` | none | unmeasured | **theatre** |
| 11 | Fail fast at boundaries `:414` | none | unmeasurable | **theatre** |
| 12 | Custom exception hierarchy `:416` | `check-rules` **R004** (literal `raise Exception(` only) | 0 by the gate; **2 by the rule** (`errors.py:301,345`) | **theatre** — the gate matches a string never written and misses both real violations, in the file the rule names |
| 13 | Never swallow errors `:419` | `check-rules` **R003** (src+evals) | 3 baselined + 10 silent sites (CR-L01 §3) | **aspirational** |
| 14 | Engine boundary fallbacks `:421` | none | 14 of 18 unwired; 0 raises; 0 `503` | **dead** |
| 15 | No try/except around invariants `:424` | none | 4 named sites | **aspirational** |
| 16 | Constructor injection `:429` | none | ~0 | **live** |
| 17 | Session ownership `:433` | none | 0 — `graph/infra/transaction_coordinator.py:43,46` is the only file calling `begin_transaction()`/`commit()` | **live** |
| 18 | Async all the way `:442` | none | unmeasured | **theatre** |
| 19 | Semaphore for batch `:444` | none | 4 of 6 gathers uncapped | **aspirational** |
| 20 | Lock for shared state `:446` | none | 0 (`emotion_store.py:28`, `session_store.py:41`) | **live** |
| 21 | Structured logging / never print `:451` | `check-rules` **R002** (src+evals) | 59 files print; 0/118 log calls carry the 4 fields | **aspirational** |
| 22 | LLM prompt redaction `:454` | **runtime validator** `config_logging_validators.py:56` | 0 | **live (genuinely gated)** |
| 23 | RNG seed logging `:457` | none | 1 of 3 sites | **aspirational** |
| 24 | Token budget enforced `:462` | none | mechanism deleted 2026-06-11 | **dead** |
| 25 | Structured output validated `:465` | none | `engines/dialogue/response_parser.py` exists | **live** |
| 26 | Idempotent assembly `:467` | none | 0 (no `datetime`/`uuid`/`random` in `prompt_builder.py`) | **live** |
| 27 | Input caps `:472` | **runtime** `dialogue_models.py:51` + `clock.py:37 Field(ge=1, le=MAX_DELTA_TICKS)` (`config.py:51 = 1000`) | 0 | **live (genuinely gated)** |
| 28 | Auth on all routes `:475` | tests only | 4 undeclared exemption classes | **aspirational** |

**Totals: 28 strict rules — 5 gated (R002, R003, R006 + 2 runtime validators), 1 gated by a gate
that does not gate (R004), 22 ungated.**

Applying **CR-L06 §4**'s executed counterfactuals to the gate side: of the 14 targets in `make
check`, **6 fail the counterfactual** (`check-human-gates`, `check-conservation` I2,
`check-test-quality`, `check-docstrings`, `check-harness`, `check-label-survival`). Of the rules
above, the one carried by `check-docstrings` (#10 in the FALSE table) is therefore **gated by a
gate proven not to gate**: CR-L06 executed `docstring_audit.audit` against a scratchpad file whose
docstring read `"""Layer: banana\nPurpose: \n"""` and got **0 findings**.

Three of the five real gates (R002/R003/R006) are **ratchets whose baseline equals their live set
exactly** — verified by importing `check_rules._collect()` and `_collect_evals()` at HEAD:
`{'R001': 31, 'R006': 102}` (133) and `{'R001': 7, 'R002': 20, 'R003': 3, 'R006': 42}` (72). Every
current violation is pre-approved. The gates can only catch the 967th-commit-plus-one.

---

### 6. Contradictions and self-conflicts

| # | Conflict | Both references |
|---|---|---|
| 1 | "**Hard limit**: 300 lines… split before merging" vs. an enforcement mechanism that permanently exempts 38 files and reports `OK` | `CLAUDE.md:128` vs `scripts/check_rules.py:186` ("split it **or add a DECISIONS.md waiver**") + `rules_baseline.txt` (133 rows). CLAUDE.md **never mentions grandfathering**, so a session reading only CLAUDE.md believes the limit is hard and a session running only the gate believes the tree is clean |
| 2 | The pre-merge checklist mandates updating a file that does not exist | `CLAUDE.md:333` (`STATUS.md`) vs `find . -name STATUS.md` → empty |
| 3 | The pre-merge checklist names `PATTERNS.md` unqualified while the canonical-locations section deliberately qualifies its three siblings and omits this one | `CLAUDE.md:331` vs `CLAUDE.md:262-264` |
| 4 | `SKILLS_QUEUE.md` is named as a normative destination for questions; CR-L07-08 measures it dead for ~90 days | `CLAUDE.md:306` vs CR-L07-08 |
| 5 | "Allowed dependencies (**enforced by `make check-layers`**)" — the gate enforces a different (weaker, rank-based) rule that permits 52 imports the table forbids | `CLAUDE.md:104-111` vs `scripts/check_layers.py:117-125` |
| 6 | The exception-hierarchy rule is violated inside the file it names as the single source of truth | `CLAUDE.md:416-418` vs `src/npc_engine/utils/errors.py:301,345` |
| 7 | vs **`HARNESS_GATES.md`**: CLAUDE.md's rules are enforced by a `make check` that HARNESS_GATES describes as 5 targets; it is 14 (`Makefile:200`). HARNESS_GATES also states the rules baseline is "57 today" (it is 133) and the mypy baseline "256 today" (it is `0`) | CR-L13-01, CR-L06 §5 — both headline numbers wrong, in opposite directions |
| 8 | vs **user-level `~/.claude/rules/common/coding-style.md`**: "200-400 lines typical, **800 max**" and "Functions are small (**<50 lines**)" — both looser than CLAUDE.md's 300/40, loaded in the same preamble, with no precedence statement in either file | user rules vs `CLAUDE.md:128,396` |
| 9 | vs **user-level `development-workflow.md`**: step 0 is *mandatory* "GitHub code search first: run `gh search repos` and `gh search code` before writing anything new". CR-L06 §5 measured `gh: command not found` on this machine. A mandatory first step is unexecutable | user rules vs environment |
| 10 | vs **user-level `testing.md`**: "Minimum Test Coverage: 80%" applies to everything; the repo's actual floors are `--cov-fail-under=80` for `tests/` (`Makefile:53`) and **75** for evals (`Makefile:139`), with `demo_game/` (36,961 LOC, 1,116 tests) under **no** coverage floor and in neither `make check` nor CI (CR-L06 §7, CR-L15-06) | user rules vs `Makefile:53,139` |
| 11 | "These rules are not suggestions. **Violating them is a bug**" vs. 26 of the file's own claims being false and 22 of 28 strict rules being ungated | `CLAUDE.md:3-4` vs §1 and §5 above |

---

## Subtraction proposal — `CLAUDE.md` 476 → **248 lines**

The governing principle: **a rule that is unenforced, dead, or contradicted by the code is worse
than no rule**, because it is the evidence a session uses to conclude the whole file is decorative.
The measured proof that this has already happened is CR-L05-03: on the two docstring fields a gate
checks, compliance is **100%**; on the three it does not, **28–66%**. Sessions obey gates and read
past prose.

### Delete (228 lines)

| Lines | Section | Lines removed | Why the deletion is safe |
|---|---|---|---|
| `155-215` | **Documentation** (whole section) | **58** (keep 3) | Replace with: *"Every module docstring carries `Layer:` and `Purpose:`; `__init__.py` also `Public surface:`. Enforced by `make check-docstrings`."* That is precisely what `docstring_audit.py:44-48` checks and what the tree achieves (100%/100%/100%). The 5-field format is at 28%; the `__init__.py` template block, the "what does NOT need documentation" list and the closing homily are 58 lines of prose that changed nothing measurable |
| `266-306` | **Issues log** template + id/archive protocol | **38** (move, don't delete) | Pure boilerplate that belongs in `ISSUES.md`'s own header, where the live examples already are. It is loaded into every session but consulted in the small minority that log an issue |
| `219-231` | **TDD discipline** (RED/GREEN/REFACTOR) | **13** | Duplicated near-verbatim in the user-level `~/.claude/rules/common/testing.md`, which loads in the same preamble. Paying twice |
| `253-258` | **Test requirements per module** | **6** | 4 claims: one FALSE (`:255`, 11 untested failure branches), one unverifiable (`:256`), two unmeasured. No gate |
| `379-392` | **SOLID** (SRP/OCP/ISP/LSP + DIP) | **12** (keep 2) | SRP/OCP/ISP/LSP are all **unverifiable — no operational definition, no gate, no violation ever recorded**. DIP survives as two lines with the `MistralAdapter` example (never existed) and the "sole composition root" clause (6 roots) removed |
| `421-423` | **Engine boundary fallback contracts** | **3** | Describes a contract implemented **0 times in 967 commits** (`git log -S "raise GraphUnavailableError"` → 0). Either implement it as CR-L01-08 proposes, or stop asserting it |
| `462-464` | **Token budget enforced** | **3** | Describes code **deleted on 2026-06-11** (`45b781d`). 78 days stale through 5 subsequent edits of this file |
| `457-458` | **RNG seed logging** | **2** (narrow to 1) | Two of its three named sites do not log a seed. Narrow to the one that does, or delete pending CR-L01-11 |
| `451-453` | **Structured logging** 4-field mandate | **2** (keep the `print()` line) | 0/118 compliance. Keep "use `utils/logging.py`, never `print()`"; delete the never-honoured field list |
| `152-153` | wildcard / deep-relative import bans | **2** | **0 violations in 967 commits**, no gate. Free to delete |
| `119` | "No HTTP calls between services" | **1** | **0 violations in 967 commits**, no gate |
| `417` (clause) | "Never `raise Exception("message")`" | **1** | **0 occurrences in 967 commits.** Replace the whole bullet with the *enforceable* form: *"Every class in `utils/errors.py` derives from `NPCSystemError` and carries structured fields"* — which is violated twice today and is one grep to gate |
| `26-44` | Key commands | **0 — keep** | 13/13 verified TRUE. Do not touch |
| `235-246` | Test layout | **0 — keep** | 7/7 verified TRUE. Do not touch |
| various | 26 FALSE claims corrected in place | ~**+8/−8** | Net zero lines, but this is the highest-value edit in the list |
| `364-371` | Token efficiency | **0 — keep** | 8 lines; the only section that pays for itself in a 9,150-token preamble |

**476 − 228 = 248 lines.**

### What survives, and why

Orientation and stack (**corrected**: OpenAI adapter ships, Python 3.11/3.14 split, 4 factions);
the 13 key commands and 13 key file paths (all verified TRUE — this is the file's single highest
value-per-token content, since it saves every session a `ls`/`make help` round trip); the demo-world
table (verified TRUE, and the "IDs are stable — do not rename" instruction is load-bearing); the
layer model **plus `observability` and `setup`**, with the allowed-dependency table replaced by the
one sentence the gate actually enforces (*"a package may import only packages of equal or lower
rank; ranks live in `scripts/check_layers.py`"*); the 4 forbidden cross-layer patterns minus the
dead one; code style minus the 3 dead import rules; test layout; the PM canonical-locations
paragraph; task discipline with the 3 dead checklist items removed; asking-before-doing; token
efficiency; and **the 13 strict rules that are either gated or measured obeyed** (function length,
never-swallow, print, nesting, ctor injection, session ownership, lock, redaction, structured
output, idempotent assembly, input caps, auth, Pydantic — the last three rewritten to state what is
true).

Every deleted rule that is worth keeping should be re-introduced **as a gate, not as prose**. Three
are one-grep gates that would have caught live violations today: `class .*\(Exception\)` in
`utils/errors.py` (2 hits), `-> dict` on public src functions (537 hits), and an
`asyncio.gather`-without-`Semaphore` check (4 hits).

---

## Findings

### [CR-L05-01] Delete or implement the three strict contracts whose machinery does not exist in `src/`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** Three rules marked **(strict)** describe mechanisms with zero implementation.
  (a) `CLAUDE.md:421-423` "Neo4j unavailable → raise `GraphUnavailableError` → API 503":
  `grep -rn "raise GraphUnavailableError" src/` → **0**; `grep -rn "503" src/npc_engine/api/` → **0**;
  `git log -S "raise GraphUnavailableError" -- src/` → **0 commits, ever**. Two service docstrings
  (`military_battle_service.py:59`, `military_resource_service.py:47`) quote the contract as fact
  (CR-L01 §1, rows 13/14: "unwired — docstring is fiction").
  (b) `CLAUDE.md:462-464` "`context_builder.py` raises `TokenBudgetExceededError`": the class at
  `utils/errors.py:301` is raised nowhere; its only non-definition reference in the repo is
  `tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`. `git log -S "raise TokenBudgetExceededError"`
  shows it was added by `f3d1a0a` (2026-06-03, SEV-07) and **deleted by `45b781d` on 2026-06-11**
  ("delete dead token_budget_enforcer").
  (c) `CLAUDE.md:385,387` DIP: `MistralAdapter` has never existed in a `.py` file
  (`git log -S "MistralAdapter" --all` → 15 commits, all markdown), and "`api/dependencies.py` is
  the **sole** composition root" is contradicted by six modules (`ls src/npc_engine/api/ | grep depend`).
- **Cost of inaction:** These are not stale comments; they are the file's own worked *examples* of
  what a "strict" rule looks like. A session that checks one and finds it fictional has been taught
  that "(strict)" is decorative, which is the mechanism behind the 22-of-28-ungated result in §5
  and the 100/100/28/66 docstring split in CR-L05-03. (b) has been wrong for 78 days across five
  edits of the file — the drift rate is already established.
- **Fix sketch:** Delete `:421-423` and `:462-464` outright (6 lines), or implement them under
  CR-L01-06/CR-L01-08 and keep the text. Rewrite the DIP bullet to two lines naming
  `LLMClientProtocol` and the real composition-root set.
- **Effort:** S (delete) / L (implement)
- **Removes:** ~10 lines of CLAUDE.md; unblocks deleting `TokenBudgetExceededError` (`errors.py:301`)
- **Blast radius:** Two `military_*_service.py` docstrings and `ports/dialogue_graph_port.py:73`
  quote contract (a) and must be corrected in the same change.

### [CR-L05-02] The 4-field engine-log mandate has 0% compliance across 118 call sites

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `CLAUDE.md:451-453` (strict): "Include `npc_id`, `player_id`, `tick`, and
  `duration_ms` in **all** engine log entries." Scanned every `LOGGER|_logger|logger|_LOGGER.<level>(`
  call under `src/npc_engine/engines/**` and inspected the following 400 characters of kwargs:

  ```
  engine log calls: 118; with npc_id: 28; with all 4 (npc_id,player_id,tick,duration_ms): 0
  ```

  **0 of 118.** No gate checks it; `check_rules.py`'s R002 only asks whether `print(` appears.
- **Cost of inaction:** Already realised, not future. CR-L01 §3 ranks `tick_scheduler.py:239` the
  #1 silent-failure site precisely because a dead engine produces a 200 with nothing correlatable;
  the field set this rule mandates is exactly what would make that observable. Every new engine
  written under this rule adds another uncorrelated log line, and the cost compounds with the 27
  tick slots.
- **Fix sketch:** Either add a bound-context helper in `utils/logging.py` that injects
  `npc_id`/`tick`/`duration_ms` at the engine boundary and gate on its use, or delete the field list
  from `:453` and keep only "use `utils/logging.py`, never `print()`" (true in `src/`: 0 real
  `print(` calls).
- **Effort:** S (delete) / M (bound-context helper)
- **Removes:** 2 lines of CLAUDE.md
- **Blast radius:** If implemented, touches the log call sites of all 27 engines.

### [CR-L05-03] Compliance tracks the gate, not the rule — measured 100/100/28/66 on one docstring

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `CLAUDE.md:162-172` mandates a **five**-field module docstring. `scripts/docstring_audit.py:44-48`
  checks **two** of them. Field-by-field compliance across all 627 `src/npc_engine/**/*.py`:

  | Field | In the rule | Checked by the gate | Compliance |
  |---|---|---|---|
  | `Layer:` | yes | **yes** | **627/627 = 100%** |
  | `Purpose:` | yes | **yes** | **627/627 = 100%** |
  | `Module:` | yes | no | 409/627 = 65% |
  | `Used by:` | yes | no | 414/627 = 66% |
  | `Dependencies:` | yes | no | **180/627 = 28%** |

  All five fields present: **176/627 = 28%.** The control: `demo_game/`, which
  `make check-docstrings` does **not** scan at all, sits at **150/183 = 81%** on the full 5-field
  format — *higher than the gated tree*, because it was written before the gate defined a lower bar.
  And CR-L06 §4 executed the counterfactual on the gate itself: a docstring reading
  `"""Layer: banana\nPurpose: \n"""` produces **0 findings**.
- **Cost of inaction:** This is the cleanest available measurement of what an unenforced rule is
  worth in this repo: **zero to +38 points**, and the gate's *definition* actively displaces the
  rule's. Every ungated rule in §5 (22 of 28) should be assumed to decay to its gated subset. It has
  been decaying since `38f7e87` (2026-06-04).
- **Fix sketch:** Cut `CLAUDE.md:162-172` to the two fields the gate checks plus `Public surface:`
  for `__init__.py` (at 102/102). If `Dependencies:`/`Used by:` are genuinely wanted, add them to
  `docstring_audit.py`'s `required` list and ratchet — do not leave them as prose.
- **Effort:** S
- **Removes:** ~58 lines of CLAUDE.md (the whole Documentation section collapses to 3)
- **Blast radius:** None if cutting. If gating the extra fields, 451 src files fail on day one and
  need a baseline.

### [CR-L05-04] The 300-line and 40-line "hard limits" are floors with permanent exemption lists, and CLAUDE.md never says so

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `CLAUDE.md:128` "Hard limit: **300 lines** of non-test code per file. If you exceed
  this, split before merging." `CLAUDE.md:396` "no function or method may exceed **40 lines**."
  Measured by importing `scripts/check_rules.py` and running its own scanners over every tree:

  ```
  src/npc_engine     files= 627  >300lines= 13  fns>40lines= 102
  demo_game          files=  96  >300lines= 18  fns>40lines=  46
  evals              files= 110  >300lines=   7  fns>40lines=  42
  scripts            files=  47  >300lines=   2  fns>40lines=   7
  seeds              files=   4  >300lines=   2  fns>40lines=   2
  ```

  **42 files and 199 functions over the limit**, and `python scripts/check_rules.py` prints
  `OK - no new violations (133 grandfathered).` The baseline set equals the live set **exactly**
  (`_collect()` → `{'R001': 31, 'R006': 102}`; `_collect_evals()` → `{'R001': 7, 'R002': 20, 'R003': 3, 'R006': 42}`).
  `check_rules._collect()` line 126 applies `_oversized_functions` only to `src`, so **46 demo_game
  + 7 scripts + 2 seeds = 55 function-length violations are outside every gate**; `scripts/` and
  `seeds/` are outside the file-size gate too (CR-L08-04). CR-L08-01 documents `demo_game/client.py`
  growing to 1,901 lines — **+481 while the gate stayed green** — against a DEC-034 waiver of ~750.
  CR-L06 §3 measures the R006 burn-down at 1.43/month ⇒ **7.8 years to zero**. CLAUDE.md contains
  **no mention of grandfathering, baselines, or waivers** for R006 at all.
- **Cost of inaction:** Two failure modes already realised. A session reading only CLAUDE.md
  believes 300/40 are hard and wastes effort splitting; a session running only `make check` believes
  the tree is clean. Meanwhile the four largest files grew past their own DECISIONS.md waivers by
  2–3× with no gate noticing (CR-L08-01/02/08).
- **Fix sketch:** State the ratchet in CLAUDE.md in one sentence next to `:128` and `:396` —
  *"enforced as a no-new-violations ratchet against `scripts/rules_baseline.txt`; the current
  exemption count is N"* — and extend `_collect()`'s `_oversized_functions` loop to `demo` (line
  126) so the 46 demo_game violations at least become visible debt.
- **Effort:** S (document) / M (extend scope + rebaseline)
- **Removes:** 0 lines; adds ~2
- **Blast radius:** Extending R006 to `demo_game/` adds 46 rows to `rules_baseline.txt`.

### [CR-L05-05] The R004 gate matches a string never written in 967 commits, and misses both real violations inside the file its rule names

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `CLAUDE.md:416-418` (strict): "all domain errors are typed exceptions in
  `utils/errors.py` **with structured fields**. Never `raise Exception("message")`."
  The gate is `check_rules.py:49 _RAISE_EXC_RE = re.compile(r"raise\s+Exception\(")`.
  `git log -S "raise Exception(" -- src/ demo_game/ evals/` → **0 commits, ever**; R004 is absent
  from both baseline files. The gate has never had anything to catch.
  The **substantive** half is violated twice, inside the file the rule names as the single source of
  truth: `src/npc_engine/utils/errors.py:301 class TokenBudgetExceededError(Exception)` and
  `:345 class ContextBudgetError(Exception)` — neither derives from `NPCSystemError` (`:29`) nor
  carries a structured field. `grep -n "^class " src/npc_engine/utils/errors.py | grep -v "Error)"`
  returns exactly those two plus the base.
- **Cost of inaction:** The repo currently believes this rule is gated. It is gated on the one form
  nobody has ever written, and unpoliced on the form that is live today. `ContextBudgetError` is
  the exception silently caught at `context_budget_enforcer.py:348` (CR-L01 §3, rank 2) — a
  fieldless bare-`Exception` subclass is exactly why that catch carries no diagnostic payload.
- **Fix sketch:** Replace `_RAISE_EXC_RE` with an AST check over `utils/errors.py` that every
  `ClassDef` whose name ends `Error` has `NPCSystemError` (or a subclass) in its bases. That is a
  ~15-line addition to `check_rules.py` and it goes red on 2 classes today.
- **Effort:** S
- **Removes:** ~1 line of CLAUDE.md (the dead `raise Exception(` clause); adds ~15 to `check_rules.py`
- **Blast radius:** Fixing the 2 classes touches `context_budget_enforcer.py` and the CR-L01-06
  decision about whether `TokenBudgetExceededError` survives at all.

### [CR-L05-06] "Auth on all routes except `GET /health`" understates the unauthenticated surface by four classes, one of them unconditional in prod

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `CLAUDE.md:475-476` (strict): "every route except `GET /health` passes through
  `auth/middleware.py`." `src/npc_engine/auth/middleware_helpers.py:66-72`:

  ```python
  if path in (HEALTH_PATH, READINESS_PATH):
      return True
  if path.startswith(SETUP_PATH_PREFIX):        # "/setup" — every env, prod included
      return True
  if path in DOCS_PATHS or path.startswith(DASHBOARD_PATH_PREFIX):
      return env == "dev"
  ```

  `/setup/*` covers `POST /setup/validate` and `POST /setup/config`
  (`api/routes/setup/setup.py:54,97`) — two **mutating** endpoints, unauthenticated in production.
  The code's own docstring justifies it ("localhost-only by bind (DEC-131)"), a constraint CLAUDE.md
  does not mention. CR-L13-09 separately records `/setup/*` as an entirely undocumented API surface.
  The rule also says "`GET` /health" while the code exempts by path only, ignoring method.
- **Cost of inaction:** The security rule most likely to be quoted in a licensing or integration
  conversation is the one that is wrong, and it is wrong in the permissive direction. A studio
  integrator reading `:475` will not know to check the bind address before exposing the container.
  CR-L16-07 measures the `app` container running as root with no healthcheck, so the localhost-bind
  assumption is the only thing holding.
- **Fix sketch:** Rewrite `:475-476` to enumerate the five exemption classes and state the DEC-131
  localhost-bind precondition for `/setup/*` explicitly, or move `/setup/*` behind a first-run
  bootstrap token.
- **Effort:** S (document) / M (token)
- **Removes:** 0; replaces 2 lines with 4
- **Blast radius:** `docs/API.md` (already missing the `/setup/*` surface per CR-L13-09) and the
  Unity first-launch wizard flow.

### [CR-L05-07] The layer model omits two real ranked packages and its dependency table is not what `check-layers` enforces

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CLAUDE.md:86-101` lists 15 packages; `scripts/check_layers.py:32-56` `LAYER_RANK`
  has **18**, adding `"observability": 1` and `"setup": 1` — both real directories in
  `ls src/npc_engine/`. A session adding a file to `observability/` has no layer entry to consult.
  `CLAUDE.md:104` claims the six dependency rows are "**enforced by `make check-layers`**", but the
  gate's rule is numeric (`check_layers.py:117-125`: violation iff `importer_rank < imported_rank`),
  which permits every same-rank import. Row `:111` "`config/common/type_registry/schema/utils` →
  **nothing**" is contradicted by **52** live intra-rank-1 imports — e.g.
  `type_registry/base_contract_loader.py:18` → `common.yaml_utils`, `:19` → `type_registry.*`,
  `:21` → `utils.errors` — **all of which pass the gate**. Separately, `CLAUDE.md:116` "No Neo4j
  queries outside `graph/`" is true today (0 hits) but its gate scans only 5 of 15 packages:
  `check_rules._CYPHER_SCAN_DIRS = ('engines','world','retrieval','services','scheduler')`, leaving
  `api/`, `auth/`, `data/`, `cache/`, `mutation/` unscanned (concurs CR-L06 §7).
- **Cost of inaction:** The layer model is the file's most-consulted section and the only one with a
  gate that CR-L06 §4 verified actually goes red. Two undocumented packages and a table that
  overstates what is enforced mean the section's authority is spent on rows that are decorative,
  and the one real constraint (rank ordering) is never stated.
- **Fix sketch:** Add `observability/` and `setup/` rows with `[config peer, rank 1]`; replace the
  six-row table with the sentence the gate implements — *"a package may import only packages of
  equal or lower rank; the ranks are in `scripts/check_layers.py`"* — and widen `_CYPHER_SCAN_DIRS`
  to all non-`graph` packages.
- **Effort:** S
- **Removes:** ~5 lines of CLAUDE.md (6 table rows → 1 sentence)
- **Blast radius:** Widening `_CYPHER_SCAN_DIRS` may surface new R005 rows; measured as 0 today.

### [CR-L05-08] The stack table is 18 days from its last edit and already wrong in three places

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `CLAUDE.md:22` states "no OpenAI adapter ships today", but
  `src/npc_engine/engines/llm/openai_adapter.py` defines `OpenAICompatibleAdapter(LLMClientProtocol)`,
  registered at `engines/llm/factory.py:107 register_backend("openai", _build_openai)`, with
  `OPENAI_API_URL`/`OPENAI_API_KEY` at `config.py:114-115` under SHIP-02/DEC-126.
  `CLAUDE.md:23` states Python 3.14 while `pyproject.toml:8` says `requires-python = ">=3.11"` and
  `mypy.ini:2` says `python_version = 3.11` (CR-L16-06 measures this as two incompatible targets).
  `CLAUDE.md:53` says the seeder creates "3 factions"; `demo_game/seeds/seed.py:896` adds a fourth
  (`iron_legion`). And `CLAUDE.md:57` — the file's **only explicitly dated self-correction**
  ("Corrected 2026-08-10… `evals/matchers.py:62-63` resolves `parents[1] / "prompts" / "eval"`") —
  now points at the wrong lines: the resolution is at `evals/matchers.py:72-73`; lines 62-63 are
  `score: bool | None` / `error: str = ""`. It drifted in **17 days**.
- **Cost of inaction:** The stack table is what a new session reads to decide whether a capability
  exists. "No OpenAI adapter ships today" will cause a session to build one that already exists —
  the single most expensive class of error this file can cause. The self-correction case establishes
  the drift rate for **any** `file:line` citation in this document: under three weeks.
- **Fix sketch:** Correct the three claims; replace the `matchers.py:62-63` citation with a
  line-number-free reference (`evals/matchers.py`, `_PROMPT_YAML_PATH`). As a standing rule, cite
  symbols, never line numbers, in a document edited 14 times in 3 months.
- **Effort:** S
- **Removes:** 0; corrects 4 claims
- **Blast radius:** None.

### [CR-L05-09] 9,150 tokens of mandatory preamble per session, ~1.8M to date, for a rule set that is 22/28 ungated

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -c` over the auto-loaded set: root `CLAUDE.md` 27 + `project-harness/CLAUDE.md`
  **20,786** + `~/.claude/rules/common/*.md` 10,628 + `~/.claude/rules/README.md` 4,310 +
  project `MEMORY.md` 844 = **36,595 chars ≈ 9,150 tokens** (chars ÷ 4), **4.6% of a 200k window**
  before the first file read. `project-harness/CLAUDE.md` alone is 5,197 tokens (2.6%).
  193 session transcripts exist for this project
  (`ls ~/.claude/projects/c--Users-lohan-Documents-hackathons-NPCSystem/*.jsonl | wc -l` → 193) across
  967 commits ⇒ **≈ 1.77M tokens** of preamble to date at one load per session (a floor — the
  preamble is re-injected on compaction), of which **≈ 1.00M** is the project file.
  Per-commit `wc -l` shows the file at 346 → 476 lines over 14 commits with **zero lines ever
  removed**. §5 measures that 22 of its 28 strict rules are enforced by nothing, and CR-L06 §4 shows
  one of the remaining gates fails its counterfactual.
- **Cost of inaction:** Roughly half of the largest fixed cost in every session buys rules that
  nothing checks and 26 claims that are false. The cost is monotonic — the file has only ever
  grown, and its growth rate (+130 lines/3 months) exceeds its correction rate (1 self-correction,
  itself now stale).
- **Fix sketch:** Execute the subtraction proposal above: 476 → 248 lines, ~10.4k chars, ~2.6k
  tokens — a **50% cut** in the project file's share of the preamble. Additionally, `TDD discipline`
  (`:219-231`) is duplicated in the user-level `rules/common/testing.md` loaded in the same
  preamble; deleting one copy is free.
- **Effort:** M
- **Removes:** **228 lines** of `project-harness/CLAUDE.md` (~10,400 chars, ~2,600 tokens/session)
- **Blast radius:** The Issues-log template (38 lines) must land in `ISSUES.md`'s header, not be
  lost. Nothing else references CLAUDE.md by line number.

### [CR-L05-10] Three pre-merge checklist items instruct sessions to satisfy things that do not exist

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CLAUDE.md:316-335` requires the checklist result be written into every task's final
  summary, and closes "If any item is not satisfied, the task is not done."
  `:333` "`STATUS.md` (or task tracking file) is updated" — `find . -name "STATUS.md" -not -path "./.git/*"`
  returns **nothing**; the only match anywhere is `project-harness/archive/STATUS_history_through_2026-05-28.md`.
  `:331` "Any new pattern reused twice is in `PATTERNS.md`" — root `PATTERNS.md` does not exist
  (`project-harness/PATTERNS.md` does), and the canonical-locations paragraph at `:262-264`
  deliberately qualifies its three siblings while omitting this one.
  `:323` "No file exceeds 300 lines of non-test code" — 42 files do (CR-L05-04); an honest session
  can never tick this box.
- **Cost of inaction:** A mandatory checklist with unsatisfiable items trains every session to tick
  boxes it has not verified — precisely the habit that produced the 29 false claims across `docs/`
  (CR-L13 §1) and the 26 here. The parenthetical escape hatch "(or task tracking file)" makes `:333`
  unfalsifiable, which is worse than deleting it.
- **Fix sketch:** Delete `:333`; change `:331` to `project-harness/PATTERNS.md`; change `:323` to
  "no **new** file exceeds 300 lines (`make check-rules` is green)".
- **Effort:** S
- **Removes:** 1 line; corrects 2
- **Blast radius:** None.

---

## Pre-merge checklist for this task

- [x] No source file created, edited or deleted — read-only lens honoured; the only write is this file
- [x] Every FALSE claim carries a `file:line` or a pasted command with real output
- [x] All three required integers reported (109 / 26 / 6)
- [x] Token cost measured, not estimated by eye (`wc -c`; method stated as chars ÷ 4)
- [x] Dead-rule claims backed by `git log -S` over the full 967-commit history, not a HEAD grep
- [x] No CRITICAL added — the review's three are already spent
- [x] No rule restated as a finding; every finding is a measurement *about* a rule
- [x] Adjacent work attributed to the sibling lens that owns it (CR-L01, CR-L06, CR-L08, CR-L13, CR-L15, CR-L16) rather than re-derived
- [ ] No `ISSUES.md` entries filed — this is a read-only review lens; the orchestrator owns backlog creation

### [CR-L05-11] The `/setup/*` auth exemption rests on a localhost bind that the shipped `docker-compose.yml` does not provide — an unauthenticated remote read of a stored plaintext API key

*Authored by the orchestrator, extending CR-L05-06. L5 raised the unconditional
`/setup/*` exemption as a question for a human; the deployment fact that turns it
from an accepted trade-off into a live vulnerability was outside its scope.*

- **Severity:** CRITICAL
- **Confidence:** Confirmed (every hop read or executed; nothing was exploited)
- **Kind:** Defect
- **Evidence:** Five hops, each verified.

  **1. The exemption is unconditional.** `src/npc_engine/auth/middleware_helpers.py`:
  ```python
  if path in (HEALTH_PATH, READINESS_PATH):
      return True
  if path.startswith(SETUP_PATH_PREFIX):
      return True                      # <- no env check
  if path in DOCS_PATHS or path.startswith(DASHBOARD_PATH_PREFIX):
      return env == "dev"              # <- compare: docs ARE env-gated
  ```
  `/docs` is gated on `env == "dev"`. `/setup/*` is not gated on anything. It is
  public in `dev`, `staging` **and `prod`**.

  **2. The stated trust boundary is the loopback bind.** The function's own
  docstring says "`/setup/*` is always public — localhost-only by bind (DEC-131)".
  `project-harness/DECISIONS.md:297-299` is explicit: "rely on the existing
  `127.0.0.1` bind (`stack_launcher.py`) so they are unreachable off-box.
  **The localhost boundary is the trust boundary — no token bootstrap needed.**"

  **3. The shipped container does not honour that bind.** `docker-compose.yml:72`
  publishes `"8000:8000"`, which Docker binds to all interfaces. Confirmed on the
  running stack:
  ```
  $ docker port npcsystem-app-1
  8000/tcp -> 0.0.0.0:8000
  8000/tcp -> [::]:8000
  ```
  `stack_launcher.py` may bind loopback, but `docker-compose up -d` — the path
  `README.md` and `project-harness/CLAUDE.md` document as *the* way to start the
  backend — does not. The sole control DEC-131 relies on is absent from the
  project's own primary deployment path.

  **4. The exposed surface includes a secret, by design.** Live against the
  running server, `GET /openapi.json` lists `POST /setup/validate`,
  `GET /setup/config`, `POST /setup/config`. DEC-131:302-303 states the wizard
  config "persists **plaintext**" a cloud API key in `~/.npc_engine/wizard_config.json`
  — accepted explicitly *because* the localhost boundary held. `GET /setup/config`
  reads that file back with no authentication.

  **5. The write side takes an unlisted directory parameter.**
  `src/npc_engine/api/routes/setup/setup.py:97-102` declares
  `config_dir: Annotated[str | None, Query(include_in_schema=False)] = None`,
  passed to `save_wizard_config`, which at
  `src/npc_engine/setup/wizard_config.py:97-102` does
  `config_dir.mkdir(parents=True, exist_ok=True)` then writes `wizard_config.json`
  into it. So an unauthenticated caller can create a directory anywhere the
  process can write and drop a fixed-name JSON file in it — as **root**, per
  CR-L16-07. Fixed filename, so not directly RCE; it is still an unauthenticated
  remote write primitive, and it is hidden from the OpenAPI schema, so no reader
  of `docs/API.md` would know it exists.

  This is the fourth CRITICAL and the brief asks for certainty above three. Each
  hop above was read in the source or executed against the live stack; hop 3 is
  the load-bearing one and is a one-line command anyone can repeat. No request
  was ever sent to a `/setup/` route.

- **Cost of inaction:** On any host where the compose file is used and port 8000
  is reachable — a LAN, a cloud VM with a permissive security group, a studio's
  shared dev box — an unauthenticated party reads the integrator's cloud API key
  and writes files as root. `CLAUDE.md`'s *Auth on all routes* rule (strict) says
  every route except `GET /health` is authenticated, so nobody auditing by the
  rules would look here.
- **Fix sketch:** Bind the published port to `127.0.0.1:8000:8000` in
  `docker-compose.yml`, and make the `/setup/*` exemption conditional on
  `env == "dev"` exactly as `/docs` already is. Then either drop `config_dir` from
  the route signature or restrict it to a fixed base directory.
- **Effort:** S
- **Blast radius:** `docker-compose.yml`, `auth/middleware_helpers.py`,
  `api/routes/setup/setup.py`. Rebinding to loopback changes how anyone reaching
  the API from another machine or another container connects — check `demo_game`'s
  `BASE_URL` and the e2e harness before shipping it. DEC-131 needs a superseding entry.

---

## L12 — Product coherence

# CR-L12 — Product coherence

Lens L12 of the 16-lens review. Branch `eval-ab-context-arms`, HEAD `d46ae42`, audited 2026-08-28.
Read-only; no source file was modified. Live API at `http://127.0.0.1:8000` used for read-only probes
(`Authorization: Bearer $API_KEY_SECRET` from `.env`). Sibling lenses CR-L01, CR-L02, CR-L03, CR-L07,
CR-L10, CR-L13, CR-L16 are cited, not re-derived.

**Verdict in one line:** this repository is an eval-research project that is building an increasingly
rigorous measuring instrument for a game engine whose signature feature does not work
(CR-L01-01/02), whose headline number is beaten by a fixed string (CR-L03-01), whose only shipping
artifact has never once been buildable, and which has no integrator, no pilot, and no second human.

---

## Required measurements

### 1. Convergence — licensable middleware, or an eval research project?

**Verdict: an eval research project. The product roadmap was formally deferred on 2026-07-31 and has
not been touched since.** The project says so itself.

`project-harness/UNREAL_DEFERRED.md:3-7`:

> **Moved out of `ROADMAP.md` on 2026-07-31**, during the eval-program planning session.
> **Why:** the active program is the eval pipeline (`ROADMAP.md` → *Active — Eval pipeline
> (EVAL-P0..P7)*). Everything below is **game-client integration work** — it is neither the
> engine nor its evals, and none of it is being worked on.

What was moved into that file: the Unity setup screen (SHIP-05b), the legible emergent hook
(SHIP-06), the talk-to-NPC client (SHIP-07), the 10-minute arc (SHIP-08), public distribution
(SHIP-09), the instrumentation/perf one-pager for the pitch (SHIP-10), the marketing clip (SHIP-11),
and all four Engine-SDK steps (SX.1 OpenAPI freeze, SX.2 Unity C# package, SX.3 Unreal plugin,
SX.4 sample scenes). **12 unchecked boxes, 119 lines, zero commits since.**

The framing that block sits under is retained verbatim in the same file (`UNREAL_DEFERRED.md:110-115`):

> **End goal: license the engine to studios (B2B).** … the near-term deliverable is a **small,
> downloadable, distributable demo game** … instrumented for the pitch.

That deliverable is 0% built.

**ROADMAP.md composition.** Every `## Active` / `## Program` heading in the live roadmap:

| Roadmap section (`project-harness/ROADMAP.md`) | Line | Subject |
|---|---:|---|
| Active — Eval suite redesign (EVAL-B2..FINAL) | 39 | evals |
| Active — Eval pipeline (EVAL-P0..P7) ← *"the current program"* | 122 | evals |
| Program 2 — Metric validity and the portfolio artifact (P9..P14) | 1120 | evals |
| Program 3 — Audit remediation and the regression harness (P15..P24) | 1600 | evals |
| Program 4 — The golden set rebuild and judge repair (P25..P28) | 3449 | evals |
| Program 5 — The first-class prompt arm (P29..P31) | 3540 | evals |
| Active — Folder reorganisation (REORG-PR6..PR9) | 3616 | harness |
| Active — ISSUES.md remediation program (REM-*) | 3639 | harness |

**Eight active programs, eight of them eval or harness meta-work. Zero product programs.** This is
the composition, not a sample of it. It corroborates the brief's 71% figure from a different angle:
71% of *items* are eval meta-work because 100% of *programs* are.

**Churn, last 200 commits** (`--no-merges`, file-touches; independently reproduced this session,
matches the brief to within rounding):

| Area | file-touches |
|---|---:|
| `evals/` | 393 |
| `tests/` | 322 |
| `project-harness/` | 288 |
| `src/npc_engine/` | 172 |
| `docs/` | 22 |
| `demo_game/` | **8** |
| `packaging/` | **1** |

**Commits, last 8 weeks (233 total):**

```
$ git log --since='8 weeks ago' --oneline -- <dir> | wc -l
project-harness  184      src         42
tests            149      scripts     38
evals            100      docs        20
                          demo_game    4
                          e2e          2
                          packaging    0
```

**Commit subjects, last 8 weeks, by conventional-commit scope:** `evals`/`eval` = **107 / 233 (46%)**;
add `harness`, `loop`, `roadmap` = **177 / 233 (76%)**. Everything touching engine code —
`retrieval`, `config`, `engines`, `dialogue`, `api`, `world`, `llm`, `seeds`, `quest` — totals
**33 / 233 (14%)**, and CR-L02-07 already established that 100% of the roadmap items that touch
engine code require editing an existing file rather than adding one.

**Size.** Product/demo/eval LOC is 54% / 29% / 16% (68,218 / 36,961 / 20,141 — the brief's corrected
figures, re-confirmed: `git ls-files demo_game | grep '\.py$' | xargs wc -l` → `36961 total`). But the
governing artifact is not code:

```
$ git ls-files project-harness | grep '\.md$' | xargs wc -l | tail -1
  48988 total          (246 tracked markdown files, 215 of them under archive/)
```

**48,988 lines of process markdown — 72% the line count of the entire engine source tree**, and
CR-L10-06 confirms the top-3 all-time churned files in the repo are all harness markdown.

**The forcing numbers:** 8 of 8 active roadmap programs are eval/harness. 76% of eight weeks of
commit subjects are eval/harness. `demo_game` 8 file-touches and `packaging` 1 in 200 commits. The
entire game-client program was moved to a deferred file 28 days ago and has had zero commits since.

---

### 2. What a game studio integrating this would need that does not exist

| # | Gap | Evidence it is absent | Blocks a pilot, or only GA? |
|---|---|---|---|
| G1 | **Unity C# package / Unreal C++ plugin** — the two clients `BUSINESS_REQUIREMENTS.md:21-22` names | `git ls-files \| grep -icE '\.(cs\|cpp\|h\|hpp\|uplugin\|asmdef)$'` → **0**. SX.2/SX.3 unchecked in `UNREAL_DEFERRED.md:63-65` | **Pilot.** A studio cannot start without writing the client themselves. |
| G2 | **A buildable distributable** — `docs/INTEGRATION.md:12-18` tells Unity to spawn `launcher.exe` | `packaging/npc_engine.spec:29-30` references `REPO_ROOT/"config"` and `REPO_ROOT/"game_schema.yaml"`; **neither exists, and neither existed at the spec's own introducing commit** (`git ls-tree 54e3a19 --name-only` → absent; `git log --all -- game_schema.yaml` → empty). PyInstaller is in no dependency set (`pyproject.toml:24-30`) and not installed. No CI job builds it. See CR-L12-02. | **Pilot.** There is no artifact to hand over. |
| G3 | **A frozen, versioned HTTP contract** — 148 operations over 132 paths, live | Total policy in the repo is one sentence: `docs/INTEGRATION.md:6` *"Routes and shapes may evolve; breaking changes will be announced."* No deprecation policy, no `/v2`, no contract test against a published spec. SX.1 (OpenAPI freeze) unchecked. Root `live_openapi.json` is 64 days stale (CR-L13-11); `docs/API.md` is missing 6 live routes (CR-L13-09, reproduced below). | **GA**, if the pilot partner tolerates breakage. |
| G4 | **Working reference behaviour for the feature being sold** | `docs/DEMO_SCRIPT.md:147` *"Each hop introduces deterministic distortion."* — CR-L01-01/02 confirm distortion never compounds across hops and the gossip write overwrites seeded distortion back to 0. | **Pilot.** See CR-L12-04. |
| G5 | **Any evidence of behaviour at contract scale** | Four of five NFRs never measured; graph is 190x below its stated node target. See §4. | **Pilot** for a studio with >52 NPCs, i.e. all of them. |
| G6 | **An error contract for a dependency outage** | The documented Neo4j-outage→503 path does not exist: `grep -rn "503" src/npc_engine/api/` → 0 (CR-L02-01); dialogue turns a Neo4j outage into a canned HTTP 200 (CR-L01, `degradation.py:107,119`). A studio cannot distinguish "backend down" from "NPC is being terse." | **Pilot.** |
| G7 | **A boot a studio engineer can perform** | Fresh clone does not boot on Windows without two undocumented fixes; three mutually contradictory setup docs (CR-L16-01, CR-L16-02). | **Pilot.** |

**Not gaps** (checked, and they are fine for the DEC-068 one-deployment-per-studio model): auth is a
shared per-deployment bearer secret and `BUSINESS_REQUIREMENTS.md:80-86` says exactly that;
rate limiting exists (`src/npc_engine/api/rate_limit.py`, in-memory token bucket per API key);
idempotency is header-enforced and documented (`docs/INTEGRATION.md:154-160`).

`docs/API.md` route-coverage check, reproduced independently against the live server:

```
live paths: 125   doc-referenced paths: 126   live-but-undocumented: 6
    /setup/config, /setup/validate, /v1/admin/debug/vector-store,
    /v1/admin/factions/{}/standings/{}, /v1/admin/schedules/character/{}/at,
    /v1/admin/vector-store/rehydrate
```

Exactly CR-L13-09's six. Cited, not claimed as new.

---

### 3. Top 3 gaps between the stated product and the built artifact

Ranked by how much they would surprise a buyer in the room.

| # | Documented claim (quoted, with file:line) | Measured reality |
|---|---|---|
| **1** | `docs/DEMO_SCRIPT.md:147` — *"tells Henryk. Each hop introduces deterministic distortion."* `:109` — *"One hop later. Faction name already garbled — the distortion engine ran."* `README.md:16` — *"Gossip engine (deterministic distortion, KNOWS_ABOUT propagation) ✅"* | Distortion **never compounds across hops** — `gossip_batch_queries.py:29-47` returns the canonical event summary, not the sharer's distorted one, and the gossip write overwrites seeded distortion back to 0 (CR-L01-01, CR-L01-02, both Confirmed). The 2-hop chain in the pitch is **hand-seeded**. The buyer is watching a fixture, narrated as an engine. |
| **2** | `README.md:56-71` requires every published rate to carry a machine-checked citation; the guard rate is the number the anti-hallucination story rests on | A **null responder emitting one fixed string scores 0.949 on the guard battery vs the engine's 0.897** (CR-L03-01, Confirmed). The number the product is sold on is not a measurement of the product. Two of four scorers are REFUSED by the project's own policy; not one has a κ interval excluding chance (CR-L03). |
| **3** | `docs/DEMO_SCRIPT.md:185-187` — *"This is middleware. Studio integration is a single API call. The knowledge graph, five engines, and streaming dialogue license as a bundle."* `BUSINESS_REQUIREMENTS.md:11` — *"designed as a plugin for both Unity and Unreal Engine games."* | **148 operations across 132 live paths**, six of them undocumented; **zero lines of C# or C++** in the tree; **no plugin, no SDK, no sample scene**; and the only packaging artifact has never been buildable (CR-L12-02). "A single API call" and "a plugin" are both untrue of the artifact as it stands. |

---

### 4. Non-functional requirements vs. reality

Targets from `docs/BUSINESS_REQUIREMENTS.md:34-38`. These five strings appear **nowhere else in the
tree except archived intent docs** — `grep -rniE "pairs/tick|10,?000 nodes|99\.5"` over all `.py`/`.md`
returns only `BUSINESS_REQUIREMENTS.md` and `project-harness/archive/2026-06-18-shipped-programs/`.
`git ls-files | grep -iE "bench|load_?test|locust|perf"` returns one eval **case** YAML and no benchmark.

| NFR | Target | Measured anywhere? | Ever met? |
|---|---|---|---|
| Gossip tick throughput | ≥ 200 NPC pairs / tick | **No.** No benchmark exists. The largest `max_pairs` value used anywhere in the repo — source, tests, evals, fixtures — is **20** (`gossip_handler.py:114` default; `api/routes/admin/batch.py:30` `Field(default=20, ge=1, le=500)`). The API will accept 200; nothing has ever sent it. | **Unknown, 10x untested.** |
| Knowledge graph size | ≥ 10,000 nodes | **Yes, this session, against the live seeded world:** `GET /v1/graph/nodes/{Character,Event,Location}?limit=1000` → **23 + 12 + 17 = 52 nodes**. No test or seeder in the tree creates >100 nodes (largest seeder: `src/npc_engine/data/seed_data.py`, 27 ids). | **No — 0.5% of target.** |
| Service uptime | 99.5% during active sessions | **No.** No SLO, no uptime probe, no restart history. `/v1/admin/system/metrics` counts requests in-process and resets on restart. CR-L16-07 confirms the `app` container has **no healthcheck**. | **Unmeasurable as built.** |
| LLM fallback on timeout | < 100 ms (serve canned) | **Yes, measured this session** (`get_canned_response`, `prompts/canned/merchant.yaml`, n=21): **median 0.687 ms, max 0.886 ms**. | **Met — and the metric is the wrong one.** Player-visible fallback latency is `LLM_TIMEOUT_SECONDS` (default **10.0**, `config.py:104`) **+ 0.7 ms**. The NFR measures the cheap half. |
| Test coverage | ~70% line on non-prompt code | **Yes.** `python -m coverage report` on the committed `.coverage`: `TOTAL 23789 stmts, 3405 miss, **85.7%**`. Gated at `--cov-fail-under=80` in `make test-cov`, which CI runs. | **Met.** |
| (same row) "100% pass on `make eval` (Layer 1+2)" | | See CR-L03: the instrument is invalid (CR-L03-01), two gates audit a superseded generation (CR-L03-07), and 1,522 lines of the newest gate layer are reachable from no `make` target (CR-L03-04). | **Not meaningfully assessable.** |

**Score: 1 of 5 NFRs measured and met (coverage). 1 met on a technicality that measures the wrong
half (fallback). 3 never measured, one of them 190x off.**

---

### 5. `demo_game/` — what is it for now?

**Verdict: it is not abandoned, it is not broken, and it is not a subtraction candidate. It has been
silently repurposed from sales demo into the eval program's world-fixture generator, and CI does not
run a single one of its 1,116 tests.**

Evidence it still runs (both commands executed this session):

```
$ python -m pytest demo_game/tests/ -q
1116 passed, 30 warnings in 9.28s

$ python -m demo_game.runners.run --dry-run
  === Demo complete. 12 acts. ... ===
[done] 0.0s elapsed
```

Evidence it is frozen: last **feature** commit `e975215 feat(G2.2): demo intrigue board` on
**2026-06-13 — 76 days ago**. The four commits since are `chore: restore the line endings my own edits
rewrote across P8`, a `feat(graph)` embedding change that swept it up, one `fix(demo)` restore-guard,
and a model-tag rename. 8 file-touches in 200 commits.

Evidence it is load-bearing for the *eval* program, not the sales pitch:

- `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` by running `python -m demo_game.snapshot`.
- `evals/anti_hallucination_runner.py:30` depends on "the demo-world player that `demo_game.seed` always creates."
- `tests/unit/api/test_client_paths_phase2.py:17`, `tests/unit/api/test_interaction_phase1.py:25`, and
  `tests/unit/config/test_seed_chain_quests.py:19` import from `demo_game` — and those tests run inside
  `make test-cov`, which **is** CI-gated.

Evidence it is off the revenue path: it is a **pygame** app. `BUSINESS_REQUIREMENTS.md:21-22` names
Unity (C#) and Unreal (C++) as the target clients; DEC-125 selected Unity. The revenue artifact
described in `UNREAL_DEFERRED.md:110-115` is a *different, Unity* demo game that does not exist.

Evidence it is ungated: `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0**.
`make check` (`Makefile:200`) does not include `test-demo`. 36,961 lines and 1,116 tests are verified by
nobody except a human who remembers to type `make test-demo`.

Subtraction verdict: **do not subtract it** — it is wired into the gated test suite and the eval
fixture pipeline, and it is the only working demonstration of the product that exists. The largest
genuine subtraction candidate in the repo is not code: **48,988 lines of `project-harness/` markdown,
215 of whose 246 tracked files are already under `archive/`**.

---

### 6. Is there a customer, a pilot, or a design partner?

**No. There is not, and nothing in the tree or history suggests there ever has been.**

```
$ git log --pretty=format:"%an <%ae>" | sort | uniq -c
    967 Lohann Colle <lohanncolle2022@gmail.com>
```

**967 commits, one author, zero external contributors.** `git remote -v` → one personal GitHub
remote. A tree-wide grep for `design partner|pilot customer|pilot studio|first customer|prospect|
licensee|LOI|letter of intent|NDA|contract signed|invoice|trial account|tenant` across all `.md` and
`.py` returns **zero** hits that are not in-game dialogue transcripts about bribing a gate guard.

Every occurrence of "studio" in a business sense is either aspirational pitch copy
(`docs/DEMO_SCRIPT.md:187`) or lives in `project-harness/archive/2026-06-18-shipped-programs/`, i.e.
it was archived 71 days ago. There is one reference to a "Munich demo"
(`archive/.../briefs/EXP-12-relation-delta-audit-log.md:8`) — a hackathon, not an integrator.

**Why this changes the rest of the review:** with no integrator, nothing in this repo has an external
deadline or an external definition of "done." That is the mechanism behind CR-L07-05 (roadmap
completion diverging), CR-L10-06 (30% of commits are pure process bookkeeping), and CR-L10-07
(loop-driven velocity). The eval harness is the only thing supplying a success criterion, which is
precisely why the tree has spent eight weeks growing one — and why CR-L03-01 (the harness's own
headline is beaten by a fixed string) is the most expensive defect in the repository.

---

## Findings

### [CR-L12-01] Restore one product program to `ROADMAP.md`, or state in writing that the product is paused

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `project-harness/UNREAL_DEFERRED.md:3-7` moved all 12 game-client items out of the roadmap on 2026-07-31 "because the active program is the eval pipeline"; `packaging/` has had **0 commits in the last 8 weeks and 1 file-touch in 200 commits** since. All 8 `## Active`/`## Program` headings in `ROADMAP.md` (lines 39, 122, 1120, 1600, 3449, 3540, 3616, 3639) are eval or harness meta-work; **zero** are product. 76% of 233 commit subjects in the last 8 weeks are eval/harness-scoped; 14% touch engine code; 4 commits touch `demo_game`.
- **Cost of inaction:** The measuring instrument keeps improving and the thing being measured does not. Concretely: by the time Programs 4 and 5 (EVAL-P25..P31) land, the engine will still have a no-op signature feature (CR-L01-01), no client SDK, and no buildable artifact — and another ~8 weeks of the only engineer's time will be spent. The failure is silent because no external party is waiting.
- **Fix sketch:** Pick one: either move `SHIP-06` (the one legible emergent hook, end-to-end) back into `ROADMAP.md` above the loop fence and let the loop starve until it lands, or add an explicit `## Paused — product` heading to `ROADMAP.md` saying the B2B track is deliberately stopped and naming the resume condition. The current state — deferred in a side file the loop cannot see — is the worst of both.
- **Effort:** S (the decision) / XL (the work it unblocks)
- **Removes:** 0 lines
- **Blast radius:** `ROADMAP.md`, `UNREAL_DEFERRED.md`, the `roadmap_cursor.py --verify` span, a DECISIONS entry.

### [CR-L12-02] `make package` has never been buildable — the PyInstaller spec references two paths that have never existed

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `packaging/npc_engine.spec:29-30` lists `datas` entries `(str(REPO_ROOT / "config"), "config")` and `(str(REPO_ROOT / "game_schema.yaml"), ".")`.
  ```
  $ python -c "from pathlib import Path; R=Path('.').resolve(); [print(p, p.exists()) for p in (R/'src/npc_engine/prompts', R/'config', R/'game_schema.yaml')]"
  ...\src\npc_engine\prompts  True
  ...\config                  False
  ...\game_schema.yaml        False
  ```
  Not merely stale — they were **already absent at the spec's own introducing commit**:
  ```
  $ git ls-tree 54e3a19 --name-only | grep -E "^(config|game_schema.yaml)$"    → (empty)
  $ git log --all --oneline -- game_schema.yaml                                → (empty; the file has only ever lived at src/npc_engine/game_schema.yaml)
  ```
  PyInstaller is absent from `pyproject.toml:24-30` `[dev]` and from the venv (`ModuleNotFoundError: No module named 'PyInstaller'`). No CI job runs `make package` (`grep -c package .github/workflows/ci.yml` → 0). `dist/` is not even in `.gitignore` — the target has never produced output.
- **Cost of inaction:** The entire distribution story — DEC-128, SHIP-04, and `docs/INTEGRATION.md:12-18`'s "game.exe spawns launcher.exe" — is documented, decided, and non-existent. The day a studio asks for a build, there is nothing to send and the first attempt to make one fails on a two-month-old path error. This is the cheapest-to-fix item that blocks a pilot outright.
- **Fix sketch:** Repoint the two `datas` entries at `src/npc_engine/config` and `src/npc_engine/game_schema.yaml`, add `pyinstaller` to a `[project.optional-dependencies] package` extra, and add one CI job that runs `make package` and asserts the binary starts and answers `GET /health`. Note the launcher binds **8080** (`stack_launcher.py:37`) while every make target, eval and doc example uses **8000** — the packaged path has never been exercised end to end.
- **Effort:** M
- **Removes:** 0 lines / 0 files (adds ~15 lines of CI)
- **Blast radius:** `packaging/npc_engine.spec`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`; `docs/INTEGRATION.md` §1 if the port is unified.

### [CR-L12-03] Ship a thin Unity C# client, or stop naming Unity and Unreal as target clients

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `docs/BUSINESS_REQUIREMENTS.md:19-23` tabulates Unity (C#) and Unreal (C++) as the two target clients. `git ls-files | grep -icE '\.(cs|cpp|h|hpp|uplugin|asmdef)$'` → **0**. All four SDK steps are unchecked and deferred (`UNREAL_DEFERRED.md:63-65`: SX.1 OpenAPI freeze, SX.2 Unity C# package, SX.3 Unreal plugin, SX.4 sample scenes). The only client in the tree is `demo_game/` — 36,961 lines of **pygame**, which is neither.
- **Cost of inaction:** Every hour spent on eval rigour is spent on a claim ("NPCs that remember") that a studio cannot evaluate without first writing the HTTP client, the WS reconnect logic, the auth header handling and the model bindings themselves — against a 148-operation surface with no frozen contract (CR-L12-07). The pitch line `docs/DEMO_SCRIPT.md:187` "Studio integration is a single API call" is false today and will read as a bluff in the first technical call.
- **Fix sketch:** SX.2 as a deliberately minimal slice: one C# file wrapping `POST /v1/dialogue`, `GET /v1/npc/{id}/state` and `POST /v1/clock/advance`, with the `ErrorEnvelope` shape and a bearer header — not the full surface. That is the smallest artifact that makes the "plugin" claim non-fiction.
- **Effort:** L
- **Removes:** 0 lines
- **Blast radius:** New top-level `sdk/` tree; `docs/INTEGRATION.md`; forces SX.1 (contract freeze) to at least a versioned snapshot.

### [CR-L12-04] The pitch narrates a hand-seeded fixture as a working engine

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `docs/DEMO_SCRIPT.md:147` — *"tells Henryk. Each hop introduces deterministic distortion."*; `:109` — *"One hop later. Faction name already garbled — the distortion engine ran."*; `:161` — *"The engine tracked every distortion hop."*; `README.md:16` marks the gossip engine ✅; `docs/ENGINES.md:102` advertises "deterministic distortion (omission, exaggeration, role-swap, timeline-shift) … Fully reproducible (seeded)." CR-L01-01 and CR-L01-02 are both Confirmed: `gossip_batch_queries.py:29-47` returns the canonical event summary rather than the sharer's distorted one, so distortion cannot compound, and the gossip write overwrites seeded distortion back to 0. The `captain_sorn → mira_innkeeper → old_henryk` chain in the script is hand-seeded (`project-harness/CLAUDE.md`, demo-world table).
- **Cost of inaction:** This is the one demo moment a buyer will try to reproduce on their own world, and it is the first thing that will fail. The reputational cost of a narrated fixture is categorically worse than the cost of a missing feature — it converts a gap into a credibility question about every other ✅ in `README.md`.
- **Fix sketch:** Until CR-L01-01 lands, change `DEMO_SCRIPT.md:147/161` to state that the two-hop chain is seeded illustration, not live propagation. After it lands, revert. Do not run the demo for an external audience in between.
- **Effort:** S (the doc honesty) / M (CR-L01-01 itself)
- **Removes:** 0 lines
- **Blast radius:** `docs/DEMO_SCRIPT.md`, `docs/ENGINES.md:102`, `README.md:16`; overlaps CR-L01-01/02 remediation.

### [CR-L12-05] Four of five NFRs have never been measured; the graph target is off by 190x and the throughput target is 10x untested

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `docs/BUSINESS_REQUIREMENTS.md:34-38`. The five target strings occur nowhere else in the tree except `project-harness/archive/2026-06-18-shipped-programs/`. No benchmark file exists (`git ls-files | grep -iE "bench|load_?test|locust|perf"` → one eval **case** YAML). Live graph measured this session: **52 nodes** (23 Character + 12 Event + 17 Location) against a **≥10,000** target. Largest `max_pairs` value used anywhere in source, tests, evals or fixtures: **20** (`gossip_handler.py:114`, `api/routes/admin/batch.py:30`), against a **≥200 pairs/tick** target. No uptime telemetry exists and the `app` container has no healthcheck (CR-L16-07). Coverage is the one target genuinely met: `coverage report` → `TOTAL 23789 3405 85.7%`, gated at 80% in CI.
- **Cost of inaction:** The first pilot world will be an order of magnitude larger than anything ever run. Failure modes at 10k nodes — Cypher plan degradation in `select_pairs`, the in-process `emotion_store`/`session_store` singletons (CR-L02-03), the in-memory rate-limit buckets, the token budget guard frozen against constants measured on a 52-node world (CR-L01-07) — are all unmeasured. These surface during the pilot, not before it.
- **Fix sketch:** One script that seeds N synthetic characters/events/locations and runs a single gossip tick at `max_pairs=200`, reporting wall-clock and Neo4j round-trips at N ∈ {100, 1000, 10000}. That is the whole gap — it is a script, not a program. Then either record the real numbers in `BUSINESS_REQUIREMENTS.md` or restate the targets to what the engine actually does.
- **Effort:** M
- **Removes:** 0 lines
- **Blast radius:** New `scripts/` benchmark; `docs/BUSINESS_REQUIREMENTS.md:34-38`; likely surfaces graph-layer work.

### [CR-L12-06] There is no integrator, and nothing in the repo supplies an external definition of "done"

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `git log --pretty="%an <%ae>" | sort | uniq -c` → **967 Lohann Colle**, single author, zero external contributors. `git remote -v` → one personal GitHub remote. A tree-wide grep for `design partner|pilot customer|pilot studio|first customer|prospect|licensee|LOI|letter of intent|NDA|contract signed|invoice|trial account|tenant` across `*.md` and `*.py` returns zero business hits. Every business-sense "studio" reference is either pitch copy (`docs/DEMO_SCRIPT.md:187`) or lives in `project-harness/archive/2026-06-18-shipped-programs/`, archived 71 days ago.
- **Cost of inaction:** Already being paid. With no external clock, "done" is defined by the harness, and the harness is the thing being built — CR-L07-05 (roadmap completion diverging), CR-L10-06 (30% of the commit stream is process bookkeeping), CR-L10-07 (loop-driven velocity causing fix-of-fix). Each additional eval program deepens the loop rather than closing it.
- **Fix sketch:** Human decision, not an engineering task. Name one external party — a jam team, a solo Unity dev, a friend's studio — who will attempt an integration against a fixed date. That single constraint reprioritises CR-L12-02, CR-L12-03 and CR-L12-05 automatically and makes CR-L12-01 answer itself.
- **Effort:** S (to decide) / L (to serve)
- **Removes:** 0 lines
- **Blast radius:** The whole roadmap.

### [CR-L12-07] The HTTP contract has 148 operations and one sentence of stability policy

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Live `openapi.json` this session: **148 operations across 132 paths**. The complete stability policy in the repo is `docs/INTEGRATION.md:6`: *"Routes and shapes may evolve; breaking changes will be announced."* No deprecation window, no `/v2` scheme, no contract test against a published spec. SX.1 (OpenAPI contract freeze) is unchecked in `UNREAL_DEFERRED.md:63`. The root `live_openapi.json` snapshot is 64 days stale (CR-L13-11) and `docs/API.md` is missing 6 live routes (CR-L13-09, re-confirmed here: `/setup/config`, `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/factions/{}/standings/{}`, `/v1/admin/schedules/character/{}/at`, `/v1/admin/vector-store/rehydrate`). The generic node-list endpoint returns no `total` in `meta` (`GET /v1/graph/nodes/Character?limit=1` → `{"limit":1,"offset":0,"sort":"id:asc","strategy":"offset"}`), so a client cannot size a paginated read without walking it.
- **Cost of inaction:** Any client written today — the SDK of CR-L12-03 included — is written against a moving target with no signal when it moves. The first integrator upgrade breaks silently.
- **Fix sketch:** Regenerate `live_openapi.json` in CI on every push and fail the build when it changes without a `CHANGELOG.md` entry. That is SX.1's cheap 80%, and it costs one CI step rather than a program.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** `.github/workflows/ci.yml`, `live_openapi.json`, `CHANGELOG.md` (already 96 commits stale — CR-L13-08).

### [CR-L12-08] `demo_game/`'s 1,116 tests are gated by nothing, while gated code imports it

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0**. `make check` (`Makefile:200`) omits `test-demo`. Yet `tests/unit/api/test_client_paths_phase2.py:17`, `tests/unit/api/test_interaction_phase1.py:25` and `tests/unit/config/test_seed_chain_quests.py:19` import `demo_game.client` / `demo_game.dialogue` / `demo_game.seeds.seed`, and those files run inside `make test-cov`, which **is** CI-gated. `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` from `python -m demo_game.snapshot`, and `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` creates. Run by hand this session: `1116 passed in 9.28s`; `python -m demo_game.runners.run --dry-run` completes 12 acts.
- **Cost of inaction:** 36,961 lines whose failure mode is silent. A `demo_game` regression breaks the eval baseline fixture and three CI-gated unit tests, and the first symptom will be an unexplained eval number rather than a red demo test. The most likely trigger is the `chore: restore the line endings my own edits rewrote across P8` class of sweep-up commit, which already accounts for half of `demo_game`'s recent churn.
- **Fix sketch:** Add `test-demo` to the CI test job (9 seconds) and to `make check`. If `demo_game` is genuinely not worth gating, then move `snapshot.py`, `client.py`, `dialogue.py` and `seeds/` out of it into a small `fixtures/` package that *is* gated, and let the pygame UI rot honestly.
- **Effort:** S (CI) / M (the extraction)
- **Removes:** 0 lines (or ~30,000 lines of pygame UI moved off the gated path, if the extraction is chosen)
- **Blast radius:** `.github/workflows/ci.yml`, `Makefile:200`; the extraction would touch `evals/fixtures`, three `tests/unit` files and 12 Makefile targets.

### [CR-L12-09] The engine package cannot be imported except in one undocumented order

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** Executed this session with `PYTHONPATH=src`:
  ```
  OK  npc_engine.retrieval.dialogue_context
  OK  npc_engine.main
  ImportError: cannot import name 'build_serialized_context_with_receipt' from partially
    initialized module 'npc_engine.retrieval.context.context_builder'
    (most likely due to a circular import)          ← npc_engine.engines.dialogue.degradation
  ImportError: (same)                               ← npc_engine.retrieval.context
  ```
  The cycle is `retrieval/context/__init__.py:46` → `context_builder.py:80` → `retrieval/dialogue_context/__init__.py:13` → `dialogue_context_adapter.py:21` → back into `context_builder`. It resolves only if `npc_engine.retrieval.dialogue_context` is imported first, which `npc_engine.main` happens to do.
- **Cost of inaction:** Anyone embedding the engine as a library rather than a server — which is what `scripts/launcher.py` and the PyInstaller path do, and what an in-process integration would do — hits an ImportError whose message names neither the real cause nor the workaround. It also makes any targeted unit-level import of `engines/dialogue` fragile, which is why the fallback-latency measurement in §4 needed a manual pre-import.
- **Fix sketch:** Move the `dialogue_context_adapter` import in `context_builder.py:80` under `TYPE_CHECKING` or into the function body — CLAUDE.md already mandates `TYPE_CHECKING` blocks for cycle resolution.
- **Effort:** S
- **Removes:** ~0 lines
- **Blast radius:** `retrieval/context/context_builder.py`, `retrieval/dialogue_context/dialogue_context_adapter.py`; import-order assumptions in `main.py` and `api/dependencies.py`.

---

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| CRITICAL | 0 | — (the CRITICALs bearing on this lens are CR-L01-01, CR-L01-02, CR-L03-01) |
| HIGH | 6 | CR-L12-01 … CR-L12-06 |
| MEDIUM | 3 | CR-L12-07, CR-L12-08, CR-L12-09 |
| LOW | 0 | — |

**Note on the ceiling.** CR-L12-02 (`make package` has never been buildable, on any commit, since the
day the spec was written) is the finding I would have raised to CRITICAL had the budget allowed: it is
a Confirmed defect, in the shipping path, in the only artifact a studio would ever receive.

## Method notes

- All live-API probes were reads. No gossip tick, event tick, clock advance, seed or write of any kind
  was issued; the ≥200-pairs/tick target was therefore assessed from the largest value ever used in the
  tree rather than by running one, per the read-only constraint.
- LOC figures are tracked files only (`git ls-files`), matching the corrected split in the brief;
  `demo_game` re-measured at exactly 36,961.
- The last-200-commit churn table was reproduced independently (`git log -n 200 --no-merges`, per-file
  `git show --name-only`) and matches the brief's figures to within rounding (288/393/322/172/8).

---

## L11 — Process-to-output ratio

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

---

## L14 — Agent-authored code smells

> **Orchestrator note — two hypotheses disproven, and one result that outranks
> its own severity label.**
>
> L14 was commissioned to confirm six suspected agent-authored smells. It
> **disproved two of them**, and those negative results are load-bearing for §C:
> vacuous docstrings are not the problem (12 of 1,551 add zero words — 0.8%), and
> the 300-line rule did **not** cause file fragmentation (median file 88 lines;
> only 28 of 627 sit in the 250–299 band). This independently corroborates L4's
> census. **The 300-line rule is exonerated by two lenses and should be kept.**
> The real cause of the file count is the DIP-strict Protocol rule.
>
> CR-L14-02 is filed HIGH. Its *evidence* is the strongest single item in this
> review and it drives §C's central pattern, so it is quoted here in the summary
> rather than left in the lens body. L14 executed the counterfactual on scratch
> copies: it gutted **105 of 180 repository methods** to return constant empty
> values. Result — `mypy` stayed clean, and exactly **66 tests failed, every one
> of them the repository layer's own `*_delegates` passthrough tests**. Zero
> engine tests, zero API tests, zero scheduler tests, zero conformance tests
> noticed that the graph read layer had stopped returning data.
>
> The reason is the second half: the 183 Cypher functions are covered only by
> `tests/integration`, which without `NEO4J_URI` reports `9 passed, 34 skipped` —
> and that is exactly what `make check` runs. So the graph read layer can be
> replaced with stubs and the full 14-gate battery, 4,048 tests and 87.86%
> coverage all stay green.
>
> A second executed counterfactual: renaming `MilitaryEngine.run_tick` to take
> `at_tick=` while the scheduler calls `run_tick(tick_id=...)` yields
> `mypy: Success, no issues in 627 files`.

# CR-L14 — Agent-authored code smells

**Lens:** L14 of 16. **Tree:** `eval-ab-context-arms` @ d46ae42. **Mode:** read-only.

**Method note:** all counterfactuals were executed against a full copy of the tree at
`<scratchpad>/cf` (src + tests + demo_game + evals + scripts + seeds). The working tree
was never modified. Baseline in that copy: `3997 passed, 37 failed` (the 37 are copy
artifacts — tests that read `project-harness/` paths not copied), and
`mypy src/` → `Success: no issues found in 627 source files`.

---

## Required measurements

| # | Category | Count | Method |
|---|---|---|---|
| 1 | Abstraction introduced only to satisfy a rule | **45 Protocols** — 44 in `engines/ports/` (40 files, **2088 lines**, 169 method declarations) + `BaseEngine`. **14** have exactly one caller; **10** declare exactly one method; **4** are both. `BaseEngine` is `(*args, **kwargs)` and enforces nothing (proven, CR-L14-04). | AST: extracted every `class X(Protocol)` in `engines/ports/`, then per port counted (a) implementor files under `graph/`, (b) referencing files outside `ports/` and `graph/`, (c) declared methods. Full table in Appendix A. |
| 2 | Tests that assert a constant / would pass with the feature deleted | **15** Confirmed tautologies (`*session_kwarg*`, feature already deleted, all pass — CR-L14-01); **127** passthrough-echo tests (`*_delegates`, `*_opens_one_session`, **1600 lines**) that patch the callee and assert the mock's own return value; **48** tests asserting `==` against a value they set as `return_value`; **47** zero-call zero-fixture tests (of which **12** are pure `CONST == literal`); **23** tests with no assertion of any kind; **18** tests asserting a string literal is `in` an ALLCAPS constant. Sets overlap; union approx **210** of 3857. | Six AST detectors over all 3857 test functions in `tests/`, plus one executed counterfactual (105 source methods gutted) and one direct execution proof. |
| 3 | Docstrings that restate the signature | **Sample = 1551** documented public functions in `src/npc_engine/` (of 1582 total; **31 have no docstring at all** despite the "mandatory" rule). Adding **0** new content words: **12 (0.8%)**. **<=1**: **88 (5.7%)**. **<=2**: **280 (18%)**. **Hypothesis largely disproven** — see CR-L14-07. The real docstring defect is **49 lines that document a parameter or signature that does not exist**. | AST: for each public function, tokenised the docstring summary and subtracted the token set derivable from the function name + parameter names + return annotation (stop-worded). Reported at three thresholds. |
| 4 | Logic scattered across files to respect the 300-line limit | **Disproven as stated.** Median `src/` file = **88 lines**; mean 108; only **28 of 627** files sit in the 250–299 band and **13 already exceed 300**. Files are not clustered against the cap. The fragmentation driver is a *different* rule — DIP-strict + the DEC-122/SEV-24 ports/repositories seam. Worst real cluster: **story_pacing, 5 files / ~610 lines for 2 Cypher queries** (chain traced in CR-L14-03). | `wc -l` over all 627 `src/` files, band histogram; then an end-to-end call-chain trace of one operation. |
| 5 | Near-duplicate helpers in sibling modules | **7** exact AST-shape clone families (19 functions) spanning 2+ different files. Semantic families are far larger: **175** copies of the `await connect(); async with get_session()` preamble across **38** repository files; **3** copies of the Neo4j→native recursive converter **with divergent error paths** (CR-L14-05). | Normalised every function body >=4 statements (names/attrs/constants/args erased), MD5-hashed the AST dump, grouped across files; plus targeted grep for the session preamble. |
| 6 | Defensive try/except around internal invariants | **84** `try` blocks in `src/` whose body calls an `npc_engine`-internal symbol; **17** of those catch bare `Exception`/`BaseException`; **3** swallow with neither a log nor a re-raise. | AST: for each `ast.Try`, resolved every call in the body against (a) names imported from `npc_engine.*` in that module and (b) top-level definitions in the same module; classified handlers. |

---

## Worst 10 overall

| # | file:line | What |
|---|---|---|
| 1 | `tests/unit/engines/test_military_engine.py:109` | `test_run_tick_ignores_scheduler_session_kwarg` — never passes `session=`; the `**_` it guards was deleted; passes anyway. x15 across the suite. |
| 2 | `src/npc_engine/engines/military/military_engine.py:34` | `run_tick` docstring documents a `**_` parameter absent from the signature. x22 engine files, 0 with a real `**kwargs`. |
| 3 | `src/npc_engine/scheduler/tick_scheduler.py:96` | 27 docstring lines promise `run_tick(session, tick_id)`; 0 of 30 engines accept a session. |
| 4 | `tests/unit/graph/test_story_pacing_repository.py:30` | Patches `get_active_high_severity_quests` with `AsyncMock(return_value=rows)`, then `assert result == rows`. x127 tests / 1600 lines. |
| 5 | `src/npc_engine/graph/repositories/story_pacing_repository.py:41` | 3-line passthrough. 117 of 180 repository methods (65%) are identical in shape; gutting 105 of them broke only their own delegate tests. |
| 6 | `src/npc_engine/engines/base_engine.py:24` | `async def run_tick(self, *args: Any, **kwargs: Any)` — types 33 scheduler parameters, enforces no signature. mypy stays clean with an incompatible engine wired in (executed). |
| 7 | `src/npc_engine/retrieval/context/context_builder_helpers.py:41` | `except Exception: return str(value)` around a recursive call to itself. Third copy of the converter; **error path diverges** from the other two. |
| 8 | `src/npc_engine/graph/graph_reader.py:212` | `except Exception: return value` — same helper, same silent swallow, different fallback. |
| 9 | `src/npc_engine/engines/ports/trait_read_port.py:17` | 1-method Protocol, **zero** implementors in `graph/`, one optional caller. |
| 10 | `tests/unit/engines/test_dialogue_models.py:33` | `assert MAX_PLAYER_MESSAGE_CHARS == 1000` — restates the constant's own definition. |

---

## Findings

### [CR-L14-01] Delete the 15 `session_kwarg` tests and the 49 docstring lines describing a parameter that no longer exists

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** The SEV-24 migration removed the `session=` kwarg from every tick engine. The tests and docstrings that guard it were not removed, and they still pass.

  ```
  $ PYTHONPATH=src python -c "...inspect.signature(MilitaryEngine.run_tick)..."
  MilitaryEngine.run_tick signature: (self, *, tick_id: 'int') -> 'dict[str, Any]'
  has **kwargs: False
  bind(session=..., tick_id=...) -> TypeError: got an unexpected keyword argument 'session'

  $ python -m pytest "tests/unit/engines/test_military_engine.py::test_run_tick_ignores_scheduler_session_kwarg" -q
  1 passed, 30 warnings in 0.16s
  ```

  That test's docstring reads *"run_tick accepts and ignores the scheduler's session= kwarg (SEV-24)."* It passes because it never passes `session=`. AST sweep of all 15 such tests: **`tests that DO pass session= to run_tick: 0`** — every one is a tautology. Files: `test_faction_politics_engine.py:222`, `test_goal_former_adapter.py:125`, `test_gossip_n_plus_one.py:170`, `test_intent_formation_engine.py:59`, `test_military_engine.py:109`, `test_mood_contagion_engine.py:111`, `test_need_decay_engine.py:124`, `test_proactive_tick_adapter.py:247`, `test_reputation_engine.py:193`, `test_routine_engine.py:93`, `test_skill_progression_engine.py:61`, `test_story_pacing_engine.py:114`, `test_succession_engine.py:81`, `tests/unit/graph/test_event_handler_port.py:113`, `tests/unit/graph/test_player_model_tick.py:91`.

  The same sweep over `src/`: **22 `run_tick` docstrings document `**_`, and 0 of them have a `**kwargs` in the signature** — `agenda_engine.py:46`, `intent_formation_engine.py:60`, `chapter_engine.py:107`, `clique_formation_engine.py:53`, `faction_politics_engine.py:52`, `gossip_handler.py:110`, `memory_decay_tick.py:40`, `military_engine.py:34`, `mood_contagion_engine.py:80`, `need_decay_engine.py:50`, `oath_engine.py:35`, `goal_former_adapter.py:73`, `player_model_tick.py:64`, `proactive_tick_adapter.py:86`, `reputation_engine.py:78`, `reputation_tick_adapter.py:76`, `routine_engine.py:46`, `scheme_advance_tick.py:63`, `skill_progression_engine.py:42`, `story_pacing_engine.py:57`, `succession_engine.py:45`, `treaty_engine.py:36`.

  And `grep -c 'run_tick(session' src/npc_engine/scheduler/tick_scheduler.py` → **27**, against `grep -rn "async def run_tick" -A2 src/npc_engine/engines/ | grep -c session` → **0**.
- **Cost of inaction:** The next person to add a tick engine reads `tick_scheduler.py:96-134` and 22 engine docstrings, all of which state the scheduler passes a session, and writes `run_tick(self, session, *, tick_id)`. The scheduler calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`), so that engine raises `TypeError` on its first real tick — and the `BaseEngine` annotation will not catch it (CR-L14-04). This is a live trap, not latent debt.
- **Fix sketch:** Delete the 15 tests; strip the `**_:` lines from the 22 `Args:` blocks; rewrite the 27 `tick_scheduler.py` parameter docstrings to the real `run_tick(*, tick_id)` contract.
- **Effort:** S
- **Removes:** ~150 lines of tests + ~49 docstring lines
- **Blast radius:** Docstrings and tests only; no runtime behaviour changes.

### [CR-L14-02] The 127 `*_delegates` tests test only that a passthrough passes through — gutting 105 repository methods broke nothing above the repository layer

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** AST over `graph/repositories/` (39 files, 3778 lines): **117 of 180 public methods (65%)** have a body that is exactly `await self._graph_db.connect()` + `async with get_session() as s: return await <query>(s, ...)`. The `connect()+get_session()` preamble appears **175 times across 38 files**.

  The test guarding each one is `tests/unit/graph/test_story_pacing_repository.py:36-41`:

  ```python
  with patch(f"{_MOD}.get_active_high_severity_quests", new=AsyncMock(return_value=rows)) as mock_fn:
      result = await repo.get_active_high_severity_quests(threshold=70)

  assert result == rows                       # the mock's own return value
  assert db.connect_calls == 1
  mock_fn.assert_awaited_once_with(session, 70)
  ```

  It patches away the only thing that carries risk (the Cypher), then asserts the mock echoed itself.

  **Executed counterfactual:** in the tree copy I rewrote all 105 type-safely-guttable passthrough bodies to a constant empty return (`return []` / `None` / `0` / `False`).

  - `python -m mypy src/` → `Success: no issues found in 627 source files`
  - `pytest tests/unit` → `103 failed, 3931 passed` vs baseline `37 failed, 3997 passed` = **66 new failures**, and **every one is in `tests/unit/graph/test_*_repository.py` or `tests/unit/retrieval/test_proactive_memory_read_repository.py`**. Zero engine, API, scheduler, or conformance tests noticed that the entire graph read layer had started returning nothing.
  - 105 methods gutted produced 66 failures, so roughly 39 gutted methods have no test at all.

  The Cypher those repositories exist to reach — **183 query functions** in `graph/*/*queries*.py` — is exercised only by `tests/integration/`, and `pytest tests/integration -q` in the default environment prints **`9 passed, 34 skipped`** (every DB test guards on `NEO4J_URI`, e.g. `tests/integration/test_faction_integration.py:30`). `make check` → `test-cov` → `pytest tests/`, so CI runs the skipping version.
- **Cost of inaction:** Ships now. A Cypher regression — a renamed property, a dropped `WHERE`, a wrong `MERGE` — is caught by no test that runs in `make check`. 1600 lines of test are spent proving that 3-line passthroughs pass through, which reads as coverage and is not.
- **Fix sketch:** Delete the 127 delegate tests; replace the per-domain repositories with one generic `SessionPerCall` helper that wraps any query function; move the freed test budget to running `tests/integration` against a Dockerised Neo4j in `make check`.
- **Effort:** L
- **Removes:** ~1600 lines of tests + ~470 lines of passthrough bodies (~2070)
- **Blast radius:** All 44 ports, 39 repositories, and the `api/dependencies_engines/` composition root; requires Neo4j in CI to be a net gain rather than a net loss.

### [CR-L14-03] The DIP-strict ports seam costs 8565 lines and 107 files to move calls from engines to query functions

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Traced end to end, one operation — "get recent major events":

  1. `src/npc_engine/engines/story_pacing/story_pacing_engine.py:71` → `self._get_recent_major_events(tick_id)`
  2. `story_pacing_engine.py:128` → `self._story_pacing_repo.get_recent_major_events(min_tick_id=..., floor=...)`
  3. type declared at `src/npc_engine/engines/ports/story_pacing_port.py:29` (re-states the signature verbatim)
  4. concrete at `src/npc_engine/graph/repositories/story_pacing_repository.py:41` (opens a session, delegates)
  5. Cypher at `src/npc_engine/graph/narrative/story_pacing_queries.py:63`, constant at `:29`
  6. wired at `src/npc_engine/api/dependencies_engines/core.py:167-182`

  **5 files** to run one query; the whole `engines/story_pacing/` domain is 230 lines across 4 files. Aggregate cost of the seam: `engines/ports/` 40 files / **2088 lines** / 169 re-declared signatures + `graph/repositories/` 39 files / **3778 lines** + `tests/unit/graph/test_*_repository.py` 28 files / **2699 lines** = **107 files, 8565 lines**.

  The seam is *not* free of value — mypy does catch adapter drift. Executed: renaming `floor` to `severity_floor` and changing the return type on `Neo4jStoryPacingRepository.get_recent_major_events` produced

  ```
  src\npc_engine\api\dependencies_engines\core.py:182: note:     Expected:
  src\npc_engine\api\dependencies_engines\core.py:182: note:         def get_recent_major_events(self, *, min_tick_id: int, floor: int) -> Coroutine[Any, Any, list[dict[str, Any]]]
  src\npc_engine\api\dependencies_engines\core.py:182: note:     Got:
  src\npc_engine\api\dependencies_engines\core.py:182: note:         def get_recent_major_events(self, *, min_tick_id: int, severity_floor: int) -> Coroutine[Any, Any, list[str]]
  Found 1 error in 1 file (checked 627 source files)
  ```

  So the port earns its keep for *signature* conformance at the composition root. It buys nothing for *behaviour* (CR-L14-02).

  Least-justified ports — one caller, one method, and for `TraitReadPort` no implementor at all: `engines/ports/trait_read_port.py:17` (0 impl / 1 caller / 1 method), `emotion_bootstrap_port.py:19` (1/1/1), `emotion_port.py:18` (1/1/1), `player_model_port.py:18` (1/1/1), `quest_port.py:52` `QuestOfferGraphPort` (1/1/3), `quest_port.py:75` `QuestRewardGraphPort` (1/1/4), `quest_port.py:21` `QuestLifecycleGraphPort` (1/1/5), `story_pacing_port.py:20` (1/1/2), `routine_port.py:19` (1/1/4), `faction_politics_port.py:21` (1/1/4).
- **Cost of inaction:** Every new graph read costs 4 file edits and a mypy round-trip. At the observed commit rate this is the single largest recurring tax in the tree.
- **Fix sketch:** Keep ports where there is real substitution or 3+ callers (`ClockPort` 16 callers, `WorldStateGraphPort` 6, `RelationReadPort` 6, `PlayerLocationReadPort` 6); collapse the 14 one-caller ports into the engine module that consumes them, and reach the query function directly.
- **Effort:** L
- **Removes:** ~552 lines across the 10 named single-caller port files (more if the full seam goes with CR-L14-02)
- **Blast radius:** `engines/ports/__init__.py` public surface, the composition root, and the layer checker's allow-list.

### [CR-L14-04] `BaseEngine` types 33 scheduler parameters and enforces no signature — mypy stays clean with an incompatible engine

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `src/npc_engine/engines/base_engine.py:24`:

  ```python
  async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...
  ```

  Its own docstring concedes the point: *"without enforcing a specific signature, since each engine's required parameters differ."* It is nonetheless the declared type of 33 constructor parameters (`tick_scheduler.py:52-82`) and 4 helper parameters (`:342`, `:375`, `:405`, `:424`), and the scheduler always calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`, `:410`).

  **Executed counterfactual:** changed `MilitaryEngine.run_tick(self, *, tick_id: int)` to `(self, *, at_tick: int)` with an internal alias so the body still typechecks. `python -m mypy src/` → **`Success: no issues found in 627 source files`**, with a scheduler call site that would raise `TypeError` on the first military tick. The only tests that failed were `MilitaryEngine`'s own four — the safety came from the engine's unit tests, not from the protocol that exists to provide it.
- **Cost of inaction:** A new engine wired into the scheduler with a mismatched `run_tick` passes `make check` and fails at the first tick in staging. `_run_distributed_interval` catches the `TypeError` and logs `tick_engine_error` (`tick_scheduler.py:387`), so the engine silently never runs.
- **Fix sketch:** Narrow `BaseEngine.run_tick` to the signature the scheduler actually calls — `async def run_tick(self, *, tick_id: int) -> dict[str, Any]` — and give the few engines with different needs their own protocols (ISP), rather than widening the shared one to `Any`.
- **Effort:** M
- **Blast radius:** 33 `tick_scheduler.py` parameters and ~30 engine signatures; mypy will name every mismatch, which is the point.

### [CR-L14-05] Three copies of the Neo4j-to-native converter with divergent error paths, each silently swallowing around a call to itself

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** The same recursive converter exists in three layers with identical structure:

  - `src/npc_engine/graph/graph_reader.py:199` `_to_native` → `except Exception: return value`
  - `src/npc_engine/graph/generic/generic_graph_utils.py:134` `to_native` → `except Exception: return value`
  - `src/npc_engine/retrieval/context/context_builder_helpers.py:21` `to_json_safe` → `except Exception: return str(value)`

  The AST-shape scan groups the first two as an exact clone family; the third escapes exact matching *only* because of the divergent fallback. So the same Neo4j value that reaches a prompt via `context_builder` serialises as `str(value)`, and via `graph_reader` as the raw driver object.

  All three violate two strict CLAUDE.md rules at once: *"No try/except around internal invariants"* (the `try` wraps a recursive call to the function itself, on an in-memory value) and *"Never swallow errors"* (no re-raise, no log). These are 3 of the 84 internal-call `try` blocks and 3 of the 17 with a bare `Exception` handler. Companions: `src/npc_engine/engines/dialogue/session_store.py:178` (logs, does not re-raise), `src/npc_engine/engines/dialogue/degradation.py:103` and `:115` (broad `except Exception` around `increment_metric` — a metrics counter, not a boundary), `src/npc_engine/api/routes/dialogue/interaction.py:216`, `src/npc_engine/api/routes/economy/groups.py:151`, `src/npc_engine/graph/graph_writer.py:182` and `:258`, `src/npc_engine/graph/relations/relation_delta_writer.py:140`, `src/npc_engine/main.py:242`.
- **Cost of inaction:** A driver type that fails `to_native()` produces two different prompt payloads depending on the read path, with no log line anywhere. Debugging that costs a day and starts from a silent divergence.
- **Fix sketch:** Keep `generic_graph_utils.to_native` as the single implementation, delete the other two, and drop the `try` entirely — a `to_native()` that raises is a driver bug that should surface, not be papered over.
- **Effort:** S
- **Removes:** ~30 lines and 2 functions
- **Blast radius:** `graph_reader`, `context_builder_helpers`, and the `retrieval → graph` import edge.

### [CR-L14-06] 47 zero-call tests and 23 assertion-free tests, of which 12 restate a constant's own definition

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** AST over all 3857 test functions: **47** have an `assert` but make no call at all and take no fixture; **23** have no `assert`, no `pytest.raises`, no `fail()`, and no `mock.assert_*`. The purest tautologies:

  - `tests/unit/engines/test_dialogue_models.py:33` — `assert MAX_PLAYER_MESSAGE_CHARS == 1000`
  - `tests/unit/retrieval/test_sentence_encoder.py:44` — `assert EMBED_DIMENSION == 384`
  - `tests/unit/engines/test_relationship_standing.py:74` — `assert HOSTILE_MAX == -50` ... `assert ALLIED_MIN == 50`, docstring *"Band cutoffs must be exposed as named module constants (not magic numbers)"*, which is what the `import` at the top of the file already proves
  - `tests/unit/engines/test_knowledge_types.py:20` — `assert KNOWLEDGE_STATE_KNOWS == "knows"`
  - `tests/unit/conformance/test_ocp_residuals.py:117` — `assert SchemeStepKind.ADVANCE == "scheme_advance"`
  - `tests/unit/conformance/test_clock_port_conformance.py:41,46` — `assert not hasattr(ClockPort, "advance")`, asserting on the content of a Protocol declaration file

  Related family: **18** tests assert a string literal is `in` an ALLCAPS constant — e.g. `tests/unit/world/test_world_state_clock_fields.py:62` asserts `"w.tick_id = CASE WHEN" in CYPHER_MERGE_WORLD_STATE`, and `tests/unit/conformance/test_sev04_gossip_graph_layer.py:30-45` asserts `"MERGE" in CYPHER_PROPAGATE_KNOWLEDGE`. These pass whether or not the query is ever executed, and would pass if the caller were deleted — which, per CR-L14-02, is exactly the situation the repository layer is already in.
- **Cost of inaction:** Low direct harm; the cost is that these inflate the apparent test count (70 of 3857) and read as behavioural coverage to the loop that generated them, which then does not write the real test.
- **Fix sketch:** Delete the 12 constant-restating tests. Replace the 18 Cypher-substring tests with integration tests that run the query (blocked on CR-L14-02's CI Neo4j).
- **Effort:** S
- **Removes:** ~120 lines
- **Blast radius:** None.

### [CR-L14-07] The docstring mandate is enforced by a gate that never reads a function docstring — and vacuity is not the problem

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CLAUDE.md requires a docstring on *"every public function"*, *"every public class"*, and every `__init__.py`. `make check-docstrings` runs `scripts/docstring_audit.py`, whose entire contract is `_extract_module_docstring` plus a substring check for `Layer:` and `Purpose:` (`scripts/docstring_audit.py:17`, `:38`, `:44`). It never visits a `FunctionDef`. Consequently **31 public functions in `src/npc_engine/` have no docstring at all** and the gate is green.

  The vacuity hypothesis is largely **disproven**: over a sample of all **1551** documented public functions, only **12 (0.8%)** add zero content words beyond the name/params/return type, **88 (5.7%)** add <=1, **280 (18%)** add <=2. Representative of the worst: `engines/tts/mock_adapter.py:43` `def backend_name` → *"Return 'mock'."*; `engines/ports/military_port.py:39` `def set_army_strength` → *"Update the strength of an army."*; `api/routes/knowledge/beliefs.py:86` `def seed_belief` → *"Seed a new belief on a character."*

  The real docstring defect in this tree is not emptiness but **falsity** — 49 lines that describe a parameter and a call convention that do not exist (CR-L14-01). No gate can see that either.
- **Cost of inaction:** The mandate produces volume the gate cannot grade, so the gate certifies nothing while implying it certifies a lot.
- **Fix sketch:** Either extend `docstring_audit.py` to check public functions (and to fail when an `Args:` entry names a parameter absent from the signature — that one check catches all 22 of CR-L14-01), or relax the CLAUDE.md rule to "module + public class" and stop claiming per-function coverage.
- **Effort:** S
- **Blast radius:** `scripts/docstring_audit.py` and `make check`; extending it will fail the build on 31 files until they are fixed.

---

## CLAUDE.md rules to change

These smells are consequences of the rules, not deviations from them. Changing the rule is worth more than fixing the instances.

1. **"DIP (strict): engines import `LLMClientProtocol`, never `MistralAdapter`... All concrete dependencies injected via `__init__`."** — Read as "every graph read needs a Protocol", it produced 44 ports / 2088 lines / 169 re-declared signatures, 14 of them with a single caller and 10 with a single method. **Change to:** require a Protocol only where there are 2+ implementors or 3+ callers, or a declared intent to substitute. Single-caller graph reads call the query function directly.
2. **"ISP (strict): protocols must be small."** — Combined with SRP-strict it produced 40 port files averaging 52 lines. `BaseEngine` shows the failure mode from the other side: when one protocol *must* cover 33 call sites, "small" became `(*args, **kwargs)`, which is not a contract. **Change to:** protocols must be *precise*; `Any`-typed varargs in a Protocol are a rule violation, not a compromise.
3. **"Hard limit: 300 lines of non-test code per file."** — **Keep it.** The data does not support blaming it: median file is 88 lines and only 28 of 627 sit in the 250–299 band. It is not what fragmented this tree; rules 1 and 2 are.
4. **"Every public function has a docstring."** — Unenforceable by the gate that claims to enforce it (CR-L14-07), and the failure mode it produced is stale docstrings, not missing ones. **Change to:** add "an `Args:` entry must name a parameter that exists in the signature" and make `docstring_audit.py` check it. That single rule would have caught all 22 phantom `**_` blocks and the 27 `tick_scheduler.py` lines.
5. **"No try/except around internal invariants" / "Never swallow errors."** — Correctly stated, unenforced: 84 internal-call `try` blocks, 17 with bare `Exception`. `tests/unit/conformance/test_error_swallowing_sev18.py` exists but did not stop any of the three in CR-L14-05. **Change:** nothing in the rule; add the AST check to `make check`.

**Total proposed for deletion: ~4,320 lines** at the full-seam ceiling. Conservative floor, excluding the full ports/repositories collapse: **~2,970 lines** — 1600 (delegate tests) + 552 (single-caller ports) + 470 (passthrough bodies) + 150 (session-kwarg tests) + 120 (constant tests) + 49 (false docstring lines) + 30 (duplicate converters).

---

## Appendix A — ports: implementors x callers x methods

`IMPL` counts files under `graph/` naming the port (2 = the repository plus `repositories/__init__.py`, i.e. one real implementor). `CALLERS` counts files outside `ports/` and `graph/`.

| Port | IMPL | CALLERS | METHODS |
|---|---|---|---|
| TraitReadPort | 0 | 1 | 1 |
| DialogueContextPort | 0 | 3 | 1 |
| ClockPort | 0 | 16 | 1 |
| QuestLifecycleGraphPort | 1 | 1 | 5 |
| QuestOfferGraphPort | 1 | 1 | 3 |
| QuestRewardGraphPort | 1 | 1 | 4 |
| QuestChainGraphPort | 1 | 2 | 3 |
| EmotionBootstrapGraphPort | 2 | 1 | 1 |
| EmotionGraphPort | 2 | 1 | 1 |
| FactionPoliticsGraphPort | 2 | 1 | 4 |
| InvestigationGraphPort | 2 | 1 | 6 |
| MemoryGraphPort | 2 | 1 | 3 |
| NeedTriggerGraphPort | 2 | 1 | 2 |
| PlayerModelGraphPort | 2 | 1 | 1 |
| RoutineGraphPort | 2 | 1 | 4 |
| StoryPacingGraphPort | 2 | 1 | 2 |
| EventGraphPort | 5 | 1 | 5 |
| ChapterGraphPort | 2 | 2 | 9 |
| CharacterReadPort | 2 | 2 | 1 |
| EconomyGraphPort | 2 | 2 | 6 |
| EventTriggerGraphPort | 2 | 2 | 3 |
| GroupGraphPort | 2 | 2 | 6 |
| MemoryConsolidationGraphPort | 2 | 2 | 4 |
| MoodGraphPort | 2 | 2 | 3 |
| NeedGraphPort | 2 | 2 | 2 |
| PledgeGraphPort | 2 | 2 | 4 |
| ProactiveMemoryReadPort | 2 | 2 | 1 |
| QuestGenerationGraphPort | 2 | 2 | 10 |
| RelationPhaseWritePort | 2 | 2 | 1 |
| ReputationGraphPort | 2 | 2 | 1 |
| TreatyGraphPort | 2 | 2 | 4 |
| DialogueGraphPort | 2 | 3 | 5 |
| GossipGraphPort | 2 | 3 | 10 |
| IntentGraphPort | 2 | 3 | 7 |
| KnowledgeGraphPort | 5 | 3 | 2 |
| PoliticalGraphPort | 2 | 3 | 6 |
| SchemingGraphPort | 2 | 3 | 8 |
| SkillGraphPort | 2 | 3 | 2 |
| InteractionGraphPort | 2 | 4 | 7 |
| PlanningGraphPort | 2 | 4 | 5 |
| MilitaryGraphPort | 2 | 5 | 9 |
| PlayerLocationReadPort | 2 | 6 | 2 |
| RelationReadPort | 2 | 6 | 2 |
| WorldStateGraphPort | 2 | 6 | 2 |

---

## L9 — Simplicity / subtraction

# CR-L09 — Simplicity / subtraction

Lens L9, dispatched last. Branch `eval-ab-context-arms`, HEAD `d46ae42`, 2026-08-28. Read-only —
the only file written is this one. Fifteen lenses have reported; their measurements are the raw
material here and are **cited, not re-derived**. Every row marked **delete now** was re-verified
this session with a command whose output is pasted or summarised below.

**The ledger is the deliverable.** It is the one artifact this review builds toward, and it is a
*proposal*: CLAUDE.md forbids deleting a file you did not create without human approval, so every
row is written to be actionable by one person in one sitting.

---

## 0. Verification pass (what I re-ran, and where the siblings' numbers moved)

| Claim | Sibling | Re-measured here | Verdict |
|---|---|---|---|
| 175 unreferenced archive files / 16,724 lines | CR-L11-07 | **177 files / 17,699 lines** (basename cross-reference over every tracked `.md/.py/.yaml/.txt/.ps1/.sh/.json/.toml` outside `archive/` and `review-2026-08/`) | Confirmed, **larger** than claimed |
| `scan_fix_diff.py` can be deleted outright | CR-L11-02 | **False.** `scripts/expand_loop.sh:387` invokes it; `tests/unit/harness/test_loop_gates.py:26` imports it | **Corrected** — it is loop machinery, not a standalone orphan |
| 14 session prompts / 3,463 lines | CR-L11-08 | 14 files / **3,463 lines** exactly; but `ROADMAP.md:3077,3452` links **2** of them (`PROMPT_P23_UNBLOCK.md`, `EVAL_P25_TO_P31_PLAN.md`) | Confirmed; deletable set is **12 files / 2,791 lines** |
| `engines/deception/` has zero external importers | CR-L01-12 | Confirmed — only its own `__init__.py` and `tests/unit/engines/test_deception_engine.py:35` | Confirmed |
| `engines/currency/` is an empty namespace | CR-L01-12 | Confirmed — `__init__.py` only, 12 lines, docstring still reads `Public surface: (list re-exports here)` | Confirmed |
| `live_openapi.json` has no consumers | CR-L08-09 | Confirmed — **zero** hits in `*.py`, `*.yml`, `Makefile`, `*.sh`, `*.ps1`; markdown-only mentions | Confirmed |
| 15 `session_kwarg` tautology tests | CR-L14-01 | Confirmed — 15 test functions, and `grep -rn "run_tick(session" tests/` → **0** | Confirmed |
| `check-base-rate` / `check-engine-coverage` have no `make` target | CR-L03-04, CR-L11-02 | Confirmed — both `MISSING`; **but both have live 227/234-line test files that run inside `make test-cov`** | Confirmed, with a material addition |
| Sequence subsystem is isolated | CR-L03-12 | **Partly false** — `evals/__main__.py`, `scenario_adapters.py`, `world_map.py`, `reset_fidelity_record.py` and two `e2e/scripts/` reference it | **Corrected** — requires unwiring, not a clean cut |
| 7 dead `verify-v13`/`verify-v14-p*` Makefile aggregates | CR-L06 §6 | Confirmed — `grep -rn "verify-v13\|verify-v14" .github/ scripts/ .claude/` → **empty** | Confirmed |

Commands, abbreviated:

```
$ git ls-files project-harness/archive | grep '\.md$' | wc -l          → 215
$ <basename cross-reference, excluding archive/ and review-2026-08/>
  archive md: 215  loc 29168
  referenced outside archive/review: 38  loc 11469
  UNREFERENCED: 177  loc 17699          ISSUES_RESOLVED.md in referenced set? True

$ for t in check-base-rate check-engine-coverage review-cases check-variance variance-score; do
      grep -qE "^$t:" Makefile && echo "$t EXISTS" || echo "$t MISSING"; done
  check-base-rate MISSING / check-engine-coverage MISSING / review-cases MISSING
  check-variance MISSING / variance-score MISSING

$ grep -rn "run_tick(session" tests/ --include=*.py | wc -l            → 0
$ grep -rn "live_openapi" --include=*.py --include=Makefile --include=*.sh --include=*.ps1 --include=*.yml .
                                                                       → (empty)
$ grep -rn "verify-v13\|verify-v14" .github/ scripts/ .claude/         → (empty)
```

**One new fact that changes a ranking.** The ten longest tracked paths in the repository are *all*
inside `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/` (67 files), and 43
tracked paths exceed 100 characters:

```
$ git ls-files | awk '{print length($0), $0}' | sort -rn | head -3
118 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-40-slice2-negotiation-backed-trade-handler.md
116 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-21-slice2-world-state-quest-trigger-wire.md
112 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-211-212-player-memory-and-forgetting.md
$ git ls-files | awk 'length($0)>100' | wc -l                          → 43
```

That directory is precisely what CR-L16-01 measured as the cause of `git clone` failing on Windows
with `Filename too long`. **Deleting the unreferenced archive is not only the largest subtraction
available — it also fixes half of the fresh-clone blocker for free.** No sibling lens connected
these two facts.

---

## 1. The ranked subtraction ledger

Ranked by (lines removed × confidence) ÷ risk, with confidence Confirmed = 1.0 / Likely = 0.7, and
risk scored 1 (nothing references it) / 2 (one known reference to update) / 4 (a subsystem seam) /
8 (needs a human decision or a CI change first). Where two lenses proposed different actions, the
resolution is in §2 and the ledger carries the resolved verdict only.

| Rank | What | Lines removed | Files | Risk | What breaks | Verdict |
|---:|---|---:|---:|---|---|---|
| 1 | **Unreferenced `project-harness/archive/` markdown** — 177 files whose basename appears nowhere outside `archive/` and this review. Keeps the 38 that something still links, `ISSUES_RESOLVED.md` among them (CR-L11-07, DEC-130) | **17,699** | 177 | **1** | Nothing. By construction no tracked file names them; git retains the history, which is what git is for. Also removes the 43 over-100-char paths that break `git clone` on Windows (CR-L16-01) | **delete now** |
| 2 | **12 one-shot session prompts and handoffs** — `PROMPT_P25_*`, `PROMPT_P26_INTEGRATION`, `HANDOFF_TRACK_A/B`, `MORNING_HANDOFF_*`, `eval_roadmap_session_prompt`, `SEED_REPRODUCTION_..._BRIEF`, `OVERNIGHT_LOOP_PLAN`, `EVAL_P20_TO_P24_UNBLOCK_PLAN`. Each written in exactly one commit, never touched again (CR-L11-08) | **2,791** | 12 | **1** | Nothing. Keeps the 2 that `ROADMAP.md:3077,3452` links. Add `PROMPT_*`/`HANDOFF_*`/`MORNING_HANDOFF_*` to `.gitignore` so the next program does not mint five more | **delete now** |
| 3 | **Overnight-loop retirement, whole** — `expand_loop.sh` (681), `loop_clock.py`, `loop_compat.sh`, `loop.config.sh`, `loop_gates.py`, `classify_gate_failure.py`, `gate_baseline.py`, `gate_attribution.py`, `gate_confirm.py`, `scan_fix_diff.py`, `roadmap_cursor.py` + core (2,220); `OVERNIGHT_LOOP.md`, `OVERNIGHT_LOOP_PLAN.md`, `human_verification.md`, `soft_review.md`, `.claude/commands/expand-linear-next.md` (1,541); `test_loop_gates.py`, `test_roadmap_cursor.py` (720); `Run-OvernightCombined.ps1` (697) | **5,178** | 18 | **8** | `ROADMAP.md`'s `LOOP:QUEUE` fence grammar and every test asserting it; `make roadmap-verify`; `.claude/commands/expand-parallel.md`; `HUMAN_TASKS.md`. **Dead 13 days** (last log 2026-08-15 09:25). All 12 HALTs were the harness tripping over its own self-tests; 3 of 140 commits touched `src/` (CR-L11-03/09) | **delete after** a `DECISIONS.md` entry retiring the loop — or restart it against an engine roadmap and fix ISSUE-126 first. **The one thing that must not happen is a third month of carrying it undecided.** |
| 4 | **`CLAUDE.md` 476 → 248** — the dead contracts (`GraphUnavailableError`→503, `TokenBudgetExceededError`, `MistralAdapter`, "sole composition root"), the 3 decorative docstring fields, the 4 never-violated import rules, the Issues-log template (moved into `ISSUES.md`'s header, not lost), the 0-of-118 log-field mandate, and the 26 false claims corrected in place (CR-L05 subtraction proposal) | **228** | 1 | **2** | Nothing at runtime. **Highest leverage per line in the ledger**: ~2,600 tokens off every session's mandatory preamble, against ~1.0M tokens already spent on this file across 193 transcripts (CR-L05-09). Sequence the Issues-template move first so it is not dropped | **delete now** |
| 5 | **106 `*_delegates` / `*_opens_one_session` repository tests + the 105 passthrough bodies they guard** — the executed counterfactual is decisive: gutting 105 repository methods produced 66 failures, *every one inside the delegate tests themselves*; zero engine, API, scheduler or conformance test noticed the graph read layer had started returning nothing (CR-L14-02) | **~2,070** | ~30 | **8** | Nothing that runs today. **But this is a net loss unless `tests/integration` runs against a Dockerised Neo4j in `make check` first** — `pytest tests/integration -q` currently prints `9 passed, 34 skipped`, so the Cypher these repositories exist to reach is exercised by nothing in CI | **delete after** Neo4j is in CI and `tests/integration` stops skipping. Not before. |
| 6 | **Trend / regression stack** — `regression_gate` (188), `instrument_gate` (147), `baseline_selection` (199), `comparability` (97), `trend_store` (248), `trend_row_builder` (262), `record_trend_and_gate` (168). `wc -l evals/trend/trend_v1.jsonl` → **1**, and that row's `harness_version` (`f22f61a5d877`) no longer matches HEAD's (`21dcfa8dbc86`), so it is already incomparable (CR-L03-05) | **1,309** | 7 | **8** | `scripts/Run-EvalHarness.ps1` steps 7–8; `docs/REGRESSION_POLICY.md`; DEC-191/194/197. Six weeks, zero verdicts | **delete after** one decision: land two comparable runs *this program* or delete. CR-L03-09's single full-corpus generation produces the second row and settles it — do that first, then re-ask |
| 7 | **Sequence subsystem** — `evals/sequence_*.py` (808) + its 6 test files (906). `make eval-sequence` exists; **no committed artifact, no report, no trend field** has ever been produced. `docs/SEQUENCE_STATS_POLICY.md` (227) diverges on 7 of 18 normative claims, 3 of them describing behaviour that does not exist. The `case_seq_*` battery it consumes has zero files (CR-L03-12) | **1,714** (+227 doc) | 12 | **4** | `evals/__main__.py`'s `eval-sequence` verb, `scenario_adapters.py`, `world_map.py`, `reset_fidelity_record.py`, two `e2e/scripts/`. **Not the clean cut CR-L03-12 implies** — I traced the consumers; the reset-fidelity half is genuinely wired to e2e | **delete after** splitting `reset_fidelity` out and keeping it. Archive the rest with its policy doc |
| 8 | **mock/oracle labelling scaffolding** — `oracle_labeller` (281), `oracle_matrix` (201), `oracle_adjudicate` (140), `mock_labeller` (142), `mock_adjudicate` (136), `build_label_order` (141), `migrate_panel_judged` (207) | **1,248** | 7 | **4** | `make mock-calibrate`, `make mock-calibrate-oracle`, `tests/unit/evals/test_oracle_labeller.py`. **Partial defence CR-L11-02 misses**: the oracle-matrix path is the only mechanism that verifies the calibration arithmetic end to end (`Makefile:475` pins an expected κ of 0.247 to 3 dp). That is a real self-test of the instrument | **delete after** — take the mock-**random** half now (`mock_labeller`, `mock_adjudicate`, `build_label_order`, `migrate_panel_judged` = 626 lines, no such defence); **keep the oracle trio** (622) |
| 9 | **`check_engine_coverage.py` + `engine_coverage_contract.py` + their test** — a 44-unit classification taxonomy with **no `make` target**, no CI job, no verdict about behaviour, and whose own doc claim is contradicted in-code (`context_slots.py:146-147` says `active_quest` is "Pinned at 89 and never serialized" while `ENGINE_EVAL_COVERAGE.md` pins it for Rule 11) | **658** | 3 | **2** | `docs/ENGINE_EVAL_COVERAGE.md:3-4`, `docs/CAPABILITY_CASES.md:69` and `ROADMAP.md` advertise `make check-engine-coverage`; those 3 doc lines go with it | **delete now** — my half of the escalated L3/L11 conflict (§2, Conflict A) |
| 10 | **10 single-caller `engines/ports/` Protocols** — `TraitReadPort` (0 implementors, 1 caller, 1 method), `emotion_bootstrap_port`, `emotion_port`, `player_model_port`, `story_pacing_port`, `routine_port`, `faction_politics_port`, and the three `quest_port` protocols. Each re-declares one signature for one caller (CR-L14-03) | **~552** | 10 | **4** | `engines/ports/__init__.py` public surface, the composition root, `check_layers`' allow-list. Keeps the ports with real fan-in — `ClockPort` (16 callers), `WorldStateGraphPort` / `RelationReadPort` / `PlayerLocationReadPort` (6 each) | **delete after** the DIP rule in CLAUDE.md is rewritten to "a Protocol requires 2+ implementors or 3+ callers" — otherwise the next session correctly re-adds them, per the rule |
| 11 | **`live_openapi.json`** — 182 KB, tracked, last regenerated 2026-06-24, 128 paths against 132 live. **Zero** consumers in `*.py`, `*.yml`, `Makefile`, `*.sh`, `*.ps1`; markdown mentions only | **182 KB** | 1 | **1** | Nothing. If the artifact is wanted, CR-L12-07's version is the right one: regenerate in CI on every push, fail on an undocumented diff. A stale committed snapshot is worse than none — a partner studio doing API discovery gets a wrong contract with no generator to refresh it | **delete now** |
| 12 | **3 abandoned harness policy docs** — `EVAL_STRATEGY.md` (175, last touched 2026-05-28, an uncorrected duplicate of `docs/EVAL_METHODOLOGY.md` carrying 3 dead commands/paths — CR-L13-10), `SKILLS_QUEUE.md` (232, dead 90 days while `CLAUDE.md:306` still names it normatively — CR-L07-08), `BATCH5_RESPONSE_MODEL.md` (108) | **515** | 3 | **1** | `docs/SCORER_TRUST_POLICY.md:75` defers its minimum-n rule to `EVAL_STRATEGY.md`. That is not a reason to keep an abandoned file — it is the finding that **sample-size adequacy has no owner anywhere in the repo** (CR-L03 §3). Move the pointer, delete the file | **delete now** |
| 13 | **`engines/deception/` (140) + `engines/currency/` (12) + `test_deception_engine.py` (98)** — the only two of 39 `engines/` subpackages with zero external importers; `currency/` is an empty namespace whose `__init__.py` docstring still reads `Public surface: (list re-exports here)` | **250** | 6 | **1** | `docs/ENGINES.md`'s "~40 engines" count, which is the number a scope conversation starts from. `contracts/currency_engine.yaml` describes transfer behaviour that lives in `api/helpers/action_helpers.py` — repoint the contract, do not delete it | **delete now** |
| 14 | **15 `session_kwarg` tautology tests (~150) + 49 phantom `**_` docstring lines + 27 `tick_scheduler.py` docstring lines** — the SEV-24 migration removed `session=` from every tick engine; the tests and docstrings guarding it were not removed and still pass. Verified: `grep -rn "run_tick(session" tests/` → **0** (CR-L14-01) | **~200** | ~17 | **1** | Nothing at runtime. Not cosmetic: 22 engine docstrings and 27 scheduler lines currently tell the next author to write `run_tick(self, session, *, tick_id)`, which raises `TypeError` on its first tick and is then swallowed by `tick_scheduler.py:387`. **A live trap, removed by subtraction** | **delete now** |
| 15 | **7 dead `verify-v13` / `verify-v14-p0..p5` Makefile aggregates** — referenced by no CI job, no script, no `.claude/` command. Each is a strict subset of what `make check` already runs | **~14** | 1 | **1** | Nothing. Shrinks the 100-target `Makefile` surface that CR-L13 §3 had to audit doc-by-doc | **delete now** |
| 16 | **4 gate names out of `make check`** — `check-human-gates` (green with the feature it guards deleted), `check-test-quality` (`main()` returns 0 unconditionally), `check-conservation` + `check-label-survival` (both audit `k3_73e6c36`, one commit, unchanged since 2026-08-09). Scripts stay; only the `Makefile:200` names go (CR-L06-01/03/09) | **0 code**, 4 target names | 1 | **2** | The "14 green" count drops to 10, which is the point — 5 of 14 can print a problem and exit 0. `check-label-survival` prints *"New (unlabelled) rows: 528"* and exits 0 today | **delete now** from `make check`; re-invoke `check-conservation`/`check-label-survival` from `make eval-generate`, where a *new* artifact is the input |
| 17 | **`mutation_probe.py` (211) + `seed_reproduction_probe.py` (271)** — `make check-mutations` and `make seed-probe` exist; no commit in 967 cites either output. `seed_reproduction.json` records `NOT_MET` at 0.628 against a 0.95 gate, measured 2026-08-14 under `ollama_version 0.32.9` while the current run records `0.32.15` (CR-L03-11) | **482** | 2 | **2** | `make check-mutations`, `make seed-probe`. **A caveat that outranks half the deletion**: 0.628 reproduction means the 6.4 pp effects the regression gate is tuned for sit *inside* the noise floor. That probe is not waste — its result is being ignored | **delete now** `mutation_probe.py` (211); **keep and justify** `seed_reproduction_probe.py` — re-measure under the current runtime and record the model digest |
| 18 | **18 dead `keyword_none` expectation blocks + 3 `moderation_everyone_*` case files** — 50% of `keyword_none` expectations and 79.5% of individual keywords are guaranteed passes against the 975-response corpus. The moderation trio forbids `gore`, `torture`, `beheading` — words a fantasy-tavern NPC on `qwen2.5:7b` has never emitted (CR-L03-08) | **~171** | 3 files + 18 blocks | **2** | Every base-rate table in `docs/`. These are the mechanism behind the 1.000 null pass rate on the YAML guard set — i.e. **behind the CRITICAL** (CR-L03-01). Until they can fail, adding cases only raises Pe and lowers κ | **delete now** — pure subtraction that makes a broken instrument less broken |
| 19 | **`check_conservation` Identity 2** — `all_slots = compare_slots`, then `ok=(compare_slots == all_slots)`. Executed by CR-L06: deleting all 345 `judged.jsonl` rows still prints `Identity 2 [OK]: compare reads all 0 unique record_ids OK`. The tautology is pinned by `test_check_conservation.py:190-191` | **~30** | 2 | **2** | The printed report format and 2 test assertions. Note the shape: it was rewritten into `x == x` **by a commit labelled a bug fix** (`9c907a9`) | **delete now** unless someone restores the pre-`9c907a9` two-population computation; a green line that means nothing is worse than a missing one |
| 20 | **`scripts/migrations/add_faction_support.py`** — its sole `CREATE CONSTRAINT faction_id_unique` is now issued on every process startup by `schema_bootstrap.py:23-29` via `main.py:166` (since `6b91e4f`, 2026-06-04). `docs/API.md:492` and `docs/DATA_MODELS.md:653` still tell operators to run it (CR-L04-02) | **89** (+2 doc lines) | 1 | **1** | Nothing — nothing imports or calls it; it is only ever run by hand, per docs that are wrong | **delete now** |
| 21 | **12 constant-restating tests + 2 duplicated helper families** — `assert MAX_PLAYER_MESSAGE_CHARS == 1000`, `assert EMBED_DIMENSION == 384`, `assert KNOWLEDGE_STATE_KNOWS == "knows"` (CR-L14-06, ~120); byte-identical `_draw_no_data` across 4 `demo_game/ui/` panels (CR-L08-07, ~45); the third copy of the Neo4j→native converter with a **divergent** error path (CR-L14-05, ~30) | **~195** | ~9 | **1–2** | Nothing for the constant tests. The converter deletion is the valuable one: today the same driver value serialises as `str(value)` via `context_builder_helpers` and as the raw object via `graph_reader`, silently and with no log | **delete now** |
| 22 | **`TokenBudgetExceededError`** — `class TokenBudgetExceededError(Exception)` at `utils/errors.py:301`, a bare `Exception` violating the typed-hierarchy rule, referenced by nothing in `src/` and imported-but-unused by one test. CLAUDE.md and `docs/PROMPT_DESIGN.md:91` both promise `context_builder` raises it; the mechanism was deleted on 2026-06-11 by `45b781d` and the promise has stood for **78 days** through 5 edits of CLAUDE.md | **4** (+2 doc claims) | 1 | **1** | One unused test import. Tiny, and the cleanest illustration in the repo of a rule outliving its machinery | **delete now** — pair with row 4 |
| 23 | **71% of unchecked roadmap items** — 46 of 65 belong to the eval-harness meta-program; 8 of 8 active `## Active`/`## Program` headings are eval or harness; zero are product. `packaging/` took 1 file-touch in 200 commits and `make package` has **never** been buildable on any commit (CR-L12-01/02, CR-L02-07) | **0 code**, 46 backlog items | 0 | **8** | The whole roadmap. This is the row the other 22 exist to make room for | **delete after** one human decision: name an external integrator and a date, per CR-L12-06. Descoping without that just moves items to a side file — which is what `UNREAL_DEFERRED.md` already is |

---

## 2. Deduplication — the sibling conflicts, resolved

### Conflict A (escalated to a human by CR-L11): wire or delete `check_base_rate` + `check_engine_coverage` (810 lines)

**Neither lens is right, because the two scripts are different in kind. Split the conflict.**

- **`check_base_rate.py` + `base_rate_contract.py` (386 lines) — WIRE IT. CR-L03-04 wins.**
  This script measures the exact property that produced the review's second CRITICAL. Run today it
  prints `ALL n=975 rate=0.943 above_band` against its declared `[0.55, 0.85]` band, with 9 of 10
  families out of band and 4 flagged `<- CONSTANT: no variance to move`. That is the base-rate
  breach underneath CR-L03-01's "a fixed string scores 0.949, the engine scores 0.897". CR-L11's own
  catch table concedes the pattern: the two instruments that would have falsified the headline
  (`hedge_responder_probe`, `check_base_rate`) exist, are correct, and were pointed away from the
  number. **Deleting an instrument because nobody wired it is deleting the wrong end of the
  problem.** The wiring is a two-line `Makefile` edit; keep `advisory` mode until EVAL-P26, as
  `base_rate_contract.py:42` already specifies.
- **`check_engine_coverage.py` + `engine_coverage_contract.py` + test (658 lines) — DELETE IT.
  CR-L11-02 wins.** It classifies 44 units into a taxonomy. It produces no verdict about behaviour,
  its exit code has never gated anything, and its own governing doc is already contradicted in-code
  (`context_slots.py:146-147` vs `ENGINE_EVAL_COVERAGE.md`'s Rule 11 pin). A taxonomy no decision
  consumes is a 658-line comment.
- **Forcing function:** CR-L11's "this week" is the right instrument. If `check-base-rate` is not in
  the `Makefile` by the next commit that touches `evals/cases/`, it joins its sibling. A gate with
  no invocation has a shelf life and 17 days is most of it.

**One recommendation, not two: wire one, delete the other, this week.**

### Conflict B: CR-L11 and CR-L08 on archived markdown

CR-L08-05/06 correctly cautions that `project-harness/archive/` is "mostly-frozen-but-partly-live"
and that `ISSUES_RESOLVED.md` is canonical and actively appended. CR-L11-07 proposes deleting 175
files. **No real conflict once the population is measured precisely, which neither lens did.** L8's
"224 files" counts untracked review-evidence under a gitignored path; the tracked, deletable
population is **215**, of which the basename cross-reference finds **177 unreferenced (17,699
lines)** and **38 referenced (11,469 lines)** — and `ISSUES_RESOLVED.md` lands in the *referenced*
set automatically. **CR-L11's deletion wins; CR-L08's exception is already satisfied by the method.**

### Conflict C: CR-L03 and CR-L06 on `check_conservation` / `check_label_survival`

- CR-L03-07: *fix* them — repoint the hardcoded `_DEFAULT_GEN_DIR` at the newest generation, render
  the missing `excluded` term in Identity 1's arithmetically-false printed line.
- CR-L06-09: *remove both from `make check`*, invoke them from the eval-regeneration path, keep the
  scripts.

**Not actually in conflict — they answer different questions, and the order matters. CR-L06 wins on
placement, CR-L03 wins on the fix, in that sequence.** Doing CR-L03's repoint while the gates still
sit in `make check` converts two guaranteed-green lines into two lines that go red on stale data at
every commit, for a pre-flight check nobody asked for at commit time — `Makefile:173-175` says so
itself: *"Run before spending a regeneration or a labelling pass."* Move them out first; repoint as
part of wiring them into `make eval-generate`. CR-L06-02's separate finding — Identity 2 is `x == x`
— is additive and is ledger row 19.

### Conflict D: CR-L11-02 proposes deleting `scan_fix_diff.py` outright

**Corrected by verification. Its line count stands; its verdict does not.**
`scripts/expand_loop.sh:387` invokes it and `tests/unit/harness/test_loop_gates.py:26` imports it.
It cannot be deleted independently — it moves into the loop-retirement bundle (row 3). The same
correction applies to CR-L11-03's 525-line "tolerance layer" (`loop_gates.py`, `gate_baseline.py`,
`gate_confirm.py`, `classify_gate_failure.py`, `gate_attribution.py`): all five are `expand_loop.sh`
call sites. **The tolerance layer cannot be subtracted while the loop it serves is undecided. One
decision, one bundle.**

### Conflict E: CR-L03-12 treats the sequence subsystem as a clean 808-line cut

**Corrected.** Traced this session: `evals/__main__.py`, `evals/scenario_adapters.py`,
`evals/world_map.py`, `evals/reset_fidelity_record.py`, `e2e/scripts/measure_reset_fidelity.py` and
`e2e/scripts/reset_fidelity_markdown.py` all reference it. The reset-fidelity half is genuinely
wired to e2e and its measured artifact (`evals/reset_fidelity.json`) matches its doc row-for-row —
CR-L03's own §5 table marks `RESET_FIDELITY` as the one policy doc whose every measured number is
true. **Split it: keep reset-fidelity, archive the order-effect / sequence-rates half with its
policy doc.** Row 7 reflects the split.

### Conflict F: CR-L12 vs the implication of CR-L11's ratio framing on `demo_game/`

CR-L11 counts `demo_game/` (36,961 lines) as shipped product; CR-L12-08 found it is load-bearing for
the *eval* program. **CR-L12 wins outright** and it goes in §4, not the ledger.

### Conflict G: CR-L05's CLAUDE.md cut vs CR-L04's ISSUES.md read-mandate rewrite

Compatible, and they should land in one commit. CR-L05 moves the 38-line Issues-log template into
`ISSUES.md`'s own header; CR-L04-03 rewrites `CLAUDE.md:268` from *"Every session reads it"* (1,799
lines, ~35,346 tokens, ~2.5 h of linear reading) to *"grep `ISSUES.md` for the module you are about
to touch"*. Row 4 carries both.

---

## 3. Grand total

| Tier | Rows | Lines | Files |
|---|---|---:|---:|
| **(a) Zero-risk** — unreferenced artifacts; a `grep` proves nothing names them | 1, 2, 4, 11, 12, 13, 14, 15, 18, 20, 21, 22 | **~22,156** | ~208 |
| **(b) Low-risk** — dead code, unwired gates, one identified reference each to update | 9, 16, 17 (mutation probe), 19, mock-random half of 8 | **~1,525** | ~14 |
| **(c) Requires a decision** — whole subsystems, roadmap descoping, or a CI change first | 3, 5, 6, 7, oracle half of 8, 10, 23 | **~10,850** | ~74 |
| | | **~34,531 lines / ~296 files** | |

Plus **182 KB** of JSON with no consumer (row 11), **46 roadmap items** (row 23), and **4 target
names** out of `make check` (row 16).

Calibration, so the number is not read as bigger than it is:

- Tier (a) alone is **45% of `project-harness/`'s 48,988 markdown lines**, and removes ~2,600 tokens
  from every session's mandatory preamble.
- The full 34,531 is **16%** of the 214,008-line tree (107,323 machinery : 106,685 product,
  CR-L11 §1). It is **not** a fix for the 1.01:1 ratio. Executing every row moves it to roughly
  **0.78:1** — better, and still nowhere near a product-led repository.
- **32,461 of the 34,531 lines (94%) are process and measurement machinery.** Only ~2,070 lines
  (row 5) and ~552 (row 10) come out of `src/` or `tests/`, and both are gated on a prerequisite.
  **Subtraction alone does not make this a product again.** Row 23 does, and row 23 removes no lines
  at all.

---

## 4. The three things I would NOT delete

A subtraction lens that deletes everything is as useless as one that deletes nothing. These three
look like waste by the review's own metrics and are not.

### 1. `tests/` — the ~61,300 engine-facing lines, not the whole 80,324

CR-L11 correctly classes `tests/unit/{evals,scripts,harness}` + `tests/integration/evals` (18,984
lines, 23.6%) as machinery, and this ledger takes ~2,270 more out of the engine half (rows 5, 14,
21). What remains — roughly **61,300 lines / 4,048 tests in 333 s** — stays, and the argument is not
sentiment:

- CR-L15 §4 tested the coverage claim honestly and it survived: import-only inflation is **under
  ~2%** of the 87.86% headline. Among the 10 largest `src/` modules, **zero** show the
  high-percentage-never-called pattern. The one bad module (`intent_queries.py`, 34.6%) is
  *honestly low* — it drags the average down, not up.
- CR-L14's own executed counterfactual is the strongest evidence *for* keeping the engine tests:
  when a mismatched `run_tick` signature was injected, the thing that caught it was
  **`MilitaryEngine`'s own four unit tests** — not `BaseEngine`, not mypy, not any gate.
- It is the only mechanism in the tree with a demonstrated relationship to catching regressions
  before they ship, and it costs 333 s.

The critique that lands is CR-L15-01's, and it is a fix, not a deletion: ~169 s of "unit" tests make
real unmocked `httpx` calls to Ollama and the live API, so the coverage number is partly a property
of what infrastructure happened to be running. **Inject the fakes the file's own two mocked tests
already use.** S-effort, and it makes the suite worth more rather than smaller.

### 2. `demo_game/` — 36,961 lines, 8 file-touches in 200 commits, and not a subtraction candidate

It looks like the single largest dead weight in the repo: frozen since `e975215` (2026-06-13, 76
days), zero commits during the loop's entire life, and it is a **pygame** app while
`BUSINESS_REQUIREMENTS.md:21-22` names Unity and Unreal as the target clients. Delete it and the
harness:product ratio improves dramatically.

**Delete it and the eval program stops working.** CR-L12 §5 traced this and it is decisive:

- `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` by
  running `python -m demo_game.snapshot`.
- `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` always creates.
- `tests/unit/api/test_client_paths_phase2.py:17`, `test_interaction_phase1.py:25` and
  `tests/unit/config/test_seed_chain_quests.py:19` import from `demo_game` — and those run inside
  `make test-cov`, which **is** CI-gated.
- It runs today: `1116 passed in 9.28s`; `python -m demo_game.runners.run --dry-run` completes
  12 acts.

It was silently repurposed from sales demo into the eval program's world-fixture generator. It is
also the only working demonstration of the product that exists. The right action is the opposite of
subtraction: **CR-L12-08's 9-second `test-demo` addition to `make check`** — currently 36,961 lines
and 1,116 tests are verified by nobody, while `check-conservation` (1 s, tautological) and
`check-label-survival` (1 s, inert) are in the gate.

### 3. `check_layers` (192 lines) — and with it, `type` / `type-evals`

In a review whose headline is that the gate battery is theatre, the temptation is to cull the
battery. **The two or three gates that are not theatre are exactly what must survive the cull**, and
`check_layers` is the clearest:

- It is one of only two gates in `make check` that **passes a counterfactual**. CR-L06 §4 executed
  it: injecting `from npc_engine.api import routes` into a `graph/` file produces
  `layer violation: 'graph' (rank 2) imports 'api' (rank 6)`.
- It holds **2 of the 9 genuine catches in 967 commits** (`d24f442` at introduction, 3 upward
  imports; `a397661`, `relation_phase_writer` importing `engines`) — and they are the only two
  *architectural* catches in the entire record.
- It costs ~1 s and is one of the 6 gates CI actually runs.
- CR-L04 §5 independently found the resulting decomposition healthy: `graph/` and `engines/` medians
  of 103.5 and 86.5 lines, intra-package fan-out ≈1.35/file. That is what an enforced layer model
  buys.

The same defence covers the mypy gates: the 256→0 burn-down (`9ee2e73`) is real and is now a
permanent property of 627 files. Delete these along with the tautologies and the review will have
removed the only load-bearing thing it found.

**Coda — the probe set, the fourth thing, and the one I would grow.** CR-L11's own table contains
the argument: in 967 commits, **exactly one** mechanism ever caused a change to shipped runtime
behaviour, and it was `probe_context_ceiling.py` (`96d83eb`) — a probe written 15 days ago that **no
gate runs**. `hedge_responder_probe.py` produced the number the second CRITICAL rests on.
`evals/mde.py` is a module whose entire job is to tell you a planned experiment is pointless before
you spend ten hours on it. `evals/synthetic_label_guard.py` stops mock labels overwriting human
verdicts. `evals/judge_config.py:114-127` enforces judge≠generator at import with a typed exception.
That is ~1,200 lines with a 1-for-1 catch record, against a gate battery at 0-for-967 on behaviour.
**Probes measure the engine against reality; gates check file shape.** CR-L11-05's `make measure` is
the right move, and it is a rename, not a new mechanism.

---

## 5. The counterfactual: if this had shipped only `src/npc_engine/` + `tests/` + a thin README

**Honest answer: five things would be worse, all of them modest; two would be much better; and the
second of those is the whole ballgame.**

**Worse — what the harness genuinely bought:**

1. **The layer model would not exist as an enforced artifact.** `check_layers` caught 3 upward
   imports at introduction and 1 since. Without it, `engines`↔`graph` tangles the way every
   unenforced layer model does, and CR-L04's healthy decomposition would not be there. This is the
   single clearest thing the process paid for.
2. **mypy would not be at 0.** `9ee2e73` burned 256 → 0 and it has held across 627 files.
3. **`ISSUES.md` / `DECISIONS.md` / `ROADMAP.md` / `PATTERNS.md` / `CLAUDE.md` compound.** Five
   files, 13,493 lines, read every session (CR-L11 §6). A thin-README project re-derives decisions.
   Discount it, though: 53% of DECs are never cited outside `project-harness/`, and 4 of a sampled
   12 are stale or unimplemented (CR-L07-06).
4. **The eval vocabulary is genuinely unusual and would not exist.** Judge≠generator enforced at
   import; the harness detecting its own single-rater tautology and *refusing to print a number*;
   cluster-resampled bootstrap with a stated √k justification; unprompted FWER disclosure;
   `evals/mde.py`. CR-L03 — the most sceptical lens in this review — says so in writing.
5. **The token-budget defect would still be live** (`96d83eb`: budget 1,062 against three NPCs
   needing 995–1,151). **Half credit only** — it was found by a hand-run probe, not by the harness.
   A thin-README project with the same curious maintainer finds it the same afternoon.

**Better — and this is the part that decides the question:**

1. **Three of the four CRITICALs would still be here, and the fourth would not exist.** Gossip
   distortion is a no-op, a fixed string beats the engine on the guard battery, the documented
   Neo4j→503 contract has never existed — none was caught by 14 gates run on every phase for three
   months; all were found by direct inspection in hours. And the `GraphUnavailableError` family was
   **manufactured by process**: CLAUDE.md mandates "document the fallback in the docstring",
   `check-docstrings` verifies a docstring is *present* and is content-blind (`"""Layer: banana"""`
   → 0 findings), so four files now carry compliant docstrings asserting a contract no code
   implements (CR-L11-06). A thin-README project has one fewer defect of that class, not more.
2. **There would be an integrator, and therefore a product.** CR-L12-06 names the mechanism and it
   is not rhetorical: 967 commits, one author, zero external contributors, and a tree-wide grep for
   `design partner|pilot|licensee|LOI` returning nothing outside in-game dialogue about bribing a
   gate guard. With no external clock, "done" is defined by the harness — and the harness is the
   thing being built. The evidence that this actually happened: the entire game-client program was
   moved into a side file on 2026-07-31 and has had **zero commits since**; 8 of 8 active roadmap
   programs are eval or harness; `packaging/` took 1 file-touch in 200 commits; `make package` has
   **never been buildable on any commit**, because the spec's `datas` entries named two paths that
   did not exist on the day it was written; and there are 0 lines of C# or C++ for the two named
   target clients.

**The trade, stated plainly.** The harness bought a good architecture boundary, a clean type tree,
and a genuinely sophisticated measurement vocabulary — for roughly a third of the project's lifetime
authorship and **81% of every commit since 2026-08-01**. It did not catch the defects it was built
to catch; it manufactured one; and its largest single effect was to supply a substitute definition
of "done" that let the product go 28 days without a roadmap entry while the instrument measuring it
got sharper every week.

A thin-README version of this project would have a worse architecture, no eval science, and a
shipping demo. Measured against what a game studio would pay for, **the trade went the wrong way** —
and it is still going, because rows 1–22 remove 34,531 lines without changing it. Only row 23 does.

---

## Findings

### [CR-L09-01] Delete the 177 unreferenced archive files — it is the largest subtraction available and it also fixes the Windows clone blocker

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git ls-files project-harness/archive | grep '\.md$' | wc -l` → **215 files / 29,168 lines**. A basename cross-reference of each against every tracked `.md/.py/.yaml/.txt/.ps1/.sh/.json/.toml` file outside `archive/` and `review-2026-08/` returns **177 unreferenced (17,699 lines)** and 38 referenced (11,469), with `ISSUES_RESOLVED.md` correctly in the referenced set. Larger than CR-L11-07's 175/16,724. Separately and not connected by any sibling lens: `git ls-files | awk '{print length($0), $0}' | sort -rn | head -10` returns ten paths all under `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/` (67 files), and `git ls-files | awk 'length($0)>100' | wc -l` → **43** — exactly the paths CR-L16-01 measured as making `git clone` fail on Windows with `Filename too long`.
- **Cost of inaction:** Every `git grep` at session start returns hits from 29,168 lines of superseded prose, and 60% of the markdown that makes `project-harness/` look like the largest thing in the repo is material nothing reads. Meanwhile every new Windows contributor or evaluator hits a dead stop at step zero, and the fix (`git config core.longpaths true`) is documented nowhere in the tree.
- **Fix sketch:** Delete the 177 unreferenced files in one commit, keeping the 38 that something links. Re-run the cross-reference at deletion time including `review-2026-08/` in the exclusion set, since this review cites archived files by name.
- **Effort:** S
- **Removes:** ~17,699 lines / 177 files
- **Blast radius:** None found by construction; verify once more at deletion time. Requires human approval per CLAUDE.md's "deleting a file you did not create" rule.

### [CR-L09-02] Resolve the escalated gate conflict by splitting it: wire `check-base-rate`, delete `check-engine-coverage`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CR-L03-04 proposes wiring both `make` targets (810 lines); CR-L11-02 proposes deleting both unless wired this week, and escalated the disagreement for a human. Verified: `for t in check-base-rate check-engine-coverage review-cases check-variance variance-score; do grep -qE "^$t:" Makefile ...` → all five **MISSING**. The two scripts are not equivalent. `check_base_rate.py` run today prints `ALL n=975 rate=0.943 above_band` against its declared `[0.55, 0.85]` band with 4 families flagged `<- CONSTANT: no variance to move` — the measurement directly underneath CR-L03-01's CRITICAL. `check_engine_coverage.py` produces a 44-unit classification table whose own governing doc is already contradicted in-code (`retrieval/context/context_slots.py:146-147` says `active_quest` is "Pinned at 89 and never serialized" while `docs/ENGINE_EVAL_COVERAGE.md` pins it for Rule 11). Both carry live test files (227 and 234 lines) that run inside `make test-cov`, so neither is unexecuted — only unconsumed.
- **Cost of inaction:** The 0.943 base-rate breach stays invisible while the branch it sits on (`eval-ab-context-arms`) runs A/B arms against it, and 658 lines of taxonomy accrue maintenance under the 300-line, docstring and layer rules for a verdict nobody reads. Both costs compound with every case file added.
- **Fix sketch:** Add `check-base-rate:` to the `Makefile` in advisory mode (2 lines; flip to blocking after EVAL-P26 as `base_rate_contract.py:42` specifies). Delete `scripts/check_engine_coverage.py`, `scripts/engine_coverage_contract.py`, `tests/unit/scripts/test_check_engine_coverage.py` and the 3 doc lines advertising the target.
- **Effort:** S
- **Removes:** ~658 lines / 3 files; adds 2 Makefile lines
- **Blast radius:** `docs/ENGINE_EVAL_COVERAGE.md:3-4`, `docs/CAPABILITY_CASES.md:69`, `ROADMAP.md`. Expect `check-base-rate` to print an out-of-band result on its first run — that is the point.

### [CR-L09-03] Decide the overnight loop's status — 5,178 lines have been carried for 13 days with no owner

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Measured this session: scripts 2,220 lines (`expand_loop.sh` 681, `_roadmap_cursor_core.py` 311, `roadmap_cursor.py` 187, `gate_baseline.py` 169, `loop_compat.sh` 161, `loop_clock.py` 147, `loop_gates.py` 135, `scan_fix_diff.py` 120, `loop.config.sh` 88, `gate_attribution.py` 74, `gate_confirm.py` 74, `classify_gate_failure.py` 73), docs 1,541 (`human_verification.md` 574, `OVERNIGHT_LOOP_PLAN.md` 384, `soft_review.md` 305, `expand-linear-next.md` 170, `OVERNIGHT_LOOP.md` 108), tests 720, plus `Run-OvernightCombined.ps1` 697 — **5,178 lines / 18 files**. CR-L11-09: last loop log 2026-08-15 09:25, 13 days ago; ISSUE-126 (`--dry-run` never terminates) open 26 days at `ISSUES.md:709`. CR-L11-03: all 12 `CLASSIFICATION=HALT` entries name one of 5 harness self-tests; **no node-id under `tests/unit/{engines,graph,retrieval,api}` appears anywhere in `human_verification.md`**. CR-L11-04: `grep -rn "soft_review"` outside `OVERNIGHT_LOOP.md:63` and the loop's own scripts returns nothing — ~60 findings read by nobody, one of which is still open as CR-L03-02.
- **Cost of inaction:** The bundle is not separable — I verified that `scan_fix_diff.py` and the whole 525-line tolerance layer are `expand_loop.sh` call sites, so CR-L11-02/03's individual deletions cannot execute independently. Carrying it undecided costs maintenance on 5,178 lines under the 300-line, docstring and layer rules for a system whose documented dry-run mode still hangs, and whose recorded precedent (2 of 2 confirmed regressions committed anyway, `human_verification.md:262,270`) says its safety layer would not stop a real one.
- **Fix sketch:** Write one `DECISIONS.md` entry: retired, or restarted against an engine-work roadmap. If retired, delete all 18 files together and strip the `LOOP:QUEUE` fence grammar from `ROADMAP.md`. If restarted, fix ISSUE-126 first (a ~3-line change marking the task in the dry-run path) and prove `gate_confirm` by injecting a deliberate `src/` regression.
- **Effort:** S (fix ISSUE-126) / M (the retirement decision and its execution)
- **Removes:** ~5,178 lines / 18 files, if retired
- **Blast radius:** `ROADMAP.md`'s `LOOP:QUEUE` fence and the `roadmap_cursor` tests asserting it, `make roadmap-verify`, `.claude/commands/expand-parallel.md`, `HUMAN_TASKS.md`.

### [CR-L09-04] Cut `CLAUDE.md` 476 → 248 — it is the highest-leverage line-for-line subtraction in the repo

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -l project-harness/CLAUDE.md` → **476**, auto-loaded into every session. CR-L05 checked 109 claims in it: **26 FALSE, 6 unverifiable**, and **22 of 28 rules marked (strict) are enforced by nothing**. Three describe machinery that has never existed: `git log -S "raise GraphUnavailableError" -- src/` → **0 commits, ever**; `TokenBudgetExceededError`'s raise site was deleted by `45b781d` on 2026-06-11 and the rule has stood for 78 days through 5 subsequent edits of this file; `MistralAdapter` has never appeared in a `.py` file in 967 commits. The measured proof that sessions have already stopped believing it is CR-L05-03: on the two docstring fields a gate checks, compliance is **100%/100%**; on the three it does not, **65%/66%/28%** — and the *ungated* `demo_game/` tree scores **81%** on the full 5-field format, higher than the gated one.
- **Cost of inaction:** ~5,197 tokens per session, ~1.0M spent on this file to date across 193 transcripts, buying a rule set that is 22/28 unenforced and 26 claims that are false. The file has grown 346 → 476 lines across 14 commits with **zero lines ever removed**, and its one dated self-correction (`:57`) drifted stale in 17 days.
- **Fix sketch:** Execute CR-L05's subtraction proposal — delete the Documentation section down to the 2 fields the gate checks, the 4 never-violated import rules, the dead contracts, the 0-of-118 log-field mandate; move the Issues-log template into `ISSUES.md`'s header rather than losing it; correct the 26 false claims in place; and apply CR-L04-03's rewrite of `:268` from "Every session reads it" to a grep instruction.
- **Effort:** M
- **Removes:** 228 lines (~10,400 chars, ~2,600 tokens/session)
- **Blast radius:** The Issues-log template must land in `ISSUES.md`, not be dropped. Nothing else references `CLAUDE.md` by line number. This is a deliberate act on the file that says "these rules are not suggestions" and should carry its own `DECISIONS.md` entry.

### [CR-L09-05] Delete the 12 one-shot session prompts and `.gitignore` the pattern before the next program mints five more

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git ls-files project-harness | grep -E "(PROMPT_|HANDOFF_|MORNING_HANDOFF|_PLAN\.md|session_prompt)"` returns **14 files / 3,463 lines**, matching CR-L11-08 exactly. `grep -n` against `ROADMAP.md` shows it links exactly **2** of them (`PROMPT_P23_UNBLOCK.md` at `:3077`, `EVAL_P25_TO_P31_PLAN.md` at `:3452,3510,3542,3605`), leaving **12 files / 2,791 lines** whose task is finished and which nothing names. `EVAL_P20_TO_P24_UNBLOCK_PLAN.md` (367) is *not* linked despite CR-L11-08 assuming both plan docs were. The growth rate is ~5 per program: EVAL-P25..P31 produced 5 in `d46ae42`+`b9717ef` alone, two days ago.
- **Cost of inaction:** They are mined by `git grep` as if they were current policy — the exact mechanism behind CR-L04-02's two docs still telling operators to run a script dead since 2026-06-04. An untracked fifteenth (`PROMPT_CODEBASE_REVIEW_2026-08.md`) is the only one currently outside git, and it is the one actually being used — which is the right pattern, accidentally.
- **Fix sketch:** Add `project-harness/PROMPT_*.md`, `HANDOFF_*.md`, `MORNING_HANDOFF_*.md` to `.gitignore`, delete the 12 tracked files, and fold anything from `EVAL_P20_TO_P24_UNBLOCK_PLAN.md` still live into `ROADMAP.md`, which is the file people read.
- **Effort:** S
- **Removes:** 2,791 lines / 12 files
- **Blast radius:** Check `DECISIONS.md` cross-links before deleting; `ROADMAP.md`'s 5 references are all to the 2 files being kept.

### [CR-L09-06] Delete the 15 `session_kwarg` tests and 76 phantom docstring lines — they are a live trap, not cosmetic debt

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `grep -rn "def test.*session_kwarg" tests/ --include=*.py | wc -l` → **15**; `grep -rn "run_tick(session" tests/ --include=*.py | wc -l` → **0**. Every one of the 15 passes because it never passes `session=` — the `**_` they were written to guard was removed by the SEV-24 migration. CR-L14-01 additionally counts **22 engine `run_tick` docstrings documenting a `**_` parameter with 0 matching `**kwargs` in any signature**, and 27 lines in `scheduler/tick_scheduler.py` promising `run_tick(session, tick_id)` against `grep -rn "async def run_tick" -A2 src/npc_engine/engines/ | grep -c session` → **0**.
- **Cost of inaction:** This is not stale prose. The next person to add a tick engine reads `tick_scheduler.py:96-134` and 22 engine docstrings, all stating the scheduler passes a session, and writes `run_tick(self, session, *, tick_id)`. The scheduler calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`), so that engine raises `TypeError` on its first real tick — and `BaseEngine`'s `(*args, **kwargs)` annotation will not catch it (CR-L14-04, executed: mypy stays clean with an incompatible engine wired in), while `_run_distributed_interval` swallows the `TypeError` at `:387` so the engine silently never runs. That is CR-L01-03's memory-consolidation failure mode, pre-loaded for the next author.
- **Fix sketch:** Delete the 15 tests; strip the `**_:` lines from the 22 `Args:` blocks; rewrite the 27 `tick_scheduler.py` parameter docstrings to the real `run_tick(*, tick_id)` contract. Pair with CR-L14-07's one-line addition to `docstring_audit.py` — "an `Args:` entry must name a parameter that exists in the signature" — which would have caught all 22.
- **Effort:** S
- **Removes:** ~200 lines across ~17 files
- **Blast radius:** Docstrings and tests only; no runtime behaviour changes.

### [CR-L09-07] Do not subtract `demo_game/` — gate it instead; it is the eval program's fixture generator

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `demo_game/` is 36,961 lines with 8 file-touches in 200 commits, last feature commit `e975215` on 2026-06-13, and it is pygame while `BUSINESS_REQUIREMENTS.md:21-22` names Unity and Unreal — every metric in this review marks it as the largest deletion candidate in the tree. CR-L12 §5 establishes it is load-bearing for the *eval* program instead: `Makefile:627` builds `evals/fixtures/eval_world_baseline.json` from `python -m demo_game.snapshot`; `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` creates; and `tests/unit/api/test_client_paths_phase2.py:17`, `test_interaction_phase1.py:25`, `tests/unit/config/test_seed_chain_quests.py:19` import it inside CI-gated `make test-cov`. It runs: `1116 passed in 9.28s`. Yet `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0** and `make check` (`Makefile:200`) omits `test-demo`.
- **Cost of inaction:** 36,961 lines whose failure mode is silent. A `demo_game` regression breaks the eval baseline fixture and three CI-gated unit tests, and the first symptom is an unexplained eval number rather than a red demo test. The likeliest trigger is the `chore: restore the line endings my own edits rewrote` class of sweep-up commit, which already accounts for half of `demo_game`'s recent churn. Meanwhile `check-conservation` (1 s, tautological) and `check-label-survival` (1 s, inert) *are* in the gate.
- **Fix sketch:** Add `test-demo` to `make check` and to the CI test job — 9.25 s against a 595 s baseline, and all 1,116 tests pass today. If `demo_game` is genuinely not worth gating, then move `snapshot.py`, `client.py`, `dialogue.py` and `seeds/` into a small `fixtures/` package that *is* gated, and let the pygame UI rot honestly — but do not delete it while the eval baseline depends on it.
- **Effort:** S (CI) / M (the extraction)
- **Removes:** 0 lines — this is a deliberate non-deletion
- **Blast radius:** `.github/workflows/ci.yml`, `Makefile:200`; `make check` +9 s.

---

## 6. Needs a human decision (not an engineering task)

1. **Conflict A's forcing function** — wire `check-base-rate` this week or delete it (§2, CR-L09-02).
2. **The overnight loop: retired or restarted?** 5,178 lines, dead 13 days, ISSUE-126 open 26 days.
   Row 3 cannot execute without this answer, and CR-L11-02/03's individual deletions are blocked
   behind it.
3. **The trend stack: one more generation, or delete?** CR-L03-09's single full-corpus run over all
   92 cases produces the second comparable row *and* the capability number the battery is missing.
   Do that run before deciding row 6.
4. **Row 23 — name an external integrator and a date.** Every other row in this ledger is
   housekeeping. This one is the review.
5. **Deletion approval.** Per CLAUDE.md, deleting a file you did not create requires human approval.
   Rows 1, 2, 11, 12, 13 and 20 are where that bites hardest — ~200 files, all verified
   unreferenced, none created by this session.

## Pre-merge checklist

- [x] Read-only — no source file created, edited or deleted; this evidence file is the only write
- [x] Every **delete now** row re-verified this session with a pasted or summarised command
- [x] Three sibling claims **corrected** by verification (archive count up; `scan_fix_diff` not
      standalone; sequence subsystem not isolated) rather than repeated
- [x] All seven cross-lens conflicts resolved to **one** recommendation each, including the one
      CR-L11 escalated for a human
- [x] No fifth CRITICAL added — the four are spent
- [x] Grand total split three ways, with the calibration stating what it does *not* fix
- [x] Three defended non-deletions, each with the evidence that defends them
- [x] No `ISSUES.md` entries filed — this is a read-only lens; the orchestrator owns backlog creation
