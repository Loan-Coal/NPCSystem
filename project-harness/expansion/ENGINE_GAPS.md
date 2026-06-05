# Engine Feature Gaps — Lens X1 (Existing-Engine Feature Gaps)

**Scope:** For each engine in `src/npc_engine/engines/` (+ `retrieval/`), what is missing,
shallow, or stubbed vs the product thesis and competitive bar in
`project-harness/expansion/BUSINESS_INTENT.md`. Read-only analysis; citations are real
`file:line`. Specs numbered EXP-10..EXP-49 (EXP-50+ reserved for the new-engines lens).

Headline domains (dialogue, emotion, gossip, memory, quest, relationship, retrieval) are
covered in depth; graveyard/niche engines (succession, clique, investigation, skill, oath,
treaty, military, faction_politics, agenda, need, mood, chapter, story_pacing, economy,
events, contracts, currency, idempotency, tts, interaction) are covered briefly at the end.

---

## DIALOGUE — `engines/dialogue/`

**Current state:** Functional request/response pipeline with degradation tiers, prompt
injection fencing, structured output, relation deltas, and TTS. Reactive only; no
player-specific long-term memory recall; relation deltas are raw and unaudited at the
dialogue boundary.

### EXP-10: Proactive / NPC-initiated dialogue (agentic loop)
Type: existing-engine-gap
Business rationale: Success criterion 2 "An NPC can be hailed proactively" and implied ambition "agentic NPCs that initiate, not just react" — Phase 14 (`BUSINESS_INTENT.md:59,75`; `ROADMAP.md:35-53`).
What it does: A tick-driven intent-formation loop that lets an NPC produce an unsolicited in-character line when conditions hold (player co-located + idle, unmet need, fresh memory/rumor, pending oath/quest). Emits a `proactive_line` over WebSocket so standing still in the world surfaces NPC speech.
Current state: Entirely absent. `grep proactive|initiate|unsolicited|hail` over `src/` returns nothing. `DialogueHandler.handle/stream` only respond to a `DialogueRequest` (`dialogue_handler.py:119,243`). No scheduler hook feeds dialogue.
Graph/schema additions: none required for v1 (read existing needs/memories/rumors). Optional `NPC -[:HAS_PENDING_UTTERANCE]-> Utterance{id,reason,created_tick}` to dedupe.
API surface: new WS push `proactive_line` on the existing NPC socket; new engine-internal `ProactiveDialogueEngine.run_tick(session, tick_id)`.
Composition: new engine in `engines/` reusing prompt_builder + llm_client + context_builder; driven by `scheduler/tick_scheduler`. Reads need/memory/rumor via existing graph services.
Architecture fit: add-by-new-file (`engines/proactive_dialogue/`), new scheduler registration. No edit to `dialogue_handler`. (ASSUMPTION: trigger gating is a deterministic rule engine, LLM only renders the line.)
Prerequisite enablers: EXP-13 (cleaner memory recall improves trigger quality) — soft. none hard.
Effort: L   Value: high   Business-fit: high
Risks / unknowns: spam/cadence control; per-NPC rate limit; cost of LLM per idle tick.
First slice: single deterministic trigger (player co-located ≥N ticks + NPC has unshared high-vividness memory) → one canned-or-LLM line over WS.
Open questions: cadence policy and budget per tick → OPEN_QUESTIONS.

### EXP-11: Player-specific long-term memory recall in dialogue
Type: existing-engine-gap
Business rationale: Core thesis "NPCs remember shared history" and "respond from what they actually know" (`BUSINESS_INTENT.md:22,35`). Anti-hallucination depends on surfacing the *right* prior interactions.
What it does: Surface the NPC's memories *of this specific player* (prior conversations, promises, slights) into the dialogue context, ranked by relevance to the current message — not just the global top-3 vividness memories.
Current state: `context_builder.py:204` fetches `get_memories_for_character(..., k=3)` — global to the NPC, not scoped to the speaking player, ranked only by the graph query's default order. Session store holds only recent turns in-process (`session_store.py`), lost on restart. Cross-conversation player history is not retrieved.
Graph/schema additions: edge `Memory -[:ABOUT_PLAYER]-> Player` (or reuse subject linkage). YAML sketch: `Memory.subject_ids: list[str]` participant tagging on creation.
API surface: engine-internal (context assembly); no route change.
Composition: extend memory recall in `retrieval/context_builder` + `graph/memory_queries`; consumed by dialogue unchanged.
Architecture fit: edits `context_builder` Tier A assembly + a new `graph/memory_queries` function — additive. Memory tagging at creation edits `MemoryEngine.create_from_arousal` (`memory_engine.py:30`).
Prerequisite enablers: EXP-13 (salience), EXP-30 (Tier A bounding so adding memories does not blow the budget).
Effort: M   Value: high   Business-fit: high
Risks / unknowns: player-id vs npc-id symmetry in memory subject tagging; back-compat for un-tagged memories.
First slice: tag new memories with the player_id present in the dialogue turn; retrieve player-scoped memories first, fall back to global.
Open questions: none.

### EXP-12: Relation-delta provenance & audit at the dialogue boundary
Type: existing-engine-gap
Business rationale: Commitment "bounded relation mutation with audit `delta_log`" and success criterion 10 "relation values cannot be griefed into extremes" (`BUSINESS_INTENT.md:47,83`).
What it does: Make the dialogue relation mutator never silently drop deltas and always write an audit record, so an integrator can trace why trust changed.
Current state: `relation_mutator.py` docstring + body: "Missing-edge errors are silently swallowed so the caller's response flow is not interrupted" — a swallow that drops legitimate first-contact relation changes and writes no audit. Conflicts with CLAUDE.md "Never swallow errors."
Graph/schema additions: none (delta_log already exists per FEATURES); ensure edge auto-create on first delta.
API surface: engine-internal.
Composition: `engines/dialogue/relation_mutator` → `mutation/` + `graph/graph_writer`.
Architecture fit: edits `relation_mutator.py` (single module bug-fix tier); pair with mutation-layer ensure-edge.
Prerequisite enablers: none.
Effort: S   Value: med   Business-fit: high
Risks / unknowns: auto-creating edges may change first-turn relation semantics; needs a test.
First slice: create-edge-then-apply on `RelationEdgeNotFoundError` instead of swallow; assert delta_log row written.
Open questions: none.

---

## EMOTION / MOOD — `engines/emotion/`, `engines/mood/`

**Current state:** Fixed 2-axis VAD (valence/arousal) with a 5-label coarse derivation,
flat linear decay, in-memory store (not persisted across restart). No personality
modulation, no extensibility seam.

### EXP-13: `EmotionModelProtocol` + personality-modulated emotion (OCP seam)
Type: existing-engine-gap
Business rationale: Implied ambition "OCP-clean expansion seams … no `EmotionModelProtocol`" flagged as a missing seam (`BUSINESS_INTENT.md:65`; FINAL_REVIEW). Constraint: emotion models are add-by-new-file (`BUSINESS_INTENT.md:94`).
What it does: Introduce a small `EmotionModelProtocol` so a richer emotion model (e.g. OCC appraisal, personality-weighted reactivity) can be added as a new file without editing the VAD updater. Lets two NPCs react differently to the same event based on traits.
Current state: `emotion_state.py:16` hard-codes VAD; `emotion_updater.py` hard-codes shock divisors/caps as module constants (`_SHOCK_VALENCE_DIVISOR` etc., lines 17-20). No protocol exists (`grep EmotionModelProtocol` → nothing). `derive_label` is a closed 5-branch if-chain (`emotion_state.py:27`).
Graph/schema additions: none for the protocol; a model variant may read existing `Trait` nodes.
API surface: engine-internal; `/npc/{id}/state` shape unchanged for VAD-compatible models.
Composition: protocol in `engines/emotion/`; injected into `EmotionUpdater` via `__init__` (DIP).
Architecture fit: add `EmotionModelProtocol` + refactor updater to delegate; default impl = current VAD. New models = new files.
Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: keeping label-derivation back-compat for existing demo expectations.
First slice: extract the protocol + wrap current logic as `VadEmotionModel`; inject; no behavior change. Then add a trait-modulated reactivity multiplier as a 2nd file.
Open questions: which appraisal model to standardize on → OPEN_QUESTIONS.

### EXP-14: Persistent emotion state (survive restart / multi-tick coherence)
Type: existing-engine-gap
Business rationale: Thesis "persistent … emotional state per NPC" (`BUSINESS_INTENT.md:35`); README "What's next" Redis-backed emotion store (`BUSINESS_INTENT.md:64`).
What it does: Persist emotion state so a fresh-checkout reboot (DEC-068 per-studio deployment) does not reset every NPC to neutral.
Current state: `emotion_store.py` is purely in-memory (`self._states: dict`, docstring "in-memory"). Lost on process restart; `session_store.py` likewise "Does NOT persist sessions across process restarts."
Graph/schema additions: persist VAD onto the `NPC`/`Character` node or an `EmotionState` node. YAML sketch: `Character.valence:int, Character.arousal:int, Character.mood_label:str, Character.mood_updated_tick:int`.
API surface: engine-internal; optional `GET /npc/{id}/emotion` already implied by npc_state route.
Composition: emotion store gains a graph-backed write-through via `graph/`; reads stay hot in-memory.
Architecture fit: needs DECISIONS approval (graph node schema change — CLAUDE.md "Asking before doing").
Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: write amplification per tick; lock discipline already present.
First slice: snapshot-on-shutdown + load-on-boot before full write-through.
Open questions: Redis vs Neo4j as the durable store (README implies Redis) → OPEN_QUESTIONS.

---

## GOSSIP — `engines/gossip/`

**Current state:** Deterministic seeded distortion with 4 fixed types, faction-hostility
amplification, secret propagation, emotion shock. Distortion application is a closed
if-chain with hardcoded English templates; not content-selective; not OCP-extensible.

### EXP-15: Distortion strategy protocol — open the closed 4-place if-chain (L7-01)
Type: existing-engine-gap
Business rationale: Constraint "distortion types added by creating a new file, never editing a closed engine file" (`BUSINESS_INTENT.md:94`); missing seam flagged as a competitive/extensibility gap (`BUSINESS_INTENT.md:65`).
What it does: Replace the fixed `omission/exaggeration/role_swap/timeline_shift` if-chain with a registry of distortion strategies so a studio can add a new distortion (e.g. `attribution_shift`, `severity_inflation`) by dropping in a file.
Current state: `gossip_distort.py:92-103` `_apply_template` is a 4-branch if-chain returning hardcoded English strings; selection is `distortion_types[seed % len]` (`gossip_distort.py:163`). Adding a type requires editing this closed function.
Graph/schema additions: none.
API surface: engine-internal.
Composition: strategy protocol + registry in `engines/gossip/`; `gossip_distort` dispatches via registry.
Architecture fit: add `distortion_strategy.py` protocol + per-strategy files; refactor `_apply_template` to dispatch. New types = new files.
Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: determinism must be preserved across registry ordering (seed→strategy mapping must be stable).
First slice: extract the 4 existing branches into 4 strategy callables behind a registry keyed by stable name; identical output.
Open questions: none.

### EXP-16: Belief/secret-selective, prompt-driven distortion content
Type: existing-engine-gap
Business rationale: Commitment "deterministic, replayable gossip distortion" with believable content (`BUSINESS_INTENT.md:48`); thesis "NPCs … change opinions" off-screen (`BUSINESS_INTENT.md:36`). Hardcoded English templates break immersion and violate "no prompt strings outside `prompts/`."
What it does: Make distorted summaries reflect the *content* of the rumor and the receiver's existing beliefs (a believer exaggerates, a skeptic omits) and render distortion text from versioned YAML prompts rather than hardcoded f-strings.
Current state: `_apply_template` emits constant strings like `"It was utterly catastrophic: {summary}"` and `"Long ago, {summary}"` (`gossip_distort.py:94-101`) — content-blind and English-only, embedded prompt-like strings outside `prompts/`. No gossip prompt dir exists (`ls prompts/gossip` → empty).
Graph/schema additions: none (reads existing `BELIEVES_RUMOR.confidence`).
API surface: engine-internal.
Composition: distortion templates move to `prompts/gossip/*.yaml`; optionally an LLM-rendered distortion path in `engines/gossip/` (LLM allowed in engines layer only).
Architecture fit: builds on EXP-15 registry; pure-deterministic strategies stay pure (template text from YAML); an LLM strategy is a new file.
Prerequisite enablers: EXP-15.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: LLM distortion sacrifices determinism — keep it opt-in; default stays seeded/templated.
First slice: move the 4 template strings into `prompts/gossip/distortion.yaml`; select by receiver belief confidence bucket.
Open questions: deterministic-template vs LLM-rendered default → OPEN_QUESTIONS.

---

## MEMORY / MEMORY CONSOLIDATION — `engines/memory/`, `engines/memory_consolidation/`

**Current state:** Memory formation only on arousal>70 with flat fixed vividness; daily
decay is a single fixed subtraction; consolidation summarizes recent session turns via LLM.
No salience/relevance decay curve, no forgetting policy, no emotional-charge-weighted decay.

### EXP-17: Salience-weighted forgetting curve (decay shaped by charge + recency + recall)
Type: existing-engine-gap
Business rationale: Thesis "persistent memory" that feels human; anti-hallucination depends on which memories survive to be retrieved (`BUSINESS_INTENT.md:35,74`).
What it does: Replace flat vividness decay with a salience curve: emotionally-charged and recently-recalled memories decay slower; trivial ones fade and eventually drop below a retrieval floor (true forgetting). Surfaces a `salience` used by retrieval ranking.
Current state: `MemoryEngine.decay_vividness` calls `decay_all_vividness` (flat amount for all; `memory_engine.py:62`). Formation uses fixed `_HIGH_AROUSAL_VIVIDNESS=80` regardless of event (`memory_engine.py:19,51`). No recall-reinforcement, no charge-weighted decay, no forget threshold.
Graph/schema additions (RESOLVED OQ-D4): `memory.yaml` **already has** `vividness`, `emotional_charge`, **and `last_recalled_at`** — so the only genuinely new fields are **`recall_count: int`** and a **`never_forget: bool`** (pinned) flag on plot-load-bearing memories. `salience` is *computed* (`f(vividness, |emotional_charge|, recency, recall_count)`), not stored.
API surface: engine-internal.
Composition: `engines/memory` computes salience + applies the curve; `retrieval/context_builder` ranks the pool (EXP-30) by salience; recall events bump `recall_count` + `last_recalled_at`. `never_forget` memories are exempt from the forget floor (symmetric with EXP-30's `pinned`).
Architecture fit: additive engine change + two optional `memory.yaml` fields (`recall_count`, `never_forget`) — minor schema add.
Prerequisite enablers: EXP-30 (pool ranking consumes salience); EXP-11 (recall path supplies reinforcement signal) — soft.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: tuning the curve; forgetting must mark below-floor, never destroy graph nodes; `never_forget` must be set on quest-critical knowledge.
First slice: charge-weighted decay rate (high `emotional_charge` decays slower), reusing existing fields — no schema change; add `recall_count`/`never_forget` next.
Open questions: RESOLVED — OQ-D4. Target half-life per charge band is a tuning detail.

### EXP-18: Memory formation beyond the arousal threshold (semantic salience)
Type: existing-engine-gap
Business rationale: "NPCs remember shared history" — promises, names, agreements are low-arousal but high-importance (`BUSINESS_INTENT.md:22`).
What it does: Form memories for narratively important low-arousal events (a promise made, a name learned, a quest accepted) — not only when arousal>70.
Current state: `MemoryEngine.create_from_arousal` is the *only* formation path and returns `None` unless `arousal > 70` (`memory_engine.py:51`). A calm but important agreement is never remembered.
Graph/schema additions: none (reuse Memory); optional `Memory.kind:Literal["episodic","commitment","fact"]`.
API surface: engine-internal.
Composition: new formation triggers in `engines/memory` invoked from dialogue action resolution (e.g. on `accept_quest`, on promise actions).
Architecture fit: add a `create_from_event(kind=...)` method (additive) + call sites; OCP-clean if formation policies are pluggable.
Prerequisite enablers: EXP-17 (salience model gives non-arousal memories a vividness/salience).
Effort: M   Value: med   Business-fit: high
Risks / unknowns: deciding what counts as "important" without an LLM call per turn (cost).
First slice: form a `commitment` memory whenever a quest is accepted (deterministic trigger).
Open questions: none.

---

## QUEST / QUEST GENERATION — `engines/quest/`, `engines/quest_generation/`

**Current state:** Solid lifecycle (offer→accept→objective→complete→reward) with atomic
reward transfer; generation is template + LLM slot-fill. Objectives are flat
(deliver/kill/visit/talk); no branching, no consequence chains, no failure-state quests.

### EXP-19: Branching quests & consequence chains
Type: existing-engine-gap
Business rationale: Living-world thesis + "win AND lose reachable game loop" (`BUSINESS_INTENT.md:50`); competitive bar for narrative NPCs implies choices with downstream effects.
What it does: Allow a quest to branch on player choice/objective outcome and chain consequences (completing/failing quest A unlocks B, shifts faction standing, mutates relations). Today quests are isolated linear records.
Current state: `quest/models.py:31` objective_type is a flat `Literal["deliver","kill","visit","talk"]`; `QuestStateRecord.status` is a plain string (`models.py:73`); `quest_lifecycle_engine.py` transitions are linear (offer→accept→update_objective→evaluate_completion→apply_rewards). No `NEXT_QUEST`/`UNLOCKS`/branch edges; `quest_generation_engine` selects one template and fills slots (`quest_generation_engine.py:253`).
Graph/schema additions: `Quest -[:UNLOCKS{on:Literal["complete","fail"]}]-> Quest`; `Quest -[:HAS_BRANCH]-> QuestBranch{choice_id,outcome}`.
API surface: lifecycle gains a branch-resolution step; possibly new `POST /quest/{id}/choose`.
Composition: extends `quest_lifecycle_engine`; consequence effects fan out to faction_politics / relation mutation services.
Architecture fit: needs DECISIONS approval (quest/edge schema); engine additions are OCP-friendly if outcome effects are a registry.
Prerequisite enablers: none hard; pairs with EXP-21.
Effort: L   Value: high   Business-fit: high
Risks / unknowns: status field should become an enum first (see EXP-20); branch authoring UX.
First slice: `UNLOCKS{on:"complete"}` edge — completing A auto-offers B. No player choice yet.
Open questions: branch authoring via YAML templates vs LLM → OPEN_QUESTIONS.

### EXP-20: Quest status as enum + explicit fail/expire states
Type: existing-engine-gap
Business rationale: Constraint "Enums/Literal for fixed sets" (`BUSINESS_INTENT.md:96`); "win AND lose reachable" requires a modeled fail state (`BUSINESS_INTENT.md:50`).
What it does: Model quest status as a `Literal`/enum with `offered/accepted/active/completed/failed/expired` and lifecycle transitions for failure and timeout, so a quest can actually be lost.
Current state: `QuestStateRecord.status: str` (raw string, `models.py:73`) — violates the fixed-set rule and admits no validated fail/expire transition. Lifecycle engine has no `fail_quest`/`expire_quest`.
Graph/schema additions: none (status already stored); enum is in-code.
API surface: engine-internal; transition meta unchanged.
Composition: `quest_lifecycle_engine` gains `fail_quest`/`expire_quest`; deadline check can be tick-driven.
Architecture fit: edits `models.py` (type tightening) + `quest_lifecycle_engine` (additive transitions).
Prerequisite enablers: none. Enabler for EXP-19 (branch-on-fail).
Effort: S   Value: med   Business-fit: high
Risks / unknowns: migrating existing string statuses; back-compat read.
First slice: introduce the enum + a `fail_quest` transition with audit event.
Open questions: none.

### EXP-21: Dynamic, world-state-aware quest generation
Type: existing-engine-gap
Business rationale: Implied ambition of a living world that *generates its own goals*; off-screen simulation (`BUSINESS_INTENT.md:36,59`).
What it does: Generate quests from current world/faction/need state and recent events (a war just started → a "deliver supplies" quest appears) rather than only static archetype templates filled by slot-LLM.
Current state: `quest_generation_engine._select_template` picks from a static `list[QuestTemplateRecord]` by archetype (`quest_generation_engine.py:253`); triggers exist (`event_quest_trigger.py`, `need_quest_trigger.py`) but still map to fixed templates. No emergent objective synthesis.
Graph/schema additions: none beyond EXP-19 if chaining.
API surface: engine-internal (driven by scheduler/event triggers).
Composition: extend the existing trigger modules; reuse slot validator for graph-grounding.
Architecture fit: add new trigger files (OCP); reuse generation pipeline.
Prerequisite enablers: EXP-20 (clean states); EXP-19 (chains) for richer output.
Effort: L   Value: med   Business-fit: med
Risks / unknowns: grounding generated objectives in real graph entities (slot_validator already helps); hallucinated targets.
First slice: an event-driven trigger that instantiates a supply/escort template seeded by the triggering event's entities.
Open questions: none.

---

## RELATIONSHIP / AFFINITY — *(no dedicated engine — gap)*

**Current state:** There is **no relationship/affinity engine.** Relations exist only as raw
per-axis integers (trust/fear/affection) mutated by dialogue deltas and clamped. There is no
derived relationship tier, no decay-toward-baseline, no relationship-driven behavior gating.

### EXP-22: Relationship/affinity engine (derived standing tiers + decay)
Type: existing-engine-gap
Business rationale: Headline thesis "persistent relationships per NPC" (`BUSINESS_INTENT.md:35`). A studio buying "relationships" expects more than three clamped integers.
What it does: Derive a relationship standing (e.g. hostile/wary/neutral/friendly/devoted) from the trust/fear/affection vector, decay relations toward a personality baseline over time, and expose standing for behavior gating (who an NPC will trade with, share secrets with, defend).
Current state: `RelationDeltas` has only `trust/fear/affection` each `[-15,15]` (`dialogue_models.py:48-53`); deltas applied raw via `relation_mutator`. `grep affinity|RelationshipEngine` → nothing. Affinity *is* read ad hoc by clique detection but no engine derives standing for general use.
Graph/schema additions: none required (derive from existing edge props); optional `KNOWS{standing:str}` cached field.
API surface: optional `GET /npc/{id}/relationship/{other_id}` returning standing; otherwise engine-internal.
Composition: new `engines/relationship/` reads relation edges via graph service; consulted by gossip (secret-sharing gate), dialogue (tone), interaction (trade gate).
Architecture fit: add-by-new-file engine; consumers call it instead of inlining trust thresholds (kills magic-number `if trust > N` smells).
Prerequisite enablers: none.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: defining standing bands without re-introducing magic numbers (must be config/enum).
First slice: pure `derive_standing(trust,fear,affection) -> Standing` enum + a `/relationship` read route; no decay yet.
**RESOLVED 2026-06-05:** **5 bands** on a composite standing score `standing = clamp(trust + affection − fear, −100, 100)` (a named formula, tunable later — the goal is to *have* bands and test them, not to find optimal values):
`HOSTILE [−100,−50) · WARY [−50,−15) · NEUTRAL [−15,15] · FRIENDLY (15,50] · ALLIED (50,100]`
(`Standing` enum + the cutoffs as `UPPER_SNAKE` module constants). **Consumer refactor order: gossip first** (secret-sharing / will-I-repeat-to-you gate), **then dialogue** (tone) — replacing inline `if trust > N` thresholds in those order. Bands/cutoffs are config so they can be tuned without code change.

---

## RETRIEVAL — `retrieval/`

**Current state:** Tiered context (Tier0 fixed / TierA non-compressible / TierB,C vector +
compressible) with cross-encoder reranking and budget enforcement. Tier A is non-compressible
and hard-fails when oversized (ISSUE-059). Retrieval quality is never measured (no precision@k).

### EXP-30: Context model — pinned-core + ranked pool (DEC-070; supersedes ISSUE-059 fix) ⭐ KEYSTONE
Type: existing-engine-gap
**RESOLVED 2026-06-05 (DEC-070).** Reframed from "trim Tier A" to a clean two-class model.
Business rationale: Success criterion 6 "degradation is invisible to the player"; ISSUE-059 currently degrades knowledge-heavy NPCs to canned (`BUSINESS_INTENT.md:79`).
What it does: Collapse the tier-A/B/C budget model into **two classes**: (1) a tiny **pinned set** that is never dropped — `world`, `emotion`, persona, the **session window**, `active_quest` — each carrying an explicit `pinned: bool` flag; (2) a single **ranked pool** of everything else (memories, beliefs, goals, items, secrets, obligations, knows_about facts), filled by `priority × relevance` until the budget is hit, dropping from the bottom. A "Tier-A exceeded" failure becomes impossible because the only un-droppable set is small and **bounded by construction** (persona + a windowed session, not an accumulating fact list).
Current state: `context_budget_enforcer.py:76-83` raises `ContextBudgetError` when `tier_a_tokens > tier_a_budget`; unbounded categories (beliefs/goals/memories/secrets) are appended to `tier_a_raw` (`context_builder.py:341-360`) and the never-trim tier therefore overflows. Every item already carries a `priority` (`context_builder.py:272-359`) — tiers were just coarse priority bands.
Graph/schema additions: none. Adds a `pinned: bool` field to the `ContextItem` model (in-memory, not graph).
API surface: engine-internal.
Composition: `retrieval/context_builder` tags pinned items; `retrieval/context_budget_enforcer` becomes "include all pinned, then fill the ranked pool by `priority × relevance` until budget". Replaces the tier-A/B/C split.
Architecture fit: edits `context_builder` + `context_budget_enforcer` (two retrieval modules); preserves and strengthens the "never drop persona/world" invariant by making it explicit.
Prerequisite enablers: none. **Keystone** — enabler for EXP-11, EXP-17, EXP-53, EXP-81, EXP-32, EXP-10.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: the session window must stay bounded (last-N turns) so even the pinned set can't exceed budget; the relevance scorer must be cheap enough to run per turn.
First slice: introduce `pinned` flag + the two-class fill on the current item set; assert pinned-set tokens are bounded for a high-knowledge NPC fixture.
**Ordering (RESOLVED 2026-06-05):** **v1 orders the pool by `priority` only** (simplest, deterministic). The existing relevance signal (`retrieval/context_relevance_engine.py` / `context_scoring.py`) is wired in as an **immediate fast-follow** to become the `× relevance` factor — the long-term target is `priority × relevance`, but the keystone ships priority-only so EXP-30 isn't blocked on relevance tuning.
Open questions: RESOLVED — see OPEN_QUESTIONS OQ-D1 / DEC-070.

### EXP-31: Retrieval-quality evaluation harness (precision@k / recall)
Type: existing-engine-gap
Business rationale: Implied ambition / success criterion 3 "retrieval returns the right memories — precision@k/recall against a labeled relevant-set, one-command headline metric" — Phase 15 (`BUSINESS_INTENT.md:60,76`; `ROADMAP.md:55-70`).
What it does: A labeled relevant-set per query + an eval that reports precision@k / recall / MRR for the retrieval stack, surfaced as a single make target.
Current state: `grep precision@|recall@|relevant_set|labeled` over `src/ tests/ e2e/` returns only an unrelated chapter_engine hit. The full stack (embedding_index, cross_encoder_reranker, subgraph_retriever) exists but only tone is judged. No retrieval metric exists.
Graph/schema additions: none (eval fixtures, not graph).
API surface: none; new `make eval-retrieval` + eval module under existing evals.
Composition: eval harness drives `retrieval/` against seeded eval worlds (village/tavern) with hand-labeled relevant nodes.
Architecture fit: new eval files (test/eval layer); no engine edits.
Prerequisite enablers: none. Strongly complements EXP-30 (proves trimming keeps the right items).
Effort: M   Value: high   Business-fit: high
Risks / unknowns: building/maintaining the labeled set; no committed precision target (open question in BUSINESS_INTENT).
First slice: 20 labeled queries on the village world → precision@5 + recall printed by one command.
Open questions: target precision@k number → OPEN_QUESTIONS (already flagged `BUSINESS_INTENT.md:106`).

### EXP-32: Measured anti-hallucination eval (fail on fallback/deflection)
Type: existing-engine-gap
Business rationale: Success criterion 1 "NPCs never assert facts they don't know — must be *measured* not asserted; eval must FAIL on empty/fallback/synonym/refusal, not pass on deflections" (SEV-01) (`BUSINESS_INTENT.md:39,74`).
What it does: An eval battery that asks NPCs about facts they do and do not know and scores a hallucination rate, treating canned/refusal answers to *known* facts as failures and any asserted *unknown* fact as a failure.
Current state: anti-hallucination is asserted, not measured (SEV-01, `BUSINESS_INTENT.md:39`). Dialogue degradation (`degradation.py`) and the demo gossip path exist but no eval distinguishes "correctly declined" from "wrongly deflected." `make eval-llm-demo` judges tone, not factual grounding.
Graph/schema additions: none.
API surface: none; eval module + make target.
Composition: eval drives dialogue against seeded worlds with known/unknown fact probes; reuses LLM-judge infra under `prompts/eval/`.
Architecture fit: new eval files; no engine edits (but may surface EXP-30 as the fix when failures cluster on knowledge-heavy NPCs).
Prerequisite enablers: EXP-30 (so knowledge-heavy NPCs are not auto-failing via canned degradation).
Effort: M   Value: high   Business-fit: high
Risks / unknowns: judging "synonym" answers; defining the known/unknown probe set per world.
First slice: 10 known + 10 unknown probes on captain_sorn (`northern_war_begins`) → hallucination-rate number.
Open questions: target hallucination rate → OPEN_QUESTIONS.

---

## NICHE / GRAVEYARD ENGINES (brief)

These are mostly deterministic tick engines that are functionally narrow. Material gaps only:

### EXP-40: Interaction dispatch trade path is a stub
Type: existing-engine-gap
Business rationale: Structured dialogue `action` must drive real interactions (trade) (`BUSINESS_INTENT.md:40`); economy engine exists but is not wired through dispatch.
Current state: `engines/interaction/dispatch.py:30` `_stub_handler` returns a placeholder `InteractionState`; quest path is implemented (`quest_handler.py`) but trade/negotiation dispatch is stubbed despite a full `economy` engine and `NegotiationStore` existing.
Graph/schema additions: none. API surface: engine-internal. Composition: wire `dispatch_interaction` → economy/negotiation. Architecture fit: replace stub with real handler (additive). Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: negotiation state lifecycle. First slice: route `propose_trade` action to economy offer evaluation. Open questions: none.

### EXP-41: Mood/need/faction/agenda engines lack player-visible surfacing & coupling
Type: existing-engine-gap
Business rationale: "World runs off-screen" is sellable only if its effects surface in dialogue/behavior (`BUSINESS_INTENT.md:36,80`).
Current state: `mood_contagion_engine`, `need_decay_engine`, `faction_politics`, `agenda_engine` each `run_tick` and write graph state, but their outputs are weakly fed back into dialogue context or proactive behavior (need state is not a dialogue trigger; mood contagion writes via `mood_queries` but EmotionStore is the dialogue source — possible divergence). These are simulation engines whose results are under-consumed.
Graph/schema additions: none. API surface: engine-internal. Composition: feed need/mood/standing into context_builder Tier A and EXP-10 triggers. Architecture fit: additive reads. Prerequisite enablers: EXP-10, EXP-22, EXP-30.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: EmotionStore vs graph mood divergence (worth an ISSUE). First slice: surface unmet-need as a dialogue Tier A item. Open questions: reconcile EmotionStore vs `mood_queries` source of truth → OPEN_QUESTIONS.

### EXP-42: Graveyard engines (succession, clique, investigation, skill, oath, treaty, military, chapter, story_pacing, contracts) — depth/coverage thin
Type: existing-engine-gap
Business rationale: Breadth-over-depth risk; these dilute the headline value proposition (memory/relationship/emotion) (`BUSINESS_INTENT.md:35`).
Current state: each is a single-purpose deterministic tick engine (e.g. `succession` grants vacant titles to heirs; `clique` detects affection clusters; `investigation` Phase 7.1 detective; `military` resolves battles; `story_pacing` writes pacing multipliers). They are shallow simulations with no eval coverage tying them to buyer value, and they expand surface area faster than the headline domains mature. Recommend treating as DEMO-tier content, not core middleware, until headline gaps (EXP-10..32) close.
Graph/schema additions: none. API surface: none. Composition: n/a (advisory). Architecture fit: n/a. Prerequisite enablers: n/a.
Effort: S (decision, not code)   Value: low   Business-fit: low
Risks / unknowns: sunk-cost; some may be demo-critical (village/tavern eval worlds use faction/military). First slice: tag each as core vs demo-tier in ROADMAP. Open questions: which graveyard engines are demo-load-bearing → OPEN_QUESTIONS.

---

## Cross-engine themes (for the feasibility lens)

1. **Agentic loop is the single biggest missing capability** (EXP-10) — the product promises a living, initiating world; today everything is reactive or fixed-tick simulation with no NPC-initiated player-facing output.
2. **Memory is the shallowest headline domain** (EXP-11, EXP-13, EXP-17, EXP-18) — formation is arousal-gated, decay is flat, recall is global-not-player-scoped, no forgetting curve. This directly undercuts the "persistent memory + anti-hallucination" thesis.
3. **Measurement gaps gate the sale** (EXP-31, EXP-32) — both anti-hallucination and retrieval quality are asserted, not measured; these are buyer-facing success criteria with no number.
4. **OCP seams are missing exactly where the docs promise add-by-new-file** (EXP-13 emotion, EXP-15 gossip distortion).
5. **ISSUE-059 (EXP-30) is a live degradation failure** — the more an NPC knows, the more likely it collapses to canned, which is the opposite of the value proposition.
