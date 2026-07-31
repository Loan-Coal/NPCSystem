# NPC Engine — Working Rules

This file is auto-loaded via the root `CLAUDE.md` @-import. These rules are not
suggestions. Violating them is a bug.

---

## Orientation

**What is this:** NPC Engine is a game backend that gives NPCs persistent memory,
relationships, and emotional state via a Neo4j knowledge graph and LLM dialogue.
Exposes HTTP + WebSocket API for licensing to game studios as middleware.

**Current phase:** Post-hackathon engine development. See `ROADMAP.md`.

### Stack

| Component | Technology |
|-----------|-----------|
| API server | FastAPI + Uvicorn |
| Knowledge graph | Neo4j 5 (Docker) |
| LLM | Ollama (`qwen2.5:7b`); pluggable via `LLMClientProtocol` + factory registry (add a local or API backend by registering an adapter — no OpenAI adapter ships today) |
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
make demo-village             # village crisis demo (seed-village-world first)
make demo-tavern              # tavern intrigue demo (seed-tavern-world first)
make seed-village-world       # seed village eval world only (idempotent)
make seed-tavern-world        # seed tavern eval world only (idempotent)
make eval-report              # generate eval summary report
make demo-snapshot            # snapshot current demo state to cache
```

### Key file locations

| Path | What it is |
|------|-----------|
| `demo_game/` | Pygame demo app (zero imports from `src/`) |
| `demo_game/runners/run.py` | Scripted scenario runner (`make demo-run`) |
| `demo_game/client.py` | `EngineClient` — REST API wrapper |
| `demo_game/seeds/seed.py` | Demo world seeder (5 NPCs, 3 locations, 3 factions) |
| `seeds/worlds/seed_village_world.py` | Village eval world (vw_ prefix) |
| `seeds/worlds/seed_tavern_world.py` | Tavern eval world (tw_ prefix) |
| `src/npc_engine/prompts/` | All runtime LLM prompt YAML files (no prompt strings in Python). Eval-judge prompts live under `src/npc_engine/prompts/eval/`. |
| `src/npc_engine/engines/` | Domain engines (dialogue, gossip, emotion, quest) |
| `docs/DEMO_SCRIPT.md` | Scripted 5-minute demo scenario |
| `project-harness/ROADMAP.md` | Two-week hackathon plan |
| `project-harness/ISSUES.md` | Persistent issue log (canonical) |
| `project-harness/DECISIONS.md` | Architecture decisions log (canonical) |

### Demo world (seed data)

| NPC | Location | Notable |
|-----|----------|---------|
| `mira_innkeeper` | `tavern` | Central gossip hub |
| `aldric_merchant` | `market_square` | Trade gossip |
| `captain_sorn` | `guard_barracks` | Direct `KNOWS_ABOUT northern_war_begins` |
| `lira_fence` | `tavern` | Thieves guild |
| `old_henryk` | `market_square` | 2-hop distorted gossip target |

Gossip demo path: `captain_sorn` → `mira_innkeeper` → `old_henryk`.
World state node ID: `world`. NPC IDs are stable — do not rename them.

---

## Architecture

### Layer model

Services belong to exactly one layer. Dependencies point downward only.

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
```

Allowed dependencies (enforced by `make check-layers`):

- `api/auth/data` → engines, scheduler, services, cache, retrieval, graph, mutation, world, config, common, type_registry, schema, utils
- `engines/scheduler` → services, cache, retrieval, graph, mutation, world, config, common, type_registry, schema, utils
- `services/cache` → retrieval, graph, mutation, world, config, common, type_registry, schema, utils
- `retrieval`  → graph, mutation, world, config, common, type_registry, schema, utils
- `graph/mutation/world` → config, common, type_registry, schema, utils
- `config/common/type_registry/schema/utils` → nothing

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

## Project management files — canonical locations

`project-harness/ISSUES.md`, `project-harness/DECISIONS.md`, and `project-harness/ROADMAP.md`
are the only copies of these files. Never create or update root-level copies.
If you find a root-level copy, delete it and consolidate into the project-harness version.

## Issues log

The file `project-harness/ISSUES.md` is the persistent issue log. Every session reads it.
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

ID is monotonic and never reused. Check **both** `ISSUES.md` and
`archive/ISSUES_RESOLVED.md` when picking the next id — fixed entries live in the
archive, so IDs there are still taken. Never delete entries — when an issue is fixed,
change the heading to `## [FIXED] ISSUE-NNN: <title>`, add a
`**Fixed:** YYYY-MM-DD, in <commit/task>` line, then move the entry (see below).

### When you fix an issue

If a current task fixes an existing logged issue:
1. Mark it `[FIXED]` and add the `**Fixed:** YYYY-MM-DD, in <commit/task>` line.
2. Move the entry out of `ISSUES.md` into `project-harness/archive/ISSUES_RESOLVED.md`
   (single append-only archive; preserve the entry's IDs and content verbatim).
   This keeps `ISSUES.md` to open issues only, so the start-of-session read stays lean.

Do this before closing the task. Rationale: DEC-130.

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

---

## Coding principles

These rules supplement the layer model and code-style sections above. Rules marked
**(strict)** have the same status as the layer rules: violating them is a bug.

### SOLID

- **SRP** (strict): every module belongs to exactly one category — data model, reader,
  writer, handler/orchestrator, utility, protocol, adapter, or test. Never mix.
- **OCP** (strict): new LLM backends, distortion types, or emotion models are added by
  creating a new file. Never edit existing engine files to add a new variant.
- **DIP** (strict): engines import `LLMClientProtocol`, never `MistralAdapter` or any
  other concrete class. All concrete dependencies are injected via `__init__`.
  `api/dependencies.py` is the sole composition root for the API layer.
- **ISP** (strict): protocols must be small. If not all implementors need a method,
  split the protocol. Do not add streaming to a protocol if some adapters cannot stream.
- **LSP** (strict): mock adapters must match the real adapter's behavior contract.
  If `MockLLMClient.generate()` returns `""` for empty input but real adapters raise,
  that mock is invalid and will produce false-passing tests.

### Structure

- **Function length** (strict): no function or method may exceed 40 lines.
- **Nesting** (strict): control-flow nesting (`if`/`for`/`try`) must not exceed 3 levels.
  Extract inner blocks into named helpers.
- **No magic numbers or strings** (strict): every constant must be named
  (`ALL_CAPS` module-level or `config.py` key). No raw numeric thresholds like `if trust > 50`.
  No raw string literals for node labels, relationship types, or Cypher query fragments.

### Types and models

- **Pydantic v2 for all data** (strict): all data crossing module boundaries
  (API schemas, graph nodes, engine inputs/outputs, config) must be a Pydantic v2
  `BaseModel` or `BaseSettings`. No raw `dict` crossing a module boundary.
- **Enums/Literal for fixed sets** (strict): any field with a fixed value set must use
  `Literal[...]` or `enum.Enum`. No raw strings for action types, knowledge states, etc.
- **Protocols over ABCs** (guideline): prefer `typing.Protocol` for interfaces.

### Error handling

- **Fail fast at boundaries** (strict): validate all external inputs (API requests,
  LLM responses, Neo4j results, file reads) immediately on receipt.
- **Custom exception hierarchy** (strict): all domain errors are typed exceptions in
  `utils/errors.py` with structured fields. Never `raise Exception("message")`.
  Examples: `GraphUnavailableError(uri=..., cause=...)`, `LLMTimeoutError(model=..., timeout_s=...)`.
- **Never swallow errors** (strict): every `except` block must re-raise, raise a domain
  error, or log-and-re-raise. No `except: pass` or `except Exception: pass`.
- **Engine boundary fallback contracts** (strict): LLM timeout → serve
  `fallback_responses.json`; Neo4j unavailable → raise `GraphUnavailableError` → API 503.
  Document the fallback in the function docstring.
- **No try/except around internal invariants** (strict): only validate at system
  boundaries. Internal calls to functions you control are covered by type hints and Pydantic.

### Dependency injection

- **Constructor injection only** (strict): all dependencies (DB session, LLM client,
  embedding index, config) are injected via `__init__`. No module-level instantiation
  of stateful objects inside engines or handlers.
  Exception: `config.py` `Settings` may be a module-level singleton via `get_config()`.
- **Session ownership** (strict): graph sub-writers receive `AsyncSession` as a
  parameter and run their writes through `transaction_coordinator.run_in_tx`
  (an inner `_work(tx)` closure). `transaction_coordinator.py` is the only file
  that calls `begin_transaction()` / `commit()`; `graph_writer.py` and every
  sub-writer delegate to it (DEC-119/SEV-21). No file outside the coordinator
  opens a transaction; no engine holds an `AsyncTransaction`.

### Async

- **Async all the way** (strict): all I/O (Neo4j, LLM HTTP, embedding) must be `async def`/`await`.
  Never block in an async context. Use `asyncio.gather()` for independent parallel ops.
- **Semaphore for batch** (strict): `asyncio.gather()` calls that could spawn unbounded
  coroutines must be capped with `asyncio.Semaphore(config.MAX_CONCURRENT_TICKS)`.
- **Lock for shared state** (strict): `emotion_store` and `session_store` mutations must
  be wrapped in `asyncio.Lock()`. Document the lock in the class docstring.

### Observability

- **Structured logging** (strict): use `utils/logging.py`. Never `print()`.
  Log as key-value pairs: `logger.info("event", npc_id=..., tick=..., duration_ms=...)`.
  Include `npc_id`, `player_id`, `tick`, and `duration_ms` in all engine log entries.
- **LLM prompt redaction** (strict): log prompts/responses only when
  `config.LOG_LLM_PROMPTS is True AND config.ENV == "dev"`. In staging/prod log token
  counts and model name only.
- **RNG seed logging** (strict): log the seed used at the start of each tick for any
  gossip pair selection, event sampling, or distortion probability call.

### Prompt hygiene

- **Token budget enforced** (strict): `context_builder.py` raises `TokenBudgetExceededError`
  if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET`. Tier B (RAG) items are
  always optional — trim them first.
- **Structured output validated** (strict): all `generate_structured()` output passes
  through a Pydantic model in `response_parser.py` before any field is accessed.
- **Idempotent assembly** (strict): `prompt_builder.build_prompt()` is a pure function
  of its inputs. No timestamps, UUIDs, or randomness injected into prompt content.

### Security

- **Input caps at API boundary** (strict): `player_message` is capped at
  `config.MAX_PLAYER_MESSAGE_CHARS` (default 1000). `delta_ticks` in `/clock/advance`
  is bounded `[1, 1000]`. Never pass unconstrained user input to Neo4j or LLM.
- **Auth on all routes** (strict): every route except `GET /health` passes through
  `auth/middleware.py`. Return HTTP 401 with no body detail on failure.
