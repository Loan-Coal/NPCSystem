# FIX-SEV-16 — Type the `OkEnvelope` payload for public/SDK routes

**Severity:** MEDIUM · **Decision:** DEC-114 (public/SDK routes first)

## Problem
`response_model=` is present on all routes, but ~130 return `OkEnvelope[dict[str,Any]]` — the `data` payload
is opaque to every OpenAPI/SDK client. DEC-114: type the payload for the routes a studio actually consumes
first; defer internal/admin routes.

## Current shape (verify against code now)
- `src/npc_engine/api/route_helpers.py` — `OkEnvelope[DataT]` generic exists; `ok_response()` returns a plain dict.
- Routes return `ok_response(<dict>)` under `response_model=OkEnvelope[dict[str,Any]]`.
- Already typed (template to copy): `api/routes/schemes.py` (SEV-03 — `SchemesPayload` + `OkEnvelope[SchemesPayload]`).
- Public/SDK-facing set to do here (confirm against `router_registry.py` public mounts): `npc_state`,
  `dialogue`/`action`, `reputation`, `relationships`/graph reads consumed by the demo client. EXCLUDE
  admin-prefixed routes for now.

## Steps
1. Enumerate the public/SDK routes (cross-check `router_registry.py` non-admin includes + `demo_game/client.py` calls).
2. Per route: define a `<Route>Payload(BaseModel)` (reuse existing models where they exist), set
   `response_model=OkEnvelope[<Payload>]`, and return the typed model (drop the raw dict / trailing `.model_dump()`).
3. Keep changes additive — same JSON shape, just typed. Do NOT touch admin/internal routes (separate effort).

## Verification
- Per-route test asserts the typed field is present (and an invalid field rejected by the model); the
  route's OpenAPI `responses` schema is non-empty. `pytest tests/ -k "<route>" -q`.
- `make check` (mypy 0).

## Blast radius
The public `api/routes/*` set + payload models + their tests + possibly `demo_game/client.py` (key shapes
must stay). No admin routes.
