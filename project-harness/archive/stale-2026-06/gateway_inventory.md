# Gateway Route Inventory

Source of truth: `src/npc_engine/main.py`, `src/npc_engine/api/routes/`, `src/npc_engine/auth/`.

Default `API_V1_PREFIX = "/v1"`.

---

## Auth model (current)

Auth lives in `auth/middleware.py` (`ApiKeyMiddleware`), applied globally via `app.add_middleware`.

- `/health` — **no auth** (HEALTH_PATH bypass)
- All other routes — require `Authorization: Bearer <token>` header
- `_required_scope_for_path` applies scope checks:
  - `/v1/graph/admin/*` → requires `graph_admin` scope
  - `/v1/graph/*` (non-admin) → requires `graph_write` scope
  - All other auth'd routes → auth only, no scope restriction
- Scope hierarchy: `graph_admin` implies `graph_write`

Auth tokens are resolved by `auth/api_key.py` against `Settings`.

---

## Route inventory

### system_router — no prefix (routes as declared)

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| GET | `/health` | none | none | none (inline) | **public** |
| GET | `/v1/protected` | bearer | none | none (inline smoke probe) | public (smoke only) |
| GET | `/v1/schema` | bearer | none | `SchemaConfig` via deps | internal (designer tool) |
| GET | `/v1/schema/registry` | bearer | none | `TypeRegistry` via deps | internal (designer tool) |

Note: `/health` is registered without the v1 prefix. `/v1/protected` and `/v1/schema` are hardcoded paths on the `system_router`; they do not use `settings.API_V1_PREFIX` at include-time.

---

### dialogue_router — prefix `/v1`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| POST | `/v1/dialogue` | bearer | none | `DialogueHandler.handle()` | **public** (game engine) |

---

### dialogue_ws_router — prefix `/v1` (conditional on `DIALOGUE_STREAM_ENABLED`)

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| WS | `/v1/ws/dialogue` | bearer (in-handler) | none | `DialogueHandler.handle()` stream | **public** (game engine) |

Note: WebSocket auth is validated inline in the handler; middleware does not intercept WS upgrades for bearer checks in the current implementation.

---

### npc_state_router — prefix `/v1`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| GET | `/v1/npc/{npc_id}/state` | bearer | none | `graph_reader` (get_character_with_relations, get_events_for_npc) | **public** (game engine) |
| GET | `/v1/npc/{npc_id}/emotion` | bearer | none | `EmotionStore.get()` | **public** (game engine) |

---

### action_router — prefix `/v1`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| POST | `/v1/action` | bearer | none | `graph_writer` (apply_relation_delta / apply_buy_sell_currency_transfer) | **public** (game engine) |

---

### quest_router — prefix `/v1`, sub-prefix `/quest`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| POST | `/v1/quest/offer` | bearer | none | `QuestLifecycleEngine.offer_quest()` | **public** (game engine) |
| POST | `/v1/quest/accept` | bearer | none | `QuestLifecycleEngine.accept_quest()` | **public** (game engine) |
| POST | `/v1/quest/objective` | bearer | none | `QuestLifecycleEngine.update_objective()` | **public** (game engine) |
| POST | `/v1/quest/evaluate` | bearer | none | `QuestLifecycleEngine.evaluate_completion()` | **public** (game engine) |
| POST | `/v1/quest/reward` | bearer | none | `QuestLifecycleEngine.apply_rewards()` | **public** (game engine) |

---

### clock_router — prefix `/v1`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| POST | `/v1/clock/advance` | bearer | none | `TickScheduler.advance()` | **public** (game engine) |
| GET | `/v1/clock/state` | bearer | none | `TickScheduler.state` | **public** (game engine) |

---

### batch_router — prefix `/v1`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| POST | `/v1/batch/gossip_tick` | bearer | none | `GossipHandler.run_tick()` | internal (admin/tooling) |
| POST | `/v1/batch/event_tick` | bearer | none | `EventHandler.run_tick()` | internal (admin/tooling) |

---

### graph_router — prefix `/v1`, sub-prefix `/graph`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| GET | `/v1/graph/nodes/{node_type}/{node_id}` | bearer | `graph_write` | `GenericGraphService.get_node()` | internal (designer tool) |
| GET | `/v1/graph/nodes/{node_type}` | bearer | `graph_write` | `GenericGraphService.list_nodes()` | internal (designer tool) |
| POST | `/v1/graph/nodes/{node_type}` | bearer | `graph_write` | `GenericGraphService.upsert_node()` | internal (designer tool) |
| PATCH | `/v1/graph/nodes/{node_type}/{node_id}` | bearer | `graph_write` | `GenericGraphService.patch_node()` | internal (designer tool) |
| GET | `/v1/graph/edges/{edge_type}/{src_id}/{dst_id}` | bearer | `graph_write` | `GenericGraphService.get_edge()` | internal (designer tool) |
| GET | `/v1/graph/edges/{edge_type}` | bearer | `graph_write` | `GenericGraphService.list_edges()` | internal (designer tool) |
| POST | `/v1/graph/edges/{edge_type}` | bearer | `graph_write` | `GenericGraphService.upsert_edge()` | internal (designer tool) |
| DELETE | `/v1/graph/edges/{edge_type}/{src_id}/{dst_id}` | bearer | `graph_write` | `GenericGraphService.delete_edge()` | internal (designer tool) |

---

### graph_admin_router — prefix `/v1`, sub-prefix `/graph/admin`

| Method | Path | Auth | Scope | Service dispatched to | Public / Internal |
|--------|------|------|-------|-----------------------|-------------------|
| DELETE | `/v1/graph/admin/characters/{character_id}` | bearer | `graph_admin` | `GraphAdminService.hard_delete_character()` | internal (designer tool) |
| DELETE | `/v1/graph/admin/events/{event_id}` | bearer | `graph_admin` | `GraphAdminService.hard_delete_event()` | internal (designer tool) |
| DELETE | `/v1/graph/admin/locations/{location_id}` | bearer | `graph_admin` | `GraphAdminService.hard_delete_location()` | internal (designer tool) |
| PUT | `/v1/graph/admin/relations/absolute` | bearer | `graph_admin` | `GraphAdminService.set_relation_absolute()` | internal (designer tool) |
| POST | `/v1/graph/admin/relations/delta` | bearer | `graph_admin` | `GraphAdminService.apply_unbounded_relation_delta()` | internal (designer tool) |
| POST | `/v1/graph/admin/reindex` | bearer | `graph_admin` | `ReindexJobService.submit_reindex()` + `EmbeddingIndex` | internal (designer tool) |
| GET | `/v1/graph/admin/reindex/{job_id}` | bearer | `graph_admin` | `ReindexJobService.get_job()` | internal (designer tool) |
| GET | `/v1/graph/admin/audit_log` | bearer | `graph_admin` | placeholder (returns empty list) | internal (designer tool) |

---

## Divergence from ROADMAP.md Feature 0.3 public surface

ROADMAP lists the intended public API as:
- `GET /v1/health` — exists at `/health` (no prefix). **Needs to move to `/v1/health` or the gateway health endpoint handles it.**
- `POST /v1/dialogue` ✅ exists
- `WS /v1/ws/dialogue` ✅ exists (conditional)
- `GET /v1/npc/{id}/state` ✅ exists
- `POST /v1/clock/advance` ✅ exists
- `GET /v1/clock/state` ✅ exists
- `GET /v1/graph/admin/*` ✅ exists
- `POST /v1/graph/admin/*` ✅ exists

**Not in ROADMAP but currently exposed:**
- `/v1/action` — game-engine facing, public-category
- `/v1/quest/*` — game-engine facing, public-category
- `/v1/batch/*` — admin/tooling, should be internal-only in gateway
- `/v1/npc/{id}/emotion` — game-engine facing, public-category
- `/v1/protected` — smoke probe, can remain
- `/v1/schema`, `/v1/schema/registry` — designer tools, internal

**Auth note:** Auth currently lives in `auth/middleware.py` applied to the existing monolithic app. For the gateway, auth must remain at gateway level and must NOT be applied again in the internal service. Since there is only one process (in-process mounting), the gateway and internal service share the same app — auth stays on the outer app.
