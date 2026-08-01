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

`make check` takes about 144 seconds on this repo. **Wait for it.** Do not background it.
Do not poll it. Do not say you will come back to it. Run it in the foreground and wait.

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

Never read the whole ROADMAP.md — it is 1183 lines and the slice is what keeps your
context small. Then read, in order:

1. The **task block for `<TASK>`** inside that slice. It carries `Files:`, a **`RED
   anchor:`** (the exact test that must fail first, and why) and a **`Validation:`** line.
   Those three are your specification — implement to them, not to your own idea of the task.
2. `project-harness/CLAUDE.md` — the hard rules. Load-bearing here: 300-line file limit,
   40-line function limit, 3-level nesting limit, no prompt strings outside
   `src/npc_engine/prompts/`, no raw `dict` across a module boundary (Pydantic v2 only),
   no magic numbers/strings, no layer violations, module + public-function docstrings.
3. `project-harness/DECISIONS.md` — only if the task block names a 🔶 decision.
4. The source files the task touches. **Never edit a file you have not read.**

## 2. Halt guards — check BEFORE writing anything

Emit the halt token and stop (no edits, clean tree) if any of these holds:

| Condition | Token |
|---|---|
| Task body carries `⚠️ ask-gate` | `AUTO_STATUS: HALT ask-gate <what needs deciding>` |
| Task is tagged `(live` — needs Neo4j/Ollama/seeded worlds | `AUTO_STATUS: HALT live-task` |
| Needs a 🔶 DECISIONS entry that is not ACCEPTED | `AUTO_STATUS: HALT needs-decision DEC-NNN` |
| Needs something that does not exist yet | `AUTO_STATUS: HALT blocked-prerequisite <what>` |
| Requires a layer violation, new dependency, graph schema change, or a public-interface change with callers outside the module | `AUTO_STATUS: HALT ask-gate <what>` |

These four halt reasons make the loop **skip the phase and keep working**, so they cost
nothing. Guessing at a human decision costs a lot. **When in doubt, halt.**

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

## 4. Gate — foreground, and wait

```bash
make check                 # ~144s. FOREGROUND. WAIT FOR IT.
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
