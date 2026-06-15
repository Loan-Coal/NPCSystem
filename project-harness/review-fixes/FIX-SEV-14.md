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

## Blast radius
`router_registry.py` + system route tests + possibly `demo_game/client.py`. **Interface change** — any
external client calling `/v1/system/*` must update.
