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

1. **Reverse LOC ratchet.** Non-test `src` LOC may only go down. Raising it needs an explicit
   baseline bump with a stated reason. Gated by `make check-loc-ratchet` from T10.2.
2. **Delete before you abstract.** If a fix can be "add an abstraction" or "remove the feature",
   remove the feature. Record the removal in `DECISIONS.md` if it was ever documented.
3. **No code without a live caller.** Every public function, `Settings` field, prompt YAML and
   contract YAML needs a reader outside its own module and its own tests. Gated from T10.2.
4. **Abstraction requires two.** A Protocol needs 2+ implementors or 3+ callers. Below that,
   inject the concrete class. Gated from T10.1.
5. **A test must be able to fail.** No existence-only assertions (`hasattr`,
   `iscoroutinefunction`), no asserting a constant equals its own literal. Gated from T12.1.
6. **Config must be read.** A declared setting nobody reads is a build failure. Part of rule 3.
7. **One path per concept.** Never two implementations of one domain (an Engine class *and* a
   parallel graph service). Pick one; delete the other.
8. **Prefer deterministic over model.** A model call is a budget item, not a default.
   `engines/gossip/` is the in-repo precedent: seeded, deterministic, no model, and it works.
9. **Net-negative phases.** See the LOC delta rule above.

## Decisions already taken (2026-09-08, by the owner — do not relitigate)

| Area | Decision |
|---|---|
| Political/military layer | **Delete all six**: `military`, `faction_politics`, `treaty`, `agenda`, `succession`, `oath`. Graph services the demo reads (`FactionService`, `pledge_service`, `treaty_service`) **survive**. |
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

- **Sprint 0 is not done. Do not start the overnight loop until it is** — the loop currently
  stages the whole working tree (ISSUE-139) and swallows concurrent edits into its commits.
- 5 tasks in the fence are flagged for an interactive session and the loop will silently pass over
  them: T6.3, T13.1, T13.2, T15.2, T16.1. `make roadmap-audit` reports them once T0B.2 lands.
- The app image is **not** bind-mounted: rebuild before any before/after measurement.
- Integration tests write to the **live** Neo4j (ISSUE-277) — never run the integration suite
  casually, and never between a corpus freeze and its generation.
- Use Git Bash for `make`; the Makefile pins no `SHELL` and POSIX recipes fail under PowerShell
  (ISSUE-281).

### History

| What | Where |
|---|---|
| The M programme (metrics readiness) + R6 | `archive/ROADMAP_M-programme_2026-09-08.md` |
| The 2026-08 remediation programme (R0–R5) | `archive/ROADMAP_remediation-2026-08_2026-09-03.md` |
| Full pre-remediation roadmap (phases 0–26, EXP/F-G-H/SEV, eval P0–P31) | `archive/ROADMAP_pre-remediation_2026-08-28.md` |
| Phases 0–13 / 14–26 | `proposals/archive/ROADMAP_through_phase13_2026-06-03.md`, `archive/ROADMAP_phase14-26_2026-06-11.md` |
| The 2026-09-07 full review that produced this programme | `REVIEW_FINDINGS.md`, `review-fixes/` |
| The 2026-08 review | `CODEBASE_REVIEW.md`, `review-2026-08/` |

---

## How to execute a task in this roadmap

Read this once before your first task. It is the contract.

0. **Sprint 0 first.** The loop is not safe to run until Sprint 0 lands — see its header. T0.1
   adds a preflight refusing to start outside a dedicated worktree, which is the mechanical block
   that enforces this.
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
4. **`make check` must be green before you tick.** It runs `roadmap-verify`, so a malformed
   roadmap edit reds the build.
5. **Report the LOC delta** in the completion note. Use the command in T0 below.
6. A task marked with the pause glyph needs a running stack or a human judgement; the overnight
   loop skips it and it must be done in an interactive session.

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

- [ ] **T0.1** Run the loop in a dedicated git worktree · ISSUE-139 · was R6.3
Files: `scripts/expand_loop.sh`, `project-harness/OVERNIGHT_LOOP.md`
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
RED anchor: dirty an unrelated file, run one task, and confirm the unrelated change lands inside the
loop's commit today.
Validation: after the fix, repeat the same experiment and confirm the loop refuses to start in the
primary checkout; then run one task from a worktree and confirm the commit contains only that task's
files plus the roadmap tick.
Done when: the preflight exists, the experiment is clean, and `OVERNIGHT_LOOP.md` documents the
worktree launch. Closes ISSUE-139.

- [ ] **T0.2** Document stale-lock recovery · ISSUE-126 (remaining half) · was R6.1
Files: `scripts/expand_loop.sh` (usage header), `project-harness/OVERNIGHT_LOOP.md`
Spec: **the no-progress guard already exists (DEC-235) — do not delete it and do not write a second
one.** `expand_loop.sh:648` compares each iteration's task id against `LAST_TASK_ID` and halts once
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
RED anchor: `grep -rn "loop-state/loop.lock" scripts/expand_loop.sh project-harness/OVERNIGHT_LOOP.md`
surfaces no recovery instruction today.
Validation: create the lock dir by hand, run the loop, and confirm the failure message now tells you
how to recover. Then recover using only what the message says.
Done when: the recovery appears in the FATAL message, the usage header and `OVERNIGHT_LOOP.md`.
Closes ISSUE-126.

- [ ] **T0.3** Route harness self-test failures to skip-and-log, not HALT · was R6.2
Files: `scripts/loop_gates.py`, `scripts/classify_gate_failure.py`
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
RED anchor: force a failure in `tests/unit/scripts/` and confirm the loop HALTs the night today.
Validation: after the change, the same forced failure skips the phase, logs the reason, and the
night continues; then force a failure in a *product* test and confirm it still HALTs.
Done when: both halves of that validation hold.

### Phase T0B — the skill and the deferred-work hole

- [ ] **T0B.1** Correct the loop skill's stale facts
Files: `.claude/commands/expand-linear-next.md`, `scripts/loop.config.sh`
Spec: the skill and the config state three things that are no longer true, and each one costs
something.
(1) **File limit.** The skill tells the agent "300-line file limit". `project-harness/CLAUDE.md`
says **400 advisory, 800 hard and unwaivable** (DEC-226). An agent following the skill will split
files that do not need splitting, adding modules to a programme whose entire purpose is removing
them.
(2) **Gate duration.** The skill says `make check` takes "about 144 seconds" and repeats the figure;
`loop.config.sh` carries the same claim plus "2618 passed / 29 skipped / 87.10 % cov". Measured
2026-09-07: **11m58s**, 4,571 passed. The stale number is dangerous rather than merely wrong — the
skill's single most load-bearing instruction is "never background the gate, wait for it", and an
agent told to expect 144s that sees nothing at 144s is exactly the one that concludes it hung. That
is scar 6.1, the night-losing one. Update both, and state the figure as approximate with the date it
was measured.
(3) **Task grammar.** The skill names `Files:`, `RED anchor:` and `Validation:` as the three lines
that constitute a task's specification. The T programme's tasks also carry `Spec:` and `Done when:`.
Add both to the skill's list so the agent is told to read them — `Spec:` in particular carries the
file:line evidence that keeps a cheap model from having to re-derive the problem.
Do not change the loop's behaviour in this task; it is documentation accuracy only.
RED anchor: `grep -n "300-line\|144" .claude/commands/expand-linear-next.md scripts/loop.config.sh`
returns the stale claims today.
Validation: re-read the skill end to end and confirm every factual claim matches the tree; then run
one task through the loop and confirm the agent's own summary does not cite a 300-line limit.
Done when: all three corrections are in and the grep is clean.

- [ ] **T0B.2** Make deferred work visible instead of silently skipped
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
Also add a short **Deferred backlog** section to `ROADMAP.md` listing the flagged tasks by id, so the
debt is visible when reading the file rather than only when running a command.
RED anchor: the new test asserts `--audit-deferred` lists exactly the flagged-and-unticked tasks for
a fixture roadmap and exits non-zero, and exits zero when none remain. Run `make roadmap-audit`
against the real roadmap first: it must list T6.3, T13.1, T13.2, T15.2 and T16.1 today.
Validation: `pytest tests/unit/scripts/test_roadmap_audit.py -v`, then `make roadmap-audit`, then
`make check`.
Done when: the command exists, the loop reports it at both ends of a run, and the roadmap carries the
backlog section.

---

## Deferred backlog — the loop will NOT do these

`compute_next` never returns a flagged task: *"an unattended session must not guess at a human
decision, and skipping costs nothing where attempting costs a whole session."* That is correct, but
it means these tasks are passed over in silence — the loop ticks everything around them and the
roadmap reads nearly complete while they never happened. **They are needed, not optional.**

`make roadmap-audit` prints this list from the file itself once T0B.2 lands; until then this table is
the only record. Keep it in sync when a flagged task is ticked or added.

| Task | Why it cannot be automated | Blocks |
|---|---|---|
| **T6.3** | Reads `engine_status` off a running stack to prove `routine` and `need_decay` revived | Sprint 3's entire purpose. If this never runs, the seed edits in T5 are unverified and the world may still be dead. |
| **T13.1** | `coverage run` over a live demo process — the census cannot be derived statically | T13.2, and therefore all of Sprint 7 |
| **T13.2** | Needs T13.1's artifact plus a live demo run to prove nothing load-bearing was cut | Sprint 7's LOC win, the largest available after tests |
| **T15.2** | Asserts the whole surviving portfolio does work against a running stack | The permanent version of the census that found this programme's biggest cluster |
| **T16.1** | Re-measures latency live; the numbers are the deliverable | DEC-273 stays wrong in the ledger until this runs |

**Two of these were mis-flagged in the first draft and have been fixed:** the seed edits for
`:Schedule` and `HAS_NEED` (T5.1, T5.2) are pure `seed.py` changes with unit tests and are now loop
work. Only their live confirmation (T6.3) is deferred. If you find yourself deferring a whole task
for a live tail again, split it the same way.

<!-- LOOP:QUEUE start -->
<!-- Everything between these markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside these markers — deliberate.
     Scope agreed 2026-09-08: sprints 1-8, the mechanical half of the T programme.
     Sprints 9 and 10 (eval repair, prompt revision) sit outside the fence because they
     need human judgement and live model runs. A task tagged with the pause glyph is
     skipped without spending a session. -->

# SPRINT 1 — The demo works again

**Self-contained goal:** at the end of this sprint a studio evaluator can boot the stack and
play the demo end to end without it breaking or losing itself. Nothing else in this programme
can be verified against a running demo until this sprint lands.

### Phase T1

The two CRITICALs that make the demo unusable. Both were found only by running it.

- [ ] **T1.1** Fix the WebSocket slot leak — the cap exhausts after 5 conversations
Files: `src/npc_engine/api/routes/dialogue/dialogue_ws.py`, new test
`tests/unit/api/test_ws_connection_slot_release.py`
Spec: `MAX_WS_CONNECTIONS_PER_KEY = 5` at `dialogue_ws.py:50`. After `_run_first_turn` the
handler enters an idle-drain loop at `:231-233` that only ever *sends*:
`while True: await drain_proactive_lines(...); await asyncio.sleep(0.5)`. Starlette surfaces a
client-initiated close as `WebSocketDisconnect` only on a `receive()`. With an empty proactive
queue this loop never receives, so `except WebSocketDisconnect` (`:234`) never fires and
`finally: await _release_ws_slot(key_id)` (`:240-241`) never runs. The slot is held for the
process lifetime. The client is NOT at fault: `demo_game/dialogue_ws.py:67` closes correctly via
a `with` block. Fix: replace the sleep-only loop with
`await asyncio.wait_for(websocket.receive(), timeout=PROACTIVE_DRAIN_POLL_SECONDS)`; treat
`TimeoutError` as "nothing from the client, keep draining" and a `websocket.disconnect` message
as the exit. Introduce `PROACTIVE_DRAIN_POLL_SECONDS = 0.5` as a named module constant — no bare
literal. Keep `_release_ws_slot` in the `finally`; the fix is making the loop *reach* it.
RED anchor: the new test opens `MAX_WS_CONNECTIONS_PER_KEY + 1` sockets **sequentially**, fully
closing each before opening the next, and asserts the last is accepted. It fails today — the 6th
is rejected. The sequential-close case is exactly what the existing helper-level guard misses.
Validation: `pytest tests/unit/api/test_ws_connection_slot_release.py -v`, then `make check`.
Done when: the new test passes, `make check` is green, and no other WS test regressed.
Blocks: T1.2, T2.3, and every demo verification in this programme. SEV-01, finding L9-01.

- [ ] **T1.2** Delete the `military` engine — it conquers the barracks on tick 5 and ends the game
Files: delete `src/npc_engine/engines/military/`, `src/npc_engine/engines/ports/military_port.py`,
`src/npc_engine/graph/repositories/military_repository.py`, `tests/unit/engines/military/` and any
`tests/**/*military*`; edit `src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/api/dependencies_advanced/politics.py`,
`src/npc_engine/api/dependencies_engines/engine_slots.py`, `docs/ENGINES.md`
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
Note `tick_scheduler.py:131-132` calls this engine "a no-op stub (see ISSUE-001)" — that docstring
is wrong on both counts and dies with the engine (ISSUE-334).
RED anchor: a new test `tests/unit/demo/test_seed_has_no_tick_zero_defeat.py` asserting that in the
seeded world no faction controls `DEMO_LOSE_LOCATION_ID` at tick 0 **and** that no two opposing
armies share a location at tick 0. Write it before deleting; it must fail today.
Validation: `pytest tests/unit/demo/test_seed_has_no_tick_zero_defeat.py -v`, then `make check`, then
`make test-demo` (baseline 1,116 passed — any delta must be explained).
Done when: `make check` green, `grep -rn "MilitaryEngine\|military_engine" src/ tests/` returns
nothing, and the LOC delta is reported (expect about -1,373).
SEV-01 sibling; findings L6-01, L9-02, L10-04, ISSUE-334.

### Phase T2

The free latency wins. Both are small, both are user-visible, neither touches a prompt.

- [ ] **T2.1** Warm the model at startup — the demo's opening line currently costs 20 seconds
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
Done when: tests pass and `make check` is green. Finding L9-04, SEV-05.

- [ ] **T2.2** Cap the reply length — `max_tokens: 512` against a "1-3 sentences" instruction
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
Done when: tests pass, `make check` green, hash unchanged. Finding L12-12, SEV-06.

- [ ] **T2.3** Rate-limit WebSocket dialogue throughput
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
so the demo still completes. Finding L1-01, SEV-09.

# SPRINT 2 — Delete the political layer and the dead engines

**Self-contained goal:** the engine portfolio contains only engines that are reachable and do
work. About 6,400 LOC leaves the repo. Deletion is cheapest immediately before a refactor, which
is why this sprint precedes the ports collapse and the test prune.

### Phase T3

The political cluster. `military` already went in T1.2; five remain.

- [ ] **T3.1** Delete `agenda`, `succession` and `oath`
Files: delete `src/npc_engine/engines/agenda/`, `src/npc_engine/engines/succession/`,
`src/npc_engine/engines/oath/`, `src/npc_engine/engines/ports/political_port.py`,
`src/npc_engine/engines/ports/pledge_port.py`,
`src/npc_engine/graph/repositories/political_repository.py`,
`src/npc_engine/graph/repositories/pledge_repository.py`, and their tests; edit
`src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/api/dependencies_advanced/politics.py`,
`src/npc_engine/api/dependencies_engines/engine_slots.py`,
`src/npc_engine/api/dependencies_engines/tick_slots.py`, `docs/ENGINES.md`
Spec: none of the three is reachable from an API route via its engine class. `agenda` tallies
`SUPPORTS_AGENDA`/`OPPOSES_AGENDA` weights past a deadline; `succession` grants vacant inheritable
titles; `oath` expires and counts violations on pledges. `agenda` and `succession` share
`PoliticalGraphPort`; `oath` uses `PledgeGraphPort`. **Keep `graph/political/pledge_service.py`** —
`routes/faction_politics/pledges.py` uses it and `demo_game/client.py:1326/1357/1377` reads it. The
engines are the writers; the services are the readers, and only the writers go.
Deletion checklist per engine — work through it exactly: (1) the engine dir; (2) its port file, but
only if no surviving engine imports it; (3) its repository, same condition; (4) its contract YAML
under `engines/contracts/` if one exists; (5) its tests, including any `tests/contract/test_*`;
(6) its `TickScheduler.__init__` parameter and its entry in `_ordered_tick_engines()`; (7) its slot
in `engine_slots.py` and its builder in `dependencies_advanced/politics.py`; (8) any `Settings`
field only it read; (9) its row in `docs/ENGINES.md`.
RED anchor: `python scripts/check_layers.py` and `make check` must be green after removal, and
`grep -rn "AgendaEngine\|SuccessionEngine\|OathEngine\|PoliticalGraphPort\|PledgeGraphPort" src/
tests/` must return nothing. Before deleting, run that grep and record the hit count — that count
going to zero is the anchor.
Validation: `make check`, then `make test-demo`. The demo must still read pledges.
Done when: green, grep clean, LOC delta reported (expect about -835).
Findings L10-03, DEC-279.

- [ ] **T3.2** Delete `treaty` and `faction_politics`
Files: delete `src/npc_engine/engines/treaty/`, `src/npc_engine/engines/faction_politics/`,
`src/npc_engine/engines/ports/treaty_port.py`,
`src/npc_engine/engines/ports/faction_politics_port.py`,
`src/npc_engine/graph/repositories/treaty_repository.py`,
`src/npc_engine/graph/repositories/faction_politics_repository.py`, and their tests; edit the same
wiring files as T3.1
Spec: same shape as T3.1 and the same checklist. `treaty` expires treaties and counts violations;
`faction_politics` decays faction standings toward neutral on a per-tick pass.
**Keep `graph/political/treaty_service.py` and the faction service** — `routes/faction_politics/`
and `demo_game/client.py:1410/1446/1463` and `:1829` read them, and those reads must keep working.
Behavioural consequence to state plainly in the completion note: standings no longer decay and
treaties no longer expire, so that data becomes static. The owner accepted this on 2026-09-08; it
is not visible in a five-minute demo, but it must be written down rather than discovered later.
RED anchor: as T3.1 — record the pre-deletion hit count of
`grep -rn "TreatyEngine\|FactionPoliticsEngine\|TreatyGraphPort\|FactionPoliticsGraphPort" src/
tests/` and drive it to zero with `make check` staying green.
Validation: `make check`, then `make test-demo`, then confirm `GET /v1/admin/factions/` still returns
standings — the service survived.
Done when: green, grep clean, LOC delta reported (expect about -1,540).
Findings L10-03, DEC-279.

### Phase T4

The remaining dead and unreachable engines, then a gate so this never regrows.

- [ ] **T4.1** Delete `mood`, `clique`, `skill`, `deception`, `currency` and the dead classes
Files: delete `src/npc_engine/engines/mood/`, `engines/clique/`, `engines/skill/`,
`engines/deception/`, `engines/currency/`, `engines/contracts/currency_engine.yaml`,
`engines/ports/mood_port.py`, `engines/ports/group_port.py`, `engines/ports/skill_port.py`,
`graph/repositories/mood_repository.py`, `graph/repositories/group_repository.py`,
`graph/repositories/skill_repository.py`, `engines/story_pacing/pacing_queries.py`, the
`SchemingEngine` class inside `engines/scheming/`, and all their tests; edit
`src/npc_engine/api/dependencies_advanced/social.py`,
`src/npc_engine/api/dependencies_advanced/progression.py`, `scheduler/tick_scheduler.py`,
`api/dependencies_engines/engine_slots.py`, `docs/ENGINES.md`
Spec: use the T3.1 checklist for each. Per-engine notes:
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
RED anchor: record the pre-deletion hit count of
`grep -rn "MoodContagionEngine\|CliqueFormationEngine\|SkillProgressionEngine\|DeceptionEngine\|SchemingEngine\|pacing_queries" src/ tests/`
and drive it to zero with `make check` green.
Validation: `make check`, then `make test-demo`.
Done when: green, grep clean, LOC delta reported (expect about -2,443).
Findings L10-01, L10-02, DEC-279.

- [ ] **T4.2** Gate the portfolio — an engine must be reachable and must do work
Files: new `scripts/check_engine_census.py`, `Makefile`, new
`tests/unit/scheduler/test_engine_census.py`
Spec: this is rule 3 ("no code without a live caller") applied to engines, and it is what would
have caught this entire sprint's worth of dead code years earlier. The gate asserts, for every
directory under `src/npc_engine/engines/` that declares a tick engine: (a) it is wired into
`TickScheduler` — a constructor parameter filled from `api/dependencies_*`; and (b) it appears in
`_ordered_tick_engines()` or is called directly by the scheduler. Non-tick engines (`dialogue`,
`economy`, `interaction`, `quest`, `relationship`, `knowledge_learning`, `idempotency`) are exempt
from (a) and (b) but must be imported by at least one file under `src/npc_engine/api/routes/`.
Infra dirs `ports/`, `contracts/`, `llm/`, `tts/` are exempt entirely — list them explicitly in the
script rather than pattern-matching, so an addition is a conscious edit.
Do NOT gate on "does work at runtime" here — that needs a running stack and belongs in T6.1.
Wire it into `make check` next to `check-layers`.
RED anchor: run the new script against the tree **before** T3 and T4 land, using
`git stash`/`git worktree` on the pre-sprint commit — it must report the engines this sprint
deleted. On the current tree it must report zero. If it reports zero on the old tree too, the
script is not actually checking anything and must be fixed.
Validation: `python scripts/check_engine_census.py`, then `make check`.
Done when: the gate is in `make check`, green on this tree, and demonstrably red on the pre-sprint
tree. Findings L10-03, rules 3 and 7.

# SPRINT 3 — Bring the world to life

**Self-contained goal:** NPCs follow daily schedules and have needs, so co-location is real and
gossip pair-selection means something. Two engines go from provably dead to provably working.

**Split note:** the seed edits are mechanical and are loop work. Only the confirmation that the
revived engines actually move NPCs needs a running stack, and that is T6.3 alone. An earlier draft
deferred the whole of T5, which would have meant the loop skipped this sprint's entire purpose.

### Phase T5

The seed defects. Both are graph-shape bugs that no observable can currently express, and both are
pure edits to `demo_game/seeds/seed.py` plus a unit test — no services required.

- [ ] **T5.1** Seed `:Schedule` nodes and `FOLLOWS_SCHEDULE` edges so `routine` can move NPCs
Files: `demo_game/seeds/seed.py`, new test `demo_game/tests/test_seed_schedules.py`
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
Validation: `pytest demo_game/tests/test_seed_schedules.py -v`, then `make check`, then
`make test-demo`.
Done when: the test passes and `make check` is green. Finding L13-01.

- [ ] **T5.2** Add `HAS_NEED` edges so `need_decay` stops being dead
Files: `demo_game/seeds/seed.py`, new test `demo_game/tests/test_seed_needs.py`,
`project-harness/ISSUES.md`
Spec: the seed writes 28 `:Need` nodes carrying a `character_id` **property**, but never the
`HAS_NEED` **edge** that `graph/needs_goals/need_queries.py` matches on
(`(:Character)-[:HAS_NEED]->(:Need)`). A complete live relationship census — 13 types — contains no
`HAS_NEED`. `need_decay` and `need_quest_trigger` are therefore both dead and both report 0.
This is partially logged as ISSUE-210/213 but scoped there as a cosmetic empty prompt field
(`npc.top_need`). It is not cosmetic: it is two dead engines. **Re-scope ISSUE-210** in this same
task — correct its severity and description to say so.
Fix: write the `HAS_NEED` edge alongside each `:Need` node. Also add `SATISFIES_NEED` edges from
locations if the registry declares that edge type, since `need_decay` adds magnitude back at
satisfying locations and without them the decay is one-directional. If the registry does not declare
it, log an issue and leave it.
Sequencing: this revives `need_quest_trigger`, which **increases** the quest-generation LLM
amplification that Sprint 4 exists to bound. That is acceptable because Sprint 4 follows
immediately; do not reorder the two sprints.
RED anchor: the new test asserts every seeded `:Need` is reachable from its `:Character` via
`HAS_NEED`. It fails today with zero such edges found.
Validation: `pytest demo_game/tests/test_seed_needs.py -v`, then `make check`, then `make test-demo`.
Done when: the test passes, `make check` is green, and ISSUE-210 is re-scoped. Finding L13-02.

### Phase T6

Fix the bug that would silently undo Sprint 3, pin the order, then prove the revival on a stack.

- [ ] **T6.1** Re-read world state inside the tick loop — batched advances see a frozen clock
Files: `src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/config.py`,
`src/npc_engine/api/routes/world/clock.py`, new test
`tests/unit/scheduler/test_advance_rereads_world_state.py`, new
`tests/unit/api/test_clock_advance_delta_bound.py`
Spec: two defects in one call path. (1) `tick_scheduler.py:568-582` reads
`world_state = await get_world_state(...)` **once, before** the `for tick_id in range(...)` loop and
passes the same object into every iteration. So `routine.run_tick(time_of_day=...)` at `:461` sees a
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
Done when: both tests pass and `make check` is green. Finding L13-09, SEV-08.

- [ ] **T6.2** Pin the tick execution order
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
Make (a)'s failure message print expected vs actual and point at `ENGINES.md`, so the next person
can tell an intentional reorder from an accident. Cross-check `ENGINES.md` against the real order and
correct the doc if they disagree — **report the discrepancy rather than silently conforming the doc
to the code.**
Note the order changed in Sprints 1-2 as engines were deleted; pin the order as it is *now*.
RED anchor: swap two adjacent engines in `_ordered_tick_engines()`, run the test, confirm it goes
red, restore. A test that does not go red here is not finished.
Validation: `pytest tests/unit/scheduler/test_tick_order.py -v`, then `make check`.
Done when: both kinds of test pass and the swap experiment was observed red. Finding L13-10, SEV-15.

- [ ] **T6.3** Confirm on a running stack that `routine` and `need_decay` now do work ⏸️
Files: new `tests/integration/test_revived_engines_do_work.py`, `project-harness/ROADMAP.md`
(carry-forward note)
Spec: this is the live tail of T5.1 and T5.2, split out so the loop can grind the seed edits
unattended and only this needs a stack. Bring a stack up, advance the clock several ticks against
the seeded world, then read `GET /v1/admin/system/engines` and assert `routine` reports a non-zero
`moved` count and `need_decay` reports a non-zero worked count. Also confirm `npc.top_need` is
populated for at least one NPC, which is the user-visible half of ISSUE-210.
If either is still zero after T5.1 and T5.2 landed, do not tick this task — the seed edit did not
achieve its purpose and the defect is upstream. Say which one, and log it.
Do NOT run the whole integration suite to do this: it writes to the live Neo4j and there is no
separate test database (ISSUE-277). Bring up the isolated stack via `make eval-stack-up`, and
rebuild first — the app image is not bind-mounted, so without a rebuild you are measuring the old
seed.
RED anchor: run this against the tree as it stood before T5.1 — both engines report zero, and the
test fails. That failure is the evidence the sprint was needed.
Validation: run against the isolated stack, then `make check`, then tear the stack down.
Done when: both engines demonstrably do work, and the carry-forward note recording the co-location
revival is added for downstream sprints. Findings L13-01, L13-02.


# SPRINT 4 — Stop the tick from starving the player

**Self-contained goal:** background work can no longer push an interactive dialogue turn past its
budget. This is the sprint that matters most for running a small local model well — the review
found contention, not model size, is the binding constraint.

### Phase T7

Reduce the offered load before arbitrating it.

- [ ] **T7.1** Make `TICK_LLM_CALLS_PER_MINUTE_MAX` real — it is broken on three axes
Files: `src/npc_engine/scheduler/tick_budget_guard.py`, `src/npc_engine/scheduler/tick_scheduler.py`,
`src/npc_engine/scheduler/tick_autopilot.py`, `src/npc_engine/api/routes/world/clock.py`,
`src/npc_engine/config.py`, new tests
`tests/unit/scheduler/test_skip_llm_engines_covers_quest_triggers.py`,
`tests/unit/scheduler/test_tick_budget_guard_counts_calls.py`,
`tests/unit/api/test_advance_clock_passes_skip_llm.py`
Spec: this is the only mechanism meant to stop background work eating the interactive model, and
all three of its axes are broken. **Wrong unit:** `tick_budget_guard.py:76-83`'s
`record_llm_tick()` appends one timestamp per *tick* regardless of how many model calls that tick
made — a tick making 84 calls costs the budget 1. **Wrong coverage:** `skip_llm_engines` is read at
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
Done when: all three pass, `make check` green, DECISIONS entry written. Finding L13-05.

- [ ] **T7.2** Give the three quest triggers one shared per-tick model budget
Files: `src/npc_engine/engines/quest_generation/quest_generation_engine.py`,
`src/npc_engine/engines/quest/` trigger modules, `src/npc_engine/api/dependencies_engines/quest.py`,
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
Done when: the test passes and `make check` is green. Finding L11-03.

### Phase T8

Arbitrate what remains.

- [ ] **T8.1** Add two-class admission control in front of the single resident model
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

- [ ] **T8.2** Wire the per-engine timeouts that four of five engines declare and nobody reads
Files: `src/npc_engine/engines/llm/factory.py`, `src/npc_engine/engines/llm_config_models.py`,
`src/npc_engine/engines/*/llm_config.yaml`,
`src/npc_engine/engines/dialogue/dialogue_handler.py`, new test
`tests/unit/llm/test_per_engine_timeout_wiring.py`
Spec: `grep -rn "timeouts_ms" src/npc_engine --include="*.py"` returns exactly two non-model rows —
the Pydantic field at `llm_config_models.py:96` and its only reader at `dialogue_handler.py:248-249`.
Meanwhile `chapter/llm_config.yaml:16` (30000), `memory_consolidation/llm_config.yaml:16` (30000),
`proactive_dialogue/llm_config.yaml:16-17` (20000) and `quest_generation/llm_config.yaml:16-17`
(30000) all declare a timeout no code path reads. The real ceiling for all five engines is one
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
same defect). Finding L11-02, SEV-10.

# SPRINT 5 — Collapse the abstraction nobody uses

**Self-contained goal:** the ports layer matches the repo's own written rule. Roughly 30 protocol
files and their mirroring repositories leave the tree, and two gates make the rule permanent.

### Phase T9

The collapse. Do it after the deletions — Sprints 2 and 3 already removed about a dozen ports, so
the surface here is smaller than the review's original 44.

- [ ] **T9.1** Collapse single-implementor, single-caller ports to concrete injection
Files: `src/npc_engine/engines/ports/*.py`, the engines that consume them,
`src/npc_engine/api/dependencies*.py`, and their tests
Spec: CLAUDE.md's rule is "abstract behind a protocol at 2+ implementors **or** 3+ callers; below
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
landed; log the deferred feature as an issue rather than leaving dead code.
Work in batches of about five ports per commit so a regression is bisectable.
RED anchor: a new `scripts/check_dip_threshold.py` (built in T10.1, so write it first if you prefer,
or write a throwaway counting script here) reporting every below-threshold protocol. Record the
count before, drive it to zero, and keep `make check` green throughout.
Validation: `make check` after each batch, then `make test-demo`.
Done when: every remaining protocol meets the threshold, `make check` green, LOC delta reported.
Findings L2-01, L2-02, L2-03, L7-05, DEC-275, rule 4.

- [ ] **T9.2** Fix the two god-ports and the ports that leak graph-owned types
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
from `graph/event/event_writer.py`, where `_EventNode` is declared at `:20` as
`class _EventNode(Protocol)` — the underscore is that module's own signal it is private — and uses
it as a parameter type at `event_port.py:33`. The port's own docstring at `:6-7` says engines use it
"instead of importing graph writers." Same shape in `relation_read_port.py:21` (`RelationPhaseRow`)
and `scheming_port.py:22` (`ActiveSchemeProgress`, `SchemeRecord`). The layer direction is legal so
`check-layers` correctly ignores it; the defect is ownership. For any of these ports that survives
T9.1, move the DTO into the port module or a shared `engines/ports/_dtos.py` and have the graph
writer conform to it.
(3) **Redeclared methods.** `quest_port.py:21-124` — three sibling protocols each redeclare a method
another declares (`get_quest_state`, `update_quest_node_status`), all satisfied by one implementor,
with structural typing letting the copies drift silently. Extract a shared base protocol or, if the
siblings collapse under T9.1, this resolves itself.
RED anchor: `grep -n "from npc_engine.graph" src/npc_engine/engines/ports/*.py` — record the hit
count, drive it to zero for private (underscore-prefixed) types, keep `make check` green.
Validation: `make check`, then `make test-demo`.
Done when: no surviving port imports a private graph type, no god-port remains, LOC delta reported.
Findings L2-03, L2-04, L2-05.

### Phase T10

Make the rules mechanical so none of this regrows.

- [ ] **T10.1** Gate the DIP threshold — abstraction requires two
Files: new `scripts/check_dip_threshold.py`, `Makefile`, new
`tests/unit/conformance/test_dip_threshold_gate.py`
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
Wire into `make check`.
RED anchor: run it on the pre-Sprint-5 commit via `git worktree` — it must report the ports T9.1
deleted. On the current tree it must report zero. If it reports zero on both, the counting is wrong.
Validation: `python scripts/check_dip_threshold.py`, then `make check`.
Done when: the gate is in `make check`, green here, demonstrably red before T9.1. Rule 4.

- [ ] **T10.2** Gate dead surface and install the reverse LOC ratchet
Files: new `scripts/check_dead_surface.py`, new `scripts/check_loc_ratchet.py`, new
`scripts/loc_baseline.txt`, `Makefile`, `src/npc_engine/config.py`, delete two prompt YAMLs,
`project-harness/CLAUDE.md`
Spec: two gates plus the cleanup they expose. This is rules 1, 3 and 6.
**Dead surface** (`check_dead_surface.py`): report every `Settings` field with no reader outside
`config.py` and its own tests; every prompt YAML under `src/npc_engine/prompts/` and `prompts/eval/`
that no code loads; every `engines/contracts/*.yaml` with no matching engine. Known findings to
clear as part of this task — verify each is still true before deleting, then delete:
the 9 reader-less `Settings` fields `CONSOLIDATION_CLEAR_TURNS`, `EMBEDDING_REFRESH_ON_WRITE`,
`GOSSIP_DISTORTION_MAX`, `GOSSIP_PERSONALITY_FIELDS_ENABLED`, `GOSSIP_RNG_SEED`, `LLAMA_API_URL`,
`LLM_CACHE_ENABLED`, `MISTRAL_API_URL`, `QDRANT_URL`; and the 2 dead prompts
`prompts/quest_generation/slot_fill_v1.yaml` and `prompts/quest_generation/flavor_v1.yaml`, both
superseded by hardcoded v2 loads — also correct the engine's `llm_config.yaml`, which still names
the dead `v1`. Note `escort_npc.yaml` and `fetch_item.yaml` are loaded via glob and are **not** dead
despite zero literal-name hits; the script must not flag them, which is the main correctness test
for the glob handling.
**LOC ratchet** (`check_loc_ratchet.py`): count non-test LOC under `src/npc_engine/` and compare to
`scripts/loc_baseline.txt`. Fail if it rose. Raising the baseline is a deliberate edit with a reason
in the commit message. Seed the baseline from the tree as it stands *after* this task.
Finally, add the nine rules from this roadmap's preamble to `project-harness/CLAUDE.md` under "The
strict rules", each naming its gate, so the rules survive an unloaded skill — that file's own stated
design principle.
RED anchor: `check_dead_surface.py` must report the 9 settings and 2 prompts **before** you delete
them; that report going to zero is the anchor. For the ratchet, add a throwaway 50-line module,
confirm the gate reds, delete it.
Validation: `python scripts/check_dead_surface.py`, `python scripts/check_loc_ratchet.py`, `make check`.
Done when: both gates in `make check` and green, the 11 dead items deleted, CLAUDE.md updated.
Findings L10 dead-surface sweep, L12-15, ISSUE-332, rules 1, 3, 6.

# SPRINT 6 — Prune the test suite

**Self-contained goal:** `tests/` stops being the largest area in the repo and starts protecting
something. Every surviving test can fail.

### Phase T11

Delete what cannot fail. Sprints 2-3 already removed the tests belonging to deleted engines, so
this sprint works on what remains.

- [ ] **T11.1** Delete tests that assert nothing and tests that assert existence
Files: across `tests/`, plus `project-harness/ISSUES.md`
Spec: rule 5. Three mechanical categories, each identified by a grep and then read individually
before deletion — never delete on the grep alone.
(a) **Assert-nothing:** ISSUE-234 records 25 tests that call the SUT and assert nothing. Find them
with a scan for test functions containing no `assert` and no `pytest.raises`.
(b) **Existence-only:** tests whose only assertions are `hasattr(...)`,
`inspect.iscoroutinefunction(...)`, or "this symbol imports". They prove a name exists and survive
any implementation change that keeps the signature.
(c) **Constant-equals-literal:** tests asserting a module constant equals the literal it is defined
as. These restate the source and go red only when someone edits the constant deliberately.
For each: if the behaviour it gestures at is load-bearing, replace it with a behavioural test; if
not, delete it. Judge "load-bearing" by whether the code under it is reachable from a route, the
scheduler, or the demo — the same standard as T4.2.
Close ISSUE-234 when its 25 are resolved.
RED anchor: this is a deletion task, so the anchor is inverted — record the test count and the
`make test` pass count before, and after. `make check` must stay green, and the pass count must drop
by exactly the number of tests deleted. A larger drop means you deleted something load-bearing;
investigate before continuing.
Validation: `make test`, then `make check`.
Done when: the three categories are empty, ISSUE-234 closed, LOC delta reported.
Findings L4-06, ISSUE-234, ISSUE-310, rule 5.

- [ ] **T11.2** Replace the mock-echo delegate tests with real coverage
Files: `tests/unit/graph/`, `tests/integration/`, `project-harness/DECISIONS.md`
Spec: 127 delegate tests only prove a mock echoed itself. The review ran the counterfactual:
gutting 105 repository passthrough methods produced only 66 failures, so 39 methods are covered by
nothing that can fail. The wrapped Cypher is exercised only by `tests/integration/`, which skips 34
of 43 in the default environment — so `make check` executes **zero real Cypher**. The
representative shape is `tests/unit/graph/test_story_pacing_repository.py:31-41`.
Do not simply delete all 127 — that would remove the only mention of those methods. Instead:
(1) delete the delegate test where an integration test already covers the same method against real
Cypher; (2) keep and strengthen it where no integration coverage exists, by asserting on the
*result shape* the caller depends on rather than that the mock was called; (3) list any method with
neither, and add an integration test for it.
**Do not run the integration suite casually** — it writes to the live Neo4j and there is no separate
test database (ISSUE-277). Use the compose override and a disposable database, or defer execution to
CI. Record which route you took in `DECISIONS.md`.
Sequencing: T12.2 verifies the CI job that runs these; if that verification shows integration tests
do not gate merge, this task's value drops sharply and you should say so in the completion note.
RED anchor: re-run the counterfactual on a sample — gut five repository methods, confirm the suite
goes red for all five. Before this task it goes red for about three of five.
Validation: `make check`, then `make test`.
Done when: the sample counterfactual catches all five, LOC delta reported.
Findings L4-05, CR-L14-02, ISSUE-309.

### Phase T12

Make it stick, and close the two test gaps the review called out by name.

- [ ] **T12.1** Gate that a test can fail, and test the auth wiring that nothing tests
Files: new `scripts/check_test_quality_can_fail.py` or an extension of the existing
`scripts/check_test_quality.py`, `Makefile`, new `tests/unit/api/test_create_app_auth_wiring.py`
Spec: two things, both about the same gap.
(1) **The gate.** Extend the existing test-quality check to fail on the three categories T11.1
deleted, so they cannot come back: no-assert test bodies, existence-only assertions, and
constant-equals-literal. Use an AST walk, not a regex — ISSUE-191 records that the existing
`check_rules.py` is a regex scanner that flags patterns inside comments and docstrings, and
repeating that mistake here would make the gate untrustworthy.
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
Done when: the gate is in `make check`, the auth test passes, and the comment-out experiment was
observed red. Findings L4-02, L4-06, SEV-11, rule 5.

- [ ] **T12.2** Cover the measurement tool, and re-baseline coverage after the prune
Files: new `tests/unit/evals/test_arm_probe*.py`, `Makefile`, `.github/workflows/ci.yml`,
`project-harness/DECISIONS.md`, new `project-harness/BASELINE_2026-09.md`
Spec: three loose ends this sprint must close.
(1) **The unmeasured measurement tool.** `evals/arm_probe.py` and `evals/arm_probe_report.py` ship
at **0%** coverage and `evals/arm_probe_client.py` at 46%. This is the P9 measurement-integrity
tooling — the thing whose job is to establish that measurements are trustworthy — and the aggregate
`make test-cov-evals` floor of 75 passes at 79.76% while these specific modules sit at zero. Test
`ProbeClient.observe/rehydrate/corpus_fingerprint` first (success, HTTP error, malformed payload,
timeout, transport mocked, no live services), then `_run`/`_live_gates` orchestration — especially
that a failing gate is *reported* as failing — then report rendering including empty and all-failed.
Consider a per-module floor so the aggregate cannot hide a zero again; if the harness has no
per-module mechanism, log an issue rather than building one here.
(2) **Verify the CI gate.** Confirm whether the `integration-tests` job is a **required** status
check for merge. If it is not, make it required. Record the answer in `DECISIONS.md` — it determines
whether "no real Cypher in `make check`" is a local-only gap or fully open, and T11.2 depends on it.
(3) **Re-baseline.** `review-2026-08/BASELINE_2026-08-28.md` no longer matches the tree and is
deliberately immutable, so "no delta" can no longer be used as a check. Capture a fresh dated
baseline: `make check` timing, `make test` and `make test-demo` counts, coverage for both floors,
mypy count, and the LOC table from this roadmap's preamble. Lower the coverage floors to match
reality **after** the prune, and state the old and new numbers explicitly — a floor quietly lowered
is how a gate stops meaning anything.
RED anchor: for (1), per-module coverage for the three `arm_probe` modules, before and after. Report
both; do not quote the aggregate as if it were the point.
Validation: `pytest tests/unit/evals/ -v`, `make test-cov-evals`, `make check`.
Done when: the three modules are covered, the CI question is answered in `DECISIONS.md`, and the new
baseline file exists. Findings L4-01, L4-03, L9-09, SEV-14.

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
Known context to fold in rather than re-derive: `demo_game/game_window.py` is 925 lines against a
documented 350-line waiver (CR-L07-03); the branch system is a single two-option stub
(`garrick_deserter`, finding L6-03); and `e2e/scenarios/scenario_territorial_war.py` cannot even be
imported (ISSUE-204) and targeted the `military` engine deleted in T1.2, so it goes regardless.
Mark this file temporary at the top per CLAUDE.md's temporary-file rule and log it in `ISSUES.md`
with a deletion deadline of the end of Sprint 7.
RED anchor: none — this is a measurement task. Its output gates T13.2, which must not start without
it.
Validation: the census table exists and covers every module under `demo_game/`.
Done when: the table is complete and every row has a verdict.

- [ ] **T13.2** Delete what the census marked dead ⏸️
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
Then run the scripted demo end to end and confirm all 12 acts still complete.
Validation: `make test-demo`, `make check`, scripted demo to completion.
Done when: the demo runs, the census's delete rows are gone, LOC delta reported.
Findings L6-03, ISSUE-204, ISSUE-311, CR-L07-03.

### Phase T14

Gate what survives.

- [ ] **T14.1** Bring `demo_game/` under mypy
Files: `mypy.ini`, `Makefile`, `demo_game/`
Spec: `demo_game/` has 256 mypy errors across 45 files and is completely **ungated** — it is
excluded from the type checker while `src/` sits at 0 errors across 637 files. After T13.2 the file
count is much smaller, which is why this comes second: fixing types in modules you are about to
delete is wasted work.
Add `demo_game` to the checked set, fix what remains, and add it to `make check`. If a residual
count cannot be driven to zero in one session, add a `.mypy_baseline`-style ratchet for
`demo_game` specifically and drive it down over subsequent sessions — but a ratchet that never
moves is just a permanent exclusion with extra steps, so record a target date in `ISSUES.md`.
RED anchor: `python -m mypy demo_game` — record the error count before (256 at the 2026-08-28
baseline, expected lower after T13.2) and drive it to zero, or to a recorded ratchet floor.
Validation: `python -m mypy demo_game`, then `make check`.
Done when: `demo_game` is type-checked in `make check`. Baseline finding from
`review-2026-08/BASELINE_2026-08-28.md`.

- [ ] **T14.2** Bring `demo_game/` under the size and structure rules
Files: `demo_game/game_window.py` and any other oversized module, `scripts/check_rules.py`,
`scripts/rules_baseline.txt`, `project-harness/DECISIONS.md`
Spec: `demo_game/game_window.py` is 925 lines against a documented 350-line waiver in
`DECISIONS.md` — a waiver silently violated live on main (CR-L07-03). CLAUDE.md's limits are 400
advisory and **800 hard and unwaivable**, so 925 breaches the hard limit, not just the waiver.
Split it by responsibility, not by line count: one module per category (model, view wiring, event
handling, rendering), per the SRP rule. Then confirm `check_rules.py` actually scans `demo_game/` —
the review found R005 was not scanning `api`, `auth`, `data`, `cache` or `mutation` (CR-L02-04), so
verify the scan set rather than assuming it. Correct the stale waiver in `DECISIONS.md` to match
whatever the file becomes.
While here, clear ISSUE-320: `check-rules` reports a resolved baseline entry on every run and never
ratchets it down — a baseline that cannot shrink is not a ratchet.
RED anchor: `python scripts/check_rules.py` with `demo_game` in scope must report `game_window.py`
over the hard limit. Today it does not, because the file is not scanned. Getting it to report is
half the task.
Validation: `python scripts/check_rules.py`, `make check`, `make test-demo`.
Done when: no `demo_game` module exceeds 800 lines, the scan set is verified, the waiver is honest,
ISSUE-320 closed. Findings CR-L07-03, CR-L02-04, ISSUE-320.

# SPRINT 8 — Make failure visible and the ledger true

**Self-contained goal:** an engine that stops working says so, and the written record matches the
measured system. This sprint closes the observability gap that let every finding in this programme
hide.

### Phase T15

The census gap: 27 engines ran, every `last_error` null, and only 6 did any work.

- [ ] **T15.1** Teach `engine_status` to say "starved", and export it
Files: `src/npc_engine/scheduler/engine_status_store.py`,
`src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/api/routes/admin/system.py`, new
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
Validation: `pytest tests/unit/scheduler/ tests/unit/api/test_engine_status_metrics_exported.py -v`,
then `make check`. Findings L13-04, SEV-12.

- [ ] **T15.2** Assert the surviving portfolio actually works ⏸️
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
Update `docs/ENGINES.md` so its engine list matches the post-Sprint-2 reality — several rows now
describe deleted engines.
RED anchor: run it against the pre-Sprint-3 tree via `git worktree` — `routine` and `need_decay`
must fail. On the current tree, after T5.1 and T5.2, they must pass.
Validation: run against a stack, then `make check`.
Done when: the check exists, passes on this tree, and demonstrably fails before Sprint 3.
Finding L13, census section.

### Phase T16

The written record.

- [ ] **T16.1** Amend DEC-273 — its mechanism holds, its constants do not ⏸️
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
exists at `engines/quest/world_state_quest_trigger.py:150` and `:Quest` held at 18 across 6
advances. Mark it `## [FIXED] ISSUE-273:`, add the `**Fixed:**` line, move it verbatim into
`archive/ISSUES_RESOLVED.md`.
RED anchor: `make check-ledger-ids` must stay green through the ISSUE-273 move, and ISSUE-273 must
appear in exactly one file afterwards.
Validation: `make check-ledger-ids`, then `make check`.
Done when: DEC-273 amended with fresh numbers and stated conditions, ISSUE-273 archived.
Findings L9-03, L9-04, SEV-13.

- [ ] **T16.2** Fix the instrumentation that cannot express its own budget
Files: `src/npc_engine/engines/llm/llm_metrics.py`, new
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
Done when: buckets exist, token counting is correct, both issues closed.
Findings L9-05, L9-06, ISSUE-318, ISSUE-319.
<!-- LOOP:QUEUE end -->

---

## Outside the queue

These need human judgement or live model runs the overnight loop cannot supply. They are sequenced
after Sprint 8 because both depend on a settled codebase — measuring a system you are still deleting
from produces numbers you cannot attribute.

### SPRINT 9 — Repair the judged eval layer

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
