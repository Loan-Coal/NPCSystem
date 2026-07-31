# NPC Engine — Engine Capability Catalog

This document is the canonical, market-facing catalog of the **domain engines** that
power NPC Engine. It describes *what each engine does for your game* (the business
capability), *how it runs* (on request, or autonomously on a clock tick), and *which
API routes* expose or drive it.

For the raw HTTP contract see [API.md](API.md). For system layering and data flow see
[ARCHITECTURE.md](ARCHITECTURE.md). For the graph schema see [DATA_MODELS.md](DATA_MODELS.md).

---

## How engines run

Every engine lives under `engines/` and depends only on lower layers (services,
retrieval, graph). Engines never call each other over HTTP; they compose in-process.
There are two execution models:

| Model | Trigger | Examples |
|-------|---------|----------|
| **Request-driven** | A game/HTTP call invokes the engine synchronously and returns a result. | Dialogue, Economy pricing, Quest lifecycle, Relationship standing |
| **Tick-driven** | The engine runs autonomously when the game clock advances, simulating the world off-screen. | Gossip, Faction politics, Routine movement, Schemes, Memory decay |

### The tick model

Tick-driven engines are orchestrated by the **scheduler**
([tick_scheduler.py](../src/npc_engine/scheduler/tick_scheduler.py)). The clock advances
in one of two modes:

- **`game_driven`** — the game calls `POST /v1/clock/advance` to advance N ticks
  (recommended for single-player and deterministic testing).
- **`realtime`** — the server advances the clock on a wall-clock interval.

On each tick the scheduler runs the registered engines **in a fixed order** so that
upstream state (pacing multipliers, gossip, movement) is visible to downstream engines
within the same tick:

1. **Story pacing** (writes pacing multipliers that gate the rest)
2. **Gossip** *(interval-gated)* and **Event generation** *(interval-gated)*
3. **Routine** movement
4. **Chapter** detection *(interval-gated, LLM)*
5. All remaining per-tick engines (faction politics, cliques, skills, oaths, treaties,
   mood, succession, agendas, needs, military, quest triggers, proactive dialogue,
   reputation, intents, goals, player model, director, memory decay, schemes)
6. **Memory consolidation** *(advance-cadence, LLM)*

Cadences are configurable. Gossip and event generation run every *N* ticks
(`GOSSIP_TICK_INTERVAL`, `EVENT_TICK_INTERVAL`); several engines self-gate on their own
interval and no-op on off-ticks. Each engine is run in isolation — an exception in one
engine is logged and recorded but **does not stop the tick or the other engines**.

### Observing engines

- `GET /v1/admin/system/engines` — per-engine last-run tick, last error, and error count.
- `GET /v1/clock/state` — current tick plus next gossip/event tick.
- `GET /v1/admin/system/metrics` — in-process request and engine metrics snapshot.

### LLM usage

Engines that call an LLM declare `uses_llm: true` in their engine contract
(`engines/contracts/<name>.yaml`) and own a co-located `llm_config.yaml`. The backend is
pluggable via `LLMClientProtocol` + a factory registry; the shipping backends are
**Ollama** (default, e.g. `qwen2.5:7b`) and a deterministic **Mock** adapter for tests.
LLM-using engines below are marked **🤖 LLM**.

---

## Capability catalog

### Conversation & dialogue

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Dialogue** 🤖 | Generates an in-character NPC reply plus a structured `action`, `facial_expression`, bounded relation deltas, and mood update. Grounds responses in graph facts (Tier A) and semantic memory (Tier B), degrading gracefully (`full → graph_only → canned`) under timeout or graph outage. | Request | `POST /v1/dialogue`, `WS /v1/ws/dialogue` |
| **Interaction dispatch** | Routes action proposals emitted by dialogue (trade, give-item, quest offer, relationship band change) into the correct downstream engine, validating ownership and bounds. | Request | `POST /v1/interaction`, `POST /v1/interaction/band` |
| **Knowledge learning** 🤖 | Extracts player-stated facts during conversation and persists them as NPC belief nodes, so NPCs "remember" what the player told them. | Request (in dialogue path) | `/v1/admin/beliefs/*` |
| **Proactive dialogue** | Lets NPCs *start* conversations: detects high-vividness unshared memories for NPCs co-located with the player and emits an opening line. | Tick (every tick) | surfaced via `GET /v1/dialogue/pending` |
| **Intent formation** | Scores candidate conversation intents and enqueues the most salient as pending proactive dialogue, so NPCs approach the player with purpose. | Tick (every tick) | `GET /v1/dialogue/pending` |
| **Drama director** | Observes engagement signals (idle player, narrative plateau) and decides whether to inject a story beat, raising tension when play stalls. | Tick (every tick) | `GET /v1/dialogue/director-beats` |

### Memory & cognition

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Memory formation & decay** | Forms vivid memories from high-arousal moments and decays memory vividness over time (charge-weighted), so salient events persist and trivia fades. | Tick (decay self-gates on interval) | `/v1/admin/memories/*` |
| **Memory consolidation** 🤖 | Summarises an NPC's recent session-turn history into durable long-term Memory nodes, keeping context affordable while preserving the gist. | Tick (advance cadence) | `POST /v1/admin/memories/consolidate/{npc_id}` |
| **Player model (theory-of-mind)** | Maintains each NPC's *model of the player* (perceived intent, trust, reputation), so different NPCs can hold different opinions of the same player. | Tick (every tick) | `GET /v1/npc/{npc_id}/player-model/{player_id}` |
| **Planning (GOAP)** | Reads NPC needs, forms goals, and selects actions toward them — lightweight goal-oriented action planning. | Tick (goal formation every tick) | `/v1/admin/goals/*` |
| **Needs** | Decays per-character need levels each tick and applies location-based restoration, driving the motivational substrate for planning and quests. | Tick (every tick) | — (feeds planning & quest triggers) |

### Emotion & mood

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Emotion** | Persistent VAD emotion state (valence/arousal + derived label) per NPC. Updated after dialogue and witnessed events; decays toward neutral. Injected into dialogue context for in-character tone. | Request (update) + decay | `GET /v1/npc/{npc_id}/emotion` |
| **Mood contagion** | Spreads emotional state between co-located, affectionate NPCs each tick, so moods ripple through a crowd. | Tick (every tick) | — |

### Social dynamics

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Gossip** | NPC-to-NPC rumor propagation with deterministic distortion (omission, exaggeration, role-swap, timeline-shift). Spreads knowledge along plausible social paths, weighted by personality and faction standing. Fully reproducible (seeded). | Tick (interval-gated) | `/v1/admin/gossip/*`, `/v1/admin/rumors/*`, `/v1/admin/witnessed/*` |
| **Reputation** | Propagates 1-hop personal reputation through the social graph, so an NPC's standing colors how that NPC's contacts perceive a subject. | Tick (every tick) | `GET /v1/graph/characters/{id}/reputation`, `/v1/admin/characters/{id}/reputation/*` |
| **Relationship standing** | Derives a named Standing band (e.g. ally, rival) from raw trust/fear/affection scalars — a designer-friendly summary of a relationship. | Request | `GET /v1/npc/{npc_id}/relationship/{other_id}` |
| **Clique formation** | Detects and maintains character cliques based on mutual affection, surfacing emergent social groups. | Tick (every tick) | `/v1/admin/groups/*` |
| **Routine / movement** | Moves active characters to their scheduled locations every tick and resolves temporary routine overrides, producing a living, populated world. | Tick (every tick) | `/v1/admin/schedules/*`, `/v1/locations/*`, `/v1/admin/location-history/*` |

### Knowledge, belief & intrigue

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Deception** | Plants deliberate false beliefs on NPCs (designer/quest tool for misinformation and intrigue plots). | Request | `/v1/admin/beliefs/*` |
| **Investigation** | Detective/mystery engine: lets an NPC investigate an event, weighing alibis and witnesses; also detects witnessed, sufficiently-advanced schemes. | Request + Tick (scheme detection) | `GET /v1/investigations/{investigator_id}/{event_id}` |
| **Scheming** | Long-horizon covert schemes: forms capped scheme nodes and advances them step-by-step by minting covert events, enabling slow-burn antagonist plots. | Tick (advance self-gates) | `GET /v1/npc/{npc_id}/schemes` |

### Politics & factions

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Faction politics** | Deterministically drifts faction standings based on world events and time decay, so alliances and rivalries evolve on their own. | Tick (every tick) | `/v1/admin/factions/*` |
| **Succession** | Grants vacant inheritable titles to the first eligible heir, keeping power structures intact when title-holders die or leave. | Tick (every tick) | — |
| **Oaths / pledges** | Manages pledge lifecycle: expiry and violation detection, so promises between characters have mechanical consequences. | Tick (every tick) | `/v1/admin/pledges/*` |
| **Treaties** | Manages treaty lifecycle between factions: expiry plus mechanical and LLM-checked conditions. 🤖 | Tick (every tick) | `/v1/admin/treaties/*` |
| **Agendas / voting** | Resolves open agendas (e.g. council votes) whose deadline has passed, driving collective faction decisions. | Tick (every tick) | — |
| **Military** | Per-tick military simulation — battle resolution between opposing armies. *(Currently a no-op stub; see ISSUES.md.)* | Tick (every tick) | — |

### Economy & progression

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Economy (pricing & trade)** | Deterministic item pricing and trade-offer evaluation, so merchant NPCs quote and accept/reject trades by rule rather than by LLM guesswork. | Request | `GET /v1/admin/economy/price`, `POST /v1/admin/economy/trade` |
| **Currency** | Currency-transfer safety flows backing trades and player actions (bounded, auditable transfers). | Request (in trade/action path) | drives `/v1/action`, `/v1/admin/economy/trade`, `/v1/admin/debts/*` |
| **Skills & XP** | Awards XP and levels character skills after quest completion, and answers skill checks. | Tick (progression) + Request | `/v1/admin/skills/*` |

### Quests

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Quest lifecycle** | Orchestrates the full quest flow — offer → accept → objective progress → evaluate → reward — with idempotent, branchable quests. | Request | `/v1/quest/*` |
| **Quest generation** 🤖 | LLM-powered quest generation with slot-filling, graph validation, and retry. Tick-driven *triggers* propose draft quests from events, critical NPC needs, and world-state epochs. | Request + Tick (triggers) | `/v1/admin/quests/*` |

### Narrative & pacing

| Engine | Capability | Execution | Key APIs |
|--------|-----------|-----------|----------|
| **Chapter** 🤖 | Detects narrative chapter transitions and labels them via LLM, giving a long-running game a readable story structure. | Tick (interval-gated) | `GET /v1/chapters/current` |
| **Story pacing** | Meta-engine that gates the other engines by writing pacing multipliers to WorldState each tick — speeds up or slows down world simulation to match dramatic need. | Tick (runs first) | reflected in `GET /v1/admin/system/config` |

---

## Infrastructure engines

These live under `engines/` but provide cross-cutting plumbing rather than a player-facing
capability. They are documented here for completeness.

| Engine | Purpose |
|--------|---------|
| **LLM** | Backend adapters (`mock`, `ollama`) and the registry/factory. Add a backend by implementing `LLMClientProtocol` and registering it — no engine edits (OCP). |
| **TTS** | Text-to-speech adapters and emotion-to-voice-parameter modulation for NPC voice synthesis. |
| **Idempotency** | Transport idempotency persistence (Neo4j-backed) and expiry scheduling for safe request replay. |
| **Contracts** | Engine contract schema + loader; declares per-engine metadata such as `uses_llm`, validated fail-fast at startup. |
| **Ports** | Structural graph-access Protocols grouped by graph domain — the interface surface engines depend on instead of concrete graph code. |

---

## Extending with a new engine

Engines follow Open/Closed: add capability by adding a file, not editing existing ones.

1. Create `engines/<name>/<name>_engine.py` implementing `BaseEngine` (`run_tick(...)` for
   tick engines) or a request handler.
2. If it calls an LLM, add `engines/contracts/<name>.yaml` with `uses_llm: true` and a
   co-located `llm_config.yaml`.
3. Inject dependencies via the constructor; wire it in the composition root
   (`api/dependencies.py`) and, for tick engines, register it in the scheduler.
4. Add routes under `api/routes/` if it needs an HTTP surface, and register them in
   `api/router_registry.py`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full layer model and extension points.
