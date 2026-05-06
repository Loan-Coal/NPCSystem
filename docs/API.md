# NPC Engine — Public API Reference

This document covers the **game-engine public surface** only: routes under `/v1/`.
Designer/tooling routes under `/v1/admin/` are not documented here and must not be
exposed on the public port in production.

---

## Authentication

Every route (except `/health`) requires a Bearer token:

```
Authorization: Bearer <API_KEY_SECRET>
```

The token is a shared secret configured via `API_KEY_SECRET` in the environment.
Game-engine routes require only a valid token (no additional scope).
Admin routes additionally require the `graph_write` or `graph_admin` scope —
see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Rate Limiting

Requests are rate-limited per API key (token bucket, in-memory).

- Default: **50 req/sec** sustained, burst up to **100 requests**.
- Configurable via `RATE_LIMIT_REQUESTS_PER_SECOND` and `RATE_LIMIT_BURST_SIZE`.
- Exceeded limit → `HTTP 429` with body `{"error": "RATE_LIMIT_EXCEEDED"}`.
- `/health` is always exempt.

---

## Base URL

```
http://localhost:8000
```

---

## Routes

### Health

#### `GET /health`

No authentication required.

```bash
curl http://localhost:8000/health
```

Response `200 OK`:
```json
{"success": true, "data": {"status": "ok", "tick": 0, "neo4j": "degraded"}}
```

---

### Dialogue

#### `POST /v1/dialogue`

Run one synchronous dialogue turn with an NPC.

```bash
curl -X POST http://localhost:8000/v1/dialogue \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player-1",
    "npc_id": "npc-alice",
    "player_message": "Have you heard any news lately?"
  }'
```

Response `200 OK`:
```json
{
  "success": true,
  "data": {
    "npc_response": "Aye, there was a fire at the docks last night.",
    "action": {"type": "none"},
    "facial_expression": {"type": "neutral"},
    "degradation_level": "full"
  }
}
```

#### `WS /v1/ws/dialogue`

Stream dialogue token-by-token over WebSocket. Requires `DIALOGUE_STREAM_ENABLED=true`.

```bash
wscat -c ws://localhost:8000/v1/ws/dialogue \
  -H "Authorization: Bearer $API_KEY_SECRET"
# Send:
# {"player_id": "player-1", "npc_id": "npc-alice", "player_message": "Hello"}
# Receive:
# {"type": "token", "data": "Hello"}
# {"type": "token", "data": " there!"}
# {"type": "action", "data": {"type": "none"}}
# {"type": "expression", "data": {"type": "neutral"}}
# {"type": "done"}
```

---

### NPC State

#### `GET /v1/npc/{npc_id}/state`

Return the current graph state snapshot for one NPC.

```bash
curl http://localhost:8000/v1/npc/npc-alice/state \
  -H "Authorization: Bearer $API_KEY_SECRET"
```

Query params: `include_relations` (bool, default `true`), `include_events` (bool, default `true`).

Response `200 OK`:
```json
{
  "success": true,
  "data": {
    "character": {"id": "npc-alice", "name": "Alice", ...},
    "relations": [...],
    "events": [...]
  }
}
```

#### `GET /v1/npc/{npc_id}/emotion`

Return the in-memory emotion snapshot for one NPC.

```bash
curl http://localhost:8000/v1/npc/npc-alice/emotion \
  -H "Authorization: Bearer $API_KEY_SECRET"
```

Response `200 OK`:
```json
{
  "success": true,
  "data": {
    "npc_id": "npc-alice",
    "label": "calm",
    "valence": 0.2,
    "arousal": 0.1,
    "updated_at": "2026-05-05T10:00:00Z"
  }
}
```

---

### Player Actions

#### `POST /v1/action`

Report a player action against an NPC. Applies conservative relation deltas or executes
a currency transfer.

```bash
curl -X POST http://localhost:8000/v1/action \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player-1",
    "npc_id": "npc-alice",
    "action_type": "help",
    "intensity": 1.0
  }'
```

Response `200 OK`:
```json
{"success": true, "data": {"status": "ok", "applied_deltas": {...}}}
```

---

### Clock

#### `POST /v1/clock/advance`

Advance the game clock and trigger due engine ticks. Requires `CLOCK_MODE=game_driven`.

```bash
curl -X POST http://localhost:8000/v1/clock/advance \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"delta_ticks": 1, "game_time_seconds": 60}'
```

Response `200 OK`:
```json
{"success": true, "data": {"ticks_advanced": 1, ...}}
```

#### `GET /v1/clock/state`

Return current clock snapshot.

```bash
curl http://localhost:8000/v1/clock/state \
  -H "Authorization: Bearer $API_KEY_SECRET"
```

---

### Quests

All quest routes require an `X-Request-ID` header, an idempotency key
(`X-Idempotency-Key`), and an `X-Idempotency-Request-Hash` header when
`IDEMPOTENCY_ENFORCE_HEADER=true`.

#### `POST /v1/quest/offer`

Offer a quest to a player.

```bash
curl -X POST http://localhost:8000/v1/quest/offer \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "X-Request-ID: req-001" \
  -H "X-Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "quest_id": "q-001",
    "player_id": "player-1",
    "title": "Find the lost amulet",
    "objectives": [{"objective_id": "find-amulet", "target_count": 1}],
    "item_rewards": [],
    "currency_reward": null
  }'
```

#### `POST /v1/quest/accept`

Accept an offered quest.

#### `POST /v1/quest/objective`

Report progress on one quest objective.

#### `POST /v1/quest/evaluate`

Evaluate whether a quest's success conditions are met.

#### `POST /v1/quest/reward`

Apply rewards for a completed quest.

---

### Graph (game-engine read/write)

These routes require `graph_write` scope. Use `API_KEY_GRAPH_WRITE` as the bearer
token, or a key whose resolved scope includes `graph_write`.

#### `GET /v1/graph/nodes/{node_type}`

List nodes of a type (paginated).

```bash
curl "http://localhost:8000/v1/graph/nodes/Character?limit=10&offset=0" \
  -H "Authorization: Bearer $API_KEY_GRAPH_WRITE"
```

#### `GET /v1/graph/nodes/{node_type}/{node_id}`

Fetch one node.

#### `POST /v1/graph/nodes/{node_type}`

Upsert a node.

```bash
curl -X POST http://localhost:8000/v1/graph/nodes/Character \
  -H "Authorization: Bearer $API_KEY_GRAPH_WRITE" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"id": "npc-bob", "name": "Bob", "is_active": true}}'
```

#### `PATCH /v1/graph/nodes/{node_type}/{node_id}`

Patch specific fields on an existing node.

#### `GET /v1/graph/edges/{edge_type}`

List edges of a type (paginated). Optional `src_id` and `dst_id` filters.

#### `GET /v1/graph/edges/{edge_type}/{src_id}/{dst_id}`

Fetch one edge.

#### `POST /v1/graph/edges/{edge_type}`

Upsert an edge.

```bash
curl -X POST http://localhost:8000/v1/graph/edges/RELATES_TO \
  -H "Authorization: Bearer $API_KEY_GRAPH_WRITE" \
  -H "Content-Type: application/json" \
  -d '{"src_id": "npc-alice", "dst_id": "npc-bob", "properties": {"trust": 50}}'
```

#### `DELETE /v1/graph/edges/{edge_type}/{src_id}/{dst_id}`

Delete an edge.

---

## OpenAPI

The full interactive spec is served at `/docs` (Swagger UI) and `/openapi.json`.

---

## Error format

All errors use a consistent envelope:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable description.",
  "request_id": "req-abc123"
}
```

Common codes:

| Code | HTTP | Meaning |
|------|------|---------|
| `RATE_LIMIT_EXCEEDED` | 429 | Token bucket exhausted for this API key |
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Mutating request missing idempotency header |
| `IDEMPOTENCY_KEY_INVALID` | 422 | Idempotency key is not a valid UUIDv4 |
| `IDEMPOTENCY_KEY_CONFLICT` | 409 | Key reused with different request payload |
| `IDEMPOTENCY_IN_FLIGHT` | 409 | Identical request is still processing |
