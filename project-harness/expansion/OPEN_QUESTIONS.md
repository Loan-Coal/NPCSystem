# OPEN_QUESTIONS.md — human decisions (each with an educated-guess default)

**Written:** 2026-06-11. Companion to `EXPANSION_ROADMAP.md` / `FEASIBILITY.md`.
**Rule:** every item below has a **Default** = the assumption the analysis used so nothing is blocked.
If you do nothing, the roadmap proceeds on the Default. Override only where you disagree.

These are grouped: **(A) schema/layer decisions that gate phases**, **(B) product-shape decisions**,
**(C) commercial/sequencing decisions**, **(D) assumptions the run made about already-built code**.

---

## A. Schema & layer decisions (gate Phases C/D/E)

### OQ-1 — Memory node schema batch *(Keystone 1; gates EXP-11/17/18)*
**Question:** Add `subject_player_id: str|None`, `recall_count: int=0`, `never_forget: bool=false`, and
`kind: Literal["episodic","commitment","fact"]|None` to `memory.yaml` as optional/back-compat fields?
**Default:** **Yes, as one batched DECISIONS entry.** All four are nullable/defaulted, so existing
memories stay valid (null `subject_player_id` = world memory; null `kind` = episodic). This unlocks the
two highest-value memory features at once. Risk: forget-threshold tuning — set a conservative
`MEMORY_FORGET_THRESHOLD` constant and gate forgetting behind `never_forget=false`.

### OQ-2 — Scheduler → API delivery pattern *(gates EXP-35)*
**Question:** How does a tick-scheduler-generated proactive line reach a connected WebSocket without an
upward layer import (scheduler is `engines` peer; WS is `api`)?
**Default:** **In-process async queue** — new `engines/proactive_dialogue/proactive_queue.py` (an
`asyncio.Queue` owned in `engines`), the scheduler enqueues, the `api` WS handler drains. No upward
import; `api` depends on `engines` (allowed). Document in DECISIONS. Reject alternatives (callback
injection, polling) as either layer-violating or higher-latency.

### OQ-3 — Canonical NPC emotion source *(gates EXP-34 and EXP-42)*
**Question:** When `EmotionStore` (in-memory, `EmotionUpdater`) and graph mood (`MoodContagionEngine`
writes) diverge, which is the source of truth for dialogue context?
**Default:** **In-memory `EmotionStore` is canonical for the current tick; graph mood is the durable
snapshot written at tick end.** Dialogue reads `EmotionStore`. Resolve divergence by having the
contagion engine write *through* the store, not around it. Needs a DECISIONS entry before EXP-34.

### OQ-4 — UNLOCKS edge: `on_choice_id` *(gates EXP-19 quest branching)*
**Question:** Add optional `on_choice_id: str|None` to `unlocks.yaml` so a quest's successor depends on a
player choice?
**Default:** **Yes.** Null = auto-unlock (current behaviour preserved); set = player choice selects the
branch. Back-compat. Defer the richer "weighted/conditional unlock" model — single choice id is enough
for the first consequence-chain slice.

### OQ-5 — Player-model node + edge *(gates EXP-41)*
**Question:** Approve new `base_nodes/player_model.yaml` + `base_edges/has_player_model.yaml` for NPC
theory-of-mind of the player?
**Default:** **Approve, but Phase E only.** This is the entry point to the flagship emergent-cognition
story, but it is the first genuinely new schema territory since Phase 26. Gate it behind Phase A–D
landing first so the social-graph depth (EXP-40) exists to anchor it.

### OQ-6 — Deception fields on `believes.yaml` *(gates EXP-43)*
**Question:** Add `is_deception: bool=false` + `deception_goal_id: str|None` to `believes.yaml`?
**Default:** **Approve in Phase E, coupled with an anti-hallucination eval update.** The eval battery
(EXP-32) must treat `is_deception=true` beliefs as *intended* behaviour, not guard failures — otherwise
the deception engine and the moat eval fight each other. Do not ship EXP-43 before EXP-32 can distinguish
them.

### OQ-7 — Scheme node + edges *(gates EXP-44)*
**Question:** Approve `scheme` node + `EXECUTES_SCHEME` + `SCHEME_STEP` edges, and a per-NPC active-scheme
cap?
**Default:** **Defer to end of Phase E.** XL effort, depends on EXP-43, and is only detectable if
`investigation` (graveyard) is revived. Treat as the flagship capstone, not near-term. Default cap:
`MAX_ACTIVE_SCHEMES_PER_NPC = 2`.

### OQ-8 — `stands_with.yaml` character→faction *(gates EXP-93 fix)*
**Question:** Does the existing `stands_with` edge support a *character→faction* standing, or does the
ACT-3 fix need a new edge type?
**Default:** **Assume the existing edge supports it; the bug is a wrong client method
(`put_npc_reputation` → `adjust_npc_reputation`), not a schema gap.** Verify in code first (FEASIBILITY
§5). If a new edge is actually required, that escalates EXP-93 from S to M and needs its own DECISIONS
entry.

### OQ-9 — Session persistence storage model *(gates EXP-33)*
**Question:** Persist dialogue session history as a Character property, a new `SESSION_TURNS` node, or an
external store (Redis)?
**Default:** **New `SESSION_TURNS` node in Neo4j**, capped to last N turns per (npc, player). Keeps the
single-deployment-per-studio model (DEC-068) with no new infra dependency. Reject Redis (adds a service
to every studio deployment). Low priority (P3) — verify it isn't already covered by the dialogue cache
first.

---

## B. Product-shape decisions

### OQ-10 — Is the demo a sandbox or an authored campaign?
**Question:** Should demo investment go toward an open-ended sandbox or a tighter authored 5–10 min arc?
**Default:** **Both, but the authored scripted arc is the sales artifact and gets priority.** Sandbox
already exists (EXP-80). The recordable scripted run (Keystone 3) is what closes studios, so Phase A
hardens *that*. Sandbox depth is Phase D polish.

### OQ-11 — Event `targets_player_id` field *(EXP-42 drama director)*
**Question:** Add an optional `targets_player_id` to `event.yaml` so the director can aim beats at a
specific player?
**Default:** **No — ship the director without it (slice 1).** The director can infer the target from
player location/session; adding a graph field is a schema cost not yet justified. Revisit if multi-player
targeting becomes real (out of scope under single-deployment).

### OQ-12 — Revive `investigation` engine? *(EXP-44 detection)*
**Question:** Un-graveyard `investigation` so schemes/deceptions are *discoverable* by other NPCs?
**Default:** **Yes, but only as part of Phase E EXP-44.** Undetectable schemes are a design dead-end
(nothing surfaces to the player). If EXP-44 is built, reviving `investigation` is its detection half and
should be scoped together, not separately.

---

## C. Commercial / sequencing decisions (the only ones outside the engineering plan)

### OQ-13 — When does the Unity/Unreal SDK (Phase X) start? *(highest commercial-ROI question)*
**Question:** Phase X is the deferred commercial milestone gated on an OpenAPI contract freeze (delivered
in Phases 20–21 per ROADMAP). Do we start it now, or finish the engine-depth Phases A–E first?
**Default:** **Finish Phase A (demo credibility) first, then start Phase X in parallel with Phase B.**
Rationale: the SDK sells the engine, but a studio evaluating the SDK still judges it by the demo. A
credible recorded demo (Phase A) + a frozen contract (done) is the minimum viable sales package; the SDK
can then proceed against a stable surface while eval/depth work continues. This is a business call —
flagged explicitly because it trades near-term commercial reach against demo polish.

### OQ-14 — Eval rigor bar for the moat claim
**Question:** What pass bar makes the anti-hallucination claim "provable" to a technical buyer?
**Default:** **Zero hallucination failures across the EXP-32 battery + precision@k ≥ 0.8 on the EXP-31
labeled set, reported by `make eval-*` and regression-gated in CI.** Deflections do not count as passes
(per BUSINESS_INTENT success criterion 1). Tighten later; this is the credible opening bar.

---

## D. Assumptions the run made about already-built code (verify, don't re-derive)

These are not decisions — they are claims the analysis relied on. Each should be code-verified before the
dependent EXP is implemented (all flagged in `FEASIBILITY.md §5`).

- **EXP-14 emotion persistence is wired** (`EmotionBootstrapper` in `main.py:125`). *Verify:* is
  `EmotionGraphWriter` injected into `EmotionUpdater` for write-through? If not, one composition-root line.
- **EXP-21 reputation is wired** (`dependencies_engines.py:388`, `tick_scheduler.py:551`). *Verify:* the
  stale "not wired in this slice" docstring should be corrected; update ISSUES.
- **EXP-30 pinned-core context model is done** (ISSUE-059 fixed). *Verify:* `TokenBudgetExceededError` is
  structurally unreachable on Tier0+TierA.
- **EXP-20 / EXP-37 stubs may be partly wired** (`event_quest_trigger.py`, `world_state_quest_trigger.py`
  passed to `TickScheduler`; `trade_handler_sync.py`). *Verify:* are the trigger bodies real or no-ops?
- **EXP-99 need→behaviour coupling.** *Verify:* does `routine_engine` actually consume Need thresholds, or
  do needs only decay?
- **EXP-87 faction-count assumption.** *Verify:* `game_end_checker.py` 3-faction gate before adding factions.

---

## Attestation (what the run assumed and why)

The analysis proceeded autonomously on every Default above. The defaults were chosen to be the most
**business-aligned, lowest-schema-cost, layer-clean** option in each case, consistent with DEC-068
(single deployment) and the layer model. The two genuinely human calls that the engineering plan cannot
make for you are **OQ-13** (when to start the commercial SDK) and **OQ-1** (the only schema change on the
critical path of the top-5). Everything else can run on its Default without blocking.
