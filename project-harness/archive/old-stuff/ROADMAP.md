# NPC Engine — Feature Roadmap

This document is the source of truth for what features get built, in what order,
and what "done" looks like for each one.

## How to use this document

- Each feature is a self-contained Claude Code session. Sessions are sized to
  one feature, not multiple.
- Features are listed in dependency order. Do not skip ahead.
- Each feature has explicit dependencies. If a dependency is not done, the
  feature cannot start.
- Each feature has a definition of done that includes unit tests, integration
  tests where appropriate, an e2e script, and documentation updates.
- Each feature has a "Not in this feature" section. Anything in there is logged
  to `ISSUES.md` if discovered during the work.

## Phase structure

- **Phase 0** — Foundations. Repo cleanup, gateway, per-engine LLM config.
- **Phase 1** — First vertical slice (Faction + faction-aware gossip).
- **Phase 2** — Routine engine.
- **Phase 3** — World depth (memories, beliefs, secrets, time).
- **Phase 4** — Authoring engines (quest generation, story pacing).
- **Phase 5** — Demo polish.

Phases are not strictly sequential — within a phase, features have explicit
dependencies. Across phases, later phases assume earlier phases are done.

---

## Phase 0 — Foundations

### Feature 0.1 — Retroactive cleanup ✅ (assumed done)

Already covered by `PHASE_0_1_PROMPT.md`.

### Feature 0.2 — Repo reorganization ✅ (covered by `PHASE_0_2_PROMPT.md`)

### Feature 0.3 — Gateway service

**Goal:** A single FastAPI service that is the public entry point for all
external consumers (game engines, designer tools). It forwards calls to
internal services, owns auth, basic rate limiting, and request logging.

**Why:** Game engine integration needs one Docker port and one OpenAPI spec.
Internal service shape can change without breaking external contracts.

**Dependencies:** 0.2 done.

**What to build:**
- New package `src/npc_engine/gateway/` with FastAPI app.
- Gateway exposes versioned routes under `/v1/`. Internal services keep their
  existing routes.
- Gateway forwards by direct in-process function call (not HTTP) — it imports
  the internal service routers and mounts them under its own prefix.
- Auth middleware lives at the gateway layer only.
- Request logging middleware lives at the gateway layer only.
- Basic in-memory rate limiting (token bucket per API key) at the gateway
  layer.
- Health check endpoint `/health` (no auth).
- OpenAPI documentation auto-generated and served at `/docs`.

**Public API surface (initial):**
- `GET /v1/health`
- `POST /v1/dialogue` and `WS /v1/ws/dialogue`
- `GET /v1/npc/{id}/state`
- `POST /v1/clock/advance`, `GET /v1/clock/state`
- `GET /v1/graph/admin/*` (authoring)
- `POST /v1/graph/admin/*` (authoring)

**Definition of done:**
- All existing API tests pass against the gateway.
- New unit tests for auth middleware, rate limit middleware.
- Integration test confirming gateway forwards correctly.
- E2E script `e2e/scripts/gateway_smoke.py` that runs against `docker compose
  up` and exercises every public route.
- OpenAPI spec accessible at `/docs`.
- `docker-compose.yml` exposes only the gateway port.
- Documentation updated: `docs/ARCHITECTURE.md` shows the gateway layer,
  `docs/API.md` is created with the public API surface and example curl calls.

**Not in this feature:**
- Production-grade rate limiting (Redis-backed). In-memory is fine for now.
- API versioning beyond `/v1/`.
- Per-user authentication. Single shared secret remains.

### Feature 0.4 — Per-engine LLM config

**Goal:** Each engine has its own LLM configuration file. Same model, different
parameters, different prompts, different fallback policies per engine.

**Why:** Different engines have different needs (gossip distortion can use low
temperature; dialogue needs higher; quest generation needs strict structure).
Config-per-engine is also the architecture that fine-tuning will plug into
later.

**Dependencies:** 0.3 done.

**What to build:**
- Each engine gets `engines/<engine>/llm_config.yaml`. Schema:

```yaml
engine: dialogue
llm:
  model: mixtral-8x7b-instruct-q5
  temperature: 0.8
  max_tokens: 512
  top_p: 0.95
  stop_sequences: []
  # adapter_path: null   # placeholder for future fine-tuning
prompt:
  name: dialogue_main
  version: 1
output_schema_ref: dialogue_response_v1
fallback:
  policy: graceful_degradation
  tiers:
    - full
    - graph_only
    - canned
timeouts_ms:
  full: 30000
  graph_only: 10000
  canned: 100
```

- A loader at `src/npc_engine/engines/llm_config_loader.py` that reads each
  engine's config at startup, validates schema, and exposes `get_config(engine_name)`.
- Each engine's LLM call site reads from its own config rather than a global
  config.
- Validation: every engine that calls an LLM must have a config file. Startup
  fails if a registered engine lacks a config.

**Definition of done:**
- Every engine that uses an LLM has a config file.
- Unit tests for config loader: schema validation, missing file, invalid
  values.
- Integration test confirming each engine reads its own config and behaves
  differently when configs differ.
- `docs/ARCHITECTURE.md` updated with the per-engine config pattern.

**Not in this feature:**
- Fine-tuning. The `adapter_path` field is reserved but not consumed.
- Multiple models loaded simultaneously. Single model, multiple configs.
- Hot-reload of config. Restart required.

---

## Phase 1 — First vertical slice (Factions)

### Feature 1.1 — Faction nodes and membership

**Goal:** Add Faction as a first-class graph node, with characters belonging to
factions and factions standing toward each other.

**Why:** Factions are referenced by gossip propagation, dialogue context,
event scoping, and reputation. They are the highest-leverage graph addition.

**Dependencies:** 0.4 done.

**What to build:**

Node: `Faction`
- `id` (string, unique)
- `name` (string)
- `description` (string, freeform, ≤500 chars, indexable for embeddings)
- `archetype` (enum: religious, political, mercantile, military, criminal,
  social, other)
- `is_active` (bool)
- `created_at`, `last_graph_updated_at` (timestamps)

Edges:
- `(:Character)-[:MEMBER_OF {role, joined_at, status}]->(:Faction)`
  - `role` (enum: leader, officer, member, recruit)
  - `status` (enum: active, exiled, deceased)
- `(:Faction)-[:STANDS_WITH {standing, last_changed_at}]->(:Faction)`
  - `standing` (int -100 to 100; -100 = at war, 0 = neutral, 100 = allied)
  - Standings are bidirectional but stored as two directed edges; values may
    differ (A's view of B vs B's view of A).
- `(:Faction)-[:CONTROLS]->(:Location)`

Service operations:
- Create faction.
- Add character to faction (creates MEMBER_OF edge).
- Remove character from faction.
- Set faction standing toward another faction.
- Query: get factions for a character, get members of a faction, get standing
  between two factions.

**Definition of done:**
- Schema files in `type_registry/base_nodes/faction.yaml` and
  `type_registry/base_edges/member_of.yaml`, `stands_with.yaml`,
  `controls.yaml`.
- Service code in `src/npc_engine/graph/faction_service.py` (≤300 lines).
- Unit tests for service operations.
- Integration tests against test Neo4j.
- API endpoints under `/v1/graph/admin/factions/*`.
- E2E script `e2e/scripts/faction_setup.py` that creates a small faction graph
  and queries it.
- `docs/DATA_MODELS.md` updated with Faction schema.
- Migration script in `scripts/migrations/` to add Faction support to existing
  graphs (idempotent).

**Not in this feature:**
- Faction-aware gossip (next feature).
- Faction-aware dialogue context (later feature, after gossip works).
- WorldState `faction_standings` JSON field migration. Defer.

### Feature 1.2 — Faction-aware gossip propagation

**Goal:** Gossip pair selection and distortion considers faction membership
and standing.

**Why:** Information spreads differently along faction lines. Allies share
freely; enemies distort or refuse. This is the first real demonstration of why
the graph matters for engine behavior.

**Dependencies:** 1.1 done.

**What to build:**
- Update gossip pair selection algorithm to include faction-based weighting:
  - Same faction: pair probability multiplied by `same_faction_boost` (default 2.0).
  - Allied factions (standing ≥ 50): multiplied by `allied_boost` (default 1.5).
  - Hostile factions (standing ≤ -50): multiplied by `hostile_penalty` (default 0.1).
  - Neutral: unchanged.
- Update distortion: cross-faction gossip is more likely to distort if hostile
  (multiply distortion probability by `hostile_distortion_factor`).
- All these factors live in `engines/gossip/config.yaml`.

**Definition of done:**
- Algorithm changes documented in `docs/ARCHITECTURE.md` under gossip engine.
- Property tests: deterministic given same inputs (existing requirement extended).
- Unit tests for new pair-selection weights.
- Integration test: seed a graph with two opposing factions, run N gossip
  ticks, assert distribution of cross-faction vs same-faction shares matches
  expectations.
- Eval case: gossip about an event between two hostile factions distorts more
  than within one faction.
- E2E script: `e2e/scenarios/scenario_factional_rumor.py` — two factions,
  player tells a member of faction A something, ticks advance, member of
  faction B has a more distorted version than another member of faction A.

**Not in this feature:**
- Reputation propagation across factions (separate later feature).
- Faction-specific dialogue tone (later).

### Feature 1.3 — Reputation as faction-mediated standing

**Goal:** A character (especially the player) has reputation with factions,
distinct from individual `RELATES_TO` edges.

**Why:** Guards in faction A treat the player based on faction reputation, not
on individual relationships with each guard.

**Dependencies:** 1.1 done. (1.2 not required.)

**What to build:**
- Edge: `(:Character)-[:HAS_REPUTATION_WITH {standing, last_changed_at}]->(:Faction)`
  - `standing` (int -100 to 100)
- Service operations: get/set/adjust reputation.
- Reputation is included in dialogue context Tier A when the NPC's faction is
  known.
- Reputation propagation policy: events involving the character that affect a
  faction member adjust reputation toward that faction (e.g., killing a
  faction member: -20 reputation).

**Definition of done:**
- Schema, service code (≤300 lines), unit + integration tests.
- API endpoint to query/adjust reputation.
- Eval case: dialogue with NPC in faction A differs based on player's
  reputation with faction A.
- E2E script: scenario_reputation_drift.py.

**Not in this feature:**
- Reputation decay over time. Defer.
- Cross-faction reputation propagation (faction A and B are allies; reputation
  with A affects standing with B). Defer.

---

## Phase 2 — Routine engine

### Feature 2.1 — Schedule nodes and edges

**Goal:** NPCs have schedules: where they are at different times of day.

**Why:** Makes the world feel alive at zero LLM cost. Drives gossip pair
selection (NPCs co-locate at predictable times). Enables player to look for
NPCs at specific times.

**Dependencies:** Phase 1 done. Phase 1 not strictly required, but the demo
benefits from both.

**What to build:**

Node: `Schedule`
- `id`, `name`, `description`
- `entries` (list of `{time_of_day, location_id, activity}` — store as JSON
  property for now; revisit if querying inside entries becomes necessary)

Edge:
- `(:Character)-[:FOLLOWS_SCHEDULE]->(:Schedule)`

Time of day enum: `morning`, `midday`, `afternoon`, `evening`, `night`.

Service operations:
- Assign schedule to character.
- Query: where is character X at time-of-day Y.
- Query: who is at location L at time-of-day T.

**Definition of done:**
- Schema, service, unit tests, integration tests, e2e script.
- WorldState extended with `time_of_day` field.
- `docs/DATA_MODELS.md` updated.

**Not in this feature:**
- Routine engine itself (next feature).
- Per-day-of-week schedules. One schedule per character; revisit later.

### Feature 2.2 — Routine engine

**Goal:** On clock tick, NPCs move to their scheduled locations. The engine
updates `LOCATED_AT` edges deterministically.

**Why:** Ties Schedule data to actual character location. Pure deterministic
engine. No LLM cost. High demo impact.

**Dependencies:** 2.1 done.

**What to build:**
- New engine `src/npc_engine/engines/routine/`.
- On each clock tick, the engine:
  1. Reads current `time_of_day` from WorldState.
  2. For every active character with a schedule, looks up the location for
     this time-of-day.
  3. If different from current `LOCATED_AT`, updates the edge atomically.
  4. Logs the movement.
- Engine is registered with the scheduler.
- Routine disruption: if a character has an `is_active = false` flag (deceased,
  exiled, etc.), schedule is not applied.
- Routine override: a character can have a `routine_override` field (one-off
  location for next N ticks) that takes precedence.

**Definition of done:**
- Engine code (≤300 lines).
- Unit tests for scheduling logic.
- Integration tests: full tick cycle moves characters correctly.
- Eval case: NPC is at expected location after tick.
- E2E script `e2e/scenarios/scenario_daily_life.py`: seed a village with
  schedules, advance N ticks, verify NPCs are where expected throughout.
- Update gossip pair selection to use current `LOCATED_AT` (which now changes
  per tick) — verify gossip pairs reflect schedule co-location.

**Not in this feature:**
- LLM-driven routine generation. Schedules are designer-authored or seeded.
- Routine disruption based on events (Bob is dead → his schedule stops).
  Implemented in a later feature.
- Travel time between locations. Currently movement is instantaneous on tick.

### Feature 2.3 — Routine disruption

**Goal:** Events that affect a character disrupt their routine. NPC who lost a
loved one stays home. Dead NPC stops moving.

**Dependencies:** 2.2 done. Emotion engine exists.

**What to build:**
- On certain events (death of related character, severe negative event in
  vicinity), set a `routine_override` on the character with a duration.
- Override reverts to normal after duration expires.
- Integration with emotion engine: very-negative emotion state (valence < -60)
  triggers automatic stay-home override.

**Definition of done:**
- Routine override logic in routine engine.
- Event-to-disruption mapping in `engines/events/disruption_rules.yaml`.
- Tests, e2e scenario.

**Not in this feature:**
- LLM-driven disruption. Rules-based only.

---

## Phase 3 — World depth

### Feature 3.1 — Time as a first-class concept

**Goal:** A queryable game-time abstraction with epoch, year, season, day,
time-of-day.

**Why:** Distortion (gossip, memory) needs "long ago" vs "yesterday." Quests
need deadlines. Routines already use time-of-day; formalize.

**Dependencies:** None hard. Recommended after Phase 2 because routines
already informally use time.

**What to build:**
- WorldState gets structured time fields: `year`, `season`, `day`, `time_of_day`.
- `POST /v1/clock/advance` accepts what to advance (`time_of_day`, `day`,
  `season`, `year`).
- Helper: "how long ago" between two timestamps in human-friendly buckets
  ("this morning", "yesterday", "last week", "long ago").
- Available to dialogue prompts and gossip distortion.

**Definition of done:**
- Schema update (WorldState).
- Service operations.
- Helper integrated into dialogue context.
- Tests, e2e scenario.

**Not in this feature:**
- Per-region time (different time zones). Single global clock.
- Real-time-of-day simulation. Game-driven only.

### Feature 3.2 — Memories vs Knowledge

**Goal:** Distinguish factual knowledge (KNOWS_ABOUT events) from personal
memories (REMEMBERS — emotional, vivid, specific moments).

**Why:** "I know the king died" is different from "I remember the day my son
told me he was leaving." Memories are richer prompt context and decay
differently.

**Dependencies:** 3.1 done.

**What to build:**

Node: `Memory`
- `id`, `content` (freeform, embedded), `vividness` (0-100), `emotional_charge`
  (-100 to 100), `created_at_game_time`, `last_recalled_at`.

Edge:
- `(:Character)-[:REMEMBERS]->(:Memory)`

Memories can reference events: `(:Memory)-[:ABOUT]->(:Event)`.

Service operations:
- Create memory (typically from emotion engine after high-arousal dialogue or
  event).
- Query memories for character (sorted by vividness × recency).
- Decay vividness over game time.

Retrieval: top-K memories included in dialogue Tier A when relevant. Memory
text is embedded for RAG.

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Emotion engine writes memories on high-arousal moments.
- Dialogue retrieval includes memories.

**Not in this feature:**
- Memory consolidation engine (next feature).
- LLM-driven memory creation. Rules-based only at this stage.

### Feature 3.3 — Memory consolidation engine

**Goal:** Periodically, an NPC's recent dialogue session turns are consolidated
into a longer-term memory paragraph.

**Why:** Solves long-running session memory cleanly. Cheap (one LLM call per
consolidation, infrequent).

**Dependencies:** 3.2 done.

**What to build:**
- Scheduled job: for each NPC with recent dialogue activity, summarize the
  last N session turns into a Memory node.
- LLM-driven (uses the Memory consolidation prompt).
- Original session turns can be discarded after consolidation (configurable).

**Definition of done:**
- New engine `engines/memory_consolidation/`.
- Prompt template in `prompts/memory_consolidation/`.
- Tests including LLM-mocked consolidation.
- E2E scenario: long conversation, advance time, verify memory created.

**Not in this feature:**
- Cross-NPC memory sharing.

### Feature 3.4 — Beliefs (separate from knowledge)

**Goal:** NPCs have stable opinions not tied to specific events.

**Why:** Much of conversation is opinion, not fact. "I think the merchants are
all crooks" is a belief. Beliefs are stable and color dialogue tone.

**Dependencies:** None hard.

**What to build:**

Node: `Belief`
- `id`, `content` (freeform, embedded), `confidence` (0-100), `created_at`.

Edge:
- `(:Character)-[:BELIEVES]->(:Belief)`

Beliefs can be designer-seeded. Beliefs may be derived from repeated events
later (defer).

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Beliefs included in dialogue context Tier A.

**Not in this feature:**
- Belief drift (events update confidence). Defer.

### Feature 3.5 — Goals on characters

**Goal:** NPCs have explicit goals that influence behavior.

**Why:** NPCs without goals are reactive only. With goals, dialogue has natural
hooks, gossip is filtered (goal-relevant gossip is sticky), quest generation
has anchors.

**Dependencies:** 3.4 done (similar shape).

**What to build:**

Node: `Goal`
- `id`, `description`, `urgency` (0-100), `status` (active, achieved,
  abandoned), `created_at`, `target_id` (optional, references another node).

Edge:
- `(:Character)-[:PURSUES]->(:Goal)`

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Goals included in dialogue context.
- Gossip relevance scoring uses goal alignment as a factor.

**Not in this feature:**
- Goal pursuit engine (NPCs taking action to achieve goals). Long-horizon
  goal pursuit is a v3 feature. Goals here are static descriptors.

### Feature 3.6 — Items and ownership

**Goal:** Items as graph entities, owned by characters.

**Why:** Action validation (NPC can't give what they don't own) needs this.
Trade needs this. Evidence and unique items need this.

**Dependencies:** None hard.

**What to build:**

Node: `Item`
- `id`, `name`, `description`, `value`, `rarity`, `type` (enum), `is_unique`,
  `properties` (JSON for flexible attributes).

Edge:
- `(:Character)-[:OWNS {acquired_at}]->(:Item)`

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Action resolver in dialogue engine validates `give_item` against ownership.

**Not in this feature:**
- Trade engine (separate feature).
- Item generation by LLM. Items are seeded or designer-created.
- Inventory mechanics (slots, weight). Game-engine territory.

### Feature 3.7 — Secrets

**Goal:** Secrets as discrete graph entities. NPCs may know secrets. Secrets
propagate via gossip differently than events (more distortion, slower spread).

**Dependencies:** 3.6 done. (Secrets and Items are separate but added together
for thematic coherence.)

**What to build:**

Node: `Secret`
- `id`, `content`, `severity` (0-100), `created_at`.

Edge:
- `(:Character)-[:KNOWS_SECRET]->(:Secret)`

Gossip about secrets uses separate propagation parameters (lower base
probability, higher distortion).

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Gossip engine handles secrets distinctly.

**Not in this feature:**
- LLM-driven secret generation.

### Feature 3.8 — Promises and debts

**Goal:** A web of obligations between characters.

**Dependencies:** None hard. Recommended after items.

**What to build:**

Edge:
- `(:Character)-[:OWES {kind, magnitude, due_by, status}]->(:Character)`
  - `kind` (enum: money, favor, item, service)
  - `magnitude` (numeric or descriptive)
  - `due_by` (game time)
  - `status` (pending, fulfilled, defaulted)

**Definition of done:**
- Schema, service, tests, e2e scenario.
- Dialogue context includes pending obligations.

**Not in this feature:**
- Auto-fulfillment logic. Defer until quest engine consumes obligations.

---

## Phase 4 — Authoring engines

### Feature 4.1 — Faction politics engine (deterministic)

**Goal:** Faction standings drift over time based on events. Deterministic
rules, no LLM.

**Dependencies:** Phase 1 done.

**What to build:**
- New engine that on each tick reads recent events and adjusts faction
  standings based on rules in `engines/faction_politics/rules.yaml`.
- Example rule: event of type `betrayal` between members of factions A and B
  → A's standing toward B decreases by N.
- Standings drift toward neutral over time (slow decay).

**Definition of done:**
- Engine code, tests, e2e scenario.
- Configurable rules.

**Not in this feature:**
- LLM-driven politics. Rule-based only.

### Feature 4.2 — Quest templates and slot-filling generation

**Goal:** LLM generates quests by filling slots in templates. Slots are
graph-validated. Flavor text is LLM. Structure is deterministic.

**Why:** This is the safe authoring agent pattern. No unbounded LLM creativity.

**Dependencies:** 3.5 (goals), 3.6 (items), Phase 1 (factions). All required.

**What to build:**

Node: `Quest`
- `id`, `description`, `quest_giver_id`, `target_id`, `reward_id`,
  `success_condition`, `failure_condition`, `status`, `created_at`,
  `completed_at`.

Node: `QuestTemplate`
- `id`, `name`, `slot_definitions` (which slot needs what type of node),
  `description_template`, `reward_template`, `severity`.

Quest generation engine:
- Selects template based on quest_giver's archetype, faction, current state.
- Asks LLM to propose slot fills given constraints.
- Validates slot fills against the graph (does the proposed item exist? does
  the proposed location exist? does it match the type required?).
- On validation failure, re-prompts LLM with the constraint violation. After
  3 failures, falls back to deterministic random selection from valid options.
- LLM generates flavor text (description, NPC plea) only after slots are
  validated.

**Definition of done:**
- Schema, engine, tests including LLM-mocked generation, e2e scenario.
- Templates in `prompts/quest_generation/templates/`.
- Validation harness with property tests.

**Not in this feature:**
- Story-pacing meta-engine (next feature). Quest generator runs whenever called.
- LLM-driven template creation.

### Feature 4.3 — Story pacing engine

**Goal:** A meta-engine that decides when high-severity events and quests are
allowed to fire, based on current game state.

**Why:** Prevents the event during quest breaks qust, such as war-during-princess-delivery problem. World-altering
events should not break critical quests.

**Dependencies:** 4.1 done. 4.2 done.

**What to build:**
- On each tick, the pacing engine reads:
  - Active quests (especially high-severity ones).
  - Player recent activity.
  - Time since last major event.
- Updates a `pacing_state` field on WorldState that constrains other engines:
  - `max_event_severity` — events above this are suppressed.
  - `quest_generation_rate` — multiplier for new quest generation.
- Other engines respect `pacing_state` when sampling.

**Definition of done:**
- Engine code, configurable rules, tests, e2e scenario.

**Not in this feature:**
- LLM-driven pacing. Rules-based only.

### Feature 4.4 — Economy engine (basic)

**Goal:** Items have prices. Prices vary by location and supply/demand.
Trading with NPCs uses unified valuation.

**Dependencies:** 3.6 (items) done.

**What to build:**
- Pricing service that computes item value at a given location.
- Modifiers: location-based (rare in this region → higher), event-based (war
  → weapons cost more), faction-based (member discount).
- Trade endpoint that handles offer/accept logic.

**Definition of done:**
- Schema, service, tests, e2e scenario.

**Not in this feature:**
- LLM-driven trade negotiation.
- Trade routes between NPCs. Defer.

---

## Phase 5 — Demo polish

### Feature 5.1 — The 90-second video scenario

**Goal:** A single e2e scenario that produces the demo: tavern, two NPCs,
factions, schedules, gossip propagation, player asks each NPC, distorted rumor
surfaces.

**Dependencies:** Phases 1-2 done at minimum. Phases 3+ optional but enrich
the demo.

**What to build:**
- A self-contained e2e scenario that boots from clean state, seeds the world,
  and runs the full demo loop.
- Outputs a clean transcript suitable for video voiceover.

**Definition of done:**
- Scenario runs reliably (deterministic given seed).
- Transcript reads like a story.
- Documented in `docs/DEMO.md` with how to reproduce.

### Feature 5.2 — Visualizer for gossip flow (optional)

**Goal:** A web page that visualizes how a rumor flowed through the world.

**Why:** Good marketing artifact. Auditable gossip is a differentiator.

**Dependencies:** Phase 1 done.

**What to build:**
- Simple HTML/JS page that reads gossip trace logs and shows a graph of the
  spread.

---

## Backlog (not yet planned)

These are real future features but have no dates:

- LLM-as-judge evaluation layer.
- Per-engine fine-tuning. Revisit when eval suite is mature and a specific
  engine has plateaued on prompt engineering.
- Per-day-of-week schedules.
- Cross-faction reputation propagation.
- Long-horizon goal-pursuing NPCs.
- Trade routes and economic networks.
- Content safety filter on LLM outputs.
- Production rate limiting (Redis-backed).
- Hot reload of configs.
- Multi-tenant deployment.
