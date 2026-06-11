# Expansion Lens X2 — Missing Engines / New Domains (Refresh 2026-06-11)

**Lens:** X2 (new engines/domains the product vision implies but that do not exist).
**Mode:** READ-ONLY. Rubric: `project-harness/expansion/BUSINESS_INTENT.md`.
**Codebase state:** Phases 0–26 complete, branch `munich-demo`. `make check` green
(1967 passed, 22 skipped, 85.70% coverage). All EXPANSION_INDEX Phase 0–4 items
completed as of this refresh.
**Constraints honored:** layer model (downward-only), LLM only in `engines/`, Cypher only
in `graph/`, prompts in YAML only, OCP add-by-new-file via `type_registry/base_nodes|edges/`,
Pydantic v2, single-tenant (DEC-068 — no `world_id` proposed anywhere below).

IDs run EXP-40 through EXP-69. Numbered top-down by combined Value × Business-fit.

---

## What already exists — do NOT re-propose

| Candidate territory | Verdict | Confirmatory evidence |
|---|---|---|
| Personal NPC relationships (trust/fear/affection scalars) | **Built** | `type_registry/base_edges/relates_to.yaml:4-12` |
| Reputation propagation | **Built** | `engines/reputation/reputation_engine.py` (1-hop, player-personal) |
| NPC GOAP goal/planning | **Built** | `engines/planning/goal_former.py` + `action_selector.py` |
| Daily-life scheduling / routine | **Built** | `engines/routine/routine_engine.py` |
| Dialogue-driven knowledge extraction | **Built** | `engines/knowledge_learning/knowledge_extraction_engine.py` |
| Need decay | **Built** | `engines/need/need_decay_engine.py` |
| NPC-initiated / proactive dialogue | **Built** | `engines/proactive_dialogue/proactive_engine.py` + `proactive_tick_adapter.py` |
| EmotionModelProtocol OCP seam | **Built** | `engines/emotion/emotion_model_protocol.py` |
| Distortion-strategy registry | **Built** | `engines/gossip/distortion_strategy.py` STRATEGY_REGISTRY |
| Location hierarchy (PART_OF) | **Built** | `type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` (ISSUE-057 FIXED) |
| Branching quests / UNLOCKS chain | **Built** | `engines/quest/quest_chain_resolver.py` + `base_edges/unlocks.yaml` |
| Persistent emotion (survive restart) | **Built** | `graph/emotion_writer.py` + `engines/emotion/emotion_bootstrap.py` (EXP-14) |
| Clique / group formation | **Built (graveyard)** | `engines/clique/clique_formation_engine.py` |
| Military / battle | **Built (graveyard)** | `engines/military/military_battle_service.py` |
| Trade / economy / pricing | **Built** | `engines/economy/trade_engine.py` + `pricing_engine.py` |
| Content moderation (input + output blocklist + ESRB/PEGI ceiling) | **Built** | `services/input_moderation.py` + `services/output_moderation.py` + `services/content_rating_resolver.py` |
| TTS output | **Built** | `engines/tts/` (protocols + piper_adapter + mock) |
| Localization / multi-language | **Dropped** | OQ-D11 (out of scope) |
| Voice / STT input | **Dropped** | OQ-D11 (out of scope) |
| Multi-tenant world isolation | **Forbidden** | DEC-068 |

**Confirmed absent (candidate territory for this lens):**
- Relationship affinity engine (phase mapping over existing dead `relationship_phase` field)
- Player-model / theory-of-mind engine (second-order belief)
- Player-aware drama director engine (targeted engagement manager)
- NPC deception / betrayal engine (covert goal concealment + false-belief seeding)
- Long-horizon NPC scheming engine (multi-step covert plan execution)

---

## Index table

| EXP | Title | Effort | Value | Fit | Status |
|-----|-------|--------|-------|-----|--------|
| EXP-40 | Relationship affinity phase engine | S | high | high | First-slice ready |
| EXP-41 | Player-model / theory-of-mind engine | M | high | high | Schema-gated (DECISIONS req.) |
| EXP-42 | Player-aware drama director engine | M | med | high | New-file-add; soft deps on EXP-40/41 |
| EXP-43 | NPC deception / false-belief engine | L | high | high | Schema-gated; prompts-gated |
| EXP-44 | Long-horizon covert scheming engine | XL | med | med | Requires EXP-41 + EXP-43 |

---

## TOP 1 — highest combined value × fit

### EXP-40: Relationship Affinity Phase Engine
Type: new-engine
Business rationale: "Persistent NPC relationships" is an explicit commitment
(`BUSINESS_INTENT.md:35`; `docs/BUSINESS_REQUIREMENTS.md:58`). The `relates_to.yaml`
schema already declares `relationship_phase` (optional `str`) and `phase_started_at_tick`
(optional `int`) — both fields are populated in **zero Python files** (`grep
relationship_phase src/npc_engine` → single hit: the YAML itself). A studio reading the
OpenAPI spec sees these fields on every `RELATES_TO` edge and gets nothing back. Turning raw
trust/fear/affection scalars into named, queryable relationship phases (STRANGER →
ACQUAINTANCE → ALLY/RIVAL → CONFIDANT/NEMESIS) is the semantic layer studios pay for — it
drives dialogue tone, unlocks quests by relationship depth, and makes the social graph
legible to designers without inspecting raw integers.
What it does: Per-tick (and post-dialogue) engine that maps the composite affinity score
(derived by the already-built `engines/relationship/standing.py::derive_standing`) onto a
named `relationship_phase`, records `phase_started_at_tick`, and emits a phase-transition
event to the WS stream when a boundary is crossed. Dialogue prompt builder reads the phase
string to set conversational tone (no raw `if trust > N` comparisons in prompt templates).
Quest engine can gate offers on phase (e.g. "CONFIDANT" unlocks personal-secret quest).
Current state: `engines/relationship/standing.py` provides `derive_standing()` and the
`Standing` enum, but no engine reads these and writes back to the graph.
`type_registry/base_edges/relates_to.yaml:11-12` has `relationship_phase` and
`phase_started_at_tick` with `required: false` — populating them requires **no schema
change**. The only absent piece is the engine that calls `derive_standing`, compares to the
current phase, and writes through `graph/`.
Graph/schema additions:
```yaml
# No new base node or edge. Populate existing optional fields only.
# relates_to.yaml already has:
#   relationship_phase:     { type: str, required: false }
#   phase_started_at_tick:  { type: int, required: false }
#
# Phase thresholds: new YAML file (designer-editable, no Python edit):
# src/npc_engine/engines/relationship/phase_rules.yaml
phases:
  STRANGER:    { min: -100, max: -50 }   # maps to Standing.HOSTILE
  WARY:        { min: -50,  max: -15 }   # maps to Standing.WARY
  NEUTRAL:     { min: -15,  max:  15 }   # maps to Standing.NEUTRAL
  ALLY:        { min:  15,  max:  50 }   # maps to Standing.FRIENDLY
  CONFIDANT:   { min:  50,  max: 100 }   # maps to Standing.ALLIED
```
API surface: `GET /v1/characters/{npc_id}/relationships` already exists
(`api/routes/relationship.py`) — extend its response model to include `phase` + `phase_since_tick`.
Phase-transition events pushed on existing WS event stream (additive push, no route change).
Composition:
- New file: `engines/relationship/affinity_engine.py` — `AffinityEngine.run_tick(session, tick_id)` reads all `RELATES_TO` edges via `retrieval/`, calls `derive_standing()`, compares to stored `relationship_phase`, writes updated phase via a new `graph/relation_phase_writer.py` (graph-layer file, `AsyncSession`-injected, follows session-ownership rule). Post-dialogue trigger also wired from `dialogue_handler` (one additive call site after `relation_mutator.apply()`).
- New file: `engines/relationship/phase_rules_loader.py` — YAML loader (mirrors `economy/pricing_rules_loader.py` pattern).
- New file: `graph/relation_phase_writer.py` — writes `relationship_phase` + `phase_started_at_tick` on `RELATES_TO` (one function, `AsyncSession`-injected).
- No edit to `dialogue_handler`, `relation_mutator`, or `standing.py`.
Architecture fit: Pure new-file-add through the existing engine OCP seam. No schema change (populating an already-declared optional field is not a schema addition). No DECISIONS entry required unless the opt-in tick cadence or hysteresis config is non-obvious — if so, log in DECISIONS.
Prerequisite enablers: none (scalars are already written by `relation_mutator.apply()`). Synergizes with EXP-42 (drama director reads phase) and EXP-43 (deception engine needs phase to know who is CONFIDANT).
Effort: S   Value: high   Business-fit: high
Risks / unknowns: phase thrash at boundaries (A is ALLY one tick, NEUTRAL the next) → hysteresis band (±5 pts dead zone around phase boundary) configurable in YAML; directed edges mean A's phase toward B may differ from B's phase toward A — both are populated independently (correct behavior, explicitly asymmetric).
First slice: deterministic phase write on every dialogue turn (not full tick scan), triggered from `dialogue_handler` post-`relation_mutator`; expose phase in the existing relationship GET; one eval asserting tone shift when phase crosses ALLY.
Open questions: Should phase-transition events be gossipable (e.g. "Mira became an Ally of the player")? → `OPEN_QUESTIONS.md`.

---

## TOP 2

### EXP-41: Player-Model / Theory-of-Mind Engine
Type: new-engine
Business rationale: Implied agentic ambition (`BUSINESS_INTENT.md:59` Phase 14 "agentic
NPCs") + retrieval-precision ambition (Phase 15 — "the right memories are retrieved"). An
NPC that maintains a per-(NPC, player) model of the player's disposition, reliability
(promise-keeping), and inferred playstyle retrieves **more relevant memories** and generates
**more in-character responses**. This is the natural attribution sink for facts learned via
`engines/knowledge_learning/` (EXP-53, already built). OQ-D6 deferred this on 2026-06-05
with "express second-order belief through memories for now" — the deferral is now ripe to
revisit because `knowledge_extraction_engine.py` is shipping and needs a per-player model
to contextualize which facts were told by whom and with what reliability.
What it does: Maintains a per-(NPC, player) `player_model` node — updated post-dialogue and
post-quest outcome — tracking: `inferred_style` (AGGRESSIVE/DIPLOMATIC/MANIPULATIVE/NEUTRAL
Literal enum), `reliability` (0-100, computed deterministically from kept/broken `PLEDGE`
edges and quest outcomes), and an optional LLM-generated `summary` string ("this NPC thinks
the player is a cautious opportunist who honored past deals"). The model is injected into the
dialogue prompt as a Tier-B (droppable) context block so budget is never blown. Enables
NPCs to be surprised when the player breaks character ("You seemed more diplomatic before…").
Current state: deferred by OQ-D6 (`OPEN_QUESTIONS.md:100`). The player is already a
`character` node (`seed.py`, `is_player: true`). Perceived trust/affection/fear live on
`RELATES_TO` edges (already built). The ONLY genuinely absent piece is the persisted
per-(NPC, player) inference node and the engine that updates it. Zero Python files reference
`player_model` or `PlayerModel` — confirmed absent.
Graph/schema additions:
```yaml
# NEW: type_registry/base_nodes/player_model.yaml   → DECISIONS entry required
node_type: player_model
fields:
  id:               { type: str, required: true }
  npc_id:           { type: str, required: true }
  player_id:        { type: str, required: true }
  inferred_style:   { type: str, required: true }   # Literal-backed enum in code
  reliability:      { type: int, required: true, range: [0, 100] }
  summary:          { type: str, required: false }
  updated_at_tick:  { type: int, required: true }

# NEW: type_registry/base_edges/has_player_model.yaml   → DECISIONS entry required
edge_type: HAS_PLAYER_MODEL
src_type: character   # the NPC
dst_type: player_model
fields:
  player_id: { type: str, required: true }
```
API surface: admin `GET /v1/admin/characters/{npc_id}/player-model` for the designer
dashboard (read-only); engine-internal write path.
Composition: `engines/player_model/` — `player_model_updater.py` (post-dialogue hook,
deterministic reliability from PLEDGE + quest graph reads; optional LLM summary behind
`PLAYER_MODEL_LLM_SUMMARY_ENABLED` config flag, prompt YAML in `prompts/player_model/`);
`player_model_reader.py` (Tier-B context block assembly). Graph reads via `retrieval/`,
writes via a new `graph/player_model_writer.py` (session-injected). No LLM required for
slice-1 (reliability is deterministic).
Architecture fit: Net-new node + edge = **schema change requiring DECISIONS entry** (per
CLAUDE.md "Asking before doing"). Once approved, pure new-file-add. Token-budget: summary
must be Tier-B (droppable first per context_budget_enforcer ranked pool — OQ-D1 resolved).
Prerequisite enablers: EXP-40 (affinity phase gives richer input signal, soft); EXP-53
already built (learned facts per-player provenance makes more sense with a model). Hard dep:
DECISIONS approval for new node/edge.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: one model per NPC-player pair → `O(N_npcs)` nodes, bounded by world
size (acceptable under single-game-deployment model, DEC-068); privacy of inference is N/A
single-tenant; risk of tone overfitting (NPC labels player as AGGRESSIVE after one choice
→ mitigated by decay + multi-turn averaging).
First slice: deterministic `reliability` only (from kept/broken `PLEDGE` edge `is_active`
status + quest outcomes), no LLM summary, no new node in slice-1 (can be injected as a
transient computed block); schema + persisted node in slice-2.
Open questions: one model per NPC-player pair vs one shared player profile across NPCs?
(single-player world → either works; directed per-(NPC, player) is more realistic) → `OPEN_QUESTIONS.md`.

---

## TOP 3

### EXP-42: Player-Aware Drama Director Engine
Type: new-engine
Business rationale: "Living off-screen world" commitment (`BUSINESS_INTENT.md:36`) + Phase
14 agentic ambition. The existing `events` engine generates world events unconditionally and
`story_pacing` gates their severity globally. Neither **targets** drama at the specific player's
current engagement state. A drama director that reads player idle-time, stalled quests, and
relationship plateaus and injects a beat aimed at re-engagement is the classic "drama manager"
differentiator studios look for in middleware vs a raw event system. It converts a procedural
event engine into a narrative co-author.
What it does: Per-tick reads player engagement signals — `last_interaction_tick` (from
dialogue session), open quests with `expires_at_tick`, and EXP-40's `relationship_phase` for
plateau detection — and within `story_pacing`'s `max_event_severity` WorldState budget,
selects + injects a *targeted* world event or NPC proactive intent aimed at re-engaging
the player. Event selection is deterministic over a YAML beat library with configurable
cooldowns (no spam). LLM optional for flavor-text variation; the selection itself is a
deterministic rule engine.
Current state: `engines/events/event_pool.py:17-30` generates weighted events from
`event_pool.json`; `engines/story_pacing/story_pacing_engine.py` writes severity multipliers
to WorldState. No file reads player engagement signals or targets beats at a specific player.
`grep director` → 15 hits, none in engine logic (only `retrieval/cross_encoder_reranker.py`
internal variable name, `prompts/chapter/chapter_label_v1.yaml` prose, and
`observability/README.md`). Confirmed absent as an engine.
Graph/schema additions:
```yaml
# OPTIONAL (additive): extend base_edges/has_quest.yaml with expires_at_tick
# (already present? check: has_quest.yaml fields — if absent, add optional field)
# OR: additive optional field on base_nodes/event.yaml:
#   targets_player_id: { type: str, required: false }
# This is a single-optional-field addition to an existing node → minor schema addition
# → DECISIONS entry if targets_player_id is added; otherwise engine-internal state only.
```
API surface: tick-only; beats surface on existing WS event stream as typed push events
(additive). New `GET /v1/admin/director/status` (current cooldown state, last beat injected)
for designer dashboard.
Composition: `engines/director/` — `engagement_reader.py` (reads dialogue session
`last_interaction_tick` + quest deadlines via `retrieval/`); `beat_library_loader.py` (YAML
beat templates, mirrors `event_pool.py` pattern); `director_engine.py` (deterministic beat
selection, respects `story_pacing` WorldState multipliers via read-only graph query, never
edits `story_pacing` — OCP strict). Emits event injection calls through existing
`events`/graph path. No LLM for slice-1.
Architecture fit: New-file-add if the optional `targets_player_id` field is not added (event
creation re-uses existing event fields). If the field is added → single-field schema addition
→ DECISIONS entry. OCP strictly respected: director reads `story_pacing` WorldState values
but never edits `story_pacing_engine.py`.
Prerequisite enablers: EXP-40 (relationship plateau signal, soft); EXP-41 (engagement
quality, soft). No hard deps — can ship without either.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: clashing with `story_pacing` budget (read-only on its multipliers so no
clash possible by design); over-firing without cooldown → configurable per-beat cooldown in
YAML; determinism + RNG seed logging required (CLAUDE.md Observability strict rule).
First slice: single beat type — "player idle ≥N ticks → nearest co-located NPC pushes
a proactive intent" — gated by `story_pacing` severity budget; cooldown config; eval that
verifies the beat fires once per cooldown window, not every tick.
Open questions: Does the director own engagement metrics or read them from a
`metrics_snapshot` node? If a `metrics_snapshot` node is needed → schema call.
→ `OPEN_QUESTIONS.md`.

---

## STRONG (rank 4–5)

### EXP-43: NPC Deception / False-Belief Engine
Type: new-engine
Business rationale: "Anti-hallucination guarantee" (`BUSINESS_INTENT.md:43`) + implied
ambition "NPCs initiate, not just react" + "betrayal/deception modeling" as a candidate
territory. The graph already has `secret` nodes, `leverage` nodes (with `GROUNDED_IN →
Secret`), and a `SUSPECTS` edge. The missing piece is an **active** engine that lets an NPC
*deliberately* plant a false belief in another NPC (or the player) — seeding a `belief` node
with intentionally false content and provenance. This is the "deception" half of the social
graph and is deeply connected to the anti-hallucination moat: an NPC who was *deliberately
lied to* should have that marked so the anti-hallucination pipeline does not suppress the
false belief as an error. Studios building political intrigue, heist, or mystery games require
this.
What it does: Adds a deception intent formation layer to the planning engine and a false-
belief write path. An NPC with a `secret` they wish to protect and an NPC target with
`WARY` or lower standing can form a "deceive" goal. The engine selects a plausible false
belief to plant (drawn from a deception-strategy YAML, analogous to gossip distortion
strategies), produces it as a `belief` node with `source_character_id = deceiving_npc`,
`is_deception: bool = true`, and optionally injects it into a future proactive-dialogue turn.
The anti-hallucination pipeline is extended to treat a `is_deception: true` belief as an
*intended* false claim (not a hallucination guard failure).
Current state: `engines/gossip/distortion_strategy.py` provides STRATEGY_REGISTRY for
distortion of rumors; no parallel mechanism exists for intentional deception.
`type_registry/base_edges/believes.yaml` has `source_character_id`, `learned_at_tick`,
`confidence` provenance fields (added by EXP-53, already built) but no `is_deception` flag.
`engines/planning/goal_former.py` forms only need-satisfaction goals; no deception goal type
exists. Zero Python files contain "deception", "false_belief", or "misinform" as
logic-level terms — confirmed absent.
Graph/schema additions:
```yaml
# Extend base_edges/believes.yaml (additive optional field) → minor schema addition → DECISIONS
# believes.yaml — add:
#   is_deception: { type: bool, required: false }    # true = NPC planted this deliberately
#   deception_goal_id: { type: str, required: false } # back-link to the goal that generated it

# New: type_registry/base_nodes/deception_strategy.yaml → DECISIONS
node_type: deception_strategy
fields:
  id:          { type: str, required: true }
  name:        { type: str, required: true }   # e.g. "false_alibi", "blame_shift", "flattery_plant"
  target_type: { type: str, required: true }   # "belief" | "rumor"
  template:    { type: str, required: true }   # moustache-style template string
```
API surface: admin `GET /v1/admin/characters/{npc_id}/deceptions` (beliefs NPC planted,
for designer debug); engine-internal write path.
Composition: `engines/deception/` — `deception_goal_former.py` (extends `planning/goal_former.py`
via separate file, not edit — reads secrets + leverage + affinity phase to decide whether to
deceive); `deception_strategy_loader.py` (YAML strategy registry, mirrors
`gossip/distortion_strategy.py` pattern); `false_belief_writer.py` (calls
`graph/knowledge_writer.py` with `is_deception=True` provenance). Prompt YAML in
`prompts/deception/` for any LLM-flavored false-belief phrasing (optional in slice-1).
Architecture fit: `believes.yaml` optional field addition → **minor schema change →
DECISIONS entry**. New engine dir is pure new-file-add. OCP: `planning/goal_former.py` is
**not** edited; deception goal formation is a separate `deception_goal_former.py` that
reads the same graph inputs. Must coordinate with anti-hallucination eval runner to prevent
false-positives on `is_deception: true` beliefs.
Prerequisite enablers: EXP-40 (affinity phase to target WARY/HOSTILE relationships for
deception, soft); EXP-53 already built (belief write path exists). Hard dep: DECISIONS
approval for `is_deception` field addition.
Effort: L   Value: high   Business-fit: high
Risks / unknowns: anti-hallucination eval must be updated to treat `is_deception: true`
beliefs as intended (not guard failures) — requires a new eval matcher; without this the
deception engine would fail the eval battery; template injection risk (deception templates
must be bounded by the existing `config.MAX_PLAYER_MESSAGE_CHARS` equivalent for template
output); the first-slice limits to NPC→NPC deception only (not player-targeted) to avoid
prompt-injection surface.
First slice: NPC with a secret and a HOSTILE/WARY target forms a "false-alibi" deception goal;
seeds one `belief` node with `is_deception: true`; eval verifies the belief is retrievable
by the target NPC and the anti-hallucination pipeline does not suppress it.
Open questions: Can the player discover that a belief was a deception? (`investigate` engine
already exists in graveyard — `SUSPECTS` edge is there; wire them?) → `OPEN_QUESTIONS.md`.

### EXP-44: Long-Horizon Covert Scheming Engine
Type: new-engine
Business rationale: Implied agentic ambition (`BUSINESS_INTENT.md:59`, Phase 14) + NPC
theory-of-mind (EXP-41). The current planning engine (`engines/planning/`) forms single-tick
goals from need urgency. A covert scheming engine enables NPCs with complex agendas —
conspiring against rivals, staging a coup, orchestrating a trade embargo — to form and
execute multi-step hidden plans spanning many ticks. This is the "faction villain" and
"master manipulator" archetype studios sell in political RPGs and mystery games. It
directly extends the existing `agenda` / `faction_politics` / `oath` / `secret` graph
vocabulary.
What it does: An NPC with a high-urgency `agenda` they support, a target faction/character to
undermine, and sufficient ALLY-phase relationships (EXP-40) forms a covert multi-step `scheme`
node. Each step in the scheme maps to an existing action primitive (seed-rumor, plant-belief,
forge-alliance, trigger-event) scheduled across future ticks. The scheme is invisible to
outside NPCs unless discovered via the `investigation` engine (graveyard, but wired here).
Progress is tracked on the scheme node; if a step is blocked (target NPC dies, plan exposed)
the scheme branches or aborts.
Current state: `engines/agenda/agenda_engine.py` resolves faction votes (who-won-the-agenda)
but never forms or executes a covert plan. `engines/planning/goal_former.py` forms single-
step need-satisfaction goals only. No "scheme" or "plot" concept exists anywhere in the
engines or type_registry — confirmed absent from all Python and YAML.
Graph/schema additions:
```yaml
# NEW: type_registry/base_nodes/scheme.yaml → DECISIONS entry required
node_type: scheme
fields:
  id:              { type: str, required: true }
  instigator_id:   { type: str, required: true }   # the scheming NPC
  target_id:       { type: str, required: true }   # character or faction
  goal_type:       { type: str, required: true }   # Literal: "undermine" | "alliance" | "expose"
  steps_total:     { type: int, required: true }
  steps_completed: { type: int, required: true }
  status:          { type: str, required: true }   # active | paused | succeeded | failed | exposed
  created_at_tick: { type: int, required: true }
  expires_at_tick: { type: int, required: false }
  is_covert:       { type: bool, required: true }

# NEW: type_registry/base_edges/executes_scheme.yaml → DECISIONS entry required
edge_type: EXECUTES_SCHEME
src_type: character
dst_type: scheme
fields:
  role: { type: str, required: true }   # Literal: "instigator" | "accomplice" | "target"

# NEW: type_registry/base_edges/scheme_step.yaml → DECISIONS entry required
edge_type: SCHEME_STEP
src_type: scheme
dst_type: goal          # reuse existing goal node; each step is a goal
fields:
  step_order:  { type: int, required: true }
  completed:   { type: bool, required: true }
```
API surface: admin `GET /v1/admin/characters/{npc_id}/schemes` (all active schemes for an
NPC, designer debug only); engine-internal execution path.
Composition: `engines/scheming/` — `scheme_planner.py` (forms the scheme: reads agenda
support, leverage, and alliances via `retrieval/`; emits a scheme node with ordered steps via
`graph/scheme_writer.py`); `scheme_executor.py` (per-tick step dispatcher — maps step type
to existing action primitives: `engines/deception/` for false-belief steps, `engines/gossip/`
for rumor-injection steps, `engines/interaction/` for trade/alliance steps). No LLM for plan
formation (deterministic rule engine over graph state); LLM optional for flavor text in
proactive-dialogue turns announcing a scheme. Requires `asyncio.Semaphore` bounding (per
`MAX_CONCURRENT_TICKS` config).
Architecture fit: Three new base nodes/edges = **schema-heavy → multiple DECISIONS entries
required**. Once approved, pure new-file-add engine dir. Dispatcher calls into *existing*
engines (deception, gossip, interaction) — OCP compliant: no edits to those engines.
Prerequisite enablers: EXP-40 (affinity phase for alliance detection, soft); EXP-41
(player-model for targeting quality, soft); EXP-43 (deception step primitive, hard dep for
"plant false belief" steps). Without EXP-43, scheme can still ship with rumor-injection +
trade steps only.
Effort: XL   Value: med   Business-fit: med
Risks / unknowns: scheme explosion — a greedy schemer fills the tick budget →
`MAX_ACTIVE_SCHEMES_PER_NPC` config cap; cross-scheme conflicts (two NPCs scheming against
each other) must be deterministic; determinism + RNG seed logging required (CLAUDE.md
Observability strict rule); exposing a scheme via `investigation` engine (graveyard) would
need that engine un-graveyarded — scope risk.
First slice: single-step "undermine-faction" scheme (one agenda vote manipulation: one
`OPPOSES_AGENDA` edge planted); prove the scheme executes at the right tick and the
`agenda_engine` reflects it; no multi-step chaining in slice-1.
Open questions: Should a discovered scheme become gossipable as a `secret` → `rumor`
cascade? What is the investigation trigger cost? → `OPEN_QUESTIONS.md`.

---

## Dropped / not re-proposed (one-line each)

- **Relationship/affinity scalars** — already in `RELATES_TO`, populated by `relation_mutator.apply()`.
- **Economy/trade** — `engines/economy/trade_engine.py` + `pricing_engine.py` + `engines/currency/` already built.
- **Reputation propagation** — `engines/reputation/reputation_engine.py` already built (EXP-52 done).
- **NPC goal/GOAP** — `engines/planning/goal_former.py` + `action_selector.py` already built (EXP-51 done).
- **Daily scheduling** — `engines/routine/routine_engine.py` already built.
- **Dialogue-driven knowledge extraction** — `engines/knowledge_learning/knowledge_extraction_engine.py` built.
- **Need decay** — `engines/need/need_decay_engine.py` built.
- **Proactive dialogue** — `engines/proactive_dialogue/proactive_engine.py` built (EXP-10 done).
- **Clique/crowd/group formation** — `engines/clique/clique_formation_engine.py` built (graveyard).
- **Military/battle** — `engines/military/military_battle_service.py` built (graveyard).
- **Content moderation** — `services/output_moderation.py` + `input_moderation.py` + `content_rating_resolver.py` built (Phase 16).
- **TTS output voice** — `engines/tts/` built (piper + mock adapters).
- **Localization / multi-language** — dropped OQ-D11.
- **Voice / STT input** — dropped OQ-D11.
- **Multi-tenant isolation** — forbidden DEC-068.
- **Player-faction standing** — already `has_reputation_with.yaml` character→faction.
- **EmotionModelProtocol OCP seam** — `engines/emotion/emotion_model_protocol.py` built (EXP-13 done).
- **Distortion-strategy registry** — `engines/gossip/distortion_strategy.py` STRATEGY_REGISTRY built (EXP-15 done).
- **Location hierarchy** — `type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` built (EXP-87 done, ISSUE-057 fixed).
- **Branching quests** — `engines/quest/quest_chain_resolver.py` + `base_edges/unlocks.yaml` built (EXP-19 done).

---

## Summary ranking

| Rank | EXP | Title | Effort | Value | Fit | Schema-gated? |
|------|-----|-------|--------|-------|-----|---------------|
| 1 ⭐ | EXP-40 | Relationship affinity phase engine | S | high | high | No (fills existing optional fields) |
| 2 ⭐ | EXP-41 | Player-model / theory-of-mind | M | high | high | Yes (new node + edge → DECISIONS) |
| 3 ⭐ | EXP-42 | Player-aware drama director | M | med | high | Optional (1 field addition → DECISIONS if used) |
| 4 | EXP-43 | NPC deception / false-belief | L | high | high | Yes (1 optional field on believes.yaml → DECISIONS) |
| 5 | EXP-44 | Long-horizon covert scheming | XL | med | med | Yes (3 new nodes/edges → multiple DECISIONS) |
