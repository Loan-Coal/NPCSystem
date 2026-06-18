# Batch 5 Handoff — API response typing (`response_model` on all 123 routes)

**Status:** NOT STARTED. Self-contained spec so a fresh session can execute it cleanly.
**Source findings:** `project-harness/FINAL_REVIEW_FINDINGS.md` L3-01/02/03/07 (+ raw evidence
in `project-harness/review-evidence/final/L3-types.md`, gitignored).
**Effort:** L (largest single remaining item; ~100+ small route edits + a handful of models).
**Branch:** `munich-demo`. **Created:** 2026-06-04, during the final hardening review.

---

## Why this batch exists

mypy is already 0 and holds (SEV-14). But SEV-14 only fixed the *internal* type errors —
it never typed the **API exit surface**. Today:

- `route_helpers.ok_response()` and `error_response()` return `dict[str, Any]`.
- **120 of 123 routes have no `response_model=`** (only `dialogue.py` ×1 and `npc_state.py` ×2 do).
- FastAPI therefore emits **empty `{}` response bodies** in the OpenAPI schema for those 120 routes.
- A game studio generating a client from the OpenAPI spec gets unusable stubs — which directly
  undercuts the product premise ("license to studios, integrate in one call").

This is purely the **exit contract**; it does not change runtime behavior, only the schema +
exit validation.

## Goal / acceptance criteria

- `OkEnvelope[T]` generic envelope exists; `ok_response` is typed to return it.
- Every route declares `response_model=OkEnvelope[ConcreteModel]` (or a bare concrete model where a
  route already returns one).
- Raw `dict`/`list[dict]` payloads inside response models replaced with typed Pydantic sub-models.
- `make type` still 0; `make check` green.
- OpenAPI bodies non-empty: assert `len([r for r in app.routes if getattr(r,'response_model',None) is None and r.methods]) == 0` (excluding /health, websocket, static).
- Generic graph services validate typed payloads, not `dict[str, Any]` (L3-07).

## The work, concretely

### 1. Envelope (L3-02) — do first, everything depends on it
- In `src/npc_engine/api/route_helpers.py`: add
  ```python
  from typing import Generic, TypeVar
  from pydantic import BaseModel
  T = TypeVar("T")
  class OkEnvelope(BaseModel, Generic[T]):
      success: bool = True
      data: T
      meta: dict[str, Any] | None = None
  ```
- Keep `ok_response()` returning a dict at runtime (FastAPI serializes fine) BUT add the typed
  envelope for `response_model=`. Simplest path: routes declare `response_model=OkEnvelope[X]` and
  keep returning `ok_response(x)`. FastAPI validates the dict against the model on the way out.
- Consider an `ErrEnvelope` too for documented error responses (optional; lower priority).

### 2. Per-route `response_model=` (L3-01) — the bulk
Add `response_model=OkEnvelope[ConcreteModel]` to each route decorator. Route files and route
counts (from L3-types.md):

```
action.py:1  batch.py:2  beliefs.py:4  causality.py:2  clock.py:2  debts.py:3
dialogue_ws.py:1(WS-exempt)  economy.py:2  factions.py:10  goals.py:4  gossip_spread.py:1
graph.py:8  graph_admin.py:8  groups.py:5  interaction.py:2  items.py:4
location_graph.py:4  location_history.py:3  memories.py:6  pledges.py:3  quest.py:6
quest_generation.py:4  rumor_trace.py:2  rumors.py:5  schedules.py:7  secrets.py:3
skills.py:6  system.py:2  traits.py:3  treaties.py:4  witnessed.py:3
```
Total 123 (already typed: dialogue.py×1, npc_state.py×2). `/health` (system.py) and the
`dialogue_ws` WebSocket are exempt.

Strategy: go module by module. For each route, define (or reuse) a concrete Pydantic model for its
`data` payload. Many already have request models nearby; mirror them for responses. Where a route
returns a graph node/edge, build typed node/edge models (see #3).

### 3. Kill raw dicts in models + generic services (L3-03, L3-07)
- `api/schemas.py:67-69` `NPCStateResponse` has `character: dict | None`, `relations: list[dict]`,
  `events: list[dict]` → define `CharacterNode`, `RelationEdge`, `EventNode` models and use them.
- `graph/generic_node_service.py` (`upsert_node`/`patch_node`/`missing_extension_warnings`) and
  `graph/generic_edge_service.py` (`upsert_edge`) accept/return `dict[str, Any]`. The type_registry
  already builds runtime Pydantic models — validate against those at the boundary instead. This also
  hardens the world_state 422 path already partially handled in Batch 1.

### 4. Optional adjacent cleanups (same review, can fold in)
- L3-04 `BaseEngine.run_tick` returns untyped `dict` across 11 engines → a `TickResult` model.
- L3-05 add `from __future__ import annotations` to the 136 files missing it: `ruff check
  --select=FA102 --fix src/` (automated, safe, do as its own commit).
- L3-06 33 request-body fields typed `str` that should be `Literal`/`Enum` (see L3-types.md list).

## Gotchas / constraints (from this codebase)
- **Function-length gate is now live (R006, `scripts/check_rules.py`).** New functions over 40 lines
  fail `make check`. Adding `response_model=` won't grow functions, but new typed helpers should stay
  small. Existing violations are grandfathered in `scripts/rules_baseline.txt`; don't add new ones.
- **300-line file gate (R001).** `api/schemas.py` and route files are near limits; if adding models
  pushes a file over 300 lines, split models into a new module (e.g. `api/response_models/`) rather
  than waiving.
- **No raw dict across module boundaries** is a strict CLAUDE.md rule — this batch is literally
  enforcing it at the API layer.
- Generic graph routes use dynamic node/edge types; their response payload is registry-driven, so a
  generic `OkEnvelope[dict[str, Any]]` may be acceptable there IF a tighter model is impractical —
  document that choice in DECISIONS if you take it.

## Suggested commit slicing (incremental, each `make check` green)
1. `feat(api): add OkEnvelope[T] envelope` (+ wire ok_response typing).
2. `refactor(api): typed sub-models for NPCStateResponse + generic graph payloads` (L3-03/07).
3..N. `feat(api): response_model on <module> routes` — one commit per few route modules.
last. `chore: ruff FA102 future-annotations` (L3-05) + `make check` + OpenAPI-non-empty assertion test.

## Verification
- `make check` (mypy 0, gates green, coverage ≥80%).
- New test: build the app, assert no route is missing `response_model` (excluding /health + WS).
- `curl /openapi.json` → spot-check a few route bodies are non-empty objects.
