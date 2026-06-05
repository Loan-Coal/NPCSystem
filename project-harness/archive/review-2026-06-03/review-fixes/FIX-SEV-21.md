# FIX-SEV-21 — Weak NEO4J_PASSWORD default, unbounded rate-limit dict, idempotency guidance

**Severity:** MEDIUM · **Effort:** M · **Category:** security
**Absorbs:** SEC-10, SEC-09, SEC-13

## Problem
1. `NEO4J_PASSWORD` defaults to `"password"` with NO validator (unlike `API_KEY_SECRET`),
   and `.env.example` ships it → DB compromise if unchanged in staging/prod.
2. `RateLimiter._buckets` dict never evicts → memory exhaustion via unique
   `Authorization` headers.
3. `IDEMPOTENCY_ENFORCE_HEADER=False` default → no replay protection (deployment guidance
   gap, not a code-default flip — see constraint below).

## Current shape (verified)
- `src/npc_engine/config.py:58` — `NEO4J_PASSWORD: str = Field(default="password")`
- `src/npc_engine/config.py:68` — `IDEMPOTENCY_ENFORCE_HEADER: bool = False`
- `src/npc_engine/config.py:163` — `ENV: Literal["dev","staging","prod"] = "dev"`
- `src/npc_engine/config_validators.py` — existing validator helpers (e.g.
  `check_api_key_secret`) imported by `config.py`. Add the new one here.
- `src/npc_engine/api/rate_limit.py:75,91,92,97` — `self._buckets: dict[str, _TokenBucket]`,
  inserted on first use, never evicted.

## Steps
1. **NEO4J_PASSWORD validator:** add `check_neo4j_password(value, env)` in
   `config_validators.py` and wire a `@field_validator` (likely model-level, needs `ENV`)
   in `config.py`. **Constraint to avoid breaking the suite/dev:** only REJECT the weak
   literal `"password"` when `ENV != "dev"`. In dev, allow it (warn-level log at most).
2. **Bounded `_buckets`:** cap the dict with a named `MAX_RATE_LIMIT_BUCKETS` constant via
   LRU/TTL eviction (e.g. evict the oldest/expired bucket when size exceeds the cap). No
   magic numbers; document the eviction in the class docstring.
3. **Idempotency:** do NOT flip the global code default (keeping `False` keeps tests green).
   Instead: add a `.env.example` comment recommending `IDEMPOTENCY_ENFORCE_HEADER=true` for
   staging/prod, and **flag a DECISIONS entry** for the orchestrator (do not edit DECISIONS.md).

## Verification
- `tests/unit/test_sev21_security_hardening.py`:
  - `check_neo4j_password("password", env="prod")` raises; `(…, env="dev")` does not;
    a strong password passes in every env.
  - RateLimiter never exceeds `MAX_RATE_LIMIT_BUCKETS` after inserting many unique keys;
    an evicted key behaves as a fresh bucket.
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev21_security_hardening.py -q`

## Blast radius
Config validation (a model validator that could reject prod boots with weak passwords — by
design), rate-limiter memory. Keep dev defaults working so the existing suite stays green.
