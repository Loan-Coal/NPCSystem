# NPC Engine — Feature Compilation

**As of:** 2026-06-04 (final hardening review). Two views: **internal** engine capabilities and the
**external** surface a game studio integrates against. Status reflects what the review verified.

Legend: ✅ implemented + tested · 🟡 implemented, thin/﻿no dedicated test · ⚠️ known issue (see ISSUES.md).

---

## A. Internal capabilities (engine domains, `src/npc_engine/engines/`)

| Domain | Capability | Status |
|--------|-----------|--------|
| **dialogue** | LLM-driven NPC dialogue with structured output (response + relation deltas + action + facial expression), tiered degradation (full → graph_only → canned), TTS hook, prompt-injection fence | ✅ (⚠️ tier-A budget, ISSUE-059) |
| **gossip** | NPC-to-NPC knowledge propagation on gossip ticks; per-pair distortion (omission/exaggeration/role_swap/timeline_shift); seeded, logged RNG; batched graph read/write | ✅ |
| **emotion** | Per-NPC valence/arousal state with decay + event shocks; derived mood labels; async lock-guarded store | ✅ |
| **mood** | Mood contagion between co-located/related NPCs | ✅ |
| **memory_consolidation** | Periodic consolidation of dialogue turns into durable Memory nodes; arousal-triggered memory creation; injection-resistant prompt | ✅ |
| **quest** | Quest lifecycle (offered → active → completed) with atomic reward/currency/item transfer (single transaction) | ✅ |
| **quest_generation** | Engine-generated quests from events/needs (LLM) with slot validation | ✅ |
| **events** | World-event materialization, awareness seeding, location scoping | ✅ |
| **faction_politics** | Faction standing dynamics, pledges, treaties | 🟡 |
| **story_pacing / chapter** | Narrative pacing + chapter labeling over the tick timeline | 🟡 |
| **routine / skill / military / clique** | NPC routines, skill progression, battles, social clique formation | 🟡 |
| **interaction** | Player action reporting + proposal dispatch (trade/quest/give), quest verification | ✅ |
| **llm** | `LLMClientProtocol` + adapter registry (Ollama built-in; mock for tests); per-engine model config; **pluggable**: register a new local/API backend, validated at config load | ✅ |
| **tts** | Pluggable text-to-speech (Piper / mock) with graceful failure + metric | 🟡 |
| **scheduler** | Tick scheduler advancing game time; triggers gossip/event/decay; distributed tick lease | ✅ |
| **retrieval** | Graph RAG (vector + graph context), tiered context builder, token-budget enforcement, embedding reconciliation | ✅ (⚠️ ISSUE-059) |

**Cross-cutting (verified):** persistent Neo4j knowledge graph; anti-hallucination guard (NPCs answer
only from known context; eval battery in `evals/`); win **and** lose reachable game loop; structured
logging with RNG-seed + duration; typed exception hierarchy; mypy 0; 98% coverage on the eval harness.

---

## B. External surface (what a studio integrates against)

### B.1 Transport & auth
- **HTTP REST + WebSocket** (FastAPI + Uvicorn), versioned under `/v1`.
- **API-key auth** (`Authorization: Bearer <key>`) on every route except `GET /health`; 401/403 with
  no body detail. Admin routes under `/v1/admin/*` (deploy behind a proxy that blocks them externally).
- **Rate limiting** (token bucket, SHA-256 keyed, bounded buckets) + **per-key WebSocket connection cap**.
- **Idempotency** support (`X-Idempotency-Key`) for mutating routes (enable in staging/prod).

### B.2 Route groups (123 routes across 31 modules)
| Group | Routes | Purpose |
|-------|--------|---------|
| Dialogue | `POST /v1/dialogue`, `WS /v1/ws/dialogue` | Player↔NPC conversation (sync + streamed) |
| NPC state | `GET /v1/npc/{id}/state` | Character + relations + events snapshot |
| Action / interaction | `/v1/action`, `/v1/interaction` | Report player actions; dispatch proposals |
| Quests | `/v1/quests/*`, `/v1/admin/quests/*` | Lifecycle + engine generation |
| Clock | `/v1/clock/advance` | Advance game time (ticks) |
| Graph CRUD | `/v1/graph/nodes/*`, `/v1/graph/edges/*` | Generic registry-driven node/edge read/write/patch |
| Reputation | `/v1/reputation/*` | Faction standings |
| Gossip | `/v1/admin/gossip/spread`, `/v1/admin/rumors/*`, `/v1/admin/rumor-trace/*` | Plant rumors; trace propagation |
| Admin domain | beliefs, goals, items, memories, secrets, debts, factions, schedules, skills, traits, pledges, treaties, groups, causality, witnessed, economy, location-history | Typed admin CRUD for every node/edge domain |
| System | `GET /health`, `GET /readiness`, `/v1/system/*` | Liveness (+ build SHA), dep readiness, config/metrics snapshots, schema introspection |

> ⚠️ API contract caveat: most routes do not yet declare `response_model=`, so the **OpenAPI schema
> emits empty bodies** for ~120 routes — client codegen is not yet usable. Fixing this is the planned
> Batch 5 (`refactor/BATCH5_RESPONSE_MODEL.md`).

### B.3 Configuration knobs (`Settings`, env-driven)
Neo4j connection; LLM backend + per-engine model/timeouts; Ollama context length + derived prompt
token budget; gossip distortion base/max + tick interval; event tick interval; relation/currency
caps; reputation thresholds; embedding/vector backend; TTS; idempotency; rate-limit caps;
`ENV` (dev/staging/prod) gating of secrets, docs, and prompt logging; `WORLD_ID`; `BUILD_SHA`.

### B.4 Integration model & seeding
- **One deployment per studio/game** (DEC-068): each ships its own Docker stack + Neo4j locally; the
  graph holds a single game world. No multi-tenant `world_id` needed.
- **Game schema** (`game_schema.yaml`) + **type registry** (`base_nodes/`, `base_edges/` YAML +
  extension sources) define node/edge contracts — **extend with new YAML, no core code edits**.
- **Seeding**: idempotent admin-endpoint seeding (`make demo-seed`, eval-world seeders).

### B.5 Reliability contracts
- LLM timeout/parse failure → tiered degradation → canned fallback (never a hard error to the player).
- Neo4j unavailable → `GraphUnavailableError` → HTTP 503.
- Token budget exceeded → `TokenBudgetExceededError` (⚠️ currently degrades dialogue to canned for
  knowledge-heavy NPCs — ISSUE-059).
- Errors are redacted at the API boundary (no node ids / schema paths / stack traces leak).

---

## C. Known gaps (see ISSUES.md / FINAL_REVIEW_FINDINGS.md)
- **ISSUE-059** (P1): tier-A context unbounded → canned dialogue once an NPC accumulates knowledge.
- **Batch 5**: `response_model`/OpenAPI typing across 123 routes (client codegen).
- **ISSUE-060** (P2): scripted `demo-run` ACT-3 bribe uses the wrong edge type.
- **ISSUE-058 / SEV-04 PARTIAL**: residual Cypher + engine-owned transactions outside `graph/`.
