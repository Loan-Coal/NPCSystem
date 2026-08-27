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
