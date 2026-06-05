# FEASIBILITY.md — Lens X3 (Architecture & Feasibility Fit)

> **Resolutions applied 2026-06-05** (see `OPEN_QUESTIONS.md` §A, DEC-070/071/072) — these override the
> verdicts below where they differ:
> - **EXP-30** (KE-1): reframed to **pinned-core + ranked pool** (DEC-070). Still edits `context_builder.py`
>   + `context_budget_enforcer.py`; no schema. Adds an in-memory `pinned: bool` field.
> - **EXP-53 / KE-2**: **no `LEARNED_FROM` edge, no 2nd LLM pass** (DEC-072). Single-pass `learned_facts`
>   output → existing `BELIEVES` edge + 3 optional provenance fields on `believes.yaml`. Drops **L → M**.
> - **EXP-50**: confirmed **schema-free** (reuses `event` node for history; no `relationship_event` node).
> - **EXP-55**: **deferred** — player is already a `character` node, so no `player_model` node now; second-order
>   ToM via memories later.
> - **EXP-17**: only new fields are `recall_count` + `never_forget` (`memory.yaml` already has `last_recalled_at`).
> - **EXP-51**: precedence uses existing `goal.urgency` vs routine — **no schema, no LLM threshold**.
> - **EXP-93 / OQ-D7**: bribe → existing `HAS_REPUTATION_WITH` edge (confirmed). No schema.
> - **KE-5 / EXP-87**: `PART_OF` edge + `location_writer.py` **APPROVED** (DEC-071).
> - **Dropped**: EXP-56 (localization), EXP-57 (voice/STT).
> - **Reprioritized**: dialogue + gossip are the focus; gossip mechanics (EXP-15/16) pulled into the showcase phase.

**Mode:** READ-ONLY. Assesses each candidate expansion against the *current* architecture: does it land as a new-file add through an existing seam (YAML type_registry, OCP registry, Protocol + DI composition root in `api/dependencies.py`), or does it require editing a closed module / a graph-schema or layer-rule change (→ human DECISIONS call per `project-harness/CLAUDE.md` "Asking before doing")? Citations are real `file:line`. DEC-068 single-tenant respected throughout — no candidate below introduces a `world_id`.

**Seam-reality grounding (verified, not assumed):**
- **YAML type_registry is genuinely pure-additive at the *extension* layer.** `extension_loader.py:34-41` globs+validates extension docs; `registry.py:40-47` merges base + custom node/edge maps via `merge_registry`. BUT the `base_nodes/`+`base_edges/` directories are the *base contract* — adding a file there (e.g. `learned_from.yaml`, `goal_targets.yaml`) is a **graph edge/node schema addition**, which CLAUDE.md "Asking before doing" classifies as a stop-and-ask. The friction-free path is a *game-schema extension* YAML, not a new base file. This distinction drives every "schema call" verdict below.
- **OCP registry seam for engines = constructor-injected Protocol via `api/dependencies.py` (sole composition root, DIP-strict).** `base_engine.py:14-23` is a structural `run_tick` Protocol only; each new engine is a new dir injected at the composition root. New engines are clean new-file adds *as long as* they need no new base-schema edge.
- **L7-01 confirmed:** `gossip_distort.py:93-103` (`_apply_template` 4-branch if-chain) + `:162-163` (hardcoded `distortion_types` list). Closed.
- **L7-06 confirmed:** `emotion_updater.py:16-19` hardcoded shock constants; no `EmotionModelProtocol`; VAD baked into `emotion_state.py`.
- **EXP-30/ISSUE-059 confirmed:** `context_budget_enforcer.py:78-84` hard-raises on Tier A overflow; Tier A carries `priority` but is never priority-trimmed (only B/C are, `:139-144`).
- **L7-02 confirmed:** no `location_writer.py`; `CONNECTS_TO` exists (`location_graph_queries.py:20-29`) but no `PART_OF` in `base_edges/`.
- **EXP-53 confirmed:** `dialogue_handler.py:179` writes arousal memory only; no `KNOWS_ABOUT`/belief write path.
- **EXP-50 confirmed:** `relates_to.yaml:11-12` already declares `relationship_phase`+`phase_started_at_tick` (`required: false`) — populating them is **not** a schema change.

---

## 1. Per-candidate feasibility table

| ID | Architecture-fit verdict | Effort | Prerequisite enablers |
|----|--------------------------|--------|-----------------------|
| **EXP-50 / EXP-22** (affinity engine — *reconciled, see note*) | **New-file-add** via engine seam + `phase_rules_loader` YAML. Fills the *existing* `relates_to.yaml:11-12` dead fields → **no schema call** for the core. Optional `relationship_event` audit node = schema call (defer). | **S** | None (scalars already populated by `relation_mutator`). |
| **EXP-30** (bounded Tier A) | **Edits one closed module:** `context_budget_enforcer.py:78-84` (both `enforce_context_budget` and `fill_to_budget:209-217`). Priority-ordered Tier-A trim before raising. Self-contained, preserves Tier0/session non-droppable invariant. No schema, no layer change. | **M** | None. Requires a named non-droppable Tier-A sub-core constant (DEC-style choice, not a schema call). |
| **EXP-31** (retrieval precision@k eval) | **New-file-add** in eval/test layer + `make eval-retrieval`. Zero engine edits, zero schema. Pure additive harness over seeded worlds. | **M** | None. |
| **EXP-32** (anti-hallucination eval) | **New-file-add** eval harness reusing `prompts/eval/` LLM-judge infra. No engine edits, no schema. | **M** | EXP-30 (soft — else knowledge-heavy NPCs auto-fail via canned degradation; see keystone). |
| **EXP-17** (salience forgetting curve) | **Hybrid.** First slice (charge-weighted decay, reusing existing `emotional_charge`) edits `memory_engine.py` only — additive, no schema. Full version needs `Memory.salience/last_recalled_tick/recall_count` → **schema call**. | **M** | EXP-30 (so added Tier-A memories don't blow budget); EXP-11 recall path (soft). |
| **EXP-52** (reputation propagation) | **New-file-add** engine (`engines/reputation/`) reading `relates_to`/`member_of`, semaphore-bounded. Reuses existing edges. Optional cached `character.player_reputation_baseline` field → **schema call** (additive optional field). Must route deltas through existing mutation-layer audit. | **M** | EXP-50 (affinity source signal, soft). |
| **EXP-55** (player-model / theory-of-mind) | **New engine** but requires a net-new `player_model` base node → **schema call**. First slice (deterministic `reliability` from oath/quest outcomes, injected as Tier-B) can run engine-side; the persisted node is the schema gate. | **M** | EXP-53 (learned facts attach), EXP-50 (affinity input) — both soft. EXP-30 (Tier-A pressure). |
| **EXP-10** (proactive dialogue) | **New-file-add** engine (`engines/proactive_dialogue/`) + new scheduler registration + **new WS push** `proactive_line`. Reuses prompt_builder/llm_client/context_builder; does **not** edit `dialogue_handler`. v1 needs no schema. The WS-push + scheduler hook is an **API-surface addition** (public interface — stop-and-ask, but additive not breaking). | **L** | EXP-30 (knowledge-heavy NPCs must not go canned mid-proactive); cadence/budget policy (open question). EXP-51 optional (intent source). |
| **EXP-53** (dialogue-driven knowledge extraction) | **New engine + new graph sub-writer + new prompt YAML**, BUT a new `LEARNED_FROM` base edge → **schema call**. Also a *second LLM pass* per turn and a new `graph/knowledge_writer.py` (graph-owned, session-injected). Validator + Pydantic parser are clean new files. The hook into `dialogue_handler` after `response_parser` is an edit to a closed orchestrator (additive call site). | **L** | EXP-32 (so the learn-loop is *measured*); strict validator + low-confidence quarantine (design). EXP-55 (attribution, soft). |
| **EXP-51** (NPC goal-formation / GOAP) | **New engine** (`engines/planning/`) over existing `goal.yaml`+`pursues.yaml`. Action selection dispatches through existing `interaction/dispatch` (but see EXP-40: trade dispatch is a stub). New `GOAL_TARGETS` base edge → **schema call**. Action vocabulary must be `Literal`/Enum. Precedence vs `routine` engine needs a DECISIONS entry. | **L** | EXP-50 (rival targeting, soft), EXP-10 (consumes selected intent, soft). Action-dispatch maturity (EXP-40, soft). |
| **EXP-80** (free-play / sandbox demo) | **Demo-only**, zero `src/` change. New `demo_game/sandbox_loop.py` + window toggle over existing `/v1/clock/advance` + pollers. | **M** | None. (ISSUE-059 degrades hub NPCs mid-sandbox — quality risk, not a blocker.) |
| **EXP-81** (cross-session memory recall demo) | **Demo-only**, zero `src/` change — *iff* retrieval surfaces the Memory. New `MemoryRecallBeat` + session rotation. | **M** | **ISSUE-059 / EXP-30** (hard — recall depends on the exact path that overflows for knowledge-rich NPCs). First slice sidesteps via a low-knowledge NPC. |
| **EXP-83** (integrator hello-world) | **Demo-only**, new standalone `demo_game/quickstart.py` (httpx-only, no `EngineClient`) + `make hello`. Zero `src/`, zero schema. | **S** | None for happy-path; clean full run benefits from fresh-boot fix + Batch 5 typed responses (soft). |
| **EXP-93** (fix ISSUE-060) | **Demo-only if** `adjust_npc_reputation` (`client.py:1274` → player→faction reputation route) covers the bribe path; then re-point `BribeScene`. Escalates to a **schema call** only if no player→faction standing representation exists. | **S** (if adjust works) / **M** | Decision on canonical player→faction standing (route to DECISIONS). |

**EXP-22 / EXP-50 reconciliation:** These are the same affinity engine from two lenses. Unified verdict: **new-file-add engine, effort S, no schema call for the core** (X2's insight that `relates_to.yaml:11-12` already carries the dead `relationship_phase` field is correct and decisive — it converts X1's "M, derive standing" into a populate-existing-field "S"). Take X2's framing (fill the dead field + thresholds YAML) as the implementation; take X1's framing (derived standing bands consumed by gossip/dialogue/interaction to kill `if trust > N` magic numbers) as the value justification. The only schema-gated piece is the *optional* `relationship_event` audit node — defer it.

---

## 2. Shared / keystone enablers

These cross-cutting enablers unblock multiple expansions. Building them first is the highest-leverage sequencing.

### KE-1 — EXP-30: Bounded / gracefully-degrading Tier A (fixes ISSUE-059)
**The single highest-leverage enabler.** It is itself a candidate (M), edits one closed module (`context_budget_enforcer.py:78-84`), and is a hard or soft prerequisite for nearly every memory/knowledge expansion because every one of them *adds Tier-A items* into the exact budget that currently hard-fails.
**Unblocks:** EXP-81 (hard — recall path is the overflow path), EXP-32 (hard — else knowledge NPCs auto-fail as canned, poisoning the hallucination metric), EXP-17 (memories→Tier A), EXP-11 (player-scoped memories→Tier A), EXP-53 (learned facts→Tier A), EXP-55 (player-model block→Tier A), EXP-10 (proactive on knowledge-rich NPCs), EXP-41 (need/mood→Tier A). **Verdict: build first.**

### KE-2 — "Engine-writes-graph-facts" seam (for EXP-53)
There is no generic seam for an engine to *write new typed knowledge edges* — `dialogue_handler.py:179` only writes arousal memory; graph writers exist per-domain (`character_writer`, `relation_writer`, etc.) but none for belief/knowledge provenance. EXP-53 needs a new `graph/knowledge_writer.py` (graph-owned, `AsyncSession`-injected per the session-ownership rule) **plus** a new `LEARNED_FROM` base edge.
**Unblocks:** EXP-53 (directly), EXP-18 (commitment/fact memory formation), and provides the write-target EXP-55's learned facts attach to. **Verdict: schema-gated; needs DECISIONS.**

### KE-3 — `EmotionModelProtocol` (L7-06)
Extract a small Protocol + wrap current logic as `VadEmotionModel`, inject via `EmotionUpdater.__init__` (DI seam already present, `emotion_updater.py:25`). No schema. After it lands, trait-modulated/OCC models are clean new files.
**Unblocks:** EXP-13 (directly), and is the OCP-compliant *vehicle* for any future emotion variant. Soft-enables EXP-41 (mood coupling) by giving a clean model boundary. **Verdict: pure refactor, no schema. Build when emotion expansion is on the table.**

### KE-4 — Distortion-strategy registry (L7-01)
Replace the closed `_apply_template` if-chain (`gossip_distort.py:93-103`) with a name-keyed strategy registry; **determinism caveat (verified):** selection is `distortion_types[seed % len]` (`:163`), so the seed→strategy mapping must stay stable across registry ordering or replayability breaks. Extract the 4 branches into 4 callables behind a stable-keyed registry first (identical output). No schema.
**Unblocks:** EXP-15 (directly), EXP-16 (content-selective distortion — also moves the hardcoded English strings into `prompts/gossip/*.yaml`, fixing a live "no prompt strings outside prompts/" violation at `gossip_distort.py:94-101`), EXP-84 demo (distortion-diff view reads richer per-strategy metadata). **Verdict: pure refactor, no schema.**

### KE-5 — ISSUE-057: location hierarchy (`PART_OF` + `location_writer.py`, L7-02)
Confirmed: no `location_writer.py` exists and no `PART_OF` base edge. A real nested geography needs both. This is a **schema call** (new base edge) plus the missing writer module.
**Unblocks:** EXP-87 (hierarchical world — flat NPC/location additions land *without* it; the hierarchy is the gated part), EXP-93 partially (location/standing graph correctness), region-scoped gossip. **Verdict: schema-gated; needs DECISIONS. Not on the critical path for the top wins — flat world expansion is independent.**

### KE-6 — ISSUE-055: client-supplied stable-id seeding (get-then-skip, L7-09)
Idempotent seeding by stable id. Not a schema change; a seeding-path robustness fix.
**Unblocks:** EXP-87 (re-seeding bigger worlds idempotently), EXP-95 (in-window scenario picker that reseeds per arc), reliable demo boot for EXP-80/81/83 recordings. **Verdict: enabler for demo-scale and multi-world demo flows; low risk, no schema.**

### KE-7 (cross-cutting note) — Tier-A `priority` already exists
Confirmed Tier-A `ContextItem`s carry `priority` (used in B/C sort, `context_budget_enforcer.py:139`). EXP-30 does **not** need a new field — it needs to *apply* the existing priority to Tier A before raising. This lowers EXP-30's risk: the data model is ready; only the policy is missing.

---

## 3. Schema / layer-change flags (require human DECISIONS approval)

Per CLAUDE.md "Asking before doing", every item below changes a graph node/edge schema or adds a public API surface and must stop-and-ask. None require a *layer-rule* change — all proposed engines fit the existing downward-only layer model (engines → services/retrieval → graph), and all keep LLM in `engines/` and Cypher in `graph/`.

**Graph schema changes (new/extended base node or edge):**
- **EXP-53** — new `LEARNED_FROM` base edge (+ `graph/knowledge_writer.py`). **Schema call.**
- **EXP-51** — new `GOAL_TARGETS` base edge. **Schema call** (+ a DECISIONS entry for `routine`-vs-`planning` precedence).
- **EXP-55** — new `player_model` base node. **Schema call.**
- **EXP-17** (full version only) — `Memory.salience` / `last_recalled_tick` / `recall_count`. **Schema call.** *(First slice — charge-weighted decay reusing existing `emotional_charge` — is NOT a schema call.)*
- **EXP-52** (optional cached field only) — `character.player_reputation_baseline`. **Schema call** *(avoidable: derive on read instead of caching → no schema call).*
- **EXP-50** (optional audit only) — `relationship_event` node. **Schema call** *(avoidable: core engine populates the already-declared `relates_to` fields → no schema call).*
- **KE-5 / ISSUE-057 (EXP-87 hierarchy)** — new `PART_OF` base edge. **Schema call.**

**API-surface additions (public interface — additive, stop-and-ask but non-breaking):**
- **EXP-10** — new WS push `proactive_line` + scheduler registration.
- **EXP-50 / EXP-52 / EXP-55** — optional admin GET routes for the dashboard (deferrable).

**No schema, no layer change (clean):** EXP-30, EXP-31, EXP-32, EXP-50 (core), EXP-17 (first slice), KE-3, KE-4, KE-6, and all demo items (EXP-80/81/83/93 — demo-only, zero `src/`).

**EXP-93 conditional flag:** demo-only *unless* the engine has no player→faction standing representation, in which case it escalates to a new `Character→Faction` reputation edge (**schema call**). Verify `adjust_npc_reputation` (`client.py:1274`) first.

---

## 4. Ranked feasibility verdict (architecture-fit ease × value)

### Lowest-friction, high-value wins (do these first)
1. **EXP-30 (M, edits one module, no schema)** — *the keystone.* It is the cheapest single change that unblocks the most other work (KE-1) and fixes a live success-criterion failure (degradation invisible to player, ISSUE-059). The data model already carries Tier-A `priority`; only the trim policy is missing. **Highest ROI on the board.**
2. **EXP-50/EXP-22 (S, new-file-add, no schema)** — fills already-declared dead fields (`relates_to.yaml:11-12`), kills `if trust > N` magic-number smells across consumers, delivers a headline "relationships" capability a buyer expects. Lowest effort × high value.
3. **EXP-83 (S, demo-only) + EXP-31/EXP-32 (M, new-file evals, no schema)** — pure-additive, zero architectural risk. EXP-83 is the smallest sales artifact (success criterion 5); EXP-31/32 convert the two *asserted* buyer metrics (anti-hallucination, retrieval quality) into *measured* numbers with no engine edits. EXP-32 pairs with EXP-30 (run it after, or it auto-fails knowledge NPCs).

### High-value but architecturally expensive (sequence behind enablers / DECISIONS)
1. **EXP-53 (L, schema call + 2nd LLM pass + new graph writer)** — the strongest *business-fit* (closes the learn→ground→answer anti-hallucination loop, the moat). But it is the most architecturally loaded: new base edge (schema call), new graph sub-writer, a per-turn extra LLM pass (cost/latency), an extraction-hallucination validator, and a closed-orchestrator hook in `dialogue_handler`. Gate it behind EXP-32 (so it's measured) and a DECISIONS entry for `LEARNED_FROM`.
2. **EXP-51 (L, schema call + dispatch dependency + precedence DECISIONS)** — high value (the missing "agentic, not reactive" core) but expensive: new base edge, action-vocabulary enum, dependency on the `interaction/dispatch` trade path (stubbed today, EXP-40), and an unresolved `routine`-vs-`planning` precedence call.
3. **EXP-10 (L, new engine + WS + scheduler)** — directly serves success criterion 2 (proactive hail) but is L-effort: a new scheduler-driven engine, a new public WS surface, and a cadence/budget policy that doesn't exist. Architecturally *clean* (no schema, no `dialogue_handler` edit) — its cost is breadth and the unsolved spam/cost policy, not structural friction. Hard-depends on EXP-30 to avoid proactive lines collapsing to canned on the very hub NPCs that have the most to say.

**Demo note:** EXP-81 ("the NPC remembers you" — the single highest-value demo against the product thesis) is **demo-only but hard-blocked by ISSUE-059/EXP-30.** This is the clearest illustration of EXP-30's keystone status: the headline demo, the anti-hallucination eval, and the knowledge-extraction moat all route through the same Tier-A overflow path. **Fix EXP-30 and three separate high-value items unlock at once.**

### One-line sequencing
**EXP-30 → (EXP-50, EXP-83, EXP-31) → EXP-32 → KE-3/KE-4 refactors → EXP-17 first-slice / EXP-81 demo → schema-gated heavies (EXP-53, EXP-51, EXP-55) each behind a DECISIONS entry.**
