# Business Requirements — NPC Engine

## Project Vision

NPC Engine is a game backend service that makes non-player characters feel alive.
It manages persistent knowledge, relationships, and emotional state for every NPC
across an entire game world, and drives natural-feeling conversations between players
and NPCs. The system runs off-screen as well as on-screen: NPCs gossip, witness events,
change their opinions, and react to a changing world even when the player is not watching.

The service is designed as a plugin for both Unity and Unreal Engine games.
It exposes a clean HTTP + WebSocket API so that any game engine can integrate without
depending on internal implementation details.

---

## Target Clients

| Client | Integration Method | Primary Use |
|---|---|---|
| Unity (C#) | REST + WebSocket | Calls `/dialogue` or `/ws/dialogue`; polls `/npc/{id}/state` |
| Unreal Engine (C++) | REST + WebSocket | Same as Unity; Blueprint-friendly response shapes |
| Game Designer Tools | REST | Seeding world state, advancing clock, reviewing NPC knowledge |

---

## Non-Functional Requirements

| Requirement | Target |
|---|---|
| Dialogue response latency (first token via WebSocket) | Best-effort; prototype targets quality over latency. Production target TBD. |
| Full dialogue response (REST, no streaming) | Best-effort; prototype targets quality over latency. |
| Concurrent dialogue sessions | Single-stream prototype; concurrency is a post-prototype concern. |
| Gossip tick throughput | ≥ 200 NPC pairs / tick |
| Knowledge graph size | ≥ 10,000 nodes (characters + events + locations) |
| Service uptime | 99.5% during active game sessions |
| LLM fallback on timeout | < 100 ms (serve canned response) |
| Test coverage | 100% pass on `make eval` (Layer 1+2) + ~70% line coverage on non-prompt code |

---

## Module Business Requirements

### 1. Graph Layer (`graph/`)

**Business Goal:** Provide a persistent, queryable knowledge graph that is the single
source of truth for the game world's facts about characters, events, and locations.

**Requirements:**
- Base node and edge contracts are owned by `type_registry/base_nodes/*.yaml` and `type_registry/base_edges/*.yaml`; `game_schema.yaml` expands those contracts and can add new node or edge types.
- Graph services use a hybrid model: registry-backed dynamic model generation plus specialized per-type services for unique behavior.
- Store Characters with personality traits, faction, location, biography, and relationship history.
- Store Events with timestamp, severity, location, participants, and a summary.
- Store Locations with descriptors and connected NPCs.
- Store WorldState as a single node representing global conditions.
- Relationships between characters (RELATES_TO) must track:
  - `trust`, `fear`, `affection` (integers, range 0–100, neutral = 50)
  - `interaction_count` — total dialogue exchanges
  - `delta_log` — last N delta events for bounded mutation
  - `last_updated_at` — timestamp of most recent change
  - `relevance_score` — computed from shared faction or proximity
- Relationships must be bidirectional: A→B and B→A initialized independently.
- All writes must be atomic (Neo4j transactions). Partial writes must be rolled back.

**Out of scope:** This layer does not decide when or why to write; it only executes writes.

---

### 2. Auth (`auth/`)

**Business Goal:** Prevent unauthorized access from non-game-engine clients.

**Requirements:**
- All API routes (except `/health`) require a valid `Authorization: Bearer <token>` header.
- The token is a shared secret configured per deployment, not per user.
- Invalid tokens return HTTP 401 with no internal detail in the response body.
- API key rotation must be possible by changing the env var and restarting the service.

**Out of scope:** Per-player authentication, OAuth, session-based auth.

---

### 3. Retrieval Layer (`retrieval/`)

**Business Goal:** Assemble the right NPC context for each dialogue call — fast enough
to not add perceptible latency, rich enough to make NPC responses feel grounded.

**Requirements:**
- **Tier 0** (always included, minimal tokens): world state, NPC emotion state, current session turns.
- **Tier A** (authoritative graph facts): NPC biography, current location, direct relationships with player and nearby NPCs, known events. These are fetched via Cypher — they are facts, not approximations.
- **Tier B** (optional RAG): top-K semantically similar events or facts from the embedding index. Trimmed first when token budget is tight.
- Total context fed to LLM must not exceed `PROMPT_TOKEN_BUDGET` tokens (default 800).
- Embedding index must support invalidation when an NPC's knowledge changes, so stale facts are not retrieved.

**Out of scope:** Retrieval does not generate or interpret; it only fetches and assembles.

---

### 4. Dialogue Engine (`engines/dialogue/`)

**Business Goal:** Make conversations with NPCs feel natural, reactive, and world-aware.
The NPC must respond in character, take contextually appropriate actions, and show
believable emotional reactions.

**Requirements:**
- Player types free-form text. The system generates:
  - `npc_response` — NPC's spoken text
  - `action` — what the NPC does (speak, gesture, move, attack, give_item, none)
  - `facial_expression` — what to render on the NPC's face
  - `relation_deltas` — how this conversation shifted trust/fear/affection
  - `mood_update` — if the NPC's emotional state label changes
- Actions must be validated: an NPC cannot give an item they do not own.
- Relation deltas are bounded per-turn and per-window (sliding window of last N interactions).
- WebSocket endpoint streams tokens progressively so the player sees the NPC "thinking."
- If the LLM times out, serve a canned fallback response appropriate to the NPC's archetype.
- Conversation sessions persist for `DIALOGUE_SESSION_TTL` seconds so NPCs remember recent exchanges.

**Out of scope:** Voice synthesis, lip sync. Rendering of expressions/animations is the game engine's responsibility.

---

### 5. Gossip Engine (`engines/gossip/`)

**Business Goal:** Create an emergent, believable world where NPCs share information,
spread rumors, and form opinions based on what they've heard — even when the player
is not present.

**Requirements:**
- On each gossip tick, select a pair of NPCs who could plausibly interact (shared location or proximity).
- Pair selection probability is weighted by the NPC's `gossipy` personality field.
- The NPC who shares news is chosen by `gossipy` score and recency of knowledge.
- Information shared may be distorted based on the sharer's `honesty` and the trust between the pair.
- Distortion types: omission (detail removed), exaggeration (severity inflated), role_swap (roles reversed), timeline_shift (timing changed).
- Distortion must be deterministic: same inputs → same output (enables reproducible debugging).
- Result is recorded as a KNOWS_ABOUT edge with `knowledge_state: "knows"` or `"rumor"`.
- If a rumor is later proven false (cross-checked against a factual Event node), the trust on the gossip edge is penalized.
- All gossip traces are logged with tick_id and sharer/receiver IDs.

**Out of scope:** Player-initiated gossip (handled by dialogue engine). LLM is not used in the gossip engine.

---

### 6. Event Engine (`engines/events/`)

**Business Goal:** Drive world change autonomously. Events happen in the world independent
of player action, and NPCs become aware of them over time.

**Requirements:**
- Event templates are defined in `event_pool.json` with weight, severity, location_tag, and summary_template.
- On each event tick, sample one or more events based on weights and current world conditions.
- Scope each event to the relevant location(s) using the location graph.
- Create KNOWS_ABOUT edges for all NPCs at affected locations with `knowledge_state: "knows"`.
- For world-altering events (war declared, plague, etc.), update the WorldState node.
- Events that change WorldState trigger embedding index invalidation for all affected NPCs.

**Out of scope:** Scripted/story events (those are seeded directly via seed.py or designer tools).

---

### 7. Emotion Engine (`engines/emotion/`)

**Business Goal:** Give NPCs persistent emotional state that colors their dialogue,
not just a point-in-time mood tag.

**Requirements:**
- Each NPC has an emotion state: `valence` (positive/negative affect, -100 to 100),
  `arousal` (intensity, 0–100), and a derived `label` (e.g., "melancholic", "elated").
- Emotion state persists between player interactions.
- After each dialogue exchange, apply `mood_update` delta to the NPC's emotion state.
- After each witnessed event, apply an emotion delta proportional to event severity.
- Emotion decays toward neutral over time at a configurable `decay_rate`.
- Emotion state is injected into dialogue context so the LLM generates in-character responses.

**Out of scope:** Emotion does not determine NPC pathfinding or animations directly (the game engine reads emotion state and decides rendering).

---

### 8. World State (`world/`)

**Business Goal:** Provide a shared global context that all NPCs and engines can read,
so that world-level changes (war, famine, political shifts) are reflected consistently.

**Requirements:**
- WorldState node stores: `epoch`, `faction_standings` (dict), `active_conditions` (list), `weather`.
- WorldState is always included in dialogue context as Tier 0.
- World-altering events update WorldState atomically.
- WorldState changes trigger context invalidation for all NPC embeddings.

**Out of scope:** WorldState does not store per-character data.

---

### 9. Mutation Rules (`mutation/`)

**Business Goal:** Prevent LLM-driven or gossip-driven relation values from being
manipulated into extreme states through repeated interactions.

**Requirements:**
- Per-turn delta for any relation variable (trust, fear, affection) is capped at `MAX_RELATION_DELTA_PER_TURN`.
- Windowed delta (sum of last `RELATION_WINDOW_SIZE` changes) is capped at `MAX_RELATION_DELTA_PER_WINDOW`.
- Values clamp to [0, 100]; they do not overflow.
- All delta applications are logged to the edge's `delta_log` for audit.
- The validator raises `RelationDeltaExceededError` with full context if bounds are exceeded before clamping.

**Out of scope:** These bounds apply to runtime delta application only. Seed data may set any value.

---

### 10. Scheduler (`scheduler/`)

**Business Goal:** Drive gossip and event ticks at appropriate intervals,
supporting both real-time (server-controlled) and game-driven (player/designer-controlled) timing.

**Requirements:**
- In `realtime` mode, gossip ticks fire every `GOSSIP_TICK_INTERVAL` real seconds.
- In `game_driven` mode, game engine calls `POST /clock/advance` to advance ticks manually.
- Tick history is queryable via `GET /clock/state`.
- RNG seeds used for each tick are logged for reproducibility.

**Out of scope:** In-game time-of-day simulation (the game engine handles that; this service tracks ticks and game-time-seconds as provided by the game).

---

## User Stories

### Player Perspective
- As a player, I want NPCs to respond in character based on our relationship history.
- As a player, I want conversations to feel immediate — I should see the NPC "responding" as it generates text.
- As a player, I want NPCs to remember what we talked about recently within the same conversation.
- As a player, I want NPCs to reference things that happened in the world even if I wasn't there.
- As a player, I want NPC emotions to feel consistent — a grieving NPC should not suddenly seem cheerful.

### Game Designer Perspective
- As a designer, I want to seed the world with specific characters, events, and relationships.
- As a designer, I want to add new event templates without writing code.
- As a designer, I want to swap the LLM backend without changing any game code.
- As a designer, I want to run the gossip engine faster during testing by advancing the clock manually.
- As a designer, I want NPC personality fields (gossipy, honesty, credulity) to visibly affect NPC behavior.

### Developer Perspective
- As a developer, I want to add a new LLM backend by creating one file and adding one line to the factory.
- As a developer, I want failing tests to tell me which exact mutation rule was violated.
- As a developer, I want to replay any gossip tick deterministically using the logged seed.
- As a developer, I want the codebase to stay under 200 lines per file so it stays navigable.
