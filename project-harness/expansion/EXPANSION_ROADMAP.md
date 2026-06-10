# EXPANSION_ROADMAP.md — Synthesis & Prioritization (Lens X5)

> **Updated 2026-06-10 — last batch: EXP-92 + EXP-95 merged (1879 unit + 614 demo tests green). Phase 17 COMPLETE. Next batch: all remaining items are schema/DECISIONS-gated (EXP-51, EXP-14, EXP-19). No deployable batch until a DECISIONS entry is approved.**
> **Prior update 2026-06-05 with human resolutions** (see `OPEN_QUESTIONS.md` §A, `DECISIONS.md` DEC-070/071/072).
> Net effect: (1) **dialogue + gossip are the priority** — show they work in the playable demo; (2) several
> proposals lost their schema cost by reusing existing graph vocabulary (EXP-53→`BELIEVES`, EXP-50 schema-free,
> EXP-55 deferred); (3) EXP-30 is reframed as **pinned-core + ranked-pool** (not "trim Tier A"); (4) gossip
> mechanics (EXP-15/16) pulled up into the showcase phase; (5) localization/voice dropped; (6) the demo is a
> **playable game to strengthen**, not a single run-through.

**Inputs:** `BUSINESS_INTENT.md` (rubric), `ENGINE_GAPS.md` (EXP-10..42), `NEW_ENGINES.md` (EXP-50..57),
`DEMO_EXPANSIONS.md` (EXP-80..99), `FEASIBILITY.md` (architecture fit + keystones).
**Method:** every proposal scored on **business-fit** (traceability to BUSINESS_INTENT), **value**
(studio-perceived impact), **effort** (from X3), **arch-fit** (✅ new-file-add · ⚠️ edits closed module ·
🔶 schema/DECISIONS call), then sequenced so each phase clears the prerequisites of the next.

---

## 1. The one-paragraph thesis (from BUSINESS_INTENT)

NPC Engine sells **licensable game middleware** (HTTP+WS, one deployment per studio, single world, no
multi-tenant per DEC-068) whose differentiator is **NPCs with persistent memory, relationships, and
emotion plus a living off-screen world**. A studio judges it on: (1) a *measured* anti-hallucination
guarantee, (2) a clean integrator hello-world + working OpenAPI client codegen, (3) agentic NPCs
(proactive dialogue), (4) retrieval quality (precision@k). Every expansion below traces to one of
those four. The recurring theme across all four lenses: **the engine already ships the capabilities;
what it lacks is (a) proof they work, (b) the ability to grow knowledge, and (c) a demo that shows the
headline claims.** The product is feature-rich and proof-poor — so the highest-value work is
unblock-and-prove, not greenfield.

---

## 2. Master scored table

Arch-fit legend: ✅ clean new-file add · ⚠️ edits one closed module (no schema) · 🔶 needs schema/DECISIONS call.
Score = qualitative roll-up; "Phase" column is the sequencing decision in §3.

### Tier S — keystone & lowest-friction high-value (Phase 1)

| ID | Title | Type | Bus-fit | Value | Effort | Arch-fit | Phase |
|----|-------|------|--------|-------|--------|----------|-------|
| **EXP-30** | Bounded/graceful Tier-A (fix ISSUE-059) | engine-gap | high | high | M | ⚠️ `context_budget_enforcer.py` | **1** |
| **EXP-50/22** | Relationship/affinity engine (fills `relates_to.yaml:11-12` dead fields) | new-engine | high | high | S | ✅ | **1** |
| **EXP-83** | Integrator hello-world quickstart | demo | high | high | S | ✅ demo-only | **1** |
| **EXP-31** | Retrieval-quality eval (precision@k/recall) | engine-gap | high | high | M | ✅ | **1** |
| **EXP-32** | Measured anti-hallucination eval | engine-gap | high | high | M | ✅ (after EXP-30) | **1** |

### Tier A — high value, behind a Phase-1 enabler (Phase 2)

| ID | Title | Type | Bus-fit | Value | Effort | Arch-fit | Phase |
|----|-------|------|--------|-------|--------|----------|-------|
| **EXP-10** | Proactive / NPC-initiated dialogue (agentic loop) | engine-gap | high | high | L | ✅ new engine + WS (API add) | **2** |
| **EXP-81** | Cross-session memory recall demo ("remembers you") | demo | high | high | M | ✅ demo-only (needs EXP-30) | **2** |
| **EXP-11** | Player-scoped long-term memory recall in dialogue | engine-gap | high | high | M | ⚠️ retrieval edit | **2** |
| **EXP-80** | Free-play / sandbox demo mode | demo | high | high | M | ✅ demo-only | **2** |
| **EXP-93** | Fix ISSUE-060 (7-act scripted demo completes) | demo | med | high | S/M | ✅/🔶 (verify `client.py:1274`) | **2** |
| **EXP-17** | Salience-weighted forgetting curve (first slice) | engine-gap | high | high | M | ⚠️ `memory_engine.py` (slice); 🔶 full | **2** |

### Tier B — strong, schema-gated or refactor-gated (Phase 3)

| ID | Title | Type | Bus-fit | Value | Effort | Arch-fit | Phase |
|----|-------|------|--------|-------|--------|----------|-------|
| **EXP-53** | Dialogue-driven knowledge extraction (NPCs learn facts) | new-engine | high | high | L | 🔶 `LEARNED_FROM` edge + `knowledge_writer.py` | **3** |
| **EXP-15** | Distortion-strategy registry (open L7-01 if-chain) | engine-gap | med | med | M | ⚠️ refactor `gossip_distort.py` | **3** |
| **EXP-16** | Belief/secret-selective, prompt-driven distortion | engine-gap | med | med | M | ⚠️ (needs EXP-15) | **3** |
| **EXP-13** | `EmotionModelProtocol` + personality modulation | engine-gap | med | med | M | ⚠️ refactor `emotion_updater.py` | **3** |
| **EXP-14** | Persistent emotion state (survive restart) | engine-gap | med | med | M | 🔶 emotion node/field | **3** |
| **EXP-52** | Personal reputation propagation engine | new-engine | med | med | M | ✅/🔶 (avoid cached field) | **3** |
| **EXP-12** | Relation-delta provenance & audit at dialogue boundary | engine-gap | med | med | S | ⚠️ | **3** |
| **EXP-20** | Quest status enum + explicit fail/expire states | engine-gap | med | med | S | 🔶 (enum field) | **3** |

### Tier C — high-ceiling but expensive / later (Phase 4)

| ID | Title | Type | Bus-fit | Value | Effort | Arch-fit | Phase |
|----|-------|------|--------|-------|--------|----------|-------|
| **EXP-51** | NPC goal-formation & action-selection (GOAP) | new-engine | high | high | L | 🔶 `GOAL_TARGETS` edge + precedence DEC | **4** |
| **EXP-55** | Player-model / theory-of-mind engine | new-engine | med | med | M | 🔶 `player_model` node | **4** |
| **EXP-54** | Player-aware drama director engine | new-engine | med | med | L | 🔶 | **4** |
| **EXP-19** | Branching quests & consequence chains | engine-gap | med | high | L | 🔶 | **4** |
| **EXP-18** | Memory formation beyond arousal (semantic salience) | engine-gap | med | med | M | ⚠️/🔶 | **4** |
| **EXP-21** | World-state-aware dynamic quest generation | engine-gap | med | med | M | ⚠️ | **4** |
| **EXP-40** | Interaction dispatch trade path (currently stub) | engine-gap | med | med | M | ⚠️ | **4** (unblocks EXP-51) |
| **EXP-87** | Richer world on a location hierarchy (ISSUE-057) | demo | med | med | L | 🔶 `PART_OF` edge | **4** |

### Tier D — demo polish & niche (opportunistic, Phase 2–4 as cheap wins)

| ID | Title | Effort | Note |
|----|-------|--------|------|
| EXP-84 | Gossip distortion diff view ("telephone") | S | great sales visual; pairs with EXP-15/16 |
| EXP-85 | Anti-hallucination "I don't know" demo beat | S | showcases the moat; pairs with EXP-32 |
| EXP-86 | Degradation-as-a-feature banner | S | turns ISSUE-059 optics into a selling point |
| EXP-88 | Recording / marketing mode (deterministic playback) | M | needs KE-6 stable-id seeding |
| EXP-89 | Mood-contagion visualiser | S | surfaces an unshowcased engine |
| EXP-90 | Retrieval-explainer panel ("why did NPC say that?") | M | needs S15.1 debug route |
| EXP-91 | Relationship-delta live ticker | S | pairs with EXP-50 |
| EXP-92 | Determinism / replay proof toggle | M | needs KE-6 |
| EXP-94 | Facial-expression / portrait rendering | M | dialogue already returns expression |
| EXP-95 | In-window scenario picker (unify arcs+free-play) | M | pairs with EXP-80 |
| EXP-96/97/98/99 | Pacing readout / gossip-pairs counter / treaty board / needs demo | S–M | each surfaces one unshowcased engine |
| EXP-41 | Mood/need/faction surfacing & coupling | M | partly delivered by Tier-D demo panels |
| EXP-42 | Graveyard-engine depth (succession/clique/etc.) | — | **defer/keep as-is** — surface area without buyer value |
| EXP-56 | Localization / multi-language output | M | real for non-EN studios; route to OPEN_QUESTIONS |
| EXP-57 | Voice / STT input | L | complements TTS; market-driven, defer |
| EXP-82 | Demo surface for proactive dialogue | S | demo half of EXP-10 |

---

## 3. Phase plan (re-weighted 2026-06-05 — dialogue + gossip are the priority)

**Organizing principle (human steer):** the product story to prove *now* is **dialogue + gossip working in
the playable demo**. Everything in Phases 1–2 serves that; deep autonomy and world richness move later.

### Phase 0 — Demo repair + endpoint-contract guard 🔴 BLOCKER (do before anything else)
**Fix the regressions that currently make the playable demo unusable, then lock the demo↔API contract so it
can't silently drift again.** The demo is the thing we're expanding (Phase 2) — it must run first.
- **EXP-00a — fix `/v1/system/engines` 500 (ISSUE-062, P1). ✅ DONE 2026-06-05.** Actual root cause (live traceback): **double serialization** — `TickScheduler.engine_status` already returns serialized dicts and the handler re-called `.model_dump()` → `AttributeError` → 500. (The "rebuild storm" hypothesis was wrong; the scheduler ticks fine.) Fix: pass the property's dicts through (`system.py:91-95`) + regression test. Verified live HTTP 200; `make check` green. The separate demo timeout cascade split out to **ISSUE-063** (EXP-00c / concurrency pass).
- **EXP-00b — fix demo↔API path drift (ISSUE-061, P2). ✅ DONE 2026-06-05.** `/v1/pledges/...` 404'd because pledges moved to `/v1/admin/pledges/...`; fixed by aligning the client (consistent with the other `/v1/admin` inner-life reads; no API-surface change). Full path audit done: pledges was the ONLY real drift (the suspected `/v1/quests/offer` is a docstring, not a call). Regression tests added; seed + live verified 200.
- **EXP-00d — fix demo timeout cascade (ISSUE-063, P2). ✅ DONE 2026-06-05.** Root cause (confirmed live): `EmbeddingIndex.upsert/search/embed_batch` called the **synchronous** sentence-transformers `encode()` directly on the asyncio event loop; the startup embedding reconciler blocked the single worker for seconds → every demo poller + the quest/trade POST timed out. Fixed by offloading the encode via `asyncio.to_thread`. Verified live: 24 concurrent polls, slowest 42ms. (Residual same-pattern reranker block → ISSUE-064.)
- **EXP-00e — fix WS dialogue timeout (ISSUE-065, P2). ✅ DONE 2026-06-05.** Talking to an NPC `ws_recv_timeout`'d: the WS server fully generates before streaming (first frame measured live at 38.1s) but the client WS timeout was a stale 30s (HTTP path uses 120s). Raised `constants.NPC_DIALOGUE_TIMEOUT_S` to 120s + regression test. (Pre-existing demo-worker test failures spotted → ISSUE-066. Future UX: real token streaming from Ollama.)
- **EXP-00f — fix confirm-trade 422 (ISSUE-067, P2). ✅ DONE 2026-06-05.** Trade confirm always 422'd: the server's `propose_trade` returns `negotiation_state.item_type=""`, and `on_trade_confirm`'s `state.get("item_type","spice")` passed the empty string through (dict.get only defaults on *absent* keys) → `/economy/trade` rejects empty (`min_length=1`). Fixed demo-side with `... or "spice"`. (Deeper: the engine should populate `item_type` in negotiation_state — logged, ties to EXP-40.)
- **EXP-00c — boot + demo-endpoint smoke test in CI.** A test that boots the stack and hits every endpoint the demo calls (asserting non-5xx / non-404) **and runs `make test-demo`**, so path drift, construction errors, event-loop stalls, and demo-test breakage (ISSUE-066) all fail CI. Closes the long-standing "live-only breaks are unguarded" gap (L9-01/02/05, SEV-02). **Still TODO** — the only remaining Phase 0 item.
**Exit:** `make demo-seed && make demo` runs with zero `error:`/`500`/`404`/`timed out` lines in the console; `make demo-run` reaches at least ACT 3 (then EXP-93 for the bribe). **No Phase-1 work starts until Phase 0 is green.**

### Phase 1 — Prove & unblock the core
**EXP-30 (pinned-core + ranked pool) → EXP-32, EXP-31, EXP-50.** (+ EXP-83 hello-world as a cheap parallel.)
Rationale: EXP-30 is the keystone (KE-1) — reframed per DEC-070 as **two classes: a tiny pinned set
(`world`, `emotion`, persona, session window, `active_quest`, marked `pinned:true`) + one ranked pool filled
by `priority × relevance`**. This *deletes* the "Tier-A exceeded → canned" failure by construction and is the
hard/soft prerequisite for every memory/knowledge/dialogue item below. With it in, EXP-32 (anti-hallucination)
and EXP-31 (retrieval precision@k) turn the two asserted buyer metrics into **reported numbers** (no SLA gate,
OQ-D2). EXP-50 (affinity) is schema-free (fills `relates_to.yaml:11-12`, reuses the `event` node for any
history — OQ-A3). **All Phase 1 items are S/M, none needs a schema call.**

### Phase 2 — Dialogue + Gossip showcase (THE priority)
**Dialogue:** EXP-53 (knowledge learning), EXP-11 (player-scoped recall), EXP-17 (forgetting curve + `never_forget`).
**Gossip:** EXP-15 (distortion-strategy registry) → EXP-16 (belief/secret-selective, prompt-driven distortion).
**Demo (make it visible & playable):** EXP-81 ("remembers you"), EXP-84 (telephone-diff view), EXP-85
("I don't know" beat), EXP-92 (determinism toggle), EXP-91 (relationship ticker), EXP-80 (free-play depth),
EXP-93 (bribe fix), EXP-95 (scenario picker).
Rationale: this is where the product proves itself. EXP-53 is now **M, not L** (DEC-072: single-pass
`learned_facts` output, writes to existing `BELIEVES` edge with 3 added provenance fields — no second LLM
pass, no `LEARNED_FROM` edge), so the learn→ground→answer moat ships here, measured by EXP-32. Gossip
mechanics are **expanded now** (EXP-15/16, pulled up from the old Phase 3) and surfaced in the demo
(EXP-84/92). The KE-4 distortion registry also fixes a live "prompt strings outside prompts/" violation
(`gossip_distort.py:94-101`). The demo is treated as a **playable game to strengthen**, not a recording.

### Phase 3 — Agentic NPCs
**EXP-10 (proactive dialogue + new WS `proactive_line` push, OQ-D8/9), EXP-51 (GOAP — goal `urgency` vs
routine, OQ-D5), EXP-52 (reputation propagation), EXP-13/EXP-14 (EmotionModelProtocol + persistent emotion).**
Rationale: with the core proven, make the world act on its own. EXP-10 adds the public WS push surface so an
NPC can hail the player. EXP-51 uses the existing `goal.urgency` field (no schema, no LLM threshold).
KE-3 (`EmotionModelProtocol`) is a pure-additive OCP refactor unlocking emotion variants.

### Phase 4 — World richness & deep systems (schema-heavy / niche, later)
**EXP-87 (location hierarchy — `PART_OF` edge + `location_writer.py`, APPROVED DEC-071), EXP-19 (branching
quests), EXP-18 (semantic memory formation), EXP-21 (world-aware quests), EXP-40 (trade dispatch),
EXP-42 (niche-engine expansions: investigation/skill/treaty/military/etc. — planned + demo-integrated but
deprioritized), EXP-55 (second-order theory-of-mind — future, via memories for now per OQ-D6).**
Dropped: **EXP-56 (localization), EXP-57 (voice/STT)** — out of scope.

---

## 4. Top 5 do-next (with one-line justifications)

1. **EXP-30 — Context: pinned-core + ranked pool (DEC-070, supersedes ISSUE-059 fix).** The keystone:
   one/two-module change that *deletes* the canned-dialogue failure and unblocks the whole dialogue+memory
   line. Pinned set is small and bounded by construction, so "Tier-A exceeded" can't recur.
2. **EXP-50 — Relationship/affinity engine.** Highest value-per-effort (S): fills already-declared
   `relates_to.yaml:11-12` fields, reuses the `event` node for history (no new node), kills `if trust > N`
   magic numbers, delivers the expected "relationships" headline.
3. **EXP-53 — Dialogue-driven knowledge learning (now M, DEC-072).** The anti-hallucination moat: NPCs
   learn facts the player states via a single-pass `learned_facts` output → `BELIEVES` edge (player-sourced
   knowledge is legitimate). The core of the dialogue showcase.
4. **EXP-32 — Measured anti-hallucination eval.** Turns the #1 product claim (SEV-01, *asserted not proven*)
   into a reported number; the rubric that keeps EXP-53 honest.
5. **EXP-15 → EXP-16 — Expand gossip mechanics now.** Open the closed distortion if-chain into a strategy
   registry, then make distortion belief/secret-selective and prompt-driven — the second headline system,
   surfaced in the demo via the telephone-diff view (EXP-84).

---

## 5. Keystone enablers (the 2–3 that unlock the most downstream value)

1. **KE-1 / EXP-30 — Tier-A bounding.** *The* keystone. Hard/soft-unblocks EXP-81, EXP-32, EXP-11,
   EXP-17, EXP-53, EXP-55, EXP-10. Fix one module → three+ high-value items unlock. Already has the data
   model (`priority` exists on Tier-A items); only the trim policy is missing. **Lowest cost, highest leverage.**
2. **KE-2 — `learned_facts` on the dialogue output + `graph/knowledge_writer.py` (DEC-072).** The gate for
   the learning moat (EXP-53). **Reduced from the original `LEARNED_FROM`-edge design:** facts ride the
   *existing* single dialogue LLM pass as a `learned_facts` field and persist to the existing `BELIEVES`
   edge (+3 optional provenance fields on `believes.yaml`). The only graph touch is those optional fields.
3. **KE-6 / ISSUE-055 — stable-id idempotent seeding.** Low-risk, no-schema enabler for every
   demo-scale/replay item (EXP-87, EXP-92, EXP-95) and reliable seeding of the strengthened playable demo.

Secondary refactor enablers (no schema, unlock variant families): **KE-3** `EmotionModelProtocol`
(→ EXP-13/14/41), **KE-4** distortion-strategy registry (→ EXP-15/16/84). **KE-5** location hierarchy
(ISSUE-057, `PART_OF`) is schema-gated and **off** the top-5 critical path — flat world expansion needs it not.

---

## 6. Dependency graph (who unblocks whom)

```
EXP-30 (pinned-core + ranked pool) ──┬─► EXP-32 (anti-hallucination eval) ──► EXP-53 (knowledge learning)
                                     ├─► EXP-81 (remembers-you demo)
                                     ├─► EXP-11 (player-scoped recall) ──► EXP-17 (forgetting + never_forget)
                                     └─► EXP-10 (proactive dialogue) ◄── EXP-51 (GOAP intent, optional)

EXP-50 (affinity, schema-free) ──┬─► EXP-52 (reputation propagation)
                                 └─► EXP-91 (relationship ticker demo)

KE-4 (distortion registry) ──► EXP-15 ──► EXP-16 ──► EXP-84 (telephone demo) ─┐
                                                       EXP-92 (determinism)  ─┴─► gossip showcase
KE-3 (emotion protocol)    ──► EXP-13 ──► EXP-14
KE-2 (learned_facts output + knowledge_writer; reuse BELIEVES) ──► EXP-53
KE-6 (stable-id seeding)   ──► EXP-87, EXP-92, EXP-95
EXP-40 (trade dispatch)    ──► EXP-51 (GOAP action execution)
ISSUE-057 / KE-5 (PART_OF, APPROVED) ──► EXP-87 (hierarchy)

Deferred: EXP-55 (second-order ToM → via memories for now). Dropped: EXP-56, EXP-57.
Independent / no blockers: EXP-31 (retrieval eval), EXP-83 (hello-world), EXP-80 (free-play),
                           EXP-93 (bribe → HAS_REPUTATION_WITH), most demo polish.
```

---

## 7. Cross-references
- Per-proposal mini-specs: `ENGINE_GAPS.md` (EXP-10..42), `NEW_ENGINES.md` (EXP-50..57), `DEMO_EXPANSIONS.md` (EXP-80..99).
- Architecture verdicts, schema-call flags, keystone analysis: `FEASIBILITY.md`.
- The rubric every score traces to: `BUSINESS_INTENT.md`.
- Human-only decisions + assumed defaults: `OPEN_QUESTIONS.md`.
