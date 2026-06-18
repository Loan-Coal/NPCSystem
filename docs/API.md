# NPC Engine — HTTP & WebSocket API Reference

This document covers the **complete mounted API surface** across all three audiences:

| Surface | Prefix | Audience | Auth |
|---------|--------|----------|------|
| Public game-engine | `/v1/` | Unity, Unreal, any game client | Bearer token |
| Graph read/write | `/v1/graph/*` | Game client — graph CRUD | Bearer + `graph_write` scope |
| Admin / designer tooling | `/v1/admin/*` | Designer tools, ops | Bearer + `graph_admin` scope |
| Liveness | `/health`, `/readiness` | Probes | None |

> **Production note:** restrict `/v1/admin/*` at the reverse proxy or Docker network
> layer. `graph_admin` is a strict superset of `graph_write`. See
> [ARCHITECTURE.md](ARCHITECTURE.md#auth-scope-model).

The full interactive contract (every request/response model) is always served live at
`/docs` (Swagger UI) and `/openapi.json` — treat that as the source of truth for field
shapes; this document is the curated guide.

---

## Authentication

Every route except `/health` and `/readiness` requires a Bearer token:

```
Authorization: Bearer <API_KEY_SECRET>
```

The token is a shared secret configured per deployment (not per user) via the
environment. Invalid tokens return `HTTP 401` with no internal detail.

### Scopes

A single API key carries one scope value. `graph_admin ⊃ graph_write`.

| Scope | Grants |
|-------|--------|
| *(none)* | All non-graph `/v1/` routes (dialogue, npc state, quests, clock, …) |
| `graph_write` | The above **+** `/v1/graph/*` generic node/edge CRUD and reputation reads |
| `graph_admin` | The above **+** all `/v1/admin/*` routes |

Configure dedicated keys with `API_KEY_GRAPH_WRITE` and `API_KEY_GRAPH_ADMIN`.

---

## Rate limiting

Per-API-key in-memory token bucket.

- Default **50 req/sec** sustained, burst up to **100** (`RATE_LIMIT_REQUESTS_PER_SECOND`,
  `RATE_LIMIT_BURST_SIZE`).
- Exceeded → `HTTP 429`, body `{"error": "RATE_LIMIT_EXCEEDED"}`.
- `/health` is always exempt. Disable entirely with `RATE_LIMIT_ENABLED=false`.

## Idempotency

When `IDEMPOTENCY_ENFORCE_HEADER=true`, mutating requests (`POST`, `PATCH`, `PUT`,
`DELETE`) under `/v1/*` must send an idempotency key:

```
X-Idempotency-Key: <UUIDv4>
```

Replaying the same key with the same payload returns the original stored response;
reusing it with a different payload is a conflict. See the [error table](#error-format).

> **Quest mutations are stricter.** Every `/v1/quest/*` mutation route requires three
> provenance headers on **every** call (independent of `IDEMPOTENCY_ENFORCE_HEADER`):
> `X-Request-ID`, `X-Idempotency-Key`, and `X-Idempotency-Request-Hash`. A missing one
> returns `HTTP 400 QUEST_PROVENANCE_REQUIRED`.

---

## Base URL

```
http://localhost:8000
```

---

## Health & readiness *(no auth)*

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Process liveness + build id + current tick. |
| `GET` | `/readiness` | Readiness including LLM backend reachability. |

```bash
curl http://localhost:8000/health
# {"success": true, "data": {"status": "ok", "tick": 0, "neo4j": "degraded"}}
```

---

# Public surface (`/v1`)

Requires only a valid Bearer token unless a scope is noted.

## Dialogue

### `POST /v1/dialogue`

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

`degradation_level` is one of `full | graph_only | canned` — see
[dialogue degradation tiers](ARCHITECTURE.md#dialogue-degradation-tiers).
`player_message` is capped at `MAX_PLAYER_MESSAGE_CHARS` (default 1000).

### `WS /v1/ws/dialogue`

Stream dialogue token-by-token. Requires `DIALOGUE_STREAM_ENABLED=true`.

```
# Send:    {"player_id": "player-1", "npc_id": "npc-alice", "player_message": "Hello"}
# Receive: {"type": "token", "data": "Hello"}
#          {"type": "token", "data": " there!"}
#          {"type": "action", "data": {"type": "none"}}
#          {"type": "expression", "data": {"type": "neutral"}}
#          {"type": "done"}
```

### Other dialogue routes

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/dialogue/pending?player_id=` | Pending NPC-initiated (proactive) conversation intents for a player. |
| `GET` | `/v1/dialogue/director-beats?limit=` | Recent drama-director story beats. |

## NPC state

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/npc/{npc_id}/state` | Graph state snapshot (query: `include_relations`, `include_events`, default `true`). |
| `GET` | `/v1/npc/{npc_id}/emotion` | In-memory VAD emotion snapshot (`valence`, `arousal`, `label`). |
| `GET` | `/v1/npc/{npc_id}/relationship/{other_id}` | Derived relationship Standing band between two characters. |
| `GET` | `/v1/npc/{npc_id}/player-model/{player_id}` | NPC's theory-of-mind model of a player. |
| `GET` | `/v1/npc/{npc_id}/schemes` | Active covert schemes an NPC is running. |

## Player actions

### `POST /v1/action`

Report a player action against an NPC; applies bounded relation deltas or a currency transfer.

```bash
curl -X POST http://localhost:8000/v1/action \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"player_id": "player-1", "npc_id": "npc-alice", "action_type": "help", "intensity": 1.0}'
```

## Interaction

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/interaction` | Submit a structured interaction proposal (trade, give-item, quest offer, …). |
| `POST` | `/v1/interaction/band` | Update the relationship band between two characters. |

## Quests

Every quest mutation route requires the `X-Request-ID`, `X-Idempotency-Key`, and
`X-Idempotency-Request-Hash` provenance headers — see [Idempotency](#idempotency).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/quest/offer-draft` | Offer a draft (LLM-generated) quest to a player. |
| `POST` | `/v1/quest/offer` | Offer a fully-specified quest. |
| `POST` | `/v1/quest/accept` | Accept an offered quest. |
| `POST` | `/v1/quest/objective` | Report progress on one objective. |
| `POST` | `/v1/quest/evaluate` | Evaluate whether success conditions are met. |
| `POST` | `/v1/quest/reward` | Apply rewards for a completed quest. |
| `POST` | `/v1/quest/{quest_id}/choose` | Choose a branch in a branching quest. |

```bash
curl -X POST http://localhost:8000/v1/quest/offer \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "X-Request-ID: req-001" \
  -H "X-Idempotency-Key: $(uuidgen)" \
  -H "X-Idempotency-Request-Hash: $(sha256sum <<<'{}' | cut -d' ' -f1)" \
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

## Clock

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/clock/advance` | Advance the game clock and run due engine ticks. Requires `CLOCK_MODE=game_driven`. `delta_ticks` bounded `[1, 1000]`. |
| `GET` | `/v1/clock/state` | Current clock snapshot with per-engine status and next gossip/event tick. |

```bash
curl -X POST http://localhost:8000/v1/clock/advance \
  -H "Authorization: Bearer $API_KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"delta_ticks": 1, "game_time_seconds": 60}'
```

## Investigations, chapters, locations, player events

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/investigations/{investigator_id}/{event_id}` | An NPC's investigation result for an event (alibis, witnesses). |
| `GET` | `/v1/chapters/current` | Current narrative chapter label and bounds. |
| `GET` | `/v1/locations/{location_id}/ancestors` | Location-hierarchy ancestors. |
| `GET` | `/v1/locations/{location_id}/descendants` | Location-hierarchy descendants. |
| `GET` | `/v1/player/{player_id}/events` | Event feed scoped to a player. |

## Graph CRUD — `/v1/graph/*` *(requires `graph_write`)*

Generic, registry-driven node/edge access. `{node_type}`/`{edge_type}` are validated
against the loaded type registry.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/graph/nodes/{node_type}` | List nodes of a type (paginated: `limit`, `offset`). |
| `GET` | `/v1/graph/nodes/{node_type}/{node_id}` | Fetch one node. |
| `POST` | `/v1/graph/nodes/{node_type}` | Upsert a node. |
| `PATCH` | `/v1/graph/nodes/{node_type}/{node_id}` | Patch fields on a node. |
| `GET` | `/v1/graph/edges/{edge_type}` | List edges (paginated; optional `src_id`, `dst_id`). |
| `GET` | `/v1/graph/edges/{edge_type}/{src_id}/{dst_id}` | Fetch one edge. |
| `POST` | `/v1/graph/edges/{edge_type}` | Upsert an edge. |
| `DELETE` | `/v1/graph/edges/{edge_type}/{src_id}/{dst_id}` | Delete an edge. |
| `GET` | `/v1/graph/characters/{character_id}/reputation` | List a character's faction reputations. |
| `GET` | `/v1/graph/characters/{character_id}/reputation/{faction_id}` | One reputation standing. |

```bash
curl -X POST http://localhost:8000/v1/graph/nodes/Character \
  -H "Authorization: Bearer $API_KEY_GRAPH_WRITE" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"id": "npc-bob", "name": "Bob", "is_active": true}}'
```

---

# Admin / designer surface (`/v1/admin`) *(requires `graph_admin`)*

These power designer tooling, seeding, and operations. They are **not** intended for the
public game port. Mutations honor idempotency headers when enforcement is on.

## System & observability

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/admin/system/engines` | Per-engine last-run tick, last error, error count. |
| `GET` | `/v1/admin/system/config` | Curated read-only view of cadence and cost settings. |
| `GET` | `/v1/admin/system/metrics` | Immutable snapshot of request and engine metrics. |
| `GET` | `/v1/admin/system/events` | Recent world events feed (`limit` 1–100). |
| `GET` | `/v1/admin/schema` | Loaded game schema (node/edge types, extension fields). |
| `GET` | `/v1/admin/schema/registry` | Serialized type-registry snapshot. |
| `GET` | `/v1/admin/protected` | Auth smoke-test probe. |

## Graph admin — `/v1/admin/graph/*`

| Method | Path | Purpose |
|--------|------|---------|
| `DELETE` | `/v1/admin/graph/characters/{character_id}` | Hard-delete a character + all edges (cascade). |
| `DELETE` | `/v1/admin/graph/events/{event_id}` | Hard-delete an event + edges. |
| `DELETE` | `/v1/admin/graph/locations/{location_id}` | Hard-delete a location + edges. |
| `PUT` | `/v1/admin/graph/relations/absolute` | Set a relation's absolute values (unbounded; bypasses mutation caps). |
| `POST` | `/v1/admin/graph/relations/delta` | Apply an unbounded relation delta. |
| `POST` | `/v1/admin/graph/reindex` | Submit an embedding reindex job (`202`). |
| `GET` | `/v1/admin/graph/reindex/{job_id}` | Reindex job status. |
| `GET` | `/v1/admin/graph/audit_log?limit=` | Recent admin audit entries. |

## Batch ticks — `/v1/admin/batch/*`

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/admin/batch/gossip_tick` | Run one gossip tick on demand. |
| `POST` | `/v1/admin/batch/event_tick` | Run one event-generation tick on demand. |

## Characters: beliefs, goals, items, memories, secrets, traits, skills, debts

| Method | Path | Purpose |
|--------|------|---------|
| `POST`/`GET` | `/v1/admin/beliefs/{character_id}` | Seed / list NPC beliefs. |
| `PATCH` | `/v1/admin/beliefs/{belief_id}/confidence` | Adjust belief confidence. |
| `DELETE` | `/v1/admin/beliefs/{belief_id}` | Remove a belief. |
| `POST`/`GET` | `/v1/admin/goals/{character_id}` | Seed / list goals. |
| `PATCH` | `/v1/admin/goals/{goal_id}/status` | Update goal status. |
| `DELETE` | `/v1/admin/goals/{goal_id}` | Remove a goal. |
| `POST`/`GET` | `/v1/admin/items/{character_id}` | Create / list items for a character. |
| `PATCH` | `/v1/admin/items/{item_id}/owner` | Transfer item ownership. |
| `DELETE` | `/v1/admin/items/{item_id}` | Remove an item. |
| `POST`/`GET` | `/v1/admin/memories/{character_id}` | Seed / list memories. |
| `POST` | `/v1/admin/memories/from-arousal/{character_id}` | Form a memory from a high-arousal moment. |
| `POST` | `/v1/admin/memories/decay` | Run vividness decay. |
| `POST` | `/v1/admin/memories/consolidate/{npc_id}` | Consolidate session turns into long-term memory (LLM). |
| `DELETE` | `/v1/admin/memories/{memory_id}` | Remove a memory. |
| `POST`/`GET` | `/v1/admin/secrets/{character_id}` | Create / list secrets. |
| `DELETE` | `/v1/admin/secrets/{secret_id}` | Remove a secret. |
| `POST`/`GET` | `/v1/admin/traits/characters/{character_id}` | Add / list character traits. |
| `DELETE` | `/v1/admin/traits/characters/{character_id}/{trait_id}` | Remove a trait. |
| `POST`/`GET` | `/v1/admin/skills/characters/{character_id}` | Add / list character skills. |
| `POST` | `/v1/admin/skills/characters/{character_id}/xp` | Award XP across skills. |
| `POST` | `/v1/admin/skills/characters/{character_id}/{skill_id}/xp` | Award XP to one skill. |
| `GET` | `/v1/admin/skills/characters/{character_id}/{skill_id}/check` | Resolve a skill check. |
| `GET` | `/v1/admin/skills/{skill_id}/characters` | List characters with a skill. |
| `POST` | `/v1/admin/debts/{debtor_id}` | Create a debt. |
| `GET` | `/v1/admin/debts/{character_id}` | List debts. |
| `PATCH` | `/v1/admin/debts/{debtor_id}/{creditor_id}` | Update debt status. |

## Factions, reputation, pledges, treaties

| Method | Path | Purpose |
|--------|------|---------|
| `POST`/`GET` | `/v1/admin/factions/` | Create / list factions. |
| `GET` | `/v1/admin/factions/{faction_id}` | Get a faction. |
| `POST`/`GET` | `/v1/admin/factions/{faction_id}/members` | Add / list members. |
| `DELETE` | `/v1/admin/factions/{faction_id}/members/{character_id}` | Remove a member. |
| `PUT`/`GET` | `/v1/admin/factions/{faction_id}/standings[/{target_id}]` | Set / list faction standings. |
| `POST`/`DELETE` | `/v1/admin/factions/{faction_id}/controls/{location_id}` | Set / remove location control. |
| `PUT` | `/v1/admin/characters/{character_id}/reputation/{faction_id}` | Set a character's faction reputation. |
| `POST` | `/v1/admin/characters/{character_id}/reputation/{faction_id}/adjust` | Adjust reputation by delta. |
| `POST`/`GET` | `/v1/admin/pledges/characters/{character_id}` | Create / list pledges. |
| `POST` | `/v1/admin/pledges/characters/{character_id}/break` | Break a pledge. |
| `POST` | `/v1/admin/treaties/` | Create a treaty. |
| `GET` | `/v1/admin/treaties/factions/{faction_id}` | List a faction's treaties. |
| `POST` | `/v1/admin/treaties/{treaty_id}/expire` | Expire a treaty. |
| `POST` | `/v1/admin/treaties/{treaty_id}/break` | Break a treaty. |

## Social: groups, rumors, gossip, witnessed, causality

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/admin/groups` | Create a clique/group. |
| `GET` | `/v1/admin/groups/{character_id}` | List a character's groups. |
| `GET` | `/v1/admin/groups/members/{group_id}` | List group members. |
| `POST` | `/v1/admin/groups/{group_id}/members` | Add a member. |
| `DELETE` | `/v1/admin/groups/{group_id}` | Dissolve a group. |
| `POST` | `/v1/admin/rumors` | Create a rumor. |
| `POST` | `/v1/admin/rumors/{rumor_id}/believe` | Mark a rumor believed. |
| `GET` | `/v1/admin/rumors/{character_id}` | Rumors known by a character. |
| `GET` | `/v1/admin/rumors/tree/{rumor_id}` | Rumor propagation tree. |
| `GET` | `/v1/admin/rumors/event/{event_id}` | Rumors about an event. |
| `POST` | `/v1/admin/gossip/spread` | Spread a rumor between NPCs on demand. |
| `GET` | `/v1/admin/gossip/trace/{event_id}` | Trace how a rumor spread from an event. |
| `POST` | `/v1/admin/gossip/correct` | Issue a correction to a false rumor. |
| `GET` | `/v1/admin/witnessed/event/{event_id}` | Witnesses of an event. |
| `GET` | `/v1/admin/witnessed/by/{subject_id}` | Observations of a subject. |
| `PATCH` | `/v1/admin/witnessed/disclose?witness_id=` | Disclose a witnessed observation. |
| `GET` | `/v1/admin/causality/chain/{event_id}` | Consequence chain from an event. |
| `GET` | `/v1/admin/causality/causes/{node_id}` | Direct causes of a node. |

## Economy, quest generation, schedules, locations, history

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/admin/economy/price?item_type=` | Deterministic item price. |
| `POST` | `/v1/admin/economy/trade` | Evaluate a trade offer. |
| `POST` | `/v1/admin/quests/generate` | LLM-generate a draft quest. |
| `GET` | `/v1/admin/quests/drafts?quest_giver_id=` | List draft quests. |
| `POST` | `/v1/admin/quests/{quest_id}/offer` | Offer a draft quest. |
| `GET` | `/v1/admin/quests/{quest_id}` | Get a quest node. |
| `POST` | `/v1/admin/schedules/` | Create a schedule. |
| `GET` | `/v1/admin/schedules/{schedule_id}` | Get a schedule. |
| `POST` | `/v1/admin/schedules/{schedule_id}/assign/{character_id}` | Assign a schedule. |
| `DELETE` | `/v1/admin/schedules/{character_id}/unassign` | Unassign a schedule. |
| `GET` | `/v1/admin/schedules/character/{character_id}[/at]` | A character's schedule / location at a time. |
| `GET` | `/v1/admin/schedules/location/{location_id}/at` | Characters at a location at a time. |
| `POST` | `/v1/admin/locations/{child_id}/part_of` | Add a location-hierarchy edge. |
| `DELETE` | `/v1/admin/locations/{child_id}/part_of/{parent_id}` | Remove a hierarchy edge. |
| `GET` | `/v1/admin/location-history/{character_id}` | A character's movement history. |
| `GET` | `/v1/admin/location-history/alibi/{character_id}` | Alibi window for a character. |
| `DELETE` | `/v1/admin/location-history/{character_id}/prune` | Prune old history. |

## Debug

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/admin/debug/retrieval?npc_id=` | Inspect the assembled dialogue context (tiers, scores, budget) for an NPC. |

---

## OpenAPI

The full interactive spec is served at `/docs` (Swagger UI) and `/openapi.json`.

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

---

## External Seeding & E2E

All tooling runs **outside** Docker against the exposed API on port `8000`.
Ensure the stack is up (`docker compose up`) before running any command below.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NPC_BASE_URL` | `http://localhost:8000` | API base URL for tooling and scenarios |
| `NPC_API_KEY` | `local_dev_secret_change_this_2026` | Bearer token (must match `API_KEY_SECRET` in `.env`) |

### Seed world data

Seeds locations, characters, edges, events, and knowledge via the HTTP API. Idempotent.

```bash
make seed-api
# or:
python src/npc_engine/data/api_seeder.py \
  --base-url http://localhost:8000 \
  --api-key local_dev_secret_change_this_2026
```

> **Note:** The WorldState node is created lazily by the engine on first clock advance.

### Smoke test

```bash
make smoke
# or:
python e2e/scripts/gateway_smoke.py \
  --base-url http://localhost:8000 \
  --api-key local_dev_secret_change_this_2026
```

### Scenario tests

Scenario tests use `NPC_BASE_URL` / `NPC_API_KEY`. Run after `make seed-api`.

```bash
make scenarios
# single:
NPC_API_KEY=local_dev_secret_change_this_2026 \
  python -m pytest e2e/scenarios/scenario_reputation_drift.py -v --scenarios-only
```

Transcripts are written to `transcripts/` (gitignored).

### Migration scripts

Migration scripts connect to Neo4j directly via Bolt (default `bolt://localhost:7687`,
the exposed Docker port).

```bash
NEO4J_PASSWORD=password python scripts/migrations/add_faction_support.py
```

> **Warning:** Do not `source`/`export` the project `.env` before running these — `.env`
> sets `NEO4J_URI=bolt://neo4j:7687` (container hostname), unreachable from the host.
