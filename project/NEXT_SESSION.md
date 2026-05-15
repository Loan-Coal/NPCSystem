# Next Session Instructions

## Roadmap V2 — Phase 2: Engine Configuration Baseline

Current state: Phase 1 is **DONE** — 695 unit tests green, 0 failures.

Run tests before touching any code:

```bash
pytest tests/ -q
```

All 12 items of Phase 2 must be completed before moving to Phase 3.

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — add RoadmapV2 Phase 2 section marked IN_PROGRESS.
2. `project/STATUS.md` — row for Phase 2 already exists; update it to IN_PROGRESS.

---

## Phase 2 — Engine Configuration Baseline (12 items)

Items are ordered by dependency. Do them in sequence. Run `pytest tests/ -q` after each item.

---

### 2.1 Create `MemoryConsolidationEngine` `llm_config.yaml` + contract YAML — M

**Goal:** Make memory consolidation visible to the startup validator.

**New file:** `src/npc_engine/engines/memory_consolidation/llm_config.yaml`

```yaml
engine: memory_consolidation
llm:
  backend: ollama
  model: mistral:7b-instruct
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

**New file:** `src/npc_engine/engines/contracts/memory_consolidation_engine.yaml`
— Look at `src/npc_engine/engines/contracts/dialogue_engine.yaml` for the pattern.

Wire the engine into `validate_all_engine_llm_configs` (check `src/npc_engine/engines/llm_config_loader.py`).

**Tests to add:** Unit test that `load_llm_config("memory_consolidation")` loads without error.

---

### 2.2 Fix `consolidate_memories` singleton — use proper `llm_config.yaml` — S

**Depends on:** 2.1

`src/npc_engine/api/dependency_singletons.py` — update `get_memory_consolidation_engine`:

```python
@lru_cache
def get_memory_consolidation_engine():
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import MemoryConsolidationEngine
    from npc_engine.engines.llm.factory import create_llm_client_for_engine

    settings = get_settings()
    engine_config = get_engine_model_config_for("memory_consolidation")   # ← was "dialogue"
    llm_client = create_llm_client_for_engine(engine_config, settings)
    return MemoryConsolidationEngine(
        session_store=get_session_store(),
        llm_client=llm_client,
        turn_threshold=5,
        clear_turns_after=False,
    )
```

`main.py` already has `get_memory_consolidation_engine.cache_clear()` in lifespan — no change needed there.

---

### 2.3 Fix `EngineTimeoutsMs` schema — allow per-engine tier declaration — S

**Problem:** `EngineTimeoutsMs` requires `full`, `graph_only`, and `canned`. Quest generation only has `full` and `deterministic`.

**File:** `src/npc_engine/engines/llm_config_models.py` (the per-engine config, not `schema/context_config_models.py`)

Make `graph_only` and `canned` optional, add `deterministic`:

```python
class EngineTimeoutsMs(BaseModel):
    full: int = Field(gt=0)
    graph_only: int | None = Field(default=None, gt=0)
    canned: int | None = Field(default=None, gt=0)
    deterministic: int | None = Field(default=None, gt=0)
    model_config = ConfigDict(frozen=True, extra="forbid")
```

Update quest_generation's YAML to drop the lying `graph_only`/`canned` entries:

```yaml
timeouts_ms:
  full: 30000
  deterministic: 100
```

---

### 2.4 Fix `@lru_cache` — add `cache_clear()` for all rules-based engines — M

**File:** `src/npc_engine/main.py` — in `lifespan`, add cache clears before the existing ones:

```python
get_faction_politics_engine.cache_clear()
get_story_pacing_engine.cache_clear()
get_pricing_engine.cache_clear()
get_trade_engine.cache_clear()
get_quest_generation_engine.cache_clear()
get_routine_engine.cache_clear()
```

After clearing, pre-warm to fail fast on bad rules:

```python
get_faction_politics_engine()
get_story_pacing_engine()
get_quest_generation_engine()
```

**In tests:** Add an `autouse=True` fixture in `tests/conftest.py` that calls `cache_clear()` for all singletons in teardown to prevent state leakage between test modules.

---

### 2.5 Fix `QuestGenerationEngine` — use `llm_config.max_tokens` — S

**File:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py`

Replace hardcoded `256` in `_ask_llm_for_fills` and `_generate_flavor` with an injected `max_tokens`:

```python
class QuestGenerationEngine:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        templates: list[QuestTemplateRecord],
        prompts_dir: Path,
        max_tokens: int = 256,
    ) -> None:
        self._max_tokens = max_tokens
        ...
```

`dependency_singletons.py` — pass `max_tokens=engine_config.llm.max_tokens` when constructing.

---

### 2.6 Fix bare `except Exception` in `QuestGenerationEngine` — S

**File:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py`

In `_ask_llm_for_fills` and `_generate_flavor`, replace the bare `except Exception` with specific catches:

```python
from npc_engine.utils.errors import LLMTimeoutError, LLMRequestError
from pydantic import ValidationError

except (LLMTimeoutError, LLMRequestError) as error:
    _logger.warning("LLM error during slot fill: %s", error)
    ...
except ValidationError as error:
    _logger.warning("Schema validation error: %s", error)
    ...
# programmer errors bubble up naturally
```

---

### 2.7 Add HTTP connection pooling — shared `httpx.AsyncClient` per engine — S

**Files:** `src/npc_engine/engines/llm/ollama_adapter.py`, `src/npc_engine/engines/llm/mistral_adapter.py`

Move `httpx.AsyncClient` from per-call to instance-level:

```python
class OllamaAdapter(LLMClientProtocol):
    def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        """Release the shared HTTP client. Call at shutdown."""
        await self._client.aclose()
```

Replace all `async with httpx.AsyncClient(timeout=...) as client:` blocks in `generate`, `generate_structured`, and `stream` with `client = self._client`.

Same pattern for `MistralAdapter`.

In `main.py` lifespan teardown, call `adapter.close()` for each singleton that owns an adapter.

---

### 2.8 Add LLM health/readiness probe — S

**Files:** `src/npc_engine/engines/llm/protocols.py`, all adapters, `src/npc_engine/api/routes/system.py`

Add to `LLMClientProtocol`:

```python
async def health_check(self) -> bool:
    """Return True if the backend is reachable and ready. Non-raising."""
```

`OllamaAdapter`:

```python
async def health_check(self) -> bool:
    try:
        response = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False
```

`MistralAdapter`, `LlamaAdapter`: `return True` (Mistral is always external; health checked at startup).

`MockLLMAdapter`: `return True`.

`main.py` lifespan — probe after connecting:

```python
dialogue_adapter = get_llm_client(...)
if not await dialogue_adapter.health_check():
    _logger.warning("LLM backend health check failed — starting degraded")
```

`system.py` readiness route: include LLM health in the `/readiness` response.

---

### 2.9 Make `TypeRegistry`-derived models used for write validation — M

**New file:** `src/npc_engine/type_registry/node_validator.py`

```python
"""
node_validator.py - Runtime node payload validation against TypeRegistry-derived models.

Does NOT: perform graph writes or query Neo4j.

Dependencies injected: TypeRegistry.
"""

from __future__ import annotations

from npc_engine.type_registry.contracts import TypeRegistry


def validate_node_write(
    registry: TypeRegistry,
    node_type: str,
    props: dict,
) -> dict:
    """Validate and coerce props against the registry-derived model for node_type.

    Args:
        registry: The active TypeRegistry.
        node_type: Node label string (e.g. "Character").
        props: Raw property dict to validate.

    Returns:
        Validated props dict with None-valued keys excluded.
    """
    model_cls = registry.node_models.get(node_type)
    if model_cls is None:
        return props
    return model_cls.model_validate(props).model_dump(exclude_none=True)
```

Wire into `EventHandler`, `QuestLifecycleEngine` — validate before writing graph nodes.

---

### 2.10 Make LLM factory extensible — plugin registration — M

**File:** `src/npc_engine/engines/llm/factory.py`

Replace the `if/elif` chain with a registry pattern:

```python
from typing import Callable

_REGISTRY: dict[str, Callable[..., LLMClientProtocol]] = {}


def register_backend(name: str, constructor: Callable[..., LLMClientProtocol]) -> None:
    """Register a backend constructor under name."""
    _REGISTRY[name] = constructor


def create_llm_client_for_engine(engine_config, settings) -> LLMClientProtocol:
    backend = engine_config.llm.backend
    constructor = _REGISTRY.get(backend)
    if constructor is None:
        raise ValueError(f"Unsupported LLM backend: {backend!r}")
    return constructor(engine_config=engine_config, settings=settings)
```

Register built-ins at module load time (bottom of `factory.py`). Each adapter module calls `register_backend(...)` from its own module for self-registration.

---

### 2.11 Fix `BaseEngine` Protocol — `TickScheduler` type constraint — S

**File:** `src/npc_engine/scheduler/tick_scheduler.py`

Change constructor parameters from `object` to `BaseEngine` (locate or create `src/npc_engine/engines/base_engine.py`):

```python
from npc_engine.engines.base_engine import BaseEngine

class TickScheduler:
    def __init__(
        self,
        clock: GameClock,
        gossip_handler: BaseEngine,
        event_handler: BaseEngine,
        ...
    ) -> None:
```

Ensure every engine passed to `TickScheduler` implements `BaseEngine` (has `run_tick` and any required methods).

---

### 2.12 Resolve circular import in `dependency_singletons.py` — S

**Problem:** `create_llm_client_for_engine` is imported inside a function body to work around a circular import.

**Steps:**
1. Map the cycle: `dependency_singletons` → `factory` → `engines/llm_config_loader` → `dependency_singletons`.
2. Extract the shared type into `src/npc_engine/engines/llm/types.py` with no intra-project imports.
3. Move the in-function import to the module top-level.

---

## Verification Gate for Phase 2

```bash
pytest tests/ -q
# Must see: 0 errors, 0 failures
```

Additional manual checks:
- Startup validator sees all engine contracts (dialogue + quest_generation + memory_consolidation).
- Cold-start with bad `OLLAMA_API_URL` shows health-check warning in logs, not a dialogue-turn error.

---

## Phase 3 — Retrieval Foundation (next after Phase 2)

After Phase 2 passes, proceed with Phase 3. Key items:

- **3.1** Replace character-bucket hash with `sentence-transformers` embedding
- **3.2** Fix recency scoring — use game time, not wall-clock time
- **3.3** Map `emotional_charge`, `urgency`, `confidence` into severity scoring
- **3.4** Cap Tier 0 in the active `context_budget_enforcer`
- **3.5** Increase `PROMPT_TOKEN_BUDGET` from 800 → 2500
- **3.6** Parallelize Tier A queries with `asyncio.gather`
- **3.7** Add `KNOWS_ABOUT` filter to vector retrieval

Full spec for each item is in `project/ROADMAP_V2.md` (Phase 3 section).

---

## Open issues to be aware of (do NOT fix unless blocking)

- ISSUE-013: `how_long_ago` bucket gap 7–27 days (P3)
- ISSUE-005: `adjust_reputation_for_event` not wired (P3)
- ISSUE-006: `Character.faction` string field not migrated (P3)
- ISSUE-004: `edge_updater.py` mypy warning (P3)
- ISSUE-011: `.env` uses Docker DNS (P3)
