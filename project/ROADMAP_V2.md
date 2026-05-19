# Roadmap V2 — Fixes → Retrieval → Graph Expansion → Genre Modules

> **Source:** Synthesised from reports 1–4 (architecture, graph expansion, fine-tuning, context retrieval).
> **Fine-tuning:** Out of scope for this roadmap.
> **Ordering principle:** Each phase must leave zero rework for subsequent phases.
> **Effort labels:** XS < 1 h · S half-day · M 1–2 days · L 3–5 days

---

## Phase 1 — Critical Structural Fixes

Run `pytest tests/ -q` before touching anything. All tests must stay green throughout this phase.

---

### 1.1 Fix `model_name()` on `MistralAdapter` / `LlamaAdapter` — S

**Problem:** `MistralAdapter.model_name()` returns the hardcoded string `"mistral7b"` regardless of the configured model. `LlamaAdapter` returns `"llama8b"`. All metrics labels and fine-tuning logs that call `adapter.model_name()` get the adapter class name, not the actual model tag.

**Files to change:**

`src/npc_engine/engines/llm/mistral_adapter.py`

```python
# __init__ — add model_name param
def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
    self._base_url = base_url
    self._model_name = model_name
    self._timeout_seconds = timeout_seconds

# model_name() — return configured tag, not hardcoded string
def model_name(self) -> str:
    return self._model_name
```

`src/npc_engine/engines/llm/llama_adapter.py`

```python
# Remove the model_name() override entirely.
# LlamaAdapter inherits MistralAdapter.__init__, so it already accepts model_name.
# The inherited model_name() now returns self._model_name correctly.
class LlamaAdapter(MistralAdapter):
    """Adapter for Llama completion endpoints using shared HTTP implementation."""
    # (no overrides needed)
```

`src/npc_engine/engines/llm/factory.py`

```python
# In create_llm_client_for_engine, pass model to both constructors:
if backend == "mistral7b":
    ...
    return MistralAdapter(
        base_url=settings.MISTRAL_API_URL,
        model_name=model,          # ← add this
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )
if backend == "llama8b":
    ...
    return LlamaAdapter(
        base_url=settings.LLAMA_API_URL,
        model_name=model,          # ← add this
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )
```

**Tests to add:** Unit test `MistralAdapter("url", "my-model", 30).model_name() == "my-model"` and same for `LlamaAdapter`.

---

### 1.2 Add `system` kwarg to `MistralAdapter` / `LlamaAdapter` — S

**Problem:** `LLMClientProtocol` declares `system: str | None = None` on all three methods. `MistralAdapter` (and `LlamaAdapter` which inherits it) do not accept this kwarg. Any call to a mistral/llama backend with a system prompt raises `TypeError` at runtime.

**Files to change:**

`src/npc_engine/engines/llm/mistral_adapter.py`

Add `system: str | None = None` to `generate`, `generate_structured`, and `stream`. Prepend the system prompt to `prompt` when provided — the Mistral `/generate` endpoint is a plain completion endpoint, not a chat endpoint, so injection into the prompt body is the correct approach:

```python
async def generate(
    self,
    prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float | None = None,
    stop_sequences: list[str] | None = None,
    system: str | None = None,   # ← add
) -> str:
    effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
    payload: dict = {"prompt": effective_prompt, ...}
    ...

async def generate_structured(
    self,
    prompt: str,
    schema: dict[str, Any],
    max_tokens: int,
    top_p: float | None = None,
    stop_sequences: list[str] | None = None,
    system: str | None = None,   # ← add
) -> dict[str, Any]:
    effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
    payload: dict = {"prompt": effective_prompt, ...}
    ...

async def stream(
    self,
    prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float | None = None,
    stop_sequences: list[str] | None = None,
    system: str | None = None,   # ← add
) -> AsyncIterator[str]:
    effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
    payload: dict = {"prompt": effective_prompt, ...}
    ...
```

`LlamaAdapter` inherits all three methods from `MistralAdapter` — no changes needed.

**Tests to add:** Call `MistralAdapter.generate(prompt="hello", system="be concise", ...)` against a mock HTTP server; verify the POST body's `"prompt"` field starts with `"be concise\n\n"`.

---

### 1.3 Fix `consolidate_memories` route — stop using dialogue's `get_llm_client` — S

**Problem:** `api/routes/memories.py:consolidate_memories` depends on `get_llm_client` which returns an `OllamaAdapter` configured from `engines/dialogue/llm_config.yaml` (model `mixtral:8x7b`, dialogue-specific settings). This silently misconfigures the memory consolidation engine. When Phase 2.1 adds a proper `llm_config.yaml` for memory consolidation, the route must use it, not dialogue's config.

**Phase 1 fix:** Create a provisional singleton in `dependency_singletons.py`. The route wires to this singleton; Phase 2.2 replaces the singleton's internals without touching the route.

`src/npc_engine/api/dependency_singletons.py` — add at the bottom:

```python
@lru_cache
def get_memory_consolidation_engine():
    """Provisional singleton for the memory consolidation engine.

    Uses dialogue's LLM adapter until Phase 2.1 creates engines/memory_consolidation/llm_config.yaml
    and Phase 2.2 replaces this with a properly-configured singleton.
    """
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import MemoryConsolidationEngine
    from npc_engine.engines.llm.factory import create_llm_client_for_engine

    settings = get_settings()
    engine_config = get_engine_model_config_for("dialogue")   # ← temporary; replaced in Phase 2.2
    llm_client = create_llm_client_for_engine(engine_config, settings)
    return MemoryConsolidationEngine(
        session_store=get_session_store(),
        llm_client=llm_client,
        turn_threshold=5,
        clear_turns_after=False,
    )
```

`src/npc_engine/api/routes/memories.py` — update `consolidate_memories`:

```python
# Remove these imports:
#   from npc_engine.api.dependencies import get_llm_client, get_session_store
# Keep get_session_store if used elsewhere, but remove get_llm_client

# Add import:
from npc_engine.api.dependency_singletons import get_memory_consolidation_engine

# Change route signature — remove llm_client dependency, inject engine instead:
@router.post("/consolidate/{npc_id}")
async def consolidate_memories(
    npc_id: str,
    body: ConsolidateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    engine = get_memory_consolidation_engine()
    gt = body.game_time
    game_time = TimePoint(...)
    memory_id = await engine.consolidate(session, npc_id=npc_id, game_time=game_time)
    return ok_response({"memory_id": memory_id})
```

Remove the local `from npc_engine.engines.memory_consolidation... import MemoryConsolidationEngine` that was inside the handler.

Also add `get_memory_consolidation_engine` to the `lifespan` cache-clear list in `main.py` alongside the other singletons:
```python
get_memory_consolidation_engine.cache_clear()
```

**Tests to add:** Mock `get_memory_consolidation_engine` in a route test; verify `consolidate_memories` calls `engine.consolidate()` with correct `npc_id` and `game_time`.

---

### 1.4 Fix `MockLLMAdapter` — respect the `schema` argument — S

**Problem:** `MockLLMAdapter.generate_structured` ignores `schema` and always returns `dict(self._response)`, which is a hardcoded dialogue payload. Quest generation tests that pass a slot-fill schema get back a dialogue-shaped dict, making those tests structurally invalid.

**Files to change:**

`src/npc_engine/engines/llm/mock_adapter.py`

```python
class MockLLMAdapter(LLMClientProtocol):
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        structured_response: dict[str, Any] | None = None,  # ← add
    ) -> None:
        self._response = dict(response) if response is not None else dict(DEFAULT_RESPONSE)
        # structured_response defaults to the same as response if not provided
        self._structured_response = (
            dict(structured_response) if structured_response is not None else dict(self._response)
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        return dict(self._structured_response)   # ← return dedicated structured payload
```

**Usage in existing quest generation tests:** Pass the appropriate slot-fill payload via `structured_response`:
```python
mock = MockLLMAdapter(
    structured_response={"target": "char_bandit_lord_42", "location": "loc_mill"}
)
```

**Tests to add:** Verify `MockLLMAdapter(structured_response={"key": "val"}).generate_structured(...)` returns `{"key": "val"}` while `.generate(...)` still returns the npc_response string.

---

### 1.5 Rename `schema/llm_config_models.py` → `schema/context_config_models.py` — M

**Problem:** `engines/llm_config_models.py` (per-engine LLM config) and `schema/llm_config_models.py` (context scoring/budget config) share the same filename, making imports ambiguous and error-prone.

**Decision:** Rename the `schema/` side since its content (`LLMConfig`, `RelevanceWeights`, `TierBudgetTokens`) is more accurately described as context pipeline config, not LLM engine config.

**Steps:**

1. Rename file: `src/npc_engine/schema/llm_config_models.py` → `src/npc_engine/schema/context_config_models.py`

2. Update all 9 import sites — change every occurrence of:
   ```python
   from npc_engine.schema.llm_config_models import ...
   ```
   to:
   ```python
   from npc_engine.schema.context_config_models import ...
   ```

   Files to update:
   - `src/npc_engine/api/dependency_singletons.py`
   - `src/npc_engine/api/dependencies.py`
   - `src/npc_engine/retrieval/context_builder.py`
   - `src/npc_engine/retrieval/context_budget_enforcer.py`
   - `src/npc_engine/retrieval/context_compression.py`
   - `src/npc_engine/retrieval/context_relevance_engine.py`
   - `src/npc_engine/retrieval/context_scoring.py`
   - `src/npc_engine/schema/llm_config_loader.py`
   - `src/npc_engine/engines/dialogue/dialogue_handler.py`

3. Update any test files that import from `npc_engine.schema.llm_config_models`.

4. Run `pytest tests/ -q` and verify zero import errors.

---

### 1.6 Remove redundant schema injection in `OllamaAdapter.generate_structured` — S

**Problem:** `OllamaAdapter.generate_structured` injects the JSON schema into the prompt body AND sets `"format": "json"`. The body injection is redundant and costs tokens on every structured call.

**File:** `src/npc_engine/engines/llm/ollama_adapter.py`

Change the `generate_structured` payload construction:

```python
# Before:
payload: dict = {
    "model": self._model_name,
    "prompt": f"{prompt}\n\nRequired JSON schema:\n{json.dumps(schema, ensure_ascii=True)}",
    "stream": False,
    "format": "json",
    "options": options,
}

# After:
payload: dict = {
    "model": self._model_name,
    "prompt": prompt,
    "stream": False,
    "format": "json",
    "options": options,
}
```

The `schema` parameter is part of the protocol signature and should be retained for documentation purposes; simply stop injecting it into the body. Ollama's `"format": "json"` is sufficient to constrain the response to a JSON object.

**Tests to add:** Mock the Ollama HTTP endpoint; assert the POST body's `"prompt"` field equals the raw `prompt` argument with no appended schema text.

---

### 1.7 Preserve `httpx` status code in `LLMRequestError` — S

**Problem:** Both `MistralAdapter` and `OllamaAdapter` catch all `httpx.HTTPError` and raise `LLMRequestError(detail="http_error")`. For `HTTPStatusError` (4xx/5xx responses), the actual status code is discarded — impossible to distinguish a 429 (rate-limit) from a 503 (backend down) in logs.

**Files:** `src/npc_engine/engines/llm/mistral_adapter.py`, `src/npc_engine/engines/llm/ollama_adapter.py`

In each method that catches `httpx.HTTPError`, split the catch:

```python
# In generate, generate_structured, stream of both adapters:
except httpx.HTTPStatusError as error:
    raise LLMRequestError(
        model=self.model_name(),
        detail=f"http_error:{error.response.status_code}",
    ) from error
except httpx.HTTPError as error:
    raise LLMRequestError(model=self.model_name(), detail="http_error") from error
```

`httpx.HTTPStatusError` is a subclass of `httpx.HTTPError`, so it must be caught first.

**Tests to add:** Simulate a 429 response from the mock Ollama server; assert `LLMRequestError.detail == "http_error:429"`.

---

### 1.8 Remove redundant `get_character_with_relations` call — XS

**Problem:** `context_builder.py` calls `get_character_with_relations` at the top of `build_serialized_context` to get the character payload for the cache key and emotion snapshot. `retrieve_tier_a_context` (called a few lines later) also calls `get_character_with_relations` internally. This is two identical Neo4j round trips per dialogue turn.

**Fix:** Pass the pre-fetched bundle into `retrieve_tier_a_context`.

`src/npc_engine/retrieval/subgraph_retriever.py`

Change the function signature:

```python
async def retrieve_tier_a_context(
    session: AsyncSession,
    npc_id: str,
    event_limit: int,
    character_bundle: dict | None = None,   # ← add optional param
) -> list[ContextItem]:
    # If bundle already fetched by caller, skip the round trip
    bundle = character_bundle if character_bundle is not None else (
        await get_character_with_relations(session=session, npc_id=npc_id)
    )
    events = await get_events_for_npc(session=session, npc_id=npc_id, limit=event_limit)
    # Use `bundle` instead of `character_bundle` from here on
    ...
```

`src/npc_engine/retrieval/context_builder.py`

Pass `character_bundle=character_bundle` to `retrieve_tier_a_context`:

```python
tier_a_raw.extend(
    await retrieve_tier_a_context(
        session=session,
        npc_id=npc_id,
        event_limit=settings.RAG_TOP_K,
        character_bundle=character_bundle,   # ← pass pre-fetched bundle
    )
)
```

---

### 1.9 Fix compression — byte truncation → JSON-safe field selection — S

**Problem:** `context_compression._compress_text` left-truncates bytes, producing invalid JSON (`{"summary":"…","participants":["a","b...[compressed]#abcd1234`). The LLM receives malformed input.

**Fix:** In `ContextCompressionCache.compress_item`, parse the JSON, project to essential fields per node type, re-serialize. Fall back to truncation only if still over budget after projection.

`src/npc_engine/retrieval/context_compression.py`

Add essential field definitions and a field-projection compressor:

```python
# Essential fields to retain per node type when compressing.
# All other fields are dropped before the token-size check.
_ESSENTIAL_FIELDS: dict[str, frozenset[str]] = {
    "event": frozenset({"summary", "event_type", "severity", "occurred_at"}),
    "character": frozenset({"name", "archetype", "current_mood", "biography"}),
    "location": frozenset({"name", "descriptor", "region"}),
    "memory": frozenset({"content", "vividness", "emotional_charge"}),
    "belief": frozenset({"content", "confidence", "target_id"}),
    "goal": frozenset({"description", "urgency", "status", "target_id"}),
    "secret": frozenset({"content", "severity"}),
    "item": frozenset({"name", "item_type", "value", "rarity"}),
    "debt": frozenset({"amount", "reason", "due_by"}),
}


def _field_select_compress(text: str, node_type: str, target_tokens: int) -> str:
    """Compress by removing non-essential fields, then fall back to byte truncation."""
    from npc_engine.common.json_utils import parse_json_object

    payload = parse_json_object(text)
    if not payload:
        return _compress_text(text, target_tokens=target_tokens)

    essential = _ESSENTIAL_FIELDS.get(node_type)
    if essential is not None:
        projected = {k: v for k, v in payload.items() if k in essential and v is not None}
    else:
        projected = {k: v for k, v in payload.items() if v is not None}

    import json
    projected_text = json.dumps(projected, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    target_chars = max(MIN_COMPRESSED_CHARS, target_tokens * CHARS_PER_TOKEN_ESTIMATE)
    if len(projected_text) <= target_chars:
        return projected_text

    # Still over budget after projection — fall back to byte truncation on the projected text
    return _compress_text(projected_text, target_tokens=target_tokens)
```

Update `ContextCompressionCache.compress_item` to call `_field_select_compress` instead of `_compress_text`:

```python
compressed = _field_select_compress(item.text, node_type=node_type, target_tokens=target_tokens)
```

---

### 1.10 Strip null fields and low-value ID fields from serialized items — S

**Problem:** `serialize_json` includes `null` values and verbose identifiers (`actor_id`, `location_id`, `schema_version`) in event and belief serializations. Estimated 25–35% of Tier A tokens are recoverable waste.

**Files:** `src/npc_engine/retrieval/context_utils.py`, `src/npc_engine/retrieval/context_builder.py`

`context_utils.py` — extend `serialize_json`:

```python
_LOW_VALUE_FIELDS: frozenset[str] = frozenset({
    "actor_id", "location_id", "schema_version", "id",
    "created_at_game_time",  # game time appears separately in tier0
})


def serialize_json(
    value: Any,
    *,
    compact: bool = False,
    strip_nulls: bool = False,
    strip_fields: frozenset[str] | None = None,
) -> str:
    if strip_nulls or strip_fields:
        value = _clean(value, strip_nulls=strip_nulls, strip_fields=strip_fields or frozenset())
    separators = (",", ":") if compact else None
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=separators)


def _clean(
    value: Any,
    *,
    strip_nulls: bool,
    strip_fields: frozenset[str],
) -> Any:
    if isinstance(value, dict):
        return {
            k: _clean(v, strip_nulls=strip_nulls, strip_fields=strip_fields)
            for k, v in value.items()
            if k not in strip_fields and (not strip_nulls or v is not None)
        }
    if isinstance(value, list):
        return [_clean(item, strip_nulls=strip_nulls, strip_fields=strip_fields) for item in value]
    return value
```

`context_builder.py` — use strip options for tier A items:

```python
# When serializing event/belief/goal/secret/memory items in tier_a_raw, pass strip_nulls=True
# The serialize_json calls come through context_utils.serialize_json in subgraph_retriever.py
# Easiest to apply at the subgraph_retriever level:
```

`src/npc_engine/retrieval/subgraph_retriever.py` — update event serialization:

```python
for index, event in enumerate(events):
    items.append(
        ContextItem(
            key=f"event:{index}:{npc_id}",
            text=serialize_json(event, strip_nulls=True, strip_fields=_LOW_VALUE_FIELDS),
            ...
        )
    )
```

Import `_LOW_VALUE_FIELDS` from `context_utils` or define equivalently in `subgraph_retriever`.

Apply `strip_nulls=True` consistently to all `serialize_json` calls in `context_builder.py` that serialize beliefs, goals, secrets, memories, and debts.

---

### 1.11 Cap nearby NPC payload in `subgraph_retriever` — S

**Problem:** `CYPHER_GET_LOCATION_CONTEXT` returns `collect(properties(c))` — all properties of every NPC at the location. A market scene with 6 NPCs emits ~600 tokens of properties the LLM doesn't use.

**File:** `src/npc_engine/retrieval/subgraph_retriever.py`

After building `nearby_npcs`, project to essential fields:

```python
_NPC_NEARBY_FIELDS = ("id", "name", "archetype", "faction")

nearby_npcs = [
    {k: npc[k] for k in _NPC_NEARBY_FIELDS if k in npc}
    for npc in location_context.get("present_npcs", [])
    if isinstance(npc, dict) and npc.get("id") != npc_id and not npc.get("is_player", False)
]
```

---

### 1.12 Add `k=10` limit to `get_items_for_character` — S

**Problem:** `get_items_for_character` is called with no limit. An NPC with 50 items dumps all 50 into Tier A.

**Files:** `src/npc_engine/graph/item_queries.py` (or wherever the query is defined), `src/npc_engine/retrieval/context_builder.py`

In the graph query function, add `k: int = 10` parameter and append `LIMIT $k` to the Cypher. In `context_builder.py`, update the call:

```python
owned_items = await get_items_for_character(session, character_id=npc_id, k=10)
```

Order items by value descending or relevance (equip-status first) before the LIMIT.

---

### 1.13 Remove the `explicit` scoring weight — XS

**Problem:** `explicit` returns `1.0` for all Tier A items and `0.0` everywhere else. It is a tier membership flag, not a ranking signal — it has no ranking effect within any tier. Its 0.05 weight is wasted.

**Files:**

`config/llm_config.yaml` — redistribute the 0.05:

```yaml
relevance_weights:
  recency: 0.30      # was 0.25 — absorbs the explicit 0.05
  severity: 0.20
  proximity: 0.20
  relation: 0.20
  quest: 0.10
  # explicit removed
```

`src/npc_engine/schema/context_config_models.py` (after 1.5 rename):

```python
class RelevanceWeights(BaseModel):
    recency: float = Field(ge=0.0, le=1.0)
    severity: float = Field(ge=0.0, le=1.0)
    proximity: float = Field(ge=0.0, le=1.0)
    relation: float = Field(ge=0.0, le=1.0)
    quest: float = Field(ge=0.0, le=1.0)
    # explicit field removed
```

`src/npc_engine/retrieval/context_relevance_engine.py`:

```python
class ContextRelevanceCandidate(BaseModel):
    node_id: str
    node_type: str
    item: ContextItem
    recency: float
    severity: float
    proximity_hops: int
    relation: float
    quest: float
    # explicit field removed

def score_candidate(...) -> float:
    ...
    return (
        weights.recency * candidate.recency
        + weights.severity * candidate.severity
        + weights.proximity * proximity_score
        + weights.relation * candidate.relation
        + weights.quest * candidate.quest
        # explicit term removed
    )
```

`src/npc_engine/retrieval/context_scoring.py`:

```python
def _build_candidate(...) -> ContextRelevanceCandidate:
    return ContextRelevanceCandidate(
        node_type=node_type,
        node_id=node_id,
        item=item,
        recency=_extract_recency_score(payload),
        severity=_extract_severity_score(payload),
        proximity_hops=_infer_proximity_hops(item.key, llm_config.max_proximity_hops),
        relation=_extract_relation_score(item=item, vector_scores=vector_scores),
        quest=_quest_score(item=item),
        # explicit removed
    )
```

---

### 1.14 Fix `registry.py` double `TypeRegistry` construction — S

**Problem:** `build_type_registry` constructs two `TypeRegistry` instances — the first is only used to pass to `build_runtime_models`; the second is the actual return value. The first instance is discarded immediately.

**File:** `src/npc_engine/type_registry/registry.py`

Change `build_runtime_models` to return a `TypeRegistry` (the final one) rather than a separate models object, eliminating the second construction:

```python
def build_type_registry(*, base_schema: SchemaConfig, extension_sources: tuple[str, ...]) -> TypeRegistry:
    loaded_extensions = load_registry_extensions(extension_sources=extension_sources)
    extension_registry = merge_registry(base_schema=base_schema, extensions=loaded_extensions)

    # Two-phase build: (1) structural registry for model generation, (2) final registry with models.
    # This is intentional — runtime_models require the node/edge type definitions to be present.
    structural = TypeRegistry(
        schema_version=extension_registry.schema_version,
        base_node_types=load_base_node_types(),
        base_edge_types=load_base_edge_types(),
        core_types=extension_registry.core_types,
        custom_node_types=extension_registry.custom_node_types,
        custom_edge_types=extension_registry.custom_edge_types,
        enum_extensions=extension_registry.enum_extensions,
    )
    runtime_models = build_runtime_models(registry=structural)
    return structural.model_copy(update={
        "node_models": runtime_models.node_models,
        "edge_models": runtime_models.edge_models,
    })
```

If `TypeRegistry` is frozen (no `model_copy`), use `TypeRegistry(**{**structural.model_dump(), "node_models": ..., "edge_models": ...})` instead. Either way, the caller now builds one final instance from the structural one, with the comment explaining the two-phase necessity.

---

## Phase 2 — Engine Configuration Baseline

> Prerequisite: all Phase 1 tests pass. Every new engine added from Phase 4 onward must follow the patterns established here.

---

### 2.1 Create `MemoryConsolidationEngine` `llm_config.yaml` + contract YAML — M

**Goal:** Make memory consolidation visible to the startup validator and follow the same config pattern as dialogue and quest_generation.

**New file:** `src/npc_engine/engines/memory_consolidation/llm_config.yaml`

```yaml
engine: memory_consolidation
llm:
  backend: ollama
  model: mistral:7b-instruct   # smaller than mixtral — summarization doesn't need full capacity
  temperature: 0.4
  max_tokens: 300
  top_p: 0.9
  stop_sequences: []
prompt:
  name: consolidation_v1
  version: 1
output_schema_ref: memory_consolidation_response_v1
fallback:
  policy: graceful_degradation
  tiers:
    - full
timeouts_ms:
  full: 30000
```

**New file:** `src/npc_engine/engines/contracts/memory_consolidation_engine.yaml` (contract YAML; match the pattern of the existing dialogue/quest_generation contracts in the `contracts/` directory)

Remove the hardcoded constants from `memory_consolidation_engine.py`:

```python
# Before:
_MAX_TOKENS = 300
_TEMPERATURE = 0.4

# After: load from llm_config.yaml
# The engine will accept max_tokens/temperature from its injected LLM client
```

Wire the engine into `validate_all_engine_llm_configs` so the startup validator sees it.

---

### 2.2 Fix `consolidate_memories` singleton — use proper `llm_config.yaml` — S

**Depends on:** 2.1 creating the YAML.

`src/npc_engine/api/dependency_singletons.py` — update `get_memory_consolidation_engine`:

```python
@lru_cache
def get_memory_consolidation_engine():
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import MemoryConsolidationEngine
    from npc_engine.engines.llm.factory import create_llm_client_for_engine

    settings = get_settings()
    engine_config = get_engine_model_config_for("memory_consolidation")   # ← now loads own YAML
    llm_client = create_llm_client_for_engine(engine_config, settings)
    return MemoryConsolidationEngine(
        session_store=get_session_store(),
        llm_client=llm_client,
        turn_threshold=5,
        clear_turns_after=False,
    )
```

Add `get_memory_consolidation_engine.cache_clear()` to `lifespan` in `main.py`.

---

### 2.3 Fix `EngineTimeoutsMs` schema — allow per-engine tier declaration — S

**Problem:** `EngineTimeoutsMs` mandates `full`, `graph_only`, and `canned` keys. Engines with fewer fallback tiers (e.g., quest_generation has only `full` and `deterministic`) must lie in their YAML.

**File:** `src/npc_engine/engines/engine_config_models.py` (formerly `engines/llm_config_models.py` after 1.5)

Make fields optional with `None` default:

```python
class EngineTimeoutsMs(BaseModel):
    full: int = Field(gt=0)
    graph_only: int | None = Field(default=None, gt=0)
    canned: int | None = Field(default=None, gt=0)
    deterministic: int | None = Field(default=None, gt=0)  # quest_generation tier
    model_config = ConfigDict(frozen=True, extra="forbid")
```

Remove the validator that errors on undeclared keys. Update quest_generation's YAML to remove the lying `graph_only`/`canned` entries:

```yaml
timeouts_ms:
  full: 30000
  deterministic: 100
```

---

### 2.4 Fix `@lru_cache` — add `cache_clear()` for rules-based engines — M

**Problem:** `get_faction_politics_engine`, `get_story_pacing_engine`, `get_pricing_engine`, `get_trade_engine`, `get_quest_generation_engine` are `@lru_cache` singletons whose rules YAMLs are frozen at first access. Hot-reload requires a process restart. In tests, state leaks between test modules.

**File:** `src/npc_engine/main.py` — in `lifespan`, add cache clears for all rules-based engines:

```python
get_faction_politics_engine.cache_clear()
get_story_pacing_engine.cache_clear()
get_pricing_engine.cache_clear()
get_trade_engine.cache_clear()
get_quest_generation_engine.cache_clear()
get_routine_engine.cache_clear()
```

Reload (call each to warm the new cache) after clearing if you want to fail-fast on bad rules at startup:

```python
get_faction_politics_engine()
get_story_pacing_engine()
get_quest_generation_engine()
```

**In tests:** Add a `conftest.py` fixture at the suite root that calls `cache_clear()` for all singletons in `autouse=True` teardown.

---

### 2.5 Fix `QuestGenerationEngine` — use `llm_config.max_tokens` — S

**File:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py`

The hardcoded `256` in `_ask_llm_for_fills` and `_generate_flavor` must use `engine_config.llm.max_tokens`. Pass the config to the engine constructor:

```python
class QuestGenerationEngine:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        templates: list[QuestTemplateRecord],
        prompts_dir: Path,
        max_tokens: int = 256,   # ← injected from llm_config.yaml
    ) -> None:
        self._max_tokens = max_tokens
        ...
```

`dependency_singletons.py` — pass `max_tokens=engine_config.llm.max_tokens` when constructing `QuestGenerationEngine`.

---

### 2.6 Fix bare `except Exception` in `QuestGenerationEngine` — S

**Problem:** The bare `except Exception` in `QuestGenerationEngine` swallows programmer errors (attribute errors, type errors) silently, degrading to deterministic fallback for all error kinds.

**File:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py`

In `_ask_llm_for_fills` and `_generate_flavor`, replace:

```python
# Before:
except Exception:
    ...

# After: only catch LLM errors and validation errors
except (LLMTimeoutError, LLMRequestError) as error:
    _logger.warning("LLM error during slot fill: %s", error)
    ...
except ValidationError as error:
    _logger.warning("Schema validation error: %s", error)
    ...
# programmer errors (AttributeError, TypeError, etc.) bubble up naturally
```

---

### 2.7 Add HTTP connection pooling — shared `httpx.AsyncClient` per engine — S

**Problem:** `OllamaAdapter` creates a new `httpx.AsyncClient` per HTTP call — no connection reuse. High-frequency dialogue calls never reuse TCP connections.

**File:** `src/npc_engine/engines/llm/ollama_adapter.py`

Add a shared client, initialized in `__init__` and reused across calls:

```python
class OllamaAdapter(LLMClientProtocol):
    def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)  # ← shared client

    async def close(self) -> None:
        """Release the shared HTTP client. Call at shutdown."""
        await self._client.aclose()

    async def generate(self, ...) -> str:
        # Replace:   async with httpx.AsyncClient(timeout=...) as client:
        # With:      client = self._client
        try:
            response = await self._client.post(...)
            response.raise_for_status()
        ...
```

Repeat for `generate_structured` and `stream`. Do the same for `MistralAdapter`.

In `dependency_singletons.py`, call `adapter.close()` in `lifespan` teardown for each singleton that owns an adapter.

**Note:** `MistralAdapter` also creates per-call clients; same pattern.

---

### 2.8 Add LLM health/readiness probe — S

**Problem:** A misconfigured `OLLAMA_API_URL` only surfaces on the first real request.

**Files:** `src/npc_engine/engines/llm/protocols.py`, `src/npc_engine/engines/llm/ollama_adapter.py`, `src/npc_engine/api/routes/system.py`

Add to `LLMClientProtocol`:

```python
async def health_check(self) -> bool:
    """Return True if the backend is reachable and ready. Non-raising."""
```

`OllamaAdapter` implementation:

```python
async def health_check(self) -> bool:
    try:
        response = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False
```

`MistralAdapter` and `MockLLMAdapter`: implement trivially (`return True` for mock).

`src/npc_engine/main.py` lifespan — probe after connecting:

```python
dialogue_adapter = get_llm_client(...)
if not await dialogue_adapter.health_check():
    _logger.warning("LLM backend health check failed — starting degraded")
```

`system.py` readiness route: include LLM health in the `/readiness` response.

---

### 2.9 Make `TypeRegistry`-derived models used for write validation — M

**Problem:** `build_runtime_models` builds Pydantic models from the registry but no engine uses them. Engines hand-roll Cypher with hardcoded labels.

**File:** New service-layer helper `src/npc_engine/type_registry/node_validator.py`

```python
def validate_node_write(
    registry: TypeRegistry,
    node_type: str,
    props: dict,
) -> dict:
    """Validate and coerce props against the registry-derived model for node_type.
    Returns the validated props dict. Raises ValidationError on failure."""
    model_cls = registry.node_models.get(node_type)
    if model_cls is None:
        return props   # unknown type — pass through
    return model_cls.model_validate(props).model_dump(exclude_none=True)
```

Wire into `EventHandler`, `QuestLifecycleEngine`, and any other engine that writes graph nodes with hardcoded labels.

---

### 2.10 Make LLM factory extensible — plugin registration — M

**Problem:** `factory.py` is a closed `if/elif` chain. Adding a new backend (vLLM, llama.cpp) requires editing 4 files in 3 packages.

**File:** `src/npc_engine/engines/llm/factory.py`

```python
from typing import Callable

_REGISTRY: dict[str, Callable[..., LLMClientProtocol]] = {}

def register_backend(name: str, constructor: Callable[..., LLMClientProtocol]) -> None:
    _REGISTRY[name] = constructor

def create_llm_client_for_engine(engine_config, settings) -> LLMClientProtocol:
    backend = engine_config.llm.backend
    constructor = _REGISTRY.get(backend)
    if constructor is None:
        raise ValueError(f"Unsupported backend: {backend}")
    return constructor(engine_config=engine_config, settings=settings)
```

Register built-ins at module load time. New adapters call `register_backend(...)` from their own module.

---

### 2.11 Fix `BaseEngine` Protocol — M `TickScheduler` type constraint — S

**File:** `src/npc_engine/scheduler/tick_scheduler.py`

Change constructor parameters from `object` to `BaseEngine`:

```python
from npc_engine.engines.base_engine import BaseEngine

class TickScheduler:
    def __init__(
        self,
        clock: GameClock,
        gossip_handler: BaseEngine,
        event_handler: BaseEngine,
        routine_engine: BaseEngine,
        faction_politics_engine: BaseEngine,
        story_pacing_engine: BaseEngine,
        ...
    ) -> None:
```

Ensure every engine passed to `TickScheduler` implements `BaseEngine` (adds `run_tick` and any other required methods to the protocol).

---

### 2.12 Resolve circular import in `dependency_singletons.py` — S

**Problem:** `create_llm_client_for_engine` is imported inside a function body in `dependency_singletons.py` to work around a circular import.

**Steps:**
1. Identify the circular import chain (likely: `dependency_singletons` → `factory` → `engines/llm_config_loader` → `dependency_singletons`).
2. Extract the shared type from whichever module is the root of the cycle into a separate `src/npc_engine/engines/llm/types.py` with no intra-project imports.
3. Move the in-function import to the module top-level.

---

## Phase 3 — Retrieval Foundation

> Must complete before graph expansion adds new node types that need indexing, scoring, and retrieval.

---

### 3.1 Replace character-bucket hash with `sentence-transformers` — M

**Problem:** `embedding_index._embed_text` is a 16-dimensional character-bucket hash. It is not semantic. `Settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"` is dead config — no model is loaded. Tier B/C results are effectively random.

**New file:** `src/npc_engine/retrieval/sentence_encoder.py`

```python
"""sentence_encoder.py — Lazy-loaded sentence-transformers encoder with GPU/CPU auto-detect."""

from __future__ import annotations
from functools import lru_cache

import torch
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_encoder(model_name: str) -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else (
        "mps" if torch.backends.mps.is_available() else "cpu"
    )
    return SentenceTransformer(model_name, device=device)


def embed(text: str, model_name: str) -> list[float]:
    """Return a normalized float vector for text."""
    encoder = get_encoder(model_name)
    vector = encoder.encode(text, normalize_embeddings=True)
    return vector.tolist()
```

`src/npc_engine/retrieval/embedding_index.py` — replace `_embed_text`:

```python
EMBED_DIMENSION = 384   # all-MiniLM-L6-v2 output dimension

def _embed_text(text: str, model_name: str) -> list[float]:
    if text == "":
        return [0.0] * EMBED_DIMENSION
    from npc_engine.retrieval.sentence_encoder import embed
    return embed(text, model_name=model_name)
```

Update `EmbeddingIndex.__init__` to accept and store `model_name: str`. Update `upsert` and `search` to pass `model_name` to `_embed_text`.

`dependency_singletons.py` — pass `Settings.EMBEDDING_MODEL` when constructing `EmbeddingIndex`.

**Dependencies to add:** `sentence-transformers>=2.6.0`, `torch>=2.0.0` (already likely present; add to `pyproject.toml` if not).

**Cold-start note:** First call loads the model (~80 MB) and caches it. This is acceptable at startup (during the first `embedding_reconciler` run). Add a log line: `_logger.info("Loading embedding model %s on %s", model_name, device)`.

---

### 3.2 Fix recency scoring — use game time, not wall-clock time — S

**Problem:** `context_scoring._extract_recency_score` decays based on `datetime.now(UTC) - parsed_timestamp`. For graph nodes created recently (their DB row inserted minutes ago), the recency score is high regardless of the in-game time of the event. Ancient game events appear "very recent" because their DB rows are new.

**Fix:** Add a `game_time` epoch parameter to the scoring pipeline. For now, a pragmatic fallback: if the timestamp string matches a game-time format (year/season/day) rather than an ISO 8601 string, score it using a fixed reference epoch instead of wall clock.

`src/npc_engine/retrieval/context_scoring.py` — add a game-epoch normalizer:

```python
# Game-time fields that should NOT be scored against wall-clock time
_GAME_TIME_FIELDS = frozenset({"created_at_game_time", "occurred_at_game_time"})

def _extract_recency_score(payload: dict[str, Any]) -> float:
    # Skip game-time fields; only score real ISO timestamps
    for field in ("occurred_at", "updated_at", "last_graph_updated_at", "created_at"):
        if field in _GAME_TIME_FIELDS:
            continue
        raw_value = payload.get(field)
        if not isinstance(raw_value, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
        return _normalize_ratio(1.0 - min(age_hours / 72.0, 1.0))
    return 0.0
```

Long-term fix (Phase 6): pass the current game tick to the scoring pipeline so game-time timestamps can be scored relative to current in-game time.

---

### 3.3 Map `emotional_charge`, `urgency`, `confidence` into severity scoring — S

**Problem:** `_extract_severity_score` only reads the `severity` field. `Memory.emotional_charge`, `Goal.urgency`, and `Belief.confidence` all return `0.0` for severity and consequently lose all ranking matches.

`src/npc_engine/retrieval/context_scoring.py`:

```python
def _extract_severity_score(payload: dict[str, Any]) -> float:
    # Direct severity field (Event, Secret)
    raw = payload.get("severity")
    if isinstance(raw, (int, float)):
        return _normalize_ratio(float(raw) / 100.0)

    # Goal urgency (0–100)
    urgency = payload.get("urgency")
    if isinstance(urgency, (int, float)):
        return _normalize_ratio(float(urgency) / 100.0)

    # Belief confidence (0–100)
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        return _normalize_ratio(float(confidence) / 100.0)

    # Memory emotional charge (-100 to 100) — use absolute value
    charge = payload.get("emotional_charge")
    if isinstance(charge, (int, float)):
        return _normalize_ratio(abs(float(charge)) / 100.0)

    return 0.0
```

---

### 3.4 Cap Tier 0 in the active `context_budget_enforcer` — S

**Problem:** The active enforcer (`context_budget_enforcer.enforce_context_budget`) never validates Tier 0. A large `WorldState` silently consumes all available prompt space. The cap (`TIER0_MAX_TOKENS = 380`) exists only in the unused legacy `token_budget_enforcer.py`.

`src/npc_engine/retrieval/context_budget_enforcer.py` — add a Tier 0 guard:

```python
TIER0_MAX_TOKENS = 380   # matches legacy enforcer constant

def enforce_context_budget(...) -> MergedContext:
    cache = compression_cache or ContextCompressionCache()

    tier0_items = [item for item in context.items if item.tier == "tier0"]
    tier_a_items = [item for item in context.items if item.tier == "tierA"]
    tier_b_items = [item for item in context.items if item.tier == "tierB"]
    tier_c_items = [item for item in context.items if item.tier == "tierC"]

    # NEW: cap tier0
    tier0_tokens = sum(estimate_tokens(item.text) for item in tier0_items)
    if tier0_tokens > TIER0_MAX_TOKENS:
        raise ContextBudgetError(
            tier="tier0",
            used_tokens=tier0_tokens,
            budget_tokens=TIER0_MAX_TOKENS,
            detail="Tier 0 (world + emotion) exceeds non-compressible cap.",
        )
    ...
```

---

### 3.5 Increase `PROMPT_TOKEN_BUDGET` from 800 → 2500 — XS

**Depends on:** 1.9, 1.10, 1.11, 1.12, 3.4 (Phase 1 savings + Tier 0 cap).

`src/npc_engine/config.py` (or wherever `PROMPT_TOKEN_BUDGET` is set as a Setting):

```python
PROMPT_TOKEN_BUDGET: int = 2500   # was 800; Mixtral has 32K context, system ≈ 256 tokens
```

Monitor for `ContextBudgetError` increases after this change. The typical Tier 0 + A is ~1400 tokens (from report 4 analysis); with Phase 1 savings (~30% reduction) it becomes ~1000 tokens, well within 2500.

---

### 3.6 Parallelize Tier A queries with `asyncio.gather` — M

**Problem:** `build_serialized_context` makes ~13 sequential Neo4j round trips. At 5–15 ms each, the lower bound is ~65 ms before the LLM call. Expected reduction: ~130 ms → ~40–60 ms.

**File:** `src/npc_engine/retrieval/context_builder.py`

True dependency chain: `get_npc_location_id` → `get_location_context`. Everything else is independent.

Replace the sequential fetch sequence with:

```python
import asyncio

# Stage 1: character + vector search in parallel (vector search depends only on player_message)
character_bundle_task = asyncio.create_task(
    get_character_with_relations(session=session, npc_id=npc_id)
)
vector_task = asyncio.create_task(
    embedding_index.search(query=player_message, top_k=settings.RAG_TOP_K)
) if not skip_rag else None

character_bundle = await character_bundle_task
tier_b_results = await vector_task if vector_task else []

# Stage 2: location_id (depends on character_bundle for npc_id — but npc_id is already known)
location_id = await get_npc_location_id(session=session, npc_id=npc_id)

# Stage 3: all independent graph fetches + location_context in parallel
results = await asyncio.gather(
    get_location_context(session=session, location_id=location_id),
    get_events_for_npc(session=session, npc_id=npc_id, limit=settings.RAG_TOP_K),
    get_reputation_context_for_npc(session, npc_id=npc_id, player_id=player_id or "", ...),
    get_memories_for_character(session, character_id=npc_id, k=3),
    get_beliefs_for_character(session, character_id=npc_id, k=3),
    get_goals_for_character(session, character_id=npc_id, k=3, status_filter="active"),
    get_items_for_character(session, character_id=npc_id, k=10),
    get_secrets_for_character(session, character_id=npc_id, k=3),
    get_debts_for_character(session, character_id=npc_id, k=5),
)
location_ctx, events, reputation_items, memories, beliefs, goals, items, secrets, debts = results
```

Pass `character_bundle` to `retrieve_tier_a_context` (now just assembles `ContextItem` lists from pre-fetched data — refactor that function into a pure assembly step).

---

### 3.7 Add `KNOWS_ABOUT` filter to vector retrieval — M

**Problem:** Vector search queries the global corpus. An NPC in a remote region can surface events from anywhere. There is no `KNOWS_ABOUT` filter on retrieval, so the NPC can "know" about events they have no graph connection to.

**Files:** `src/npc_engine/retrieval/embedding_index.py`, `src/npc_engine/retrieval/context_builder.py`

Add a `filter_ids: set[str] | None` parameter to `EmbeddingIndex.search`:

```python
async def search(self, query: str, top_k: int, filter_ids: set[str] | None = None) -> list[VectorSearchResult]:
    query_vector = _embed_text(query, self._model_name)
    results = await self._vector_store.search(query_vector=query_vector, top_k=top_k)
    if filter_ids is not None:
        results = [r for r in results if r["id"] in filter_ids]
    return results[:top_k]
```

In `context_builder.py`, before the vector search, fetch the set of event IDs the NPC `KNOWS_ABOUT`:

```python
known_event_ids: set[str] | None = await get_known_event_ids_for_npc(session, npc_id=npc_id)
tier_b_results = await embedding_index.search(
    query=player_message,
    top_k=settings.RAG_TOP_K,
    filter_ids=known_event_ids,
)
```

Add `get_known_event_ids_for_npc` as a new graph query:

```cypher
MATCH (c:Character {id: $npc_id})-[:KNOWS_ABOUT]->(e:Event)
RETURN e.id AS id
```

Return a `set[str]`.

---

## Phase 4 — Cross-Domain Graph Primitives

> Prerequisite: Phase 3 complete. New nodes added here will be indexed with real embeddings, scored correctly, and retrieved within knowledge boundaries.

---

### 4.1 `WAS_AT` edge — Location History — S

**Schema:**

```python
# Edge: Character → Location
class WasAtEdge:
    arrived_at_tick: int
    departed_at_tick: int
    reason: Literal["routine", "quest", "fled", "ordered"]
    tick_duration: int
```

**Service API** (`src/npc_engine/graph/location_history_service.py`):

```python
async def record_departure(
    session: AsyncSession,
    character_id: str,
    location_id: str,
    arrived_at_tick: int,
    departed_at_tick: int,
    reason: str,
) -> None:
    """Archive the current LOCATED_AT as a WAS_AT edge before movement."""

async def get_location_history(
    session: AsyncSession,
    character_id: str,
    limit: int = 20,
) -> list[dict]:
    """Return WAS_AT edges in reverse chronological order."""

async def get_alibi_window(
    session: AsyncSession,
    character_id: str,
    from_tick: int,
    to_tick: int,
) -> list[dict]:
    """Return all locations a character was at during the tick window."""

async def prune_location_history(
    session: AsyncSession,
    older_than_ticks: int,
    compact_to_summary: bool = True,
) -> int:
    """Remove WAS_AT edges older than threshold; optionally create BIOGRAPHICAL_STAY summaries."""
```

**Integration:** `RoutineEngine.move_npc` — before overwriting `LOCATED_AT`, call `record_departure`.

**Test:** After moving an NPC, verify `get_location_history` returns the previous location.

---

### 4.2 `CAUSED_BY` edge — Consequence Provenance — S + M retrofit

**Schema:**

```python
# Edge: (Event | Quest | FactionStandingEvent | Rumor) → Event
class CausedByEdge:
    causation_strength: int   # 0–100
    cause_type: Literal["direct", "indirect", "narrative"]
    tick_lag: int             # ticks between cause and effect
```

**Service API** (`src/npc_engine/graph/causality_service.py`):

```python
async def record_causation(
    session: AsyncSession,
    effect_node_id: str,
    effect_node_type: str,
    cause_event_id: str,
    causation_strength: int,
    cause_type: str,
    tick_lag: int,
) -> None:
    """Write a CAUSED_BY edge from effect node to cause event."""

async def get_consequence_chain(
    session: AsyncSession,
    root_event_id: str,
    max_depth: int = 5,
) -> list[dict]:
    """Walk CAUSED_BY edges forward from a root event and return the causal chain."""

async def get_causes(
    session: AsyncSession,
    node_id: str,
    node_type: str,
) -> list[dict]:
    """Return direct cause events for a given node."""
```

**Retrofit (M effort):** After adding the service, update:
- `EventHandler`: when a disruption rule fires and creates/overrides events, write `CAUSED_BY` linking the new event to the triggering event.
- `QuestGenerationEngine`: after quest creation, if `cause_event_id` is passed, write `CAUSED_BY`.
- `FactionPoliticsEngine`: after `set_standing()`, write `CAUSED_BY` if the standing change was triggered by an event.

**Test:** Create an event chain A→B→C; verify `get_consequence_chain(A)` returns B and C.

---

### 4.3 `WITNESSED` edge — Character → Character — M

**Schema:**

```python
# Edge: Character → Character (event-keyed)
class WitnessedEdge:
    event_id: str
    action_type: str          # "stole", "helped", "attacked", "lied", ...
    witnessed_at_tick: int
    clarity: int              # 0–100; affects later misremembering
    interpretation: str       # witness's biased reading
    disclosed: bool           # True once the witness has told someone
```

**Service API** (`src/npc_engine/graph/witnessed_service.py`):

```python
async def record_witness(
    session: AsyncSession,
    witness_id: str,
    subject_id: str,
    event_id: str,
    action_type: str,
    tick: int,
    clarity: int,
    interpretation: str,
) -> None:
    """Create a WITNESSED edge from witness to subject."""

async def get_witnesses_of_event(
    session: AsyncSession,
    event_id: str,
) -> list[dict]:
    """Return all characters who witnessed an event."""

async def get_witnessed_by(
    session: AsyncSession,
    subject_id: str,
    limit: int = 20,
) -> list[dict]:
    """Return all WITNESSED edges pointing at subject_id (what others have seen them do)."""

async def get_undisclosed_witnesses(
    session: AsyncSession,
    npc_id: str,
) -> list[dict]:
    """Return WITNESSED edges for npc_id where disclosed=False — latent rumor sources."""

async def mark_disclosed(
    session: AsyncSession,
    witness_id: str,
    subject_id: str,
    event_id: str,
) -> None:
    """Set disclosed=True on a WITNESSED edge."""
```

**New engine hook:** After `EventHandler` processes a high-severity event, query NPCs at the event's location (`LOCATED_AT`) and create `WITNESSED` edges for each with a `clarity` based on their proximity and sight-line attributes.

**Gossip integration:** `GossipHandler.propagate` — when propagating gossip about an event, check for `WITNESSED` edges with `disclosed=False` as authoritative rumor seeds.

**Memory integration:** `MemoryConsolidationEngine` — memories with a linked `WITNESSED` edge inherit `clarity` as `vividness`.

**Test:** Seed an event at a location with 2 NPCs present; verify both have `WITNESSED` edges to the actor.

---

### 4.4 `GROUP` node + Membership Edges — M

**Schema:**

```python
class GroupNode:
    id: str
    name: str
    kind: Literal["clique", "conspiracy", "family", "crew", "fellowship", "mob"]
    cohesion: int             # 0–100
    is_secret: bool
    formed_at_tick: int
    dissolved_at_tick: int | None
    home_location_id: str | None

# Edges:
class BelongsToGroupEdge:   # Character → Group
    role: str
    joined_at_tick: int
    commitment: int         # 0–100

# Group → Secret (GROUP_SHARES_SECRET)
# Group → Goal   (GROUP_PURSUES)
# Group → Group or Character (OPPOSES)
```

**Service API** (`src/npc_engine/graph/group_service.py`):

```python
async def create_group(session, *, name, kind, cohesion, is_secret, formed_at_tick, home_location_id=None) -> str
async def add_member(session, *, group_id, character_id, role, joined_at_tick, commitment) -> None
async def remove_member(session, *, group_id, character_id) -> None
async def get_groups_for_character(session, character_id, include_dissolved=False) -> list[dict]
async def get_members(session, group_id) -> list[dict]
async def dissolve_group(session, *, group_id, tick) -> None
async def get_shared_secrets(session, group_id) -> list[dict]
async def get_group_goals(session, group_id) -> list[dict]
```

**New engine — clique formation** (`src/npc_engine/engines/clique/clique_formation_engine.py`):

On each tick:
1. Query pairs of co-located characters with `RELATES_TO.affection > 70` (bidirectional).
2. For pairs meeting the threshold, if no group already exists for them, create one (`kind="clique"`, low cohesion initially).
3. On cohesion decay (no recent co-location), dissolve.

Wire into `TickScheduler`.

**Test:** Create 3 characters with high mutual affection at the same location; run the clique formation engine; verify a GROUP node with 3 `BELONGS_TO_GROUP` edges.

---

### 4.5 `RUMOR` node + Mutation Tree — L

**Schema:**

```python
class RumorNode:
    id: str
    content: str
    origin_event_id: str | None   # None if pure fabrication
    created_at_tick: int
    mutation_distance: int        # edit distance from origin
    severity: int                 # 0–100
    is_fabricated: bool

# Edges:
class DerivedFromEdge:     # Rumor → Rumor (parent mutation)
    mutation_type: str     # "distorted", "exaggerated", "denied"

class BelievesRumorEdge:   # Character → Rumor
    confidence: int        # 0–100
    learned_at_tick: int
    from_character_id: str

class ContradictsEdge:     # Rumor → Rumor (alternate version of same event)
```

**Service API** (`src/npc_engine/graph/rumor_service.py`):

```python
async def create_rumor(session, *, content, origin_event_id=None, created_at_tick, mutation_distance=0, severity, is_fabricated=False) -> str
async def create_derived_rumor(session, *, parent_rumor_id, content, mutation_type, created_at_tick) -> str
async def believe_rumor(session, *, character_id, rumor_id, confidence, tick, from_character_id) -> None
async def get_rumors_for_character(session, character_id, min_confidence=0) -> list[dict]
async def get_rumor_tree(session, rumor_id) -> list[dict]
async def get_rumor_believers(session, rumor_id) -> list[dict]
async def get_rumors_about_event(session, event_id) -> list[dict]
```

**Gossip engine rewrite:** Replace in-edge distortion fields on `KNOWS_ABOUT` with rumor node creation when distortion crosses a configurable threshold. The transition is backward-compatible: `KNOWS_ABOUT` edges continue to exist; distortion fields can be deprecated over multiple releases.

New gossip logic:
1. When distortion is minor → update `KNOWS_ABOUT` edge fields as before.
2. When distortion exceeds threshold → create a new `RUMOR` node derived from the parent, create `BELIEVES_RUMOR` for the receiver.

**Memory integration:** When consolidating memories, if a `BELIEVES_RUMOR` edge references a rumor that `CONTRADICTS` a known belief, trigger an immediate consolidation pass for that NPC.

**Dialogue integration:** `context_builder` adds `BELIEVES_RUMOR` edges (top 3 by confidence, relevant to the player message) to Tier A.

**Test:** Propagate a rumor through a chain of 5 NPCs; verify `mutation_distance` increments and a `DERIVED_FROM` chain is queryable.

---

## Phase 5 — RPG Depth Additions

> Builds on Phase 4 primitives. Each item can be shipped independently.

---

### 5.1 `SKILL` / `TRAIT` nodes + Quest Gating — M

**Schema:**

```python
class SkillNode:
    id: str
    name: str
    category: Literal["combat", "social", "craft", "knowledge"]
    description: str

class HasSkillEdge:     # Character → Skill
    level: int          # 0–100
    xp: int
    last_used_at_tick: int

class TraitNode:
    id: str
    name: str
    description: str

class HasTraitEdge:     # Character → Trait
    intensity: int      # 0–100
    is_secret: bool

class RequiresSkillEdge:  # QuestTemplate → Skill
    min_level: int
```

**Service API** (`src/npc_engine/graph/skill_service.py`):

```python
async def add_skill(session, *, character_id, skill_id, level, xp=0) -> None
async def get_skills(session, character_id) -> list[dict]
async def increment_xp(session, *, character_id, skill_id, xp_delta) -> int   # returns new level
async def get_characters_with_skill(session, skill_id, min_level=0) -> list[dict]
async def check_skill_threshold(session, *, character_id, skill_id, min_level) -> bool
```

**Quest slot validator extension:** Before accepting a candidate character for a slot with `REQUIRES_SKILL`, call `check_skill_threshold`. Add violation type `"skill_threshold_not_met"` to `SlotValidator`.

**New engine — skill progression** (`src/npc_engine/engines/skill/skill_progression_engine.py`):
On quest completion, for each participating character, call `increment_xp` for relevant skills.

---

### 5.2 `PLEDGE` edge — Character → Character — M

**Schema:**

```python
class PledgeEdge:
    pledge_type: Literal["protect", "serve", "kill", "marry", "mentor", "fealty", "vendetta"]
    sworn_at_tick: int
    expires_at_tick: int | None
    witness_character_id: str | None
    binding_event_id: str | None
    is_active: bool
    severity: int   # magnitude of social fallout if broken (0–100)
```

**Service API** (`src/npc_engine/graph/pledge_service.py`):

```python
async def create_pledge(session, *, pledger_id, pledgee_id, pledge_type, tick, expires_at_tick=None, witness_id=None, binding_event_id=None, severity=50) -> None
async def get_pledges_for_character(session, character_id, active_only=True) -> list[dict]
async def break_pledge(session, *, pledger_id, pledgee_id, pledge_type, tick) -> None   # sets is_active=False, generates EVENT
async def check_pledge_violations(session, *, pledger_id, tick) -> list[dict]
```

**New engine — oath violation** (`src/npc_engine/engines/oath/oath_engine.py`):
Tick-level scan: for each active pledge, check whether the pledger's recent actions (via `PARTICIPATED_IN` or `WITNESSED` edges) constitute a violation. On violation: call `break_pledge`, generate a high-severity `EVENT`, apply large `STANDS_WITH` swing.

**Context integration:** `context_builder` adds active pledges for the NPC to Tier A (low-priority bucket).

---

### 5.3 `FACTION_STANDING_EVENT` node — append-only history — S

**Schema:**

```python
class FactionStandingEventNode:
    id: str
    src_faction_id: str
    dst_faction_id: str
    delta: int          # signed change
    new_standing: int   # standing after change
    tick_id: int
    cause_event_id: str | None
    cause_rule_id: str | None
```

**Service API** (`src/npc_engine/graph/faction_history_service.py`):

```python
async def record_standing_change(session, *, src_faction_id, dst_faction_id, delta, new_standing, tick, cause_event_id=None, cause_rule_id=None) -> str
async def get_standing_history(session, src_faction_id, dst_faction_id, limit=50) -> list[dict]
async def get_standing_trend(session, src_faction_id, dst_faction_id, window_ticks=100) -> float   # positive/negative trajectory
```

**Integration:** `FactionPoliticsEngine.set_standing()` — after updating `STANDS_WITH`, call `record_standing_change`.

---

### 5.4 `TREATY` node + Treaty Engine — M

**Schema:**

```python
class TreatyNode:
    id: str
    parties: list[str]   # faction IDs
    terms: str
    signed_at_tick: int
    expires_at_tick: int | None
    binding_event_id: str | None
    status: Literal["active", "broken", "expired"]

class BoundByEdge:   # Faction → Treaty
    role: Literal["signatory", "guarantor"]
```

**Service API** (`src/npc_engine/graph/treaty_service.py`):

```python
async def create_treaty(session, *, parties, terms, signed_at_tick, expires_at_tick=None, binding_event_id=None) -> str
async def get_active_treaties(session, faction_id) -> list[dict]
async def expire_treaty(session, treaty_id, tick) -> None
async def break_treaty(session, *, treaty_id, breaking_faction_id, tick) -> None   # generates EVENT
```

**New engine — treaty** (`src/npc_engine/engines/treaty/treaty_engine.py`):
Tick-level: query treaties where `expires_at_tick <= current_tick` and call `expire_treaty`. Check for violations by comparing treaty terms against recent faction actions.

---

## Phase 6 — Retrieval Quality Lift

> Requires Phase 3's real embedding to be meaningful. Phase 4 graph nodes enrich what can be retrieved.

---

### 6.1 Two-pass belief/goal/secret retrieval — M

**Problem:** Top-3 by intrinsic intensity may be entirely irrelevant to the current player message.

**File:** `src/npc_engine/retrieval/context_builder.py`

Replace flat top-3 fetches with a two-pass approach:

```python
# Fetch top-10 by intrinsic score
beliefs_top10 = await get_beliefs_for_character(session, character_id=npc_id, k=10)

# Re-rank by keyword overlap with player_message, keep top-3
def _keyword_overlap(text: str, query: str) -> float:
    query_tokens = set(query.lower().split())
    text_tokens = set(text.lower().split())
    return len(query_tokens & text_tokens) / max(1, len(query_tokens))

beliefs = sorted(
    beliefs_top10,
    key=lambda b: _keyword_overlap(b.get("content", ""), player_message),
    reverse=True,
)[:3]
```

Apply same pattern to goals and secrets.

---

### 6.2 Add `RELATES_TO.trust` as event scoring signal — M

**Problem:** The `relation` weight (0.20) uses vector cosine similarity for Tier B/C items and falls back to `item.priority / 100.0` for Tier A. The actual trust relationship between the NPC and an event's participants is never consulted.

**File:** `src/npc_engine/retrieval/context_scoring.py`

Add a graph query that fetches trust scores for the NPC toward event participants. Pass as an optional `trust_scores: dict[str, float]` parameter into `rank_tier_items` and use in `_extract_relation_score`.

New graph query in `src/npc_engine/graph/trust_queries.py`:

```python
async def get_trust_scores_for_events(
    session: AsyncSession,
    npc_id: str,
    event_ids: list[str],
) -> dict[str, float]:
    """Return normalized trust (0–1) from npc to the actor of each event."""
```

Cypher: for each event, `MATCH (npc)-[r:RELATES_TO]->(actor {id: e.actor_id}) RETURN e.id, r.trust / 100.0`.

---

### 6.3 Conversation-aware query expansion — S

**Problem:** Vector search uses only the current `player_message`. Follow-up messages ("What about the leader?") lack context for pronouns and references.

**File:** `src/npc_engine/retrieval/context_builder.py`

Before the vector search, expand the query:

```python
def _expand_query(player_message: str, session_turns: list[str]) -> str:
    recent = " ".join(session_turns[-2:]) if len(session_turns) >= 2 else ""
    return f"{recent} {player_message}".strip() if recent else player_message

expanded_query = _expand_query(player_message, session_turns)
tier_b_results = await embedding_index.search(query=expanded_query, top_k=..., filter_ids=...)
```

---

### 6.4 Player quest state as a retrieval signal — M

**Problem:** The `quest` scoring dimension returns `1.0` based on key string substring match only. No actual quest data is fetched.

**New query** (`src/npc_engine/graph/quest_queries.py`):

```python
async def get_active_quest_for_player(
    session: AsyncSession,
    player_id: str,
) -> dict | None:
    """Return the player's current active quest node (targets, objectives, giver_id)."""
```

In `context_builder.py`:
- Fetch player quest alongside other Tier A data (in the `asyncio.gather` batch).
- Add it as a Tier A item with high priority.
- Pass `active_quest` to `rank_tier_items`; update `_quest_score` to check whether an item's payload references the quest's `target_id` or `giver_id`.

---

### 6.5 Cross-encoder rerank for Tier B/C — M

**Depends on:** Phase 3.1 (real bi-encoder).

**New file:** `src/npc_engine/retrieval/cross_encoder_reranker.py`

```python
from sentence_transformers import CrossEncoder
from functools import lru_cache

@lru_cache(maxsize=1)
def get_cross_encoder() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, candidates: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    """Rerank (text, payload) candidates by cross-encoder score."""
    scores = get_cross_encoder().predict([(query, text) for text, _ in candidates])
    return [c for _, c in sorted(zip(scores, candidates), reverse=True)]
```

Call in `context_builder.py` after vector search, before building `ContextItem` objects:

```python
if len(tier_b_results) > 0:
    reranked = rerank(player_message, [(r["payload"].get("summary", ""), r) for r in tier_b_results])
    tier_b_results = [r for _, r in reranked]
```

---

### 6.6 Trust-weighted second-hop event retrieval — M

**Depends on:** Phase 4.3 (`WITNESSED` creates richer second-hop paths).

**New query** (`src/npc_engine/graph/trust_queries.py`):

```python
async def get_second_hop_events(
    session: AsyncSession,
    npc_id: str,
    trust_threshold: int = 50,
    limit: int = 5,
) -> list[dict]:
    """Return events that trusted friends KNOW_ABOUT but the NPC does not."""
```

Cypher:
```cypher
MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(friend:Character)
WHERE r.trust >= $trust_threshold
MATCH (friend)-[:KNOWS_ABOUT]->(e:Event)
WHERE NOT (npc)-[:KNOWS_ABOUT]->(e)
RETURN DISTINCT e, r.trust AS trust_weight
ORDER BY trust_weight DESC, e.occurred_at DESC
LIMIT $limit
```

Add these as low-priority Tier A items in `context_builder.py` (priority 70–75, below regular events).

---

## Phase 7 — Genre-Specific Modules

> Each module is independently deployable. All depend on Phase 4 cross-domain primitives.

> **⚠ FLAW (2026-05-19):** Schema migrations are not planned for Phase 7. Each sub-phase adds new
> fields to existing nodes/edges (`IS_CANONICAL` on Event §7.5, `power_score`/`treasury`/
> `military_strength` on Faction §7.2, `RELATIONSHIP_PHASE` on RELATES_TO §7.3). Without
> migration scripts, existing graph data silently lacks these fields and queries break.
> **Action required:** Add a Phase 7.0 "schema migration" step before each genre module,
> analogous to `scripts/migrations/add_faction_support.py` from Phase 1.

> **⚠ NOTE (2026-05-19):** Phase 7.2 (Political Simulation) should inherit the
> `faction_id`/`reputation_delta` pattern on `EventTemplate` for political events (AGENDA
> votes, power shifts) rather than inventing separate reputation wiring. See ISSUE-005 fix
> and `EventHandler.run_tick` for the established pattern.

---

### 7.1 Detective / Mystery (B.1) — L

**Prerequisite nodes from Phase 4:** `WAS_AT` (4.1) for alibi, `WITNESSED` (4.3) as testimonial evidence, `CAUSED_BY` (4.2) for clue-to-crime links.

**New nodes and edges:**

| Symbol | Type | Key fields |
|--------|------|------------|
| `EVIDENCE` | Node | `id`, `kind` (physical/testimonial/documentary), `description`, `discovered_at_tick`, `discovered_by_character_id`, `links_to_event_id`, `confidence` (0–100) |
| `DEDUCTION` | Node | `id`, `held_by_character_id`, `claim`, `supporting_evidence_ids`, `confidence`, `status` (open/confirmed/refuted) |
| `IMPLICATES` | Edge: Evidence → Character | `weight` (0–100), `is_misleading` |
| `SUSPECTS` | Edge: Character → Character | `event_id`, `evidence_ids`, `confidence` |
| `PRESENT_AT` | Edge: Evidence → Location | |

**Service API** (`src/npc_engine/graph/investigation_service.py`):

```python
async def create_evidence(session, *, kind, description, discovered_at_tick, discovered_by_character_id, links_to_event_id=None, confidence=100) -> str
async def implicate(session, *, evidence_id, character_id, weight, is_misleading=False) -> None
async def create_deduction(session, *, held_by_character_id, claim, supporting_evidence_ids, confidence) -> str
async def update_deduction_status(session, *, deduction_id, status) -> None
async def get_investigation_context(session, *, investigator_id, event_id) -> dict
    # Returns: witnesses, evidence, suspects, alibi windows, rumor tree
```

**New engine — investigation** (`src/npc_engine/engines/investigation/investigation_engine.py`):
On query, surface inconsistencies:
- NPC claims location X (`LOCATED_AT`) but a `WITNESSED` edge places them elsewhere at same tick → alibi contradiction.
- Two `BELIEVES_RUMOR` versions of the same event contradict each other.
Returns structured inconsistency list for LLM to narrate.

---

### 7.2 Political Simulation (B.2) — L

**Prerequisite nodes from Phase 5:** `PLEDGE` (5.2) for fealty oaths, `TREATY` (5.4) for alliance modeling.

**New nodes and edges:**

| Symbol | Type | Key fields |
|--------|------|------------|
| `TITLE` | Node | `id`, `name`, `faction_id`, `power` (int), `is_inheritable`, `current_holder_id` |
| `AGENDA` | Node | `id`, `description`, `proposed_by_faction_id`, `status`, `deadline_tick` |
| `LEVERAGE` | Edge: Character → Character | `secret_id`, `demand`, `status` (held/used/exposed) |
| `HOLDS_TITLE` | Edge: Character → Title | `since_tick` |
| `HEIR_OF` | Edge: Character → Character | `priority`, `legitimacy` |
| `SUPPORTS_AGENDA` | Edge: Character/Faction → Agenda | `weight` |
| `OPPOSES_AGENDA` | Edge: Character/Faction → Agenda | `weight` |

Add `power_score`, `treasury`, `military_strength` fields to `FACTION` node.

**New engines:** succession engine (tick-scan for title transitions), agenda/voting engine.

---

### 7.3 Social Simulation (B.3) — L (mood contagion ships independently as M)

**Prerequisite nodes from Phase 4:** `GROUP` (4.4) for clique dynamics.

**New nodes and edges:**

| Symbol | Type | Key fields |
|--------|------|------------|
| `NEED` | Node | `kind` (hunger/social/rest/recreation), `level` (0–100), `decay_rate` |
| `LIFE_EVENT` | Node (subtype of EVENT) | `kind` (birth/death/marriage/illness), high persistence flag |
| `SATISFIES_NEED` | Edge: Action/Item/Location → Need | `magnitude` |
| `OUTRANKS` | Edge: Character → Character | `context` (faction/group), `rank_delta` |

Add `RELATIONSHIP_PHASE` field (str enum) and `phase_started_at_tick` to `RELATES_TO` edge.

**New engines:** mood-contagion (M — ships first), need-decay.

**Mood-contagion engine** (`src/npc_engine/engines/mood/mood_contagion_engine.py`):
Per tick: query co-located character pairs with `RELATES_TO.affection > 50`. For each pair, exchange `current_mood` values by a fraction: `new_mood_a = 0.9 * mood_a + 0.1 * mood_b`. Update via `EmotionStore`.

---

### 7.4 Strategy / 4X (B.4) — L (`CONNECTS_TO` ships independently as S)

**Prerequisite:** Phase 5.4 (treaties matter for territory agreements).

**New nodes and edges:**

| Symbol | Type | Key fields |
|--------|------|------------|
| `RESOURCE_NODE` | Node | `kind` (gold/iron/grain/mana), `yield_per_tick`, `depletion` |
| `ARMY` | Node | `faction_id`, `strength`, `current_location_id`, `composition` |
| `CONNECTS_TO` | Edge: Location → Location | `kind` (road/river/sea/secret), `travel_cost`, `is_open` |
| `PRODUCES` | Edge: Location → ResourceNode | |
| `COMMANDS` | Edge: Character → Army | |
| `OCCUPIES` | Edge: Army → Location | |

Add `control_strength` (0–100) and `contested_by_faction_id` to `CONTROLS` edge.

**`CONNECTS_TO` ships first (S):** Enables travel-cost queries, supply-line detection, and path-finding without needing armies. Add `get_shortest_path(session, from_location_id, to_location_id)` using Cypher shortest-path query.

---

### 7.5 Narrative Adventure (B.5) — L (structural pieces ship as M without LLM chapter labeling)

**Prerequisite nodes:** `CAUSED_BY` (4.2) drives chapter transitions, `RUMOR` (4.5) as narrative events, `SKILL` (5.1) gates branching choices.

**New nodes and edges:**

| Symbol | Type | Key fields |
|--------|------|------------|
| `CHAPTER` | Node | `id`, `name`, `started_at_tick`, `ended_at_tick`, `theme`, `status` |
| `CHOICE` | Node | `id`, `chosen_at_tick`, `chosen_by_character_id`, `selected_option`, `available_options`, `consequence_event_id` |
| `NARRATIVE_BEAT` | Node | `id`, `kind` (rising/climax/falling/denouement), `intensity`, `chapter_id` |
| `PART_OF_CHAPTER` | Edge: Event/Quest → Chapter | |
| `UNLOCKED_BY` | Edge: Quest/Event → Choice | |

Add `IS_CANONICAL: bool` field to `EVENT` node — prevents memory decay and gossip distortion above threshold.

**New engine — chapter** (`src/npc_engine/engines/chapter/chapter_engine.py`):
Tick-level: detect chapter transitions based on completed quest cluster density or `NARRATIVE_BEAT` intensity threshold. With LLM integration: generate chapter title/description. Without: use rule-based labeling from event types.

---

## Phase 8 — Scale & Retrieval Unification

> Run after Phase 6–7 graph density is high enough to make these worthwhile.

---

### 8.1 Sub-cache decomposition of `DialogueContextCache` — L

**Problem:** Cache key includes `current_mood` which changes after every dialogue turn → near-100% cache miss rate within active conversations.

**File:** `src/npc_engine/retrieval/dialogue_context_cache.py`

Split into sub-caches with different invalidation TTLs:

```python
class DialogueContextSubCache:
    """Cache with independent TTL per context component."""
    world_state: CacheEntry          # invalidates on world_last_updated_at change
    npc_profile: CacheEntry          # invalidates on npc_last_graph_updated_at change
    npc_beliefs_goals: CacheEntry    # invalidates on npc_last_graph_updated_at change
    dynamic: None                    # never cached (emotion, session turns, relation deltas)
```

On each turn, fetch only components whose cache has expired. Estimated savings: 70–80% of graph queries on repeat turns in the same session.

---

### 8.2 GraphRAG pattern — unified Tier A + B/C traversal — L

**Goal:** Replace the current two-track model (Tier A = full graph fetch, Tier B/C = vector search) with a unified traversal that:
1. Vector-searches for top-K seed nodes.
2. Filters seeds by `KNOWS_ABOUT` (npc knowledge boundary).
3. Expands 1 hop from each seed along trust-weighted or quest-relevant edges.
4. Returns seed + expansion as a ranked subgraph.

**New file:** `src/npc_engine/retrieval/graph_rag.py`

```python
async def graph_rag_retrieve(
    session: AsyncSession,
    embedding_index: EmbeddingIndex,
    npc_id: str,
    query: str,
    top_k: int = 5,
    expand_hops: int = 1,
) -> list[ContextItem]:
    """Unified graph+vector retrieval respecting NPC knowledge boundary."""
    # Step 1: vector search
    seeds = await embedding_index.search(query=query, top_k=top_k * 2, filter_ids=None)
    # Step 2: knowledge filter
    known_ids = await get_known_event_ids_for_npc(session, npc_id=npc_id)
    seeds = [s for s in seeds if s["id"] in known_ids][:top_k]
    # Step 3: graph expansion
    expanded = await expand_subgraph(session, seed_ids=[s["id"] for s in seeds], hops=expand_hops, npc_id=npc_id)
    # Step 4: return as ContextItem list
    return _to_context_items(seeds + expanded)
```

This becomes the new Tier B/C path, replacing the current vector-only retrieval.

---

## Verification Checklist Per Phase

| Phase | Gate to pass before starting next |
|-------|-----------------------------------|
| 1 | `pytest tests/ -q` — zero regressions. No `ContextBudgetError` in a normal dialogue turn. |
| 2 | Startup validator sees all 3 engine contracts. Cold-start with bad `OLLAMA_API_URL` shows health-check error, not dialogue error. |
| 3 | Tier B/C results change meaningfully after a real embedding model loads. Context build latency measurably lower (log before/after). No `ContextBudgetError` on typical 3-belief NPC. |
| 4 | Cypher: can answer "where was X N ticks ago?", "who witnessed X do Y?", "what groups is X in?", "what rumors about event Z does X believe?". |
| 5 | Quest slot validator rejects candidates below required skill level. FactionPoliticsEngine logs `FACTION_STANDING_EVENT` rows. |
| 6 | Spot-check 5 dialogue turns: retrieved beliefs are topically related to the player message, not just highest-confidence. |
| 7 | Genre-module integration tests pass; no regression on existing scenarios. |
| 8 | Full context build latency < 50 ms on repeat dialogue turns (sub-cache hit). |
