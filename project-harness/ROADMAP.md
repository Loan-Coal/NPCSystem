# NPCSystem — Engine Roadmap

**Status (2026-10-21): the T programme's Sprints 0-8 are complete and archived** at
`archive/ROADMAP_T-programme_2026-10-21.md` (C1, DEC-310). This roadmap is the **drain programme**
(Sprints 11-20). It is built from the 2026-10-21 review (`REVIEW_2026-10-21.md`), the owner's decisions
(DEC-296..DEC-315) and the challenge session that amended them (DEC-316..DEC-327). The handoff is
`OWNER_DECISIONS_2026-10-21.md`.

## The goal

The owner starts `scripts/expand_loop.sh` overnight, possibly over several nights. It drains the queue
below until `roadmap_cursor.py --next` prints `ALL_DONE`, and leaves a strong, clean, simple build:
- NPCs that **remember, feel and gossip**, proved by a pillar eval over the public HTTP/WS routes;
- a demo cut down to text;
- one engine-owned contract;
- a lighter harness.

**Simple beats clever. Fewer moving parts wins every tie.**

**Inside the fence:** only work the loop can do unattended. **Outside it:** the owner's work, with dates
(see "Owner work").

## LOC policy (DEC-313 as amended by DEC-320)

- **Every phase is net-negative on its own**, in the rule-1 four-directory non-test count
  (`src/npc_engine/`, `scripts/`, `evals/`, `demo_game/`; `.py` only, tests excluded).
- **Order within a phase.** Deletion tasks come first, so the running total never exceeds the baseline at any commit.
- **The baseline only goes down.** `scripts/loc_baseline.txt` is never raised. **Each phase's last task**
  lowers it with `python scripts/check_loc_ratchet.py --update` and states the phase's delta.
- **Every task states its LOC delta.** A task whose delta turns out positive while its phase is
  still net-negative says so in its commit body.

Running total against `scripts/loc_baseline.txt` (121,771; measured 121,674 on 2026-10-21). Estimates
from `wc -l` of the files each task deletes or touches:

| Phase | Theme | Est. delta | Running total | Net-negative? |
|---|---|---:|---:|---|
| (start) | — | — | 121,674 | — |
| T21 | Loop bootstrap | −321 | 121,353 | yes |
| T22 | Harness cuts | −200 | 121,153 | yes |
| T23 | Demo shrink | −13,500 | 107,653 | yes |
| T24 | Pillar eval | −1,200 | 106,453 | yes |
| T25 | Pillar fixes | −120 | 106,333 | yes (thin; deletions first) |
| T26 | Contract + ledger truth | −340 | 105,993 | yes |
| T28 | Seams + dead surface | −700 | 105,293 | yes |
| T17 | Judge repair, loop half | −340 | 104,953 | yes |
| T19 | Prompt parts | −320 | 104,633 | yes |
| T29 | Latency | −265 | 104,368 | yes |
| **Programme** | | **≈ −17,306** | **≈ 104,368** | |

T27 is unused, because its ledger-truth tasks live in T26 (DEC-323). T25 has the thinnest margin.
Its first task is a pure deletion (about −270), so its four fixes share about 270 LOC. A fix that needs
more pulls a deletion from the T28 pool forward into its own commit, rather than raising anything.

---

## Carry-forward notes

*Cheap context for the next session. Keep this to 10 lines or fewer, and delete a line once it is consumed.*

- **Flagged tasks:** **0** tasks in the fence are flagged. Every task inside the fence is loop work.
  Work that needs a person sits outside the fence, under "Owner work".
- **Fence size:** **45** tasks in 10 phases (T21, T22, T23, T24, T25, T26, T28, T17, T19, T29), counted 2026-10-21.
  Nothing tests this number. Recount it whenever you move the fence.
- **Night 1 runs the bootstrap alone:** `bash scripts/expand_loop.sh --max-phases 1`. The task-session
  frozen-path check (T21.4) takes effect only when the driver next starts, so phase T21 must finish
  and the driver must restart before any later phase runs (DEC-316).
- **The app image is not bind-mounted.** Every live check rebuilds the isolated eval stack first:
  `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`. It then checks against
  `:8001` and bolt `:7688`. Nothing that must survive lives in the eval Neo4j.
- **Integration tests write to whatever `NEO4J_URI` names** (ISSUE-277). The driver exports the
  default stack's `:7687` (`loop_compat.sh:170`), so keep nothing you need in that Neo4j.
- **Use Git Bash for `make`.** Bare `bash` on this machine is WSL (ISSUE-281).

## Deferred backlog — the loop will NOT do these

`compute_next` never returns a flagged task. The drain programme keeps **no** flagged task inside the
fence: work that needs a person sits outside it, under "Owner work", with a date. This table is kept
because `tests/unit/scripts/test_roadmap_audit.py` reads it. It must list exactly what
`make roadmap-audit` reports, which today is nothing.

| Task | Why it cannot be automated | Blocks | Owner | Due |
|---|---|---|---|---|

---

## How to execute a task in this roadmap

1. **One task per session.** Every task has five lines, and they are the whole specification:
   - **`Files:`** what you may touch;
   - **`Spec:`** the problem, with file:line evidence;
   - **`RED anchor:`** the check that must fail first;
   - **`Validation:`** the exact commands;
   - **`Done when:`** the finish line.
   
   Implement to those. Notice something else? Log it in `ISSUES.md` and carry on.
2. **RED first.** Run the anchor and watch it fail *for the stated reason*. A deletion's anchor is
   usually a grep or `git ls-files` that prints something today and must print nothing afterwards.
3. **Done when names an artefact** (DEC-318): a named test, a command's output, or a committed file
   with an exact path and the content it must hold. Produce that artefact before you tick.
   "Verified" without an artefact is not done. For a live task, the artefact is a committed file.
   Never tick on prose.
4. **`make check` must be green before you tick.** Run it at most twice. Use the task's targeted
   `pytest` path while iterating. `make roadmap-verify` is not part of `make check`, so run it yourself
   after any roadmap edit.
5. **Baselines.**
   - If a deletion resolves baselined violations, update the baseline in the **same** commit and
     state N: `make check-rules-update`, `make type-demo-update`, or the test-quality baselines.
   - `scripts/loc_baseline.txt` is lowered only by a phase's last task (see the LOC policy).
6. **Pre-approval.** A `Pre-approved:` line names exactly the classes the owner approved for that task:
   `file-deletion`, `public-interface`, `graph-schema` or `new-dependency`. Do not halt for a class it
   names, and name the approval in your commit body. A class it does not name still halts.
7. **Live checks** are loop work. Rebuild first with
   `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`. If the stack cannot be built,
   halt `blocked-prerequisite eval-stack <cause>` and never tick.
8. **Frozen paths (DEC-316, from T21.4 on).** A task session must never write:
   - `evals/calibration/`;
   - `evals/generations/k3_73e6c36/`;
   - the loop's own machinery and its instructions (`scripts/expand_loop.sh` and the files listed in T21.4).
   
   The driver resets a session that does and ends the night. New generation runs go in a **new**
   `evals/generations/<id>/` dir, and label exports go to `evals/label_batches/`.

### History

| What | Where |
|---|---|
| The T programme, Sprints 0-8 (T0-T16), as of `3bc86199` | `archive/ROADMAP_T-programme_2026-10-21.md` |
| The M programme + R6 | `archive/ROADMAP_M-programme_2026-09-08.md` |
| The 2026-08 remediation programme (R0-R5) | `archive/ROADMAP_remediation-2026-08_2026-09-03.md` |
| Pre-remediation roadmap (phases 0-26, eval P0-P31) | `archive/ROADMAP_pre-remediation_2026-08-28.md` |
| The 2026-10-21 review, and the decisions that shaped this programme | `REVIEW_2026-10-21.md`, `OWNER_DECISIONS_2026-10-21.md`, DEC-296..DEC-327 |

<!-- LOOP:QUEUE start -->
<!-- Everything between these markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside these markers.
     Scope 2026-10-21: only work the loop can do unattended. Owner work sits below the end marker. -->

---

# SPRINT 11 — Make the loop safe to leave alone

**Self-contained goal:**
- the driver refuses to let a task write the human labels or the loop's own machinery;
- a bad night cannot carry over silently into the next;
- the unused gate machinery is gone.

Run this sprint **alone on night 1** (`--max-phases 1`). The frozen-path check lands in it and takes
effect only when the driver next starts.

### Phase T21

Every task here edits the driver, before T21.4 freezes it. **T21.4 must stay last.**

- [x] **T21.1** Delete the HUMAN GATE machinery
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: delete `scripts/check_human_gates.py` and `tests/unit/scripts/test_check_human_gates.py`.
Edit:
- `Makefile`: `.PHONY` :18, `check-human-gates` :327-328, `check-blocking` :334, and the `check` prerequisite list :489;
- `scripts/expand_loop.sh`: the `gates()` wrapper :174 and the `--check` call :827-835;
- `project-harness/HARNESS_GATES.md`: rows naming either target.
Spec: DEC-317.
- The roadmap holds 0 `#### HUMAN GATE` blocks.
- `TASK_ID_RE` (`check_human_gates.py:34`) reads only `EVAL-P` ids, so the gate blocks nothing.
- A closed gate would end the run (`break`, `expand_loop.sh:833`) rather than skip a task.
- File order already sequences the queue.

Delete the script, both targets, the test and the driver call. Change no other driver logic.
`.github/` references neither target (checked 2026-10-21).
RED anchor: `grep -n "check_human_gates\|check-human-gates\|check-blocking" Makefile scripts/expand_loop.sh`
prints lines today, and must print none afterwards.
Validation:
- the grep above;
- `bash -n scripts/expand_loop.sh`;
- `pytest tests/unit/scripts -q`;
- `make check`.

Done when:
- the grep prints nothing;
- `git ls-files scripts/check_human_gates.py tests/unit/scripts/test_check_human_gates.py` prints nothing;
- `bash -n scripts/expand_loop.sh` exits 0;
- `make check` is green.

LOC: −321 non-test (scripts). ✅ AUTO (T21.1, 2026-10-21)

- [x] **T21.2** Stop committing night-shift reports (C10)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- `scripts/loop.config.sh` :14-15 (`HUMAN_VERIFICATION_FILE`, `SOFT_REVIEW_FILE`);
- `scripts/expand_loop.sh` `checkpoint_reports()` :376-390;
- `.gitignore`;
- `git mv` `project-harness/human_verification.md` and `project-harness/soft_review.md` into `project-harness/archive/`;
- `project-harness/OVERNIGHT_LOOP.md`, the lines naming the report paths.
Spec: C10 (DEC-310). 58 `chore(loop): checkpoint night-shift reports` commits added +1,362 lines
(review §8.1), and 293 of `human_verification.md`'s 858 lines are pasted coverage rows. Do this:
- point both report variables at `overnight_logs/human_verification.md` and `overnight_logs/soft_review.md`;
- add `overnight_logs/` to `.gitignore`;
- make `checkpoint_reports()` stage `ROADMAP.md` only, which keeps the next task's clean-tree preflight passing;
- archive the two tracked reports verbatim;
- remove the pasted coverage rows from the archived copy (they are reproducible with `make test-cov`).
RED anchor: `grep -n "HARNESS_DIR/human_verification\|HARNESS_DIR/soft_review" scripts/loop.config.sh`
prints 2 lines today and must print 0.
Validation:
- the grep;
- `bash -n scripts/expand_loop.sh scripts/loop.config.sh`;
- `git check-ignore overnight_logs/x.md` exits 0;
- `pytest tests/unit/scripts -q`;
- `make check`.

Done when:
- the grep prints nothing;
- `git check-ignore -q overnight_logs/human_verification.md` exits 0;
- `git ls-files project-harness/human_verification.md` prints nothing;
- `make check` is green.

LOC: 0 non-test (bash and markdown only). ✅ AUTO (T21.2, 2026-10-21)

- [x] **T21.3** Guard between nights: night tag, UNVERIFIED refusal, gate-baseline hash
Files: `scripts/expand_loop.sh` (preflight near :241-252, `run_one_task`, the run end near :866-870),
`scripts/loop.config.sh`, and a new test `tests/unit/scripts/test_expand_loop_night_guard.py`.
Spec: DEC-319. Three checks, all in bash:
1. **Night tag.** At the run's end, `git tag -f loop-night-$(date +%F)`.
2. **UNVERIFIED refusal.** Preflight exits non-zero with a clear message while any task line
   carries the cursor's unverified tick marker, unless `--ack` is passed. The marker is the
   prefix of `UNVERIFIED_TEMPLATE` (`_roadmap_cursor_core.py:47`), so match that prefix
   (`AUTO ⚠️ UNVERIFIED`) on task lines only (`^- \[x\]`). Never match the bare word: this
   roadmap's prose names it, and the old count at `:870` read 2 on a clean queue for that reason.
   Fix `:870` to use the same match. `--ack` is a new flag, parsed beside the others at :129-140.
3. **Gate-baseline hash.** Take `sha256sum project-harness/.loop-state/gate_baseline.json`
   before and after every task session. If the two differ, call `flag_for_human` and return 2,
   which ends the night. The file is gitignored (`.gitignore:89`), so no diff would ever show a
   session laundering its failures into it.

Follow the pattern in `tests/unit/scripts/test_expand_loop_execution_error.py:25-62`: source the script
under Git Bash with `main` guarded, and call the functions directly.
RED anchor: the new test fails on all three behaviours today:
- the preflight helper passes with an unverified tick line present (made by `--mark T --date D --unverified r` on a fixture); the test also asserts it still passes on a fixture that mentions the word only in prose;
- the baseline-hash helper does not exist;
- no tag is written.

Validation:
- `pytest tests/unit/scripts/test_expand_loop_night_guard.py -v`;
- `bash -n scripts/expand_loop.sh`;
- `make check`.

Done when: `pytest tests/unit/scripts/test_expand_loop_night_guard.py` passes with 3 or more tests, one per
behaviour, and `make check` is green.
LOC: 0 non-test (bash); about +80 test. ✅ AUTO (T21.3, 2026-10-21)

- [x] **T21.4** Task-session frozen-path check, fixed in the driver
Files: `scripts/expand_loop.sh` (`run_one_task` near :720-770), and a new test
`tests/unit/scripts/test_expand_loop_frozen_paths.py`.
Spec: DEC-316, which supersedes DEC-309's mechanism.
1. **The regex.** Define `TASK_FROZEN_RE` in `expand_loop.sh` itself, not in Python, so it is fixed for
   the run. It covers:
   - `^evals/calibration/`;
   - `^evals/generations/k3_73e6c36/`;
   - `^scripts/(expand_loop\.sh|loop\.config\.sh|loop_compat\.sh|loop_gates\.py|scan_fix_diff\.py|gate_baseline\.py|gate_attribution\.py|gate_confirm\.py|classify_gate_failure\.py|worktree_guard\.py|_roadmap_cursor_core\.py|roadmap_cursor\.py)$`;
   - `^\.claude/commands/expand-linear-next\.md$`;
   - `^\.claude/settings`.
2. **Record the start.** Before the session, set `before=$(git rev-parse HEAD)`.
3. **Collect hits.** After the session:
   - `{ git diff --name-only "$before"; git ls-files --others --exclude-standard; } | grep -E "$TASK_FROZEN_RE"`;
   - plus a hit if `git merge-base --is-ancestor "$before" HEAD` fails.
4. **On any hit:**
   - `git reset --hard "$before" && git clean -fd`;
   - `flag_for_human "frozen path written by <task>" "<paths>"`;
   - return 2, which ends the night.

Do **not** reuse `FROZEN_PATH_PREFIXES` (`loop_gates.py:105-144`). It freezes `tests/`, `Makefile` and
`loc_baseline.txt`, so it would halt every task. Do **not** use `scan_fix_diff.py` either: it diffs only the
working tree, which is empty after a task commits.
RED anchor: the new test fails today. It sources the script, runs the check against a temp repo where a
fake session committed `evals/calibration/x.jsonl`, and expects return 2 with HEAD reset. A second case,
committing only `tests/x.py`, expects return 0.
Validation:
- `pytest tests/unit/scripts/test_expand_loop_frozen_paths.py -v`;
- `bash -n scripts/expand_loop.sh`;
- `make check`.

This is the phase's last task, so it also runs `python scripts/check_loc_ratchet.py --update`.
Done when:
- the new test passes, with at least the calibration-hit case, the `tests/`-allowed case and a
  history-rewrite case;
- `scripts/loc_baseline.txt` total equals the `check_loc_ratchet.py` count;
- `make check` is green.

LOC: 0 non-test (bash); about +90 test. Phase T21 total ≈ −321. ✅ AUTO (T21.4, 2026-10-21)

---

# SPRINT 12 — Cut the harness down

**Self-contained goal:** every later session reads a lighter ledger, and every gate does a job (DEC-310,
DEC-323). C1 (archive Sprints 0-8) was done by hand on 2026-10-21.

### Phase T22

- [x] **T22.1** Delete the fence-snapshot tripwire test (C9)
Files: `tests/unit/harness/test_roadmap_cursor.py`.
Spec: C9. `test_real_roadmap_fence_state_tripwire` (`:241`) was the only failing test in 7 of the 11
historical `HALT FAILED_CHECK=tests` events (review §8.3).
- Delete it, and its history docstring.
- Move its two still-useful assertions into `test_real_roadmap_parses_and_verifies_clean`:
  - every phase has at least one task;
  - `sorted(pending) == actionable`.
- Keep `EXPECTED_FLAGS`: `tests/unit/scripts/test_roadmap_audit.py:28` imports it.
- Keep `_EXPECTED_PHASE_IDS`.
- Shorten the history comment above `_EXPECTED_PHASE_IDS` to 3 lines, pointing at the archives.

RED anchor: `grep -c "def test_real_roadmap_fence_state_tripwire" tests/unit/harness/test_roadmap_cursor.py`
prints 1 today and must print 0.
Validation:
- the grep;
- `pytest tests/unit/harness tests/unit/scripts/test_roadmap_audit.py -v`;
- `make check`.

Done when:
- the grep prints 0;
- `pytest tests/unit/harness/test_roadmap_cursor.py -k parses_and_verifies_clean` passes and asserts
  every phase has a task and `pending == actionable`;
- `make check` is green.

LOC: 0 non-test; about −150 test. ✅ AUTO (T22.1, 2026-10-21)

- [x] **T22.2** Merge the three ledger/report gates into one, and read the DECISIONS history (C7, DEC-327)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- `scripts/check_ledger_ids.py` (200);
- delete `scripts/check_cited_reports.py` (124) and `scripts/check_ceiling_baseline.py` (122);
- their tests under `tests/unit/scripts/`;
- `Makefile` :281, :382, :389 and the `check` list :489;
- `project-harness/HARNESS_GATES.md`.
Spec: C7.
- Fold the cited-report check and the ceiling-baseline check into `check_ledger_ids.py` as two more
  functions. They become one `make check-ledger-ids` target, and their tests move with them.
- Add `"archive/DECISIONS_history.md"` to `_DECISION_FILES` (`:36`) now. T22.3 creates that file, and
  this change keeps it from reading as undeclared citations (DEC-327).
- `check-ceiling-baseline` "does NOT re-measure" (`d331dd24`). If merging it adds nothing beyond a
  file-exists check, delete it outright and say so.

RED anchor: `ls scripts/check_cited_reports.py scripts/check_ceiling_baseline.py` succeeds today and
must fail afterwards. `grep -c "DECISIONS_history" scripts/check_ledger_ids.py` must go from 0 to 1.
Validation:
- `pytest tests/unit/scripts -q`;
- `make check-ledger-ids`;
- `make check`.

Done when:
- both files are gone;
- `make check-ledger-ids` runs all three checks and prints OK;
- `grep -c DECISIONS_history scripts/check_ledger_ids.py` is 1;
- `make check` is green.

LOC: about −200 non-test (scripts). ✅ AUTO (T22.2, 2026-10-21)

- [x] **T22.3** Move uncited DECISIONS to the history file (C2, DEC-327)
Files: `project-harness/DECISIONS.md`, and a new `project-harness/archive/DECISIONS_history.md`.
Spec: DEC-327.
1. **Find the uncited entries.** Take every `## DEC-NNN` heading in `DECISIONS.md` whose id is cited
   nowhere outside `DECISIONS.md` and `project-harness/archive/`. The test is
   `git grep -lw "DEC-NNN" -- . ':!project-harness/DECISIONS.md' ':!project-harness/archive/'` printing nothing.
2. **Move them verbatim**, in their current order, to `archive/DECISIONS_history.md`, under a 3-line
   header saying what the file is.
3. **Do not edit any entry's text.** Do not sort, and do not add Status lines.
4. **Keep in `DECISIONS.md`** everything that is cited, plus DEC-296..DEC-327.
5. Put a 2-line pointer to the history file at the top of `DECISIONS.md`.

RED anchor: `test -f project-harness/archive/DECISIONS_history.md` fails today.
Validation:
- `make check-ledger-ids`, which must report 0 undeclared citations and the same reused-id count as before (DEC: 4);
- `make check`.

Done when:
- the history file exists;
- `grep -c "^## DEC-" project-harness/DECISIONS.md` is below 200;
- `make check-ledger-ids` prints OK with `DEC: 4 reused id(s), 0 undocumented`;
- `make check` is green.

LOC: 0 non-test. ✅ AUTO (T22.3, 2026-10-21)

- [x] **T22.4** Apply the issue triage (C3, DEC-304)
Files: `project-harness/ISSUES.md` and `project-harness/archive/ISSUES_RESOLVED.md`.
Spec: DEC-304, executed from the verdict column of `REVIEW_2026-10-21.md` §6.1 (lines 380-551).
- **KEEP:** stays open.
- **LOOSE-KEEP:** stays open, with a one-line `**Theme:**` naming the drain task that will touch it
  (e.g. `T25.3`). The eval-layer LOOSE-KEEPs name `T17` or "Owner work: labels".
- **Every other verdict:**
  - prefix the heading with `[CLOSED — not scheduled 2026-10-21]`;
  - add `**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites`;
  - move the entry verbatim to `archive/ISSUES_RESOLVED.md`.
- Remove the misleading `## Closed` heading at `ISSUES.md:1463`.
- Before moving anything, confirm that `check_ledger_ids.py`'s declaration regex still matches the new
  heading prefix. If it does not, use `[FIXED]`-style wording that it does match.
RED anchor: `grep -c "^## ISSUE-" project-harness/ISSUES.md` is 165 today, and must drop to 50 or fewer.
Validation:
- `make check-ledger-ids`, which must report 0 undeclared citations;
- `make check`.

Done when:
- the count is 50 or fewer;
- `grep -c "^## Closed" project-harness/ISSUES.md` is 0;
- `make check-ledger-ids` prints OK;
- `make check` is green.

LOC: 0 non-test. ✅ AUTO (T22.4, 2026-10-21)

- [x] **T22.5** Archive the one-off files, delete the stale commands, fix CLAUDE.md's rule-5 line (C4, C11, C14)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- `git mv` into `project-harness/archive/`: `CODEBASE_REVIEW.md`, every `project-harness/PROMPT_*.md`,
  `EVAL_P25_TO_P31_PLAN.md`, `OVERNIGHT_LOOP_PLAN.md`, `BASELINE_2026-09*.md`, `REVIEW_FINDINGS.md`,
  `review-fixes/` and `roadmap-review/`;
- delete `.claude/commands/continue.md`, `fix-next.md`, `fix-parallel.md` and `full-review.md`;
- `project-harness/CLAUDE.md` :140, plus any file whose citation of a moved path breaks.
Spec:
- **C4.** Archive the one-off review and plan files.
- **C11.** Delete the four stale commands. `continue.md` reads a missing `NEXT_SESSION.md`; the other
  three drive the retired 2026-08 programme.
- **C14.** CLAUDE.md says rule 5 has "No gate on this tree". It has been gated since `3ab66da0`.
  Rewrite the line to name `make check-test-quality`.
- **Citations.** `check-cited-reports` (merged into `check-ledger-ids` by T22.2) globs `**/*.md`, so a
  moved file stays visible. Fix any citation whose path the merged check reports as missing.
RED anchor: `ls project-harness/CODEBASE_REVIEW.md .claude/commands/fix-next.md` succeeds today and must fail.
Validation:
- `make check-ledger-ids`;
- `grep -n "No gate on this tree" project-harness/CLAUDE.md` prints nothing;
- `make check`.

Done when:
- both paths are gone from their old locations;
- `git ls-files project-harness/archive/CODEBASE_REVIEW.md` prints the file;
- the CLAUDE.md grep prints nothing;
- `make check` is green.

LOC: 0 non-test. ✅ AUTO (T22.5, 2026-10-21)

- [x] **T22.6** Delete the unreferenced Makefile targets and fix HARNESS_GATES.md (C12)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: `Makefile`, `project-harness/HARNESS_GATES.md`.
Spec: C12, with one correction checked on 2026-10-21. Review §8.1 called 20 targets unreferenced, but
`.github/workflows/ci.yml` still runs five of them:
- `test-v13-contracts`, `test-v13-graph-admin` and `test-v13-retrieval` (ci.yml:129-131);
- `test-v14-p4` (ci.yml:184);
- `test-v14-p5` (ci.yml:205).

**Keep those five**: touching CI needs the owner. Delete these, and their `.PHONY` entries:
- `verify-v13` :491;
- `verify-v14-p0..p5` :493-503;
- `test-v14-p0..p3` :184-196;
- `type-ratchet`.

Fix HARNESS_GATES.md so every gate it lists exists in `make check` (`Makefile:489`). It contradicts
`Makefile:229,489` at `:29,32` today.
This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: `grep -cE "^(verify-v13|verify-v14-p[0-5]|test-v14-p[0-3]|type-ratchet):" Makefile` is above 0
today, and must be 0.
Validation:
- the grep;
- for each target in `.github/workflows/ci.yml`, `make -n <target>` succeeds;
- `make check`.

Done when:
- the grep prints 0;
- every target `ci.yml` calls still exists;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: 0 non-test (Makefile). Phase T22 total ≈ −200. ✅ AUTO (T22.6, 2026-10-21)

---

# SPRINT 13 — Cut the demo to text

**Self-contained goal:** `demo_game/` holds only the scripted runner, the seeder, the snapshot tools, the
scenarios and a thin text client (DEC-296, DEC-297). About 12.8k LOC of pygame UI is gone.

### Phase T23

- [x] **T23.1** Delete the pygame UI packages
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: delete
- `demo_game/ui/` (7,989), `demo_game/pollers/` (2,168), `demo_game/graph_panel/` (562), `demo_game/workers/` (272);
- `demo_game/tests/ui/` and `demo_game/tests/pollers/`.

Edit any surviving import site.
Spec: DEC-297. A top-level-import closure on 2026-10-21 showed that none of these four packages is
reached by `make demo-run` (`runners/`, `beats/`, `branches/`, `client`, `config`, `constants`,
`dialogue_ws`, `encoding_utils`, `arc_choice`, `seeds/seed_npc_data`) or by `make demo-seed`
(`seeds/`). They are reached only through `demo_game/__init__.py:38,45`, which lazily imports
`start_menu` and `game_window`. Keep `scenarios/`, `snapshot.py`, `restore_guard.py`,
`derived_fields.py` and `quickstart.py`: other Makefile targets use them (:865, :900-937, :966-972).
RED anchor: `git ls-files demo_game/ui demo_game/pollers demo_game/graph_panel demo_game/workers | wc -l`
is above 0 today, and must be 0.
Validation:
- the count;
- `make test-demo`;
- `make type-demo`, then `make type-demo-update` in the same commit if the count dropped;
- `make demo-run ARGS=--dry-run`, or the closest offline form `Makefile:874` supports;
- `make check`.

Done when:
- the count is 0;
- `make test-demo` passes;
- `.mypy_baseline_demo` is no higher than 256;
- `make check` is green.

LOC: about −10,991 non-test (demo_game). ✅ AUTO (T23.1, 2026-10-21)

- [x] **T23.2** Delete the interactive root modules and their entry points
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: delete
- `demo_game/game_controller.py` (556), `game_end_checker.py` (505), `quest_trade_controller.py` (329),
  `dialogue.py` (152), `world_objectives.py` (149), `knowledge_sidebar_fetcher.py` (53),
  `audio_player.py` (35), `__main__.py` (35), `intent_ui.py` (19);
- the ten interactive-only tests in `demo_game/tests/core/`: `test_action_workers`, `test_dialogue_logic`,
  `test_g1_wiring`, `test_g2_deception_tell`, `test_game_end_checker`, `test_gossip_chain`,
  `test_gossip_chain_distortion_type`, `test_quest_trade_controller`, `test_sev11_game_end` and
  `test_spread_rumor_worker`.

Edit `demo_game/__init__.py` (the FREE_PLAY dispatch branch), `Makefile` (`demo` :841-843,
`demo-stale` :846-848 and `.PHONY`), `docs/overview.md:42`, and `scripts/check_test_quality_demo_baseline.txt`.
Spec: DEC-297, continued. These nine modules are reachable only from `make demo` / `python -m demo_game`.
- Delete them, the two Makefile targets and the start-menu dispatch.
- Re-ratchet the demo test-quality baseline (a single number, now 50) to the new count.
- Do not touch `scenarios/`.

RED anchor: `ls demo_game/game_controller.py demo_game/__main__.py` succeeds today and must fail.
`grep -c "^demo:" Makefile` must go from 1 to 0.
Validation:
- `make test-demo`;
- `make type-demo`, updating the baseline downward if the count dropped;
- `make check`.

Done when:
- the files are gone;
- `grep -c "^demo:" Makefile` is 0;
- `python -c "import demo_game"` exits 0;
- `make test-demo` and `make check` are green.

LOC: about −1,833 non-test (demo_game). ✅ AUTO (T23.2, 2026-10-22)

- [x] **T23.3** Trim `client.py` to the methods the kept code calls
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: `demo_game/client.py`, its tests under `demo_game/tests/`, `scripts/rules_baseline.txt`.
Spec:
1. **Dead methods.** `client.py` is 1,901 lines with 66 public methods, and it carries an R001 waiver
   (`rules_baseline.txt:4`). After T23.1-T23.2, about 27 methods (≈617 LOC) have no caller left, and 4
   more (≈103 LOC) never had one: `get_quest_drafts` :968, `post_quest_objective` :1113,
   `post_quest_evaluate` :1150 and `get_item_price` :1262.
2. **Delete every public method with no non-test caller in `demo_game/`, `scripts/` or `e2e/`.** Find them
   with `git grep -w <name> -- ':!demo_game/tests' ':!tests'`.
3. **Then the size cap.** If the file is still over 800 lines, split it by API domain into
   `demo_game/client/` modules behind the same `NpcEngineClient` import path, and delete the R001 row.
   If it is 800 lines or fewer, just delete the R001 row.

RED anchor: `grep -c "R001|demo_game/client.py" scripts/rules_baseline.txt` is 1 today, and must be 0.
Validation:
- `make test-demo`;
- `make check-rules`;
- `make check`.

Done when:
- the R001 row is gone;
- `wc -l` of every file holding the client is 800 or fewer;
- `make check-rules` reports no violation for it;
- `make check` is green.

LOC: about −700 non-test (demo_game). ✅ AUTO (T23.3, 2026-10-22)

- [x] **T23.4** Make `quickstart.py` the thin text client
Files: `demo_game/quickstart.py`, `Makefile` (the `hello` target :865-866), a new test
`demo_game/tests/core/test_quickstart_chat.py`, and `README.md` (the quickstart section only).
Spec: DEC-297 keeps "a thin text client". `quickstart.py` (177) already seeds one NPC and sends one
turn (`:136`). Extend it into a REPL:
- `python -m demo_game.quickstart --npc <id>` reads lines from stdin and sends each over the public WS
  dialogue route through the existing `dialogue_ws` helper;
- it prints `npc_response`, `emotion` and `relation_deltas`;
- it exits on EOF.

Add `make chat NPC=<id>` beside `make hello`. Add no new dependency.
This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: the new test feeds two lines through a stubbed client and asserts two sends and two printed
replies. It fails today.
Validation:
- `pytest demo_game/tests/core/test_quickstart_chat.py -v`;
- `make test-demo`;
- `make check`.

Done when:
- the test passes;
- `grep -c "^chat:" Makefile` is 1;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: about +40 non-test. Phase T23 total ≈ −13,500. ✅ AUTO (T23.4, 2026-10-22)

---

# SPRINT 14 — An eval that goes red when NPCs don't remember, feel or gossip

**Self-contained goal:** `make demo-run-live` drives the public HTTP/WS routes Unreal calls (DEC-299).
It writes a diffable JSONL transcript, and commits one verdict per pillar to `evals/pillar_verdicts.jsonl`
(DEC-301, DEC-321). It is expected to be red on first run (review §4). Every pillar fix in Sprint 15 is
done when its line turns green.

### Phase T24

- [x] **T24.1** Delete the dead eval probes
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: delete
- `evals/probe_runner.py` (386), `probe_dialogue.py` (246), `probe_quest.py` (201), `probe_memory.py` (179),
  `probe_gossip.py` (170), `probe_events.py` (120), `probe_legacy_adapters.py` (112), `probe_protocol.py` (64);
- their tests.

Edit `evals/__main__.py:139-140` (the `probe` verb), `Makefile` (`eval-probe` :738-742 and `.PHONY` :25),
and `scripts/evals_baseline.txt:24`. Do **not** touch `arm_probe*` (`eval-arm-probe`, a separate live tool).
Spec: the probes measure nothing:
- ISSUE-336: `probe_events` 422s every POST;
- ISSUE-337: `probe_gossip` reads a key that does not exist;
- ISSUE-339: 10 of 11 probes ask for engine names the scheduler never registers.

The pillar eval replaces them. Close all three issues: mark each `[FIXED]` with a `**Fixed:**` line and
move it verbatim to `archive/ISSUES_RESOLVED.md`.
RED anchor: `ls evals/probe_runner.py` succeeds today and must fail.
Validation:
- `make check-evals-rules`;
- `make type-evals`;
- `make check-ledger-ids`;
- `make check`.

Done when:
- `git ls-files 'evals/probe_*.py'` prints nothing;
- ISSUE-336/337/339 appear only in `archive/ISSUES_RESOLVED.md`;
- `make check` is green.

LOC: −1,478 non-test (evals). ✅ AUTO (T24.1, 2026-10-22)

- [x] **T24.2** Give the scripted runner a transcript recorder and bounded waits
Files: `demo_game/runners/run.py` (`DemoRunner` :536-597, `LLMCache` :86-91),
`demo_game/runners/run_scenes.py` (:196, :229), `demo_game/dialogue_ws.py`, a new
`demo_game/runners/transcript.py`, and new tests in `demo_game/tests/runners/`.
Spec: DEC-321. The transcript is the eval's evidence.
1. **Recorder.** `DemoRunner` gains one more hook: a `TranscriptRecorder` passed in through the
   constructor, as `cache=` is today. It appends one JSON line per HTTP/WS request and response
   (method, path, status, body) and per graph read. Graph reads go through public or admin HTTP
   routes only (`api/routes/admin/graph.py`), never a Neo4j driver (DEC-299).
2. **ISSUE-348.** Change `if cached:` at `run_scenes.py:196,229` so that an empty cached reply is not
   treated as a hit.
3. **ISSUE-347.** Every WS `recv` in `dialogue_ws.py` gets a timeout (a named constant). Without one,
   an unattended run can hang until the 5,400 s session timeout ends the night.

RED anchor: three tests fail today:
- a recorder test, asserting one line per request on a stubbed client;
- a cache test, where an empty cached reply must miss;
- a WS test, where a stubbed socket that never answers must raise within the timeout.

Validation:
- `pytest demo_game/tests/runners -v`;
- `make test-demo`;
- `make check`.

Done when: all three tests pass, ISSUE-347 and ISSUE-348 are archived as `[FIXED]`, and `make check` is green.
LOC: about +120 non-test (demo_game). ✅ AUTO (T24.2, 2026-10-22)

- [x] **T24.3** Pillar assertions, replacing `demo_run_live.py`
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- a new `demo_game/runners/pillars.py`;
- delete `scripts/demo_run_live.py` (338) and its tests;
- `Makefile` `demo-run-live` :882-884;
- `demo_game/beats/determinism_beat.py` :75-80;
- new tests in `demo_game/tests/runners/`.

Spec: DEC-301 and DEC-321. `pillars.py` reads a transcript and returns one verdict per pillar:
- **FEEL:** after the market-fire event, `GET /v1/npc/aldric_merchant/emotion` is not neutral 0/0;
- **REMEMBER:** after the dialogue beats, a relation edge has a non-zero delta, and after ACT 4 a
  `Memory` node exists;
- **GOSSIP:** the hop-2 `KNOWS_ABOUT` edge has `distortion_level > 0`, and `source_character_id` points
  back along the chain;
- **WORLD:** after ACT 1's ticks, each seeded NPC is at its seeded location (`seed_world_data.py:226-235`);
- **DETERMINISM:** two runs compare **non-empty** tables. Fix the vacuous `{} == {}` at
  `determinism_beat.py:75-80`.

FEEL, the REMEMBER delta and GOSSIP distortion are LLM-dependent. They repeat only their own beats, three
times, and pass on 2 of 3. Everything else runs once. `make demo-run-live`:
- keeps its name and its `DEMO_LIVE=` line, which the driver's nightly report reads (`expand_loop.sh:300-322`);
- prints `DEMO_LIVE=PASS` only when every pillar is green;
- writes `evals/pillar_verdicts.jsonl`, one line `{"pillar","verdict","repeats","evidence","sha"}` per pillar;
- exits 0 when pillars are red, and non-zero only on a harness or stack error.

Close ISSUE-351: the beats no longer claim what they do not show.
RED anchor: unit tests over recorded transcript fixtures, under `demo_game/tests/runners/fixtures/`, fail today:
- a fixture copying review §4's red facts must yield FEEL, REMEMBER, GOSSIP and WORLD red;
- a hand-made green fixture must yield all green;
- `{} == {}` must yield DETERMINISM red.

Validation:
- `pytest demo_game/tests/runners -v`;
- `make test-demo`;
- `make check`.

Done when:
- the fixture tests pass;
- `git ls-files scripts/demo_run_live.py` prints nothing;
- `make -n demo-run-live` names `pillars`;
- `make check` is green.

LOC: about +500 −338 non-test. ✅ AUTO (T24.3, 2026-10-22)

- [x] **T24.4** First pillar run on the stack, committed as the red baseline
Files: `evals/pillar_verdicts.jsonl` (new) and `project-harness/ISSUES.md`.
Spec: DEC-301 says the eval is expected to go red today. Make that a committed fact.
1. Rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`.
2. Run `make demo-run-live`.
3. Commit the verdict file.
4. For every red pillar, check that an open issue names it: ISSUE-373 for WORLD, ISSUE-228 for GOSSIP,
   ISSUE-201 for FEEL. For a red pillar with no issue (REMEMBER's relation deltas; consolidation never
   firing), log a new issue with the evidence line.
5. The verdicts are data. Do not try to turn them green in this task.

This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: `test -f evals/pillar_verdicts.jsonl` fails today.
Validation:
- `make demo-run-live`;
- `python -c "import json;[json.loads(l) for l in open('evals/pillar_verdicts.jsonl')]"`;
- `make check`.

Done when:
- `evals/pillar_verdicts.jsonl` is committed with 5 lines, each carrying the `sha` that `/health`
  reported for this commit;
- every red pillar is named by an open issue;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: 0 non-test. Phase T24 total ≈ −1,200. ✅ AUTO (T24.4, 2026-10-22)

---

# SPRINT 15 — NPCs remember, feel and gossip

**Self-contained goal:** every pillar line in `evals/pillar_verdicts.jsonl` is green (DEC-315 #3).
Each fix is done when a fresh `make demo-run-live` at its own commit turns its line green, and the
re-run verdict file is committed with the fix. RED anchors reuse the committed red line from T24.4,
so a fix task needs no old-tree rebuild.

### Phase T25

- [x] **T25.1** Collapse the emotion-model protocol and delete the dead mood/routine surface
Pre-approved: file-deletion, public-interface · owner 2026-10-21 · DEC-311
Files:
- delete `src/npc_engine/engines/emotion/emotion_model_protocol.py` (68) and `emotion_model_factory.py` (76);
- `src/npc_engine/engines/emotion/emotion_updater.py` :17,42,56;
- `vad_emotion_model.py` :13,116;
- `src/npc_engine/api/dependencies_stores.py` :19,76-78;
- `src/npc_engine/config.py` :265-268,526-530;
- `src/npc_engine/graph/emotion/mood_queries.py`;
- delete `src/npc_engine/engines/routine/routine_queries.py` (23);
- `src/npc_engine/engines/relationship/relation_mutator.py`;
- `scripts/dip_waivers.txt`;
- the matching tests.

Spec: DEC-326, which supersedes DEC-303's emotion-registry reshape.
- `EmotionModelProtocol` has one implementor, and the registry holds only `"vad"` (`factory:76`). Inject
  `VadEmotionModel` concretely into `EmotionUpdater`, and delete the protocol, the factory, the
  `registered_emotion_models` config hook, and the stale `trait_modulated` mention.
- Delete the dead `mood_queries.py` symbols `get_co_located_affectionate_pairs` :48,
  `set_character_mood` :90 and `get_all_character_moods` :112, with their Cypher constants. Keep
  `get_character_mood` :70.
- Delete the importer-less `routine_queries.py` shim, and `relation_mutator.apply_dialogue_relation_deltas`
  (:31, no callers).
- Close ISSUE-362.

RED anchor: `git grep -n "EmotionModelProtocol\|registered_emotion_models" -- src` prints lines today and must print none.
Validation:
- `pytest tests/unit/engines -q`;
- `make check-dip-threshold`;
- `make check-dead-surface`;
- `make check`.

Done when:
- the grep prints nothing;
- the three dead `mood_queries` functions and `routine_queries.py` are gone;
- ISSUE-362 is archived;
- `make check` is green.

LOC: about −270 non-test (src). ✅ AUTO (T25.1, 2026-10-22)

- [x] **T25.2** WORLD: NPCs stay where they were seeded (ISSUE-373)
Files:
- `src/npc_engine/graph/scheduling/routine_queries.py` :39-46,81-85;
- `src/npc_engine/graph/planning/planning_repository.py` :79-85 (`move_character`);
- `src/npc_engine/graph/needs/need_queries.py` :110-131;
- `src/npc_engine/engines/routine/routine_engine.py` :92,113-142;
- tests in `tests/unit/graph/` and `tests/unit/engines/`;
- `evals/pillar_verdicts.jsonl`.

Spec: ISSUE-373. By tick 5, Sorn, Mira and Henryk are all at `loc_temple` with `arrived_at_tick 0`
(review §4). The best static cause:
- `move_character` omits `arrived_at_tick`, so it is always 0;
- its target comes from `get_satisfying_location_for_need`, which is `LIMIT 1` with no `ORDER BY`, so
  every NPC gets the same global location.

Fix it:
- pass the tick id through `move_character`;
- scope the satisfier query to locations the NPC's schedule or region allows, ordered deterministically
  (e.g. nearest, then id);
- make the routine engine keep the seeded location while no schedule entry or need applies.

Confirm the cause on the stack before fixing: if the first live run shows a different writer, fix that
writer and note it in the issue. No schema change is expected. If one proves necessary, halt
`needs-decision` rather than change the schema.
RED anchor: two things fail today:
- a unit test where two NPCs with different needs get different satisfier locations, and `move_character`
  records the tick;
- the WORLD line in `evals/pillar_verdicts.jsonl` (T24.4), which is red.

Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- `make demo-run-live`.

Done when:
- the unit test passes;
- the re-committed `evals/pillar_verdicts.jsonl` has `"pillar": "WORLD"` with `"verdict": "green"` at this commit's sha;
- ISSUE-373 is archived;
- `make check` is green.

LOC: about +30 non-test. ✅ AUTO (T25.2, 2026-10-22)

- [x] **T25.3** GOSSIP: distortion compounds and edges point the right way (ISSUE-228)
Files: `src/npc_engine/graph/gossip/gossip_batch_queries.py` :36-62,
`src/npc_engine/engines/gossip/gossip_distort.py` :240, tests in `tests/unit/graph/` and
`tests/unit/engines/gossip/`, and `evals/pillar_verdicts.jsonl`.
Spec: ISSUE-228. Three bugs:
- **Mispairing.** `gossip_batch_queries.py:36-39` builds three separate `head(collect(...))` values.
  `collect()` drops nulls, so `best_distorted_summary` can come from a different event than `best_event`.
  Collect one map per row instead.
- **Overwrite.** `k.distortion_level` is never read. The level is recomputed from probability alone
  (`gossip_distort.py:240`), and an unconditional `SET` (`:56-62`) overwrites the seeded value. Read the
  prior level and compound it.
- **Backwards source.** `KNOWS_ABOUT/mira_innkeeper/northern_war_begins` carries
  `source_character_id: old_henryk` (review §4). Fix whichever write makes it point backwards.

Gossip stays deterministic and seeded (rule 8).
RED anchor: unit tests fail today:
- a batch where one candidate has a null summary must pair the summary with its own event;
- a hop-2 edge must have a level above the hop-1 edge's.

The GOSSIP line in `evals/pillar_verdicts.jsonl` is also red.
Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- `make demo-run-live`.

Done when:
- the unit tests pass;
- the re-committed verdict file has GOSSIP `"green"` at this commit's sha;
- ISSUE-228 is archived;
- `make check` is green.

LOC: about +20 non-test. ✅ AUTO (T25.3, 2026-10-22)

- [x] **T25.4** FEEL: a world event moves the emotion of NPCs who witness it (ISSUE-201)
Files:
- the events/world-state route handler that `EventFire` calls (`demo_game/runners/run_scenes.py:91-104`
  shows which route; find its handler under `src/npc_engine/api/routes/`);
- `src/npc_engine/engines/emotion/emotion_updater.py` :101-124 (`apply_event_shock`);
- `src/npc_engine/engines/emotion/emotion_store.py` :26-40;
- tests;
- `evals/pillar_verdicts.jsonl`.

Spec: in review §4, Aldric stays `neutral 0/0` after the market fire. The cause:
- `EventFire` only PUTs world-state conditions;
- `apply_event_shock` has one caller, the gossip handler (`gossip_handler.py:338-346`), and that path
  covers gossip receivers only;
- `EmotionStore` is in-process memory with a neutral default, so nothing writes it on a world event
  (ISSUE-201).

Call `apply_event_shock` for NPCs at the event's location when a world event or condition is applied,
using the existing severity threshold. Add `npc_id` to the updater's signature only if this needs it
(DEC-326). Rules:
- it is deterministic, with no new LLM call (rule 8);
- it must go through the same route the demo and Unreal use (DEC-299);
- a `graph-schema` change is not pre-approved. If an emotion property must persist on the node, halt
  `needs-decision`.

RED anchor: a route-level unit test fails today: applying a severe event at Aldric's location must leave
his emotion non-neutral. The FEEL line in `evals/pillar_verdicts.jsonl` is also red.
Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- `make demo-run-live`.

Done when:
- the test passes;
- the re-committed verdict file has FEEL `"green"`, at 2 of 3 or better, at this commit's sha;
- ISSUE-201 is archived;
- `make check` is green.

LOC: about +60 non-test. ✅ AUTO (T25.4, 2026-10-22)

- [x] **T25.5** REMEMBER: dialogue moves relationships
Files:
- `src/npc_engine/engines/dialogue/dialogue_models.py` :74-79,129;
- `src/npc_engine/engines/dialogue/dialogue_handler.py` :271-280;
- `src/npc_engine/graph/dialogue/dialogue_repository.py` :85-160;
- `src/npc_engine/prompts/dialogue/system_v1.yaml` :316;
- tests;
- `evals/pillar_verdicts.jsonl`.

Spec: all 11 live `llm_response` lines carried `relation_deltas {0,0,0}` (review §4). The evidence so far:
- the prompt rule at `system_v1.yaml:316` mentions only trust and affection;
- `RelationDeltas` defaults to 0 with a range of ±15;
- the application at `dialogue_handler.py:271-280` is skipped at canned degradation;
- an out-of-range value probably fails validation and falls back to zeros. This is unverified, so verify
  it first, on the stack, from the transcript.

Fix the root cause the transcript shows. The likely fixes:
- clamp instead of rejecting;
- give the prompt rule a concrete example per field, `fear` included.

The prompt edit moves `dialogue_prompt_hash`, which is expected (DEC-305).
RED anchor:
- a unit test fails today: an out-of-range delta from a stub LLM must be clamped and applied, not zeroed;
- the REMEMBER-delta part of the REMEMBER line in `evals/pillar_verdicts.jsonl` is red.

Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- `make demo-run-live`.

Done when:
- the test passes;
- the re-committed verdict file shows the REMEMBER relation-delta check green at 2 of 3 or better,
  at this commit's sha;
- `make check` is green.

LOC: about +15 non-test. ✅ AUTO (T25.5, 2026-10-22)

- [x] **T25.6** REMEMBER: consolidation fires from config, and its failure is visible
Files:
- `src/npc_engine/api/dependencies_advanced/progression.py` :104;
- `src/npc_engine/api/routes/knowledge/memories.py` :93,283 (the route that ignores `body.turn_threshold`);
- `src/npc_engine/engines/memory_consolidation/memory_consolidation_engine.py` :112-114;
- `src/npc_engine/config.py` :269;
- `demo_game/runners/run.py` (`LLMCache`), `demo_game/runners/run_scenes.py` (`MemoryConsolidate`), `demo_game/runners/pillars.py`;
- tests;
- `evals/pillar_verdicts.jsonl`.

Spec: ACT 4 prints "Turn threshold not met" (review §4). Causes:
- the engine is built with a hard-coded `turn_threshold=5` (`progression.py:104`), while
  `CONSOLIDATION_TURN_THRESHOLD=10` (`config.py:269`) is read only by the dashboard;
- the route ignores `body.turn_threshold`, and the request model's own default (5) would override config;
- Mira has 1 dialogue before ACT 4, and a warm demo disk cache serves even that one without reaching the engine (DEC-328);
- the engine returns `None` on LLM failure, so the message conflates two causes.

Fix them:
- read the config value in `progression.py` (one source, rule 3); the request field defaults to `None`;
- honour `body.turn_threshold`;
- return a distinct status on LLM failure;
- pass `turn_threshold` in the scene's request, and make the pillar eval bypass the disk cache (DEC-328).

*Amended 2026-11-16:* finished interactively after the 2026-10-22 night was interrupted mid-task. The
LOC ratchet moves to the new last task of the phase (T25.10).
RED anchor: unit tests fail today:
- the route must pass `body.turn_threshold` to the engine, and `None` when omitted;
- an LLM failure must not report "Turn threshold not met";
- the pillar eval's runner must use a disabled cache.
Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- `make demo-run-live`.

Done when:
- the tests pass;
- a live run with the cache bypassed prints "Memory node created" at ACT 4;
- `make check` is green.

LOC: about +10 non-test. Phase T25 total ≈ −120 (T25.1 funds T25.2-T25.10). ✅ AUTO (T25.6, 2026-11-16)

*T25.7–T25.10 were added on 2026-11-16, after an audit of T25.2–T25.5 (owner: fix the high findings before
relaunch). They are done interactively, not by the loop.*

- [x] **T25.7** WORLD: NPCs have homes, and a move to a missing location is a no-op
Files:
- `src/npc_engine/type_registry/base_nodes/character.yaml`;
- `src/npc_engine/graph/scheduling/routine_queries.py` (`CYPHER_UPDATE_LOCATED_AT`, `CYPHER_GET_SCHEDULED_CHARACTERS`);
- `src/npc_engine/engines/routine/routine_engine.py` (`_resolve_target`);
- `demo_game/seeds/seed_builders.py` (`build_npc_payload`), `demo_game/seeds/seed_world_data.py` (Nel's hunger);
- tests in `tests/unit/engines/`, `tests/integration/`, `demo_game/tests/seeds/`.

Spec: two writers send NPCs to the location id `"home"`: the low-valence dialogue override
(`dialogue_handler.py`) and the event disruption rules (`disruption_rules.yaml`). No Location `home` exists and
Characters had no home field. `CYPHER_UPDATE_LOCATED_AT` deleted the old edge before matching the destination,
so the NPC lost its `LOCATED_AT` edge for the override's duration, although its docstring promised a no-op.
T25.2 also raised Nel's hunger seed from 40 to 90 to keep her at the tavern. Her move to the market is correct
need-driven behaviour, and the bump did not hold (WORLD red at `90c800c6`).

Fix (owner, 2026-11-16):
- Character gains an optional `home_location_id`. The seed sets it to each NPC's seeded start location
  (`build_npc_payload` already receives it).
- The routine engine resolves an override to `"home"` through `home_location_id`. With no home, it skips the move.
- `CYPHER_UPDATE_LOCATED_AT` matches the destination before deleting anything.
- Nel's hunger seed returns to 40.

The richer design (several "safe places", leaving home when upset, a mover choosing the destination) is
recorded as an issue, not built.
RED anchor:
- a routine-engine unit test where an override to `"home"` moves the NPC to its `home_location_id`;
- an integration test where moving to a missing location keeps the old edge;
- a seed test where every NPC payload's `home_location_id` is its `LOCATED_AT` location.

Validation: targeted pytest; `make check`; the integration test against the eval Neo4j. Done when they pass.
LOC: about +15 non-test. ✅ AUTO (T25.7, 2026-11-16)

- [x] **T25.8** FEEL: shock only newly active events, and never 500 after the write
Files: `src/npc_engine/api/routes/admin/graph.py` (`patch_world_state`); `tests/unit/api/test_world_state_event_shock.py`.

Spec: T25.4 shocked NPCs for every condition in the PATCH body. `EventFire` resends the full list each time,
so repeated PATCHes stacked shocks. A shock failure escaped after the world-state write had landed (a 500,
and a client retry shocks again). `active_conditions` was read unchecked, so a string was iterated
character by character.

Fix:
- shock only the conditions absent from the node before the PATCH;
- validate `active_conditions` as `list[str]` (422 otherwise);
- return a shock failure as an `EVENT_SHOCK_FAILED` warning in `meta`, logged with the request id;
- use `removesuffix`.

RED anchor: unit tests for a repeated PATCH (one shock), an already-active condition (no shock), a failing
shock (200 plus a warning), and malformed conditions (422).
Validation: targeted pytest; `make check`. LOC: about +40 non-test. ✅ AUTO (T25.8, 2026-11-16)

- [ ] **T25.9** Pillar checks that tell the bugs apart
Files: `demo_game/runners/pillars.py`; `demo_game/tests/runners/` (checks and fixtures); `evals/pillar_verdicts.jsonl`.

Spec: the audit found GOSSIP and FEEL green before T25.3 and T25.4 changed anything, and REMEMBER-delta green
on `interaction_count > 0`, which every turn increments. Each check reads one value after the run, so it cannot
see a change.

Fix:
- take baseline reads before the demo runs; the transcript order tells baseline from after;
- REMEMBER-delta: trust, fear or affection differ from the baseline;
- FEEL: the witness's emotion differs from the baseline;
- GOSSIP: hop-2 distortion is above 0 and at least hop-1's;
- WORLD (owner, 2026-11-16): every NPC is at its seeded location before the first tick. After the run, an
  NPC that moved has `arrived_at_tick > 0` and is not the global snap;
- `check_world` stays within 40 lines and 3 levels of nesting; `main()` loses its duplicate branch;
  `EXIT_HARNESS_ERROR` becomes reachable.

The verdict file records the sha the stack was built from, which is the parent of the commit that holds it.
A commit cannot contain its own sha (DEC-329).
RED anchor: fixture tests where a transcript showing each old bug is red, and a fixed one is green.

Validation: a live red→green proof. Run the working-tree `pillars.py` against stacks built at `72675ac7`
(pre-T25.2), `7d2103a1` (pre-T25.3/T25.4) and `2c939d5a` (pre-T25.5); each pillar is red where its fix is
missing, and every pillar is green at HEAD. Raw outputs are cited in the commit body. Done when that holds and
`make check` is green.

- [ ] **T25.10** GOSSIP mispairing test that can fail, and the phase's LOC ratchet
Files: `tests/integration/` (gossip batch); `tests/unit/graph/test_gossip_batch_mispairing.py`; `scripts/loc_baseline.txt`.

Spec: `_MispairingAwareSession` picked its answer by matching the query string, so it could not catch a
mispairing. Replace it with an integration test against Neo4j: a batch where one candidate has a null summary.
This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
Done when the integration test passes against the eval Neo4j, `make check` is green, and the baseline total
equals the measured count.

- [x] **T25.11** REMEMBER/FEEL: the model's grammar requires every field it authors
Files: `src/npc_engine/engines/dialogue/dialogue_models.py` (`generation_json_schema`), `engines/dialogue/llm_client.py`;
`tests/unit/engines/test_dialogue_generation_schema.py`.

Spec: found while writing T25.9's stricter REMEMBER check (DEC-330). Four live dialogues left Mira→player at
0/0/0. The grammar required only `npc_response`, and under the full prompt qwen2.5:7b skipped
`relation_deltas`, `mood_update` and `facial_expression` in 3 of 3 replays.
Fix: send a grammar whose `required` lists name every authored field, and the delta, expression and action
keys. The public `DialogueResponse` schema is unchanged.
RED anchor: the grammar's `required` covers every authored field, and the client sends that grammar.
Validation: targeted pytest; `make check`; the T25.9 live run (REMEMBER-delta green, canned replies counted). ✅ AUTO (T25.11, 2026-11-16)

- [x] **T25.12** GOSSIP: the allowlist applies before the pair cut, and a sharer tells something new
Files: `src/npc_engine/engines/gossip/pair_selector.py`, `engines/gossip/gossip_handler.py`,
`src/npc_engine/graph/gossip/gossip_batch_queries.py`; tests.

Spec: also found during T25.9.
- `run_tick` took the global top `max_pairs`, then filtered by `npc_ids`. The determinism beat
  (`npc_ids=[sorn, mira]`, `max_pairs=1`) therefore always got `[]`, and `seeds_used` was `{}` (ISSUE-380).
- `CYPHER_BATCH_EVENT_TRUST` picked the sharer's canonical, newest event whatever the receiver knew. Every NPC
  on the demo seed knows one public event, so pairs re-told it and the war rumour never left Mira.

Fix:
- filter by the allowlist before ranking;
- order a sharer's events by "the receiver does not know it" first; retelling still happens when nothing is new.

RED anchor: unit tests for the allowlist (selector and handler); an integration test in which the fresh event
beats the canonical known one.
Validation: targeted pytest; integration tests against the eval Neo4j; `make check`; the T25.9 live run
(DETERMINISM gets real seeds). ✅ AUTO (T25.12, 2026-11-16)

---

# SPRINT 16 — One contract Unreal can trust, and a ledger that tells the truth

**Self-contained goal:**
- one committed contract file, guarded by the existing type-level gate (DEC-324);
- one dialogue payload on HTTP and WS (DEC-325);
- `contract_version` served on every response (DEC-300);
- the three claims ticked without evidence are re-measured on the stack (DEC-308, DEC-318).

### Phase T26

- [ ] **T26.1** Delete the unreachable `stream` chain and the docs that describe it (ISSUE-322, ISSUE-299)
Pre-approved: file-deletion, public-interface · owner 2026-10-21 · DEC-311
Files:
- `src/npc_engine/engines/dialogue/dialogue_handler.py` :371-391;
- `src/npc_engine/engines/llm/llm_client.py` :214-250;
- the `stream` methods in `admission_control.py` :219-247, `mock_adapter.py` :201-230,
  `ollama_adapter.py` :222-292 and `openai_adapter.py` :220-257;
- `LLMStreamProtocol` in `protocols.py` :111-125;
- the matching tests;
- `docs/API.md` and `docs/ARCHITECTURE.md` (the streaming-frame sections).

Spec: ISSUE-322.
- `DialogueHandler.stream` has no caller. It is the only consumer of `stream_text`, which is the only
  consumer of the adapters' `stream` methods.
- The WS route awaits `handler.handle` in full (`dialogue_ws.py:293`).
- Delete the chain.
- Correct the docs (ISSUE-299). They must describe the frames the code sends: `token`, `done`, `error`
  and `proactive_line`.

RED anchor: `git grep -n "def stream\b\|stream_text\|LLMStreamProtocol" -- src` prints lines today and must print none.
Validation:
- `pytest tests/unit -q -k "llm or dialogue"`;
- `make check-dip-threshold`;
- `make check`.

Done when:
- the grep prints nothing;
- ISSUE-322 and ISSUE-299 are archived;
- `make check` is green.

LOC: about −240 non-test (src).

- [ ] **T26.2** One contract file under the existing gate (DEC-324)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- a new `contracts/openapi_v1.json`;
- `scripts/check_api_contract.py`, `scripts/api_contract_extractor.py`;
- delete `scripts/api_contract_baseline.json` and `scripts/check_api_stability.py` (163), plus its baseline file and tests;
- `Makefile` :427-428,447-448,489;
- `project-harness/HARNESS_GATES.md`.

Spec: DEC-324, superseding DEC-298's mechanics.
- `check-api-contract` is already type-level and additive-pass (DEC-254).
- Make the committed raw `app.openapi()` dump the gate's baseline: `--update` writes the dump, and the
  check extracts the baseline contract from the dump.
- Delete the second baseline file.
- Delete `check-api-stability`, a strict subset of this gate (ISSUE-269).
- Add no new dependency.

RED anchor: `test -f contracts/openapi_v1.json` fails today, and `ls scripts/check_api_stability.py` succeeds.
Validation:
- `make check-api-contract`;
- a scratch test that removes a field from a copy of `DialogueResponse` must make the differ report a break;
- `make check`.

Done when:
- `contracts/openapi_v1.json` is committed;
- `git ls-files scripts/api_contract_baseline.json scripts/check_api_stability.py` prints nothing;
- `make check-api-contract` passes;
- ISSUE-269 is archived;
- `make check` is green.

LOC: about −150 non-test (scripts).

- [ ] **T26.3** WS `done.data` is the full `DialogueResponse` (DEC-325)
Pre-approved: public-interface · owner 2026-10-21 · DEC-311
Files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py` :168-192,215,295-296,326, a new
`src/npc_engine/api/routes/dialogue/ws_frames.py`,
`src/npc_engine/engines/proactive_dialogue/models.py` :56-57, `scripts/api_contract_extractor.py`,
`contracts/openapi_v1.json`, and tests.
Spec: DEC-325, amending DEC-299.
1. **Delete the whitelist.** Remove `_build_done_data`'s hand-picked dict (`:168-192`). It drops
   `learned_facts` and `memories_recalled`.
2. **Type the frames.** Define them as one Pydantic discriminated union:
   - `TokenFrame`;
   - `DoneFrame`, whose `data` is `DialogueResponse` plus the WS-only `audio_bytes_b64`;
   - `ErrorFrame`;
   - `ProactiveLineFrame`.
3. **Send through the models.** Send every frame through `model_dump`.
4. **Export the schema.** Write the union's `model_json_schema()` into `contracts/openapi_v1.json`
   under `x-ws-frames`, via the extractor, so the existing differ guards it.
5. **Keep `DialogueGeneration` separate.**
6. **Additive only.** No existing field is removed.

RED anchor: a test fails today: a WS turn's `done.data` keys must equal `DialogueResponse`'s fields plus
`audio_bytes_b64`.
Validation:
- the targeted pytest;
- `make check-api-contract`, re-recorded with `--update` once, because the change is additive;
- `make check`.

Done when:
- the test passes;
- `grep -c "x-ws-frames" contracts/openapi_v1.json` is 1 or more;
- `make check` is green.

LOC: about +40 non-test.

- [ ] **T26.4** Serve `contract_version` (DEC-300, DEC-324)
Pre-approved: public-interface · owner 2026-10-21 · DEC-311
Files: `src/npc_engine/api/routes/admin/system.py` :54, the app middleware module, `src/npc_engine/config.py`,
`contracts/openapi_v1.json`, `docs/API.md`, and tests.
Spec:
- Add `CONTRACT_VERSION = 1` as one named constant.
- Serve it as `contract_version` in the `GET /health` body, and as an `X-Contract-Version` header on every
  response, through one middleware (DEC-324).
- State the policy in `docs/API.md` in 3 lines: additive changes are free; removing, renaming or retyping
  bumps the version and needs a DECISIONS entry.

RED anchor: a test fails today: any route's response must carry `X-Contract-Version: 1`, and `/health`
must carry `contract_version: 1`.
Validation:
- the targeted pytest;
- `make check-api-contract`;
- `make check`.

Done when: the test passes, `contracts/openapi_v1.json` shows `contract_version` in the health schema, and
`make check` is green.
LOC: about +20 non-test.

- [ ] **T26.5** Re-measure DEC-273 on the stack, with the raw output committed
Files: `project-harness/DECISIONS.md` (DEC-273) and a new `project-harness/evidence/T26.5_dec273.txt`.
Spec: DEC-308 and DEC-318 re-issue T16.1. T16.1's numbers were copied from
`archive/review-fixes/evidence/L9.md:128-134` (review §3.1), and nothing was measured.
1. Rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`.
2. With the tick frozen and one session, send 4 dialogue turns.
3. Capture `GET /health` and `GET /v1/admin/system/metrics` before and after.
4. Commit the raw output, unedited, to the evidence file.
5. Amend DEC-273 with a new dated paragraph citing the file. Take the numbers from the file only.

RED anchor: `test -f project-harness/evidence/T26.5_dec273.txt` fails today.
Validation:
- `grep -c '"version"' project-harness/evidence/T26.5_dec273.txt` is 1 or more;
- `make check-ledger-ids`;
- `make check`.

Done when:
- the evidence file is committed and its `/health` `version` equals this task's parent sha;
- DEC-273 has an amendment citing `evidence/T26.5_dec273.txt`;
- `make check` is green.

LOC: 0 non-test.

- [ ] **T26.6** Stale-image check and live `/standings` GET, with the raw output committed
Files: a new `project-harness/evidence/T26.6_live_checks.txt`, and `project-harness/ISSUES.md` (only if a
check fails).
Spec: DEC-308 and DEC-318 re-issue T16.4 and T15.4.
1. **Stale image.** Rebuild the eval stack at `HEAD~1` with `bash scripts/eval_stack_at.sh HEAD~1 --reset`.
   Run one eval resolution from HEAD (`resolve_run_config`) against it. Capture `git_sha` and
   `engine_build_sha` differing. Then rebuild at HEAD and capture them matching.
2. **Standings.** `GET /v1/admin/factions/{id}/standings` must return 200, with `target` as a string and
   `target_name` present (ISSUE-354's fix).
3. **Record.** Commit every command and its raw output to the evidence file. If a check fails, log an
   issue with the evidence and still commit the file. Tick only if both checks pass.

This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: `test -f project-harness/evidence/T26.6_live_checks.txt` fails today.
Validation: the two checks above, then `make check`.
Done when:
- the evidence file is committed, holding both sha pairs (differing, then matching) and a `200` standings
  body with `target_name`;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: 0 non-test. Phase T26 total ≈ −340.

---

# SPRINT 17 — Seams and dead surface

**Self-contained goal:**
- a node label is declared once;
- one fallback path for a failed LLM call;
- `graph/` carries no public symbol nothing calls (DEC-303, review §7.2).

### Phase T28

- [ ] **T28.1** Delete the dead public symbols in `graph/`
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: `src/npc_engine/graph/**`, the matching tests, and `scripts/rules_baseline.txt` if rows resolve.
**Excludes** the three political writer files, which T29.1 handles.
Spec: review §7.2 counts 68 dead public symbols (about 1,467 LOC), 50 of them in `graph/`.
- **Finding them.** For each module-level public `def` or `class` under `src/npc_engine/graph/`, check
  `git grep -w <name> -- src scripts evals demo_game e2e ':!<its own file>'`. No hit means dead.
- **Not dead:** names used through decorators, registries, `__all__` or string lookups. Check those by
  hand.
- Delete the dead ones, and any test that only exercises them.
- List every deleted symbol in the commit body.

RED anchor: before deleting, write the candidate list to the commit body draft. Each name's grep must
print nothing outside its own file today. This is a deletion anchor: the census is green before and after.
Validation:
- `make check-dead-surface`;
- `pytest tests/unit/graph -q`;
- `make check`.

Done when:
- the commit body lists the deleted symbols;
- `git grep -w <name> -- src` prints nothing for each;
- the phase's running LOC is at least 500 below its start;
- `make check` is green.

LOC: about −600 non-test (src).

- [ ] **T28.2** One LLM-fallback path, one default payload
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- `src/npc_engine/config.py` :128-129,305;
- `src/npc_engine/engines/llm/llm_client.py` :178-189;
- `src/npc_engine/engines/llm/mock_adapter.py` :18-24;
- `src/npc_engine/engines/dialogue/degradation.py` :44-70;
- `src/npc_engine/engines/dialogue/dialogue_handler.py` :179,221;
- `src/npc_engine/utils/errors.py` :308;
- `src/npc_engine/api/.../dashboard_models.py` :62;
- `.env.example`;
- tests.

Spec: rule 7. There are two "LLM failed → canned line" stores:
- `LLM_FALLBACK_PATH` (JSON, `llm_client.py:178-189`);
- `CANNED_RESPONSES_DIR` (YAML, `degradation.py:44-70`).

The default payload is also hand-written three times: `llm_client.py:183-189`, `mock_adapter.py:18-24`
and `degradation.py:62-69`. Make these changes:
- keep the YAML path and delete the JSON one with its setting;
- define the default payload once, in `degradation.py`, and import it in the other two places;
- delete `TokenBudgetExceededError` (no references);
- delete `CLIQUE_FORMATION_TICK_INTERVAL` and its dashboard row (its engine was deleted).

RED anchor: `git grep -n "LLM_FALLBACK_PATH\|TokenBudgetExceededError\|CLIQUE_FORMATION_TICK_INTERVAL" -- src .env.example`
prints lines today and must print none.
Validation:
- `pytest tests/unit -q -k "llm or degradation or dialogue"`;
- `make check-dead-surface`;
- `make check`.

Done when: the grep prints nothing, `grep -c "I need a moment to think" -r src` is 1, and `make check` is green.
LOC: about −80 non-test.

- [ ] **T28.3** Declare each node label once (DEC-303)
Files:
- `src/npc_engine/graph/infra/labels.py` :12-19;
- `src/npc_engine/graph/generic/generic_graph_utils.py` :22-30;
- `src/npc_engine/graph/infra/schema_bootstrap.py` :23-31;
- `src/npc_engine/graph/politics/political_queries.py` :27;
- `src/npc_engine/type_registry/base_nodes/title.yaml` :3;
- tests;
- `project-harness/ISSUES.md`.

Spec: DEC-303. A node label is declared in four places, five counting `political_queries.py:27`.
- Make `graph/infra/labels.py` the one Python declaration.
- `BASE_NODE_LABELS` and `_CORE_LABELS` derive from it.
- The YAML `label:` stays the type-registry contract, with a test asserting it agrees with `labels.py`.
- ISSUE-315 (tick-engine registration in 4 files / 9 edits) closes **by design** per DEC-303. Archive it
  with that note and its recorded cost.

This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: a test fails today: every label in `BASE_NODE_LABELS` and `_CORE_LABELS` must be imported from
`labels.py` rather than defined as a literal, and every base-node YAML `label:` must be in `labels.py`.
Validation:
- `pytest tests/unit/graph -q`;
- `make check`.

Done when:
- the test passes;
- `git grep -n '"Title"' -- src/npc_engine/graph` prints only `labels.py`;
- ISSUE-315 is archived as by-design;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: about −20 non-test. Phase T28 total ≈ −700.

---

# SPRINT 18 — Judge repair, the half the loop can do

**Self-contained goal:** everything in the judge repair (DEC-302) that does not need the owner's labels
is done. The roster is right, the adequacy test stops pinning old counts, and a labelling batch of
failure-designed cases waits for the owner (DEC-322). The owner's labelling, T18.1 and T18.2 sit under
"Owner work".

### Phase T17

- [ ] **T17.1** Fix the scorer roster and delete the dead draft-case path (ISSUE-295, ISSUE-282, ISSUE-148)
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- delete `evals/case_drafts.py` (359) and its tests;
- `evals/__main__.py` :126-127 and `Makefile` :798 (the `draft-cases` verb and target);
- `evals/calibration.py` :817-821;
- `scripts/check_label_adequacy.py` :68;
- `evals/label_export_stratified.py` :44;
- tests in `tests/unit/evals/`.

Spec: the diagnosis is done (review §5.1). All five scorers are refused, and two of the refusals are
roster artefacts:
- `calibration.py:817-821` and `check_label_adequacy.py:68` take the roster from the labels file
  (`dict.fromkeys(r.scorer for r in rows)`);
- so `refusal_judge` (retired, DEC-269) and `anti_hallucination_grounded` (out of `IN_SCOPE_SCORERS`)
  are still calibrated and counted (ISSUE-295);
- `family_size` counts every scorer with 2 or more human verdicts, not every adequacy-passing one (ISSUE-282).

Fix it:
- take the roster from one place, `IN_SCOPE_SCORERS` (`label_export_stratified.py:44`), in both;
- count `family_size` over adequacy-passing scorers;
- delete `case_drafts.py`. It cannot reach the grounded edges it exists to read (ISSUE-148), and it has
  no caller beyond its own verb.

Do not write under `evals/calibration/` (DEC-316).
RED anchor: unit tests fail today:
- a labels fixture holding a retired scorer must not appear in the adequacy roster;
- `family_size` with one adequate and two inadequate scorers must equal the one-scorer value.

Validation:
- `pytest tests/unit/evals -q`;
- `python scripts/check_label_adequacy.py`, whose output must list exactly `affirms_judge`, `commits_judge` and `tone_judge`;
- `make check-evals-rules`;
- `make check`.

Done when:
- the tests pass;
- `check_label_adequacy.py` lists exactly the three in-scope scorers;
- ISSUE-295, ISSUE-282 and ISSUE-148 are archived;
- `make check` is green.

LOC: about −340 non-test (evals).

- [ ] **T17.2** Stop `test_label_adequacy` pinning today's label counts (DEC-312 #2)
Files: `tests/unit/evals/test_label_adequacy.py` :70-89.
Spec: `:70-89` asserts that `tone_judge` is refused with `minority_n == 7` and `n_clusters == 45` on the
real committed labels. It goes red the moment the owner's labelling succeeds, which is a tripwire that
fires on success.
- Replace it with an invariant over the real file: every in-scope scorer has a verdict, and a refused
  scorer's reason names the floor it misses.
- Keep the fixture-based tests that pin the thresholds (`MIN_MINORITY_LABELS=25`, `MIN_CASE_CLUSTERS=10`).

RED anchor: a fixture-based test fails today: a labels fixture with 25 or more minority labels in 10 or more
clusters must pass adequacy, which shows the new invariant is not tied to today's counts.
Validation:
- `pytest tests/unit/evals/test_label_adequacy.py -v`;
- `make check`.

Done when: `grep -c "== 7\|== 45" tests/unit/evals/test_label_adequacy.py` is 0, the file's tests pass,
and `make check` is green.
LOC: 0 non-test.

- [ ] **T17.3** Author failure-designed cases, generate them on the stack, and export the labelling batch
Files:
- new case YAML under the eval case directory, the same place existing judged cases live;
- a new `evals/generations/<new_gen_id>/`;
- a new `evals/label_batches/<new_gen_id>/`;
- `project-harness/ISSUES.md`.

Spec: DEC-302 and DEC-322. Labels are short of the minority floor by 18 (tone), 17 (affirms) and 25
(commits) (review §5.1), and failures sit in only 3-5 clusters per scorer.
1. **Author.** Write cases built to elicit each failure: a tone mismatch, a false affirmation, a
   non-commitment. Spread them over 10 or more new clusters per scorer, with at least 2× each shortfall,
   so the owner can reject weak ones.
2. **Generate.** Rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`.
   Generate into a **new** generation dir, never `k3_73e6c36` (DEC-316).
3. **Export.**
   `make label-export-stratified TRANSCRIPT=evals/generations/<id>/outputs.jsonl OUT_DIR=evals/label_batches/<id>`.
   Never use the default `evals/calibration/...` path, which is frozen.
4. **Hand over.** Write the batch path into the "Owner work" section of this file, on the labelling line.

This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: `ls evals/label_batches/` fails today.
Validation:
- the export command;
- for each of `tone_judge`, `affirms_judge` and `commits_judge`, the batch dir holds 2× that scorer's
  shortfall in items;
- `make check`.

Done when:
- `evals/label_batches/<id>/{tone_judge,affirms_judge,commits_judge}/` exist, with at least 36, 34 and 50 items;
- the Owner-work labelling line names `<id>`;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: 0 non-test. Phase T17 total ≈ −340.

---

# SPRINT 19 — The prompt parts that need no judged score

**Self-contained goal:** the dialogue prompt has one numbering, no dead trigger, guidance for every
generated field and one tone system, and its hash covers exactly what changes behaviour (DEC-305,
DEC-306, DEC-307). Rule 16 vs Rule 2 (T19.1) and the re-baseline (T20.2) are owner work.

### Phase T19

- [ ] **T19.2** Delete the dead public symbols outside `graph/`
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files: `src/npc_engine/{engines,retrieval,services,api,cache,utils}/**`, the matching tests, and
`scripts/rules_baseline.txt` if rows resolve.
Spec: these are the remaining dead public symbols of review §7.2's 68, after T28.1. The method is the same
as T28.1: a `git grep -w` census, decorator and registry names checked by hand, and every deleted symbol
listed in the commit body. This deletion funds the rest of the phase (DEC-320).
RED anchor: each listed name's grep prints nothing outside its own file today. This is a deletion anchor.
Validation:
- `make check-dead-surface`;
- `pytest tests/unit -q`;
- `make check`.

Done when:
- the commit body lists the deleted symbols, and `git grep -w <name> -- src` prints nothing for each;
- the phase's running LOC is at least 250 below its start;
- `make check` is green.

LOC: about −300 non-test.

- [ ] **T19.3** Renumber the two rule 17s, and rewrite Rule 11's trigger (DEC-305, DEC-306)
Files:
- `src/npc_engine/prompts/dialogue/system_v1.yaml` :181,283;
- `src/npc_engine/prompts/dialogue/system_state_v1.yaml` :2;
- the cross-references at `config_prompt_window.py:48`, `context_slots.py:108-109,148`,
  `context_tier_builders.py:90` and `prompt_builder.py:164,195`;
- eval case YAML that cites a rule number;
- tests.

Spec:
- **ISSUE-325.** Give `system_state_v1.yaml`'s rule the next free number, and update every cross-reference.
- **DEC-306.** Rule 11 fires on `available_interactions`, which nothing produces (`system_v1.yaml:181`).
  Rewrite its trigger to fire on context the prompt already carries: an active quest, or a
  trade-capable NPC. Keep its body. Build no producer.

RED anchor: two tests fail today:
- a prompt-render test asserting no rule number appears twice across the rendered system prompt;
- a test asserting `available_interactions` is not in any prompt YAML.

Validation:
- the targeted pytest;
- `make check-dead-surface`;
- `make check`.

Done when:
- both tests pass;
- `git grep -n "available_interactions" -- src/npc_engine/prompts` prints nothing;
- ISSUE-325 and ISSUE-293 are archived;
- `make check` is green.

LOC: 0 non-test.

- [ ] **T19.4** Give the prompt guidance for every field the model generates
Files: `src/npc_engine/prompts/dialogue/system_v1.yaml` (Output rules, about :310-322), and tests.
Spec: review §9 T9. Of the 6 fields the model generates, `facial_expression` and `mood_update` get
**zero** guidance, and `relation_deltas.fear` is missing from the Output rules. `facial_expression`
reaches Unreal (DEC-298).
- Add one line per field: the allowed values, sourced from the schema enum, and when to use each.
- Do not restate schema-enforced constraints (ISSUE-330).

RED anchor: a test fails today: every field of `DialogueGeneration` must be named in the Output rules.
Validation:
- the targeted pytest;
- `make check`.

Done when: the test passes and `make check` is green.
LOC: 0 non-test.

- [ ] **T19.5** Resolve the tone band server-side: one system, not two (ISSUE-328)
Pre-approved: public-interface · owner 2026-10-21 · DEC-311
Files:
- `src/npc_engine/prompts/dialogue/system_v1.yaml` :36-50 (Rule 2), :269 (Rule 16);
- `src/npc_engine/graph/reputation/reputation_queries.py` :60-87;
- `src/npc_engine/engines/relationship/standing.py` :43-86;
- `src/npc_engine/engines/dialogue/prompt_builder_standing.py`;
- `src/npc_engine/services/context_slots.py`;
- tests.

Spec: ISSUE-328. Two independent five-band tone systems do one job:
- Rule 2 uses reputation bands (`reputation_queries.py:64-87`);
- Rule 16 uses `derive_standing` (`standing.py:61`).

Make one change:
- resolve one band server-side, with `derive_standing` as the survivor;
- pass the prompt one resolved answer;
- delete the other band computation and its prompt rule text.

Rule 8: deterministic beats model judgement. **Do not** decide the Rule 16 vs Rule 2 tie-break for
conflicting signals. That is T19.1, owner work. Where the two disagree today, keep `derive_standing`'s
answer and note the disagreement in the commit.
RED anchor: a test fails today: the rendered prompt must contain exactly one tone band, and the reputation
band labels must not appear in any prompt YAML.
Validation:
- the targeted pytest;
- `make check-api-contract`;
- `make check`.

Done when: the test passes, ISSUE-328 is archived, and `make check` is green.
LOC: about −30 non-test.

- [ ] **T20.1** Hash exactly the dialogue prompt's four inputs (DEC-307)
Files: `evals/_run_config_hashing.py` :25,148-167, `evals/run_config.py` :447,
`project-harness/DECISIONS.md` (a migration note), and tests.
Spec: DEC-307. `dialogue_prompt_hash` hashes every `*.yaml` under the prompts dir, so editing an unrelated
prompt breaks comparability (L12-14).
- Hash exactly four inputs: `system_v1`, `system_state_v1`, `moderation/content_ceiling_v1`, and the
  `llm_config` `prompt.version`.
- The hash is not in `ComparabilityKey` (`evals/comparability.py:30-55`), so no baseline is orphaned (DEC-305).
- Write a short DECISIONS migration note: old recorded hashes will not reproduce.

This is the phase's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: unit tests fail today:
- editing an unrelated prompt YAML must not change the hash;
- editing `moderation/content_ceiling_v1.yaml` must change it.

Validation:
- `pytest tests/unit/evals -q`;
- `make check-evals-rules`;
- `make check`.

Done when:
- both tests pass;
- the migration note exists and cites DEC-307;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: about +10 non-test. Phase T19 total ≈ −320.

---

# SPRINT 20 — Stop the tick and aborted turns from starving the player

**Self-contained goal:**
- the per-tick LLM caps hold;
- an aborted WS turn stops spending the model;
- first-turn latency is measured honestly against T7.5's 2x target, which was waived into this sprint (DEC-308).

### Phase T29

- [ ] **T29.1** Delete the dead political writers and the unused Redis runtime
Pre-approved: file-deletion · owner 2026-10-21 · DEC-311
Files:
- delete `src/npc_engine/graph/politics/political_leverage_writer.py` (100);
- `political_title_writer.py` (130): delete `grant_title`, and its repository method if that has no caller;
- `political_agenda_writer.py` (111): keep `set_agenda_status`, delete `create_agenda` and `vote_on_agenda`;
- `src/npc_engine/graph/repositories/political_repository.py` :25;
- delete `src/npc_engine/cache/redis_runtime.py` (68);
- `src/npc_engine/main.py` :108,174,235;
- `src/npc_engine/config.py` :118-120;
- `docker-compose.yml` :59-68;
- `pyproject.toml` :17;
- `.env.example` :17-19;
- tests.

Spec:
- **Political writers** (review §7.2). Only `set_agenda_status` is live (`agenda_engine.py:73`).
- **Redis.** `redis_runtime` connects and closes, but nothing reads its client, and
  `REDIS_ENABLED=False` by default. Removing an unused dependency is not a new dependency.
- **Docker.** Do not edit the eval-stack compose project's other services.

These deletions fund T29.2-T29.4 (DEC-320).
RED anchor: `git grep -n "redis_runtime\|political_leverage_writer" -- src` prints lines today and must print none.
Validation:
- `pytest tests/unit -q`;
- `make check-dead-surface`;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset`, which boots without Redis.

Done when:
- the grep prints nothing;
- the eval stack's `/health` returns 200 at this commit's sha;
- `make check` is green.

LOC: about −320 non-test (src).

- [ ] **T29.2** Make the per-tick quest LLM cap hold
Files:
- `src/npc_engine/engines/quest_generation/tick_llm_budget.py` :31;
- `src/npc_engine/api/dependencies_engines/quest.py` :161;
- `src/npc_engine/scheduler/tick_scheduler.py` :544-569,640;
- `src/npc_engine/scheduler/tick_budget_guard.py`;
- tests;
- a new `project-harness/evidence/T29.2_tick_calls.txt`.

Spec: review §4 records one tick making **14** quest LLM calls against `QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK=10`
(`config.py:60`) and `TICK_LLM_CALLS_PER_MINUTE_MAX=6` (`config.py:289`). The scheduler's guard is a
pre-check only (`tick_scheduler.py:544-562`).
- Find why `TickLLMBudget` let 14 through. A likely cause is a budget built per trigger rather than per tick.
- Make the cap a hard per-tick ceiling, checked per call.

RED anchor: a unit test fails today: a tick whose quest triggers want 14 calls must make at most 10.
Validation:
- the targeted pytest;
- `make check`;
- rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`;
- one `clock/advance`;
- capture `llm_backend_calls_total` before and after into the evidence file.

Done when:
- the test passes;
- the evidence file is committed and shows at most 10 quest calls on the first tick;
- `make check` is green.

LOC: about +25 non-test.

- [ ] **T29.3** Stop generating after a WS client disconnects
Files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py` :293,316-322, and tests.
Spec: review §4 shows 6 aborted WS turns still running their LLM calls (`llm_backend_calls_total` 11 → 26).
`handler.handle` is awaited inline (`:293`), and disconnect is detected only after `done` (`:316-322`).
- Run the handle as a task.
- Race it against `websocket.receive` for a disconnect.
- Cancel the task on disconnect.
- Release the slot exactly once. The slot-leak fix must hold (`dialogue_ws.py:51,328-329`).

RED anchor: a test fails today: with a stub handler that sleeps, a client disconnect must cancel it, and
the slot count must return to 0.
Validation:
- the targeted pytest;
- `make check`.

Done when: the test passes, the existing WS slot tests still pass, and `make check` is green.
LOC: about +30 non-test.

- [ ] **T29.4** Measure first-turn latency against T7.5's 2x target, raw output committed
Files: a new `project-harness/evidence/T29.4_first_turn.txt`, `project-harness/DECISIONS.md`, and
`project-harness/ISSUES.md` (if over target).
Spec: DEC-308 waived T7.5, which measured 2.63x against a ≤2x target, into this theme.
1. Rebuild with `bash scripts/eval_stack_at.sh HEAD --reset && make eval-stack-seed`.
2. Measure the first dialogue turn after boot and the median of the next 4 turns.
3. Commit the raw timings.
4. **If the ratio is 2x or below:** add a DECISIONS note closing the waiver.
5. **If it is above 2x:** log an issue with the measurement. Do not tune constants to pass.

This is the phase's last task, and the queue's last task: run `python scripts/check_loc_ratchet.py --update`.
RED anchor: `test -f project-harness/evidence/T29.4_first_turn.txt` fails today.
Validation: the measurement, then `make check`.
Done when:
- the evidence file is committed with the `/health` sha and the five timings;
- either a DECISIONS note (2x or below) or an open issue (above 2x) cites it;
- `scripts/loc_baseline.txt` total equals the measured count;
- `make check` is green.

LOC: 0 non-test. Phase T29 total ≈ −265.

<!-- LOOP:QUEUE end -->

---

## Owner work (outside the fence; the loop never reaches it)

Each item names the date it is due and what it unblocks.

| # | Work | Due | Unblocks |
|---|---|---|---|
| O1 | **Before night 1:** know that the driver starts Neo4j and exports `NEO4J_URI=bolt://localhost:7687` (`loop_compat.sh:170`). `make check`'s integration tests then write to that default-stack Neo4j, as on every earlier night. Keep nothing there you need, or snapshot it first (`make demo-snapshot`). | before night 1 | a safe night 1 |
| O2 | **Night 1:** `bash scripts/expand_loop.sh --max-phases 1` (phase T21 only). In the morning, read `git log loop-night-<date>` and the report. | night 1 | T21.4 live from night 2 |
| O3 | **Each morning:** review the night's commits, then fast-forward `remediation-2026-08` from the loop branch by hand. If preflight refuses because of an `UNVERIFIED` tick, read it, then restart with `--ack`. | daily | the next night |
| O4 | **T17.1 detailing:** done by the roadmap builder on 2026-10-21 (DEC-322). Review the spec. | 2026-10-27 | — |
| O5 | **DemoGame repo:** repoint `Scripts/check_contract_sync.py` at this repo's `contracts/openapi_v1.json`, and drop the hand copy (DEC-298, DEC-324). | within 7 days of T26.2 | the Unreal contract pillar |
| O6 | **Labelling pass:** label the batch T17.3 exports at `evals/label_batches/<id>/`. You need ≥25 minority labels per scorer, in ≥10 clusters (+18 tone, +17 affirms, +25 commits). T17.3 writes `<id>` here. | within 14 days of T17.3 | T18.1 |
| O7 | **T18.1 relabel and freeze, T18.2 re-baseline and sign-off:** write these as a follow-up roadmap once O6 lands. They accept or reject real kappa numbers; affirms (0.530) would be RESTRICTED and commits (0.308) HIDDEN (`docs/SCORER_TRUST_POLICY.md:22-24`). | after O6 | T20.2, the quest slot-fill deletion |
| O8 | **T19.1 tie-break:** decide what wins when Rule 16 (standing) and Rule 2 (reputation) disagree (ISSUE-327). This is a product-behaviour call. T19.5 keeps `derive_standing` meanwhile. | before T18.2 | the prompt revision's last part |
| O9 | **T20.2:** re-baseline the judged evals against the new prompt and publish the delta. | after O7 | — |

### Parked

These are not scheduled. They are recorded so they are not rediscovered as new.
- **Rebuilding the political layer.** It is recoverable from git. Do it only if a studio needs it.
- **Deleting the quest slot-fill LLM call** in favour of `_deterministic_fill` (`quest_generation_engine.py:353`).
  It waits on O7, because quality is not measurable until then.
- **`:TickLease` / `SchedulerState` growth** (ISSUE-335). It needs one retention policy.
- **Memory consolidation asks for JSON through `generate`** rather than `generate_structured` (ISSUE-323).

### Not scheduled (theme T3, evaluator first run)

These are open, have no task, and are kept by DEC-304:
- ISSUE-209 and ISSUE-297: the `.env.example` context-window budget;
- ISSUE-265: a missing model falls back silently to canned replies;
- ISSUE-281: no `SHELL` in the Makefile;
- ISSUE-349: DEMO_SCRIPT describes 5 acts;
- ISSUE-377: ENGINES.md lists deleted engines.

Schedule them in the next roadmap, or fold them into a drain task that touches the same file.
