# Expansion Lens X2 — Missing Engines / New Domains

**Lens:** X2 (new engines/domains the product vision implies but that do not exist).
**Mode:** READ-ONLY. Rubric: `project-harness/expansion/BUSINESS_INTENT.md`.
**Constraints honored:** layer model (downward-only), LLM only in `engines/`, Cypher only
in `graph/`, prompts in YAML only, OCP add-by-new-file via `type_registry/base_nodes|edges/`,
Pydantic v2, single-tenant (DEC-068 — no multi-tenant `world_id` proposed anywhere below).

IDs run EXP-50..EXP-79. Numbered top-down by combined Value × Business-fit.

---

## Reconnaissance: what already exists (so these are NOT re-proposed)

| Candidate territory | Verdict | Evidence |
|---|---|---|
| Personal NPC relationships (trust/fear/affection) | **Primitive exists; affinity *semantics* do not** | `type_registry/base_edges/relates_to.yaml:5-12` carries trust/fear/affection/interaction_count + a **declared-but-dead** `relationship_phase`/`phase_started_at_tick`; `relationship_phase` is used in **zero** Python files (grep hit only the YAML). Deltas are applied raw by `engines/dialogue/relation_mutator.py` with no phase/affinity layer. → **EXP-50 keeps** (fill the dead field). |
| Reputation propagation | **Partial: faction standing + gossip exist, propagation does not** | `has_reputation_with.yaml` (character→faction standing), `faction_politics` drifts standings deterministically, `gossip` spreads rumors. No engine propagates *personal* reputation across the social graph. → **EXP-52 keeps (narrowed)**. |
| NPC goal/GOAP autonomy | **Schema + CRUD only; no autonomy** | `goal.yaml` node + `PURSUES` edge exist, but goals are only **seeded via API** (`api/routes/goals.py:62 seed_goal`, plus GET/PATCH/DELETE). `agenda_engine` is **faction voting**, not personal planning. No engine forms goals or selects actions toward them. → **EXP-51 keeps**. |
| Daily-life world-simulation tick | **Mostly exists** | `routine` (location by schedule), `need` (need decay), `mood` (contagion), `agenda`/`succession`/`oath`/`military`/`economy` all run per-tick. → **DROPPED** as net-new; folded as the consumer of EXP-51. |
| Dynamic world-event / drama director | **Partial: generator + gater exist; targeted director does not** | `events` engine generates autonomous world events; `story_pacing` writes `max_event_severity`/`quest_generation_rate` *multipliers* to gate them (`story_pacing_engine` docstring). Neither **targets** drama at a specific player/NPC based on player state. → **EXP-54 keeps (narrowed to a player-aware director)**. |
| Dialogue-driven knowledge extraction | **None** | `dialogue_handler` only writes memory from arousal (`dialogue_handler.py:179 create_from_arousal`); it never writes new `KNOWS_ABOUT`/belief facts the player tells the NPC. → **EXP-53 keeps (highest moat-fit)**. |
| Player-modeling / theory-of-mind | **None** | No `player` node beyond a relation target; no NPC model of player intent/style. → **EXP-55 keeps**. |
| Localization / multi-language | **None** | Only hit is an instruction inside `prompts/dialogue/system_v1.yaml`; no output-language pipeline. → **EXP-56 keeps (low business-fit, see note)**. |
| Voice / STT input | **None (TTS only)** | `tts` engine exists; no STT/transcription anywhere (grep empty). → **EXP-57 keeps (low fit)**. |

---

## TOP 3 (highest value — flagged)

> **EXP-53 (knowledge extraction), EXP-50 (affinity), EXP-51 (goal autonomy)** are the
> three highest-value proposals. EXP-53 is the strongest *business-fit* because it directly
> feeds the anti-hallucination moat (Success Criterion 1): an NPC that can *learn* facts
> from the player and ground future answers in them is the differentiator a studio buys.

---

### EXP-53: Dialogue-Driven Knowledge Learning ⭐ TOP-1 (RESOLVED DEC-072 — now M, single-pass, no new edge)
Type: new-engine
**RESOLVED 2026-06-05 (DEC-072).** Simplified: no second LLM pass, no `LEARNED_FROM` edge — reuse `BELIEVES`.
Business rationale: Anti-hallucination is the core moat — "NPCs answer only from known context" (Success Criterion 1, `BUSINESS_INTENT.md:74`; commitment `FEATURES.md:31-33`). Today an NPC can *forget* what the player just told it because dialogue never writes new facts to the graph; the moat is half-built. This closes the learn→ground→answer loop, and is part of the **dialogue showcase priority**.
What it does: The dialogue LLM already returns structured output (response + relation deltas + action + expression). Extend that **same schema** with an optional **`learned_facts`** list — facts the player asserted ("the bandits moved to the old mill", "I am the new captain") emitted **in the same single pass** (no extra round-trip, ≈ a few output tokens). A deterministic validator gates them; accepted facts are written as `belief` nodes via a `BELIEVES` edge from the speaking NPC, with provenance `source_character_id = player_demo`. Retrieval then surfaces these so the NPC answers from what it *learned*. **Player-sourced knowledge is legitimate** (OQ-D3): the anti-hallucination eval (EXP-32) scores a repeated player-taught fact as grounded, authorized by the provenance.
Current state: `dialogue_handler.py:179` writes arousal-driven `memory` nodes only; no fact/belief write. `believes.yaml` (char→belief, currently empty fields) is the write target.
Graph/schema additions (RESOLVED): **reuse the `belief` node + `BELIEVES` edge.** Player-taught facts land on `belief` nodes (NOT `event`/`KNOWS_ABOUT` — events are reserved for world-happenings). The only schema touch is **3 optional provenance fields on `believes.yaml`**:
```yaml
# believes.yaml — add optional provenance (no new edge type)
edge_type: BELIEVES
src_type: character
dst_type: belief
fields:
  source_character_id: { type: str, required: false }   # = player_demo when player-taught
  learned_at_tick:     { type: int, required: false }
  confidence:          { type: int, required: false, range: [0, 100] }
```
API surface: none new on the LLM path (rides the existing dialogue structured output); optional admin `GET /v1/admin/characters/{id}/beliefs` for the designer dashboard.
Composition: `engines/knowledge_learning/` validates the `learned_facts` slice of the dialogue output through a Pydantic model, dedupes against known beliefs via `retrieval/`, and writes through a new graph sub-writer `graph/knowledge_writer.py` (graph-owned, `AsyncSession`-injected). No second LLM client, no new prompt file (the field is added to the existing dialogue prompt schema).
Architecture fit: new engine dir + one graph sub-writer + 3 optional fields on an existing edge. The provenance-field add is a **minor schema change → DEC-072** (approved).
Prerequisite enablers: EXP-32 (so the learn-loop is *measured*); EXP-30 (learned beliefs enter the ranked pool, not an overflowing tier).
Effort: **M** (was L)   Value: high   Business-fit: high
Risks / unknowns: extraction hallucination (LLM emits a fact the player never stated) — strict validator + low-confidence quarantine; contradiction handling (`contradicts.yaml` edge exists — keep both, prefer higher-confidence/recent at retrieval); trust model (should a hostile NPC believe the player? — gate by affinity later).
First slice: emit + persist only **self-assertions** ("I am X") as one `BELIEVES` edge, behind a config flag; prove the NPC repeats the learned fact a turn later in an eval (EXP-32).
Fact visibility & contradictions (RESOLVED 2026-06-05, DEC-072): learned beliefs **are gossipable** — they feed the gossip engine like any knowledge (player can seed a rumor by telling one NPC). On contradiction, **keep both + link with the existing `CONTRADICTS` edge**; prefer higher-confidence/higher-trust-source at answer time, never overwrite. Binds EXP-53 to the gossip expansion (EXP-15/16).

---

### EXP-50: Relationship / Affinity engine ⭐ TOP-2
Type: new-engine
Business rationale: "Persistent relationships per NPC" is an explicit commitment (`BUSINESS_INTENT.md:35`). The schema already promises *relationship phases* but the field is dead — a studio reading the OpenAPI sees `relationship_phase` and gets nothing. This turns raw trust/fear/affection scalars into named, queryable relationship states (stranger → acquaintance → ally → rival → confidant) that drive dialogue tone and gate quests.
What it does: Per-tick (and post-dialogue) engine that maps the trust/fear/affection vector + interaction_count onto a `relationship_phase` via deterministic thresholds, records `phase_started_at_tick`, and emits phase-transition events ("X now considers you an ally"). Dialogue reads the phase to set tone; quests can require a phase. Distinct from `relation_mutator` (which only clamps raw deltas) — this is the *semantic* layer over the scalars.
Current state: scalars + dead phase fields exist at `type_registry/base_edges/relates_to.yaml:5-12`; `relationship_phase` referenced in **zero** Python files. `relation_mutator.py` applies raw deltas with no phase logic.
Graph/schema additions: no new node/edge — fills existing `relationship_phase` (make it a `Literal`-backed enum) and `phase_started_at_tick`; optional transition-audit node:
```yaml
# base_nodes/relationship_event.yaml
node_type: relationship_event
fields:
  id: { type: str, required: true }
  character_id: { type: str, required: true }
  other_id: { type: str, required: true }
  from_phase: { type: str, required: true }
  to_phase: { type: str, required: true }
  at_tick: { type: int, required: true }
```
API surface: `GET /v1/characters/{id}/relationships` (returns phase + scalars) for the dashboard; phase-transition events on the existing WS event stream. Mostly tick-driven.
Composition: `engines/affinity/` with a `phase_rules_loader.py` (YAML thresholds, mirrors `economy/pricing_rules_loader.py` pattern). Reads `relates_to` via `retrieval/`, writes phase via `graph/` (existing relation writer). No LLM. Dialogue prompt builder reads the phase string.
Architecture fit: new-file-add (new engine dir + a thresholds rules YAML + optional new node YAML). Populating an existing-but-empty schema field is low-risk; the optional `relationship_event` node is a **schema addition → DECISIONS entry**.
Prerequisite enablers: none (scalars already populated by dialogue). Synergizes with EXP-52 (reputation) and EXP-51 (goals can target high-affinity NPCs).
Effort: S   Value: high   Business-fit: high
Risks / unknowns: threshold tuning is content, not code — must be designer-editable YAML (honor "designers extend without engineers", SC-8); phase thrash near boundaries → add hysteresis.
First slice: deterministic 4-phase mapping from trust/affection thresholds written to the existing field on each dialogue turn; expose in the existing character GET; one eval asserting tone shift.
Open questions: are phases symmetric (mutual) or directed per edge? `relates_to` is directed → assume directed. (ASSUMPTION: directed.)

---

### EXP-51: NPC Goal-Formation & Action-Selection (lightweight GOAP) engine ⭐ TOP-3
Type: new-engine
Business rationale: Implied ambition "agentic NPCs that initiate, not just react" (`BUSINESS_INTENT.md:59`, Phase 14). The `goal` node + `PURSUES` edge already exist but goals are only **human-seeded** (`api/routes/goals.py:62`); no NPC ever *forms* a goal or acts on one. This is the missing "autonomous, not reactive" core.
What it does: Per-tick engine that (1) **forms** goals for NPCs from drives — unmet `need` nodes, faction `agenda`s they support, broken `oath`s, low-affinity rivals — writing `PURSUES` edges with urgency; and (2) **selects** the next action toward the highest-urgency goal from a fixed action vocabulary (move-to, seek-NPC, gossip, propose-trade, advance-quest), dispatched through the existing `interaction` dispatcher. Deterministic action scoring; LLM only used (optionally) to phrase the *intent line* for proactive dialogue (EXP-58 dependency).
Current state: `goal.yaml` + `pursues.yaml` exist; CRUD-only via `goals.py`. `agenda_engine` is faction voting, not personal planning. `routine` moves NPCs by fixed schedule, not by goal. → greenfield engine over existing schema.
Graph/schema additions: reuse `goal`/`PURSUES`; add satisfaction provenance reusing existing `satisfies_need.yaml` pattern; add:
```yaml
# base_edges/goal_targets.yaml
edge_type: GOAL_TARGETS
src_type: goal
dst_type: character        # or location / item / faction (union via multiple files, OCP)
fields:
  priority: { type: int, required: true, range: [0, 100] }
```
API surface: engine-internal/tick-only; admin `GET /v1/admin/characters/{id}/goals` already partly covered by `goals.py` GET.
Composition: `engines/planning/` — `goal_former.py` (drives→goals, deterministic), `action_selector.py` (goal→action score). Reads needs/agendas/oaths via `retrieval/`, writes goals via existing `graph/goal_service.py`, dispatches actions via `engines/interaction/dispatch`. No Neo4j or LLM in selection (LLM optional, phrasing only).
Architecture fit: new-file-add (new engine dir + one edge YAML). Net-new edge type → **DECISIONS entry**. Action vocabulary must be a `Literal`/Enum (no magic strings).
Prerequisite enablers: EXP-50 (affinity, for rival-targeting goals) is a soft dep; EXP-58 (proactive dialogue) consumes the selected intent. None hard-blocking.
Effort: L   Value: high   Business-fit: med
Risks / unknowns: combinatorial action explosion → cap action set + semaphore-bounded per-tick goal formation; determinism + RNG-seed logging required (CLAUDE.md Observability); avoid double-driving NPCs already moved by `routine` (define precedence in DECISIONS).
First slice: form **one** goal type — "satisfy most-decayed need" — and select move-to-need-location, reusing `routine` movement; prove an NPC walks to the tavern when "social" need is low, with seed logged.
Open questions: precedence between `routine` (schedule) and `planning` (goal) when they conflict → OPEN_QUESTIONS.

---

## STRONG (rank 4–7)

### EXP-52: Personal Reputation Propagation engine
Type: new-engine
Business rationale: Off-screen social simulation commitment (`BUSINESS_INTENT.md:36`) + "world changes opinions while player away". Gossip spreads *rumors* and faction-politics drifts *faction* standing, but a player's **personal reputation** (how NPC B feels about the player having never met them) never propagates through the social graph. This is what makes a reputation "precede" the player.
What it does: Per-tick engine that propagates a player's affinity/standing along `relates_to`/`member_of` edges with distance decay — if A trusts the player and A trusts B, B's baseline disposition toward the player nudges. Distinct from gossip (facts) and faction_politics (faction-level). Deterministic, seeded.
Current state: `has_reputation_with` (character→faction) + `gossip` + `faction_politics` exist; no *interpersonal* reputation diffusion. Partial overlap → narrowed to player-reputation diffusion only.
Graph/schema additions: reuse `relates_to`; optionally a cached baseline field:
```yaml
# extend base_nodes/character.yaml (new optional field, additive)
fields:
  player_reputation_baseline: { type: int, required: false, range: [0, 100] }
```
API surface: tick-only; surfaced via EXP-50's relationship GET.
Composition: `engines/reputation/` reads social edges via `retrieval/`, writes baseline via `graph/`. No LLM. Bounded by `MAX_CONCURRENT_TICKS` semaphore; must honor existing per-turn/windowed mutation caps (mutation layer).
Architecture fit: additive optional field on `character` = **schema change → DECISIONS entry**; otherwise new-file-add.
Prerequisite enablers: EXP-50 (affinity phases give the propagation source signal). Soft.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: feedback loops / runaway diffusion → decay + clamp + cap per tick; interaction with bounded-mutation audit log (must log propagated deltas too).
First slice: 1-hop propagation only, decay constant in YAML, behind a flag; eval: NPC never-met-player has nonzero disposition after a trusted intermediary.
Open questions: should propagation be symmetric with gossip distortion (reputation degrades over hops)? → OPEN_QUESTIONS.

### EXP-55: Player-Model / Theory-of-Mind engine — 🟡 DEFERRED (future expansion; via memories for now)
Type: new-engine
**RESOLVED 2026-06-05 (OQ-D6): do NOT add a `player_model` node now.** The player is already a `character`
node (`seed.py:658`, `is_player:true`, `player_demo`), so perceived trust/affection/fear, faction lean, and
known facts are already modeled via `relates_to` / `has_reputation_with` / `knows_about` (player as the other
endpoint), and reliability derives from the existing `PLEDGE` edge `is_active` + quest outcomes — no node
needed. **Second-order belief** ("what the NPC thinks the *player* knows/believes") is a good FUTURE expansion;
**for now it is expressed through memories.** The first-slice `reliability` signal (below) can still be built
deterministically and injected as context without any new node — schedule it opportunistically, not as a
near-term engine. The original node sketch is retained below for the future expansion only.
Business rationale: Implied agentic ambition (`BUSINESS_INTENT.md:59`) + retrieval-precision Phase 15: an NPC that models *who the player is to them* (playstyle, past betrayals, stated goals) retrieves more relevant memory and answers more in-character. Also the natural attribution sink for EXP-53's learned facts.
What it does: Maintains a per-(NPC, player) model node: inferred player disposition (aggressive/diplomatic), reliability (kept vs broken promises via `PLEDGE`), and a short "what this NPC expects the player to do" summary. Updated post-dialogue and post-quest. Feeds prompt context as a pooled (droppable) block.
Current state: player IS a `character` node; perceived state already expressible via existing edges. Only second-order belief + persisted inference is greenfield.
Graph/schema additions (FUTURE ONLY — not now):
```yaml
# base_nodes/player_model.yaml
node_type: player_model
fields:
  id: { type: str, required: true }
  npc_id: { type: str, required: true }
  player_id: { type: str, required: true }
  inferred_style: { type: str, required: true }   # Literal-backed enum in code
  reliability: { type: int, required: true, range: [0, 100] }
  summary: { type: str, required: false }
  updated_at_tick: { type: int, required: true }
```
API surface: admin GET for dashboard; engine-internal otherwise.
Composition: `engines/player_model/`; LLM optional for `summary` (prompt YAML), deterministic for `reliability` (from `oath`/quest outcomes). Reads via `retrieval/`, writes via `graph/`. Token-budget: summary is Tier-B (droppable first).
Architecture fit: new node type = **schema change → DECISIONS**; otherwise new-file-add.
Prerequisite enablers: EXP-53 (learned facts attach here); EXP-50 (affinity input). Soft.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: token budget pressure (must be Tier-B); privacy of inference is N/A single-tenant; risk of overfitting tone.
First slice: deterministic `reliability` only (from kept/broken oaths), injected into dialogue prompt; eval: NPC distrusts a player who broke an oath.
Open questions: one model per NPC-player pair vs one shared player profile? (single-player vs party) → OPEN_QUESTIONS.

### EXP-54: Player-Aware Drama Director engine
Type: new-engine
Business rationale: "Living off-screen world" commitment + Phase 14 agentic ambition (`BUSINESS_INTENT.md:36,59`). `events` generates world events and `story_pacing` *gates* them, but nothing **targets** drama at the current player's state (idle too long, quest stalled, relationship plateau). A director that injects a beat aimed at re-engaging the player is the classic "drama manager".
What it does: Per-tick reads player engagement signals (last interaction tick, open quests, affinity plateaus) and, within `story_pacing` severity budget, selects + injects a *targeted* event ("a rival NPC seeks the player out", "a quest deadline looms"). Deterministic selection over a YAML beat library; LLM optional for flavor text.
Current state: `events` (untargeted generation) + `story_pacing` (gating multipliers) exist; no player-aware targeting. Narrowed to the director layer on top.
Graph/schema additions: reuse `event`/`narrative_beat` nodes; optional `targets` edge `event→character`. (additive)
API surface: tick-only; emits beats on WS event stream.
Composition: `engines/director/` reads engagement via `retrieval/`, respects `story_pacing` WorldState multipliers (reads, does not write them), creates events via existing `events`/graph path. Composes *below* story_pacing's budget.
Architecture fit: new-file-add + optional edge YAML (**DECISIONS** if edge added). Must NOT edit `story_pacing` (OCP).
Prerequisite enablers: EXP-55 (engagement signal quality), EXP-51 (rival-seeks-player action). Soft.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: clashing with `story_pacing` budget (read-only on its multipliers); over-firing → cooldown in YAML; determinism + seed logging.
First slice: single beat — "idle N ticks → nearest NPC initiates" — gated by story_pacing severity; cooldown config; eval on idle trigger.
Open questions: does the director own engagement metrics or read them from metrics_snapshot? → OPEN_QUESTIONS.

---

## SPECULATIVE / LOWER-FIT (rank 8–9) — kept with caveats

### EXP-56: Localization / Multi-Language Output engine
Type: new-engine
Business rationale: Implied by "licensable to game studios" globally + buyer-facing compliance posture (`BUSINESS_INTENT.md:62`). A studio shipping in 8 languages needs NPC output localized. Currently only a prompt instruction touches language.
What it does: Post-generation language layer — either prompts the LLM in the target language or post-translates structured `response` text (NOT the structured action/expression fields). Per-world default language + per-request override.
Current state: none beyond `prompts/dialogue/system_v1.yaml` instruction. greenfield.
Graph/schema additions: none (config-level world language setting).
API surface: `language` field on dialogue request (capped Literal of supported locales); world default in config.
Composition: `engines/localization/` wraps the dialogue output; LLM via existing protocol or a translation adapter (new adapter file, OCP). Prompt strings in YAML.
Architecture fit: new-file-add (engine + prompt YAML + config key). No schema change.
Prerequisite enablers: none.
Effort: M   Value: low   Business-fit: med
Risks / unknowns: quality of small-model translation; structured fields must stay canonical (English enums); doubles LLM cost/latency per turn.
First slice: target-language *generation* (system prompt swap) for the `response` field only, one extra locale, behind config; eval round-trips meaning.
Open questions: translate vs generate-in-language; do learned facts (EXP-53) store original or localized? → OPEN_QUESTIONS.

### EXP-57: Voice / STT Input engine
Type: new-engine
Business rationale: Complements the existing `tts` engine for full voice loop; implied by immersion thesis. But the engine is a *backend middleware* — STT typically lives client-side in Unity/Unreal, weakening fit.
What it does: Accepts audio (or a client-side transcript) and produces the `player_message` string fed to dialogue. Mirrors `tts` adapter shape (`STTClientProtocol`, mock + real adapter).
Current state: none (grep for stt/whisper/transcribe empty). `tts` engine is the symmetric precedent.
Graph/schema additions: none.
API surface: `POST /v1/dialogue/{npc}/voice` (audio in) → same dialogue response; or accept transcript field.
Composition: `engines/stt/` adapter behind a protocol (OCP), output handed to existing `dialogue_handler`. No graph/LLM in STT itself.
Architecture fit: new-file-add (engine + protocol + adapters).
Prerequisite enablers: none.
Effort: M   Value: low   Business-fit: low
Risks / unknowns: audio upload size caps (security: input caps at boundary); most studios do STT client-side, so this may be redundant — likely better left to the SDK. Recommend **defer** unless a buyer asks.
First slice: accept a client transcript (no audio decode) and validate/cap it, proving the protocol seam; real STT adapter later.
Open questions: is STT in-scope for backend middleware at all, or an SDK concern? → OPEN_QUESTIONS (likely SDK).

---

## Dropped (one-line justification each)

- **Daily-life world-simulation tick** — already covered by `routine`+`need`+`mood`+`agenda`+`economy` per-tick engines; net-new not warranted (becomes EXP-51's consumer).
- **Generic "trade/economy" engine** — `economy`+`currency`+`interaction` already implement pricing, trade evaluation, and atomic transfer.
- **Crowd/clique formation** — `clique` (CliqueFormationEngine) already detects groups by affection.
- **Warfare engine** — `military` (battle resolution + resource yield) exists.
- **Faction reputation drift** — `faction_politics` already drifts faction standings; EXP-52 narrowed to *interpersonal* propagation only.
- **Multi-tenant world isolation** — forbidden by DEC-068; not proposed.

---

## Summary ranking

| Rank | EXP | Title | Effort | Value | Fit |
|------|-----|-------|--------|-------|-----|
| 1 ⭐ | EXP-53 | Dialogue-driven knowledge extraction | L | high | high |
| 2 ⭐ | EXP-50 | Relationship / affinity engine | S | high | high |
| 3 ⭐ | EXP-51 | NPC goal-formation & action-selection (GOAP) | L | high | med |
| 4 | EXP-52 | Personal reputation propagation | M | med | high |
| 5 | EXP-55 | Player-model / theory-of-mind | M | med | med |
| 6 | EXP-54 | Player-aware drama director | M | med | med |
| 7 | EXP-56 | Localization / multi-language output | M | low | med |
| 8 | EXP-57 | Voice / STT input | M | low | low |
