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

## ⚠️ Scoping finding (2026-06-14)
This is genuinely L-effort: **35 route files** use `OkEnvelope[dict[str,Any]]`, and `npc_state`/`emotion`/
`schemes` are ALREADY typed. Crucially, **many payloads are dynamic engine-aggregate dicts**, not fixed
shapes — e.g. `clock.clock_state` returns `scheduler.state.model_dump()` + 3 runtime keys + `engine_status`
(dict per engine); `clock.advance_clock` returns the scheduler's `advance()` result dict merged with an
optional `world_state`. A precise model requires real per-route modeling, and a wrong model breaks
`response_model` validation at runtime. **Do route-by-route, fixed-shape routes first** (mirror SEV-03's
`SchemesPayload`); leave genuinely-heterogeneous aggregates (clock, batch) as `dict[str,Any]` with a comment.
Pick the demo-consumed reads with a stable shape (e.g. `player_model`, `chapters/current`, `investigations`)
as batch 1. Not a single-commit job — sub-phase it.

## Blast radius
The public `api/routes/*` set (~32 still untyped) + payload models + their tests + possibly
`demo_game/client.py` (key shapes must stay). No admin routes. Multi-commit.
