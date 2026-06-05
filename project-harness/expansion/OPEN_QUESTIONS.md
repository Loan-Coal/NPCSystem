# OPEN_QUESTIONS.md — decisions + resolutions

This started as the autonomous run's open-questions log. **As of 2026-06-05 the human reviewed it and
resolved every item.** Below: §A resolved decisions (now binding on the roadmap), §B the few items left
open / deferred, §C attestation. Resolved items that change the graph schema or an existing module's
contract also have a `DECISIONS.md` entry (DEC-070..072) and/or an updated `ISSUES.md` entry.

Legend: ✅ RESOLVED · 🟡 DEFERRED (decided to not do now) · ⏳ STILL OPEN.

---

## A. Resolved decisions (binding)

### ✅ OQ-D1 — Context model: collapse tiers into pinned-core + ranked pool (→ DEC-070, supersedes ISSUE-059 fix)
**Decision:** Replace the tier-A/B/C budget model with **two classes**:
- a **pinned set** that is never dropped — `world`, `emotion`, persona, the **session window**, `active_quest` — carrying an explicit **`pinned: bool`** flag so the guarantee is in the model, not implied by a tier label;
- a single **ranked pool** of everything else (memories, beliefs, goals, items, secrets, obligations, knows_about facts), filled by **`priority × relevance`** until the budget is hit, dropping from the bottom.
**Why this is correct:** the "Tier A never trims" invariant broke because *unbounded, accumulating* categories were placed inside the never-trim tier. The only un-droppable set is now small and **bounded by construction** (persona + a windowed session, not an accumulating fact list), so a "Tier A exceeded" failure cannot occur. Every item already carries a `priority` (`context_builder.py:272-359`); tiers were just coarse priority bands.
**Caveat:** the session window must stay bounded (last-N turns) so even the pinned set can't exceed budget.
**Affects:** EXP-30 (reframed: "pinned-core + ranked-pool fill", not "trim Tier A"). Edits `context_budget_enforcer.py` + `context_builder.py`. No schema change.

### ✅ OQ-D1b — EXP-30 pool ordering: priority-only v1, relevance fast-follow
**Decision:** The ranked pool is ordered by **`priority` only in v1** (deterministic, no tuning needed). The
existing relevance signal (`context_relevance_engine.py` / `context_scoring.py`) is wired in as the
`× relevance` factor as an **immediate fast-follow** (the long-term target is `priority × relevance`). The
keystone ships without waiting on relevance tuning. *(Reconciles the two steers given — "reuse relevance"
+ "priority only" — as priority-only-now, relevance-next.)*

### ✅ OQ-A-affinity — Relationship standing: 5 bands, composite score, gossip-then-dialogue refactor
**Decision:** **5 bands** on `standing = clamp(trust + affection − fear, −100, 100)`:
`HOSTILE [−100,−50) · WARY [−50,−15) · NEUTRAL [−15,15] · FRIENDLY (15,50] · ALLIED (50,100]`
(enum + cutoffs as named config constants — tunable; the goal is to *have* bands and test them, not find
optimal values). **Consumer refactor order: gossip first** (secret-sharing gate), **then dialogue** (tone).

### ✅ OQ-Phase0 — Demo is currently broken; Phase 0 added as a blocker
**Decision/finding:** the playable demo is currently unusable (engines 500 + timeout storm, pledges 404).
Root-caused to ISSUE-061 (path drift) + ISSUE-062 (engines-500 rebuild storm). Added **Phase 0** to
`EXPANSION_ROADMAP.md` (EXP-00a/b/c) as a hard blocker before Phase 1, including a CI smoke test so it
can't silently regress. Trade itself is not broken — it was collateral from the storm.

### ✅ OQ-D2 — Eval metrics: report, do not gate
**Decision:** EXP-32 reports the anti-hallucination rate; EXP-31 reports precision@k / recall@k (k=5). **No committed SLA / floor in v1.** Publish numbers first; commit to a contractual floor later.

### ✅ OQ-D3 — Knowledge learning: single-pass `learned_facts` output, write to `belief` nodes, no new edge (→ DEC-072)
**Decision (three parts):**
1. **No second LLM pass, no `LEARNED_FROM` edge.** Add an optional **`learned_facts`** field to the *existing* dialogue structured-output schema so the model emits learned facts **in the same single pass** (parsed by `response_parser`). Cost ≈ a few output tokens; zero extra round-trips; no gameplay-speed hit.
2. **Player-taught facts land on `belief` nodes** via the `BELIEVES` edge (not `event`/`KNOWS_ABOUT`). `believes.yaml` currently has empty fields → add optional `source_character_id`, `learned_at_tick`, `confidence` provenance fields. Events stay reserved for actual world-happenings (and `event.yaml` already carries `event_type`/`src_character_id`).
3. **Player-sourced knowledge is legitimate, not hallucination.** The anti-hallucination eval (EXP-32) must score "NPC repeated a fact the player taught it" as **grounded** — the `source_character_id = player_demo` provenance is what authorizes it. EXP-53 and EXP-32 must agree on this.
**Affects:** EXP-53 drops from "L, new base edge + 2nd pass" to "**M, reuse `BELIEVES` + 3 optional fields + single-pass extraction**". The provenance-field add to `believes.yaml` is the only schema touch (→ DEC-072).

### ✅ OQ-D4 — Memory salience: approved; one new field (`recall_count`)
**Decision:** Build the salience model + forgetting curve. `memory.yaml` already has `vividness`, `emotional_charge`, **and `last_recalled_at`** — so the only genuinely new field is **`recall_count: int`**. `salience` is *computed* (`f(vividness, |emotional_charge|, recency, recall_count)`), not stored. Curve: vividness decays per tick, emotionally-charged memories decay slower, each recall boosts vividness (spacing effect); below a floor a memory is forgotten (un-retrieved / optionally pruned). **Never delete graph nodes silently** — mark below-floor.
**Plus (from OQ-D-new1):** a **`never_forget: bool`** (pinned) flag on plot-load-bearing memories so the curve can never drop quest-critical knowledge. Symmetric with the context `pinned` flag (OQ-D1).
**Affects:** EXP-17 (field list trimmed to `recall_count` + `never_forget`), EXP-18.

### ✅ OQ-D5 — GOAP precedence: goal `urgency` vs routine, no LLM
**Decision:** A goal overrides the active routine when **`goal.urgency` exceeds the routine's priority** — `goal.yaml` already has `urgency` (0-100) + `target_id`, so **no schema change** and **no LLM-decided threshold for now** (deferred as a possible future refinement). Generation sets `urgency` per goal at creation.
**Affects:** EXP-51 (precedence rule fixed; drops the dynamic-threshold complexity).

### ✅ OQ-D6 — Player-model node: not now; second-order belief via memories (future expansion)
**Decision:** **Do not add a `player_model` node now.** The player is already a `character` node (`seed.py:658`, `is_player:true`, `player_demo`), so perceived trust/affection/fear, faction lean, and known-facts are already modeled via `relates_to` / `has_reputation_with` / `knows_about` (player as the other endpoint). Reliability derives from existing `PLEDGE` edge `is_active` + quest outcomes. **Second-order belief** ("what the NPC thinks the player knows/believes") is a **good future expansion**, expressed **through memories for now**.
**Affects:** EXP-55 demoted to a future-expansion note; no near-term schema.

### ✅ OQ-D7 — Bribe points to the existing `HAS_REPUTATION_WITH` edge
**Decision:** Character→faction standing already exists as **`HAS_REPUTATION_WITH`** (`standing` -100..100). Re-point the demo's ACT-3 bribe from `STANDS_WITH` (faction→faction) to `HAS_REPUTATION_WITH`. **No schema change.**
**Affects:** EXP-93 / ISSUE-060 → S effort, demo-only.

### ✅ OQ-D8 / OQ-D9 — Proactive dialogue + WS push: build it
**Decision:** Build the proactive engine **and** the new public WS server-push surface `proactive_line` (the NPC initiates, so there's no request to answer — the server must push an unsolicited line carrying `npc_id` + opening line + trigger reason). Keep `GET /v1/dialogue/pending` as the poll fallback for non-WS integrators. Cadence = per-NPC cooldown + global per-tick cap via config (ROADMAP S14.2 backpressure); urgency from need thresholds / unresolved goals; co-located players only.
**Affects:** EXP-10 / EXP-82.

### ✅ OQ-D10 — Location hierarchy: add `PART_OF` edge + `location_writer.py` (→ DEC-071, ISSUE-057)
**Decision:** **Approved.** Add the `PART_OF` base edge and the missing `location_writer.py`. Schema change accepted.
**Affects:** EXP-87 hierarchy; ISSUE-057 unblocked.

### ✅ OQ-D11 / OQ-A-localization — No localization, no voice
**Decision:** Out of scope. **Drop EXP-56 (localization) and EXP-57 (voice/STT).**

### ✅ OQ-A1 — Plugin later; HTTP service is the near-term test target
**Decision:** Product is ultimately a Unity/Unreal plugin, but for now we test/harden the **HTTP service**; the plugin wraps it later. Keeps EXP-83 (hello-world) and Batch 5 (typed OpenAPI) relevant.

### ✅ OQ-A3 / relationship_event — Reuse the `event` node, no new node
**Decision:** No `relationship_event` node. `event.yaml` already has `event_type` (+ `subkind`, `reputation_delta`, `src_character_id`) — relationship changes are events with an appropriate `event_type`. EXP-50 stays **schema-free**.

### ✅ OQ-A6 — Single-world, single-player, single-tenant
**Decision:** Confirmed. One world, one player node (`player_demo`) for now, one deployment (DEC-068). No multi-tenant, no multi-player.

### ✅ OQ-A5 / non-critical engines — planned expansion + demo integration, deprioritized
**Decision:** The graveyard/niche engines (investigation, skill, treaty, military, succession, clique, oath, chapter, story_pacing, contracts) get **planned expansions and demo-game integration on the roadmap, but are NOT the priority.** **The priority is the dialogue + gossip systems and showing they work in the playable demo.** (Reframes EXP-42 from "keep as-is" to "planned, deprioritized.")

### ✅ Demo direction — strengthen the playable game (not a single run-through)
**Decision:** The demo is a **small playable game** (already started) to be **expanded and strengthened**. It is NOT a single scripted run-through — those are the evals/tests. So the demo work foregrounds free-play depth (EXP-80/95), surfacing dialogue+gossip richly (EXP-84/85/89/91), and the cross-session memory showcase (EXP-81) — as a *game*, not a recording.

### ✅ Gossip direction — expand the mechanics now AND make it visible in the demo
**Decision:** Actually **expand gossip mechanics now** (EXP-15 distortion-strategy registry, EXP-16 belief/secret-selective + prompt-driven distortion content) **and** make gossip visible/usable in the playable demo (EXP-84 telephone-diff view, EXP-92 determinism toggle). Pull these **up** from Phase 3 into the showcase phase.

---

## B. Deferred / still-open

- 🟡 **OQ-D6 second-order theory-of-mind** — good future expansion; deferred, expressed via memories for now.
- 🟡 **Localization / voice (EXP-56/57)** — dropped.
- 🟡 **LLM-decided goal-override threshold** — deferred; flat `urgency` vs routine priority for now.
- ✅ **EXP-53 fact visibility — RESOLVED 2026-06-05:** learned facts **CAN be gossiped onward** — a player-taught `belief` is a valid gossip source, so it propagates through the gossip engine like any other knowledge (subject to the usual per-pair distortion). This ties EXP-53 directly into the gossip expansion (EXP-15/16): the player can seed a rumor into the world by telling one NPC.
- ✅ **EXP-53/EXP-16 contradiction handling — RESOLVED 2026-06-05:** when a player teaches a fact that contradicts a known one, **keep BOTH and link them with a `CONTRADICTS` edge** (`contradicts.yaml` already exists). At retrieval/answer time, **prefer the higher-confidence / higher-trust-source belief**, but both remain in the graph (an NPC can knowingly hold a disputed belief and even voice the conflict — "some say X, but I heard Y"). No destructive overwrite.

---

## C. Attestation

- The analysis run (2026-06-04) was autonomous, overnight, **read-only** — only the six `expansion/*.md`
  deliverables were written.
- The resolutions above (2026-06-05) were made by the human reviewer. Doc updates applied: this file,
  `EXPANSION_ROADMAP.md`, `FEASIBILITY.md` (addendum), the affected mini-specs in `ENGINE_GAPS.md` /
  `NEW_ENGINES.md`, plus `DECISIONS.md` (DEC-070/071/072) and `ISSUES.md` (ISSUE-057/059 cross-refs).
  **No source/test/config code was modified** — these are still planning docs; implementation has not started.
