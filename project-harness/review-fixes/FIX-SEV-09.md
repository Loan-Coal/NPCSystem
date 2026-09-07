# SEV-09 — `/ws/dialogue` has no throughput rate limit

**HIGH** · Finding **L1-01** (security) · Confidence: Confirmed · Evidence: `evidence/L1.md`

## Problem

The WebSocket dialogue endpoint has a **concurrency** cap (5 connections per key) but no **throughput**
limit. `RateLimitMiddleware` is a `BaseHTTPMiddleware`, and `BaseHTTPMiddleware` never sees
`scope["type"] == "websocket"` — so it is **structurally bypassed** for the one endpoint that triggers an
LLM call per connection.

An authenticated key can therefore drive unbounded model calls through the WS path. Given SEV-04 (no
admission control) and one resident model, that is a denial-of-service against the interactive path, not
just a quota problem — a single client can starve every other player.

## Current shape

- `src/npc_engine/api/routes/dialogue/dialogue_ws.py:50` — `MAX_WS_CONNECTIONS_PER_KEY: int = 5`
  (concurrency only)
- `src/npc_engine/api/rate_limit.py` — `RateLimitMiddleware` derives from `BaseHTTPMiddleware`, which is
  invoked only for HTTP scopes; WS connections bypass it entirely
- No per-key token bucket exists inside the WS handler
- The HTTP dialogue route **is** rate-limited — so the two paths to the same engine have different
  protection, which is what makes this easy to miss

L1 confirmed the fix is internal and non-breaking: no schema, dependency or public-interface change.

## Steps

1. Add a **per-key token bucket inside the WS handler**, applied per dialogue turn (not per connection —
   per connection is what the existing cap already does, and it is the wrong unit for throughput).
2. Reuse the existing rate-limit accounting from `api/rate_limit.py` rather than writing a second
   implementation — one policy, two transports. Extract the bucket logic if it is currently welded to
   the middleware class.
3. On exceeding the limit, close the socket with a defined code and a structured log line (via
   `utils/logging.py`), consistent with how `ws_connection_cap_reached` is already reported.
4. Make the limit a named config field with a documented default; no literals.
5. Keep the error body free of internal detail, consistent with the existing 401/403 no-body policy.

## Verification

Write the failing test first:

`tests/unit/api/test_ws_dialogue_rate_limit.py`
- Drive more turns per interval than the limit **on a single connection** and assert the socket is closed
  with the expected code. On the current tree this fails — turns are unlimited.
- Assert a conforming rate is unaffected.
- Assert the limit is **per key**, not global (two keys do not interfere).

```
pytest tests/unit/api/test_ws_dialogue_rate_limit.py -v
make check
```

Live: confirm `make demo-run` still completes all 12 ACTs — the scripted demo's turn rate must sit
comfortably under the new limit. If it does not, the limit is too tight.

## Blast radius

One handler in `dialogue_ws.py`, plus a possible extraction in `api/rate_limit.py`. If you extract the
bucket, the HTTP rate-limit tests must keep passing unchanged — that is the regression risk.

Tuning risk: a limit set below legitimate play rate breaks the demo. Derive it from the demo's actual
turn cadence, then leave headroom.

**Sequencing: land SEV-01 FIRST.** Both edit the same handler, and SEV-01 is a CRITICAL that also has to
be verified live — verification which is impossible while the socket cap is leaking. Do not parallelise
these two.
