# LLM Generation Guide — NPC Engine

This file is a meta-document for the developer (or LLM) generating the codebase.
Read this BEFORE generating any code. It explains how to interpret the spec files,
what order to generate code in, and what traps to avoid.

---

## Spec Files Reference

| File | Purpose |
|---|---|
| `PROJECT_PLAN.xml` | Authoritative directory tree, API routes, engine pipelines, milestones |
| `CODING_PRINCIPLES.xml` | Every rule the generated code must follow, with priority and examples |
| `BUSINESS_REQUIREMENTS.md` | What each module must do from a product perspective |
| `DATA_MODELS.md` | Neo4j node/edge schemas, Cypher query patterns, seed requirements |
| `PROMPT_DESIGN.md` | LLM prompt templates, context skeleton format, token budget, few-shot examples |
| `ARCHITECTURE.md` | ASCII diagrams, data flows, extension points, deployment notes |

---

## Generation Order (Critical)

Generate files in milestone order. Each milestone depends on the previous.
Do not skip ahead — later files import from earlier files.

```
M0: config.py → utils/errors.py → utils/logging.py → auth/ → main.py skeleton
M1: graph/db.py → type_registry/runtime_models.py → graph/event_writer.py
    → graph/graph_reader.py
    → graph/delta_log_writer.py → graph/character_writer.py
    → graph/event_writer.py → graph/relation_writer.py → graph/graph_writer.py
    → mutation/ → world/ → data/seed.py
M2: engines/llm/ (protocols first, then adapters, then factory)
    → retrieval/ (vector_store_protocol → vector_store_factory → embedding_index
       → subgraph_retriever → context_merger → token_budget_enforcer
       → context_serializer → context_builder)
M3: engines/emotion/ → engines/dialogue/ (session_store → response_parser
    → action_resolver → relation_mutator → llm_client → prompt_builder
    → dialogue_handler)
    → api/dependencies.py → api/routes/dialogue.py → api/routes/dialogue_ws.py
    → api/routes/npc_state.py → api/routes/action.py
M4: engines/gossip/ → engines/events/ → scheduler/
    → api/routes/clock.py → api/routes/batch.py
M5: tests/ → .github/workflows/ci.yml → docs/
```

---

## File Generation Rules

### Every file must start with:
```python
"""
<one-sentence description of what this module does>

Does NOT: <scope boundary — what this module deliberately does not do>

Dependencies injected: <list of injected dependencies, or 'None'>
"""
```

### Imports must be ordered:
1. Standard library
2. Third-party (fastapi, pydantic, neo4j, etc.)
3. Internal (npc_engine.*)
4. Blank line between each group

### Never use:
- `from module import *`
- Global mutable state (module-level lists/dicts that are mutated at runtime)
- `print()` — always `logger.info/warning/error()`
- Bare `except:` or `except Exception:` without re-raising or logging
- `dict["key"]` on LLM output — always use Pydantic model fields

---

## Pydantic v2 Patterns

Use these exact patterns. Pydantic v2 syntax differs from v1.

```python
# Model definition
from pydantic import BaseModel, Field, field_validator

class CharacterNode(BaseModel):
    id: str
    name: str
    trust: int = Field(default=50, ge=0, le=100)

    model_config = ConfigDict(frozen=True)  # immutable

# Settings (config.py)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NEO4J_URI: str
    LLM_BACKEND: Literal["mistral7b", "llama8b", "mock"] = "mock"

    model_config = SettingsConfigDict(env_file=".env")

# Copying with update (immutability pattern)
updated = original.model_copy(update={"trust": new_trust})
```

---

## Neo4j Async Patterns

```python
# db.py — session context manager
from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase

@asynccontextmanager
async def get_session(driver):
    async with driver.session() as session:
        yield session

# graph_reader.py — query pattern
async def get_character(session: AsyncSession, npc_id: str) -> CharacterNode:
    result = await session.run(
        CYPHER_GET_CHARACTER,  # module-level constant, never f-string with user input
        npc_id=npc_id          # parameterized
    )
    record = await result.single()
    if record is None:
        raise CharacterNotFoundError(npc_id=npc_id)
    return CharacterNode(**record["c"])

# graph_writer.py — transaction pattern
async def apply_relation_delta(...):
    async with session.begin_transaction() as tx:
        await relation_writer.write(tx, ...)
        await delta_log_writer.append(tx, ...)
        await tx.commit()
```

---

## FastAPI Patterns

```python
# api/dependencies.py — composition root
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)]
) -> AsyncGenerator[AsyncSession, None]:
    driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, ...)
    async with driver.session() as session:
        yield session

async def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)]
) -> LLMClientProtocol:
    return llm_factory.create(settings.LLM_BACKEND)

# Route handler — thin, delegates to engine
@router.post("/dialogue", response_model=DialogueResponse)
async def dialogue(
    body: DialogueRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    llm: Annotated[LLMClientProtocol, Depends(get_llm_client)],
    api_key: Annotated[None, Depends(verify_api_key)],
) -> DialogueResponse:
    handler = DialogueHandler(session=session, llm=llm)
    return await handler.handle(body)
```

---

## Protocol Pattern

```python
# engines/llm/protocols.py
from typing import Protocol, AsyncIterator, runtime_checkable

@runtime_checkable
class LLMClientProtocol(Protocol):
    async def generate(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> str: ...

    async def generate_structured(
        self, prompt: str, schema: dict, max_tokens: int
    ) -> dict: ...

    async def stream(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> AsyncIterator[str]: ...

    def model_name(self) -> str: ...

# engines/llm/mock_adapter.py — for tests
class MockLLMAdapter:
    """Returns deterministic canned responses. No network calls."""

    def __init__(self, response: dict):
        self._response = response

    async def generate_structured(self, prompt: str, schema: dict, max_tokens: int) -> dict:
        return self._response

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        return self._response.get("npc_response", "")

    async def stream(self, prompt: str, max_tokens: int, temperature: float):
        for word in self._response.get("npc_response", "").split():
            yield word + " "

    def model_name(self) -> str:
        return "mock"
```

---

## Gossip Distortion — Implementation Skeleton

```python
# engines/gossip/gossip_distort.py
"""
Pure deterministic gossip distortion function.

Does NOT: access the database, use randomness from external state.
Dependencies injected: None (pure function).
"""
import hashlib
from npc_engine.engines.gossip.gossip_distort import GossipDistortion, DistortionType

DISTORTION_PROBABILITY_SCALE = 100

def gossip_distort(
    event_summary: str,
    sharer_honesty: int,
    sharer_receiver_trust: int,
    event_severity: int,
    tick_id: int,
    distortion_base: float,
) -> GossipDistortion:
    """
    Compute a deterministic distortion of an event summary.

    Distortion probability = distortion_base + (1 - honesty/100) * 0.5 + (severity/100) * 0.3
                             - (trust/100) * 0.2

    Args:
        event_summary: Original event text.
        sharer_honesty: Sharer's honesty stat [0-100].
        sharer_receiver_trust: Trust from sharer to receiver [0-100].
        event_severity: Event severity [0-100].
        tick_id: Current tick (used as deterministic seed component).
        distortion_base: Base distortion probability from config.

    Returns:
        GossipDistortion with summary, distortion_type, distortion_level.

    Raises:
        Never. Returns identity distortion if probability below threshold.
    """
    prob = _compute_distortion_probability(
        sharer_honesty, sharer_receiver_trust, event_severity, distortion_base
    )
    seed = _compute_seed(event_summary, sharer_honesty, sharer_receiver_trust, tick_id)
    # Use seed to deterministically select type and level
    ...
```

---

## Token Budget Enforcement — Implementation Skeleton

```python
# retrieval/token_budget_enforcer.py
"""
Pure function for trimming context items to a token budget.

Does NOT: fetch data, call LLM, mutate input.
Dependencies injected: None (pure function).
"""
from npc_engine.retrieval.context_merger import MergedContext, ContextItem, ContextTier

CHARS_PER_TOKEN_ESTIMATE = 4  # conservative estimate

def enforce(context: MergedContext, budget: int) -> MergedContext:
    """
    Trim Tier B items first, then Tier A items, until total tokens <= budget.
    Never trims Tier 0 items. Raises TokenBudgetExceededError if Tier 0 alone
    exceeds budget.

    Args:
        context: Merged context from context_merger.
        budget: Maximum allowed tokens.

    Returns:
        New MergedContext (immutable — never mutates input) with trimmed items.

    Raises:
        TokenBudgetExceededError: If Tier 0 alone exceeds budget.
    """
    ...
```

---

## WebSocket Streaming — Implementation Skeleton

```python
# api/routes/dialogue_ws.py
from fastapi import WebSocket, WebSocketDisconnect
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler

@router.websocket("/ws/dialogue")
async def ws_dialogue(
    websocket: WebSocket,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    llm: Annotated[LLMClientProtocol, Depends(get_llm_client)],
):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        request = DialogueRequest(**data)
        handler = DialogueHandler(session=session, llm=llm, streaming=True)

        async for event in handler.stream(request):
            await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "data": str(e)})
        await websocket.close()
```

---

## Common Mistakes to Avoid

| Mistake | Correct Pattern |
|---|---|
| `session.run(f"MATCH ... '{npc_id}'")` | `session.run(CYPHER, npc_id=npc_id)` |
| `context["items"].append(x)` | `context.model_copy(update={"items": [*context.items, x]})` |
| `from engines.llm.mistral_adapter import MistralAdapter` inside an engine | Import `LLMClientProtocol` only |
| `except Exception: pass` | `except SpecificError as e: logger.error(...); raise` |
| `random.random()` inside gossip_distort | Use seeded deterministic computation |
| `llm_response["npc_response"]` | `parsed_response.npc_response` (Pydantic field) |
| Module-level `db = Neo4jDriver(...)` | Inject `driver` via constructor or FastAPI `Depends` |
| `quest.py` route with no engine | Remove route until engine exists |
| Files > 200 lines | Extract to helper files immediately |
| `print(f"Prompt: {prompt}")` | `if config.LOG_LLM_PROMPTS and config.ENV == 'dev': logger.debug(...)` |

---

## Testing Conventions

```python
# Unit test — pure function, no mocks needed
def test_gossip_distort_is_deterministic():
    result1 = gossip_distort("A fire broke out", 30, 40, 80, tick_id=5, distortion_base=0.3)
    result2 = gossip_distort("A fire broke out", 30, 40, 80, tick_id=5, distortion_base=0.3)
    assert result1 == result2

# Unit test — with mock LLM
async def test_dialogue_handler_uses_fallback_on_timeout(mock_session):
    llm = MockLLMAdapter(raises=LLMTimeoutError)
    handler = DialogueHandler(session=mock_session, llm=llm)
    result = await handler.handle(DialogueRequest(player_id="p1", npc_id="n1", player_message="hi"))
    assert result.cached is False
    assert result.npc_response != ""  # fallback served

# Integration test — real Neo4j via testcontainers
async def test_apply_relation_delta_clamps_at_100(neo4j_session, seeded_graph):
    await graph_writer.apply_relation_delta(
        src_id="npc-1", dst_id="player-1",
        deltas={"trust": 999},  # should clamp to 100
        cause_id="test"
    )
    edge = await graph_reader.get_npc_player_edge(neo4j_session, "npc-1", "player-1")
    assert edge.trust == 100
```
