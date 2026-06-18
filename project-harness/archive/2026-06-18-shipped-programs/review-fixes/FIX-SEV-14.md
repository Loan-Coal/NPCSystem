# FIX-SEV-14 — Move `system_v1_router` under the admin prefix

**Severity:** LOW · **Decision:** DEC-112 (move; interface change)

## Problem
`system_v1_router` is mounted at `{API_V1_PREFIX}/system/*` while every other admin surface sits under
`{API_V1_PREFIX}/admin/*`. DEC-112: relocate it to `/v1/admin/system/*` for a consistent admin grouping
before any SDK consumer exists. This is a **public URL change**.

## Current shape (verify against code now)
- `src/npc_engine/api/router_registry.py:79` — `app.include_router(system_v1_router, prefix=settings.API_V1_PREFIX)`.
- `:98` — `admin_prefix = f"{settings.API_V1_PREFIX}/admin"`; `:99-103` mount admin routers with `prefix=admin_prefix`.
- The router's own internal prefix is defined in `api/routes/system.py` (`v1_router`). Confirm the resulting
  path so the final mount yields `/v1/admin/system/*` (avoid double `/system`).

## Steps
1. Move the `system_v1_router` include into the admin block and change its `prefix` to `admin_prefix`.
2. Confirm the composed path is `/v1/admin/system/<route>` (adjust the router's internal prefix if it would
   double up). Keep auth behavior identical (admin routers are auth-gated).
3. Update any route test and the demo `client.py` if either references `/v1/system/*`
   (grep `/v1/system`, `/system/events`).

## Verification
- A route test (FastAPI TestClient, mirror an existing admin-route test) asserts the new
  `/v1/admin/system/...` path responds and the old `/v1/system/...` path is 404.
- `pytest tests/ -k system -q` then `make check`.

## ⚠️ Gotcha discovered (2026-06-14 — NOT a quick win)
Auth is **path-prefix scoped**: `auth/middleware_helpers._required_scope_for_path` requires **admin scope**
for anything under `{API_V1_PREFIX}/admin`. So moving `/v1/system/*` → `/v1/admin/system/*` does not just
change the URL — it **escalates the required auth scope to admin**. And the DEMO consumes `/v1/system/*`
live: `demo_game/world_poller.py`, `demo_game/client.py`, `demo_game/run_scenes.py`, plus
`e2e/scenarios/scenario_active_conditions.py` and unit tests. Moving it would 403 the demo unless the demo
is given an admin key. `v1_router` exposes `/system/engines|config|metrics|events` (system.py).

Before implementing, DECIDE: (a) is admin-scoping these system-info endpoints intended (likely yes — they
expose engine/config/metrics/events), and (b) what key/scope does the demo poller use? Then update the
demo client + poller + run_scenes + the e2e scenario + tests together. Handle in a dedicated session.

## Blast radius
`router_registry.py`, **auth scope change**, `demo_game/{client,world_poller,run_scenes}.py`,
`e2e/scenarios/scenario_active_conditions.py`, system route tests. **Interface + auth change** — larger
than first scoped.
