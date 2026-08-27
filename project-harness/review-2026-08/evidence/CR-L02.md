# CR-L02 — Architecture (branch `eval-ab-context-arms`, HEAD `d46ae42`)

## Required measurements

### 1. Layer violations — seen vs. unseen by the import gate

```
$ make check-layers
.venv/Scripts/python.exe scripts/check_layers.py
check-layers: OK — no layer violations found.

$ make check-rules
.venv/Scripts/python.exe scripts/check_rules.py
check-rules: OK - no new violations (133 grandfathered).
```

| # | Category | Gate that should catch it | Count found | Confidence |
|---|---|---|---|---|
| a | Exception types crossing layers | none (import-graph only) | `neo4j.exceptions.Neo4jError` documented to cross graph→engines in 6 files / 11 mentions (`graph/character/player_model_writer.py:95,136`, `graph/intrigue/scheme_reader.py:166,198,232,279`, `graph/intrigue/scheme_writer.py:85,176`, `graph/relations/relation_phase_reader.py:66`, `graph/relations/relation_phase_writer.py:43`, `engines/relationship/phase_transition_applier.py:60`); traced end-to-end to a bare `except Exception` → HTTP 500 (see CR-L02-01) | Confirmed |
| b | Raw `dict` crossing a module boundary where Pydantic v2 is required | none (no such gate exists) | 145 public functions in `engines/`(67)+`graph/`(72)+`retrieval/`(6) return `-> dict[str, Any]`; includes `BaseEngine.run_tick` (`engines/base_engine.py:24`, 29 concrete implementations) and `LLMClientProtocol.generate_structured` (`engines/llm/protocols.py:73`) | Confirmed (AST-walked, script below) |
| c | Cypher / `session.run` outside `graph/` | `check-rules` R005 | 0 live instances found by manual grep of `api/`, `auth/`, `data/`, `cache/`, `mutation/` (dirs R005 does **not** scan — see CR-L02-04); 0 in the 5 dirs R005 does scan (baseline has 0 R005 entries) | Confirmed 0 today; gate coverage gap is Suspected risk |
| d | Wrong-layer runtime reach into Neo4j/LLM (not import-time) | none | Not found: `transaction_coordinator.py` is the only `begin_transaction()`/`.commit()` caller (see item 4); no engine imports a concrete LLM adapter outside `engines/llm/` (see item 2) | Confirmed |

AST script used for (b):
```python
# walks engines/graph/retrieval/services, ast.parse, counts public (non "_"-prefixed)
# FunctionDef/AsyncFunctionDef whose `returns` unparses to "dict[...]" or "dict"
```
Result: `{'engines': 67, 'graph': 72, 'retrieval': 6}`, `run_tick -> dict` count: 29.

### 2. DIP — engines importing concrete classes instead of protocols

| Scope | N violating | M total | Result |
|---|---|---|---|
| LLM backend only (CLAUDE.md's literal example: "engines import `LLMClientProtocol`, never `MistralAdapter`") | 0 | 7 engine files reference `LLMClientProtocol` | **Holds.** `grep -rln "OllamaAdapter\|OpenAICompatibleAdapter\|MockLLMAdapter" src/npc_engine/engines --include=*.py \| grep -v /engines/llm/` → empty. |
| Engine files importing anything from `graph.*` (broader interpretation; note the layer model explicitly permits `engines → graph`, so this is not itself a rule violation) | 13 | 219 engine .py files | Worst offenders: `engines/dialogue/session_store.py:170,201` (local imports of `write_session_turns`/`read_all_session_turns`, called directly, no port); `engines/dialogue/system_state_context.py:61-62` (same pattern for `get_items_for_character`/`get_active_quest_for_player`); `engines/ports/event_port.py:20` imports `_EventNode`, a `Protocol` **defined inside `graph/event/event_writer.py:20`** rather than owned by the port that consumes it — protocol ownership is on the wrong side of the boundary. The other 10 hits import DTOs (`RelationPhaseRow`, `SchemeRecord`, `IdempotencyRecord`, `ActiveSchemeProgress`) or are re-export shims (`engines/routine/routine_queries.py`, `engines/story_pacing/pacing_queries.py`, both self-documented as scheduled-for-removal back-compat forwarders). |

**"Sole composition root" claim:** false as stated. The composition root is 10 files, not 1: `api/dependencies.py`, `api/dependencies_infra.py`, `api/dependencies_stores.py`, `api/dependencies_advanced/{politics,progression,social}.py`, `api/dependencies_engines/{core,quest,tick_slots}.py`. All 43 importers of `api/dependencies.py` itself are confined to `api/` + `main.py` (`grep -rl "from npc_engine.api.dependencies import" src/npc_engine --include=*.py`), so the *direction* of composition is sound — but two stateful singletons are built entirely outside this file family (see CR-L02-03).

### 3. ROADMAP — do the 65 unchecked items require editing closed modules?

Full read of all 65 `- [ ]` lines in `project-harness/ROADMAP.md` (not sampled — 65 was small enough to do exhaustively), classified by the files each item names or the code it must touch:

| Class | Count | % | Meaning |
|---|---|---|---|
| (a) Pure addition — new file(s) only | 33 | 51% | Almost entirely `evals/`, `docs/`, `prompts/eval/`, `scripts/`, `Makefile`/`README` edits — the EVAL-P8..P31 eval-harness program (46 of the 65 items belong to this program alone) |
| (b) Requires editing an existing production file | 15 | 23% | See list below |
| (c) Requires a schema/graph-wide change | 2 | 3% | `EVAL-P29.1` (edits `src/npc_engine/config/llm_config.yaml` + `src/npc_engine/schema/context_config_models.py`); `OD-Ship-graph` (Kùzu migration touching all of `graph/`, 200 files) |
| (d) Unclear / human-only / no code (live runs, struck items, blocked-behind-gate) | 15 | 23% | e.g. `EVAL-P8.3`, `EVAL-P20.4`, `EVAL-P22.4`, `EVAL-03`/`EVAL-05` (struck) |

**(b) items, named:** `EVAL-P29.2` (edits `engines/dialogue/prompt_builder.py` **and** `engines/dialogue/dialogue_handler.py`, itself labelled "Pays down the existing constructor-injection violation" — confirmed: `prompt_builder.py:29-33` loads YAML at module import time, already logged as `ISSUE-223`); `EVAL-P30.2` (edits `engines/dialogue/dialogue_models.py`, flagged in the roadmap itself as "public interface change with callers outside its module — ask-gate per CLAUDE.md"); `PR-9` (refactors 39 files in `graph/repositories/`); `EVAL-01` (edits `dialogue_handler.py` + `context_builder.py`); `PERF-01/02/03/05/06/07` (all edit existing engine/retrieval/scheduler/config files — `PERF-02` names `context_builder.py:516-534` directly, confirmed to exist at `retrieval/context/context_builder.py`, though the current code at that range is `_build_event_trust_map`/`_drop_withheld_items`, not the graph-read loop the item describes — line-anchor drift over time); `PERF-00` (`setup/stack_launcher.py`); `H-D1`, `H-D2`, `S17.9`, `S21.6` (all edit existing engine/demo files).

**Strategic read:** of the 17 items that touch actual `src/npc_engine` production code (15 (b) + 2 (c)), **zero are pure additions — all 17 require editing an existing file.** The OCP claim ("new backends/distortions/emotion models are added by creating a new file") is not being tested by most of the open backlog, because most of the open backlog (71%, 46/65) is now the eval-harness meta-program, not engine features. Where the backlog *does* touch the engine, it is edit-heavy, not add-only.

### 4. Session/transaction ownership

```
$ grep -rn "begin_transaction(" src/npc_engine --include=*.py
graph/infra/transaction_coordinator.py:43:    tx = await session.begin_transaction()

$ grep -rn "\.commit()" src/npc_engine --include=*.py
graph/infra/transaction_coordinator.py:46:        await tx.commit()

$ grep -rn "AsyncTransaction" src/npc_engine --include=*.py | grep -v graph/infra/transaction_coordinator.py
# 90+ hits, every one is a `tx: AsyncTransaction` parameter on a graph/*_writer.py or
# graph/*_service.py `_work(tx)` closure — none outside graph/, none held as an attribute.
```
**Verdict: holds. Confirmed.** `transaction_coordinator.py` is the only file calling `begin_transaction()`/`.commit()`; no engine holds an `AsyncTransaction`.

### 5. OCP seams — LLM backend pluggability

- Protocol: `engines/llm/protocols.py` (`LLMClientProtocol`).
- Adapters shipped: **3** — `mock_adapter.py` (`MockLLMAdapter`), `ollama_adapter.py` (`OllamaAdapter`), `openai_adapter.py` (`OpenAICompatibleAdapter`, 288 lines, full `generate`/`generate_structured`/`stream`).
- Registry: `engines/llm/factory.py` — a real `dict[str, Callable]` (`_REGISTRY`), `register_backend()`, `registered_backends()` used by config validation instead of a hardcoded `Literal` (confirmed: no `Literal` of backend names found anywhere). `engines/llm/__init__.py` imports `factory` for the registration side effect.
- **To add backend #4 today:** write one new adapter file implementing `LLMClientProtocol`, then add a `_build_x` function + one `register_backend("x", _build_x)` line **inside `factory.py`**. The registry is real and config validation is genuinely open, but the 3 existing backends do not follow factory.py's own documented pattern ("writing an adapter... and calling `register_backend()` at import time" implies the adapter's own module registers itself); all three registrations are centralized in `factory.py`, so one existing file is still touched, not zero.
- **CLAUDE.md accuracy check — FAILS.** `project-harness/CLAUDE.md:22` states "no OpenAI adapter ships today." `git log --diff-filter=A -- src/npc_engine/engines/llm/openai_adapter.py` → added 2026-06-18, fully wired into `factory.py` from day one. `git blame -L 22,22 project-harness/CLAUDE.md` → that exact line was last rewritten **2026-07-31**, six weeks after the adapter shipped. The claim was false at the time it was last edited, not merely stale from disuse.

### 6. Coupling — 15 largest modules, fan-in/fan-out (AST-resolved `npc_engine.*` imports)

| File | LOC | Fan-in | Fan-out | Commits (churn) |
|---|---:|---:|---:|---:|
| `retrieval/context/context_builder.py` | 799 | 1 | 30 | 26 |
| `scheduler/tick_scheduler.py` | 630 | 4 | 10 | 31 |
| `retrieval/context/context_budget_enforcer.py` | 577 | 0 | 2 | — |
| `config.py` | 504 | **74** | 5 | **46** |
| `engines/dialogue/dialogue_handler.py` | 470 | 2 | **34** | 39 |
| `engines/gossip/gossip_handler.py` | 405 | 2 | 12 | — |
| `utils/errors.py` | 389 | 66 | 0 | 14 |
| `engines/quest/quest_lifecycle_engine.py` | 383 | 4 | 10 | — |
| `engines/quest_generation/quest_generation_engine.py` | 368 | 5 | 7 | — |
| `graph/intent/intent_queries.py` | 339 | 3 | 0 | — |
| `data/api_seeder.py` | 326 | 0 | 3 | — |
| `engines/chapter/chapter_engine.py` | 324 | 2 | 6 | — |
| `engines/dialogue/prompt_builder.py` | 305 | 1 | 5 | — |
| `api/dependencies.py` | 296 | 43 | 22 | 26 |
| `config_validators.py` | 295 | 1 | 0 | — |

**Chokepoints (high fan-in AND high-churn):** `config.py` (fan-in 74, 46 commits — the widest blast radius in the repo by 12x over the next candidate, and already flagged elsewhere as the top fix-magnet file, 68% over the 300-line limit with only a stale `DEC-077` waiver for 309 lines, not today's 504) and `engines/dialogue/dialogue_handler.py` (fan-out 34 — imports more of the tree than any other file, 39 commits, itself R001/R006-baselined). `utils/errors.py` (fan-in 66, fan-out 0) is high fan-in but a correct leaf — no churn concern, it's doing its job as the shared exception hierarchy.

---

## Findings

### [CR-L02-01] `GraphUnavailableError` is dead code — the documented Neo4j-outage fallback contract does not exist

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `utils/errors.py:54` defines `GraphUnavailableError` but `grep -rn "raise GraphUnavailableError\|GraphUnavailableError(" src/npc_engine` returns only the class definition itself — zero raise sites anywhere in the tree. Four files (`engines/military/military_battle_service.py`, `engines/military/military_resource_service.py`, `engines/ports/dialogue_graph_port.py`, `graph/political/pledge_violation_service.py`) document "Fallback: Neo4j unavailable → raises GraphUnavailableError" in their docstrings, but none actually raise it. Separately, `neo4j.exceptions.Neo4jError` is documented to propagate from `graph/relations/relation_phase_writer.py` through `engines/relationship/phase_transition_applier.py:60` into `engines/dialogue/dialogue_handler.py:283`; `api/errors/exception_handlers.py:109-120` registers handlers only for `RequestValidationError`, `HTTPException`, `ContentRatingViolationError`, and a catch-all `Exception` → `_internal_error_handler` (line 70) which returns a flat HTTP 500 `{"code": "internal_error"}` for anything untyped, `GraphUnavailableError` included were it ever raised.
- **Cost of inaction:** A live Neo4j outage during a dialogue turn will surface everywhere as a generic 500, indistinguishable from a bug in the requesting code, with no signal to a client or load balancer that the failure is retryable/transient (503 semantics). This is invisible in normal operation and will only be discovered during the first real graph outage.
- **Fix sketch:** Either wire `GraphUnavailableError` at the two or three actual Neo4j call boundaries (session acquisition, `transaction_coordinator.run_in_tx`) and register a `GraphUnavailableError → 503` handler in `exception_handlers.py`, or delete the dead class and the four false docstring claims and rely on the generic 500 deliberately — but the current state (documented contract, unimplemented, unregistered) is worse than either.
- **Effort:** M
- **Blast radius:** `api/errors/exception_handlers.py`, `graph/infra/transaction_coordinator.py` (or wherever the raise is added), the four docstrings that currently lie.

### [CR-L02-02] CLAUDE.md's stack table is factually wrong about a shipped capability, as of its most recent edit

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `project-harness/CLAUDE.md:22` — "no OpenAI adapter ships today." `src/npc_engine/engines/llm/openai_adapter.py` (288 lines) was added `2026-06-18` (`git log --diff-filter=A --format=%ad -- src/npc_engine/engines/llm/openai_adapter.py`) and is wired into `engines/llm/factory.py:24,92-102,107` from that commit. `git blame -L 22,22 project-harness/CLAUDE.md` shows that exact line was last rewritten `2026-07-31 17:48:59 +0200` — six weeks *after* the adapter shipped.
- **Cost of inaction:** Every session (including this review's own orchestrator prompt) that trusts the stack table as ground truth wastes a round-trip verifying something the repo already answers; a reviewer could wrongly credit or discredit the OCP claim based on the stale line.
- **Fix sketch:** Update the line to name the three shipped backends (mock/ollama/openai) and drop the "no OpenAI adapter" claim.
- **Effort:** S
- **Blast radius:** Documentation only.

### [CR-L02-03] Two stateful singletons are built outside every composition-root file, one of them a bare global dict guarded by a module-level lock

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `api/routes/dialogue/dialogue_ws.py:68-69` — `_active_ws_connections: dict[str, int] = {}` and `_ws_connections_lock = asyncio.Lock()` at module scope in a route file, read/written at lines 79 and 89 inside route handlers; never passed through any `dependencies*.py` file. `engines/interaction/dispatch.py:34` — `_trade_handler: SyncTradeHandlerProtocol = MinimalSyncTradeHandler()` at module scope, mutated via `global _trade_handler` in `set_trade_handler()` (lines 37-44), the module's own docstring calling this "Dependencies injected: ... via set_trade_handler" — a hand-rolled service-locator, not constructor injection. `grep -rln "^\s*global " src/npc_engine/engines src/npc_engine/api` finds exactly these 2 files (plus `engines/gossip/strategies/prefix_loader.py`, not stateful).
- **Cost of inaction:** `_active_ws_connections` is genuine cross-request mutable state with no owner and no test-time seam — a concurrency bug here (e.g. a missed lock acquisition on a future edit) won't be caught by anything that exercises `api/dependencies.py`-wired code paths, because this state was never wired through it. `dispatch.py`'s global swap makes trade-handler behavior order-dependent across tests unless every test remembers to reset it.
- **Fix sketch:** Move `_active_ws_connections`/`_ws_connections_lock` into a small class instantiated once in `api/dependencies.py` and injected into the two handlers that use it; replace `dispatch.py`'s `global`/setter pair with constructor-injected `SyncTradeHandlerProtocol`.
- **Effort:** M
- **Blast radius:** `api/routes/dialogue/dialogue_ws.py`, `engines/interaction/dispatch.py`, `api/dependencies.py`, any test currently relying on `set_trade_handler()`.

### [CR-L02-04] `check-rules` R005 (Cypher-leak) never scans `api/`, `auth/`, `data/`, `cache/`, or `mutation/`

- **Severity:** MEDIUM
- **Confidence:** Suspected (a gate coverage gap, not a live violation — verified zero live instances exist today)
- **Kind:** Gap
- **Evidence:** `scripts/check_rules.py:53` — `_CYPHER_SCAN_DIRS = ("engines", "world", "retrieval", "services", "scheduler")`. `api`, `auth`, `data`, `cache`, `mutation` are absent. Confirmed by manual scan: `grep -rniE "\b(MATCH|MERGE|CREATE|DELETE|UNWIND)\b.*\(" src/npc_engine/api src/npc_engine/auth src/npc_engine/data src/npc_engine/cache src/npc_engine/mutation` returns only case-insensitive false positives (`return cls(...)` matching `RETURN`), zero real Cypher. The regex itself is also case-sensitive-uppercase-only for `MATCH|MERGE|CREATE` and misses `DELETE`/`SET`/`UNWIND`/`WHERE`-only fragments and `.run(` on any session variable name other than literally `session`/`tx`.
- **Cost of inaction:** `api` is rank 6, the layer furthest from the DB and the one CLAUDE.md's own layer table says must never touch Neo4j directly — yet it is the one directory group R005 does not defend at all. A future handler that calls `session.run()` directly (e.g. an "quick admin debug query" added under time pressure) would pass CI silently.
- **Fix sketch:** Add `api`, `auth`, `data`, `cache`, `mutation` to `_CYPHER_SCAN_DIRS`; broaden the regex to catch lowercase and the missing keywords/session-var patterns.
- **Effort:** S
- **Blast radius:** `scripts/check_rules.py`, `scripts/rules_baseline.txt` (baseline run needed once to confirm no new hits).

### [CR-L02-05] "No raw `dict` crossing a module boundary" is violated at the two most central interfaces in the engine tree

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/base_engine.py:24` — `async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...`, the structural `Protocol` every tick-driven engine implements; confirmed 29 concrete `run_tick` methods return `dict[str, Any]` (AST count). `engines/llm/protocols.py:73` — `LLMClientProtocol.generate_structured(...) -> dict[str, Any]`, the exact seam CLAUDE.md names for "Structured output validated (strict): all `generate_structured()` output passes through a Pydantic model ... before any field is accessed" — the protocol's own contract is untyped; validation, if it happens, happens after the boundary, not at it. AST walk of `engines/graph/retrieval` (non-test, public functions) totals 145 functions returning `dict[str, Any]`/`dict` (`engines`: 67, `graph`: 72, `retrieval`: 6).
- **Cost of inaction:** The scheduler's dispatch contract and the LLM boundary — the two places a schema regression would be most expensive to debug — have no type contract to catch a shape drift; a bug here surfaces as a `KeyError` deep in a handler rather than a validation error at the boundary.
- **Fix sketch:** This is a large, deliberate trade-off (the docstring at `base_engine.py:16-19` explains engines have differing kwargs), not a quick fix — realistically requires a per-engine result model plus a narrower base protocol, sized as its own roadmap item rather than a spot fix.
- **Effort:** XL
- **Blast radius:** All ~29 tick engines, `scheduler/tick_scheduler.py`, every `LLMClientProtocol` implementation and caller.

### [CR-L02-06] `config.py`'s fan-in (74) is the widest blast radius in the repo, 12x the next non-leaf module, on top of its already-flagged churn/size

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** AST-resolved import graph over the 15 largest files (table above): `config.py` fan-in = 74 vs. the next-highest non-leaf module `api/dependencies.py` at 43 and `engines/quest_generation/quest_generation_engine.py` at 5. Combined with the already-established 46-commit churn and 504-line size (68% over limit, `DEC-077`'s waiver covers only 309 lines) this is a single file that a very large fraction of the tree depends on, changes often, and carries no current size waiver.
- **Cost of inaction:** Any change to `Settings` risks a ripple through 74 files with no compile-time enforcement beyond what mypy catches on field access; the combination of high change frequency and high fan-in is exactly the profile that produces silent cross-module breakage.
- **Fix sketch:** Split `Settings` by concern (LLM/graph/API/eval config) behind narrower accessor objects so most of the 74 importers depend on a slice, not the whole class; already implicitly proposed by `DEC-011`'s earlier `config_validators.py` extraction — extend that precedent.
- **Effort:** L
- **Blast radius:** All 74 current importers of `config.py` — this is why it hasn't been done yet.

### [CR-L02-07] Of the roadmap items that actually touch engine code, 100% require editing an existing file — OCP is not being exercised by the real remaining backlog

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** Full classification of all 65 unchecked `ROADMAP.md` items (table in Required Measurements §3): 46/65 (71%) belong to the eval-harness meta-program (`EVAL-P8..P31`) and are almost entirely new-file additions under `evals/`, `docs/`, `prompts/eval/`; of the 17 items that touch actual `src/npc_engine` production code, all 17 are (b) edit-existing or (c) schema/graph-wide — zero are pure additions. Named examples: `EVAL-P29.2` edits `engines/dialogue/prompt_builder.py` + `engines/dialogue/dialogue_handler.py` to pay down a constructor-injection violation already logged as `ISSUE-223`; `EVAL-P30.2` is explicitly flagged in the roadmap text itself as "public interface change with callers outside its module — ask-gate per CLAUDE.md"; `PR-9` and `OD-Ship-graph` each require touching dozens-to-hundreds of existing `graph/` files.
- **Cost of inaction:** The engine's OCP story ("new backends/distortions are added by creating a new file") is true for LLM backends (confirmed in item 5) but is not what the near-term roadmap will actually exercise — the visible backlog is mostly a separate eval-tooling program, and the few items that do touch the engine are all edits, several explicitly gated on "ask before touching a public interface." A planning read of the roadmap that assumes OCP will keep future engine work additive would be wrong.
- **Fix sketch:** Not a code fix — a planning input: budget engine-facing roadmap work (the 17 items) as edit-and-review work requiring the ask-gate process CLAUDE.md already specifies, not as isolated new-file additions; the eval-harness program (46 items) can continue to be scheduled more lightly since it is genuinely additive.
- **Effort:** N/A (planning finding)
- **Blast radius:** Roadmap sequencing/estimation only; no code touched.

### [CR-L02-08] The LLM factory's own extension-point docstring describes a pattern the 3 shipped adapters don't follow

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/llm/factory.py:10-14` — "add a new local/remote LLM backend by writing an adapter that satisfies `LLMClientProtocol` and calling `register_backend("name", ctor)` at import time, then importing it from `engines/llm/__init__.py`." But `mock_adapter.py`, `ollama_adapter.py`, and `openai_adapter.py` do not call `register_backend` themselves; all three `register_backend(...)` calls live centrally at `factory.py:105-107`, and the three `_build_*` constructor functions also live in `factory.py` (lines 78-102), not beside their adapters.
- **Cost of inaction:** A contributor following the documented extension point literally (adapter file calls `register_backend` itself) will add a backend in a style inconsistent with the 3 that exist, or will discover only by reading `factory.py` that they actually need to edit it too — a minor but real doc/code mismatch in the one file whose docstring is explicitly about OCP.
- **Fix sketch:** Either move each `_build_*` + `register_backend()` call into its own adapter module (matching the docstring) or rewrite the docstring to describe the actual centralized-registration pattern.
- **Effort:** S
- **Blast radius:** `engines/llm/factory.py`, `mock_adapter.py`, `ollama_adapter.py`, `openai_adapter.py` (only if code moves; doc-only fix touches nothing else).
