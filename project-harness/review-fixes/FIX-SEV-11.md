# SEV-11 — Auth wiring on the production app has no regression test

**HIGH** · Finding **L4-02** (tests) · Confidence: Confirmed · Evidence: `evidence/L4.md`

## Problem

Every test that proves "auth is required" builds its **own** FastAPI app and attaches
`ApiKeyMiddleware` by hand. Nothing exercises the middleware stack that `create_app()` actually
assembles. If a future change reorders, drops, or mis-scopes the middleware in `main.py`, the entire test
suite stays green and the API ships unauthenticated.

This is the highest-consequence instance of §3.4 (asserted-not-measured) in the suite: the control is
real, and the wiring that installs it is untested.

## Current shape

- `tests/unit/api/test_dialogue_pending_route.py:45-56,110-119` — uses the **real** `ApiKeyMiddleware`,
  but on a hand-built `FastAPI()` app, not on `create_app()`
- `src/npc_engine/main.py:271-278` — where the production middleware stack is actually assembled
- `tests/unit/conformance/test_sev20_auth_surface.py` — enumerates the auth surface, but does not
  exercise the composed application

The related route-enumeration guard does exist and holds; this fix is about the **composed app**, not
about which routes are public.

## Steps

1. Add a test that builds the app through **`create_app()`** — the real composition root — and drives it
   with `TestClient`.
2. Assert, against the composed app:
   - `GET /health` is reachable **without** credentials
   - a representative route from **each** router group returns **401** without credentials
   - a valid key succeeds on those same routes
   - `/readiness`, `/docs` and the admin surface are gated
   - 401/403 responses carry **no body** (the existing no-body policy)
3. Drive the route list **mechanically** from the app's own router table rather than hardcoding a list,
   so a newly added route is covered the day it is added. A hardcoded list would recreate the same
   asserted-not-measured gap one level up.
4. Keep it a unit test — no Neo4j, no live services. Stub the dependencies `create_app()` needs.

## Verification

Confirm the test fails for the right reason before it passes: temporarily comment out the middleware
registration in `main.py`, run the new test, and confirm it goes **red**. Restore. That step is the whole
point of this fix — a test that cannot fail proves nothing.

```
pytest tests/unit/api/test_create_app_auth_wiring.py -v
make check
```

## Blast radius

Test-only. No source change. The one risk is `create_app()` requiring live dependencies at import or
startup — if so, stub them at the seam rather than weakening the test to a hand-built app, which would
reintroduce the exact defect.

**Sequencing:** fully independent — parallelisable.
