---
description: Bounded, unattended repair of ONE auto-fixable (form-class) gate failure — lint, types, docstrings, layers, structural rules. Never touches tests or behaviour.
---

# /fix-make-failure

You are running **unattended**, invoked by `scripts/expand_loop.sh` as
`claude -p "/fix-make-failure --auto --check <CHECK>"`, after a phase gate went red.

You get **one** attempt. Your diff is then scanned by `scripts/scan_fix_diff.py`, the full
gate is re-run, and if either says no, your work is reverted entirely.

---

## What you are allowed to be looking at

The loop already ran every **behaviour** check before invoking you, and they were all
green. So `<CHECK>` is a **form** failure — one of:

`lint` · `type` · `check-rules` · `check-layers` · `check-docstrings` · `check-harness`

These assert *shape*, not behaviour, and have mechanical, verifiable fixes.

## Hard prohibitions

**You must not change behaviour, and you must not touch any of these files:**

- anything under `tests/`, `demo_game/tests/`, `e2e/`, `.github/`
- `Makefile`, `pyproject.toml`, `mypy.ini`, `conftest.py`
- **`scripts/rules_baseline.txt`** — and never run `make check-rules-update`. That target
  legitimately rewrites the violation baseline, so using it here would launder every new
  violation into "expected" and turn the gate green having fixed nothing. This is the
  single most tempting way to fake success on this repo. Do not.
- any `scripts/check_*.py`, `scripts/gate_*.py`, `scripts/loop_*`, `scripts/*cursor*`

**And you must not suppress a check instead of satisfying it.** Silencing directives
(lint/type suppression comments, swallowed or bare excepts, skip/xfail markers, runtime
skips, a lowered coverage floor, blanket mypy relaxations, new per-file ignores) are all
detected by the scanner. A detected diff is reverted whole and flagged for a human, so
adding one does not even buy you a green run — it just wastes the attempt.

## Procedure

1. **Reproduce.** Run the single failing check in the **foreground** and read the output:

   ```bash
   make <CHECK>
   ```

   Never background it. A headless turn ends the moment it stops calling tools, and your
   work dies uncommitted with it.

2. **Fix the cause, minimally.** Real fixes only:
   - `lint` → apply what ruff asks for: unused imports, ordering, formatting.
   - `type` → add or correct annotations; narrow with proper guards, never `Any`.
   - `check-docstrings` → write the missing module/class/function docstring, in the
     `Module / Layer / Purpose / Dependencies / Used by` format `CLAUDE.md` specifies.
   - `check-layers` → move the offending import, or the code, to the correct layer. If the
     only honest fix is a layer-rule change, **stop** (see step 4).
   - `check-rules` → split a file over 300 lines, a function over 40, nesting over 3;
     name a magic value. Fix the violation; never re-baseline it.

3. **Re-gate in the foreground.**

   ```bash
   make check
   ```

4. **Know when to give up.** If the honest fix needs a decision — a layer-rule change, a
   new dependency, a public-interface change, a schema change — **make no edits at all**.
   Leave the tree exactly as you found it and say in one line what the blocker is. The loop
   flags it for the morning. A clean give-up is a good outcome; a fake green is not.

## Output

Do **not** commit. The loop scans, re-gates, and commits your repair separately so it can
be reviewed on its own.

End with one short line: what you changed and why, or why you changed nothing.
