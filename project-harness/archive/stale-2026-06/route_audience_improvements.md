# Improvements and Flaws Found During Phase 0.3 Implementation

---

## 1. WebSocket auth is not covered by middleware

**File:** `src/npc_engine/api/routes/dialogue_ws.py`
**Severity:** P2

The `ApiKeyMiddleware` does not intercept WebSocket upgrade requests — Starlette's
`BaseHTTPMiddleware` only wraps HTTP requests. Auth for `WS /v1/ws/dialogue` is
validated inline in the route handler via `resolve_scope_from_authorization`. This
means:

- `RateLimitMiddleware` also does not apply to WebSocket connections.
- Request logging (via `_record_request_observability`) also does not apply.

**Consequence:** A client can bypass both rate limiting and observability by using the
WebSocket endpoint.

**Proposed fix:** Add a WebSocket-specific middleware or move WS auth/rate-limit logic
into a shared decorator. Alternatively, accept the limitation and document it, since
the WS endpoint requires a full NPC dialogue session setup which is naturally
rate-limited by LLM latency.

---

## 2. Rate limiter buckets grow without bound

**File:** `src/npc_engine/api/rate_limit.py`
**Severity:** P3

`RateLimitMiddleware._buckets` is a plain dict that accumulates one `_TokenBucket`
per distinct Authorization header value seen. In a deployment with rotating API keys
or many short-lived clients, this grows indefinitely.

**Proposed fix:** Add a periodic sweep that removes buckets whose `_last_refill` is
older than `capacity / rate` seconds (i.e., buckets that are already full and have
been idle long enough that they'd refill anyway). A simple approach: evict entries
older than `2 * RATE_LIMIT_BURST_SIZE / RATE_LIMIT_REQUESTS_PER_SECOND` seconds.
This can be done lazily on each `consume()` call or on a background sweep.

---

## 3. Single shared secret makes per-key rate limiting coarse

**File:** `src/npc_engine/config.py`, `src/npc_engine/auth/api_key.py`
**Severity:** P2

The current auth model supports one shared secret (`API_KEY_SECRET`) plus optional
per-scope keys (`API_KEY_GRAPH_WRITE`, `API_KEY_GRAPH_ADMIN`). With only 2-3 distinct
keys in the system, rate limiting "per API key" effectively means per-scope rather than
per-client. Multiple game-engine instances all using the same key share one bucket.

**Proposed fix for a future session:** Move to per-client API key issuance (even if
stored in a simple config file or env var list). This is a prerequisite for meaningful
per-client rate limiting.

---

## 4. `/v1/graph/*` requires `graph_write` scope — friction for game-engine clients

**File:** `src/npc_engine/auth/middleware_helpers.py`
**Severity:** P2

The route audience split marks `/v1/graph/*` as "game-engine public", but the scope
check still requires `graph_write`. A game-engine client that only has the base
`API_KEY_SECRET` (which resolves to no scope) will get 403 on all graph routes.

This seems intentional — graph writes are privileged even from the game engine — but
it creates a two-key management burden (base key + write-scope key) for game-engine
developers who just want to store NPC positions or custom node data.

**Options:**
  A. Keep `graph_write` scope required and document that game-engine clients need the
     write-scope key (current behavior).
  B. Make a new scope `game_engine` that covers graph CRUD but not admin operations.
  C. Make a subset of graph routes (reads) not require a scope, and keep writes
     scope-gated.

Worth a DECISIONS.md entry when this friction is confirmed by an actual integration.

---

## 5. `_required_scope_for_path` scope behavior change for `/v1/schema`

**File:** `src/npc_engine/auth/middleware_helpers.py`
**Severity:** P1 (breaking, documented)

Pre-Phase-0.3, `GET /v1/schema` required only bearer auth (no scope). Post-split, the
route moved to `/v1/admin/schema` which now requires `graph_admin` scope. Any existing
client hitting `/v1/schema` will get 404 (route gone), not 401/403. Any client hitting
`/v1/admin/schema` without `graph_admin` scope will get 403.

**Action:** This is expected and intentional. Document in the upgrade notes that
designer-tool clients must use `API_KEY_GRAPH_ADMIN` when calling schema introspection
endpoints.

---

## 6. `docker-compose.yml` `internal: true` network blocks Neo4j browser

**File:** `docker-compose.yml`
**Severity:** P3

Setting `internal: true` on the `internal` network means containers on that network
have no outbound internet access. This is desirable for production but may surprise
developers who rely on the Neo4j browser at `localhost:7474` during development —
`internal: true` does not block the host port mapping, so browser access still works.
However, any container on the internal network that needs to reach an external service
(e.g., a cloud LLM endpoint, Qdrant cloud) will be blocked.

**Proposed fix:** For development, consider removing `internal: true` or adding an
`external` network for containers that need outbound access. For production, keep it.
A docker-compose override file (`docker-compose.override.yml`) can toggle this without
touching the canonical file.
