# NPCSystem — Engine Roadmap

**Status (2026-09-08): the M programme is retired and archived. This roadmap is the T
programme — Trim.** It replaces everything that came before it and is driven entirely by the
2026-09-07 full review (`REVIEW_FINDINGS.md`, `review-fixes/`).

## The goal, in priority order

1. **It works.** A studio evaluator can boot the stack, play the demo end to end, and see NPCs
   remember, feel, and gossip.
2. **It is simple.** A very close second. Less code is better than more code. A feature nobody
   can reach is not a feature — it is a liability with a docstring.

When (1) and (2) conflict, (1) wins. When (2) conflicts with anything else — elegance,
completeness, future-proofing, "we might need it" — **(2) wins.**

## Why this programme exists

The 2026-09-07 review ran ten lenses over the engine and the demo. `make check` was green,
mypy was 0 across 637 files, coverage was 88.13%, 4,571 tests passed — and:

- the demo died after 5 dialogue turns (a WebSocket slot leak),
- the demo **lost itself 3 seconds after seeding**, before a player could type,
- 27 engines ran per tick, every `last_error` null, and only **6 did any work**,
- 34 of 44 protocols failed the repo's own DIP rule,
- and nothing arbitrated the single resident LLM against a tick that can issue ~84 model calls.

Every one of those was invisible to every gate. The lesson this programme is built on: **a gate
that green-lights a broken product is worse than no gate**, and the cheapest way to make a system
correct is to have less of it.

## Baseline, measured 2026-09-08 at HEAD `acbb36aa`

| Area | LOC | Files |
|---|---:|---:|
| `tests/` | 87,566 | 599 |
| `src/npc_engine/` | 69,247 | 637 |
| `demo_game/` | 36,937 | 184 |
| `evals/` | 23,130 | 123 |
| `scripts/` | 9,477 | 55 |
| `e2e/` | 7,605 | 51 |
| **total** | **233,962** | **1,649** |

Within `src`: `graph/` 22,794 · `engines/` 20,319 · `api/` 10,384 · `retrieval/` 5,589.

**Every phase reports its LOC delta.** A phase with a positive delta must say why in its
completion note. This is not a suggestion; it is how the programme is judged.

## The nine rules this programme adds

These bind every task below. They exist because the review found each one violated.

1. **Reverse LOC ratchet.** Non-test LOC across `src/npc_engine/`, `scripts/`, `evals/` and
   `demo_game/` may only go down **in total**. The gate records and reports the four counts
   separately, so moving logic between them is visible rather than free. Raising the total needs an
   explicit baseline bump with a stated reason. Gated by `make check-loc-ratchet` from T10.2.
   *Scope decided 2026-09-08: a `src`-only count would leave 164,715 LOC — 70.4% of the repo —
   uncounted, and this programme itself adds ~2,500 LOC of gate code to `scripts/` and `tests/`.*
2. **Delete before you abstract.** If a fix can be "add an abstraction" or "remove the feature",
   remove the feature. Record the removal in `DECISIONS.md` if it was ever documented.
   *T8.2 is a recorded exception: it threads `timeouts_ms.full` rather than deleting the unread
   field, because T8.1's admission control needs per-class ceilings.*
3. **No config, prompt or contract without a live reader.** Every `Settings` field, prompt YAML and
   contract YAML needs a reader outside its own module and its own tests. Gated by
   `make check-dead-surface` from T10.2. **Dead public functions are covered by review, not by a
   gate** — do not read this rule as gating them.
4. **Abstraction requires two.** A Protocol needs 2+ implementors or 3+ callers. Below that,
   inject the concrete class. Gated from T10.1.
5. **A test must be able to fail.** No existence-only assertions (`hasattr`,
   `iscoroutinefunction`), no asserting a constant equals its own literal. Gated from T12.1.
6. **Config must be read.** A declared setting nobody reads is a build failure. Part of rule 3.
7. **One path per concept.** Never two implementations of one domain (an Engine class *and* a
   parallel graph service). Pick one; delete the other.
8. **Prefer deterministic over model.** A model call is a budget item, not a default.
   `engines/gossip/` is the in-repo precedent: seeded, deterministic, no model, and it works.
   *T2.1 is a recorded exception: it adds an unconditional startup generation to remove the 10.5s
   cold load.*
9. **Net-negative phases.** Measured on the same four-directory non-test count rule 1 ratchets. A
   phase that adds to `tests/` states the delta but is not blocked by it.

**Four of these nine are unenforced, and that is recorded deliberately rather than left to be
discovered.** Rules 1, 3/6, 4 and 5 carry a gate. Rules **2, 7, 8 and 9 have no gate** and are
enforced by review only. The owner decided 2026-09-08 not to build gates for them; do not read an
ungated rule as mechanically checked, and do not assume a green `make check` says anything about
them.

## Decisions already taken (2026-09-08, by the owner — do not relitigate)

| Area | Decision |
|---|---|
| Political/military layer | **Delete five**: `military`, `faction_politics`, `treaty`, `succession`, `oath`. Graph services the demo reads (`FactionService`, `pledge_service`, `treaty_service`) **survive**. |
| `agenda` — amended 2026-09-09 | **`agenda` is NOT deleted.** The original decision said all six; the owner reversed the `agenda` half on 2026-09-09. The whole of `src/npc_engine/engines/agenda/` survives, including `agenda_engine.py`. Consequences: `engines/ports/political_port.py` and `graph/repositories/political_repository.py` **survive** (`agenda_engine.py:18,36` and `succession_engine.py:18,35` share `PoliticalGraphPort`, and only succession goes), and `api/dependencies_advanced/politics.py` **survives** carrying `get_agenda_engine` alone once its other four builders are removed. |
| Live demo gate | **Add `demo-run-live`** as a nightly target driving the scripted demo through real API calls, reported in the morning report and **not** wired into `make check` (so it never blocks a task). Closes DEC-280(a), pending since 2026-09-07. |
| Co-location chain | **Revive `routine` + `need`** by fixing the seed. **Delete `mood` + `clique`.** |
| Agency/intrigue | **Delete `deception` + `skill` only.** Keep `investigation`, `player_model`, `planning`. |
| Dead surface | Delete `currency`, the `SchemingEngine` class (keep `SchemeAdvanceTick`), the `story_pacing/pacing_queries.py` shim. |
| Ports | **Collapse to the simplest shape that still respects SOLID** — concrete injection below the threshold, protocols kept only where genuinely earned. |
| Tests | **Aggressive prune.** Delete every test that cannot fail. |
| `evals/` | **Keep and repair the judged layer.** Eval comparability therefore has real value. |
| Prompt | **One batched revision**, paying the `dialogue_prompt_hash` comparability cost exactly once. |
| `demo_game/` | **Trim to what the scripted demo and the walkthrough actually exercise**, then gate it. |
| Integration CI | Assume the CI job gates merge; **verify it in-phase** and make it required if it does not. |

## Carry-forward notes

*Cheap context for the next session. Add a line when a task creates something downstream work
needs; delete it once consumed. Keep <= 10 lines.*

- **Sprint 0 is done (2026-09-16).** The loop runs only from a provisioned worktree — a validated one
  exists at `../NPCSystem-loop` (branch `loop-validate-2`); follow `OVERNIGHT_LOOP.md` § Quick start
  and re-run `make check` there before a night. Open driver bug found on the way: ISSUE-343.
- **2** tasks in the fence are flagged for an interactive session and the loop will silently pass
  over them: T13.1, T13.2 (both need a person at the demo). `make roadmap-audit` reports them,
  with the line that raised each flag. The fence holds **53** tasks in total, 51 of them loop-runnable (counted
  2026-09-17, after the live-check change and the T4/T10/T11/T14 splits).
- The app image is **not** bind-mounted: rebuild before any before/after measurement. Loop live
  checks do this via `scripts/eval_stack_at.sh` — keep Docker and Ollama up overnight, and keep
  nothing you need in the eval stack's Neo4j.
- Integration tests write to the **live** Neo4j (ISSUE-277) — never run the integration suite
  casually, and never between a corpus freeze and its generation.
- Use Git Bash for `make`; the Makefile pins no `SHELL` and POSIX recipes fail under PowerShell
  (ISSUE-281).
- **Co-location revival confirmed (2026-09-18, T6.3).** After T5.1 (FOLLOWS_SCHEDULE) and T5.2
  (HAS_NEED) seeding, `routine` moves characters across time-of-day slots (moved > 0) and
  `need_decay` updates need levels (needs_updated > 0) on the live eval stack. At least one NPC has
  an unmet need (level < 50). Sprint 4's tick-budget and admission-control work now has real
  co-location and need pressure to measure against — the before-baseline is set.

### History

| What | Where |
|---|---|
| The M programme (metrics readiness) + R6 | `archive/ROADMAP_M-programme_2026-09-08.md` |
| The 2026-08 remediation programme (R0–R5) | `archive/ROADMAP_remediation-2026-08_2026-09-03.md` |
| Full pre-remediation roadmap (phases 0–26, EXP/F-G-H/SEV, eval P0–P31) | `archive/ROADMAP_pre-remediation_2026-08-28.md` |
| Phases 0–13 / 14–26 | `proposals/archive/ROADMAP_through_phase13_2026-06-03.md`, `archive/ROADMAP_phase14-26_2026-06-11.md` |
| The 2026-09-07 full review that produced this programme | `REVIEW_FINDINGS.md`, `review-fixes/` |
| The 2026-08 review | `CODEBASE_REVIEW.md`, `review-2026-08/` |
| The 2026-09-08 adversarial review of **this** roadmap (6 lenses, 77 findings) | `roadmap-review/FINDINGS.md`, `roadmap-review/R1.md`-`R6.md` |

**Re-triage of `review-2026-08/TRIAGE.md`'s CRITICALs, 2026-09-08.** That set was never
cross-referenced when this programme was written, because it uses a `CR-L*` id namespace this
roadmap does not. Checked against the tree: **CR-L05-11** (compose bound `0.0.0.0`) and
**CR-L08-03** (no 503 handler for `GraphUnavailableError`) are **fixed**; **CR-L03-01**
(`hedge_responder_probe.py`) refers to a file that no longer exists and is presumed superseded by a
refactor, unverified; **CR-L01-01** (gossip distortion discarded on read) and **CR-L15-01** (eval
live-network digest defaults) were **still live** and are now scheduled as **T5.3** and **T16.6**.
`review-fixes/INDEX.md` is superseded by this programme — its 15 Fix-now SEVs all map to tasks, with
SEV-02 and SEV-03 traceable through T7.1 and T7.2 and SEV-07 through T7.3.

---

## How to execute a task in this roadmap

Read this once before your first task. It is the contract.

0. **Sprint 0 first, and T0.0 before anything.** The loop is not safe to run until Sprint 0 lands —
   see its header. **Only the worktree half is enforced in code.** T0.1's preflight refuses to start
   outside a dedicated worktree, but `scripts/_roadmap_cursor_core.py` sees nothing outside the
   `LOOP:QUEUE` fence, so Sprint 0's *completeness* is structurally invisible to the cursor. Nothing
   stops an operator creating a worktree the moment T0.1 lands and starting the loop with T0.0,
   T0.2, T0.3, T0B.1 and T0B.2 still unticked. That is operator discipline, not a mechanism — and
   the specific cost of skipping it is a red gate nobody can fix (T0.0), a stale lock that ends the
   next night (T0.2), a harness self-test that HALTs (T0.3), and a skill telling the agent to expect
   a 144-second gate that now takes twelve minutes (T0B.1), which is the night-losing one.
1. **One task per session.** Working on X, you do not also do Y. Notice Y, log Y, continue X.
   Every task carries five lines and they are the whole specification: **`Files:`** (what you may
   touch), **`Spec:`** (the problem, with file:line evidence so you never re-derive it),
   **`RED anchor:`** (the check that must fail first), **`Validation:`** (the exact commands), and
   **`Done when:`** (the finish line). Implement to those, not to your own idea of the task.
2. **RED first.** Every task carries a **RED anchor** — a check that fails *today* and passes
   after. Run it, watch it fail, and confirm it fails *for the stated reason*. A task whose
   anchor was never seen red must not be ticked.
3. **Deletion tasks are still TDD.** The anchor for a deletion is usually "a census/gate test
   that currently passes with the dead thing present, and must still pass with it gone" plus
   "`make check` is green after removal". If deleting breaks a test, read the test before
   restoring the code — the review found many tests that assert nothing.
4. **`make check` must be green before you tick.** Note it does **not** run `roadmap-verify` —
   `Makefile:432` lists 23 targets and `roadmap-verify` is not among them; it exists at
   `Makefile:287` and in `.PHONY` only. What actually guards the queue inside `make check` is
   `tests/unit/harness/test_roadmap_cursor.py`, which runs `verify()` against the real file and pins
   the fence's phase list. Run `make roadmap-verify` yourself after any roadmap edit. Also note
   `check-mutations`, `check-conservation` and `check-label-survival` are **not** in `make check`.
5. **Report the LOC delta** in the completion note. Use the command in T0 below.
6. **Baselines.** A deletion resolves grandfathered entries and an addition can create new ones. If
   `check-rules` reports "N baselined violation(s) resolved", run `make check-rules-update` in the
   **same** commit and state N in the completion note. This is a **task-session** action; a
   `/fix-make-failure` repair session may never do it (`scripts/scan_fix_diff.py:9-14`), and that
   prohibition does not extend to you. The same applies to `make type-demo-update` for
   `.mypy_baseline_demo`, and to `scripts/loc_baseline.txt` once T10.2 lands. A task that grows a
   file already carrying an `R001|path:N` row must raise N deliberately with the reason in the
   commit message — see T5.1/T5.2 and `demo_game/seeds/seed.py`.
7. **Gate budget.** `make check` is ~12 minutes, about 13% of the 90-minute `CLAUDE_TIMEOUT`. Run
   the full gate **at most twice** — once when you believe you are green, once after a repair. Use
   the task's targeted `pytest` path for iteration; `make check` is the finish line, not the inner
   loop.
8. **Pre-approval.** Some tasks carry a `Pre-approved:` line naming one or more of `file-deletion`,
   `public-interface`, `graph-schema`, `new-dependency`. That line is the owner's standing approval
   for exactly those actions in exactly that task: **do not halt on an ask-gate for a class the line
   names.** It does not cover anything else — a task pre-approved for `file-deletion` still halts on
   a graph-schema change. Name the approval in your commit body.
9. A task marked with the pause glyph needs a **person** — a human judgement or a human at the
   keyboard; the overnight loop skips it and it must be done in an interactive session.
   **A task that only needs a running stack is loop work** (owner, 2026-09-17). The app image is
   not bind-mounted, so a stack that is merely up runs the commit it was built from; every live
   check therefore rebuilds the isolated eval stack first with `bash scripts/eval_stack_at.sh
   HEAD --reset` (or `<sha> --reset` for an older tree — never a `git worktree`), which exits
   non-zero unless `/health` reports that sha. Wherever a task below says "a running stack",
   "the isolated stack" or `make eval-stack-up`, that is the procedure; the full rules are in
   the loop skill's "Live checks" section. The owner keeps Docker and Ollama running overnight,
   and the eval stack's Neo4j is reset by the loop, so nothing that must survive lives there.

---

# SPRINT 0 — Make the overnight loop trustworthy (DO THIS FIRST, WITH THE LOOP STOPPED)

**This sprint is deliberately OUTSIDE the `LOOP:QUEUE` fence and must be done by hand.**

These tasks edit `scripts/expand_loop.sh`, `scripts/loop_gates.py`, `scripts/loop.config.sh` and
`.claude/commands/expand-linear-next.md` — the driver and the skill that execute the queue. A loop
rewriting its own driver mid-run produces a night that cannot be diagnosed. Run these with the loop
**stopped**, verify each by hand, then start Sprint 1.

**Provenance.** T0.1-T0.3 are the R6 programme from the retired M roadmap, reinstated verbatim in
substance. R6 was archived on 2026-09-08 as part of clearing the roadmap while all three of its
tasks were still unticked — that was an error, and this sprint corrects it. T0.4 and T0.5 are new,
found on 2026-09-08 while checking whether the loop was ready to run the T programme.

**Why this blocks everything.** The T programme is deletion-heavy and runs for weeks. Every defect
below either corrupts the record of what happened (T0.1), ends nights early (T0.2, T0.3), makes the
agent fight rules that do not exist (T0.4), or lets needed work vanish silently (T0.5). Running the
programme before fixing them means discovering the damage months later, which is precisely the
failure mode the 2026-09-07 review was written about.

### Phase T0 — the driver

- [x] **T0.0** Re-point the roadmap-cursor tripwire at the T programme — **do this first, by hand**
  ✅ 2026-09-16. `_EXPECTED_PHASE_IDS` = T1..T16, `EXPECTED_FLAGS` = the six `deferred` tasks.
  `make check` green end to end in **9m55s** (595s). All nine previously-unreached targets
  pass on first observation: `test-cov-evals` (82.79%), `test-cov-v13` (88.33%),
  `test-cov-full-report`, `check-migrations`, `check-api-stability`, `check-api-contract`
  (149 ops), `check-engine-logs`, `check-base-rate` (0.9140, at baseline), `check-dead-keywords`.
  LOC delta: 0 non-test; +19 test.
Files: `tests/unit/harness/test_roadmap_cursor.py`
Spec: **`make check` is RED at HEAD and has been since the commit that wrote this roadmap.** Two
tests fail — `test_real_roadmap_parses_and_verifies_clean` and `test_real_roadmap_fence_state_tripwire`
— because `_EXPECTED_PHASE_IDS` at `:201` still pins `["M1", "M2"]` from the retired M programme
while the fence now parses `T1..T16`. A second deliberate-update constant sits at `:171`:
`EXPECTED_FLAGS: dict[str, list[str]] = {}`. Fixing only the phase ids makes the assertion at `:331`
fire instead, listing the flagged tasks as "newly skipped with no recorded reason".
`verify(phases, lines)` returns `[]` — the roadmap itself is well-formed; only the pinned constants
are stale. This is the tripwire working exactly as designed; update it deliberately and record why.
Set `_EXPECTED_PHASE_IDS` to the sixteen T phases, and populate `EXPECTED_FLAGS` with the **six**
flagged tasks — T6.3, T13.1, T13.2, T15.2, T16.1 and **T16.4** — with their flags. Extend the dated
history comment with the 2026-09-08 fence move and its reason, per that comment's own contract.
**Nothing else in this programme can fix this.** `tests/` is the first entry in
`loop_gates.FROZEN_PATH_PREFIXES`, so `scan_fix_diff.py` reverts any repair session that touches it;
and it is HALT-class, so autofix is never even offered. Until this lands, `gate_attribution.py:65`
can never return GREEN, every task commits `TASK_COMPLETE_BASELINE_RED`, and the phase gate reds at
every boundary until `MAX_CONSECUTIVE_RED_GATES=2` ends the night.
Note `make check` currently **aborts at target 14 of 23**, so nine targets have never been observed
on this tree: `test-cov-evals`, `test-cov-v13`, `test-cov-full-report`, `check-migrations`,
`check-api-stability`, `check-api-contract`, `check-engine-logs`, `check-base-rate`,
`check-dead-keywords`. Four of those are exactly the gates that notice a deletion, and this is a
deletion programme.
RED anchor: `pytest tests/unit/harness/test_roadmap_cursor.py -q` — 2 failed today.
Validation: that file green, then `make check` end to end for the first time.
Done when: `make check` is green and reaches `check-dead-keywords`; the completion note records the
true green duration and **which of the nine previously-unreached targets pass** — this is their first
observation on the T tree.

- [x] **T0.1** Run the loop in a dedicated git worktree · ISSUE-139 · was R6.3
  ✅ 2026-09-16 (code in `99e7906f`). `preflight_worktree` refuses in the primary checkout, without a
  `.venv` that imports pytest/mypy/ruff, and without `.env` — each with the fix command; all three
  refusals observed. RED observed first: live run #1 from the primary checkout swept a concurrent
  `PATTERNS.md` probe into its T3.1 commit. Worktree `../NPCSystem-loop` provisioned with a fresh
  `.venv` (`pip install -e ".[dev]"` suffices) and `.env`; **`make check` green inside it** (first run
  3342 s wall on cold caches). Live run #2 from the worktree: T3.1 `TASK_COMPLETE` in 22 min, commit
  `1cb2fa8d` holds only T3.1's files + tick, and the concurrent primary-checkout probe stayed out.
  `OVERNIGHT_LOOP.md` Quick start carries the recipe. ISSUE-139 archived.
  LOC delta: +27 non-test (`scripts/expand_loop.sh`; 799 lines).
Files: `scripts/expand_loop.sh`, `project-harness/OVERNIGHT_LOOP.md`, `Makefile`
Spec: the loop stages the **whole working tree**, so a concurrent interactive session's edits are
absorbed into whatever roadmap commit the loop happens to be writing. Observed in the wild: an
interactive fix to `evals/eval_records.py` and its tests landed inside
`24f6a01 feat(evals): capability_rate as first-class metric` and was tagged
`[UNVERIFIED: regression]` by a loop that never gated it.
A worktree is strictly better than teaching the commit step to stage explicit paths: it is a
launch-time change rather than a change to the commit transaction, it makes collision structurally
impossible rather than filtered, and the repo already works this way (`/fix-parallel`, `NPCSystem-r5`).
Add a preflight that **refuses to start in the primary checkout**, with the error naming how to
create the worktree.
**Provisioning — do not skip this half, and do not trust the cited precedent for it.** `/fix-parallel`
and `/expand-parallel` never run `make check` inside a worktree; they gate serially after fan-in, and
neither skill mentions `.venv` or `.env`. `git worktree list` shows exactly one worktree today, so
**the worktree launch has never been exercised against the gate.** `.venv/` (`.gitignore:11`) and
`.env` (`.gitignore:72`) are both ignored, so a fresh worktree has neither; `Makefile:1-7` then falls
back to the ambient `python` and every one of `make check`'s 23 targets dies on a missing tool.
`Makefile:10` also reads `.env` for `API_KEY`, and `loop_gates.py:python_executable()` has the same
fallback. The preflight must therefore **also** verify, in the worktree it is about to run in, that
`.venv` resolves to a working interpreter and `.env` exists — failing with the exact commands to
create them.
RED anchor: dirty an unrelated file, run one task, and confirm the unrelated change lands inside the
loop's commit today.
Validation: after the fix, repeat the same experiment and confirm the loop refuses to start in the
primary checkout. Then create a worktree with **no** `.venv` and confirm the preflight refuses with
an actionable message; provision it; **run `make check` inside the worktree and see it green**; then
run one task from it and confirm the commit contains only that task's files plus the roadmap tick.
Done when: the preflight covers both the primary-checkout refusal **and** the missing-toolchain
refusal, `make check` has been observed green inside a worktree, and `OVERNIGHT_LOOP.md` carries the
full launch recipe — `git worktree add`, then create or link `.venv`, then copy `.env`, then one
hand-run green `make check`, then start the loop. Closes ISSUE-139.

- [x] **T0.2** Document stale-lock recovery · ISSUE-126 (remaining half) · was R6.1
  ✅ 2026-09-16. Recovery in the FATAL message (names the holder pid, `ps -p` check, `rm -rf`),
  the usage header and `OVERNIGHT_LOOP.md` § Stale lock recovery. Validated: live-pid lock →
  FATAL with recovery → recovered from the message alone → relaunch passed the lock. Note
  `compat_lock_acquire` already reclaims dead-pid locks; the FATAL only fires on a live pid.
  ISSUE-126 archived. LOC delta: +14 non-test (`scripts/expand_loop.sh`: recovery text and comments).
Files: `scripts/expand_loop.sh` (usage header), `project-harness/OVERNIGHT_LOOP.md`
Spec: **the no-progress guard already exists (DEC-235) — do not delete it and do not write a second
one.** `expand_loop.sh:649` compares each iteration's task id against `LAST_TASK_ID` and halts once
`SAME_TASK_REPEATS` reaches `MAX_SAME_TASK_REPEATS` (default 2, set at `:103`). Measured 2026-09-03:
an unbounded `--dry-run` terminated on its own after 6.5 minutes with exit 0, logging
`HALT: M1.1 repeated 2 times without advancing the cursor`.
What remains undone is the other half ISSUE-126 asks for: killing a loop leaves the `mkdir`-based
lock directory `project-harness/.loop-state/loop.lock/` behind, so the next run aborts with
`FATAL: another loop holds …`. Recovery is `rm -rf project-harness/.loop-state/loop.lock` and it is
documented **nowhere** — not in the script's usage block, not in `OVERNIGHT_LOOP.md`.
Note the guard makes the stale lock *more* likely to be met, not less: a halt is now the normal end
of a stalled night, so the next operator meets the lock rather than the spin. Consider also printing
the recovery command in the `FATAL` message itself, which is where someone actually reads it.
RED anchor: `grep -rn "rm -rf.*loop.lock\|stale lock" scripts/expand_loop.sh project-harness/OVERNIGHT_LOOP.md`
returns nothing today, and returns the recovery command once this task lands. **Do not** anchor on
the literal string `loop-state/loop.lock`: the path is composed from variables
(`loop.config.sh:11` sets `LOOP_STATE_DIR`, `expand_loop.sh:89` sets
`LOCK_DIR="$LOOP_STATE_DIR/loop.lock"`), so that grep returns zero before **and** after the fix and
cannot tell done from not-done.
Validation: create the lock dir by hand, run the loop, and confirm the failure message now tells you
how to recover. Then recover using only what the message says.
Done when: the recovery appears in the FATAL message, the usage header and `OVERNIGHT_LOOP.md`.
Closes ISSUE-126.

- [x] **T0.3** Route harness self-test failures to skip-and-log, not HALT · was R6.2
  ✅ 2026-09-16 (code in `b92a068e`). `HARNESS_TEST_PATH_PREFIXES` + `CLASSIFICATION=HARNESS` (exit 4) when
  every failing node id is under `tests/unit/scripts/` or `tests/unit/harness/`; mixed, product and
  node-less failures stay HALT. `run_phase_gate` flags it and returns **without** incrementing
  `CONSECUTIVE_RED_GATES`. Validated on the real driver with a fake `claude` and `--max-red-gates 1`:
  RED — forced `tests/unit/scripts/` failure → `HALT: 1 consecutive red phase gates`; after — the same
  failure → HARNESS, streak 0, night continued to T4.1; a forced product failure → HALT and
  "stopping: repeated red gates". **This changes the phase gate's routing only**: `gate_attribution.py`
  is untouched, so a red harness self-test still makes each task report `BASELINE_RED`.
  Found on the way, logged as ISSUE-343: the scar-6.10 boundary path swallows the red-gate HALT.
  LOC delta: +36 non-test (`scripts/`); +79 test.
Files: `scripts/loop_gates.py`, `scripts/classify_gate_failure.py`, `scripts/expand_loop.sh`
Spec: `loop_gates.py` already splits HALT-class (behaviour) from AUTOFIX-class (form) and re-runs a
failing gate's constituents individually to decide. Extend that existing classification with a third
bucket — **harness self-test failure** — routed to skip-and-log rather than halting the night. One
more branch in a structure that already exists; no new mechanism.
The motivating fact, recorded in the R6 spec: *every HALT to date was the harness tripping over its
own self-tests.* This matters more under the T programme than it did under M, because Sprints 2, 5
and 6 add five new gate scripts (`check_engine_census.py`, `check_dip_threshold.py`,
`check_dead_surface.py`, `check_loc_ratchet.py`, and the test-quality extension), each with its own
tests under `tests/unit/scripts/`. The T programme actively enlarges the surface this task protects.
Define "harness self-test" narrowly and explicitly — tests under `tests/unit/scripts/` and
`tests/unit/harness/` — rather than by heuristic, so the bucket cannot silently swallow a product
failure. A skipped harness failure must still be written to the morning report; skip-and-log is not
skip-and-forget.
Two constraints found on 2026-09-08 that this task must respect.
**(a) The night-ending decision is not in the two files originally listed.** `run_phase_gate` at
`expand_loop.sh:430-443` gates the repair on `[ "$cls" -eq 0 ]` and then increments
`CONSECUTIVE_RED_GATES`. A third classification bucket that `run_phase_gate` does not recognise
still increments the counter and still halts at 2. That is why `expand_loop.sh` is in `Files:`.
**(b) Sprint 6 makes `tests/` itself the subject of a task.** Bucket on the failing test's **path**
(`tests/unit/scripts/`, `tests/unit/harness/`), never on which task was running, or T11.1 — a
deliberate test deletion — will mis-route a genuine product failure into the skip bucket.
RED anchor: force a failure in `tests/unit/scripts/` and confirm the loop HALTs the night today.
Validation: after the change, the same forced failure skips the phase, logs the reason, and the
night continues; then force a failure in a *product* test and confirm it still HALTs.
Done when: both halves of that validation hold, a harness-classified red gate does **not** increment
`CONSECUTIVE_RED_GATES`, and the completion note states explicitly that this task changes the
**phase** gate's routing only. `gate_attribution.py`, which the skill runs per task, is untouched, so
a red harness self-test still makes every task report `BASELINE_RED` — that is **T0.0's** job, not
this one, and T0.0 must already be done.

### Phase T0B — the skill and the deferred-work hole

- [x] **T0B.1** Correct the loop skill's stale facts
  ✅ 2026-09-16 (code in `dc520046`). All five items in; the stale-fact grep is clean. Gate figure
  restated from 2026-09-16 measurements (425-595 s). Live validation: a real loop run over T3.1 on
  scratch branch `loop-validate-1` returned `TASK_COMPLETE` in 22 min with **no halt** on
  `Pre-approved: file-deletion, public-interface`, named the approval in its commit body, and its
  summary cites no 300-line limit. LOC delta: 0 non-test code (skill prose and a config comment).
Files: `.claude/commands/expand-linear-next.md`, `scripts/loop.config.sh`
Spec: the skill and the config state five things that are no longer true, and each one costs
something. Item (5) is not a correction but the mechanism without which half this programme halts.
(1) **File limit.** The skill tells the agent "300-line file limit". `project-harness/CLAUDE.md`
says **400 advisory, 800 hard and unwaivable** (DEC-226). An agent following the skill will split
files that do not need splitting, adding modules to a programme whose entire purpose is removing
them.
(2) **Gate duration.** The skill says `make check` takes "about 144 seconds" and repeats the figure;
`loop.config.sh` carries the same claim plus "2618 passed / 29 skipped / 87.10 % cov". Measured
2026-09-07: **11m58s**, 4,571 passed. The stale number is dangerous rather than merely wrong — the
skill's single most load-bearing instruction is "never background the gate, wait for it", and an
agent told to expect 144s that sees nothing at 144s is exactly the one that concludes it hung. That
is scar 6.1, the night-losing one. Update both, state the figure as approximate with the date it
was measured, and add the budget consequence the bare number does not convey: **at ~12 minutes a
gate run is ~13% of the 90-minute `CLAUDE_TIMEOUT`, so run the full gate at most twice** — once when
you believe you are green, once after a repair. Use the task's targeted `pytest` path for iteration.
(3) **Task grammar.** The skill names `Files:`, `RED anchor:` and `Validation:` as the three lines
that constitute a task's specification. The T programme's tasks also carry `Spec:` and `Done when:`.
Add both to the skill's list so the agent is told to read them — `Spec:` in particular carries the
file:line evidence that keeps a cheap model from having to re-derive the problem.
(4) **Roadmap line count.** The skill says "Never read the whole ROADMAP.md — **it is 1183 lines**".
It is over 1,400. Correct the number and **keep the instruction** — reading a slice is what keeps
the agent's context small.
(5) **Pre-approval — the load-bearing item.** The T programme deletes files, changes public
interfaces and adds graph edge types **by explicit owner decision**, on 18 in-fence tasks. The
skill's halt table as written makes the agent halt on every one of them, and a halt is not a lost
task: `expand_loop.sh:551-560` routes it to `skip_phase`, which discards **the whole phase** for the
rest of the run and passes it as `--exclude` to every later `cursor --next`. A halt on T3.1 silently
loses T3.2, unattempted and unreported, and `MAX_CONSECUTIVE_BLOCKED_PHASES=2` then ends the night —
with phases T3 and T4 consecutive and both opening on a deletion task. The halt check runs "BEFORE
writing anything" and keys on tokens, not prose, so the sentence "the owner decided 2026-09-08 to
delete" sitting in a task's `Spec:` does nothing.
Add one row to the skill's halt table, **above** the ask-gate row:
`| Task body carries a `Pre-approved:` line naming the exact class you are about to trip | do NOT
halt — the owner approved it; proceed, and name the approval in your commit body |`
The approval class must **match** the action: a task pre-approved for `file-deletion` still halts on
a graph-schema change. The vocabulary is exactly four values — `file-deletion`, `public-interface`,
`graph-schema`, `new-dependency` — so `make roadmap-verify` can validate it.
Items (1)-(4) do not change the loop's behaviour; item (5) deliberately does.
RED anchor: `grep -n "300-line\|144\|1183" .claude/commands/expand-linear-next.md scripts/loop.config.sh`
returns the stale claims today, and `grep -n "Pre-approved" .claude/commands/expand-linear-next.md`
returns nothing.
Validation: re-read the skill end to end and confirm every factual claim matches the tree; then run
one task through the loop and confirm the agent's own summary does not cite a 300-line limit.
Done when: all five items are in, the grep is clean, and **a dry run over T3.1 confirms the agent
does not halt** on its `Pre-approved: file-deletion` line.

- [x] **T0B.2** Make deferred work visible instead of silently skipped
  ✅ 2026-09-16. `roadmap_cursor.py --audit-deferred` (+ pure `flag_evidence` in the core) and
  `make roadmap-audit` list the six flagged tasks with each flag's matched line, exit 1 while any
  exist. `expand_loop.sh` logs it at startup and writes it to the morning report before
  `checkpoint_reports`. `test_roadmap_audit.py` covers the fixture cases, the ISSUE-134 sprint-heading
  leak, and agreement of the real audit / backlog table / carry-forward count / `EXPECTED_FLAGS`.
  No accidental flags on the real file: every one of the six is raised by its own heading's ⏸️. LOC delta: +83 non-test (`scripts/` +77, `Makefile` +6, a positive
  delta the task itself calls for: a new report and its loop wiring); +135 test.
Files: `scripts/roadmap_cursor.py`, `scripts/_roadmap_cursor_core.py`, `Makefile`,
`scripts/expand_loop.sh`, new `tests/unit/scripts/test_roadmap_audit.py`
Spec: this is the defect that would have quietly cost the most. `compute_next` documents its own
behaviour: *"Flagged tasks (ask-gate, live, deferred) are never returned."* That is correct — an
unattended session must not guess at a human decision — but nothing anywhere reports that a flagged
task was passed over. The loop skips it, ticks everything after it, and the roadmap reads nearly
complete while the skipped work never happened. Under the T programme that would mean the demo
census, the portfolio liveness check and the DEC-273 re-measurement silently never occur.
Add `--audit-deferred` to `roadmap_cursor.py`, exposed as `make roadmap-audit`: print every task
inside the fence that is **flagged and not done**, with its phase, its flags, and its one-line title.
Exit non-zero if any exist, so it can be read by a script.
Then wire it into `expand_loop.sh` at **both ends** of a run: once at startup (so the operator sees
the standing debt before the night begins) and once at the end, written into the morning report
alongside the other run artifacts. Do not make it fail the night — it is a report, not a gate.
The **Deferred backlog** section already exists in `ROADMAP.md` — do not treat writing it as this
task's finish line; reconcile it instead (see `Done when:`).
While here, close ISSUE-134's substring weakness in the audit's favour: `--audit-deferred` must
print, for each flagged task, the **matched line** that raised each flag, not just the flag name.
`_flags_for` greps the whole block body and `BLOCK_END_RE` (`_roadmap_cursor_core.py:38`) matches
`##` through `####` but **not** a level-1 `# SPRINT` heading, so the last task of a phase absorbs the
next sprint's prose into its own flag scan. A flag can therefore be raised by text that is not the
task's. Showing the matching line makes an accidental flag visible on the first run instead of never.
Assert it with a fixture whose sprint heading contains the word `ask-gate`.
RED anchor: the new test asserts `--audit-deferred` lists exactly the flagged-and-unticked tasks for
a fixture roadmap and exits non-zero, and exits zero when none remain. Run `make roadmap-audit`
against the real roadmap **after adding the flag**: it must list **six** tasks — T6.3, T13.1, T13.2,
T15.2, T16.1 **and T16.4**. T16.4 carries the pause glyph at its heading but was missing from every
place this roadmap records deferred work until 2026-09-08; a test written to expect five would
hardcode that omission and bless it.
Validation: `pytest tests/unit/scripts/test_roadmap_audit.py -v`, then `make roadmap-audit`, then
`make check`.
Done when: the command exists, the loop reports it at both ends of a run, each flag names the line
that raised it, and **three records of one fact agree** — the carry-forward note's count, the
Deferred backlog table, and `make roadmap-audit`'s output. Assert that agreement in the new test
against the **real** file, not only a fixture, so they cannot drift again. Cross-check the fourth
record too: `EXPECTED_FLAGS` in `tests/unit/harness/test_roadmap_cursor.py`, populated by T0.0.

---

## Deferred backlog — the loop will NOT do these

`compute_next` never returns a flagged task: *"an unattended session must not guess at a human
decision, and skipping costs nothing where attempting costs a whole session."* That is correct, but
it means these tasks are passed over in silence — the loop ticks everything around them and the
roadmap reads nearly complete while they never happened. **They are needed, not optional.**

`make roadmap-audit` prints this list from the file itself, with the line that raised each flag, and the
loop logs it at startup and writes it to the morning report at the end of every run. Keep this table in
sync when a flagged task is ticked or added — `tests/unit/scripts/test_roadmap_audit.py` fails when it,
the carry-forward count and the audit disagree.

**Every row carries an owner and a due date.** A report nobody is assigned to read is the same as no
report, and this repo has already proved that once — see Sprint 0's Provenance note. Dates are
sprint-relative so they stay meaningful whenever the loop actually reaches them.

| Task | Why it cannot be automated | Blocks | Owner | Due |
|---|---|---|---|---|
| **T13.1** | Half the census is the interactive MetaHuman walkthrough, which a person plays; the scripted run alone would mark the walkthrough's modules dead | T13.2, and therefore all of Sprint 7 | Lohann Colle | before any Sprint 7 loop task starts |
| **T13.2** | Needs T13.1's census artifact, which only an interactive session produces | Sprint 7's LOC win, the largest available after tests | Lohann Colle | within 7 days of T13.1 |

**T16.4 was invisible here until 2026-09-08.** It carried the pause glyph at its heading but appeared
in neither this table, the carry-forward note, nor T0B.2's own RED anchor — an instance of exactly
the silent-skip failure T0B.2 exists to prevent, sitting inside the record T0B.2 makes honest.

**Two other tasks were mis-flagged in the first draft and have been fixed:** the seed edits for
`:Schedule` and `HAS_NEED` (T5.1, T5.2) are pure `seed.py` changes with unit tests and are now loop
work, and their live confirmation was split into T6.3.

**2026-09-17: a running stack is no longer a reason to defer.** T3.3, T6.3, T7.4, T15.2, T16.1 and
T16.4 were deferred only because the loop could not see live code; they are loop work now that live
checks rebuild the isolated eval stack from the task's own commit (execution contract item 9). Defer
a task only when it needs a person.

<!-- LOOP:QUEUE start -->
<!-- Everything between these markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside these markers — deliberate.
     Scope agreed 2026-09-08: sprints 1-8, the mechanical half of the T programme.
     Sprints 9 and 10 (eval repair, prompt revision) sit outside the fence because they
     need human judgement and live model runs. A task tagged with the pause glyph is
     skipped without spending a session. -->

---

# SPRINT 1 — The demo works again

**Self-contained goal:** at the end of this sprint a studio evaluator can boot the stack and
play the demo end to end without it breaking or losing itself. Nothing else in this programme
can be verified against a running demo until this sprint lands.

### Phase T1

The two CRITICALs that make the demo unusable. Both were found only by running it.

- [x] **T1.1** Fix the WebSocket slot leak — the cap exhausts after 5 conversations
Files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py`, new test
`tests/unit/api/test_ws_connection_slot_release.py`
Spec: `MAX_WS_CONNECTIONS_PER_KEY = 5` at `dialogue_ws.py:50`. After `_run_first_turn` the
handler enters an idle-drain loop at `:231-233` that only ever *sends*:
`while True: await drain_proactive_lines(...); await asyncio.sleep(PROACTIVE_DRAIN_POLL_SECONDS)`.
Starlette surfaces a
client-initiated close as `WebSocketDisconnect` only on a `receive()`. With an empty proactive
queue this loop never receives, so `except WebSocketDisconnect` (`:234`) never fires and
`finally: await _release_ws_slot(key_id)` (`:240-241`) never runs. The slot is held for the
process lifetime. The client is NOT at fault: `demo_game/dialogue_ws.py:67` closes correctly via
a `with` block. Fix: replace the sleep-only loop with
`await asyncio.wait_for(websocket.receive(), timeout=PROACTIVE_DRAIN_POLL_SECONDS)`; treat
`TimeoutError` as "nothing from the client, keep draining" and a `websocket.disconnect` message
as the exit. **`PROACTIVE_DRAIN_POLL_SECONDS: float = 0.5` already exists at `dialogue_ws.py:45` and
is already used at `:233` — reuse it as the `wait_for` timeout. There is no bare literal to replace
and no new constant to introduce.** Keep `_release_ws_slot` in the `finally`; the fix is making the
loop *reach* it.
RED anchor: the new test opens `MAX_WS_CONNECTIONS_PER_KEY + 1` sockets **sequentially**, fully
closing each before opening the next, and asserts the last is accepted. It fails today — the 6th
is rejected. The sequential-close case is exactly what the existing helper-level guard misses.
Validation: `pytest tests/unit/api/test_ws_connection_slot_release.py -v`, then `make check`.
Done when: the new test passes, `make check` is green, and no other WS test regressed.
Blocks: T1.2, T2.3, and every demo verification in this programme. SEV-01, finding L9-01. ✅ AUTO (T1.1, 2026-09-16)

- [x] **T1.2** Delete the `military` engine — it conquers the barracks on tick 5 and ends the game
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-279
Files: delete `src/npc_engine/engines/military/`, `src/npc_engine/engines/ports/military_port.py`,
`src/npc_engine/graph/repositories/military_repository.py`, `src/npc_engine/graph/military/`, and
the five flat military test files —
`tests/unit/engines/test_military_engine.py`, `tests/unit/engines/test_military_battle_service.py`,
`tests/unit/engines/test_military_resource_service.py`,
`tests/unit/graph/test_military_repository.py`,
`tests/unit/conformance/test_sev04_military_clique_graph_queries.py`
(there is **no** `tests/unit/engines/military/` directory — the tests are flat);
edit `src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/api/dependencies_advanced/politics.py`,
`src/npc_engine/api/dependencies_engines/engine_slots.py`,
`src/npc_engine/graph/repositories/__init__.py`, `docs/ENGINES.md`,
`docs/DEMO_SCRIPT.md`, `demo_game/runners/run.py`, `src/npc_engine/data/event_pool.json`
Spec: the owner decided 2026-09-08 to delete the whole political/military cluster; `military` goes
first because it is the cause of a CRITICAL. Measured on a running stack:
`battle_resolved … winner iron_legion … loser city_guard … tick 5`, three seconds after seeding,
with zero player input, repeating every tick forever. The chain: `demo_game/seeds/seed.py:900-921`
seeds `army_iron_legion` (strength 100) and `army_city_guard_main` (strength 60) already
co-located at `loc_guard_barracks`; `tick_scheduler.py:356` runs `military` in the plain every-tick
list with no cadence gate; `military_engine.py:49` calls `resolve_battles(...)` unconditionally;
and `demo_game/world_objectives.py:37-38` sets `DEMO_LOSE_LOCATION_ID = "loc_guard_barracks"` /
`DEMO_LOSE_FACTION_ID = "iron_legion"` — the lose target *is* where the seed stages the battle.
`demo_game/game_end_checker.py:414-416` makes that lose override win. Deleting the engine removes
the writer, so nothing ever creates the `CONTROLS` edge and the demo stops losing itself.
Do NOT delete: `demo_game/world_objectives.py`, `game_end_checker.py`, or the army seed data —
those are demo-side and are handled in Sprint 7. Do NOT delete `graph/` services other engines use.
Note `tick_scheduler.py:130` calls this engine "a no-op stub (see ISSUE-001)" — that docstring
is wrong on both counts and dies with the engine (ISSUE-334).
**Six wiring sites, not five.** Besides the four files above, `tick_scheduler.py:329` carries
`"military": []` in the response skeleton and `tick_scheduler.py:356` the ordered-list entry. Grep
before you assume the list is complete.
**Delete `src/npc_engine/graph/military/` too** — 579 LOC across three modules whose only importer
outside itself is `military_repository.py`, which this task deletes. Verify with
`grep -rln "graph.military\|graph import military" src/ demo_game/ e2e/ evals/` and confirm the only
survivors are the files you are deleting. `graph/` services are kept **only** where a surviving
reader exists; this one has none, and T10.2a's dead-surface gate covers `Settings` fields and YAMLs,
not `graph/` modules — so nothing downstream would ever find it.
**Act 5 of the demo, and the events engine.** `docs/DEMO_SCRIPT.md:37,63-71,180-184` scripts Act 5
as a military beat and narrates "WORLD feed: battle resolved. Iron Legion wins", and its sign-off
checklist at `:255` **requires** "at least one `battle` event visible after military tick" before a
recording is allowed. `demo_game/runners/run.py:264-284` hardcodes the same beat. Deleting the
engine removes the only writer, so the clock tick still fires and the feed shows nothing — a
studio-facing script narrating a system that no longer exists.
**Owner decision 2026-09-09: keep the beat and source it from the events engine.** The events engine
already supports this: `engines/events/event_pool.py` loads weighted templates from
`src/npc_engine/data/event_pool.json` (20 templates today), each carrying `event_type`,
`severity`, `location_tag`, `summary_template`, `faction_id` and `reputation_delta` — and
`event_type: military` is already one of the thirteen in use. Add a battle-resolution template with
`event_type: military`, a `faction_id` of `iron_legion` and a `location_tag` resolving to
`loc_guard_barracks`, then update Act 5's narration in **both** files so it credits the events
engine rather than the military engine. Note the existing `location_tag` vocabulary is
`docks/keep/market/tavern/temple` — adding a barracks tag means mapping it to the seeded location
id, so check how tags resolve before inventing one. The point is that Act 5 still shows a battle
event; only its producer changes.
This also resolves **DEC-274** by a fourth option not listed in that entry — DEC-274 offered (1)
seed the armies apart, (2) give `military` a cadence gate, (3) latch the legion lose path, and
recommended (1). Deleting the engine answers the technical question; update DEC-274 to record that
as the chosen mechanism, and either close the narrative question it raised (do the armies still
meet meaningfully?) or reopen it as a new issue rather than letting it lapse.
RED anchor: a new test `tests/unit/seeds/test_seed_has_no_tick_zero_defeat.py` asserting that in the
seeded world no faction controls `DEMO_LOSE_LOCATION_ID` at tick 0 **and** that no two opposing
armies share a location at tick 0. Write it before deleting; it must fail today. Note
`tests/unit/demo/` does **not** exist — do not create a new top-level test package no `conftest.py`
covers; `tests/unit/seeds/` is the existing home.
Validation: `pytest tests/unit/seeds/test_seed_has_no_tick_zero_defeat.py -v`, then `make check`, then
`make test-demo` (baseline 1,116 passed — any delta must be explained), then run the scripted demo
and confirm Act 5 still surfaces a battle event.
Done when: `make check` green, `grep -rn "MilitaryEngine\|military_engine" src/ tests/` returns
nothing, Act 5 produces a battle event from the events engine in a live run, DEC-274 is updated, and
the LOC delta is reported (expect about -1,373 plus a further -579 for `graph/military/`).
SEV-01 sibling; findings L6-01, L9-02, L10-04, ISSUE-334, DEC-274. ✅ AUTO (T1.2, 2026-09-16)
Follow-up 2026-09-17 (interactive): the loop ran without services, so the live Act 5 check never ran,
and as wired the beat almost never fired (events every 20 ticks, `evt_21` at weight 3/74). Act 5 now
forces `evt_21` via `template_id` on `POST /v1/admin/batch/event_tick` (DEC-274 amendment). The
live-run confirmation is still outstanding — T2.4's `demo-run-live` is its first chance.
Live confirmation 2026-09-17 (T2.4): **confirmed only after a seed fix.** The first `demo-run-live` showed
`evt_21` skipped by the story-pacing severity cap (85 > 30, a seeded severity-70 quest kept pacing suppressed);
with `garrick_safe_passage` lowered to 60 (DEC-274 second amendment), Act 5 creates a `military` event at
`loc_guard_barracks` from the events engine — `act5_battle=yes` at e7d4ba87.

### Phase T2

The free latency wins. Both are small, both are user-visible, neither touches a prompt.

- [x] **T2.1** Warm the model at startup — the demo's opening line currently costs 20 seconds
Files: `src/npc_engine/main.py` (lifespan) or a new `src/npc_engine/setup/llm_warmup.py`,
`src/npc_engine/config.py`, a new prompt YAML under `src/npc_engine/prompts/`, new test
`tests/unit/setup/test_llm_warmup_on_startup.py`
Spec: `keep_alive=30m` (DEC-273) prevents the *second* cold load, not the first. Measured over
four turns on a freshly booted stack: `load_duration_ms` 10,515.194 on turn 1, then 7.863 /
10.272 / 10.065. `llm_backend_load_latency_seconds` = `{count 4, sum 10.543394, min 0.007863,
max 10.515195}` — so keep_alive verifiably works and the whole residual cost is the first load.
End to end that first turn was 20.1s against a 3-7s budget. Fix: after the app is ready, issue one
minimal generation to force the load. Add `LLM_WARMUP_ON_STARTUP: bool = True`. The warm-up prompt
text MUST live in a versioned YAML under `prompts/` — CLAUDE.md forbids prompt strings outside it,
and a one-token prompt is fine. Fail **soft**: if Ollama is not up, log via `utils/logging.py` and
continue; warm-up failure must never block boot.
RED anchor: the new test asserts that with the setting true, startup issues exactly one generation
against a mock adapter, and zero when false, and that an adapter raising during warm-up does not
prevent startup. All three fail today — there is no warm-up at all.
Validation: `pytest tests/unit/setup/test_llm_warmup_on_startup.py -v`, then `make check`.
Done when: tests pass and `make check` is green. Finding L9-04, SEV-05. ✅ AUTO (T2.1, 2026-09-17)

- [x] **T2.2** Cap the reply length — `max_tokens: 512` against a "1-3 sentences" instruction
Files: `src/npc_engine/engines/dialogue/llm_config.yaml`,
`src/npc_engine/engines/dialogue/dialogue_models.py`, new test
`tests/unit/engines/test_dialogue_response_length_cap.py`
Spec: the prompt asks for 1-3 sentences; `max_tokens` is 512, roughly 3-4x headroom, and nothing
structurally caps `npc_response`. Decode dominates a warm turn (measured 68.7 / 87.4 / 84.4%) and
scales with output tokens, so this is a real latency lever. **This fix is free**: it touches config
and schema only, NOT the prompt, so `dialogue_prompt_hash` does not change and eval comparability
survives — which matters because the owner chose to keep and repair the judged eval layer.
Do NOT trim the generation schema: DEC-273 measured that as a null result (decoded tokens 70.0 to
72.0). Derive the cap from observed good outputs and DEC-273's ~70-token typical turn; express it
as a named constant. Before lowering `max_tokens`, check `dialogue/llm_client.py` handles a reply
truncated at the cap without producing invalid JSON.
RED anchor: the new test asserts `DialogueResponse` rejects an over-long `npc_response`, accepts one
at the cap, and that the configured `max_tokens` is consistent with the schema cap. The first and
third fail today.
Validation: `pytest tests/unit/engines/test_dialogue_response_length_cap.py -v`, then `make check`.
**Also prove the hash did not move** — capture `dialogue_prompt_hash` before and after; if it
changed you edited a prompt file, and you must revert that part.
Done when: tests pass, `make check` green, hash unchanged. Finding L12-12, SEV-06. ✅ AUTO (T2.2, 2026-09-17)

- [x] **T2.3** Rate-limit WebSocket dialogue throughput
Files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py`, `src/npc_engine/api/rate_limit.py`,
`src/npc_engine/config.py`, new test `tests/unit/api/test_ws_dialogue_rate_limit.py`
Spec: the WS endpoint has a *concurrency* cap (5 per key) but no *throughput* limit.
`RateLimitMiddleware` derives from `BaseHTTPMiddleware`, which never sees
`scope["type"] == "websocket"` — so it is structurally bypassed for the one endpoint that triggers
an LLM call per turn. With one resident model, an authenticated key can starve every other player.
Fix: a per-key token bucket inside the WS handler, applied **per dialogue turn**, not per
connection — per connection is what the existing cap already does and is the wrong unit. Reuse the
bucket logic from `api/rate_limit.py` rather than writing a second implementation; extract it if it
is welded to the middleware class, and keep the existing HTTP rate-limit tests passing unchanged.
On exceeding the limit close the socket with a defined code and a structured log line, matching how
`ws_connection_cap_reached` is already reported. Named config field, no literals. Keep the error
body empty, consistent with the existing 401/403 no-body policy.
RED anchor: the new test drives more turns per interval than the limit on a single connection and
asserts the socket closes with the expected code; asserts a conforming rate is unaffected; asserts
the limit is per key, not global. All fail today — turns are unlimited.
Sequencing: **must land after T1.1**, which edits the same handler. Do not parallelise them.
Validation: `pytest tests/unit/api/test_ws_dialogue_rate_limit.py -v`, then `make check`.
Done when: tests pass, `make check` green, and the limit is above the scripted demo's turn cadence
so the demo still completes. Finding L1-01, SEV-09. ✅ (T2.3, 2026-09-17 — implemented by the loop, whose session ended before its status line; `make check` re-run green by hand and committed interactively)

- [x] **T2.4** Add a `demo-run-live` nightly target — the gate that would have caught both CRITICALs
Files: `Makefile`, `scripts/` (a new runner), `project-harness/OVERNIGHT_LOOP.md`,
`project-harness/DECISIONS.md`
Spec: closes **DEC-280(a)**, open and undecided since 2026-09-07; the owner decided 2026-09-09 to
build it. Both of Sprint 1's CRITICALs — the WebSocket slot leak that killed the demo after five
turns, and the military engine losing the game on tick 5 — were invisible to every gate and were
found only by running the system. `make check` executes zero real Cypher (`WITH_SERVICES=0`) and
never boots the app, so it structurally cannot see this class of defect.
Add a `demo-run-live` target that drives the scripted demo through **real API calls** against a
running stack — not `--dry-run`, which is what makes the existing demo tests blind to it. Assert the
run reaches its final act and that no act produced an empty required beat.
**It must not be wired into `make check`, and must not fail a task.** `make check` is the per-task
gate and is already ~12 minutes; adding a stack boot to it would make every task pay for it and
would give the loop a failure it cannot repair. Wire it into the nightly loop's **post-run report**
instead, alongside `make roadmap-audit`, so a broken demo is visible the next morning without ever
blocking a commit. Record the placement decision in `DECISIONS.md` against DEC-280(a).
Sequencing: **after T1.1 and T1.2**, or the target's first run fails for defects those tasks fix.
RED anchor: run the target against the tree as it stood before T1.1 — the demo dies partway and the
target reports failure. On the current tree it must complete. A target that passes on both is not
checking anything.
Validation: `make demo-run-live` against a stack brought up with `make eval-stack-up` (rebuild
first — the app image is not bind-mounted), then `make check` to confirm the target was **not** added
to it.
Done when: the target exists, is reported by the nightly loop, is absent from `make check`'s target
list, and DEC-280(a) is closed in `DECISIONS.md`. Finding R6-04, DEC-280(a). ✅ (T2.4, 2026-09-17 — interactive, live stack; RED at `a1365cc5^` died ACT 6 on the WS 403; first GREEN failed on three real demo defects, fixed in-task (seed pacing suppression → DEC-274 second amendment, ACT 7 gossip boundary + clock key, ACT 8 route); final `DEMO_LIVE=PASS acts_reached=12/12`; evidence in DEC-280(a))

---

# SPRINT 2 — Delete the political layer and the dead engines

**Self-contained goal:** the engine portfolio contains only engines that are reachable and do
work. About 6,400 LOC leaves the repo. Deletion is cheapest immediately before a refactor, which
is why this sprint precedes the ports collapse and the test prune.

### Phase T3

The political cluster. `military` already went in T1.2; **four** remain — `agenda` was removed from
the delete set by the owner on 2026-09-09 and survives intact.

- [x] **T3.1** Delete `succession` and `oath`
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-279
Files: delete `src/npc_engine/engines/succession/`, `src/npc_engine/engines/oath/`,
`src/npc_engine/engines/ports/pledge_port.py`,
`src/npc_engine/graph/repositories/pledge_repository.py`, and their tests; edit
`src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/api/dependencies_advanced/politics.py`,
`src/npc_engine/api/dependencies_engines/engine_slots.py`,
`src/npc_engine/api/dependencies_engines/tick_slots.py`,
`src/npc_engine/graph/repositories/__init__.py`, `src/npc_engine/engines/ports/__init__.py`,
`docs/ENGINES.md`
Spec: neither is reachable from an API route via its engine class. `succession` grants vacant
inheritable titles; `oath` expires and counts violations on pledges.
**`agenda` is NOT deleted (owner, 2026-09-09).** The whole of `src/npc_engine/engines/agenda/`
survives — `agenda_engine.py`, `intent_formation_engine.py` and `conversation_intent_service.py`.
Three consequences follow and each is load-bearing:
(a) **`engines/ports/political_port.py` and `graph/repositories/political_repository.py` survive.**
`PoliticalGraphPort` is shared: `succession_engine.py:18,35` and `agenda_engine.py:18,36` both
inject it, and only succession goes. Deleting the port or the repository breaks the surviving
`AgendaEngine`. This is the one place the per-engine checklist's step (2)/(3) condition — "only if
no surviving engine imports it" — actually bites in this task.
(b) **`api/dependencies_advanced/politics.py` survives.** It holds five builders today (treaty,
oath, succession, agenda, military at `:26,43,60,77,94`). T1.2 removes the military builder, this
task removes oath and succession, and T3.2 removes treaty — leaving `get_agenda_engine` at `:77`.
Edit the file down to that one builder; do **not** delete it.
(c) `oath`'s `PledgeGraphPort` and `Neo4jPledgeRepository` have no other consumer — verified
2026-09-08 — so both go with the engine.
**Keep `graph/political/pledge_service.py`** — `routes/faction_politics/pledges.py` uses it and
`demo_game/client.py:1326/1357/1377` reads it. The engines are the writers; the services are the
readers, and only the writers go.
Deletion checklist per engine — work through it exactly: (1) the engine dir; (2) its port file, but
only if no surviving engine imports it; (3) its repository, same condition; (4) its contract YAML
under `engines/contracts/` if one exists; (5) its tests, including any `tests/contract/test_*`;
(6) its `TickScheduler.__init__` parameter and its entry in `_ordered_tick_engines()`; (7) its slot
in `engine_slots.py` and its builder in `dependencies_advanced/politics.py`; (8) any `Settings`
field only it read; (9) its row in `docs/ENGINES.md`; **(10) its re-export in
`graph/repositories/__init__.py` and in `engines/ports/__init__.py`.** Step (10) is not optional and
is the single most likely cause of a red gate on a deletion task: both barrels import every
repository and port by name (`repositories/__init__.py:34-75` lists eight this sprint removes), so a
deleted module stays importable until the barrel is edited and then fails at collection — a red the
agent cannot attribute and, if the barrel is outside `Files:`, cannot legally fix.
RED anchor: `python scripts/check_layers.py` and `make check` must be green after removal, and
`grep -rn "SuccessionEngine\|OathEngine\|PledgeGraphPort" src/ tests/` must return nothing. Before
deleting, run that grep and record the hit count — that count going to zero is the anchor. Do
**not** include `AgendaEngine` or `PoliticalGraphPort` in the grep; both survive, and a grep driven
to zero on those means you deleted something you should not have.
Validation: `make check`, then `make test-demo`. The demo must still read pledges.
Done when: green, grep clean, `AgendaEngine` still constructible via
`dependencies_advanced/politics.py`, and LOC delta reported (expect about -600; the original -835
assumed `agenda` went too).
Findings L10-03, DEC-279. ✅ AUTO (T3.1, 2026-09-16)

- [x] **T3.2** Delete `treaty` and `faction_politics`
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-279
Files: delete `src/npc_engine/engines/treaty/`, `src/npc_engine/engines/faction_politics/`,
`src/npc_engine/engines/ports/treaty_port.py`,
`src/npc_engine/engines/ports/faction_politics_port.py`,
`src/npc_engine/graph/repositories/treaty_repository.py`,
`src/npc_engine/graph/repositories/faction_politics_repository.py`, and their tests; edit the same
wiring files as T3.1 — including `graph/repositories/__init__.py` and `engines/ports/__init__.py` —
**plus `src/npc_engine/api/dependencies_engines/core.py`**, which T3.1's list does not name and which
imports `FactionPoliticsEngine` at `:24`, builds it at `:150` and imports its repository at `:157`
Spec: same shape as T3.1 and the same checklist, **including step (10)**. `treaty` expires treaties and counts violations;
`faction_politics` decays faction standings toward neutral on a per-tick pass.
**Keep `graph/political/treaty_service.py` and the faction service** — `routes/faction_politics/`
and `demo_game/client.py:1410/1446/1463` and `:1829` read them, and those reads must keep working.
Behavioural consequence to state plainly in the completion note: standings no longer decay and
treaties no longer expire, so that data becomes static. The owner accepted this on 2026-09-08; it
is not visible in a five-minute demo, but it must be written down rather than discovered later.
RED anchor: as T3.1 — record the pre-deletion hit count of
`grep -rn "TreatyEngine\|FactionPoliticsEngine\|TreatyGraphPort\|FactionPoliticsGraphPort" src/
tests/` and drive it to zero with `make check` staying green.
Validation: `make check`, then `make test-demo`.
Done when: green, grep clean, LOC delta reported (expect about -1,540), **and** the completion note
states the frozen-data consequence explicitly — standings no longer decay and treaties no longer
expire, so `pledge_service`, `treaty_service` and the faction service become read paths that
outlived their last writer. Nothing detects that class of defect mechanically; the owner decided
2026-09-09 that the written note is the control, which makes writing it part of the finish line
rather than a courtesy. **Do not attempt the live check here** — confirming the kept services still
return data needs a running stack built from this commit, and that is T3.3 alone (split 2026-09-17,
the same way T6.3 was split from T5.1/T5.2).
Findings L10-03, DEC-279. ✅ AUTO (T3.2, 2026-09-17)

- [x] **T3.3** Confirm on a running stack that the kept faction and treaty read paths still return data
Files: `project-harness/ROADMAP.md` (tick note), `project-harness/ISSUES.md` (only if a check fails)
Spec: the live tail of T3.2, split out so the loop can do the deletion unattended. T3.2 keeps
`graph/political/treaty_service.py` and the faction service because `routes/faction_politics/` and
`demo_game/client.py:1410/1446/1463` and `:1829` read them. `make check` executes zero real Cypher
(`WITH_SERVICES=0`), so a kept service whose queries now return nothing looks identical to one that
works — only a live read tells them apart.
Bring up the isolated stack from the post-T3.2 tree with `make eval-stack-up` — **rebuild first, the
app image is not bind-mounted**, so an old image would confirm the pre-deletion code — then
`make eval-stack-seed`, and call `GET /v1/admin/factions/`. Assert a **non-empty** standings list,
not merely a 200. Also exercise the demo's treaty reads at the `demo_game/client.py` lines above
and confirm none errors.
Do NOT run the integration suite for this: it writes to the live Neo4j (ISSUE-277).
RED anchor: none — this is a confirmation task. An empty list or an erroring read is the failure it
exists to catch: if you see one, do not tick; log it in `ISSUES.md` as a T3.2 regression, naming the
service and the query.
Validation: the live calls above against the isolated stack, then `make check`.
Done when: `GET /v1/admin/factions/` returns non-empty standings on a stack built from a tree that
contains T3.2, the demo's treaty reads succeed, and the tick note records the standings count
observed. Findings L10-03, DEC-279. ✅ AUTO (T3.3, 2026-09-17)

### Phase T4

The seed split first (moved to the head of the phase 2026-09-17: a halt on T4.1 or T4.2 skips the
rest of the phase, and T5.1/T5.2 red `check-rules` without it), then the remaining dead and
unreachable engines, then a gate so this never regrows.

- [x] **T4.3** Split `demo_game/seeds/seed.py` so Sprint 3 has headroom
Pre-approved: file-deletion, public-interface · owner 2026-09-09
Files: `demo_game/seeds/seed.py`, new modules under `demo_game/seeds/`,
`scripts/rules_baseline.txt`, `demo_game/tests/` as needed
Spec: `demo_game/seeds/seed.py` is **1,677 lines** and `scripts/rules_baseline.txt:5` carries
`R001|demo_game/seeds/seed.py:1677` — the file is at *exactly* its recorded count, with zero
headroom. `check_rules.py:241` marks a **new** violation when `count > baseline`, so a single added
line reds `check-rules` and exits 1.
T5.1 and T5.2 are both pure additions to this file. Without this task they are structurally
guaranteed to red the gate, and the loop's repair path cannot rescue them: `check-rules` is
AUTOFIX-class so a `/fix-make-failure` session is spawned, but that session may touch neither
`scripts/rules_baseline.txt` nor `scripts/check_rules.py` (both `FROZEN_PATH_PREFIXES`), and any
line matching `--update\b` trips the ratchet-update suppression. Its only legal remedy would be
splitting a 1,677-line seed file **unattended** — which risks the one thing this repo calls
immovable.
So do the split here, deliberately, in a task session. Split by seeded domain — characters,
locations, armies, needs, the gossip path — into sibling modules under `demo_game/seeds/`, keeping
`seed.py` as the orchestrator that calls them. **NPC ids in the seed are stable — do not rename a
single one**, and do not change what is seeded: this is a pure move. Then ratchet
`scripts/rules_baseline.txt` down to the new counts with `make check-rules-update`, stating the old
and new numbers in the commit message.
This also pre-pays work T13.2 and T14.2 will otherwise have to do under a demo trim.
RED anchor: `wc -l demo_game/seeds/seed.py` is 1677 and `grep -n "seed.py" scripts/rules_baseline.txt`
returns `R001|demo_game/seeds/seed.py:1677` — equal, i.e. zero headroom. Add one blank line and
confirm `python scripts/check_rules.py` reds; remove it. That red is the anchor, and it is what
T5.1 would hit.
Validation: `python scripts/check_rules.py`, `make check`, then `make test-demo` (baseline 1,116
passed — the count must not move; this is a move, not a behaviour change), then prove the world is
identical on the eval stack: `bash scripts/eval_stack_at.sh <pre-split-sha> --reset`, `make
eval-stack-seed`, export every node (labels, id, properties) and relationship over
`bolt://localhost:7688`; repeat from this tree; diff the two exports.
Done when: no module under `demo_game/seeds/` exceeds 800 lines, the two graph exports are identical, every NPC id is unchanged,
`make test-demo` is unmoved at 1,116, the baseline is ratcheted, and the LOC delta is reported
(expect roughly flat — a split adds import and docstring lines). ✅ AUTO (T4.3, 2026-09-17)

- [x] **T4.1** Delete `mood`, `clique`, `skill`, `deception`, `currency` and the dead classes
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-279
Files: delete `src/npc_engine/engines/mood/`, `engines/clique/`, `engines/skill/`,
`engines/deception/`, `engines/currency/`, `engines/contracts/currency_engine.yaml`,
`engines/ports/mood_port.py`, `engines/ports/group_port.py`, `engines/ports/skill_port.py`,
`graph/repositories/mood_repository.py`, `graph/repositories/group_repository.py`,
`graph/repositories/skill_repository.py`, `engines/story_pacing/pacing_queries.py`, the
`SchemingEngine` class inside `engines/scheming/`, and all their tests; edit
`src/npc_engine/api/dependencies_advanced/social.py`,
`src/npc_engine/api/dependencies_advanced/progression.py`, `scheduler/tick_scheduler.py`,
`api/dependencies_engines/engine_slots.py`, `src/npc_engine/graph/repositories/__init__.py`,
`src/npc_engine/engines/ports/__init__.py`, `evals/scenario_adapters_extra.py`,
`project-harness/ISSUES.md`, `docs/ENGINES.md`
Spec: use the T3.1 checklist for each, **including step (10)** — the repository and port barrels.
Per-engine notes:
`currency` has 12 lines of docstring and no implementation, yet ships `currency_engine.yaml` and a
passing contract test — delete the contract and the contract test with it (finding L10-01).
`deception` — delete the `DeceptionEngine` class; it has zero production construction sites. The
*capability* partly survives through `knowledge_learning` plus gossip distortion.
`skill` awards quest-completion XP; `routes/economy/skills.py` uses `graph.character.skill_service`
directly, so **keep that service** and delete only the engine.
`mood` and `clique` both key off co-location that never happens; nothing surfaces either to a
player. `clique` uses `GroupGraphPort`.
`SchemingEngine` — delete the class **only**. `SchemeAdvanceTick` in the same dir is live and wired
at `tick_slots.py:43,187-194`; the dir stays (finding L10-02).
`story_pacing/pacing_queries.py` is a backward-compat re-export shim whose own docstring says it
has no active importers — delete the file, keep the `story_pacing` engine.
**ISSUE-338 is made moot by this task and must be closed here, not left open.**
`evals/scenario_adapters_extra.py:187-211`'s `scenario_mood_contagion` never co-locates its two NPCs
(the Location POST 422s silently) and passes vacuously by asserting only that `current_mood` is
non-`None`. Once `mood` is gone that scenario references a deleted engine, and ISSUE-338's own
proposed fix — "assert a mood *change*" — becomes actively wrong advice for a mechanism that no
longer exists. Delete or retarget the scenario, and mark ISSUE-338 `[FIXED]` (superseded by
deletion) with the `**Fixed:**` line, moving it into `archive/ISSUES_RESOLVED.md`. Note the file is
**not** under `evals/cases/`, which is why the eval-case sweep for deleted engines does not reach it.
RED anchor: record the pre-deletion hit count of
`grep -rn "MoodContagionEngine\|CliqueFormationEngine\|SkillProgressionEngine\|DeceptionEngine\|SchemingEngine\|pacing_queries" src/ tests/`
and drive it to zero with `make check` green.
Validation: `make check`, then `make test-demo`.
Done when: green, grep clean, ISSUE-338 archived, LOC delta reported (expect about -2,443).
Findings L10-01, L10-02, ISSUE-338, DEC-279. ✅ AUTO (T4.1, 2026-09-17)

- [x] **T4.2** Gate the portfolio — an engine must be reachable and must do work
Files: new `scripts/check_engine_census.py`, `Makefile`, `scripts/loop_gates.py`, new
`tests/unit/scripts/test_check_engine_census.py`
Spec: this is rule 3 ("no code without a live caller") applied to engines, and it is what would
have caught this entire sprint's worth of dead code years earlier. The gate asserts, for every
directory under `src/npc_engine/engines/` that declares a tick engine: (a) it is wired into
`TickScheduler` — a constructor parameter filled from `api/dependencies_*`; and (b) it appears in
`_ordered_tick_engines()` or is called directly by the scheduler. Non-tick engines (`dialogue`,
`economy`, `interaction`, `quest`, `relationship`, `knowledge_learning`, `idempotency`, **`emotion`**)
are exempt from (a) and (b) but must be imported by at least one file under
`src/npc_engine/api/routes/`. Infra dirs `ports/`, `contracts/`, `llm/`, `tts/` are exempt entirely —
list them explicitly in the script rather than pattern-matching, so an addition is a conscious edit.
`emotion` was missing from the original list and is live code: it declares no `run_tick` and so is
in no scheduler slot, but `api/routes/dialogue/npc_state.py` imports it. A directory matching none
of the three buckets must make the script **fail loudly**, never pass or fail by default — an
unlisted directory should be a conscious edit, and with no explicit rule the gate's behaviour on
`emotion` would depend on an implementation detail nobody wrote down.
**Two structural traps to handle explicitly.** (1) Six ordered names differ from their directory:
`skill`→`skill_progression`, `mood`→`mood_contagion`, `need`→`need_decay`, `memory`→`memory_decay`,
`scheming`→`scheme_advance`, `investigation`→`scheme_detection`. Map name→dir explicitly rather than
assuming they match. (2) Several engines are reached by a direct scheduler call rather than through
`_ordered_tick_engines()` — `routine` (`tick_scheduler.py:464`), `chapter` (`:467`),
`memory_consolidation` (`:535`), `story_pacing` (constructor `:60`), plus the interval gossip and
event paths — so clause (b) must accept a direct call as wiring.
Do NOT gate on "does work at runtime" here — that needs a running stack and belongs in T6.1.
Wire it into `make check` next to `check-layers`, **and register it in `scripts/loop_gates.py`** (see
`Done when:`).
RED anchor: **do not use `git stash` or a second `git worktree`** — the loop refuses to start on a
dirty tree (`expand_loop.sh:191`), a stray stash poisons the next run (`MAX_LOOP_STASHES=3` exists
because this has happened), and a nested worktree inherits the missing-toolchain problem T0.1
documents. Use a read-only extraction instead: `git archive <pre-sprint-sha> | tar -x -C <tmpdir>`,
and give the script a `--root` flag so it can be pointed at that directory. Record the pre-sprint
SHA in the completion note. It must report the engines this sprint deleted against that tree and
zero against the current one. **If it reports zero against both, the script is not checking anything
and must be fixed before you tick** — a gate that passes vacuously is the exact artifact this
programme was written about. The `--root` flag also makes the gate testable from
`tests/unit/scripts/` with no git operation at all.
Validation: `python scripts/check_engine_census.py`, then `make check`.
Done when: the gate is in `make check`, green on this tree, demonstrably red on the pre-sprint tree,
**and registered in the loop's classifier** — appended to `AUTOFIX_CHECK_SPECS` in
`scripts/loop_gates.py` (it asserts structure, not behaviour, so it is form-class), with the script
itself appended to `FROZEN_PATH_PREFIXES`. Without that registration the first red it ever produces
classifies as `UNATTRIBUTED` (`classify_gate_failure.py` exit 3), no repair is attempted, and the
night ends two phases later with a message naming neither the gate nor the cause. Append the entries
in the **same commit** as the gate, once its `make` target exists — an entry naming a missing target
makes the classifier report a phantom AUTOFIX failure. (Owner, 2026-09-17: the loop makes this edit
itself; `classify_gate_failure.py` re-imports `loop_gates.py` on every run, so it takes effect at the
next gate.)
Findings L10-03, rules 3 and 7. ✅ AUTO (T4.2, 2026-09-17)

---

# SPRINT 3 — Bring the world to life

**Self-contained goal:** NPCs follow daily schedules and have needs, so co-location is real and
gossip pair-selection means something. Two engines go from provably dead to provably working.

**Split note:** the seed edits are mechanical and are loop work. Only the confirmation that the
revived engines actually move NPCs needs a running stack, and that is T6.3 alone. An earlier draft
deferred the whole of T5, which would have meant the loop skipped this sprint's entire purpose.

### Phase T5

The seed defects. Both are graph-shape bugs that no observable can currently express, and both are
pure edits to `demo_game/seeds/seed.py` plus a unit test — no services required.

- [x] **T5.1** Seed `:Schedule` nodes and `FOLLOWS_SCHEDULE` edges so `routine` can move NPCs
Pre-approved: graph-schema · owner 2026-09-08 · DEC-276
Files: `demo_game/seeds/seed.py` (and the domain module T4.3 split it into), new test
`demo_game/tests/seeds/test_seed_schedules.py`
Spec: `routine_engine` moves active characters to their scheduled locations each tick. Measured on
a running stack it returns `{'moved': 0, 'skipped': 0}` — `skipped` is 0 too, meaning its query
matched **nothing**. A label census confirms no `Schedule` label exists, and
`grep -n "Schedule\|FOLLOWS_SCHEDULE" demo_game/seeds/seed.py` returns no matches: the seed never
writes them. Two more live engines starve behind this — `proactive_dialogue` and `player_model` —
along with gossip pair-selection, all of which key off NPCs being in the same place.
Add a `:Schedule` node per seeded NPC with time-of-day slots referencing locations that already
exist in the seed, and a `FOLLOWS_SCHEDULE` edge from each `:Character`. Keep it small: the three
demo MetaHumans plus the NPCs on the gossip path are enough. **NPC ids in the seed are stable — do
not rename them.** Read `src/npc_engine/type_registry/` for the declared `Schedule` node shape and
conform to it; do not invent properties. If the registry declares no `Schedule` type, that is a
blocking prerequisite — halt and say so rather than inventing a schema.
This task is complete when the seed writes the data. Proving the engine then moves someone is T6.3.
RED anchor: the new test asserts that after seeding, every seeded `:Character` has a
`FOLLOWS_SCHEDULE` edge to a `:Schedule` whose slots reference existing location ids. It fails today
with zero schedules found.
Validation: `pytest demo_game/tests/seeds/test_seed_schedules.py -v`, then `make check`, then
`make test-demo`.
Done when: the test passes and `make check` is green. Finding L13-01. ✅ AUTO (T5.1, 2026-09-17)

- [x] **T5.2** Add `HAS_NEED` edges so `need_decay` stops being dead
Pre-approved: graph-schema · owner 2026-09-08 · DEC-276
Files: `demo_game/seeds/seed.py` (and the domain module T4.3 split it into), new test
`demo_game/tests/seeds/test_seed_needs.py`,
new `src/npc_engine/type_registry/base_edges/has_need.yaml`, `project-harness/ISSUES.md`
Spec: the seed writes 28 `:Need` nodes carrying a `character_id` **property**, but never the
`HAS_NEED` **edge** that `graph/needs_goals/need_queries.py` matches on
(`(:Character)-[:HAS_NEED]->(:Need)`). A complete live relationship census — 13 types — contains no
`HAS_NEED`. `need_decay` and `need_quest_trigger` are therefore both dead and both report 0.
This is partially logged as ISSUE-210/213 but scoped there as a cosmetic empty prompt field
(`npc.top_need`). It is not cosmetic: it is two dead engines. **Re-scope ISSUE-210** in this same
task — correct its severity and description to say so.
**Prerequisite, resolved here rather than by halting.** `HAS_NEED` is used in production Cypher
(`graph/needs_goals/need_queries.py:33,61,95`, `need_writer.py:27,50`) but is **not** declared in
`src/npc_engine/type_registry/base_edges/` — only `satisfies_need.yaml` is. T5.1 four lines earlier
sets the rule "if the registry declares no type, halt and say so rather than inventing a schema",
and applying that rule here would skip phase T5 and take T5.1 with it. Do not halt: adding
`base_edges/has_need.yaml` is **part of this task and pre-approved** (owner 2026-09-08). The edge
already exists in the running graph, so the declaration records reality rather than changing the
schema. Conform it to the existing writer at `need_writer.py:50`, and note the registry gap in the
completion note — an edge the engine writes and the registry does not know about is the same class
of defect as the missing edge itself.
Fix: write the `HAS_NEED` edge alongside each `:Need` node. Also add `SATISFIES_NEED` edges from
locations if the registry declares that edge type, since `need_decay` adds magnitude back at
satisfying locations and without them the decay is one-directional. If the registry does not declare
it, log an issue and leave it.
Sequencing: this revives `need_quest_trigger`, which **increases** the quest-generation LLM
amplification that Sprint 4 exists to bound. That is acceptable because Sprint 4 follows
immediately; do not reorder the two sprints.
RED anchor: the new test asserts every seeded `:Need` is reachable from its `:Character` via
`HAS_NEED`. It fails today with zero such edges found.
Validation: `pytest demo_game/tests/seeds/test_seed_needs.py -v`, then `make check`, then `make test-demo`.
Done when: the test passes, `make check` is green, and ISSUE-210 is re-scoped. Finding L13-02. ✅ AUTO (T5.2, 2026-09-17)

- [x] **T5.3** Read gossip distortion back — it is written on every hop and discarded on read
Pre-approved: public-interface · owner 2026-09-09
Files: `src/npc_engine/graph/gossip/gossip_batch_queries.py`, new test
`tests/unit/graph/test_gossip_distortion_read_back.py`, `project-harness/DECISIONS.md`
Spec: **CR-L01-01 from the 2026-08 review, re-verified live in the tree on 2026-09-08 and absent
from this roadmap until now.** `CYPHER_BATCH_PROPAGATE_KNOWLEDGE` at
`gossip_batch_queries.py:60` faithfully writes `k.distorted_summary = w.distorted_summary` on every
propagation hop. The event-trust read query at `:34-46` then selects
`best_event.summary AS summary` — straight off the canonical `:Event` node — and never reads
`k.distorted_summary` from the sharer's own `KNOWS_ABOUT` edge. Distortion is computed, stored, and
thrown away on every read. Every NPC therefore recounts the canonical text no matter how many hops
it travelled.
This is not cosmetic and it is not a performance defect: **it silently defeats the one mechanic the
product pitch rests on** — "no one has cracked persistent knowledge propagation". It also sits
directly downstream of this sprint: T5.1 and T5.2 make co-location and gossip pair-selection real,
which makes propagation actually happen, which makes the discarded distortion matter for the first
time.
Fix: select `k.distorted_summary` from the sharer's `KNOWS_ABOUT` edge, falling back to
`best_event.summary` **only** where no `KNOWS_ABOUT` edge exists yet (a first-hand witness, who
legitimately has the canonical text). Do not change the write side — it is correct. Record in
`DECISIONS.md` that this changes what a gossip read returns, since any recorded eval output
containing gossip text predates the fix.
RED anchor: the new test seeds a two-hop propagation with a distortion applied at each hop and
asserts the second-hop reader sees text that **differs** from the canonical `:Event` summary. It
fails today — the two are identical, which is the bug.
Validation: `pytest tests/unit/graph/test_gossip_distortion_read_back.py -v`, then `make check`.
Done when: the test passes, `make check` is green, the `DECISIONS.md` note is written, and the
completion note records that CR-L01-01 is closed — it survived two review cycles under a `CR-L*` id
this programme never cross-referenced.
Finding CR-L01-01 (`review-2026-08/TRIAGE.md`). ✅ AUTO (T5.3, 2026-09-18)

### Phase T6

Fix the bug that would silently undo Sprint 3, pin the order, then prove the revival on a stack.

- [x] **T6.1** Re-read world state inside the tick loop — batched advances see a frozen clock
Pre-approved: public-interface · owner 2026-09-08
Files: `src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/config.py`,
`src/npc_engine/api/routes/world/clock.py`, new test
`tests/unit/scheduler/test_advance_rereads_world_state.py`, new
`tests/unit/api/test_clock_advance_delta_bound.py`
Spec: two defects in one call path. (1) `tick_scheduler.py:568-582` reads
`world_state = await get_world_state(...)` **once, before** the `for tick_id in range(...)` loop and
passes the same object into every iteration. So `routine.run_tick(time_of_day=...)` at `:464` sees a
frozen time-of-day for all N ticks, and `_maybe_consolidate_memory` at `:538-543` builds its
`TimePoint` from the same stale snapshot. **This directly undoes T5.1**: a batched advance would
move every NPC into the same slot N times. (2) `config.py:52` sets `MAX_DELTA_TICKS = 1000` and
`api/routes/world/clock.py:37` accepts `delta_ticks` up to it, all inside `async with self._lock` on
one session — at the measured 433-570ms deterministic floor that is about 8 minutes of held lock
with no LLM work at all.
Fix (1) by re-reading world state per tick, or at minimum recomputing `time_of_day` and the
consolidation `TimePoint`. Fix (2) by lowering `MAX_DELTA_TICKS` to single digits. Before lowering
it, `grep -rn "delta_ticks" demo_game/ evals/ e2e/` and confirm no caller relies on a large batch.
If large catch-up advances are genuinely needed, do NOT raise the cap — log a `DECISIONS.md`
question proposing a background job instead, and move on.
RED anchor: the first test advances N>1 ticks across a time-of-day boundary and asserts engines
observe **changing** time-of-day. It fails today. The second asserts a `delta_ticks` above the new
cap is rejected with 422 and the boundary value is accepted.
Validation: `pytest tests/unit/scheduler/ tests/unit/api/test_clock_advance_delta_bound.py -v`, then
`make check`. Measure the added per-tick graph read against the 433-570ms baseline and confirm it is
noise, not a new regression.
Done when: both tests pass and `make check` is green. Finding L13-09, SEV-08. ✅ AUTO (T6.1, 2026-09-18)

- [x] **T6.2** Pin the tick execution order
Files: new `tests/unit/scheduler/test_tick_order.py`, `docs/ENGINES.md`
Spec: `ENGINES.md` says the scheduler runs engines in a fixed order so upstream state is visible
downstream in the same tick, and the review mapped real read-after-write dependencies
(`review-fixes/evidence/L13.md` section A.2). Nothing pins the order. Reordering
`_ordered_tick_engines()`, or inserting a new engine in the wrong position, silently changes
behaviour and no test goes red — and the failure mode is not a crash but an engine reading state
that has not been written yet, which per the census looks identical to healthy idleness.
Write two kinds of assertion: (a) one test pinning the **full** engine execution order as an
explicit expected sequence — keep the expected list literal in the test, never imported from the
source it checks, or it asserts nothing; (b) targeted tests for each read-after-write pair in
L13.md section A.2, asserting the writer's index is lower than the reader's. The pairwise tests
survive a legitimate reorder; the full-sequence test intentionally does not.
**Two of L13.md §A.2's twelve pairs name engines that no longer exist by the time you run this**, so
**ten** pairs remain to test: skip `mood_contagion (11)` reading co-location written by `routine (4)`
— `mood_contagion` is deleted by T4.1, one phase earlier — and `faction_politics (6)` reading
`:Event` rows written by `gossip (2)`/`event (3)`, deleted by T3.2 two phases earlier. That table is
frozen evidence written before Sprint 2's deletions were decided; nothing downstream re-validated it.
Importing `MoodContagionEngine` or `FactionPoliticsEngine` in the new test fails at collection and
reds the gate for a reason unrelated to the ordering work.
Make (a)'s failure message print expected vs actual and point at `ENGINES.md`, so the next person
can tell an intentional reorder from an accident. Cross-check `ENGINES.md` against the real order and
correct the doc if they disagree — **report the discrepancy rather than silently conforming the doc
to the code.**
Note the order changed in Sprints 1-2 as engines were deleted; pin the order as it is *now*.
RED anchor: swap two adjacent engines in `_ordered_tick_engines()`, run the test, confirm it goes
red, restore. A test that does not go red here is not finished.
Validation: `pytest tests/unit/scheduler/test_tick_order.py -v`, then `make check`.
Done when: both kinds of test pass and the swap experiment was observed red. Finding L13-10, SEV-15. ✅ AUTO (T6.2, 2026-09-18)

- [x] **T6.3** Confirm on a running stack that `routine` and `need_decay` now do work
Files: new `tests/integration/test_revived_engines_do_work.py`, `project-harness/ROADMAP.md`
(carry-forward note)
Spec: this is the live tail of T5.1 and T5.2, split out so the loop can grind the seed edits
unattended and only this needs a stack. Bring a stack up, advance the clock several ticks against
the seeded world, then read `GET /v1/admin/system/engines` and assert `routine` reports a non-zero
`moved` count and `need_decay` reports a non-zero worked count. Also confirm `npc.top_need` is
populated for at least one NPC, which is the user-visible half of ISSUE-210.
If either is still zero after T5.1 and T5.2 landed, do not tick this task — the seed edit did not
achieve its purpose and the defect is upstream. Say which one, and log it.
**Read a zero carefully, because this task runs in the one unbounded window in the programme.**
T5.2 revives `need_quest_trigger`, and Sprint 4 — which bounds the resulting amplification — has not
landed yet. T7.2 costs a saturated tick at up to 84 model calls against a single resident model with
no admission control (T8.1 is also not in) and a 10s per-call timeout. This is the first live tick
advance after `HAS_NEED` edges exist and before any of that is fixed. So **advance ticks one at a
time and watch the log for LLM timeouts**: a zero or flaky `need_quest_trigger` count *under visible
timeout errors* is a Sprint-4 ordering artifact, not evidence T5.2 failed — do not use it to reopen
Sprint 3. A zero with a clean log is the real signal this task is looking for.
Do NOT run the whole integration suite to do this: it writes to the live Neo4j and there is no
separate test database (ISSUE-277). Bring up the isolated stack via `make eval-stack-up`, and
rebuild first — the app image is not bind-mounted, so without a rebuild you are measuring the old
seed.
RED anchor: run this against the tree as it stood before T5.1 — both engines report zero, and the
test fails. That failure is the evidence the sprint was needed.
Validation: run against the isolated stack, then `make check`, then tear the stack down.
Done when: both engines demonstrably do work, and the carry-forward note recording the co-location
revival is added for downstream sprints. Findings L13-01, L13-02. ✅ AUTO (T6.3, 2026-09-18)


---

# SPRINT 4 — Stop the tick from starving the player

**Self-contained goal:** background work can no longer push an interactive dialogue turn past its
budget. This is the sprint that matters most for running a small local model well — the review
found contention, not model size, is the binding constraint.

### Phase T7

Reduce the offered load before arbitrating it.

- [x] **T7.1** Make `TICK_LLM_CALLS_PER_MINUTE_MAX` real — it is broken on three axes
Pre-approved: public-interface · owner 2026-09-08
Files: `src/npc_engine/scheduler/tick_budget_guard.py`, `src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/scheduler/tick_autopilot.py`, `src/npc_engine/api/routes/world/clock.py`,
`src/npc_engine/config.py`, new tests
`tests/unit/scheduler/test_skip_llm_engines_covers_quest_triggers.py`,
`tests/unit/scheduler/test_tick_budget_guard_counts_calls.py`,
`tests/unit/api/test_advance_clock_passes_skip_llm.py`
Spec: this is the only mechanism meant to stop background work eating the interactive model, and
all three of its axes are broken. **Wrong unit:** `tick_budget_guard.py:54-61`'s
`record_llm_tick()` appends one timestamp per *tick* regardless of how many model calls that tick
made — a tick making 84 calls costs the budget 1. Its only caller is `tick_autopilot.py:102`, which
is the mechanical proof of the wrong-entry-point axis below. (The file is 71 lines; an earlier draft
cited `:76-83`, past its end.) **Wrong coverage:** `skip_llm_engines` is read at
exactly two sites, `tick_scheduler.py:467` (`chapter`) and `:535` (`memory_consolidation`); the
three quest triggers run at `:472` in the ungated `_ordered_tick_engines()` list and are 63 of the
84 worst-case calls, so shedding removes 25% and leaves 75%. **Wrong entry point:**
`tick_scheduler.py:552` declares `advance(..., skip_llm_engines: bool = False)` but
`advance_clock` never passes it — `grep -rn "skip_llm_engines" src/npc_engine/api/` returns
nothing, and `ENGINES.md:29-31` calls `game_driven` the *recommended* mode, so in the recommended
mode the guard does not exist at all.
Do the steps in this order. **Step 1 first — it is about five lines and delivers most of the
value:** extend `skip_llm_engines` to cover the three quest triggers, exactly as `chapter` and
`memory_consolidation` are already gated. Step 2: move the gate from the autopilot into
`TickScheduler.advance()` so both clock modes get it, and have `advance_clock` pass it through.
Step 3: increment the guard per **call** rather than per tick — DEC-273's `llm_backend_calls_total`
counter already sits at the right seam — and reconcile the setting's name with its unit. Steps 2
and 3 change a public config contract, so record them in `DECISIONS.md`.
RED anchor: `test_skip_llm_engines_covers_quest_triggers` asserts that with the flag true the three
quest trigger engines make **zero** LLM calls through a mock adapter. It must fail on the current
tree; that failure is the bug. The other two tests likewise fail today.
Validation: `pytest tests/unit/scheduler/ tests/unit/api/test_advance_clock_passes_skip_llm.py -v`,
then `make check`.
Done when: all three pass, `make check` green, DECISIONS entry written. Finding L13-05, **SEV-02**. ✅ AUTO (T7.1, 2026-09-18)

- [x] **T7.2** Give the three quest triggers one shared per-tick model budget
Files: `src/npc_engine/engines/quest_generation/quest_generation_engine.py`,
the trigger modules in `src/npc_engine/engines/quest_generation/` — `event_quest_trigger.py`,
`need_quest_trigger.py`, `world_state_quest_trigger.py` (they are **not** in `engines/quest/`, which
holds the lifecycle engine), `src/npc_engine/api/dependencies_engines/quest.py`,
`src/npc_engine/config.py`, new test `tests/unit/engines/test_quest_trigger_shared_budget.py`
Spec: three trigger entry points each drive `quest_generation`, which retries up to 3 times, and
nothing caps the total across them. Worst case in one tick: event triggers 10 invocations x up to 4
calls, plus need triggers 10 x up to 4 — 80 calls, and two lenses independently derived about 84
for a saturated tick. Costed at measured decode rates that is 84-220 seconds of model time in a
single tick, against one resident model.
Fix: add a shared per-tick LLM call budget the three triggers draw from, injected via the
constructor (constructor injection only, per CLAUDE.md). When the budget is exhausted a trigger
falls through to its existing deterministic path rather than raising. Cap total trigger invocations
per tick with a named constant, not a literal. Do **not** attack the retry counts as the primary
fix — amplification is the product of invocations and retries, and invocations are the larger term.
Sequencing: T7.1 step 1 must already be in, or you will fix the same amplification twice. Note
T5.2 revived `need_quest_trigger`, so this is now load-bearing rather than theoretical.
Out of scope, do not do it here: deleting the slot-fill LLM call in favour of the existing
`_deterministic_fill` is a quality trade-off that cannot be measured until the eval layer is
repaired. It is logged for Sprint 9.
RED anchor: the new test constructs a tick where all three triggers fire with maximum candidates,
counts calls through a mock adapter, and asserts the total is at or below the shared cap. It should
count 40+ and fail today.
Validation: `pytest tests/unit/engines/test_quest_trigger_shared_budget.py -v`, then `make check`.
Done when: the test passes and `make check` is green. Finding L11-03, **SEV-03**. ✅ AUTO (T7.2, 2026-09-18)

- [x] **T7.3** Stop the gossip tick reconciling the whole corpus per propagated pair
Files: `src/npc_engine/graph/gossip/` (the propagation query path),
`src/npc_engine/engines/gossip/`, new test `tests/unit/graph/test_gossip_tick_query_count.py`
Spec: **SEV-07, whose fix brief is already written at `project-harness/review-fixes/FIX-SEV-07.md`
— read it first rather than re-deriving.** This finding was dropped in translation when this
roadmap was written and appeared nowhere in it until 2026-09-09.
Measured: the gossip tick costs **24,252 ms** against **433-570 ms** for every neighbouring tick —
40 to 55 times its neighbours — with **zero LLM calls**. It is pure graph work, which makes it the
cheapest large latency win in the programme and the one least entangled with the model. The cause is
a full corpus reconciliation performed per propagated pair rather than once per tick.
This matters more after Sprint 3, not less: T5.1 and T5.2 make co-location real, which increases the
number of propagated pairs, which multiplies exactly the term that is already dominating. And it
matters for T6.1's measurement — the 433-570 ms deterministic floor that task compares against is
the *neighbouring* ticks, not this one.
Rule 8 applies directly: this is deterministic work being done badly, not a model problem.
RED anchor: the new test counts graph round-trips (or reconciliation invocations) for a tick
propagating N pairs and asserts the count does not scale with N. It fails today — the count is
linear in pairs.
Validation: `pytest tests/unit/graph/test_gossip_tick_query_count.py -v`, then `make check`.
Done when: the test passes and `make check` is green. **Do not attempt the live timing here** — the
before/after tick duration needs a running stack built from each tree, and that is T7.4 alone (split
2026-09-17). SEV-07, brief at `review-fixes/FIX-SEV-07.md`. ✅ AUTO (T7.3, 2026-09-18)

- [x] **T7.5** Load the embedding encoder at boot — the "slow gossip tick" is a one-time cold load
Files: `src/npc_engine/retrieval/embedding/sentence_encoder.py` (a warm-up function beside
`get_encoder`), `src/npc_engine/main.py` (call it in `lifespan`, after `warm_up_llm`),
`src/npc_engine/config.py` (new `EMBEDDING_WARMUP_ON_STARTUP: bool = True`, mirroring
`LLM_WARMUP_ON_STARTUP`), new test `tests/unit/api/test_main_encoder_warmup.py`
Spec: ISSUE-356 and SEV-07 blame gossip logic; the measurement says otherwise. Measured 2026-09-18 on
the isolated stack, replaying the demo's opening (epoch=war, +1 tick, then advance to each gossip
boundary), per-engine `last_duration_ms` from `GET /v1/admin/system/engines`:
`57fe6bf4` (237-node seed): first gossip tick after boot **23,471 ms**, second **1,131 ms**;
`3019b51e` (301-node seed): first **19,221 ms**, second **1,449 ms**.
The app log of the cold tick shows where the ~21 s goes: the first pair finishes at +0.7 s; then
`get_encoder` runs for the first time in the process — `from sentence_transformers import ...` plus
`import torch` (11.3 s, ending at the `Loading embedding model all-MiniLM-L6-v2 on cpu` line), then
building the model (10.0 s, ending at the first `vector_store.incremental_upsert`). The other ~9 pairs
finish within 1.2 s. `get_encoder` is `lru_cache`d and never called at startup; `lifespan` warms the
LLM (`warm_up_llm`) but not the encoder. So whichever request first needs an embedding pays ~21 s —
the first gossip tick if nothing embedded earlier; a dialogue turn otherwise (this is why the live
demo, which talks before its ACT 7 gossip tick, passed with this code). SEV-07's 24,252 ms was taken
on "the tick landing on GOSSIP_TICK_INTERVAL=10", i.e. the first gossip tick — consistent with a cold
load, though whether that stack was freshly booted is not recorded.
Owner decision 2026-09-18: warm the encoder **at boot**, behind the new setting, accepting a slower
boot. Layer note: `setup/` is rank 1 and cannot import `retrieval/` (rank 3), so the warm-up is a
`retrieval/embedding` function called from `main.py` (api, rank 6), run via `asyncio.to_thread` like
every other encoder call in `embedding_index.py`. A warm-up failure logs a warning and boot continues
degraded (the lazy path still works) — it must not crash boot.
RED anchor: the new test drives `lifespan` with `get_encoder` patched (no model load, no I/O) and
asserts it is called once with `settings.EMBEDDING_MODEL` when the setting is true, not at all when
false, and that an exception from it does not propagate. It fails today — `lifespan` never calls it.
Validation: `pytest tests/unit/api/test_main_encoder_warmup.py -v`, `make check`; then live —
`bash scripts/eval_stack_at.sh HEAD --reset` (rebuild; the image is not bind-mounted), note the boot
time, `make eval-stack-seed`, replay the protocol above and read the first and second gossip ticks.
Do NOT run the integration suite for this: it writes to the live Neo4j (ISSUE-277).
Done when: the unit test passes, `make check` is green, `eval_stack_at.sh` still reports
`EVAL_STACK_SHA` (so the compose healthcheck window — `start_period: 30s`, 5 × 15 s — still covers
the slower boot), and on the live stack the **first** gossip tick after boot is within 2× the second.
Record boot time and both gossip ticks in the tick note. ISSUE-356, SEV-07. ✅ AUTO (T7.5, 2026-09-18)

- [x] **T7.4** Measure the gossip tick before and after T7.3 on a running stack
Files: `project-harness/ROADMAP.md` (tick note), `project-harness/ISSUES.md` (only if the tick did not improve)
Spec: the live tail of T7.3, split out so the loop can land the query fix unattended. T7.3's unit test
proves the round-trip count no longer scales with propagated pairs; it does not prove the tick got
faster, and the 24,252 ms figure (40-55x its 433-570 ms neighbours) is the number SEV-07 was raised
on. Measure it.
Build the isolated stack twice against the **same seeded world**: once from T7.3's parent commit
(`bash scripts/eval_stack_at.sh <parent-sha> --reset`), once from T7.3's commit. Each time `make eval-stack-up` — **rebuild,
the app image is not bind-mounted** — then `make eval-stack-seed`, advance ticks one at a time, and
read the per-engine tick durations. Report the gossip tick alongside its neighbouring ticks for both
trees. Sprint 3 raised co-location, so the "before" may exceed the historical 24,252 ms; compare
before and after on the same seed, not against the historical figure alone.
Do NOT run the integration suite for this: it writes to the live Neo4j (ISSUE-277).
RED anchor: the "before" measurement — the gossip tick is an outlier against its neighbours on the
pre-T7.3 tree. If it is not an outlier there, say so: the baseline has moved and the comparison
means nothing.
Validation: both measurements on the isolated stack, then rebuild it from HEAD and leave it running.
Done when: the tick note states the gossip tick duration before and after, each alongside its
neighbours, on the same seed. If the after figure is still an outlier, do not tick — log it in
`ISSUES.md` against SEV-07. SEV-07.
📊 Measured 2026-09-18 (301-node seed, GOSSIP_TICK_INTERVAL=10, same world both trees):
before (68735025): gossip 22,484 ms — neighbours goal_formation 436 ms, chapter 135 ms, need_decay 109 ms, faction_politics 100 ms, routine 73 ms (>50×);
after (c190952d): gossip 19,797 ms — neighbours goal_formation 425 ms, chapter 90 ms, faction_politics 104 ms, need_decay 109 ms, routine 77 ms (>46×).
T7.3 reduced the gossip tick by ~12% (embedding-reconcile O(N)→O(1)). Gossip is still a severe outlier. Logged as ISSUE-356; task not ticked.
**Amended 2026-09-18 (owner):** both figures above are the *first* gossip tick after boot, which
includes the one-time ~21 s encoder load (see T7.5) — they measure the cold start, not the tick. Re-run
the protocol after T7.5 and report the **first and second** gossip tick after boot for each tree; the
outlier test in "Done when" uses the second (warm) tick. Reference from 2026-09-18, same protocol:
warm gossip 1,131 ms at `57fe6bf4` (slowest neighbour: event 231 ms), 1,449 ms at `3019b51e`
(slowest neighbour: goal_formation 475 ms).
📊 Re-measured 2026-09-18 after T7.5 (301-node seed, GOSSIP_TICK_INTERVAL=10, same world both trees):
before (68735025): first gossip tick (cold) 29,139 ms — 2.6× slowest neighbour (need_quest 11,180 ms); second gossip tick (warm) 2,568 ms — 0.3× slowest neighbour (need_quest 8,461 ms);
after (c190952d): first gossip tick (cold) 25,920 ms — 2.4× slowest neighbour (need_quest 10,674 ms); second gossip tick (warm) 1,322 ms — 0.1× slowest neighbour (need_quest 8,865 ms).
T7.3 reduced warm gossip by 48% (2,568 ms → 1,322 ms). Warm gossip is not an outlier vs its neighbours — gossip (1,322 ms) is faster than need_quest (8,865 ms). Cold gossip (~26-29 s) is dominated by encoder load (fixed by T7.5 at boot). ISSUE-356 resolved; task ticked. ✅ AUTO (T7.4, 2026-09-18)

### Phase T8

Arbitrate what remains.

- [x] **T8.1** Add two-class admission control in front of the single resident model
Pre-approved: public-interface · owner 2026-09-17
Files: `src/npc_engine/engines/llm/` (adapter and factory),
`src/npc_engine/engines/llm/llm_metrics.py`, `src/npc_engine/config.py`, new test
`tests/unit/llm/test_admission_control.py`
Spec: nothing arbitrates the one resident model.
`grep -rn "Semaphore\|asyncio.Lock\|queue" src/npc_engine/engines/llm/*.py` returns **no matches**
across `ollama_adapter.py`, `factory.py`, `protocols.py`, `openai_adapter.py`, `ollama_payload.py`.
Nothing distinguishes an interactive call from a background one.
`memory_consolidation_engine.py:214` fans out up to `MAX_CONCURRENT_TICKS` (20 on the eval stack)
simultaneous generations. `LLM_TIMEOUT_SECONDS=60`, and dialogue degrades
`full -> graph_only -> canned` on timeout — so a player's turn arriving mid-tick either lands tens
of seconds late or silently downgrades, with no attributable cause in any log.
Fix: a two-class gate in the LLM layer — a semaphore with a slot reserved for the interactive
class, or a small priority queue. Classify from the existing DEC-273 `engine` metric label, which
already carries the distinction, so classification costs nothing: `dialogue` and player-facing
proactive are interactive; everything tick-originated is background. **Interactive pre-empts.**
**Shed, do not queue** — while an interactive call is active or pending, tick-originated calls are
rejected and fall through to their fallback path; queueing only moves the latency. Add
`llm_backend_queue_wait_seconds` next to the existing latency metric. Keep the gate in the LLM
layer, not in each engine — one arbitration point, per SRP.
RED anchor: the new test asserts that with N background calls in flight an interactive call
acquires within a bounded wait (assert on a fake clock, never wall time), that with an interactive
call active a background call is **shed** rather than queued, and that the new metric is observed
for both classes. All fail today.
Validation: `pytest tests/unit/llm/ -v`, then `make check`.
Done when: tests pass and `make check` is green. Finding L13-06, SEV-04.
Note (owner, 2026-09-18, ISSUE-358): out of scope here, but if a hard per-minute cap on background calls
is ever wanted, it belongs in this gate, which sees every backend call, not in the scheduler. ✅ AUTO (T8.1, 2026-09-18)

- [x] **T8.2** Wire the per-engine timeouts that four of five engines declare and nobody reads
Pre-approved: public-interface · owner 2026-09-08
Files: `src/npc_engine/engines/llm/factory.py`, `src/npc_engine/engines/llm_config_models.py`,
`src/npc_engine/engines/*/llm_config.yaml`,
`src/npc_engine/engines/dialogue/dialogue_handler.py`, new test
`tests/unit/llm/test_per_engine_timeout_wiring.py`
Spec: `grep -rn "timeouts_ms" src/npc_engine --include="*.py"` returns exactly two non-model rows —
the Pydantic field at `llm_config_models.py:96` and its only reader at `dialogue_handler.py:248-249`.
Meanwhile `chapter/llm_config.yaml:18` (30000), `memory_consolidation/llm_config.yaml:18` (30000),
`proactive_dialogue/llm_config.yaml:18-19` (20000) and `quest_generation/llm_config.yaml:18-19`
(30000) all declare a timeout no code path reads. (Each `timeouts_ms:` key sits at `:17`, its
`full:` value at `:18`; an earlier draft cited `:16` for all four.) The real ceiling for all five engines is one
process-wide `settings.LLM_TIMEOUT_SECONDS` (default 10.0, `config.py:111`) passed uniformly to
every adapter at `factory.py:88,103`. Worse, dialogue's declared 200000ms tier timeout
(`degradation.py:124`, genuinely enforced via `asyncio.wait_for`) sits *behind* that same 10s HTTP
ceiling, so it is asserted and unreachable.
Take option (a): thread `EngineModelConfig.timeouts_ms.full` into `create_llm_client_for_engine` as
the per-adapter timeout, demoting `settings.LLM_TIMEOUT_SECONDS` to a fallback for engines that
declare nothing. Option (a) is chosen over deleting the field because T8.1's admission control wants
per-class ceilings — a background engine that may wait 30s and an interactive turn that must not is
exactly the distinction this field was reaching for. Reconcile dialogue's tier ceiling so it is not
greater than the transport ceiling.
Sequencing: after T8.1 — longer background timeouts are only safe once background work can be shed.
RED anchor: the new test asserts an engine declaring `timeouts_ms.full: 30000` produces an adapter
whose effective timeout is 30s, not 10s; and that no `llm_config.yaml` declares a field no code
reads. Both fail today.
Validation: `pytest tests/unit/llm/ tests/unit/engines/ -v`, then `make check`.
Done when: tests pass, `make check` green. Related to ISSUE-298 (the temperature version of the
same defect). Finding L11-02, SEV-10. ✅ AUTO (T8.2, 2026-09-18)

---

# SPRINT 5 — Collapse the abstraction nobody uses

**Self-contained goal:** the ports layer matches the repo's own written rule. Roughly 30 protocol
files and their mirroring repositories leave the tree, and two gates make the rule permanent.

### Phase T9

The collapse. Do it after the deletions — Sprints 2 and 3 already removed about a dozen ports, so
the surface here is smaller than the review's original 44.

**T9.1 is four tasks, not one.** The collapse is 70-100 file touches and its original text said
"work in batches of about five ports per commit" — against a loop that runs one task per session and
produces exactly one commit, with a 90-minute timeout. Five `make check` runs alone is ~60 minutes
of that budget. A timed-out session is killed and its partial work stashed
(`expand_loop.sh:592-594`), and a half-collapsed ports layer still compiles, making it the least
detectable partial completion in the programme. So the census is its own task and each batch is its
own task; the shared method below belongs to all four.

- [x] **T9.1a** Recount the ports layer and record the collapse plan
Files: new `project-harness/ports_census.md` (temporary — delete at end of Sprint 5)
Spec: **no deletions in this task.** Run the count described in the shared method below over the
ports surviving Sprints 1-3, and write one table: port, implementor count, caller count, verdict
keep/collapse, consuming engine, wiring site, and the tests that mock it. This artifact is what
turns each later "batch" into a task with a fixed, reviewable scope — which is the whole reason the
original single task could not fit a session.
Mark the file temporary at the top per CLAUDE.md's temporary-file rule and log it in `ISSUES.md`
with a deletion deadline of the end of Sprint 5.
RED anchor: none — this is a measurement task, like T13.1. Its output gates T9.1b-d, which must not
start without it.
Validation: the table covers every file in `src/npc_engine/engines/ports/` with no row left
unverdicted, and the keep/collapse counts are stated.
Done when: the table is complete, every row has a verdict, and the total collapse count is recorded
so T10.1's gate has a number to drive to zero. ✅ AUTO (T9.1a, 2026-09-18)

- [x] **T9.1b** Collapse the ports in rows 1-8 of the census
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-275
Files: the port files, consuming engines, `src/npc_engine/engines/ports/__init__.py`,
`src/npc_engine/api/dependencies*.py` and the tests named in rows 1-8 of `ports_census.md`
Spec: apply the shared method below to the first eight rows only. One commit, own `make check`, own
LOC delta. Do not read ahead into other rows — the split exists so a regression is bisectable.
RED anchor: the census's recorded below-threshold count for these eight rows, driven to zero.
Validation: `make check`, then `make test-demo`.
Done when: rows 1-8 are collapsed, `make check` green, LOC delta reported. ✅ AUTO (T9.1b, 2026-09-18)

- [x] **T9.1c** Collapse the ports in rows 9-16 of the census
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-275
Files: as T9.1b, for rows 9-16 of `ports_census.md`
Spec, RED anchor, Validation and Done when: as T9.1b, for its own row range. ✅ AUTO (T9.1c, 2026-09-18)

- [x] **T9.1d** Collapse the remaining census rows
Pre-approved: file-deletion, public-interface · owner 2026-09-08 · DEC-275
Files: as T9.1b, for the remaining rows of `ports_census.md`; also
`tests/unit/engines/test_emotion_updater.py`
Spec: as T9.1b for the remaining rows, **plus** the `TraitReadPort` deletion described in the shared
method — it lands here because it is the one row that also removes a model class. Note
`tests/unit/engines/test_emotion_updater.py:116,117,136` are the only sites injecting `trait_reader`
and must be updated with it; no production site constructs `TraitModulatedEmotionModel`, which is
what makes the deletion safe.
RED anchor: as T9.1b. Additionally `grep -rn "TraitReadPort\|TraitModulatedEmotionModel" src/ tests/`
goes to zero.
Done when: **every** remaining protocol meets the threshold, the census has no unresolved row,
`ports_census.md` is deleted, `make check` green, LOC delta reported.

**Shared method for T9.1a-d.** CLAUDE.md's rule is "abstract behind a protocol at 2+ implementors **or** 3+ callers; below
that, inject the concrete class." At review time 34 of 44 protocols failed it — most had exactly
one implementor and one or two callers, sustaining polymorphism never exercised anywhere.
The owner chose 2026-09-08: collapse to the simplest shape that still respects SOLID. Concrete
constructor injection **is** SOLID-respecting here; the repo's own rule says so, and a concrete
class injected through a constructor is exactly as testable and mockable as a Protocol.
Method — do this mechanically, not by judgement: (1) for each remaining file in `engines/ports/`,
count implementors (concrete classes in `graph/repositories/` satisfying it) and callers (distinct
non-port, non-wiring files using it as a parameter annotation); (2) if implementors >= 2 **or**
callers >= 3, **keep** the protocol; (3) otherwise delete the protocol file and change the
consuming engine's constructor annotation to the concrete repository class. Do not delete the
repository — it is the implementation and it stays.
Known keepers by the review's count, subject to recounting after Sprints 2-3:
`ClockPort` (14 callers), `RelationReadPort` (6), `PlayerLocationReadPort` (5),
`WorldStateGraphPort` (5), `InteractionGraphPort` (3), `IntentGraphPort` (3), `GossipGraphPort` (3),
`PlanningGraphPort` (3), `SchemingGraphPort` (3). Recount rather than trusting this list.
Also in scope: `TraitReadPort` has **zero** implementors — `engines/ports/trait_read_port.py:9`
claims one "in the graph.repositories layer (slice 2 wiring)" and none exists. Delete the port, the
`trait_reader` parameter at `engines/emotion/emotion_updater.py:56,76,152-155`, the `_get_model_for`
branch, and the unreachable `TraitModulatedEmotionModel`. DEC-137 deferred this in June and it never
landed; log the deferred feature as an issue rather than leaving dead code. This row belongs to
**T9.1d**.
Counting note for T9.1a: `scripts/check_dip_threshold.py` is built in **T10.1**, one phase later, so
do not treat it as a prerequisite — write a throwaway counting script for the census and let T10.1's
gate confirm the result afterwards. Do not block on a tool that does not exist yet.
Findings L2-01, L2-02, L2-03, L7-05, DEC-275, rule 4. ✅ AUTO (T9.1d, 2026-09-18)

- [x] **T9.2** Fix the two god-ports and the ports that leak graph-owned types
Pre-approved: public-interface · owner 2026-09-08 · DEC-275
Files: `src/npc_engine/engines/ports/chapter_port.py`,
`src/npc_engine/engines/ports/quest_generation_port.py`,
`src/npc_engine/engines/ports/event_port.py`,
`src/npc_engine/engines/ports/relation_read_port.py`,
`src/npc_engine/engines/ports/scheming_port.py`, `src/npc_engine/engines/ports/quest_port.py`
Spec: three residual shapes T9.1 does not cover.
(1) **God-ports.** `chapter_port.py:21-70` — `ChapterGraphPort`, 9 methods, 1 implementor,
1 caller; `quest_generation_port.py:17-76` — `QuestGenerationGraphPort`, 11 methods, 1 implementor,
2 callers. Both fall below the threshold, so T9.1 already deletes them; this task exists to confirm
that and to catch them if a recount kept either. If one survives the recount, split it by consumer
role rather than keeping one wide interface.
(2) **Leaked private types.** `event_port.py:19-20` imports `RoutineOverridePlan` and `_EventNode`
from two different modules, not one: `RoutineOverridePlan` comes from
`graph/event/event_emission_service.py` (`:19`) and only `_EventNode` from
`graph/event/event_writer.py` (`:20`), where `_EventNode` is declared at `:20` as
`class _EventNode(Protocol)` — the underscore is that module's own signal it is private — and uses
it as a parameter type at `event_port.py:33`. The port's own docstring at `:6-7` says engines use it
"instead of importing graph writers." Same shape in `relation_read_port.py:21` (`RelationPhaseRow`)
and `scheming_port.py:22` (`ActiveSchemeProgress`, `SchemeRecord`). The layer direction is legal so
`check-layers` correctly ignores it; the defect is ownership. For any of these ports that survives
T9.1, move the DTO into the port module or a shared `engines/ports/_dtos.py` and have the graph
writer conform to it.
(3) **Redeclared methods.** `quest_port.py:21-124` — **four** sibling protocols (at `:21`, `:52`,
`:75` and `:110`) with redeclared methods: `get_quest_state` appears at `:24` and `:78`, and
`update_quest_node_status` at `:43` and `:59`, all satisfied by one implementor,
with structural typing letting the copies drift silently. Extract a shared base protocol or, if the
siblings collapse under T9.1, this resolves itself.
RED anchor: `grep -n "from npc_engine.graph" src/npc_engine/engines/ports/*.py` — record the hit
count, drive it to zero for private (underscore-prefixed) types, keep `make check` green.
Validation: `make check`, then `make test-demo`.
Done when: no surviving port imports a private graph type, no god-port remains, LOC delta reported.
Findings L2-03, L2-04, L2-05. ✅ AUTO (T9.2, 2026-09-18)

### Phase T10

Make the rules mechanical so none of this regrows.

- [x] **T10.1** Gate the DIP threshold — abstraction requires two
Files: new `scripts/check_dip_threshold.py`, `Makefile`, `scripts/loop_gates.py`, new
`tests/unit/scripts/test_check_dip_threshold.py`
Spec: rule 4. The script walks `src/npc_engine/engines/ports/`, and for each Protocol class counts
implementors (concrete classes structurally satisfying it) and callers (distinct non-port,
non-wiring files using it as a parameter annotation). A protocol with fewer than 2 implementors
**and** fewer than 3 callers fails the gate. Exclude the `engines/ports/__init__.py` re-export from
the caller count, and exclude files that merely mention the name in a docstring — the review found
`api/dependencies_advanced/progression.py:38,54,100` are prose, not imports, and counting them would
make the gate lie.
Provide a documented waiver file, `scripts/dip_waivers.txt`, for protocols kept deliberately, each
line requiring a `DEC-NNN` reference. An empty waiver file is the target state and the gate should
report how many waivers are in use so the number is visible.
Wire into `make check`, and register it in `scripts/loop_gates.py` (see `Done when:`).
RED anchor: **do not use `git worktree` or `git stash`** — see T4.2 for why. Extract the pre-Sprint-5
tree read-only with `git archive <sha> | tar -x -C <tmpdir>` and point the script at it with the same
`--root` flag T4.2 establishes. It must report the ports T9.1a-d deleted against that tree and zero
against the current one. If it reports zero on both, the counting is wrong and the gate asserts
nothing.
Validation: `python scripts/check_dip_threshold.py`, then `make check`.
Done when: the gate is in `make check`, green here, demonstrably red before T9.1b, **and registered
in `scripts/loop_gates.py`** — appended to `AUTOFIX_CHECK_SPECS`, with `check_dip_threshold.py`
**and `scripts/dip_waivers.txt`** appended to `FROZEN_PATH_PREFIXES`. Freezing the waiver file is not
optional: it is the designed escape hatch, and an unattended repair session that can append a
`DEC-NNN` line to it turns the gate green having fixed nothing — the same laundering
`scan_fix_diff.py:9-14` describes for `rules_baseline.txt`. Append the entries in the same commit as
the gate (see T4.2). Rule 4. ✅ AUTO (T10.1, 2026-09-19)

- [x] **T10.2a** Gate dead surface, and delete what it finds
Pre-approved: file-deletion, public-interface · owner 2026-09-08
Files: new `scripts/check_dead_surface.py`, new `tests/unit/scripts/test_check_dead_surface.py`,
`Makefile`, `scripts/loop_gates.py`, `src/npc_engine/config.py`, delete two prompt YAMLs,
`src/npc_engine/engines/quest_generation/llm_config.yaml`
Spec: rule 3. T10.2 was split three ways 2026-09-17 — two gates, eleven deletions and a CLAUDE.md
rewrite do not fit one session. The gate (`check_dead_surface.py`) reports every `Settings` field
with no reader outside `config.py` and its own tests; every prompt YAML under
`src/npc_engine/prompts/` and `prompts/eval/` that no code loads; every `engines/contracts/*.yaml`
with no matching engine; and every module under `src/npc_engine/graph/` with no importer outside its
own package — Sprint 2 deleted the engines that were several of these modules' only readers, and
without that scope the gate cannot see the class of orphan T1.2 had to delete by hand.
Known findings to clear — verify each is still true before deleting, then delete: the 9 reader-less
`Settings` fields `CONSOLIDATION_CLEAR_TURNS`, `EMBEDDING_REFRESH_ON_WRITE`,
`GOSSIP_DISTORTION_MAX`, `GOSSIP_PERSONALITY_FIELDS_ENABLED`, `GOSSIP_RNG_SEED`, `LLAMA_API_URL`,
`LLM_CACHE_ENABLED`, `MISTRAL_API_URL`, `QDRANT_URL`; and the 2 dead prompts
`prompts/quest_generation/slot_fill_v1.yaml` and `prompts/quest_generation/flavor_v1.yaml`, both
superseded by hardcoded v2 loads — also correct the engine's `llm_config.yaml`, which still names
the dead `v1`. `escort_npc.yaml` and `fetch_item.yaml` are loaded via glob and are **not** dead
despite zero literal-name hits; the script must not flag them, which is the main correctness test
for the glob handling. Any `graph/` orphan the report finds beyond these: delete it if nothing
reaches it, otherwise log an issue — do not widen this task into a second Sprint 2.
RED anchor: `check_dead_surface.py` reports the 9 settings and 2 prompts **before** you delete them;
that report going to zero is the anchor.
Validation: `python scripts/check_dead_surface.py`, then `make check`.
Done when: the gate is in `make check` and green, the 11 dead items are deleted, and the gate is
registered in `scripts/loop_gates.py` — appended to `AUTOFIX_CHECK_SPECS`, with the script appended
to `FROZEN_PATH_PREFIXES`, in the same commit (see T4.2). Findings L10 dead-surface sweep, L12-15,
ISSUE-332, rule 3. ✅ AUTO (T10.2a, 2026-09-19)

- [x] **T10.2b** Install the reverse LOC ratchet
Files: new `scripts/check_loc_ratchet.py`, new `scripts/loc_baseline.txt`, new
`tests/unit/scripts/test_check_loc_ratchet.py`, `Makefile`, `scripts/loop_gates.py`
Spec: rules 1 and 6. `check_loc_ratchet.py` counts non-test LOC across **`src/npc_engine/`,
`scripts/`, `evals/` and `demo_game/`** and compares the **total** to `scripts/loc_baseline.txt`,
which carries one line per directory plus the total. Fail if the total rose. Report all four numbers
on every run, so moving logic from `src/` into `scripts/` or `demo_game/` is visible rather than free
— a `src`-only count would leave 164,715 LOC, 70.4% of the repo, outside the gate. Raising the
baseline is a deliberate edit with a reason in the commit message.
**Seed the baseline with Sprints 6-8's additive work already budgeted, not from the bare tree.**
T12.1 adds a gate script, T15.1 adds `working_set_size` plus two gauges, and T16.2 adds histogram
buckets — all after this task. Seeding from the tree as it stands installs a ratchet before the last
additive work and guarantees a red those tasks cannot legally clear. State the budgeted allowance and
its reason in the baseline file itself.
While registering, freeze the gate surfaces that are unprotected today:
`scripts/check_test_quality.py`, `scripts/check_test_quality_baseline.txt`,
`scripts/evals_baseline.txt` and `scripts/engine_logs_baseline.txt`.
RED anchor: add a throwaway 50-line module, confirm the gate reds, delete it.
Validation: `python scripts/check_loc_ratchet.py`, then `make check`.
Done when: the gate is in `make check` and green, registered in `scripts/loop_gates.py` in the same
commit — appended to `AUTOFIX_CHECK_SPECS`, with the script, `scripts/loc_baseline.txt` and the four
surfaces above appended to `FROZEN_PATH_PREFIXES` — and the completion note records the combined wall
time of T10.1, T10.2a and T10.2b's gates; if it exceeds 60s, say so — the ratchet must not become the
reason the gate stops being run. Findings L10 dead-surface sweep, rules 1, 6. ✅ AUTO (T10.2b, 2026-09-19)

- [ ] **T10.2c** Write the nine programme rules into `project-harness/CLAUDE.md`
Files: `project-harness/CLAUDE.md`
Spec: add the nine rules from this roadmap's preamble to `project-harness/CLAUDE.md` under "The
strict rules", so the rules survive an unloaded skill — that file's own stated design principle.
**Name each rule's gate, and for rules 2, 7, 8 and 9 say explicitly that they have none and are
enforced by review.** The owner chose 2026-09-09 to copy all nine rather than only the gated four;
that choice is only safe if the ungated ones are labelled as such, or a reader will assume a green
`make check` covers them. Name gates as they exist on this tree — T10.1, T10.2a and T10.2b have
landed. While in the file, fold in ISSUE-307 (the layer diagram omits `observability/` and `setup/`)
if it is still true, and close it.
RED anchor: none of the nine rules appears under "The strict rules" today — check each by its key
phrase and record the zero; all nine present, each stating its gate or "no gate — enforced by
review", is the anchor.
Validation: `make check-harness`, then `make check`.
Done when: all nine rules are in `project-harness/CLAUDE.md` with their gate status, and ISSUE-307 is
closed or re-logged with the reason. Rules 1-9.

---

# SPRINT 6 — Prune the test suite

**Self-contained goal:** `tests/` stops being the largest area in the repo and starts protecting
something. Every surviving test can fail.

### Phase T11

Delete what cannot fail. Sprints 2-3 already removed the tests belonging to deleted engines, so
this sprint works on what remains.

- [ ] **T11.1a** Resolve the waived NO_ASSERTION findings
Pre-approved: file-deletion · owner 2026-09-08
Files: the `tests/` files carrying these findings, `project-harness/ISSUES.md`
Spec: rule 5, part 1 of 3 — read the shared notes after T11.1c first. Re-run the test-quality
scanner with waivers **ignored** and take the **NO_ASSERTION** findings (21 measured 2026-09-08).
Read each test: if the behaviour it gestures at is load-bearing, give it a real behavioural
assertion; if not, delete it. Remove its `# quality-ok:` marker either way.
RED anchor: the waiver-ignored scan reports the NO_ASSERTION count (21 on 2026-09-08); that count
going to zero is the anchor. Record the `make test` pass count before and after — it must drop by
exactly the number of tests deleted.
Validation: `make test`, then `make check`.
Done when: zero NO_ASSERTION findings with waivers ignored, `make check` green, and the LOC and
coverage deltas reported.

- [ ] **T11.1b** Resolve the waived BARE_EXCEPTION_RAISES findings
Pre-approved: file-deletion · owner 2026-09-08
Files: the `tests/` files carrying these findings, `project-harness/ISSUES.md`
Spec: rule 5, part 2 of 3 — shared notes after T11.1c. Same method as T11.1a for the
**BARE_EXCEPTION_RAISES** findings (31 measured 2026-09-08): a `pytest.raises(Exception)` that would
pass on any error gets the specific typed exception from `utils/errors.py` the code raises, and a
`match=` where the message is the contract; delete the test only if nothing load-bearing is under it.
RED anchor: the waiver-ignored BARE_EXCEPTION_RAISES count going to zero; `make test` pass count
before and after, dropping by exactly the tests deleted.
Validation: `make test`, then `make check`.
Done when: zero BARE_EXCEPTION_RAISES findings with waivers ignored, `make check` green, LOC and
coverage deltas reported.

- [ ] **T11.1c** Resolve the vacuous-mock findings, delete existence-only and constant tests, close ISSUE-234
Pre-approved: file-deletion · owner 2026-09-08
Files: across `tests/`, `project-harness/ISSUES.md`, `project-harness/archive/ISSUES_RESOLVED.md`
Spec: rule 5, part 3 of 3 — shared notes below. (1) The **VACUOUS_MOCK_NOT_CALLED** findings (8
measured 2026-09-08), same method as T11.1a. (2) **Existence-only** tests: tests whose only assertions
are `hasattr(...)`, `inspect.iscoroutinefunction(...)`, or "this symbol imports". They prove a name
exists and survive any implementation change that keeps the signature. (3) **Constant-equals-literal**
tests: asserting a module constant equals the literal it is defined as. These restate the source and
go red only when someone edits the constant deliberately. For (2) and (3): replace with a behavioural
test if the code under it is load-bearing, otherwise delete.
Close ISSUE-234, correcting its count from 25 to 21.
RED anchor: record the test count and the `make test` pass count before and after — the pass count
must drop by exactly the number of tests deleted; a larger drop means something load-bearing went.
Validation: `make test`, then `make check`.
Done when: all three waived categories are empty **with waivers ignored** — not merely green against
the waiver-honouring gate — `grep -rn 'assert hasattr\|iscoroutinefunction' tests/` returns nothing
T12.1's detectors would flag, ISSUE-234 is corrected, closed and archived, and the LOC and coverage
deltas are reported.

**Shared notes for T11.1a-c** (split three ways 2026-09-17: 60 findings plus two categories did not
fit one session). Judge "load-bearing" by whether the code under a test is reachable from a route,
the scheduler, or the demo — the same standard as T4.2. Never delete on a grep alone; read each test.
**`make check-test-quality` reports 0 issues today — do not read that zero as the categories being
empty.** `check_test_quality.py:243` skips any finding whose line carries the `# quality-ok:` marker
(`_WAIVER_MARKER`, `:34`), and there are **66** such markers in `tests/`, several sharing one generic
reason. ISSUE-234's findings were *waived, not fixed*, and `check_test_quality_baseline.txt` already
contains `0`. Measured 2026-09-08 with waivers ignored: **60 findings — 21 NO_ASSERTION, 31
BARE_EXCEPTION_RAISES, 8 VACUOUS_MOCK_NOT_CALLED.** Start from `grep -rn "quality-ok" tests/`.
**T12.1 removes the `# quality-ok:` mechanism entirely** (owner decision, 2026-09-09), so every one of
those findings must be resolved in T11.1a-c — a waiver is not an option.
**Loop note — every failure these tasks can cause lands on a frozen path.** `tests/` is the first
entry in `loop_gates.FROZEN_PATH_PREFIXES`, so the loop's repair session cannot fix anything broken
here and a red pushes `CONSECUTIVE_RED_GATES` toward the night-ending halt at 2. **Leave the tree
green**: iterate with `make test` after each file, run `make check` at most twice at the end, and if a
form gate (`check-test-quality`, `check-rules`) reds, fix it in the same session.
**Coverage is invisible to the loop's attribution, so measure it by hand.**
`loop_gates.HALT_CHECK_SPECS` runs pytest without `--cov-fail-under`, so a coverage-floor breach
produces zero failing node ids and would be ticked. Record `make test-cov | tail -3` before and after
and put both numbers in the completion note. **If coverage falls below 80, stop and do not tick** —
the floor move is T12.2's job. (Calibration: headroom is 1,486 statements at 88.13%.)
Findings L4-06, ISSUE-234, ISSUE-310, rule 5.

- [ ] **T11.2** Strengthen the mock-echo delegate tests, and list what nothing covers
Pre-approved: file-deletion · owner 2026-09-08
Files: `tests/unit/graph/`, `project-harness/ISSUES.md`
Spec: 127 delegate tests only prove a mock echoed itself. The review ran the counterfactual:
gutting 105 repository passthrough methods produced only 66 failures, so 39 methods are covered by
nothing that can fail. The wrapped Cypher is exercised only by `tests/integration/`, which skips 34
of 43 in the default environment — so `make check` executes **zero real Cypher**. The
representative shape is `tests/unit/graph/test_story_pacing_repository.py:31-41`.
Split 2026-09-17: this task is the unit side; T11.3 adds and runs the integration tests. Do not simply
delete all 127 — that would remove the only mention of those methods. Instead: (1) delete the
delegate test where an integration test already covers the same method against real Cypher; (2) keep
and strengthen it where no integration coverage exists, by asserting on the *result shape* the caller
depends on rather than that the mock was called; (3) list every method with neither in a new
`ISSUES.md` entry that T11.3 consumes. Do not run `tests/integration` in this task.
RED anchor: gut five repository methods whose delegate tests you strengthened; `make test` must go
red for all five. Restore them.
Validation: `make test`, then `make check`.
Done when: the five-method counterfactual is observed red, the uncovered-method list is logged, LOC
delta reported, **and the coverage delta reported — if it drops more than 3pp, stop: you deleted
more than delegate tests.** Measure coverage by hand, as in T11.1's shared notes.
Findings L4-05, CR-L14-02, ISSUE-309.

- [ ] **T11.3** Add integration tests for the uncovered repository methods, on the eval stack's Neo4j
Files: `tests/integration/`, `project-harness/ISSUES.md`, `project-harness/DECISIONS.md`
Spec: the integration half of T11.2. For each method in the uncovered list T11.2 logged, add an
integration test against real Cypher. Run them **only** against the eval stack's disposable Neo4j —
`bash scripts/eval_stack_at.sh HEAD --reset`, then export `NEO4J_URI=bolt://localhost:7688` with
`NEO4J_USER`/`NEO4J_PASSWORD` from `.env` — **never the default URI**: the default Neo4j is the
developer's live database and there is no separate test database (ISSUE-277). The suite carries 8
known failures (ISSUE-236), so judge it with `make check-integration-baseline` under the same
exports, not by a raw pass count. Record in `DECISIONS.md` that integration runs use the eval stack's
Neo4j, and close T11.2's uncovered-method issue.
Sequencing: T12.2 records whether the CI `integration-tests` job gates merge (owner, 2026-09-17: it
will); if it did not, this task's value would drop sharply.
RED anchor: re-run the counterfactual on a sample across unit **and** integration — gut five
repository methods from the uncovered list, confirm the combined run goes red for all five. Before
this task it goes red for about three of five.
Validation: the integration run above, `make check-integration-baseline` with the exports, then
`make check`.
Done when: every listed method has an integration test that ran against the eval Neo4j, the sample
counterfactual catches all five, the `DECISIONS.md` note is written, and the issue is closed.
Findings L4-05, CR-L14-02, ISSUE-309.

### Phase T12

Make it stick, and close the two test gaps the review called out by name.

- [ ] **T12.1** Gate that a test can fail, and test the auth wiring that nothing tests
Files: new `scripts/check_test_quality_can_fail.py` or an extension of the existing
`scripts/check_test_quality.py`, `Makefile`, `scripts/loop_gates.py`,
`tests/unit/scripts/test_check_test_quality.py`, new `scripts/check_test_quality_demo_baseline.txt`,
new `tests/unit/api/test_create_app_auth_wiring.py`
Spec: two things, both about the same gap.
(1) **The gate.** Extend the existing test-quality check to fail on the three categories T11.1a-c
deleted, so they cannot come back: no-assert test bodies, existence-only assertions, and
constant-equals-literal. Use an AST walk, not a regex — ISSUE-191 records that the existing
`check_rules.py` is a regex scanner that flags patterns inside comments and docstrings, and
repeating that mistake here would make the gate untrustworthy.
**Remove the `# quality-ok:` waiver mechanism entirely** (owner decision, 2026-09-09). Rule 5 says
"a test must be able to fail" with no waiver clause, while the gate honours a comment — and 66 of
them currently hide 60 findings, which is how ISSUE-234's 25 became invisible. Delete `_WAIVER_MARKER`
(`:34`) and the skip at `:243`, and delete every remaining `# quality-ok:` comment from `tests/`.
T11.1a-c resolves all 60 findings first, so by the time this task runs there should be nothing left
behind a waiver; if there is, that work belongs in T11.1a-c, not here.
**Keep `scripts/check_test_quality_baseline.txt` at `0`.** The check is a ratchet
(`:315-334`: `if count > baseline`). Your new detectors will surface 30+ findings on their first run
— `grep -rn "assert hasattr" tests/` is 26 across 7 files and `iscoroutinefunction` is 7 — so
without T11.1a-c clearing them first, the gate you write reds the gate you must pass to be ticked.
**Do not raise the baseline to get green**; the missing work belongs in T11.1a-c.
**Point the scanner at both test roots.** `_TESTS_ROOT` (`:35`) is hardcoded to `tests/`, so
`demo_game/tests/` — 87 files, 15,852 LOC, **1,097 test functions, 25.6% of the repo's tests** — is
entirely outside rule 5's gate, and `make check` never executes them either. Sprint 3 puts *both* of
its RED anchors there. Take a `--tests-dir` list instead of the single constant and record the
`demo_game/tests/` finding count separately. **Give `demo_game/tests/` its own baseline** (owner,
2026-09-17): nothing before this task clears `demo_game/tests/`, so a single `0` would red this task's
own gate. Seed `scripts/check_test_quality_demo_baseline.txt` at the count the new detectors report
on their first run, ratcheted like the main one (fails only when the count rises); `tests/` stays at
`0`. State the seeded number in the completion note and log an issue to drive it to zero.
(2) **The auth test.** Every current test that proves "auth is required" builds its **own**
`FastAPI()` app and attaches `ApiKeyMiddleware` by hand —
`tests/unit/api/test_dialogue_pending_route.py:45-56,110-119`. Nothing exercises the middleware
stack that `create_app()` actually assembles at `main.py:271-278`. If a future change reorders or
drops the middleware there, the whole suite stays green and the API ships unauthenticated.
Write a test that builds the app through **`create_app()`** and asserts, against the composed app:
`GET /health` reachable without credentials; a representative route from each router group returns
401 without credentials; a valid key succeeds; `/readiness`, `/docs` and the admin surface are
gated; and 401/403 carry no body. Drive the route list **mechanically from the app's own router
table**, not a hardcoded list, or you recreate the same gap one level up. Keep it a unit test — stub
whatever `create_app()` needs rather than starting services.
RED anchor: comment out the middleware registration in `main.py`, run the new test, confirm it goes
**red**, restore. That step is the entire point; a test that cannot fail proves nothing.
Validation: `pytest tests/unit/api/test_create_app_auth_wiring.py -v`, then `make check`.
Done when: the gate is in `make check` with the `tests/` baseline still at `0` and the
`demo_game/tests/` baseline seeded and logged, no `# quality-ok:` marker remains anywhere in `tests/`,
both test roots are scanned, the auth test passes, the comment-out
experiment was observed red, **and the gate is registered in `scripts/loop_gates.py`** — appended to
`AUTOFIX_CHECK_SPECS`, with its script and both baselines in `FROZEN_PATH_PREFIXES`. Note
`tests/unit/api/test_create_app_auth_wiring.py` is a **product** test and stays where it is; it must
not move into `tests/unit/scripts/`, which T0.3 routes to skip-and-log. Append the `loop_gates.py`
entries in the same commit as the gate (see T4.2). Findings L4-02, L4-06, SEV-11, rule 5.

- [ ] **T12.2** Cover the measurement tool, and re-baseline coverage after the prune
Files: new `tests/unit/evals/test_arm_probe*.py`, `Makefile`, `project-harness/DECISIONS.md`,
new `project-harness/BASELINE_2026-09.md`
Spec: three loose ends this sprint must close.
(1) **The unmeasured measurement tool.** `evals/arm_probe.py` and `evals/arm_probe_report.py` ship
at **0%** coverage and `evals/arm_probe_client.py` at 46%. This is the P9 measurement-integrity
tooling — the thing whose job is to establish that measurements are trustworthy — and the aggregate
`make test-cov-evals` floor of 75 passes at **82.79%** (re-measured 2026-09-08; an earlier draft said
79.76%) while these specific modules sit at zero. Test
`ProbeClient.observe/rehydrate/corpus_fingerprint` first (success, HTTP error, malformed payload,
timeout, transport mocked, no live services), then `_run`/`_live_gates` orchestration — especially
that a failing gate is *reported* as failing — then report rendering including empty and all-failed.
Consider a per-module floor so the aggregate cannot hide a zero again; if the harness has no
per-module mechanism, log an issue rather than building one here.
(2) **Record the CI gate decision.** The owner approved on 2026-09-17 making the `integration-tests`
job a **required** status check for merge on `main`. That is a GitHub branch-protection setting, not
a repo file, and the owner applies it by hand — do not edit `.github/` or try to change it through
the API. Record in `DECISIONS.md` that it is required by owner decision 2026-09-17: that answers
whether "no real Cypher in `make check`" is a local-only gap (it is), which T11.3 depends on.
(3) **Re-baseline.** `review-2026-08/BASELINE_2026-08-28.md` no longer matches the tree and is
deliberately immutable, so "no delta" can no longer be used as a check. Capture a fresh dated
baseline: `make check` timing, `make test` and `make test-demo` counts, coverage for both floors,
mypy count, and the LOC table from this roadmap's preamble. **Re-measure `make test-cov-evals` at
the moment you write the file — do not copy the figure from this roadmap**; that is how the last
baseline stopped meaning anything.
Then re-measure both floors and **lower a floor only if the measured value is within 2pp of it**.
Otherwise record the new numbers and leave the floors alone, stating in the completion note that the
prune did not move coverage materially. Measured 2026-09-08, the headroom is 1,486 statements at
88.13% against a floor of 80, and Sprint 2's deletions move the headline only 87.97% → 87.57%
because the deleted set was *better* covered than the mean — so the predicted outcome is that
neither floor needs to move. Lowering one anyway would be exactly the ceremony the next sentence
warns against. If a floor **is** lowered, say by how much and against which measured number — a
floor quietly lowered is how a gate stops meaning anything.
Close **ISSUE-321** here: it records that `BASELINE_2026-08-28.md` no longer matches the tree, which
the new baseline file supersedes.
RED anchor: for (1), per-module coverage for the three `arm_probe` modules, before and after. Report
both; do not quote the aggregate as if it were the point.
Validation: `pytest tests/unit/evals/ -v`, `make test-cov-evals`, `make check`.
Done when: the three modules are covered, the CI decision is recorded in `DECISIONS.md`, the new
baseline file exists, and ISSUE-321 is closed and archived.
Findings L4-01, L4-03, L9-09, ISSUE-321, SEV-14.

---

# SPRINT 7 — Trim the demo to what it actually shows

**Self-contained goal:** `demo_game/` contains only what the scripted demo and the interactive
walkthrough exercise, and it is type-gated like the rest of the repo.

### Phase T13

Cut first, using evidence rather than judgement.

- [ ] **T13.1** Census what the demo actually exercises ⏸️
Files: new `project-harness/demo_census.md` (working artifact, delete at end of Sprint 7)
Spec: this task produces evidence, not deletions — do not delete anything here. `demo_game/` is
36,937 LOC across 184 files, the second-largest area in the repo and larger than the whole engine
layer, and it is a demo, not a licensed product.
Run the scripted demo to completion against a running stack (possible only after T1.1) and the
interactive walkthrough in `docs/DEMO_SCRIPT.md`, and record which modules are actually imported and
executed. Use `coverage run` over the demo process rather than reading imports statically — a
statically-imported module that never executes is exactly what you are hunting.
Produce one table: module, executed in scripted run, executed in walkthrough, verdict keep/delete.
**Compute the census over `demo_game/` excluding `tests/`, and judge test files by a different
rule.** No test file is ever imported or executed by the demo *process* — tests run under pytest, a
separate process from the one you instrument with `coverage run` — so applying the coverage method
literally to `demo_game/tests/**` returns "not executed" for **every** test in the tree, all 87
files. That would sweep up `demo_game/tests/seeds/test_seed_schedules.py` and `test_seed_needs.py`,
which T5.1 and T5.2 were required to add four sprints earlier, alongside genuinely dead files like
`demo_game/tests/pollers/test_treaty_poller.py` — and nothing in the method distinguishes them.
So: census the non-test modules by coverage, then separately map each test file to the module(s) it
imports. **A test whose target module is kept is kept, regardless of its own coverage.**
Known context to fold in rather than re-derive: `demo_game/ui/layout/game_window.py` is 925 lines against a
documented 350-line waiver (CR-L07-03); the branch system is a single two-option stub
(`garrick_deserter`, finding L6-03); and `e2e/scenarios/scenario_territorial_war.py` cannot even be
imported (ISSUE-204) and targeted the `military` engine deleted in T1.2, so it goes regardless.
Mark this file temporary at the top per CLAUDE.md's temporary-file rule and log it in `ISSUES.md`
with a deletion deadline of the end of Sprint 7.
Also flag the TREATY and OATH tabs explicitly. After Sprint 2 those panels poll data nothing writes
any more (`demo_game/pollers/treaty_poller.py`, `demo_game/ui/panels/treaty_panel.py`, and the oath
controls in `game_window.py`), and `grep -in "treaty" docs/DEMO_SCRIPT.md demo_game/runners/run.py`
returns nothing — so they are not part of the scripted 12-act path and are known deletion
candidates. Confirm they reach a verdict rather than being silently skipped.
Rule on the FACTION tab the same way (ISSUE-359, added 2026-09-18): it's never fed, isn't in the scripted
path, and its data changes only by admin PUT or pledge break. If kept, feed it on tab open through
`RightPanelRenderer`, not a poller, and fix `FactionBoard` to read the inner `standings` rows.
RED anchor: none — this is a measurement task. Its output gates T13.2, which must not start without
it.
Validation: the census table exists and covers every module under `demo_game/`.
Done when: the table is complete, every row has a verdict, and test files are verdicted by their
target module rather than by their own coverage.

- [ ] **T13.2** Delete what the census marked dead ⏸️
Pre-approved: file-deletion · owner 2026-09-08
Files: `demo_game/`, `e2e/`, `project-harness/ISSUES.md`
Spec: delete every module the T13.1 census marked delete, plus `e2e/scenarios/` entries that target
deleted engines. Work in batches by subsystem — pollers, panels, branches, scenarios, runners — so a
break is bisectable, running `make test-demo` after each batch.
Two constraints. **Keep the interactive UI**: the MetaHuman walkthrough is how a buyer sees
persistent memory working, and the owner explicitly kept it on 2026-09-08 — the cut is unused
panels, pollers, branches, scenarios and helpers, not the demo itself. **Keep `world_objectives.py`
and `game_end_checker.py`**, which T1.2 deliberately left alone; with `military` gone the legion
lose path can no longer fire, but the win path and the other lose conditions still matter. While
here, confirm the win path is reachable in the seeded world and log an issue if it is not.
Also resolve ISSUE-311: `e2e/scenarios/scenario_memory_recall_e2e.py` has no `test_*` function and
is collected by nothing, despite ISSUE-107 being closed with the claim it was "wired into the e2e
battery". Either give it a collectable entry point in a suite that runs, or delete it and correct
the record — do not leave a third state.
RED anchor: `make test-demo` before and after — baseline 1,116 passed. The count must drop by
exactly the tests belonging to deleted modules; any other delta means something load-bearing went.
**That arithmetic alone is not sufficient** — it balances by construction if a test file is itself
one of the "deleted modules", which is exactly the failure T13.1's methodology note guards against.
So also assert **by name** that `demo_game/tests/seeds/test_seed_schedules.py` and
`demo_game/tests/seeds/test_seed_needs.py` still exist after the trim, along with every other test
whose target module survived. Those two are T5.1's and T5.2's RED anchors; losing them silently
un-verifies Sprint 3.
Then run the scripted demo end to end and confirm all 12 acts still complete — including Act 5,
which T1.2 re-sourced from the events engine.
Validation: `make test-demo`, `make check`, `make type-demo-update` (the deletions lower the
`demo_game/` mypy count; ratchet it down in the same commit), scripted demo to completion. Then pick up
the `game_window.py` split issue T14.2 logged, if the file is still over 800 lines.
Done when: the demo runs, the census's delete rows are gone, LOC delta reported.
Findings L6-03, ISSUE-204, ISSUE-311, CR-L07-03.

### Phase T14

Gate what survives.

- [ ] **T14.1** Bring `demo_game/` under mypy
Files: `Makefile`, `scripts/harness_status.py`, `scripts/check_harness_honesty.py`,
`project-harness/ISSUES.md` — **not** `demo_game/`
Spec: **`demo_game/` is ratcheted but not gated — the ratchet you would build already exists.**
`make type-demo` (`Makefile:226-237`) already drives `scripts/mypy_ratchet.py --target demo_game/
--baseline-file .mypy_baseline_demo`, with `make type-demo-update` to ratchet it down and
`scripts/harness_status.py:29` reporting it. `.mypy_baseline_demo` is **256**, and
`python -m mypy demo_game` reports 256 errors in 45 files across 184 checked — the baseline matches
reality exactly.
The only real gap is that **`type-demo` is absent from `make check`'s target list** (`Makefile:432`),
so nothing runs it. That is a one-word edit, not a session of building a ratchet. **Do not build a
second ratchet** — an earlier draft's instruction to "add a `.mypy_baseline`-style ratchet for
`demo_game` specifically" would add a duplicate mechanism to a programme whose purpose is removing
things.
So: add `type-demo` to `check:` at the current baseline, so the count can no longer grow.
**Do not fix any `demo_game/` type error in this task** (narrowed 2026-09-17). The loop reaches T14
while T13.1/T13.2 are still deferred, so the census has not run and nobody knows which modules
survive; fixing types in modules T13.2 is about to delete is wasted work. Driving the count down
belongs after T13.2 — log that as an issue in `ISSUES.md` naming T13.2 as its prerequisite, with the
count recorded here as its starting point. T13.2's own deletions lower the count, and it ratchets the
baseline down in the same commit (execution contract item 6).
Note `scripts/check_harness_honesty.py:27` reads `.mypy_baseline` only and has no view of
`.mypy_baseline_demo`, so a non-zero demo baseline is invisible to the gate whose job is "the docs
claim a clean state the gates contradict". Extend `harness_status.py`'s existing
`.mypy_baseline_demo` row into H1, or log an issue saying why not.
The issue's target date for reaching zero is not gated — the owner decided 2026-09-09 that it is a
promise rather than a mechanism, and the completion note should say so plainly.
`type-demo` needs `demo_game/requirements.txt` installed or mypy reports import errors and the count
will not reproduce (see the `Makefile` comment above the target); confirm the count matches
`.mypy_baseline_demo` before wiring it in, or the gate reds on its first run.
RED anchor: `grep '^check:' Makefile | grep -c type-demo` returns **0** today — the ratchet exists and
`make check` does not run it. That going to 1 is the anchor.
Validation: `make type-demo`, `python -m mypy demo_game`, then `make check`.
Done when: `type-demo` is in `make check`'s target list, no second ratchet was created, no file under
`demo_game/` was edited, the `.mypy_baseline_demo` count is recorded, and the drive-to-zero issue is
logged with T13.2 as its prerequisite. Baseline finding from
`review-2026-08/BASELINE_2026-08-28.md`.

- [ ] **T14.2** Make the rules baseline shrink, and correct the `game_window.py` waiver record
Files: `scripts/check_rules.py`, `scripts/rules_baseline.txt`, `project-harness/DECISIONS.md`,
`project-harness/ISSUES.md` — **not** `demo_game/`
Spec: narrowed 2026-09-17 the same way as T14.1. `demo_game/ui/layout/game_window.py` is 925 lines,
grandfathered at exactly 925 in `rules_baseline.txt` against a limit CLAUDE.md calls **800 hard and
unwaivable**, and against a documented 350-line waiver in `DECISIONS.md` (CR-L07-03). Splitting it is
the obvious fix, but the loop reaches T14 while the T13 census is still deferred, and T13.1 already
names the oath and treaty controls inside that file as deletion candidates — splitting it now splits
code T13.2 is expected to cut. **Do not edit any file under `demo_game/` in this task.** Do only what
does not depend on the census:
(1) **ISSUE-320.** `check-rules` reports a resolved baseline entry on every run and never ratchets it
down — a baseline that cannot shrink is not a ratchet. Make the ratchet remove resolved entries, prune
the stale ones, and close the issue.
(2) **The waiver record.** `DEC-074` records the file under a third path
(`demo_game/ui/game_window.py`); correct it to `demo_game/ui/layout/game_window.py`, and correct the
stale 350-line waiver to state the file's real size and that its split waits on T13.2.
(3) **Log the split** as an issue with T13.2 as its prerequisite: split `game_window.py` by
responsibility (model, view wiring, event handling, rendering) per SRP, then delete — not merely
resolve — its `R001` row from `rules_baseline.txt`, and bring any other `demo_game` module over 800
lines under it.
`check_rules.py` already scans `demo_game/` (docstring `:23`, `:254`; iterated at `:258`) — do not
spend the session making it.
RED anchor: `python scripts/check_rules.py` reports at least one resolved baseline entry today and
`scripts/rules_baseline.txt` still carries it (ISSUE-320); after the fix the resolved entry is gone
from the file and the next run reports none.
Validation: `python scripts/check_rules.py` twice (the second run reports no resolved entry),
`make check`.
Done when: ISSUE-320 is closed, `DEC-074`'s path and the waiver are corrected, the split issue is
logged against T13.2, and no file under `demo_game/` was edited. Findings CR-L07-03, ISSUE-320.

---

# SPRINT 8 — Make failure visible and the ledger true

**Self-contained goal:** an engine that stops working says so, and the written record matches the
measured system. This sprint closes the observability gap that let every finding in this programme
hide.

### Phase T15

The census gap: 27 engines ran, every `last_error` null, and only 6 did any work.

- [ ] **T15.1** Teach `engine_status` to say "starved", and export it
Pre-approved: public-interface · owner 2026-09-08
Files: `src/npc_engine/scheduler/engine_status_store.py`,
`src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/api/routes/admin/system.py`,
`scripts/loc_baseline.txt`, new
tests `tests/unit/scheduler/test_engine_status_working_set.py`,
`tests/unit/api/test_engine_status_metrics_exported.py`
Spec: engines are exception-isolated so one bad engine cannot halt the tick — sound, but it converts
a loud crash into a silent absence with no compensating signal. The record itself is good:
`EngineStatusRecord` carries `last_tick_id`, `last_error`, `last_error_tick`, `error_count`,
`last_duration_ms`, `tick_count`, populated at `tick_scheduler.py:225-241`. It is surfaced at
`api/routes/admin/system.py:98-109` and `api/routes/world/clock.py:131`, and consumed by
**nothing** — `grep -rn "engine_status\|last_error\|error_count" src/npc_engine/api/` returns only
the wiring and those two read routes. `GET /health` returned `{"status":"ok"}` throughout the review
and would do so with every engine erroring.
Two changes, and **(2) is the load-bearing one** — without it, (1) would not have caught the two
dead engines Sprint 3 revived, because `error_count: 0` and a non-null `last_duration_ms` look
identical for a healthy idle engine and a permanently starved one.
(1) Export `engine_last_error_tick` and `engine_error_count` as gauges on
`GET /v1/admin/system/metrics`, beside the DEC-273 `llm_backend_*` metrics.
(2) Add `working_set_size` (or a `worked` boolean) to `EngineStatusRecord`, set by the scheduler
from the engine's returned payload — engines already return dicts like
`{'moved': 0, 'skipped': 0}`, so the scheduler can derive it without touching each engine. Export it
too, so a permanently-zero working set is visible over time rather than only in a single poll.
Do **not** add a gate that fails the build on an idle engine — some are legitimately idle. Make it
visible; T15.2 turns it into a check.
RED anchor: the first test asserts an engine returning a zero-size working set is distinguishable
from one that did work; the second asserts a non-null `last_error` produces a non-zero
`engine_error_count` on the metrics endpoint. Both fail today.
**This task does NOT fix ISSUE-339, and that limits what it delivers.** Ten of eleven
`evals/probe_*.py` modules pass an `engine_name` to `probe_runner.py:204`'s `_merge_status_metrics`
that the scheduler never registers (`"events"` vs `"event"`, `"memory"` vs
`"memory_consolidation"`/`"memory_decay"`, and so on), so those probes silently receive no
`tick_count`, `error_count` or `duration_ms`. **`working_set_size` will be exactly as invisible to
them, for the identical reason** — so Sprint 8 can ship believing it closed the observability gap
while the eval-side consumer of that observability stays broken. Either fold ISSUE-339's mapping fix
in here, or state in the completion note that it must land separately before probes can observe
`working_set_size`.
This task adds src LOC after T10.2b seeded the ratchet, so if the delta is positive bump
`scripts/loc_baseline.txt` in the same commit with the reason in the commit message, per rule 1.
T10.2b is instructed to budget this addition into its seed, so a bump should be unnecessary — if one
is needed, say why.
Validation: `pytest tests/unit/scheduler/ tests/unit/api/test_engine_status_metrics_exported.py -v`,
then `make check`. Findings L13-04, ISSUE-339, SEV-12.

- [ ] **T15.2** Assert the surviving portfolio actually works
Files: new `tests/integration/test_engine_census_does_work.py` or a `make` target, `docs/ENGINES.md`
Spec: T4.2 gated *reachability* statically; this gates *effect* dynamically, which is the half that
needs a running stack. Bring a stack up, advance the clock several ticks against the seeded world,
read `GET /v1/admin/system/engines`, and assert that every engine expected to work has a non-zero
working set. Maintain the expected-to-work list explicitly in the test, with a one-line reason per
engine — an engine legitimately idle in the demo seed is listed as such rather than silently
excluded.
This is the check that would have caught the entire Sprint 2 and 3 finding set in one run: at review
time it would have reported 17 of 27 engines doing nothing, with `routine` and `need_decay` as hard
failures.
On `docs/ENGINES.md`: T3.1, T3.2 and T4.1 each already update the **per-engine description rows**
for the engines they remove, so do not re-derive those. What those tasks do **not** touch, and what
this task owns, is the **tick-order and dependency sections** — re-derive them against the surviving
portfolio and the order T6.2 pinned.
RED anchor: run it against the pre-Sprint-3 tree — `routine` and `need_decay` must fail; on the
current tree, after T5.1 and T5.2, they must pass. Get that old tree with
`bash scripts/eval_stack_at.sh <pre-Sprint-3-sha> --reset`, which extracts it with `git archive`
rather than a `git worktree`, for the reasons T4.2 gives.
Validation: run against a stack, then `make check`.
Done when: the check exists, passes on this tree, and demonstrably fails before Sprint 3.
Finding L13, census section.

- [ ] **T15.3** Close the three API-boundary security findings nothing scheduled
Pre-approved: public-interface · owner 2026-09-09
Files: `src/npc_engine/config.py`, `src/npc_engine/auth/`, the admin route models under
`src/npc_engine/api/routes/admin/`, the `/setup` route, new
`tests/unit/api/test_api_boundary_hardening.py`, `project-harness/ISSUES.md`
Spec: three Log-dispositioned findings from the 2026-09-07 review that had no task and were not in
the Parked list until 2026-09-09. All three are the exact class `project-harness/CLAUDE.md` names in
its own strict rules — "input caps at the API boundary; auth on every route except `GET /health`" —
and they are what a studio security review asks about first, which matters for a programme whose
priority-1 goal is a studio evaluator booting the stack.
(1) **ISSUE-301** — `API_KEY_GRAPH_WRITE` and `API_KEY_ADMIN` have no weak-secret validation. Add
startup validation rejecting empty, default, or trivially short keys, failing fast with a clear
message rather than booting with a guessable admin key.
(2) **ISSUE-302** — the admin `npc_ids` and `location_ids` list parameters are unbounded. Add a
named cap and return 422 above it. An unbounded id list is an amplification vector into the graph.
(3) **ISSUE-303** — `/setup` uses a **prefix match** rather than an allow-list. Replace it with an
explicit allow-list; a prefix match grants more than it names, which is the defect.
Do all three in one task: they are small, they share a test file, and they are the same rule.
RED anchor: the new test asserts a weak `API_KEY_ADMIN` is rejected at startup, an over-cap
`npc_ids` list returns 422, and a path that merely *shares a prefix* with an allowed `/setup` route
is refused. All three fail today.
Validation: `pytest tests/unit/api/test_api_boundary_hardening.py -v`, then `make check`.
Done when: all three tests pass, `make check` is green, and ISSUE-301, ISSUE-302 and ISSUE-303 are
closed and archived. Findings ISSUE-301, ISSUE-302, ISSUE-303.

- [ ] **T15.4** Fix the `/standings` 500 by adding `target_name`, not by changing `target`
Pre-approved: file-deletion · owner 2026-09-18
Files: `src/npc_engine/graph/faction/faction_queries.py` (`CYPHER_LIST_STANDINGS`, `list_standings`),
`src/npc_engine/api/routes/faction_politics/factions.py` (`FactionStandingRow`),
`tests/unit/graph/test_faction_queries.py`, new test `tests/unit/api/test_faction_standings_route.py`,
delete `e2e/scenarios/scenario_faction_politics.py`, `docs/API.md`, `docs/DATA_MODELS.md`
Spec: ISSUE-354. `GET /v1/admin/factions/{id}/standings` has 500'd on every call since `87038812`
(2026-06-15): the query returns `properties(b) AS target` (a node dict) and `FactionStandingRow`
declares `target: str`. Owner decision 2026-09-18, after an adversarial review: fix it **additively**:
the query returns `b.id AS target, b.name AS target_name`, and `FactionStandingRow` gains
`target_name: str`. Do NOT change `target`'s type: a string-to-object change is a
`RESPONSE_FIELD_TYPE_CHANGED` break in `scripts/api_contract_differ.py`, and no surviving consumer needs
more than id and name (`e2e/scripts/faction_setup.py:153-157` reads only `standing`). Delete
`e2e/scenarios/scenario_faction_politics.py`: its only assertion is decay by the `faction_politics`
engine deleted in T3.2, and it is the sole reader of `target["id"]`. Update `list_standings`'s docstring
and the two docs' row shape. The demo's FACTION panel is **out of scope** (ISSUE-359, owned by T13.1).
RED anchor: the new route test drives the endpoint with a service returning the query's real row shape and
expects 200 with `target` a string and `target_name` present; it fails today with a response-validation 500.
Validation: `pytest tests/unit/api/test_faction_standings_route.py tests/unit/graph/test_faction_queries.py -v`,
then `make check`. `make check-api-contract` must pass **without** `--update`: needing a re-record means
the change is not additive and the task is wrong. Live: rebuild the eval stack
(`bash scripts/eval_stack_at.sh HEAD --reset`), `make eval-stack-seed`, and `GET` one seeded faction's
standings: expect 200 and non-empty rows.
Done when: both tests pass, `make check` is green with no contract re-record, the live GET returns rows,
and ISSUE-354 is closed and archived. ISSUE-354.

### Phase T16

The written record.

- [ ] **T16.1** Amend DEC-273 — its mechanism holds, its constants do not
Files: `project-harness/DECISIONS.md`, `project-harness/ISSUES.md`,
`project-harness/archive/ISSUES_RESOLVED.md`
Spec: DEC-273 was three days old at review time and already being cited as settled. Re-measured over
four turns on a running stack, three of its five claims do not reproduce: decode is **68.7 / 87.4 /
84.4%** of a warm turn, not ~97%; prefill is **540-1,779ms**, 11-30% of the turn, not "prefix-cached
and effectively free"; warm dialogue is **4.79-5.95s** backend and **5.26-6.39s** end to end, not
3.5-4.2s. Confirmed: the 10.3s cold load (10.515s) and that `keep_alive` holds the model. Half true:
`keep_alive` prevents the *second* cold load, not the first.
**Amend in place, do not retract** — replace the constants, date the amendment, and name this
programme's HEAD. State the measurement conditions the original omitted: idle backend, single
session, no concurrent tick — and add the caveat that these are best-case numbers, since T8.1 exists
precisely because a background tick can push an interactive turn past its timeout. Preserve DEC-273's
null result verbatim: schema trimming moved decoded tokens 70.0 to 72.0, and it remains a reason not
to re-propose schema trimming.
**Re-measure before writing the numbers**, on a tree with Sprints 1-4 landed, and rebuild first —
the app image is not bind-mounted, and measuring without a rebuild re-records stale numbers, which
is exactly how DEC-273 acquired its wrong constants. Say in the entry which fixes were in the tree
when the numbers were taken; that one line is what would have prevented this task existing.
Also **archive ISSUE-273** while here — it is fixed but still open. The `has_draft_quest` guard
exists at `engines/quest_generation/world_state_quest_trigger.py:150` (note the directory —
`engines/quest/` holds the lifecycle engine, not the triggers) and `:Quest` held at 18 across 6
advances. Mark it `## [FIXED] ISSUE-273:`, add the `**Fixed:**` line, move it verbatim into
`archive/ISSUES_RESOLVED.md`.
RED anchor: `make check-ledger-ids` must stay green through the ISSUE-273 move, and ISSUE-273 must
appear in exactly one file afterwards.
Validation: `make check-ledger-ids`, then `make check`.
Done when: DEC-273 amended with fresh numbers and stated conditions, ISSUE-273 archived.
Findings L9-03, L9-04, SEV-13.

- [ ] **T16.2** Fix the instrumentation that cannot express its own budget
Pre-approved: public-interface · owner 2026-09-08
Files: `src/npc_engine/engines/llm/llm_metrics.py`, `scripts/loc_baseline.txt`, new
`tests/unit/llm/test_llm_metrics_buckets.py`, `project-harness/ISSUES.md`
Spec: two defects in the metrics DEC-273 introduced.
(1) **No buckets.** `llm_backend_latency_seconds` is a count/sum/min/max summary
(`llm_metrics.py:12-14`), so no p50/p95 is derivable from the endpoint. The 3-7s dialogue budget is
a percentile claim the shipped instrumentation cannot evaluate. Add histogram buckets sized around
that budget — the boundaries should straddle 3s and 7s so a breach is visible without arithmetic.
(2) **Under-counting.** `llm_tokens_in_total` excludes the system channel and under-counts real
input tokens by **4.3x**, measured. Given the ~4,245-token static system prompt, any prompt-budget
reasoning done from this metric is wrong by that factor. Include the system channel, and state the
change in `DECISIONS.md` because it moves a published number.
Close ISSUE-318 and ISSUE-319 as part of this task.
RED anchor: the new test asserts the latency metric exposes buckets spanning the budget, and that a
call with a known system-prompt size increments `llm_tokens_in_total` by the full input including
system. Both fail today.
Validation: `pytest tests/unit/llm/test_llm_metrics_buckets.py -v`, then `make check`, then confirm
against a running stack that `GET /v1/admin/system/metrics` exposes the buckets.
Done when: buckets exist, token counting is correct, both issues closed. This task adds src LOC after
T10.2b seeded the ratchet — if the delta is positive, bump `scripts/loc_baseline.txt` in the same
commit with the reason, per rule 1 (T10.2b is instructed to budget it, so a bump should not be needed).
Findings L9-05, L9-06, ISSUE-318, ISSUE-319.

- [ ] **T16.3** Split `harness_version` so a case edit stops orphaning every prior run
Pre-approved: public-interface · owner 2026-09-08 · DEC-281
Files: `evals/_run_config_hashing.py`, `evals/run_config.py`, `evals/comparability.py`,
`evals/trend_store.py`, `evals/trend_row_builder.py`, `docs/REGRESSION_POLICY.md`, new test
`tests/unit/evals/test_comparability_case_set.py`
Spec: `resolve_harness_version` (`_run_config_hashing.py:98-122`) hashes `evals/cases/**/*.yaml` +
`prompts/eval/*.yaml` + `evals/matchers.py` into one value, and `ComparabilityKey` is exactly
`(harness_version, judge_identity)` (`comparability.py:57-58`) compared for equality (`:76-97`). So
editing one case file makes every earlier run incomparable. This is not hypothetical: the two rows in
`evals/trend/trend_v1.jsonl` carry `f22f61a5d877` and `014abac09947`, so the trend store has never
held a comparable pair and the regression gate has never had a baseline to select.
Split the hash by what it stands for. `harness_version` keeps the **instrument** — `matchers.py` and
`prompts/eval/`. A new `resolve_case_set_version` takes the **subject** — `evals/cases/` — and
`TrendRow` gains `case_set_version`. `ComparabilityKey` keeps its shape and keys on the instrument,
because an instrument change is what actually invalidates a comparison; that is why EVAL-P18.1 added
the hash. Case-set drift is already covered by `compare.py`'s case-intersection refusal
(`_comparability_error`, `:228-258`), so nothing is lost. Do **not** simply weaken the hash — that
trades a false negative for a false positive.
`docs/REGRESSION_POLICY.md` states this contract at `:27-30` and is part of this change, not separate
work; while there, fix its stale code sample at `:143`, which shows a
`select_baseline(harness_version, ...)` signature that no longer matches `baseline_selection.py:109`.
Recorded hashes will not reproduce under the narrower scope — write the migration note in
`DECISIONS.md`, the same cost T20.1 already accepts once for `dialogue_prompt_hash`.
**Must land before T17.2.** T17.2 re-authors or retires scorers and T18.1 relabels; both edit
`evals/cases/` and `matchers.py`. In the current order Sprint 9 would change `harness_version` and
orphan its own baseline, and T18.2's re-baseline would hide the break — so the sprint costing the most
human effort would be the one whose before/after cannot be measured.
RED anchor: a test building two `TrendRow`s that differ only in their case set and asserting
`is_comparable` is True. It fails today at the attribute — `case_set_version` does not exist — and
after that is added it fails on the value, because the case bytes are still folded into
`harness_version`.
Verify: `pytest tests/unit/evals/test_comparability_case_set.py -v`, then `make check-evals-rules`,
`make type-evals`, `make test-cov-evals`, then `make check`.
Done when: the test is green, `docs/REGRESSION_POLICY.md` matches the code, the migration note is in
`DECISIONS.md`, and the two existing trend rows are either comparable or documented as legitimately
not. LOC delta is positive (about +15) — state in the completion note that this buys the
comparability the whole eval layer rests on, per rule 9.
DEC-281 (b).

- [ ] **T16.4** Record the engine's build sha, not the client's working tree
Pre-approved: public-interface · owner 2026-09-08 · DEC-281
Files: `evals/engine_adapter.py`, `evals/run_config.py`, `evals/trend_store.py`,
`evals/trend_row_builder.py`, new test `tests/unit/evals/test_engine_build_sha.py`
Spec: `RunConfig.git_sha` is `git rev-parse --short=7 HEAD` run on the machine driving the eval
(`run_config.py:265-271`). The engine's own identity is `Settings.BUILD_SHA`, served at `GET /health`
as `data.version` (`api/routes/admin/system.py:54-63`) and already compared by
`e2e/scripts/boot_check.py:66-76`. Nothing in `resolve_run_config` calls it. Because the app image is
not bind-mounted, a recorded run can name a tree that never generated its text — the defect class
`trend_row_builder.py:72-79` documents as having once let an arm "claim a SHA it never ran", where the
fix was applied only to the token budget.
Add `fetch_build_sha(base_url, api_key)` to `engine_adapter.py` reading `data.version`, reusing the
unwrap `boot_check.py:29-40` already performs; add `engine_build_sha` to `RunConfig` and `TrendRow`
alongside `git_sha`. Keep both: the two differing is the signal, so do not replace one with the other.
Treat an unreachable `/health` as unknown rather than fatal — this must not stop a run the way
`ModelDigestUnavailableError` does.
RED anchor: a test resolving a `RunConfig` against a stub `/health` and asserting it carries the
stub's sha. Fails today at the attribute — the field does not exist.
Verify: `pytest tests/unit/evals/test_engine_build_sha.py -v`, then `make check`. Then, against a
running stack: `make eval-stack-up` (which boot-checks the sha), resolve a config and assert
`engine_build_sha` equals `git rev-parse --short HEAD`; then deliberately point at a stale image and
assert the two fields **differ** — that second half is the whole point of the task. Build the stale
image with `bash scripts/eval_stack_at.sh <older-sha>` and resolve the config from this tree.
Done when: both fields are recorded, the stale-image case is demonstrated to differ, and a note in
`DECISIONS.md` says which of the two downstream consumers read. LOC delta about +10; justify per
rule 9 as the attribution the A/B rests on.
DEC-281 (c).

- [ ] **T16.5** Correct the two measurement constants that name retired things
Pre-approved: file-deletion · owner 2026-09-08 · DEC-281
Files: `evals/regression_gate.py`, `evals/mde.py`, `tests/unit/evals/test_regression_gate.py`,
`tests/unit/evals/test_mde.py`
Spec: two independent stale references, both silent.
(1) **A regression check that has never fired.** `check_regression` (`regression_gate.py:157-173`)
reads `candidate.guard`, the combined field DEC-243 **retired**. It is `None` on every row written
since, and `_rate_regressed` returns `False` when either side is `None` (`:89-90`), so one of four
regression checks is a structural no-op. The trend store shows it: the newer row carries
`guard: None` with `guard_adversarial` populated. Point the check at `guard_adversarial` and
`guard_anti_hallucination`, or delete the dead branch — rule 2 favours deleting if the two successor
fields are already covered elsewhere; check before choosing.
(2) **An MDE table citing a retired judge.** `mde.RECORDED_KAPPAS` (`:132-136`) is
`tone_judge 0.849, affirms_judge 0.530, refusal_judge 0.247`. DEC-269 retired `refusal_judge` into
`affirms_judge` and split out `commits_judge`, which is absent — so every table
`arm_probe_report.print_mde_section` prints is wrong in both directions. Correct the tuple, and
prefer sourcing kappa from the calibration artifact over a module constant if one is readable at call
time.
RED anchor: two assertions. First, a candidate that regresses on `guard_adversarial` against a
baseline — `check_regression` returns `regressed=False` today. Second, `RECORDED_KAPPAS` names exactly
the surviving scorers — it names `refusal_judge` today. Both fail.
Verify: `pytest tests/unit/evals/test_regression_gate.py tests/unit/evals/test_mde.py -v`, then
`make check-evals-rules`, `make type-evals`, `make test-cov-evals`, then `make check`.
Done when: both anchors are green and the LOC delta is reported — this one should be negative or flat.
DEC-281, "Found while auditing".

- [ ] **T16.6** Stop the eval harness recording `None` model digests from live-network defaults
Pre-approved: public-interface · owner 2026-09-09
Files: `evals/run_config.py`, `tests/unit/evals/` (the call sites that exercise it),
`project-harness/DECISIONS.md`
Spec: **CR-L15-01 from the 2026-08 review, re-verified live in the tree on 2026-09-08 and absent
from this roadmap until now.** `run_config.py:348-350` reads:
`gen_digest_fn = fetch_generation_digest or _engine_adapter.fetch_model_digest`,
`judge_digest_fn = ... or _engine_adapter.fetch_model_digest`,
`version_fn = fetch_ollama_version_fn or _engine_adapter.fetch_ollama_version`.
Every one of those defaults to a **live network call**. Unit tests and CI that do not inject a fake
therefore reach for a backend that is not there, and the run records `None` for the generation and
judge digests — the model identity that makes a row attributable at all.
This sits directly against T16.4, which is added in this same phase to stop a run naming a tree that
never generated its text. A row with a null model digest is the same class of unattributable record,
arriving from a different code path. Fixing one without the other leaves the attribution story half
built.
Fix: inject fakes for `fetch_generation_digest`, `fetch_judge_digest` and `fetch_ollama_version_fn`
at every uninjected call site `run_config.py` and its tests exercise, so no unit test can silently
reach the network. Treat an unavailable digest the way T16.4 treats an unreachable `/health` — record
it as explicitly unknown, not as `None` masquerading as a value — and decide deliberately whether a
missing digest should fail a *recorded* run rather than being written as null. State the choice in
`DECISIONS.md`.
Sequencing: **before Sprint 9's re-baseline.** T18.2 re-baselines on top of whatever the trend store
holds; doing that over rows with null digests bakes the defect into the new baseline.
RED anchor: a test resolving a `RunConfig` with **no** digest functions injected and no backend
reachable, asserting it does not attempt a network call and does not record a `None` digest. It
fails today on both halves.
Validation: `pytest tests/unit/evals/ -v`, then `make check-evals-rules`, `make type-evals`,
`make test-cov-evals`, then `make check`.
Done when: no uninjected live-network default remains in `resolve_run_config`'s digest path, the
`DECISIONS.md` note is written, and the completion note records that CR-L15-01 is closed.
Finding CR-L15-01 (`review-2026-08/TRIAGE.md`).

<!-- LOOP:QUEUE end -->

---

## Outside the queue

These need human judgement or live model runs the overnight loop cannot supply. They are sequenced
after Sprint 8 because both depend on a settled codebase — measuring a system you are still deleting
from produces numbers you cannot attribute.

### SPRINT 9 — Repair the judged eval layer

**Owner: Lohann Colle. Due: detailed into tasks within 7 days of Sprint 8's last commit.**

> **Sprint 9 is unscheduled; do not assume it will happen automatically.** It sits outside the fence,
> so the loop will never reach it, and nothing else forces it. That matters more than it looks:
> Sprints 6-8 spend real engineering (T16.3, T16.4, T16.5, T16.6) on eval infrastructure whose
> **entire payoff is conditional on this sprint running**. If it does not, the honest six-month
> status is "the mechanism is better, and we still cannot say whether dialogue quality regressed" —
> the same practical position as today, with more infrastructure underneath it. This repo has
> already lived that failure once: see Sprint 0's Provenance note, where R6.1-3 sat
> archived-and-unticked through a whole review cycle.

**Owner decision, 2026-09-08: keep and repair.** This is why eval comparability has value
throughout this roadmap, and why T2.2 was chosen specifically for not touching the prompt hash.

**The situation.** All five scorers are REFUSED by `scripts/check_label_adequacy.py`, the label set
is NOT FROZEN, and panel kappa swung 0.58 to 0.83 between runs. Until this sprint lands, **no judged
number may be quoted as evidence of quality** — deterministic matchers, latency stats, retrieval
metrics and `engine_status` liveness remain usable throughout.

Sketch, to be detailed into tasks when the sprint is reached (the specifics will have moved by then;
detailing them now would be writing fiction):

- **T17.1** Diagnose why each of the five scorers is refused — insufficient labels, poor agreement,
  or a population defect. ISSUE-184 records `refusal_judge` and `affirms_judge` at kappa 0.23/0.28;
  ISSUE-295 records the calibration population being derived from the labels file so retired scorers
  are still calibrated; ISSUE-282 and ISSUE-290 record family-size and per-criterion defects.
- **T17.2** Re-author or retire the scorers that cannot reach adequacy. ISSUE-291 records that
  `tone_judge`'s fate is decided but not implemented. Retiring a scorer is a legitimate outcome and
  is cheaper than repairing one — rule 2 applies to evals too.
- **T18.1** Relabel and freeze. The most expensive human step in the programme.
- **T18.2** Re-baseline and re-publish the trend, resolving ISSUE-275, ISSUE-283 and ISSUE-246,
  which all concern rows attributing one generation's kappa to another.

### SPRINT 10 — One batched prompt revision

**Owner: Lohann Colle. Due: within 14 days of Sprint 9's last commit** — it is gated on Sprint 9,
so it inherits Sprint 9's scheduling risk in full.

**Owner decision, 2026-09-08: one batched revision**, paying the `dialogue_prompt_hash`
comparability break exactly once rather than per fix. Must follow Sprint 9, so the before/after is
measurable rather than blind.

The dialogue prompt is ~4,245 static tokens of 17 rules on every turn and had never been reviewed as
a prompt until 2026-09-07. Everything below lands in **one** change:

- **T19.1** Resolve the conflicts and redundancy: Rule 8 (VOICE) vs Rule 2 (ALLIED band) for
  guard/soldier archetypes (L12-02); the Rule 16 vs Rule 2 tie-break currently delegated to model
  "judgement" with no algorithm (ISSUE-327); the two independent 5-band tone systems doing one job
  (ISSUE-328) — prefer resolving the bands **server-side** and passing one answer, per rule 8; the
  three rules restating one anti-hallucination policy (ISSUE-329); and the Output-rules prose
  restating schema-enforced constraints (ISSUE-330).
- **T19.2** Fix the schema coverage: the prompt instructs 4 of 13 fields, and of the 6 the model
  generates, `facial_expression` and `mood_update` get **zero** guidance while `relation_deltas.fear`
  is omitted from the Output rules. `facial_expression` is player-visible in `demo_game/` and judged
  by evals (L12-11). Also delete the dead Rule 11 reference to `available_interactions`, which no
  producer emits (ISSUE-293), and renumber the two rules both numbered 17 (ISSUE-325).
- **T20.1** Re-scope `dialogue_prompt_hash`, which currently hashes the **entire**
  `src/npc_engine/prompts/` tree rather than the dialogue prompt — so editing an unrelated prompt
  already breaks comparability (L12-14). This is an `evals/` semantics change: existing recorded
  hashes will not reproduce under a narrower scope, so it needs its own `DECISIONS.md` entry and a
  migration note.
- **T20.2** Re-baseline the evals against the new prompt and publish the delta.

### Parked

Not scheduled, recorded so they are not rediscovered as new:

- **Rebuilding the political layer.** Deleted in Sprint 2 and recoverable from git
  (`git show <sha>:src/npc_engine/engines/<name>`). The engines are small and templated; rebuilding
  into the settled codebase this programme produces was estimated at 1-2 sessions for all six. Only
  do it if a studio requirement actually appears.
- **Deleting the quest slot-fill LLM call** in favour of the existing `_deterministic_fill`
  fallback — zero new code, removes up to 30 of the worst-case model calls per tick, and rule 8
  favours it. Blocked on Sprint 9: it is a quality trade-off and quality is currently unmeasurable.
- **`stream`/`stream_text`** are implemented but unreachable from the production dialogue path
  (ISSUE-322), while `docs/API.md` and `docs/ARCHITECTURE.md` document WS streaming frames the code
  does not send (ISSUE-299). Either wire streaming up or delete it and correct the docs — do not
  leave the third state.
- **`:TickLease` and the `SchedulerState` tick-id array** grow unboundedly, and the array is scanned
  O(n) every interval tick (ISSUE-335). Needs one retention policy covering ISSUE-279 as well.
- **Memory consolidation asks for JSON through the unstructured `generate`** protocol rather than
  `generate_structured` (ISSUE-323) — exactly the cognitive-demand class a smaller model handles
  worst without structural constraints.

### Also open, not scheduled

Added 2026-09-09. These are dispositioned "Log" in the 2026-09-07 review and appear in **no** task
above. They were previously in neither a `Files:` line nor the Parked section, so a reader of this
roadmap alone — the document `CLAUDE.md` names as "current phase and next task" — would not have
learned they exist. Listing them is honesty about the gap, not a commitment to fix them. Details in
`ISSUES.md`.

| Issue | What | Why not scheduled |
|---|---|---|
| **ISSUE-307** | CLAUDE.md's layer diagram omits `observability/` and `setup/` | Doc accuracy; fold into the next CLAUDE.md edit (T10.2c) if convenient |
| **ISSUE-313** | `matchers.py` has a closed dispatch seam | Touches the eval instrument; belongs with Sprint 9, not before it |
| **ISSUE-314** | Factory self-registration docstring overclaims | Cosmetic |
| **ISSUE-315** | Adding a tick engine touches 4 files | Real friction, but the portfolio is shrinking, not growing — revisit if that reverses |
| **ISSUE-316** | Connection `kind` is an unconstrained `str` | Wants a `Literal`/`Enum`; small, no live defect |
| **ISSUE-317** | `distortion_strategy` docstring overclaims | Cosmetic — but read it alongside T5.3, which fixes the real distortion defect |
| **ISSUE-321** | `BASELINE_2026-08-28.md` is stale | **Closed by T12.2**; listed here only because it was previously unmapped |
| **ISSUE-324** | Proactive dialogue has no fallback or timeout | Overlaps T8.1/T8.2; check whether those close it before scheduling separately |
| **ISSUE-326** | Rule 9 vs Rule 5 collision | Partly addressed by rule 9's scope amendment above; re-read after T10.2c |
| **ISSUE-331** | Rule 8 carve-out contributing to ISSUE-128 | Rule 8 is ungated by decision; this is the cost of that |
| **ISSUE-333** | `tone_judge.yaml` construction | Sprint 9 owns `tone_judge`'s fate (ISSUE-291) |

**ISSUE-301, ISSUE-302 and ISSUE-303** were on this list and are now **scheduled as T15.3** — they
are the three security findings, and the owner decided 2026-09-09 that a studio-facing programme
should not carry them unowned.
