# NPC Engine — Expansion Roadmap (X5 synthesis)

**Written:** 2026-06-11. Orchestrator synthesis of lenses X0–X4 + X3 feasibility.
**Inputs:** `BUSINESS_INTENT.md` (rubric), `ENGINE_GAPS.md` (EXP-10..38), `NEW_ENGINES.md` (EXP-40..44),
`DEMO_EXPANSIONS.md` (EXP-70..99), `FEASIBILITY.md` (architecture fit + keystones).
**State of the codebase:** Phases 0–26 complete; the engine is mature. This is **not** a greenfield
plan — most "obvious" engines already exist (relationship, reputation, economy/currency, planning,
knowledge_learning, need, routine, proactive_dialogue, oath, treaty, succession). The expansion frontier
is now **depth, wiring, and visibility**, not breadth. Several proposals were found **already shipped**
during feasibility (EXP-14, EXP-21, EXP-30, EXP-80/81/83/85/92) and are excluded from the active plan.

---

## 1. The throughline (read this first)

Three independent lenses converged on the **same** structural finding:

> **The simulation runs correctly but is invisible to the dialogue layer and to the buyer.**

- **Engines compute, dialogue ignores.** Emotion, need, mood, memory, and relationship engines tick and
  write state every loop, but the dialogue context builder never surfaces most of it (X1: EXP-22, 34;
  cross-engine theme). NPCs are still effectively reactive.
- **Built engines are unwired or undelivered.** ProactiveDialogue + IntentFormation generate lines that
  are logged and discarded — never reach the player (X1: EXP-10/35).
- **Shipped capability is unshown.** Retrieval explainability, gossip distortion text, proactive
  initiation, temporal memory, faction standings — all have live routes/data but no demo surface
  (X4: EXP-71/72/73/74/70).

The highest-leverage work is therefore **connective**, not additive: wire what computes into what the
player sees and what the LLM reads. This is also the cheapest work (mostly S/M, new-file-add or
demo-side) and the most defensible against the product thesis (the moat is *persistent, visible* state).

---

## 2. Scoring model

Each active proposal is scored on four axes, then assigned a **composite priority** (P0 highest):

- **Value** — studio-perceived impact toward a `BUSINESS_INTENT.md` success criterion (low/med/high).
- **Business-fit** — traceability to an explicit commitment vs an implied ambition (low/med/high).
- **Effort** — from `FEASIBILITY.md`, reconciled (S/M/L/XL).
- **Arch-fit** — new-file-add (✅ cleanest) | closed-edit (⚠) | needs DECISIONS (🔒) | demo-side (🎮).

**Composite priority rule:** P0 = high value × (S/M effort) × (✅/🎮 arch-fit) × unblocks others.
P1 = high value but needs a DECISIONS call, or med value + cheap. P2 = real but lower leverage.
P3 = niche / deferred / graveyard-adjacent.

---

## 3. Master ranked table

| Pri | EXP | Title | Type | Value | Fit | Effort | Arch | Unblocks |
|-----|-----|-------|------|-------|-----|--------|------|----------|
| **P0** | EXP-40 | Relationship affinity phase engine | new-engine | high | high | S | ✅ | EXP-22/41/42/43 (Keystone 2) |
| **P0** | EXP-72 | Gossip distortion diff view (demo) | demo | high | high | S | 🎮 | demo credibility (Keystone 3) |
| **P0** | EXP-70 | Proactive dialogue act in scripted runner | demo | high | high | S | 🎮 | demo "NPCs initiate" claim (Keystone 3) |
| **P0** | EXP-93 | Fix ISSUE-060 ACT-3 abort | demo | high | high | S | 🎮 | EXP-79, full-arc recording (Keystone 3) |
| **P0** | EXP-12 | Relation-delta first-contact fix | engine-gap | med | high | S | ⚠ | correctness (CLAUDE.md "never swallow") |
| **P0** | EXP-22 | Standing → dialogue tone + secret gate | engine-gap | high | high | M | ⚠ | makes relationships *felt* in dialogue |
| **P1** | EXP-10 | Unified proactive-trigger surface | engine-gap | high | high | M | ✅ | EXP-35 |
| **P1** | EXP-35 | Proactive line delivered over WS | engine-gap | high | high | S | 🔒 | closes agentic-NPC loop |
| **P1** | EXP-11 | Player-scoped memory recall in dialogue | engine-gap | high | high | M | 🔒 | headline "remembers you" claim (Keystone 1) |
| **P1** | EXP-17 | Salience-weighted forgetting curve | engine-gap | high | med | M | 🔒 | believable memory (Keystone 1) |
| **P1** | EXP-32 | Anti-hallucination eval battery | engine-gap | high | high | M | ✅ | proves the moat claim |
| **P1** | EXP-31 | Retrieval-quality eval (precision@k) | engine-gap | med | high | M | ✅ | proves retrieval quality |
| **P1** | EXP-71 | Retrieval-explainer panel (demo) | demo | high | med | M | 🎮 | "LLM is not a black box" pitch |
| **P1** | EXP-34 | Need/mood fed into dialogue context | engine-gap | med | high | S | 🔒 | living-NPC feel |
| **P1** | EXP-74 | Temporal memory readout (demo) | demo | med | med | S | 🎮 | surfaces Phase-26 temporal cognition |
| **P2** | EXP-13 | Personality-modulated emotion model | engine-gap | med | med | M | ✅ | distinct NPC personalities |
| **P2** | EXP-15 | Distortion content → prompts YAML | engine-gap | med | med | S | ⚠ | EXP-16; authoring surface |
| **P2** | EXP-16 | Belief-confidence-aware distortion | engine-gap | med | med | M | ⚠ | richer gossip drift |
| **P2** | EXP-18 | Commitment/fact memory formation | engine-gap | med | med | M | 🔒 | quests/promises remembered |
| **P2** | EXP-36 | Belief contradiction detection/dedup | engine-gap | med | med | M | ⚠ | clean learned-knowledge graph |
| **P2** | EXP-37 | Trade dispatch → NegotiationStore | engine-gap | med | med | M | ⚠ | economy becomes interactive |
| **P2** | EXP-38 | Player-observable event endpoint | engine-gap | med | med | S | ✅ | SDK integration story |
| **P2** | EXP-73 | Faction standing board (demo) | demo | med | med | S | 🎮 | politics visibility |
| **P2** | EXP-75 | Location hierarchy breadcrumb (demo) | demo | med | low | S | 🎮 | surfaces ISSUE-057 fix |
| **P2** | EXP-76/77/78 | Degradation label / face glyph / delta ticker | demo | med | med | S | 🎮 | polish cluster, data already parsed |
| **P2** | EXP-19 | Quest branching on player choice | engine-gap | high | med | L | 🔒 | consequence chains |
| **P2** | EXP-79 | Cinematic / recording mode (demo) | demo | med | med | M | 🎮 | marketing asset (needs EXP-93) |
| **P2** | EXP-87 | Richer world (more NPCs/locations) | demo | med | med | M/L | 🎮 | game depth (gated on faction logic) |
| **P2** | EXP-89 | Mood-contagion visualiser (demo) | demo | med | low | M | 🎮 | surfaces contagion engine |
| **P2** | EXP-82/95 | Proactive window surface / scenario picker | demo | med | med | S | 🎮 | interactive-mode polish |
| **P3** | EXP-41 | Player-model / theory-of-mind engine | new-engine | high | med | M | 🔒 | EXP-42/43 (advanced cognition) |
| **P3** | EXP-42 | Player-aware drama director engine | new-engine | med | med | M | ✅/🔒 | engagement management |
| **P3** | EXP-43 | NPC deception / false-belief engine | new-engine | high | med | L | 🔒 | EXP-44; emergent intrigue |
| **P3** | EXP-44 | Long-horizon covert scheming engine | new-engine | high | low | XL | 🔒 | flagship emergent-drama feature |
| **P3** | EXP-20 | World-state-driven dynamic quests | engine-gap | med | med | L | ⚠ | living-world quests (verify stubs) |
| **P3** | EXP-33 | Session history persisted across restart | engine-gap | med | med | M | 🔒 | continuity (verify vs EXP-14/cache) |
| **P3** | EXP-96/97/99 | Pacing readout / gossip counter / needs demo | demo | low/med | low | M | engine-dep | need engine-side route/metric first |

*Excluded — already shipped (confirmed in FEASIBILITY §Orientation/§4):* EXP-14 (emotion persistence),
EXP-21 (reputation wiring), EXP-30 (pinned-core context), EXP-80 (sandbox), EXP-81 (cross-session recall
scripted), EXP-83 (quickstart), EXP-85 (anti-hallucination beat), EXP-92 (determinism beat). Several have
S-effort residuals (e.g. EXP-83 field-name bug, `make hello`); these are tracked as cleanup, not phases.

---

## 4. Top 5 do-next

1. **EXP-40 — Relationship affinity phase engine** *(P0, S, ✅)*. The single highest-leverage item:
   zero-schema new-file-add that fills already-declared `relates_to.yaml` fields and is a soft prereq for
   four downstream proposals (Keystone 2). Makes relationships a first-class, queryable arc, not a scalar.
2. **EXP-93 + EXP-72 + EXP-70 — the demo-credibility cluster** *(P0, all S, 🎮)*. One bug fix + two
   demo surfaces that together turn the scripted runner into a recordable, end-to-end pitch (Keystone 3).
   EXP-72 makes the gossip "telephone game" visually undeniable using data already fetched.
3. **EXP-22 — Standing → dialogue tone & secret-share gate** *(P0, M, ⚠)*. EXP-21 is done, so this is
   unblocked. Turns the now-running reputation/relationship state into something the player *hears* —
   directly attacks the "simulation is invisible" throughline.
4. **EXP-10 + EXP-35 — proactive trigger surface + WS delivery** *(P1, M+S)*. Closes the agentic-NPC
   loop: lines the engine already generates finally reach the player. Needs one DECISIONS call (EXP-35
   scheduler→api queue pattern) — see OPEN_QUESTIONS.
5. **EXP-32 — anti-hallucination eval battery** *(P1, M, ✅)*. The product's headline claim ("NPCs never
   assert what they don't know") is currently *asserted, not measured*. This makes it provable and
   regression-guarded — pure eval-layer, no engine edits.

---

## 5. Keystone enablers (the multipliers)

From `FEASIBILITY.md §2` — build these early to unlock the most downstream value:

1. **Keystone 1 — Memory schema DECISIONS call** (`subject_player_id`, `recall_count`, `never_forget`,
   `kind`). One batched `memory.yaml` edit unlocks EXP-11, EXP-17, EXP-18 (two HIGH-value memory features).
2. **Keystone 2 — EXP-40 (relationship phase engine)**. S-effort, no schema change; soft-unblocks
   EXP-22/41/42/43. The cleanest high-multiplier build in the set.
3. **Keystone 3 — EXP-93 + EXP-72 + EXP-70 (demo credibility)**. Three S items that make the engine's
   differentiators *visible in a recording* — the artifact that actually closes studios.

---

## 6. Dependency graph

```
Keystone 1 (memory.yaml DECISIONS) ──► EXP-11 ─┐
                                   └─► EXP-17 ──► EXP-18
EXP-30 (DONE) ────────────────────────► EXP-11, EXP-32, EXP-34

EXP-40 (Keystone 2) ─┬─► EXP-22 (also needs EXP-21 DONE ✓)
                     ├─► EXP-41 ──► EXP-42
                     │         └──► EXP-43 ──► EXP-44
EXP-10 ──► EXP-35 (needs scheduler→api DECISIONS)
EXP-15 ──► EXP-16
EXP-93 (Keystone 3) ──► EXP-79 (cinematic) ──► EXP-87 (richer world; also gated on faction logic)
EXP-43 ──► EXP-44 (also wants un-graveyarding `investigation` for detection)
engine route enablers ──► EXP-96 (chapter route) / EXP-97 (gossip metric) / EXP-99 (need→behaviour)
```

---

## 7. Sequenced phase plan

Each phase is sized to land green under `make check` (≥80% cov) with tests-first. Phases are ordered by
value × friction × unblock-multiplier. This is the block to promote into `ROADMAP.md`'s "Next" section.

### Phase A — "Make it visible" (the throughline; mostly S, no schema)
*Goal:* connect computed state to player + buyer; convert the demo into a recordable pitch.
- EXP-40 (relationship phase engine) · EXP-22 (standing→dialogue) · EXP-12 (relation-delta fix)
- EXP-93 + EXP-72 + EXP-70 (demo credibility cluster) · EXP-74/76/77/78 (demo polish, data-already-parsed)
- EXP-34 (need/mood→dialogue context)
*Exit:* an unassisted scripted run shows persistent relationships shaping tone, visible gossip drift,
an NPC-initiated beat, and temporal memory — recorded end-to-end without the ACT-3 abort.

### Phase B — "Prove the moat" (eval-layer; ✅ new-file-add)
*Goal:* make the headline claims measurable and regression-guarded.
- EXP-32 (anti-hallucination battery) · EXP-31 (retrieval precision@k) · EXP-71 (retrieval-explainer panel)
*Exit:* `make eval-retrieval` reports precision@k and known-fact recall; a buyer-facing panel shows *why*
each line was grounded. Zero hallucination failures in the battery.

### Phase C — "Close the agentic loop" (1–2 DECISIONS calls)
*Goal:* NPCs that act on their own state reach the player.
- DECISIONS: scheduler→api queue pattern (EXP-35) · EXP-10 (trigger surface) · EXP-35 (WS delivery)
- DECISIONS: Memory schema batch (Keystone 1) · EXP-11 (player-scoped recall) · EXP-17 (forgetting curve)
*Exit:* an idle player receives an NPC-initiated line grounded in that NPC's need/memory; memories decay
by salience and player-specific recall surfaces in conversation.

### Phase D — "Deepen the systems" (content + economy + gossip authoring)
*Goal:* more game, richer drift, interactive economy.
- EXP-15→EXP-16 (gossip authoring + belief-confidence) · EXP-18 (commitment memories) · EXP-36 (belief dedup)
- EXP-37 (trade dispatch) · EXP-38 (player event endpoint) · EXP-73/75 (politics + location demo surfaces)
- EXP-87 (richer world — first resolve faction-count assumption in `game_end_checker.py`)
*Exit:* trades negotiate, gossip drift is authorable, the world has more NPCs/locations, and politics +
hierarchy are visible.

### Phase E — "Emergent cognition" (flagship, schema-heavy, P3)
*Goal:* the demo-defining "NPCs scheme and deceive" capability. Gated on multiple DECISIONS calls.
- EXP-41 (player-model) · EXP-42 (drama director) · EXP-43 (deception) · EXP-44 (scheming) · EXP-13
  (personality emotion) · EXP-19 (quest branching) · EXP-20 (dynamic quests — verify stubs first)
*Exit:* NPCs form theory-of-mind of the player, hold and act on false beliefs, and pursue multi-step
covert goals — the emergent-drama story that differentiates from every LLM-bolt-on competitor.

### Parked / deferred (unchanged from ROADMAP)
- **Phase X — Unity/Unreal SDK** (deferred commercial milestone; sequenced after OpenAPI freeze).
- **S17.9 niche engines** (succession, clique, investigation, skill, military) — graveyard unless a
  Phase-E proposal (EXP-44 detection) revives `investigation`.
- **S21.6 demo file-size** cluster.
- Engine-route-dependent demo items EXP-96/97/99 (need new read routes/metrics first).

---

## 8. Cross-references & caveats

- Every EXP-NN mini-spec lives in its source lens file (`ENGINE_GAPS.md`, `NEW_ENGINES.md`,
  `DEMO_EXPANSIONS.md`); feasibility and seams in `FEASIBILITY.md`; the rubric in `BUSINESS_INTENT.md`.
- **Verify-before-design flags** (FEASIBILITY §5): EXP-20/37 stubs may be partly wired; EXP-93 needs
  `stands_with.yaml` character→faction check; EXP-87 needs `game_end_checker.py` faction-count review;
  EXP-99 needs confirmation the routine engine consumes Need thresholds.
- **Human decisions** that gate phases C/D/E are compiled in `OPEN_QUESTIONS.md`, each with an
  educated-guess default so no phase is blocked overnight.
- This roadmap stops at planning. No source/config/test was modified. To activate: promote Phase A into
  `ROADMAP.md`'s "Next" block (the human action this analysis was run to enable).
