# Report 1: Architecture Review

> **Scope:** Diagnosis only — no code changes proposed.
> **Date:** 2026-05-13

---

## 1. LLM Switchability

`LLMClientProtocol` is mostly a complete abstraction for Ollama-served models (including LoRA fine-tunes served via Ollama — zero engine changes needed, just update `model:` in the YAML). Adding a new backend (vLLM, llama.cpp, OpenAI-compatible) requires editing 4 files in 3 different packages. There's no plugin mechanism — the factory is a closed `if/elif` cascade.

Three deeper gaps:

- `MistralAdapter` and `LlamaAdapter` **do not accept the `system` kwarg** defined on the protocol. If anyone flips dialogue's backend to `mistral7b`, every dialogue call will `TypeError`. The protocol is unenforced — `@runtime_checkable` does not catch keyword-signature mismatches.
- `model_name()` returns the **adapter class name** (`"mistral7b"`, `"llama8b"`), not the actual configured model identifier. Only `OllamaAdapter` returns the real model tag. This breaks any metrics or fine-tuning traceability that tries to filter by model.
- No health-check method exists on the protocol. Startup does not probe the LLM backend — a misconfigured `OLLAMA_API_URL` only surfaces on the first real request.

**Key files:** `src/npc_engine/engines/llm/protocols.py`, `src/npc_engine/engines/llm/factory.py`, `src/npc_engine/engines/llm/mistral_adapter.py`, `src/npc_engine/engines/llm/llama_adapter.py`

---

## 2. Per-Engine LLM Configuration

Only **dialogue** and **quest_generation** have `llm_config.yaml`. **Memory consolidation has none** — it hardcodes `_MAX_TOKENS = 300` and `_TEMPERATURE = 0.4` as module constants, completely bypassing the per-engine config pattern. It also has no contract YAML, so it is invisible to the startup validator.

The `EngineTimeoutsMs` schema mandates `full`/`graph_only`/`canned` keys — but quest_generation only has `full` and `deterministic` tiers. Its YAML lies, declaring `graph_only: 10000` and `canned: 100` to pass validation. There is no schema enforcement that timeout keys agree with declared fallback tiers.

The per-request vs. singleton split: dialogue creates a fresh `OllamaAdapter` per HTTP request (and `httpx.AsyncClient` per call inside it — no connection reuse at all); quest_generation uses a singleton. The concrete consequence is **no HTTP connection pooling anywhere**. The singleton offers no real advantage at the HTTP layer as currently implemented. The two patterns also require two different override mechanisms in tests.

**Key files:** `src/npc_engine/engines/memory_consolidation/memory_consolidation_engine.py`, `src/npc_engine/engines/llm_config_models.py`, `src/npc_engine/api/dependencies.py`

---

## 3. Adding New Engines

For a new LLM-using engine the minimum changeset is: package directory, `llm_config.yaml`, contract YAML, singleton provider in `dependency_singletons.py`, route file, router include in `main.py`. If tick-driven, also a `TickScheduler` constructor argument — the scheduler's constructor grows linearly with no registration system.

The contract-to-directory convention (`quest_generation_engine` → strip `_engine` → find `engines/quest_generation/`) is a string-stripping heuristic. A typo gives a misleading "file does not exist" error at startup, not a clear "contract misconfigured" error. There is no auto-discovery — every engine is hand-wired in at least 3 places.

**Key files:** `src/npc_engine/engines/llm_config_loader.py`, `src/npc_engine/api/dependency_singletons.py`, `src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/main.py`

---

## 4. Adding New Graph Nodes and Edges

The extension mechanism (`game_schema.yaml` → TypeRegistry → runtime Pydantic models) is architecturally sound but effectively **decorative**. The startup warning "custom_node_types declared but not consumed by current engines" admits it. Engines that touch custom types bypass the registry and hand-roll Cypher with hardcoded capitalized labels. The registry-derived Pydantic models are built but not used for write validation or read shaping in any current engine.

Adding a base node type requires approximately 4 new files (writer/queries/service/routes) with no scaffolding tooling. The pattern is well-established but tedious.

**Key files:** `src/npc_engine/type_registry/registry.py`, `src/npc_engine/type_registry/merge_rules.py`, `src/npc_engine/type_registry/runtime_models.py`, `src/npc_engine/engines/quest_generation/quest_generation_engine.py:264`

---

## 5. Layer Violations

The intended layering (API → Engines → Services → Graph) is broken in several places:

- `QuestGenerationEngine` executes raw Cypher directly against `AsyncSession` — no service layer.
- `FactionPoliticsEngine`, `QuestLifecycleEngine`, `TradeEngine` all import directly from `graph/*_writer.py`, bypassing services.
- **Most critical:** the `consolidate_memories` route constructs a `MemoryConsolidationEngine` inside the route handler, using **dialogue's** `get_llm_client` — dialogue's model, temperature, and timeout, not any memory-consolidation config. The route is acting as composition root with silently misconfigured LLM parameters.

There is no service layer for currency/items as a coherent boundary. Read-heavy domains go through services; writes go through `*_writer.py` called by engines directly. This is consistent within itself but inconsistent with the docs.

**Key files:** `src/npc_engine/api/routes/memories.py:225-247`, `src/npc_engine/engines/quest_generation/quest_generation_engine.py:137-138`, `src/npc_engine/engines/faction_politics/faction_politics_engine.py`

---

## 6. Singleton Pattern Risks

`@lru_cache` singletons are only cache-cleared in `lifespan` for a small subset (schema, type registry, llm_config, dialogue engine model config). Quest generation, faction politics, story pacing, pricing, and economy singletons are **not cleared** — their rules YAMLs are frozen at first access; hot-reload requires a full process restart.

In tests, any provider not explicitly `cache_clear()`'d between test modules will leak state. Combined with `lru_cache` being keyed by argument identity (all providers are zero-argument), this is a cross-test pollution risk that is easy to trigger and hard to debug.

**Key files:** `src/npc_engine/api/dependency_singletons.py`, `src/npc_engine/main.py:75-95`

---

## 7. Prompt Versioning — Not Fit for Fine-Tuning Traceability

Three independent versioning mechanisms exist: an embedded string constant (`PROMPT_VERSION = "stage_b_v1.0"` in `prompt_builder.py`), a `prompt.version` integer in the engine YAML (declared but **never read at runtime**), and a `compression_prompt_version` in the context config. None are authoritative.

What is missing for a fine-tuning dataset pipeline:

- No persisted `{prompt_version, model, model_params, request_id, prompt_text, response_text, timestamp}` log.
- No correlation between an HTTP `request_id`/`idempotency_key` and the LLM call(s) it generates.
- No prompt-template hash. Editing the system prompt without bumping the string constant produces undetected semantic drift in any downstream analytics.
- Prompts are not versioned as separate files for dialogue (the system prompt is a Python triple-string at `prompt_builder.py:14-46`).

**Key files:** `src/npc_engine/engines/dialogue/prompt_builder.py`, `src/npc_engine/engines/dialogue/llm_config.yaml`, `config/llm_config.yaml`

---

## 8. Observability Gaps

What exists: `llm_calls_total`, `llm_tokens_in/out_total`, `llm_validation_failures_total`, degradation tier counter — but **only for dialogue**. Quest generation and memory consolidation emit **no LLM metrics at all**.

What is missing:

- **No latency metrics** for LLM calls anywhere. `perf_counter` is used for graph writes; never for LLM calls.
- No per-tier latency (full vs. graph_only vs. canned).
- No fallback rate.
- `LLMRequestError` discards the underlying `httpx` status code — logged as `detail="http_error"` with the original status lost.
- No structured prompt capture — even `LOG_LLM_PROMPTS=True` emits to DEBUG without a `request_id` field, making replay impossible.

**Key files:** `src/npc_engine/engines/dialogue/llm_client.py:77-141`, `src/npc_engine/engines/llm/ollama_adapter.py:78`

---

## 9. Packaging Concerns

For shipping with external LLMs:

- **Sysadmins can configure LLM URL via env vars, but cannot change model, temperature, or max_tokens without editing files inside the installed Python package.** Per-engine YAML files live at `src/npc_engine/engines/<engine>/llm_config.yaml` — inside the package tree.
- **No API key support** in any adapter. Any cloud-hosted LLM requires adapter code changes, not config changes.
- **No OpenAI-compatible adapter** despite it being the de facto standard for externally-served LLMs (vLLM, Together, Fireworks, etc.).
- Config is split across 4 locations: env vars, top-level `game_schema.yaml`, `config/llm_config.yaml`, and per-engine YAMLs inside the package. Operator-facing and developer-facing config are not separated.
- No `/health` LLM probe. Readiness endpoint exists but does not verify LLM connectivity.
- `LLM_TIMEOUT_SECONDS` is a single global timeout for all backends; per-backend or per-engine HTTP timeouts are not separable from per-tier `timeouts_ms` (which are application-level, not network-level).

**Key files:** `src/npc_engine/config.py`, `src/npc_engine/engines/llm/ollama_adapter.py`, `src/npc_engine/api/routes/system.py`

---

## 10. Other Findings

- `MockLLMAdapter` ignores the `schema` argument in `generate_structured` — returns a hardcoded dialogue-shaped payload for all engines. Quest generation tests that pass a slot-fill schema get back a dialogue response structure, making those tests weaker than they appear.
- `OllamaAdapter.generate_structured` injects schema into the prompt body **and** sets `format: json` — the body injection is redundant and costs tokens on every structured call.
- `QuestGenerationEngine` swallows all exceptions with bare `except Exception`, degrading to deterministic fallback for validation errors, network errors, and programmer errors alike — indistinguishable in telemetry.
- `registry.py` constructs `TypeRegistry` twice; the first instance is discarded after feeding the runtime model builder. Code smell.
- `BaseEngine` Protocol is decorative — `TickScheduler` takes `object`, not `BaseEngine`. No enforcement anywhere.
- An in-function import of `create_llm_client_for_engine` in `dependency_singletons.py` suggests a circular import that was worked around rather than resolved.
- Three separate module-name collisions: `engines/llm_config_models.py` vs `schema/llm_config_models.py` — same basename, different contents, easy to import the wrong one.

---

## Prioritized Summary

| Issue | Severity | Effort |
|---|---|---|
| `MistralAdapter`/`LlamaAdapter` missing `system` kwarg — latent `TypeError` if backend is switched | **High** | S |
| `MemoryConsolidationEngine` has no `llm_config.yaml`, no contract, hardcoded params; invisible to startup validator | **High** | M |
| `consolidate_memories` route uses dialogue's LLM config for memory consolidation — silent misconfiguration | **High** | S |
| No LLM latency metrics anywhere; quest_generation and memory_consolidation emit zero LLM telemetry | **High** | M |
| No prompt-template hash or replay capability — fine-tuning dataset traceability not possible today | **High** | M |
| `model_name()` returns adapter class string, not configured model — metrics conflate adapter and model | **High** | S |
| Factory is a closed `if/elif` — adding a new backend requires 4 file edits in 3 packages, no plugin point | **Medium** | M |
| No HTTP connection pooling — per-request adapter + per-call `AsyncClient` in dialogue | **Medium** | S |
| No LLM health/readiness probe at startup | **Medium** | S |
| `EngineTimeoutsMs` schema forces single-tier engines to lie in their YAML | **Medium** | S |
| `QuestGenerationEngine` ignores its own `llm_config.max_tokens`, uses hardcoded 256 | **Medium** | S |
| Bare `except Exception` in quest_generation swallows programmer errors | **Medium** | S |
| `@lru_cache` singletons for rules-based engines not cleared in lifespan; no hot-reload | **Medium** | S |
| Extension mechanism for custom node/edge types is decorative — engines bypass it | **Medium** | L |
| No API key support in any adapter — blocks cloud LLM deployment without code changes | **Medium** | M |
| Per-engine config YAMLs inaccessible to sysadmin without touching package internals | **Medium** | M |
| Engines import directly from `graph/*_writer.py` — no consistent service layer | **Medium** | L |
| `MockLLMAdapter` ignores schema — returns dialogue payload for all engines | **Medium** | S |
| Three independent prompt-version mechanisms, none authoritative | **Medium** | M |
| `registry.py` constructs `TypeRegistry` twice | Low | S |
| `OllamaAdapter.generate_structured` injects schema twice (body + format field) | Low | S |
| `BaseEngine` Protocol unused as type constraint | Low | S |
| In-function import in `dependency_singletons.py` (circular dep workaround) | Low | S |
| Module-name collisions: `engines/llm_config_*.py` vs `schema/llm_config_*.py` | Low | M |
| `LLMRequestError` discards underlying `httpx` status code | Low | S |
| `LLM_TIMEOUT_SECONDS` is global — not separable from per-tier or per-backend timeout | Low | S |
| Contract→directory name derivation is implicit string-strip heuristic | Low | S |
