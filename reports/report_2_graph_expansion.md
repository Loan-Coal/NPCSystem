# Report 2: Graph Expansion — Game Domains

> **Scope:** Design exploration only — no code changes proposed.
> **Date:** 2026-05-13

---

## Preamble: Architectural Context

The current graph organizes into four conceptual layers:

- **Truth layer**: `EVENT`, `WORLD_STATE`, `LOCATION`, `ITEM`, `FACTION`
- **Mind layer**: `MEMORY`, `BELIEF`, `GOAL`, `SECRET`
- **Social layer**: `CHARACTER` with `RELATES_TO`, `MEMBER_OF`, `HAS_REPUTATION_WITH`, `STANDS_WITH`, `OWES`
- **Narrative layer**: `QUEST`, `QUEST_TEMPLATE`, `SCHEDULE`

Engines are deterministic-per-tick orchestrators that either mutate edge fields in place (gossip distortion onto `KNOWS_ABOUT`, standing drift on `STANDS_WITH`) or create nodes from templates (events, quests, memories). Two structural patterns drive most gaps below:

1. **Lossy in-edge mutation**: gossip distortion is stored on `KNOWS_ABOUT` edge fields rather than as an independent node. This blocks queryability and provenance chains.
2. **Implicit time series**: most edges have `last_changed_at` or `arrived_at` but no historical record. The graph captures current truth only.

---

## Part A: RPG Depth Gaps

### A.1 Rumor vs. Event

**Currently expressible**: A `KNOWS_ABOUT` edge carries `distortion_type`, `distortion_level`, `distorted_summary`, and `source_character_id`. Gossip propagation in `src/npc_engine/engines/gossip/gossip_handler.py` writes one distorted summary per receiver per event.

**What's missing**:
- No first-class identity for "the version of the story being told." If three NPCs each garble the same event differently, the graph has three edges but no way to ask "how many rumors are circulating about event_42?" or "which rumor variant is most prevalent in the docks?"
- No chain-of-custody: `source_character_id` is one-hop only. A rumor that passed through five NPCs only remembers the immediate sharer.
- No rumor mutation tree (Chinese-whispers branching).
- No "rumor heat" — a rumor believed by 30 NPCs has the same graph weight as one believed by 2.

**Proposed addition**: `RUMOR` node + relationships.

- **`RUMOR` node**: `id`, `content`, `origin_event_id` (nullable — some rumors are pure fabrication), `created_at_tick`, `mutation_distance` (edits from origin), `severity`, `is_fabricated` (bool).
- **`DERIVED_FROM` edge** (Rumor → Rumor): tracks the mutation tree. Each gossip step with significant distortion creates a new `RUMOR` node linked to its parent.
- **`BELIEVES_RUMOR` edge** (Character → Rumor): replaces distortion fields on `KNOWS_ABOUT`. Holds `confidence`, `learned_at_tick`, `from_character_id`.
- **`CONTRADICTS` edge** (Rumor → Rumor): for variants of the same origin event.

**Interacting engines**: gossip (replaces in-edge distortion with rumor-node creation when distortion crosses a threshold), dialogue (NPCs reference rumors by ID, enabling player to "name the rumor"), memory (rumors that contradict beliefs trigger consolidation).

**Effort**: **L** — new node + 3 edge types + gossip rewrite + memory/dialogue integration.

---

### A.2 Witnessed Behavior

**Currently expressible**: `PARTICIPATED_IN` (Character → Event) with a `role` field. `KNOWS_ABOUT` for awareness. `RELATES_TO` deltas for emotional outcomes. The graph can say "Alice witnessed event_7" and "Bob participated in event_7" but cannot say "Alice's opinion update of Bob is sourced to event_7."

**What's missing**:
- No edge between two characters tied to a specific event capturing the social interpretation.
- Witness reliability is not modeled. The `gossipy/credulity/honesty` triad affects gossip distortion but witness credibility has no representation.
- No way to query "all things Alice has personally seen Bob do" without joining through events twice.

**Proposed addition**: `WITNESSED` edge (Character → Character, event-keyed).

- **`WITNESSED` edge**: `event_id`, `action_type` (str: "stole", "helped", "attacked", "lied"), `witnessed_at_tick`, `clarity` (0–100 — affects whether the witness later misremembers), `interpretation` (str — the witness's biased reading), `disclosed` (bool — has the witness told anyone?).

**Interacting engines**: memory engine (`WITNESSED` edges with high `clarity` feed `MEMORY` formation with high `vividness`), faction politics (a witnessed event reweights `HAS_REPUTATION_WITH` toward the perpetrator's faction), gossip (a `WITNESSED` edge with `disclosed=false` is a latent rumor source), quest generation (enables "find someone who saw X" templates).

**Effort**: **M** — new edge contract + new engine hook ("witness reaction" per event) + gossip integration.

---

### A.3 Social Groups / Coalitions

**Currently expressible**: `MEMBER_OF` (Character → Faction) — but factions are global, declared at seed time, and binary. A tavern clique of three drinkers, or a four-person conspiracy plotting against a noble, has no graph form.

**What's missing**:
- Emergent grouping: no graph entity for "the regulars at the Iron Lantern."
- Subgroup/clique detection has no anchor — the graph has no place to write the result.
- No group-level state: shared goals, shared secrets, group cohesion, founding event.
- `FACTION` is too heavy: world-level political blocs, not casual social units.

**Proposed addition**: `GROUP` node (lighter weight than `FACTION`).

- **`GROUP` node**: `id`, `name`, `kind` (enum: clique, conspiracy, family, crew, fellowship, mob), `cohesion` (0–100), `is_secret` (bool), `formed_at_tick`, `dissolved_at_tick` (nullable), `home_location_id` (nullable).
- **`BELONGS_TO_GROUP` edge** (Character → Group): `role`, `joined_at_tick`, `commitment` (0–100).
- **`GROUP_SHARES_SECRET` edge** (Group → Secret) and **`GROUP_PURSUES` edge** (Group → Goal).
- **`OPPOSES` edge** (Group → Group or Group → Character): for conspiracy targets.

**Interacting engines**: gossip (same-group members propagate with lower distortion), new **clique-formation engine** (scans co-location + reciprocal high `RELATES_TO.affection` and spawns groups when thresholds cross), quest generation (groups as first-class quest givers and antagonists).

**Effort**: **M** — new node + 3 edge types + clustering engine.

---

### A.4 Skills and Traits

**Currently expressible**: `gossipy`, `credulity`, `honesty` are flat int properties on `CHARACTER`. `archetype` is a single string tag. There is no skill model.

**What's missing**:
- An NPC cannot have "blacksmithing 70, lockpicking 20."
- Quest gating: quest templates cannot say "needs a target with crafting≥50."
- Dialogue gating: persuasion/intimidate checks have no data backing.
- No skill progression — completing quests has no place to land experience.
- Traits as orthogonal modifiers (brave, paranoid, claustrophobic) collapse into archetype today.

**Proposed addition**: `SKILL` and `TRAIT` nodes.

- **`SKILL` node**: `id`, `name`, `category` (combat, social, craft, knowledge), `description`. Skills are types, not per-character instances.
- **`HAS_SKILL` edge** (Character → Skill): `level` (0–100), `xp` (int), `last_used_at_tick`.
- **`TRAIT` node** + **`HAS_TRAIT` edge**: `intensity` (0–100), `is_secret` (bool).
- **`REQUIRES_SKILL` edge** (QuestTemplate → Skill): `min_level`.

**Interacting engines**: quest generation slot validator gains skill-threshold checks, dialogue gains skill-gated branch logic, economy's pricing engine gains `crafting`-based price adjustments, new **skill-progression engine** increments XP on quest completion.

**Effort**: **M** — two node types + two edge types + a small progression engine.

---

### A.5 Location History / Visited

**Currently expressible**: `LOCATED_AT` (Character → Location) with `arrived_at` and `is_permanent_resident`. The routine engine moves NPCs by overwriting this edge in place. **Past locations are lost.**

**What's missing**:
- "Where was Bob last night?" — unanswerable.
- Alibi queries.
- Migration patterns / NPC backstory.
- Ambush opportunities: "lay in wait where the target usually passes" requires path history.

**Proposed addition**: `WAS_AT` edge (Character → Location) — append-only.

- **`WAS_AT` edge**: `arrived_at_tick`, `departed_at_tick`, `reason` (enum: routine, quest, fled, ordered), `tick_duration`.

The routine engine archives the previous `LOCATED_AT` as `WAS_AT` instead of deleting it. A pruning policy compacts entries older than N ticks into `BIOGRAPHICAL_STAY` summaries to bound graph size.

**Interacting engines**: routine engine (trivial modification), new alibi query helper, gossip (enables "I heard he was seen at the docks" rumor seeding).

**Effort**: **S** — one new edge contract + small routine-engine modification.

---

### A.6 Pledges and Pacts Between Characters

**Currently expressible**: `OWES` tracks transactional debt; `RELATES_TO` tracks emotional state. Neither models commitment — "sworn to protect," "blood enemy," "oath of fealty."

**What's missing**:
- A structural relationship that affects AI behavior regardless of transient mood.
- Pact breaking: a violation should be a high-magnitude `EVENT` with social fallout.
- Marriages, oaths, mentor/apprentice — semantic relationships that should override mood swings.

**Proposed addition**: `PLEDGE` edge (Character → Character).

- **`PLEDGE` edge**: `pledge_type` (enum: protect, serve, kill, marry, mentor, fealty, vendetta), `sworn_at_tick`, `expires_at_tick` (nullable), `witness_character_id` (nullable), `binding_event_id` (nullable), `is_active` (bool), `severity` (consequence magnitude of breaking it).

**Interacting engines**: faction politics (breaking a pledge generates a high-severity `EVENT` and a large `STANDS_WITH` swing), dialogue/action resolver (AI behavior selector consults `PLEDGE` edges before generic `RELATES_TO`), new **oath engine** (tick-level scan for pledge violations), quest generation (`PLEDGE` as a quest fixture — "avenge your blood oath against X").

**Effort**: **M** — new edge + oath-violation detection engine with a YAML rule loader.

---

### A.7 Faction Standing History

**Currently expressible**: `STANDS_WITH` (Faction → Faction) holds `standing` and `last_changed_at`. The faction politics engine mutates `standing` in place via `set_standing()`. **All history is lost.**

**What's missing**:
- "Have the Merchants ever allied with the Temple before?" — unanswerable.
- Treaty modeling: a treaty has a start, an end, terms, and a binding event.
- Political memory: NPCs cannot remember "we used to be allies before the betrayal."
- Trend detection: story pacing could downweight predictable trajectories if it could see them.

**Proposed addition**: `FACTION_STANDING_EVENT` node + `TREATY` node.

- **`FACTION_STANDING_EVENT` node**: `id`, `src_faction_id`, `dst_faction_id`, `delta`, `new_standing`, `tick_id`, `cause_event_id` (nullable), `cause_rule_id` (nullable).
- **`TREATY` node**: `id`, `parties` (list of faction IDs), `terms` (str), `signed_at_tick`, `expires_at_tick`, `binding_event_id`, `status` (active, broken, expired).
- **`BOUND_BY` edge** (Faction → Treaty): `role` (signatory, guarantor).
- **`CAUSED_STANDING_CHANGE` edge** (Event → FactionStandingEvent): provenance.

**Interacting engines**: faction politics (in addition to mutating `STANDS_WITH`, append a `FACTION_STANDING_EVENT` — trivial diff), new **treaty engine** (checks expiry, detects violations, generates high-severity events), memory consolidation (an NPC with reputation spanning two warring factions gets a belief about the conflict's history).

**Effort**: **M** — `FACTION_STANDING_EVENT` is **S** alone; adding `TREATY` + a treaty engine makes it **M**.

---

### A.8 Consequence Chains

**Currently expressible**: Disruption rules in `src/npc_engine/engines/events/disruption_loader.py` let a high-severity event override routines and chain effects. But the resulting state changes are not tagged back to the originating event in the graph.

**What's missing**:
- "What's the downstream of the dock fire?" — requires reading disruption rules and reconstructing manually.
- Quest causality: a quest that exists because of an event has no graph link to that event.
- Narrative replay: the player cannot ask "show me the chain of consequences from the assassination."

**Proposed addition**: `CAUSED_BY` edge (polymorphic → Event).

- **`CAUSED_BY` edge** (Event → Event, Quest → Event, FactionStandingEvent → Event, Rumor → Event): `causation_strength` (0–100), `cause_type` (direct, indirect, narrative), `tick_lag`.

**Interacting engines**: event handler (when a disruption rule fires from event A, the resulting routine overrides are tagged), quest generation (quests triggered by an event write `CAUSED_BY`), new **provenance query layer** (walks `CAUSED_BY` chains backward from any node), story pacing (analyzes consequence-chain depth to gauge narrative density).

**Effort**: **S** for the edge contract; **M** to retrofit consistently across all engines.

---

## Part B: Adjacent Game Domains

### B.1 Detective / Mystery Games

**Currently expressible with zero changes**:
- Multiple witnesses via `PARTICIPATED_IN` with `role`.
- Distorted accounts via gossip distortion fields.
- Suspect-victim emotional ties via `RELATES_TO`.
- Secret holdings via `KNOWS_SECRET`.
- Location-time via `LOCATED_AT.arrived_at`.

**What's missing**:
- **Physical evidence**: no `EVIDENCE` node distinct from `ITEM`. Clues (bloody knife, footprint, ledger entry) are not items carried by the player — they are scene-bound with provenance.
- **Alibi queries**: no `WAS_AT` history (see A.5).
- **Suspect graph**: no structured `SUSPECTS` edge linking investigator → suspect → crime.
- **Deduction state**: no place to write the player's accumulated theory separate from world truth.
- **Unreliable narrators**: distortion is anonymous; no field for "Witness X had motive to lie about Y."

**Proposed additions**:
- **`EVIDENCE` node**: `id`, `kind` (physical, testimonial, documentary), `description`, `discovered_at_tick`, `discovered_by_character_id`, `links_to_event_id`, `confidence` (0–100).
- **`IMPLICATES` edge** (Evidence → Character): `weight` (0–100), `is_misleading` (bool — red herrings).
- **`SUSPECTS` edge** (Character → Character): tied to an `Event`, with `evidence_ids` (list), `confidence`.
- **`DEDUCTION` node** (theory state): `id`, `held_by_character_id`, `claim`, `supporting_evidence_ids`, `confidence`, `status` (open, confirmed, refuted).
- **`PRESENT_AT` edge** (Evidence → Location).
- New **investigation engine**: surfaces inconsistencies (Bob claims `LOCATED_AT` tavern but a `WITNESSED` edge places him elsewhere).

**Effort**: **L** — 2–3 new node types, 3–4 edge types, plus an investigation engine that benefits from LLM-assisted "explain the inconsistency."

---

### B.2 Political Simulation (Crusader Kings-adjacent)

**Currently expressible with zero changes**:
- Factions with archetypes, controlled territory (`CONTROLS`).
- Inter-faction standings with drift and event-driven change.
- Character reputation with factions (`HAS_REPUTATION_WITH`).
- Secrets that can be leveraged (`KNOWS_SECRET`).
- Faction membership with roles (`MEMBER_OF.role`).

**What's missing**:
- **Voting / coalition logic**: no `VOTE` events, no `AGENDA` nodes.
- **Succession / inheritance**: no `HEIR_OF` or `TITLE` modeling. Factions have no leader node.
- **Power levels**: faction archetype is qualitative; no treasury or military-strength score.
- **Blackmail mechanics**: `KNOWS_SECRET` exists but no `LEVERAGE` edge linking secret-holder → target with explicit demand.
- **Treaties with expiry** (see A.7).

**Proposed additions**:
- **`TITLE` node**: `id`, `name`, `faction_id`, `power` (int), `is_inheritable`, `current_holder_id`.
- **`HOLDS_TITLE` edge** (Character → Title): `since_tick`.
- **`HEIR_OF` edge** (Character → Character): `priority`, `legitimacy`.
- **`AGENDA` node**: `id`, `description`, `proposed_by_faction_id`, `status` (proposed, voting, passed, rejected), `deadline_tick`.
- **`SUPPORTS_AGENDA` / `OPPOSES_AGENDA` edges** (Character/Faction → Agenda).
- **`LEVERAGE` edge** (Character → Character): `secret_id`, `demand`, `status` (held, used, exposed).
- Power fields on `FACTION`: `power_score`, `treasury`, `military_strength`.
- New **succession engine** + **agenda/voting engine**.

**Effort**: **L** — 4–5 new node types, several edges, 2 new engines. Best as an optional plugin module.

---

### B.3 Social Simulation (Dwarf Fortress / Sims-adjacent)

**Currently expressible with zero changes**:
- Mood per character (`current_mood`) plus in-memory `EmotionState`.
- Pair-wise relationship dynamics via `RELATES_TO`.
- Gossip-mediated information spread.
- Co-location queries via `LOCATED_AT`.
- Schedules driving daily contact patterns.

**What's missing**:
- **Social needs**: no satiation model. There is no node home for hunger, social interaction, rest needs.
- **Mood contagion**: emotion engine is per-character only; co-located NPCs do not influence each other's mood automatically.
- **Status hierarchies**: no `OUTRANKS` edge or social-status score.
- **Clique dynamics**: see A.3 (`GROUP` node).
- **Life events**: birth, death, marriage, illness have no first-class representation.
- **Relationship phases**: `RELATES_TO` is a snapshot, not a trajectory.

**Proposed additions**:
- **`NEED` node** (or per-character need fields): `kind` (hunger, social, rest, recreation), `level` (0–100), `decay_rate`.
- **`SATISFIES_NEED` edge** (Action/Item/Location → Need): `magnitude`.
- **`OUTRANKS` edge** (Character → Character): contextual ranking within faction or group.
- **`LIFE_EVENT` node**: specialized `EVENT` subtype (birth, death, marriage, illness) — high persistence, drives biography.
- **`RELATIONSHIP_PHASE` field** on `RELATES_TO`: `phase` (str enum), `phase_started_at`.
- New **mood-contagion engine**: tick-level scan; co-located NPCs with high `affection` exchange a portion of `current_mood`.
- New **need-decay engine**: every tick decrements needs; high deficits trigger goals.

**Effort**: **L** — multiple subsystems. Mood contagion alone is **M** and high-impact.

---

### B.4 Strategy / 4X

**Currently expressible with zero changes**:
- Territory control via `CONTROLS` (Faction → Location).
- Faction-to-faction conflict via `STANDS_WITH`.
- Item rarity and value (`ITEM`).
- World conditions in `WORLD_STATE.active_conditions`.

**What's missing**:
- **Contested control**: `CONTROLS` is binary, no `control_strength` or `contested_by_faction_id`.
- **Resource nodes**: locations carry no resource yields.
- **Supply lines / map topology**: no `CONNECTS_TO` edge between locations. Locations exist as a set, not a graph — travel cost is unmodeled.
- **Treaty expiry**: see A.7.
- **Unit / army modeling**: no `ARMY` node; combat is event-only.

**Proposed additions**:
- **`CONTROLS` edge upgrade**: add `control_strength` (0–100), `contested_by_faction_id` (nullable), `since_tick`.
- **`RESOURCE_NODE` node** (or fields on `LOCATION`): `kind` (gold, iron, grain, mana), `yield_per_tick`, `depletion`.
- **`PRODUCES` edge** (Location → Resource).
- **`CONNECTS_TO` edge** (Location → Location): `kind` (road, river, sea, secret), `travel_cost`, `is_open` (closeable by events).
- **`ARMY` node**: `id`, `faction_id`, `strength`, `current_location_id`, `composition`.
- **`COMMANDS` edge** (Character → Army) and **`OCCUPIES` edge** (Army → Location).
- New **economy expansion engine** (yields, trade flow over `CONNECTS_TO`).
- New **military movement engine** (army repositioning + siege resolution).

**Effort**: **L** — substantial new subsystem. `CONNECTS_TO` alone is **S** and unlocks travel/supply queries without armies.

---

### B.5 Narrative Adventure / Interactive Fiction

**Currently expressible with zero changes**:
- Quest state machine (offered, active, complete, failed) via `QUEST.status`.
- Event timeline ordered by `tick_id` / `occurred_at`.
- Memory of past scenes via `MEMORY` / `REMEMBERS`.
- Player character is a `CHARACTER` with `is_player=true`.

**What's missing**:
- **Branching narrative state**: no node for "story branch taken" — quest completion is one bit.
- **Permanent consequences**: events drift in importance; no `IS_CANONICAL` flag for plot-critical events.
- **Chapter / scene structure**: no aggregation above `EVENT` — campaigns need acts/chapters.
- **Player choice nodes**: no record of "the player chose X over Y at decision point Z."

**Proposed additions**:
- **`CHAPTER` node**: `id`, `name`, `description`, `started_at_tick`, `ended_at_tick`, `theme`, `status`.
- **`PART_OF_CHAPTER` edge** (Event/Quest → Chapter).
- **`CHOICE` node**: `id`, `description`, `chosen_at_tick`, `chosen_by_character_id`, `selected_option`, `available_options` (list), `consequence_event_id` (nullable).
- **`UNLOCKED_BY` edge** (Quest/Event → Choice): for branching prerequisites.
- **`IS_CANONICAL` field** on `EVENT`: prevents memory decay and gossip distortion above a threshold.
- **`NARRATIVE_BEAT` node** (consumed by story pacing): `id`, `kind` (rising, climax, falling, denouement), `intensity`, `chapter_id`.
- New **chapter engine**: detects chapter transitions based on completed quest clusters or `NARRATIVE_BEAT` density.

**Effort**: **L** with LLM integration for chapter labeling / beat detection; **M** for the structural pieces alone.

---

## Part C: Cross-Domain Primitives

These are the additions that serve three or more of the gaps and domains above. Implement these first.

### C.1 `WITNESSED` Edge (Character → Character, event-keyed)

Serves: A.2 (witnessed behavior), B.1 (detective evidence), B.3 (social simulation gossip seeding), A.1 (rumor origin tracking).

A single contract — `event_id`, `action_type`, `clarity`, `interpretation`, `disclosed` — unlocks witness/alibi queries, becomes the trigger for both gossip seeding and memory formation, and gives detective games their core primitive. **Highest ROI in the report.**

**Effort**: **M**

---

### C.2 `CAUSED_BY` Edge (Polymorphic → Event)

Serves: A.8 (consequence chains), B.1 (clue-to-crime linking), B.2 (political ripple effects), B.5 (narrative branches).

Once every engine that creates a node in response to an event also writes `CAUSED_BY`, the entire history becomes a navigable causality DAG. This is the difference between a graph database and a narrative graph — provenance turns the graph into a story.

**Effort**: **S** (contract) + **M** (engine retrofits)

---

### C.3 `WAS_AT` Edge — Location History (Append-only)

Serves: A.5 (location history), B.1 (alibi queries), B.2 (faction movement / scheming), B.3 (relationship co-location history), B.4 (army positioning history).

The smallest addition with surprisingly high payoff. Every "where were they?" query that is currently impossible becomes one Cypher hop.

**Effort**: **S** (with pruning policy)

---

### C.4 `GROUP` Node + Membership Edges

Serves: A.3 (cliques/coalitions), B.1 (suspect groups / conspiracies), B.2 (political blocs below faction), B.3 (Sims-style friend groups), B.5 (party-of-adventurers narrative).

`GROUP` fills the missing tier between solo `CHARACTER` and global `FACTION`. Every domain has casual social units that the current graph collapses. Once `GROUP` exists, gossip, quest generation, faction politics, and narrative all gain a new addressable entity.

**Effort**: **M**

---

### C.5 `RUMOR` Node + Mutation Tree

Serves: A.1 (rumor identity), A.2 (witnessed-but-disclosed knowledge), B.1 (red-herring testimonies in mysteries), B.2 (political misinformation campaigns), B.5 (narrative misdirection).

Promoting rumor from edge field to first-class node is the single biggest unlock for player agency around information. Players can name, share, refute, and weaponize rumors. The mutation tree (`DERIVED_FROM`) is what makes "track the lie to its source" a tractable gameplay loop.

**Effort**: **L** — but the highest narrative-richness payoff.

---

## Summary Table

| Addition | RPG Gap | Detective | Politics | Social | 4X | Narrative | Effort |
|---|---|---|---|---|---|---|---|
| `RUMOR` node + mutation tree | A.1 | ✓ | ✓ | ✓ | | ✓ | L |
| `WITNESSED` edge | A.2 | ✓ | ✓ | ✓ | | | M |
| `GROUP` node | A.3 | ✓ | ✓ | ✓ | | ✓ | M |
| `SKILL`/`TRAIT` nodes | A.4 | | | ✓ | | ✓ | M |
| `WAS_AT` edge | A.5 | ✓ | ✓ | ✓ | ✓ | | S |
| `PLEDGE` edge | A.6 | | ✓ | ✓ | | ✓ | M |
| `FACTION_STANDING_EVENT` + `TREATY` | A.7 | | ✓ | | ✓ | ✓ | M |
| `CAUSED_BY` edge | A.8 | ✓ | ✓ | ✓ | ✓ | ✓ | S+M |
| `EVIDENCE` + `SUSPECTS` + `DEDUCTION` | | ✓ | | | | ✓ | L |
| `TITLE` + `AGENDA` + `LEVERAGE` | | | ✓ | ✓ | | ✓ | L |
| `NEED` + mood contagion engine | | | | ✓ | | | M |
| `CONNECTS_TO` + `ARMY` | | | | | ✓ | | L |
| `CHAPTER` + `CHOICE` + `NARRATIVE_BEAT` | | | | | | ✓ | L |

---

## Recommended Build Order

If pursued, a sequencing that preserves backward compatibility (existing edge fields remain valid — new nodes augment rather than replace):

1. **`WAS_AT`** (S) — smallest, unlocks alibi/history queries immediately, retrofits in routine engine.
2. **`CAUSED_BY`** (S+M) — provenance retrofit; every later engine writes it; retroactive historical value.
3. **`WITNESSED`** (M) — replaces a class of in-edge magic with structured data; ties to gossip and memory.
4. **`GROUP`** (M) — fills the missing social tier.
5. **`RUMOR` node** (L) — replaces in-edge distortion; biggest narrative gain.
6. Domain-specific clusters (`EVIDENCE`/`SUSPECTS` for detective, `TITLE`/`AGENDA` for politics, etc.) as opt-in modules.
