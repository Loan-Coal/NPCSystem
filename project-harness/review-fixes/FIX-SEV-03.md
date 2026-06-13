# FIX-SEV-03 — Scheme typing: status Literal + typed route payload + covert-props model

**Severity:** HIGH · **Lens:** L3 (L3-08, L3-15, L3-13)

## Problem
The scheme feature crosses module boundaries with untyped data:
1. `SchemeRecord.status` / `SchemeWithSteps.status` are `str | None` with no `Literal`; `"active"` is a raw
   literal embedded in three Cypher `WHERE` clauses (only `_DISCOVERED_STATUS` is named) (L3-08).
2. The `/npc/{id}/schemes` route fetches typed `list[SchemeWithSteps]` then calls `.model_dump()` on each,
   discarding the type into `OkEnvelope[dict[str,Any]]` — the typed payload is thrown away before
   serialization, so OpenAPI clients see `Any` (L3-15).
3. `build_covert_event_props` returns `dict[str,Any]` that crosses engine→graph into `validate_node_write`;
   a dropped required field is caught only at runtime (L3-13).

## Current shape (verify against code now)
- `src/npc_engine/graph/scheme_reader.py:81,131` (status fields); Cypher `WHERE s.status = 'active'` at `:26,33,41`.
- `src/npc_engine/api/routes/schemes.py:25,41-44` — `response_model=OkEnvelope[dict[str,Any]]`, `.model_dump()` loop.
- `src/npc_engine/engines/scheming/covert_event_factory.py:47` — `-> dict[str, Any]`.

## Steps
1. Add `SchemeStatus = Literal["active", "discovered", "completed"]` (confirm the full set from `scheming_engine`) and `_ACTIVE_STATUS = "active"` constant; type both model fields and use the constant in the Cypher params.
2. Define `SchemesPayload(BaseModel)` wrapping `schemes: list[SchemeWithSteps]`; set the route `response_model=OkEnvelope[SchemesPayload]` and return the typed models (no `.model_dump()`).
3. Define `CovertEventProps(BaseModel)` and have `build_covert_event_props` return it; adapt the graph writer to accept the model (`.model_dump()` only at the Cypher param boundary inside `graph/`).

## Verification
- `pytest tests/ -k "schemes_route or scheme_reader or covert_event" -q` — add a test asserting the route's OpenAPI schema (or the returned model) exposes typed scheme fields, and that an invalid status is rejected by the `Literal`.
- `make check` (mypy must stay 0).

## Blast radius
`graph/scheme_reader.py`, `api/routes/schemes.py`, `engines/scheming/covert_event_factory.py`, scheme models, demo `client.get_schemes()` (it reads `data.schemes` — keep that key shape). No graph schema change.
