# FIX-SEV-14 — Restore type safety at the API boundary (Pydantic exit schemas + mypy burn-down)

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** L (multi-session, incremental)
**Category:** correctness / api-design · **Absorbs:** PY-01, PY-02, PY-03, PY-05, PY-11, PY-12
**Blocks:** SEV-15 type-gating in CI.

## Problem
~90 endpoints return bare `dict[Any,Any]`; the schema layer, dynamic-model builder, and graph writers are mypy-broken — 254 errors total, masking real `arg-type`/`attr-defined` bugs and producing empty OpenAPI response bodies (breaks client codegen for integrating studios).

## Current shape (root-cause clusters from `04_type.log`)
- **~90 `no-any-return`** (`04_type.log:164-274`): routes typed `-> dict` returning `ok_response()` which is `dict[str,Any]` (`route_helpers.py:27`). Files: `api/routes/{graph,clock,interaction,quest,debts,beliefs,causality,batch,...}.py` (29 modules).
- **22 `valid-type`/`misc`** (`:33-65`): `api/schemas.py:26` `FrozenApiModel = FrozenDialogueModel` used as a base class for 11 models.
- **`call-overload`** (`:17-28`): `type_registry/runtime_models.py:63,80` `create_model(__config__=ConfigDict(...))` — deprecated Pydantic-v2 API; plus runtime-variable type params at `:108,111`.
- **`arg-type`** (`:109-110`): `graph/quest_writer.py:86,186,215` typed `dict` but called with `neo4j.Record`.
- **`attr-defined`** (`:128-133`): `graph/{character_writer,event_writer}.py` accept `BaseModel` then read `.id`/`.producer`/`.provenance`.
- **14 `no-any-return`** (`:67-79`): `config.py:166-244` `@field_validator` helpers return `Any`.

## Target shape
Every route has a typed `response_model`; `ok_response` is generic; dynamic models use the correct Pydantic-v2 API; writers are typed to `Record`/Protocols; validator helpers are annotated. `mypy src/npc_engine` is clean (or a tracked, shrinking count).

## Steps (incremental — land per cluster, keep `make test` green)
1. **Envelope generic** (unblocks ~90): make `ok_response(data: T) -> OkEnvelope[T]` with `OkEnvelope[T](BaseModel)`; per route add a concrete `ResponseModel` and `response_model=` on the decorator, annotate `-> ResponseModel`. Do it module-by-module.
2. **FrozenApiModel** (quick, 22): replace the alias with direct inheritance `class NPCStateResponse(FrozenDialogueModel)` (or `FrozenApiModel: TypeAlias = ...`). Delete the value-alias.
3. **create_model**: use `__base__=_FrozenBase` (a pre-configured `BaseModel` with `model_config=ConfigDict(frozen=True, extra="forbid")`) instead of `__config__=`; fix the runtime-variable type params via `Annotated`/`get_args`.
4. **Writers**: type `_record_to_state_payload(record: Record)`; define `CharacterNode`/`QuestEventNode` Protocols (or a `TypeVar` bound to the concrete domain model) for `upsert_character`/`ensure_quest_event_provenance`.
5. **Validators**: add explicit return annotations to the `check_*` helpers in `config_validators.py`.

## Verification
- `mypy src/npc_engine/api/routes/` → 0 `no-any-return`; `mypy src/npc_engine/api/schemas.py` → 0; `mypy src/npc_engine/type_registry/runtime_models.py` → 0; `graph/{quest,character,event}_writer.py` → 0; `config.py` → 0.
- OpenAPI response bodies are non-empty (spot-check `/openapi.json`).
- `make type` total error count tracked down to 0 (gates CI per SEV-15).

## Blast radius
All 29 route modules + schema + type_registry + graph writers. Incremental and low-runtime-risk (mostly annotations + envelope), but broad. This is the prerequisite for type-gating CI.
