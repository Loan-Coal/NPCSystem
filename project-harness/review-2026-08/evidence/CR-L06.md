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
