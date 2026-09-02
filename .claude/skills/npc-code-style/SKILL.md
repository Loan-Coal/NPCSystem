---
name: npc-code-style
description: NPC Engine file-size, naming, type-annotation and import rules. Load before adding or restructuring a Python module in src/, evals/ or demo_game/.
---

# NPC Engine — code style

Binding (DEC-249). `project-harness/CLAUDE.md` names each rule in one line and points here;
the detail lives in this file so the rules file stays readable. Gated by `make check-rules`.

### Files

- Two-tier size limit (DEC-226), enforced by `make check-rules`:
  - **400 lines** of non-test code — soft advisory. The gate reports it and does not
    fail. Treat it as the point at which you should be looking for the split.
  - **800 lines** — hard gate, unwaivable. No baseline entry can grandfather a file
    past it.
  - A file already on the R001 baseline records the line count it was grandfathered at.
    Growing beyond that recorded count is a new violation even below 800, so debt can
    shrink but never grow.
- If a split would be artificial, write a justifying comment at the top of the file
  and add an entry to `DECISIONS.md`.
- One class or one cohesive set of functions per module.
- Module-level docstring on every module (see `documentation` section below).

### Naming

- `snake_case` for files, modules, functions, variables.
- `PascalCase` for classes.
- `UPPER_SNAKE` for constants.
- No abbreviations except well-known ones (`id`, `db`, `npc`).
- Test files: `test_<module_name>.py`.

### Type annotations

- Every public function has type annotations on parameters and return value.
- Every public class attribute has a type annotation.
- Use `from __future__ import annotations` at the top of every module.
- Use `TYPE_CHECKING` blocks for import-cycle resolution.

### Imports

- Standard library, then third-party, then first-party. Blank line between groups.
- No wildcard imports.
- No relative imports beyond one level (`from .x import y` is fine; `from ..x import y` is not).
