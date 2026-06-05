# FIX-SEV-20 — Close auth-surface gaps (/readiness, docs, WS limits)

**Severity:** MEDIUM · **Effort:** M · **Category:** security
**Absorbs:** SEC-01, SEC-02, SEC-12

## Problem
- `/readiness` is reachable without a token (infra enumeration).
- `/docs`, `/redoc`, `/openapi.json` are public in ALL environments (full API-surface
  enumeration in staging/prod).
- The `/ws/dialogue` WebSocket re-implements auth inline and bypasses
  `RateLimitMiddleware`, so per-frame LLM calls are unmetered.

## Current shape (verified)
- `src/npc_engine/auth/middleware_helpers.py:28` — `DOCS_PATHS = frozenset({"/docs","/redoc","/openapi.json"})`
- `src/npc_engine/auth/middleware_helpers.py:56` — `def is_public_path(path: str) -> bool`
  treats DOCS_PATHS (and the dashboard prefix) as always-public.
- `src/npc_engine/api/routes/system.py:44-46` — `@router.get("/readiness")` (confirm
  whether it is reachable without auth; if `/readiness` is matched as public or the
  router is mounted before auth, close that).
- `src/npc_engine/api/routes/dialogue_ws.py` — inline WS auth; no rate limiting.
- `src/npc_engine/config.py:163` — `ENV` Literal available for gating.

## Steps
1. **/readiness:** ensure it requires auth (only `GET /health` is public). If the
   public-path check or router mount currently exempts it, fix so a tokenless request
   gets 401.
2. **docs gating:** make `is_public_path` env-aware so DOCS_PATHS are public ONLY when
   `ENV == "dev"`. This changes the signature (e.g. `is_public_path(path, *, env) -> bool`
   or pass `settings`); update ALL callers in `auth/` accordingly. Keep `/health` public
   in every env.
3. **WS limits:** add a per-key cap on concurrent WS connections and/or turns-per-window
   for `/ws/dialogue` (reuse the existing limiter/config; do NOT edit `api/rate_limit.py`
   internals — instantiate/reuse the limiter from the WS handler). Use named constants
   (no magic numbers).
4. **Flag (do NOT write):** the WS auth duplication warrants a DECISIONS entry. Report it
   so the orchestrator writes it during fan-in. Do not edit DECISIONS.md.

## Verification
- `tests/unit/test_sev20_auth_surface.py`:
  - `is_public_path("/readiness", env="dev")` is False.
  - `is_public_path("/docs", env="dev")` True; `is_public_path("/docs", env="prod")` False.
  - `is_public_path("/health", env="prod")` True.
  - A WS-limit unit test for the per-key cap helper (constant respected; over-limit rejected).
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev20_auth_surface.py -q`

## Blast radius
Auth middleware public-path decision (signature change, internal to `auth/`) and the WS
dialogue handler. Keep `/health` open; do not break dev docs access.
