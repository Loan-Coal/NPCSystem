# NPC Engine — Working Rules

This file is read at the start of every Claude Code session. These rules are not
suggestions. Violating them is a bug.

---

## Orientation

**What is this:** NPC Engine is a game backend that gives NPCs persistent memory,
relationships, and emotional state via a Neo4j knowledge graph and LLM dialogue.
Exposes HTTP + WebSocket API for licensing to game studios as middleware.

**Current phase:** Hackathon prep — June 6, 2026. See `ROADMAP.md`.

### Stack

| Component | Technology |
|-----------|-----------|
| API server | FastAPI + Uvicorn |
| Knowledge graph | Neo4j 5 (Docker) |
| LLM | Ollama (`qwen2.5:14b`) or OpenAI GPT-4o |
| Demo UI | pygame-ce (Python 3.14 — **not** `pygame`) |
| Tests | pytest |

### Key commands

```bash
docker-compose up -d          # start backend
make demo-seed                # seed world (idempotent)
make demo                     # interactive pygame window
make demo-run                 # scripted demo scenario (live)
make demo-run ARGS=--dry-run  # print scene sequence only
make demo-run ARGS=--cached   # playback from cache (for recording)
make test                     # engine unit tests
make test-demo                # demo_game tests only
make eval-llm-demo            # LLM judge evals (requires Ollama)
```

### Key file locations

| Path | What it is |
|------|-----------|
| `demo_game/` | Pygame demo app (zero imports from `src/`) |
| `demo_game/run.py` | Scripted scenario runner (`make demo-run`) |
| `demo_game/client.py` | `EngineClient` — REST API wrapper |
| `demo_game/seed.py` | World seeder (5 NPCs, 3 locations, 3 factions) |
| `prompts/` | All LLM prompt YAML files (no prompt strings in Python) |
| `src/npc_engine/engines/` | Domain engines (dialogue, gossip, emotion, quest) |
| `docs/DEMO_SCRIPT.md` | Scripted 5-minute demo scenario |
| `ROADMAP.md` | Two-week hackathon plan |

### Demo world (seed data)

| NPC | Location | Notable |
|-----|----------|---------|
| `mira_innkeeper` | `tavern` | Central gossip hub |
| `aldric_merchant` | `market_square` | Trade gossip |
| `captain_sorn` | `guard_barracks` | Direct `KNOWS_ABOUT northern_war_begins` |
| `lira_fence` | `tavern` | Thieves guild |
| `old_henryk` | `market_square` | 2-hop distorted gossip target |

Gossip demo path: `captain_sorn` → `mira_innkeeper` → `old_henryk`.
World state node ID: `ws_main`. NPC IDs are stable — do not rename them.

---

## Architecture

### Layer model

Services belong to exactly one layer. Dependencies point downward only.

```
api/         → HTTP routes, request/response models, auth middleware
engines/     → domain logic, LLM orchestration, tick schedulers
services/    → shared domain operations (mutation bounds, context assembly)
retrieval/   → graph reader, vector store, context builder
graph/       → Neo4j write operations, schema enforcement
config/      → settings, environment, schema loader
```

Allowed dependencies:

- `api`       → engines, services, retrieval, graph, config
- `engines`   → services, retrieval, graph, config
- `services`  → retrieval, graph, config
- `retrieval` → graph, config
- `graph`     → config
- `config`    → nothing

### Forbidden cross-layer patterns

- No LLM calls in `graph/` or `retrieval/`. LLM lives in `engines/` only.
- No Neo4j queries outside `graph/`. Engines call services or retrieval.
- No prompt strings outside `prompts/`. Anything passed to an LLM lives in
  versioned YAML in `prompts/`.
- No HTTP calls between services. Services compose in-process.

If you need to violate a layer rule, stop and write a `DECISIONS.md` entry
proposing the change. Wait for human approval.

## Code style

### Files

- Hard limit: **300 lines of non-test code per file.** If you exceed this, split
  before merging. If a split would be artificial, write a justifying comment at
  the top of the file and add an entry to `DECISIONS.md`.
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

## Documentation

Documentation is mandatory. The `__init__.py` debugging incident happened because
this rule was implicit. It is explicit now.

### Every Python file requires:

1. **Module docstring** at the top, in this format:

```python
"""
Module: <name>
Layer: <api | engines | services | retrieval | graph | config>
Purpose: One sentence describing what this module does.
Dependencies: Which other modules this imports from.
Used by: Which other modules import from this.
"""
```

2. **Function docstrings** on every public function (one-line is acceptable for
   simple functions; multi-line for anything with non-obvious behavior). Format:

```python
def my_function(arg: str) -> int:
    """One-line summary.

    Args:
        arg: Description.
    Returns:
        Description.
    Raises:
        SomeError: When this happens.
    """
```

3. **Class docstrings** on every class.

### `__init__.py` files

These count as files. They get a docstring too, even if they are empty re-exports.
Format:

```python
"""
Package: <name>
Layer: <layer>
Purpose: One sentence describing what this package contains.
Public surface: List the names re-exported from this package.
"""
```

### What does NOT need documentation

- Private functions (leading underscore) with self-evident names. Leading-underscore
  functions are allowed to skip the docstring if and only if the function is shorter
  than 10 lines and the name is self-explanatory.
- Test functions (the test name is the documentation).
- Trivial property getters/setters.

If you are unsure whether a function needs a docstring, write one. The cost of a
one-line docstring is far less than the cost of forgetting one.

## Testing

### TDD discipline

For new code:
1. Write the failing test.
2. Confirm it fails for the right reason (not import error, not typo).
3. Write the minimum code to pass.
4. Refactor with tests green.

Bug fixes:
1. Write a regression test that reproduces the bug.
2. Confirm it fails.
3. Fix the bug.
4. Confirm the test passes.

### Test layout

```
tests/
  unit/test_<module>.py
  integration/test_<module>.py
  contract/
  conftest.py        (at repo root)

e2e/
  scenarios/
  scripts/
  transcripts/       (gitignored)
```

- Unit tests: no I/O, no DB, no network. Mock all infrastructure.
- Integration tests: may use test DB, test LLM mock, test vector store. No real
  external services.
- E2E tests: spin up the full stack via Docker Compose. Run as scenarios.

### Test requirements per module

- Every public function has at least one happy-path test and one failure test.
- Functions touching Neo4j have integration tests against a real test DB, not mocks.
- Functions calling an LLM have unit tests with the mock adapter.
- Deterministic functions with >2 input parameters have property tests.

## Issues log

The file `ISSUES.md` is the persistent issue log. Every session reads it.
Every session updates it.

### When you find a problem you are NOT fixing now

Add an entry to `ISSUES.md`. Format:

```markdown
## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 (blocking) | P2 (annoying) | P3 (nice-to-fix)
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.
```

ID is monotonic across the file. Never reuse IDs. Never delete entries — when an
issue is fixed, change the heading to `## [FIXED] ISSUE-NNN: <title>` and add a
`**Fixed:** YYYY-MM-DD, in <commit/task>` line.

### When you fix an issue

If a current task fixes an existing logged issue, update the issue's status before
closing the task.

### When NOT to log an issue

- Do not log an issue you are about to fix in the current task.
- Do not log an issue that is the current task itself.
- Do not log questions ("how should we do X?") — those go in `DECISIONS.md` or
  `SKILLS_QUEUE.md`.

## Task discipline

### Single-task focus

When you are working on task X, you do not also do task Y. If you notice Y while
doing X, log Y in `ISSUES.md` and continue X. The exception is when Y is
*blocking* X (you literally cannot finish X without fixing Y).

### Pre-merge checklist

Before declaring a task done, run this checklist mentally and write the result
into your final summary message:

- [ ] All new tests pass
- [ ] All existing tests still pass
- [ ] No file exceeds 300 lines of non-test code
- [ ] Every new file has a module docstring
- [ ] Every new public function has a docstring
- [ ] Every new public class has a docstring
- [ ] No prompt strings introduced outside `prompts/`
- [ ] No layer rule violations
- [ ] Any deferred work is in `ISSUES.md`
- [ ] Any non-obvious choice is in `DECISIONS.md`
- [ ] Any new pattern reused twice is in `PATTERNS.md`
- [ ] Bridge/temporary files from this task are deleted, not orphaned
- [ ] `STATUS.md` (or task tracking file) is updated

If any item is not satisfied, the task is not done.

### Bridge and temporary files

If you create a temporary file during a task (a bridge, a stub, a backup), do
**both** of these immediately when creating it:

1. Add a comment at the top of the file: `# TEMPORARY: delete by end of task <name>. Reason: <why>.`
2. Log it in `ISSUES.md` with the deletion deadline.

When closing the task, delete the temporary file and mark the issue fixed. Do not
leave temporary files for future-you to clean up. Future-you will not.

## Asking before doing

You may proceed without asking on:
- Bug fixes inside a single module
- Adding tests
- Adding documentation
- Adding entries to ISSUES, DECISIONS, PATTERNS

You must stop and ask before:
- Changing a public interface that has callers outside its module
- Adding a new dependency
- Changing the schema of a graph node or edge
- Touching CI configuration
- Deleting a file that is not a temporary file you yourself created
- Violating any layer rule

## Token efficiency

- Do not paraphrase the codebase back to the user.
- Do not summarize what you are about to do at length. Act, then summarize in one line.
- One precise sentence beats three vague ones.
- If you are unsure about a small thing, make a choice and note it in `DECISIONS.md`.
  Stop only for blocking or irreversible matters.
