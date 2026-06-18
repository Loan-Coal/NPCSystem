# Patterns Log

Reusable code and design patterns discovered during development. A pattern is
worth recording when it has been applied at least twice and would be worth
applying again.

Rules:
- Append-only.
- Each pattern has a short name, a "when to use" description, a "why" justification,
  and a minimal runnable example.
- If a pattern is superseded, mark it as `[SUPERSEDED]` and link to the replacement.
  Do not delete.

---

## Pattern: Frozen Exception Dataclasses
**When to use:** Every domain exception in this codebase.
**Why:** Exceptions are value objects — they carry diagnostic context and are never modified after construction. `frozen=True` enforces STRUCT-06 (immutability) and enables hashing/equality comparisons in test assertions.
**Example:**
```python
from dataclasses import dataclass
from utils.errors import StructuredNPCSystemError

@dataclass(frozen=True)
class MyServiceError(StructuredNPCSystemError):
    """Raised when X violates Y."""
    code: str
    detail: str
```
**First applied in:** utils (service #1)

---

## Pattern: Typed route exit contract via `OkEnvelope[T]`

Every HTTP route declares `response_model=OkEnvelope[T]` so `/openapi.json` emits a
real body schema (generated clients get stubs, not empty `{}`). The runtime path is
unchanged — handlers still return `ok_response(...)` (a plain dict); FastAPI validates
it against the envelope on the way out.

```python
from npc_engine.api.route_helpers import OkEnvelope, ok_response

@router.get("/{id}", response_model=OkEnvelope[dict[str, Any]])
async def get_thing(id: str) -> dict[str, Any]:
    return ok_response({"thing_id": id})   # data is a dict
```

- `data` is a dict → `OkEnvelope[dict[str, Any]]`; a list → `OkEnvelope[list[dict[str, Any]]]`.
- Routes that return a **bare** (non-enveloped) dict use `response_model=dict[str, Any]`.
- Dynamic registry routes (`graph`, `graph_admin`) stay `dict[str, Any]` (DEC-088).
- `tests/unit/test_route_response_model_contract.py` enforces "no route missing `response_model`".

**First applied in:** api (Phase 20, S20.1–S20.6) — swept across ~125 routes.

---

## Anti-Pattern: Common Mistakes to Avoid

A condensed reference of recurring mistakes observed during development. Each row
shows the wrong pattern and the correct replacement.

| Mistake | Correct Pattern |
|---|---|
| `session.run(f"MATCH ... '{npc_id}'")` | `session.run(CYPHER_CONST, npc_id=npc_id)` — parameterized Cypher only; f-strings in queries are a SQL-injection-equivalent |
| `context["items"].append(x)` | `context.model_copy(update={"items": [*context.items, x]})` — all Pydantic models are `frozen=True`; never mutate in-place |
| `from engines.llm.mistral_adapter import MistralAdapter` inside an engine | Import `LLMClientProtocol` only — depend on the protocol, not the concrete adapter |
| `except Exception: pass` | `except SpecificError as e: logger.error(...); raise` — never swallow exceptions silently |
| `random.random()` inside gossip distortion | Use seeded deterministic computation — gossip must be reproducible for the same inputs |
| `llm_response["npc_response"]` | `parsed_response.npc_response` — always parse LLM output into a Pydantic model before accessing fields |
| Module-level `db = Neo4jDriver(...)` | Inject `driver` via constructor or FastAPI `Depends` — no global mutable state |
| Files > 300 lines | Extract to helper files immediately — see CLAUDE.md § "Files" |
| `print(f"Prompt: {prompt}")` | `if settings.LOG_LLM_PROMPTS and settings.ENV == "dev": logger.debug(...)` |
| Relative imports beyond one level (`from ..x import y`) | `from npc_engine.x import y` — one level max (`from .x import y` is fine) |
