# NPC Engine — Working Rules

This file is auto-loaded via the root `CLAUDE.md` @-import. These rules are not
suggestions. Violating them is a bug.

**This file names every binding rule. It does not restate them.** The detail lives in
four skills; each rule below says which one. See "Skills" at the end for what happens
when a skill does not load.

**This file states no facts it does not own.** Commands, paths, layer lists and seed data
are pointers to the file holding the truth, because a copy here is a copy that rots
(DEC-249). If you need the value, open the pointer.

---

## Orientation

**What is this:** a game backend giving NPCs persistent memory, relationships and
emotional state via a Neo4j knowledge graph and LLM dialogue. HTTP + WebSocket API,
licensed to game studios as middleware.

| For | Read |
|---|---|
| Current phase and next task | `project-harness/ROADMAP.md` |
| Every `make` target, with its comment | `Makefile` (`make help`) |
| Open issues | `project-harness/ISSUES.md`; fixed ones in `project-harness/archive/ISSUES_RESOLVED.md` |
| Architecture decisions | `project-harness/DECISIONS.md` |
| Reusable patterns | `project-harness/PATTERNS.md` |
| Repo layout, stack, and where things live | `docs/overview.md` |
| Demo world seed data (NPC ids, locations, gossip path) | `demo_game/seeds/seed.py` |
| Scripted demo scenario | `docs/DEMO_SCRIPT.md` |
| Runtime LLM prompts | `src/npc_engine/prompts/` |
| Eval-judge prompts | `prompts/eval/` (repo **root**, not under `src/`) |

NPC ids in the seed are stable — do not rename them.

### The one fact this file owns

| Stack | Value |
|---|---|
| LLM | Ollama (`qwen2.5:7b`); pluggable via `LLMClientProtocol` + factory registry |

This row is **not** a pointer, and is the deliberate exception to the rule above, because it
is **gated**: `tests/unit/evals/test_model_identity.py` fails when it disagrees with any
engine's `llm_config.yaml`. A copy that a test pins cannot drift silently, which is what makes
copies dangerous. Change it and the configs together, or the gate reds (EVAL-P0.1, DEC-249).

---

## Architecture

The layer model is the one rule this file states in full, because it is the one an agent
must not have to look up.

Services belong to exactly one layer. **Dependencies point downward only.**

```
api/         → HTTP routes, request/response models, auth middleware
auth/        → API-key authentication middleware  [api peer, rank 6]
data/        → admin endpoint schemas + seeders   [api peer, rank 6]
engines/     → domain logic, LLM orchestration, tick schedulers
scheduler/   → tick scheduler loop               [engines peer, rank 5]
services/    → shared domain operations (mutation bounds, context assembly)
cache/       → in-process dialogue context cache  [services peer, rank 4]
retrieval/   → graph reader, vector store, context builder
graph/       → Neo4j write operations, schema enforcement
mutation/    → relation delta validation + logging [graph peer, rank 2]
world/       → world-state data model + time utils [graph peer, rank 2]
config/      → settings, environment, schema loader
common/      → zero-dep shared utilities           [config peer, rank 1]
type_registry/ → node/edge type contract system   [config peer, rank 1]
schema/      → game schema loader                  [config peer, rank 1]
utils/       → error hierarchy + structured logging [config peer, rank 1]
observability/ → monitoring artefacts (Prometheus rules, Grafana dashboard) [config peer, rank 1]
setup/         → first-run bootstrap utilities           [config peer, rank 1]
```

A layer may import from any layer of **lower** rank, never higher, never sideways except
to a declared peer. The authoritative, machine-readable edge list is in
`scripts/check_layers.py`; `make check-layers` enforces it.

### Forbidden cross-layer patterns

- No LLM calls in `graph/` or `retrieval/`. LLM lives in `engines/` only.
- No Neo4j queries outside `graph/`. Engines call services or retrieval.
- No prompt strings outside `prompts/`. Anything passed to an LLM lives in versioned YAML.
- No HTTP calls between services. Services compose in-process.

If you need to violate a layer rule, stop and write a `DECISIONS.md` entry proposing the
change. Wait for human approval.

---

## The strict rules

Each line is binding. The skill named after it holds the detail and the rationale.

**Code style** → `npc-code-style`
- Two-tier file size: 400 lines advisory, **800 hard and unwaivable**; a file on the R001
  baseline may not grow past its recorded count (DEC-226).
- No function or method over **40 lines**. Control-flow nesting no deeper than **3**.
- `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE` constants.
- Type annotations on every public parameter, return and class attribute.
- `from __future__ import annotations` at the top of every module.
- Imports grouped stdlib / third-party / first-party. No wildcards, no `from ..x import y`.

**Documentation** → `npc-documentation`
- Module docstring on every file, including `__init__.py`, in the prescribed format.
- Docstring on every public function and every class.
- Private functions may skip it only when under 10 lines with a self-evident name.

**Testing** → `npc-testing`
- New code: failing test first, confirmed failing for the right reason, then the code.
- Bug fixes: a regression test that reproduces the bug, confirmed failing, then the fix.
- Unit tests do no I/O. Neo4j-touching code gets integration tests against a real test DB.
- Every public function gets a happy-path test and a failure test.

**Coding principles** → `npc-coding-principles`
- **SRP**: one module, one category — model, reader, writer, orchestrator, utility,
  protocol, adapter, or test. Never mixed.
- **OCP**: new backends, distortion types and emotion models arrive as new files.
- **DIP**: abstract behind a protocol at **2+ implementors or 3+ callers**; below that,
  inject the concrete class. Constructor injection only.
- **ISP**/**LSP**: small protocols; mocks must match the real behaviour contract.
- Pydantic v2 for everything crossing a module boundary. No raw `dict`, no raw strings
  for fixed value sets — `Literal` or `Enum`.
- Typed exceptions from `utils/errors.py`. Never `raise Exception(...)`, never swallow.
- Validate at system boundaries only; internal invariants are covered by types.
- Async all the way for I/O. Bounded `gather`. Locks on shared mutable state.
- Structured logging via `utils/logging.py`. Never `print()`.
- Prompt token budget enforced; structured LLM output validated through Pydantic;
  `build_prompt` is a pure function of its inputs.
- Input caps at the API boundary. Auth on every route except `GET /health`.

**Programme rules (T programme)** — nine rules bound by the 2026-09-07 review. Each names its gate, or says it has none. A green `make check` says nothing about ungated rules; they are enforced by review only (DEC-249).
- **Rule 1 — Reverse LOC ratchet.** Non-test LOC across `src/npc_engine/`, `scripts/`, `evals/` and `demo_game/` may only go down in total. Raising the baseline requires an explicit bump with a stated reason. **Gate: `make check-loc-ratchet`** (T10.2b).
- **Rule 2 — Delete before you abstract.** If a fix can be "add an abstraction" or "remove the feature", remove the feature. Record the removal in `DECISIONS.md` if it was ever documented. **No gate — enforced by review.**
- **Rule 3 — No config, prompt or contract without a live reader.** Every `Settings` field, prompt YAML and contract YAML needs a reader outside its own module and its own tests. Dead public functions are covered by review, not the gate. **Gate: `make check-dead-surface`** (T10.2a).
- **Rule 4 — Abstraction requires two.** A Protocol needs 2+ implementors or 3+ callers. Below that, inject the concrete class. **Gate: `make check-dip-threshold`** (T10.1).
- **Rule 5 — A test must be able to fail.** No existence-only assertions (`hasattr`, `iscoroutinefunction`), no asserting a constant equals its own literal. **No gate on this tree** — gated from T12.1 when it lands.
- **Rule 6 — Config must be read.** Part of rule 3; declared settings with no reader outside the module are a build failure. **Gate: `make check-dead-surface`** (T10.2a).
- **Rule 7 — One path per concept.** Never two implementations of one domain concept. Pick one; delete the other. **No gate — enforced by review.**
- **Rule 8 — Prefer deterministic over model.** A model call is a budget item, not a default. `engines/gossip/` is the in-repo precedent. **No gate — enforced by review.**
- **Rule 9 — Net-negative phases.** The same four-directory non-test count that rule 1 ratchets must decrease each phase. A phase adding to `tests/` states the delta but is not blocked by it. **No gate — enforced by review.**

---

## Project management

`project-harness/ISSUES.md`, `DECISIONS.md` and `ROADMAP.md` are the **only** copies of
these files. Never create root-level copies. If you find one, delete it and consolidate.

### Issues

Log an issue for a problem you find and are **not** fixing now:

```markdown
## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 (blocking) | P2 (annoying) | P3 (nice-to-fix)
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.
```

Ids are monotonic and never reused. Check **both** `ISSUES.md` and
`archive/ISSUES_RESOLVED.md` when picking the next one — `make check-ledger-ids` enforces it.

When you fix a logged issue: mark the heading `## [FIXED] ISSUE-NNN:`, add
`**Fixed:** YYYY-MM-DD, in <commit/task>`, then move the entry verbatim into
`project-harness/archive/ISSUES_RESOLVED.md`. `ISSUES.md` holds open issues only (DEC-130).

Do **not** log: an issue you are about to fix in this task, or the task itself. Open
questions go in `DECISIONS.md`.

### Single-task focus

Working on X, you do not also do Y. Notice Y, log Y, continue X. The only exception is Y
blocking X — you literally cannot finish X without it.

### Temporary files

On creating one: put `# TEMPORARY: delete by end of task <name>. Reason: <why>.` at the
top **and** log it in `ISSUES.md` with a deletion deadline. Delete it before closing the
task. Future-you will not.

### Pre-merge checklist

Run this mentally and write the result into your final summary:

- [ ] New tests pass; existing tests still pass
- [ ] No file over 800 lines of non-test code, and no grandfathered file grew
- [ ] Every new file, public function and public class has a docstring
- [ ] No prompt strings outside `prompts/`
- [ ] No layer rule violations
- [ ] Deferred work is in `ISSUES.md`; non-obvious choices are in `DECISIONS.md`
- [ ] A pattern reused twice is in `PATTERNS.md`
- [ ] Temporary files from this task are deleted, not orphaned

If any item is unsatisfied, the task is not done.

---

## Asking before doing

Proceed without asking on: bug fixes inside one module, adding tests, adding
documentation, adding ISSUES/DECISIONS/PATTERNS entries.

**Stop and ask before:**
- Changing a public interface that has callers outside its module
- Adding a new dependency
- Changing the schema of a graph node or edge
- Touching CI configuration
- Deleting a file that is not a temporary file you created
- Violating any layer rule

---

## Token efficiency

- Do not paraphrase the codebase back to the user.
- Act, then summarise in one line. Do not narrate the plan at length first.
- One precise sentence beats three vague ones.
- Unsure about something small: choose, and note it in `DECISIONS.md`. Stop only for
  blocking or irreversible matters.

---

## Skills

The four skills named above live in `.claude/skills/`. They are **invoked, not
auto-loaded** — unlike this file, which is always in context.

**That is the failure mode: if a skill does not load, the rule it holds silently stops
being enforced by the agent.** Nothing announces it. This is why every strict rule is
named in "The strict rules" above, so this file alone still tells you the rule exists and
what it requires, even when no skill loads. The skill adds the detail, the format and the
rationale — never the existence of the obligation.

The load-bearing backstop is not the skill and not this file: it is `make check`. A rule
with a gate survives an unloaded skill. A rule without one depends on the agent reading
this list. Prefer adding a gate over adding prose (DEC-249).
