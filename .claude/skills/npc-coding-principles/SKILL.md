---
name: npc-coding-principles
description: NPC Engine SOLID, structure, typing, error-handling, DI, async, observability, prompt-hygiene and security rules. Load before adding an engine, an adapter, an LLM call, or anything crossing a module boundary.
---

# NPC Engine — coding principles

Binding (DEC-249). `project-harness/CLAUDE.md` names each rule in one line and points here.
Rules marked **(strict)** have the same status as the layer rules: violating them is a bug.

These rules supplement the layer model and code-style sections above. Rules marked
**(strict)** have the same status as the layer rules: violating them is a bug.

### SOLID

- **SRP** (strict): every module belongs to exactly one category — data model, reader,
  writer, handler/orchestrator, utility, protocol, adapter, or test. Never mix.
- **OCP** (strict): new LLM backends, distortion types, or emotion models are added by
  creating a new file. Never edit existing engine files to add a new variant.
- **DIP** (strict, scoped 2026-09-02): a dependency is abstracted behind a protocol when it
  has **2+ implementors or 3+ callers**. Below that, inject the concrete class — a protocol
  with one implementor and one caller is indirection, not inversion. Where the threshold is
  met, engines import the protocol (e.g. `LLMClientProtocol`), never a concrete adapter.
  Concrete dependencies are injected via `__init__` either way; `api/dependencies.py` is
  the sole composition root for the API layer.
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
  Include whichever of `npc_id`, `player_id` and `tick` the call site actually has.
  `duration_ms` on engine log entries is the part that is **gated**, by
  `make check-engine-logs` against `scripts/engine_logs_baseline.txt` — a ratchet, so the
  count of non-compliant sites can shrink but never grow. The former blanket mandate to
  include all four fields everywhere was deleted on 2026-09-02: measured across ~76 engine
  logger call sites, **zero** carried all four, so it was describing no code. Follow the
  gate, not the aspiration (DEC-249).
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
