---
description: Implement exactly ONE roadmap task headlessly for the overnight loop, gate it, tick it, commit it, and print a bare status token. Not for interactive use — use /expand-next for that.
---

# /expand-linear-next

You are running **unattended, inside `scripts/expand_loop.sh`**, invoked as
`claude -p "/expand-linear-next --auto --single-task --phase <PHASE> --task <TASK>"`.

Nobody is watching. Nobody will answer a question. Your entire job is **one task**, end to
end, finished and committed before this turn ends.

---

## ⛔ THE TWO RULES THAT LOSE NIGHTS

### 1. NEVER BACKGROUND THE GATE. RUN `make check` IN THE FOREGROUND.

A headless turn **ends the moment you stop calling tools.** If you background `make check`
and say "I'll check the result shortly", this session dies right there and every edit you
made is lost with it.

`make check` takes **about 7 to 12 minutes** on this repo (measured 2026-09-16: 425–595 s,
4,571 tests; 11m58s on 2026-09-07). **Wait for it.** Seeing no output for several minutes is
normal — it has not hung. Do not background it. Do not poll it. Do not say you will come
back to it. Run it in the foreground and wait.

**Budget consequence:** at ~12 minutes a gate run is ~13% of your 90-minute session timeout
(`CLAUDE_TIMEOUT`). Run the full gate **at most twice** — once when you believe you are
green, once after a repair. Iterate with the task's targeted `pytest` path, never with
`make check`.

**Say it again: never background the gate. Run it in the foreground and wait for it.**

### 2. COMMIT BEFORE YOU STOP.

If this turn ends with edits still in the working tree, the loop's next preflight refuses
a dirty tree and **your work is thrown away.** There is no "I'll commit next time".

Every exit path from this skill — success, red gate, even a halt after you edited
something — ends with either a commit or a clean tree. No exceptions.

---

## Your output contract

The **last line** of your response must be exactly one of these, **bare on its own line**,
with no backticks, no bold, no surrounding prose:

```
AUTO_STATUS: TASK_COMPLETE
AUTO_STATUS: PHASE_COMPLETE
AUTO_STATUS: ALL_DONE
AUTO_STATUS: TASK_COMPLETE_BASELINE_RED
AUTO_STATUS: TASK_COMMITTED_REGRESSION
AUTO_STATUS: HALT <reason>
```

A token wrapped in backticks breaks the loop's parser and reads as a halt. Emit exactly one.

---

## 1. Orient — read only what you need

```bash
python scripts/roadmap_cursor.py --slice <PHASE>     # ONLY this phase's body
```

Never read the whole ROADMAP.md — it is over 2,200 lines and the slice is what keeps your
context small. Then read, in order:

1. The **task block for `<TASK>`** inside that slice. It carries five lines, and together
   they are your whole specification — implement to them, not to your own idea of the task:
   - **`Files:`** — what you may touch;
   - **`Spec:`** — the problem, with file:line evidence, so you do not re-derive it;
   - **`RED anchor:`** — the exact check that must fail first, and why;
   - **`Validation:`** — the exact commands;
   - **`Done when:`** — the finish line.
   A task may also carry a **`Pre-approved:`** line — see the halt table in step 2.
2. `project-harness/CLAUDE.md` — the hard rules. Load-bearing here: file size **400 lines
   advisory, 800 hard and unwaivable** (DEC-226; a grandfathered file may not grow) — do not
   split a file that is under 800 lines,
   40-line function limit, 3-level nesting limit, no prompt strings outside
   `src/npc_engine/prompts/`, no raw `dict` across a module boundary (Pydantic v2 only),
   no magic numbers/strings, no layer violations, module + public-function docstrings.
3. `project-harness/DECISIONS.md` — only if the task block names a 🔶 decision.
4. The source files the task touches. **Never edit a file you have not read.**

## 2. Halt guards — check BEFORE writing anything

Emit the halt token and stop (no edits, clean tree) if any of these holds:

| Condition | Token |
|---|---|
| Task body carries a `Pre-approved:` line naming the exact class you are about to trip — one of `file-deletion`, `public-interface`, `graph-schema`, `new-dependency` | do NOT halt — the owner approved it; proceed, and name the approval in your commit body |
| Task body carries `⚠️ ask-gate` | `AUTO_STATUS: HALT ask-gate <what needs deciding>` |
| Task needs a running stack (Neo4j, Ollama, a seeded world, a live measurement) | do NOT halt — follow **Live checks** below. Halt `blocked-prerequisite eval-stack <cause>` only if the stack cannot be built or boot-checked |
| Needs a 🔶 DECISIONS entry that is not ACCEPTED | `AUTO_STATUS: HALT needs-decision DEC-NNN` |
| Needs something that does not exist yet | `AUTO_STATUS: HALT blocked-prerequisite <what>` |
| Requires a layer violation, new dependency, graph schema change, or a public-interface change with callers outside the module | `AUTO_STATUS: HALT ask-gate <what>` |

**The approval must match the action.** A task pre-approved for `file-deletion` still halts
on a graph-schema change; a `Pre-approved:` line covers exactly the classes it names, in
exactly that task, and nothing else. Prose in `Spec:` such as "the owner decided to delete"
is **not** an approval — only the `Pre-approved:` line is.

A halt makes the loop **skip the whole phase** for the rest of the run — every later task
in it goes unattempted. That is why a pre-approved class must not halt. For everything
else, guessing at a human decision costs more than a skipped phase. **When in doubt, halt.**

## 3. Implement — strict TDD, one task only

1. **RED.** Write the test named by the task's `RED anchor` *first*. Run that single test.
   Confirm it fails **for the stated reason** — not an import error, not a typo.
2. **GREEN.** Minimum code to pass. No speculative abstraction. Mock only infrastructure
   (Neo4j, LLM, embedding), and mocks must match real adapter behaviour (LSP).
3. **Review your own diff** before gating: in-place mutation (must be immutable), magic
   numbers/strings, functions over 40 lines, nesting over 3 levels, raw `dict` across a
   boundary, swallowed exceptions, `print()` instead of structured logging.

**Do not do any work outside `<TASK>`.** If you notice a problem elsewhere, append it to
`project-harness/ISSUES.md` with the next free ID and carry on. Do not context-switch.

## Live checks — when the task needs a running stack

A task that says "running stack", "live", "the isolated stack", `make eval-stack-up`, or asks you
to observe or measure the running app is **loop work** (owner, 2026-09-17). The app image is **not
bind-mounted**, so a stack that is already up runs whatever commit it was built from — checking it
checks old code. **Always rebuild first**, in the foreground, and wait (several minutes):

```bash
bash scripts/eval_stack_at.sh HEAD --reset     # build from YOUR working tree, clean eval Neo4j
make eval-stack-seed                           # seed the demo world into it
# ...the task's checks, against http://localhost:8001 ...
```

- **An older tree** (a RED anchor "on the tree before Tx", a before/after pair, a stale image):
  `bash scripts/eval_stack_at.sh <sha> --reset`, then seed. Find the sha with
  `git log --oneline --grep "(Tx)"`. Never use `git worktree` or `git stash` for this.
- The script exits non-zero unless `/health` reports the sha you asked for. **Never trust a live
  result from a stack whose sha you did not just confirm.**
- **Only the eval stack**: app `:8001`, Neo4j `bolt://localhost:7688`, compose project
  `npcsystem-eval`. Never touch the default stack on `:8000`, its `neo4j_data` volume, or any
  `docker compose` command without `-p npcsystem-eval`.
- **Integration tests** run only with `NEO4J_URI=bolt://localhost:7688` and `NEO4J_USER` /
  `NEO4J_PASSWORD` from `.env` exported explicitly. Never run `tests/integration` with the default
  URI — that is the developer's live database (ISSUE-277).
- **Order**: targeted tests → `make check` green → live checks (the HEAD build includes your
  uncommitted edits) → tick and commit. Put the observed numbers in the commit body.
- **Finish with the stack built from your final tree** — if you last built an older commit, run
  `bash scripts/eval_stack_at.sh HEAD` before committing. The owner keeps it up.
- If Docker is unreachable, the build fails, or boot-check never reports the sha: clean the tree and
  emit `AUTO_STATUS: HALT blocked-prerequisite eval-stack <one-line cause>`. **Never tick a task
  whose live check did not run.**

## 4. Gate — foreground, and wait

```bash
make check                 # ~7-12 min. FOREGROUND. WAIT FOR IT. At most twice.
make test-demo             # additionally, if you touched demo_game/
```

### If the gate is GREEN

```bash
python scripts/roadmap_cursor.py --mark <TASK> --date $(date +%Y-%m-%d)
git add -A
git commit -m "<type>(<scope>): <description>"
```

One commit, containing the code **and** the roadmap tick. That commit is the transaction
— it is the only record that this task happened.

Then ask the roadmap whether the phase is finished:

```bash
python scripts/roadmap_cursor.py --phase-done <PHASE>   # exit 0 = phase complete
```

Exit 0 → `AUTO_STATUS: PHASE_COMPLETE`, otherwise → `AUTO_STATUS: TASK_COMPLETE`.

### If the gate is RED

**Do not throw the work away, and do not halt.** Attribute it first:

```bash
python scripts/gate_attribution.py
```

- **`ATTRIBUTION=BASELINE_RED`** (no new failures — everything already failed before you
  started): commit the work normally, tick the task, and emit
  `AUTO_STATUS: TASK_COMPLETE_BASELINE_RED`.

- **`ATTRIBUTION=NEW_FAILURES`**: confirm before accepting the blame — one flake must not
  cost the phase:

  ```bash
  python scripts/gate_attribution.py | grep '^NEW_FAILURE ' | cut -d' ' -f2 \
    | python scripts/gate_confirm.py
  ```

  - `CONFIRM=FLAKE` → it did not reproduce. Commit normally, emit `AUTO_STATUS: TASK_COMPLETE`.
  - `CONFIRM=CONFIRMED` → a real regression you introduced. **Still commit** — visible debt
    beats lost work — but tick it as unverified so the morning sees it:

    ```bash
    python scripts/roadmap_cursor.py --mark <TASK> --date $(date +%Y-%m-%d) \
      --unverified "confirmed regression: <node ids>"
    git add -A && git commit -m "<type>(<scope>): <description> [UNVERIFIED: regression]"
    ```

    Then emit `AUTO_STATUS: TASK_COMMITTED_REGRESSION`.

**Never** make a red test green by editing the test, adding `# noqa`, `# type: ignore`,
`@pytest.mark.skip`, or lowering `--cov-fail-under`. That is fraud, `scan_fix_diff.py`
detects it, and it wastes the night it was meant to save.

## 5. Finish

Your final line is the bare token. Nothing after it.

Before you emit it, confirm: **is the working tree clean?** (`git status --porcelain`
prints nothing.) If not, you have not finished step 4 — go back and commit.
