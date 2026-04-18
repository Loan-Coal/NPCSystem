# Write-Path Convergence (P0)

## Scope
This document defines the converged write-path behavior delivered in v1.4 P0 for transport idempotency and response replay safety.

Included:
- Mutating `/v1/*` requests (`POST`, `PATCH`, `PUT`, `DELETE`).
- Header-level idempotency contract enforcement.
- Persistent idempotency state in Neo4j.
- Terminal response capture and replay.
- Expiry cleanup loop.

Out of scope:
- Currency/quest domain-level transactional convergence (P2/P3).
- Redis-backed idempotency state.

## Converged Flow
1. Client sends mutating request with `X-Idempotency-Key` (UUIDv4).
2. `ApiKeyMiddleware` validates auth/scope, then idempotency key format.
3. Middleware computes preflight input and calls `IdempotencyService.preflight(...)`.
4. Service resolves `resource_scope = METHOD:path` and `request_hash = sha256(method|path|query|body)`.
5. Service checks `IdempotencyRecord` by `(idempotency_key, resource_scope)`:
- Missing record: create `pending`, return `proceed`.
- Different `request_hash`: return `conflict`.
- `completed` or `failed_terminal`: return `replay` with stored response.
- `pending` and still within timeout: return `in_flight`.
- `pending` and timeout expired: refresh `pending`, return `proceed`.
6. If decision is `proceed`, route handler executes.
7. Middleware materializes response body and calls `IdempotencyService.finalize(...)`.
8. Service writes terminal state:
- `<500` status: `completed`.
- `>=500` status: `failed_terminal`.
9. Future matching requests replay stored response deterministically.

## Persistence Model
Neo4j label: `IdempotencyRecord`

Key fields:
- `idempotency_key`
- `resource_scope`
- `request_hash`
- `status` (`pending`, `completed`, `failed_terminal`)
- `response_status_code`, `response_body`, `response_hash`
- `created_at`, `updated_at`, `expires_at`
- `pending_timeout_seconds`

Constraint:
- Unique `(idempotency_key, resource_scope)`

## Background Cleanup
`IdempotencyCleanupScheduler` runs every `IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS` and deletes records where `expires_at < now`.

## Operational Notes
- Header enforcement remains controlled by `IDEMPOTENCY_ENFORCE_HEADER` for rollout safety.
- Redis integration is optional and currently reserved for non-idempotency runtime caches.
- Startup is fail-fast for schema and llm config, but Redis connect degrades gracefully when unavailable.

## Verification Evidence
Primary gate:
- `make verify-v14-p0`

Includes:
- lint (`ruff`)
- type-check (`mypy`)
- contract validation (`make check-contracts`)
- idempotency middleware/service + lifespan tests
