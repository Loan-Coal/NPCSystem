# Overnight Roadmap Loop — operator runbook

Implements one ROADMAP task per fresh headless Claude session, gates it, ticks it, commits
it, and keeps going until the queue drains. Built 2026-07-31. Design rationale and the
Windows port analysis: `OVERNIGHT_LOOP_PLAN.md`.

---

## Quick start

**The loop runs only in a dedicated git worktree** (ISSUE-139). In the primary checkout it
refuses to start: sessions commit with `git add -A`, so a concurrent interactive edit would be
swept into a roadmap commit nobody gated. From the primary checkout, once:

```bash
# 1. a worktree on its own branch (the loop also refuses to run on main)
git worktree add ../NPCSystem-loop -b auto/roadmap-night
cd ../NPCSystem-loop

# 2. a FRESH .venv — do not link the primary one: its editable install imports the
#    primary checkout's src/, so the gate would test the wrong code
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 3. the .env (API_KEY for the Makefile, settings for the tests)
cp ../NPCSystem/.env .env

# 4. one hand-run green gate, so the first red the loop sees is not the environment
make check                                # ~7-12 min, must be green

# 5. start the loop — from the worktree
git status --porcelain                    # must be empty
bash scripts/expand_loop.sh --max-tasks 1 # watch one task, foreground
```

The preflight refuses, with the command to fix it, when run in the primary checkout, when
`.venv` is missing or cannot import `pytest`/`mypy`/`ruff`, or when `.env` is missing. Before
a later night, bring the worktree's branch up to date (`git merge` or `git rebase` onto the
work branch) and re-run `make check` there.

Then widen: `--max-phases 1`, then a real night:

```bash
bash scripts/expand_loop.sh --start-at 20:00 --stop-at 08:00
```

## Stale lock recovery

The loop takes a `mkdir` lock at `project-harness/.loop-state/loop.lock/` holding its pid.
A killed run (Ctrl-C mid-teardown, power cut, `taskkill`) can leave it behind.

- **Holder pid dead** — reclaimed automatically on the next launch; you never see it.
- **Holder pid alive** — the launch aborts with
  `FATAL: another loop holds …/loop.lock (pid N)`. Either a loop really is running, or the
  stale pid has been reused by an unrelated process (common under MSYS). Check first:

```bash
ps -p "$(cat project-harness/.loop-state/loop.lock/pid)"   # is it a loop? (bash expand_loop.sh)
rm -rf project-harness/.loop-state/loop.lock               # only if no loop is running
```

The FATAL message and `bash scripts/expand_loop.sh --help` print the same recovery.

## The pieces

| File | Role |
|---|---|
| `scripts/expand_loop.sh` | The loop. Bash, no state of its own. |
| `scripts/loop.config.sh` | Every knob. Edit this, not the loop. |
| `scripts/loop_gates.py` | HALT/AUTOFIX split + frozen paths. **The one file to edit when the gate changes.** |
| `scripts/loop_compat.sh` | Windows substitutes: lock, tree-kill, UTF-8, services. |
| `scripts/roadmap_cursor.py` | The ONLY reader/writer of the roadmap grammar. |
| `scripts/_roadmap_cursor_core.py` | Pure parse/mark logic behind the cursor. |
| `scripts/gate_baseline.py` | Snapshots already-failing tests (phase boundaries only). |
| `scripts/gate_attribution.py` | Is this red gate the task's fault, or pre-existing? |
| `scripts/gate_confirm.py` | Re-runs a failure to rule out a flake. |
| `scripts/classify_gate_failure.py` | Routes a red gate to AUTOFIX or HALT. |
| `scripts/scan_fix_diff.py` | Scans a repair diff for gate-gaming. |
| `.claude/commands/expand-linear-next.md` | The per-task skill. |
| `.claude/commands/fix-make-failure.md` | The bounded repair skill. |

## The work queue

Only tasks between `<!-- LOOP:QUEUE start -->` and `<!-- LOOP:QUEUE end -->` in
`ROADMAP.md` exist to the loop. Currently **EVAL-P0..P24** (Program 3 released 2026-08-09, DEC-160). **19 open tasks elsewhere in the
file** (Phase PERF, Phase EVAL, two bullets inside `## Completed`, Parked, optional PR-9)
are deliberately unreachable. To widen, move the `end` marker — never delete the fence.

```bash
make roadmap-verify                         # after ANY hand edit
python scripts/roadmap_cursor.py --status   # per-phase queue summary
python scripts/roadmap_cursor.py --list-flagged
```

A task is skipped without spending a session if its body carries `⚠️ ask-gate`, `(live`,
or `⏸️`. Today that is EVAL-P0.3, EVAL-P0.4, EVAL-P1.2, EVAL-P6.3.

## Morning review

1. `project-harness/human_verification.md` — everything the night wants a human for.
2. `git log --oneline` — one commit per task. Look for `[UNVERIFIED: regression]` and
   `fix(loop): auto-repair ... [needs review]`.
3. `grep "UNVERIFIED" project-harness/ROADMAP.md` — tasks committed over a red gate.
4. ~~`project-harness/soft_review.md`~~ — deleted 2026-08-28 (DEC-225/DEC-227): 305 lines of
   loop-generated findings that nothing read. The loop rework (R6) must not recreate an
   unread output; findings go to `ISSUES.md` or nowhere.

## Flags

`--max-tasks N` · `--max-phases N` · `--start-at HH:MM` · `--stop-at HH:MM` ·
`--timeout-secs N` · `--model M` · `--sleep-secs N` · `--no-sleep` · `--no-autofix` ·
`--no-review` · `--with-services` · `--push` · `--allow-main` · `--commit-dirty` ·
`--phase ID` · `--dry-run`

## Tolerances (why one bad test does not cost the night)

| Knob | Default | Meaning |
|---|---|---|
| `MAX_CONSECUTIVE_RED_GATES` | 2 | red phase gates in a row before a real halt |
| `MAX_RED_COMMITS` | 3 | task-introduced regressions in a row before a halt |
| `MAX_CONSECUTIVE_BLOCKED_PHASES` | 2 | skips in a row with no progress before a halt |
| `AUTOFIX_ENABLED` | 1 | one bounded repair per auto-fixable red gate |

## Services (`--with-services`, default OFF)

Boots Docker + Neo4j once at startup so the 31 Neo4j-gated integration tests run instead
of skipping, then re-seeds the baseline. **A failed boot degrades to skipping and is
logged — it never turns the gate red.** Leave off for EVAL-P0..P7 (nearly pure Python);
turn on when a program touches `graph/`.

The mixtral judge is deliberately NOT loop work: 26.44 GB on a 12 GB GPU means CPU
inference. Judging is a deliberate batch (see `OVERNIGHT_LOOP_PLAN.md` §6.4).

## Validating a change to the loop — without burning a night

`scripts/expand_loop.sh` is exercised end-to-end by a throwaway rig with stub gates and a
fake `claude` earlier on `PATH`: the whole loop runs in ~40 s with **zero model calls**.
Two bugs were caught this way during the build (a double phase boundary, and
`checkpoint_reports` silently failing on a missing pathspec). Rebuild the rig before
touching the loop. When copying a fixed script into the rig, copy it **after** any
`git reset --hard` — a tracked script gets reverted otherwise.

## Known Windows facts

- `timeout` reports 124 but leaves the process tree alive → all timeouts go through
  `compat_run_timeout`, which reaps via `taskkill //T //F` and **verifies** the reap.
- Every Python child runs with `PYTHONUTF8=1`; the roadmap is full of `—→✅⚠️` and a
  cp1252 child dies on it.
- `ROADMAP.md` is CRLF and `core.autocrlf=false`; the cursor reads and writes with
  `newline=""` so a `--mark` touches two lines, not 1183.
- Disable Windows sleep, or the run dies at the first suspend.
