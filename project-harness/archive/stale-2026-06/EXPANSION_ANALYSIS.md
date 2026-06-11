# NPC Engine — Expansion Analysis (overnight orchestration prompt)

**Purpose:** Not a review. An **expansion analysis**: surface high-value ways to grow the product —
first the **engines** (missing features in existing engines; entire missing engines), then the
**demo game** — all grounded in the **business desires expressed in the documentation**. Produce a
prioritized, review-ready expansion roadmap a human can act on tomorrow morning.

**Mode:** fully autonomous (overnight, no human checkpoints) · **parallel split-role agents** ·
**READ-ONLY** (analysis + design docs only; do NOT modify source, tests, configs, or run the app).
**Cost:** unconstrained — be thorough. **You are the orchestrator.**

> Companion to `FINAL_REVIEW.md` (which hardens what exists). This one decides *what to build next*.

---

## 0. Deliverables & acceptance

Write everything under `project-harness/expansion/` (create the dir). The run is complete only when
all of these exist, are concrete (cite `file:line` and propose real schema/API), and are internally
consistent:

1. `BUSINESS_INTENT.md` — the extracted product thesis, target customer, and the feature ambitions
   the documentation explicitly or implicitly commits to. Everything else must trace back to this.
2. `ENGINE_GAPS.md` — per existing engine: missing/incomplete features vs the business intent and the
   competitive bar for "NPCs with persistent memory, relationships, and emotion."
3. `NEW_ENGINES.md` — proposed entire new engines/domains the vision implies but that don't exist.
4. `DEMO_EXPANSIONS.md` — how to make the demo a stronger showcase + sales artifact.
5. `EXPANSION_ROADMAP.md` — the synthesis: every proposal scored (value × effort × business-fit ×
   architecture-fit) and sequenced into phases, with a clear "top 5 do-next" and dependency ordering.
6. `OPEN_QUESTIONS.md` — decisions only the human can make, each with your educated-guess default
   (the one you assumed during the run) so work isn't blocked. Mirror the FINAL_REVIEW attestation
   style: list what you assumed and why.

**Acceptance:** every proposed expansion is a *mini-spec* concrete enough that a future session could
start it without re-deriving context (see the §3 schema). No vague "add more AI." No source changes.

---

## 1. Ground truth — read these first (in priority order)

The analysis is **documentation-grounded**. Extract intent from, and cite, these:

- `project-harness/CLAUDE.md` — Orientation ("game backend… persistent memory, relationships,
  emotional state… HTTP+WS API for licensing to game studios as middleware"), the layer model, the
  SOLID/OCP rules (these constrain *how* expansions must be added).
- `project-harness/ROADMAP.md` — the stated plan and ambitions.
- `project-harness/FEATURES.md` — the current capability inventory (internal + external). The gap
  analysis is literally "intent minus FEATURES.md."
- `project-harness/FINAL_REVIEW_FINDINGS.md` §L7 (expansion readiness) — already-identified OCP seams,
  blockers, and the ranked "top expansion blockers." **Build on this; do not redo it.**
- `project-harness/ISSUES.md` — esp. ISSUE-057 (location hierarchy / `PART_OF`), ISSUE-055
  (client-supplied stable ids / seeding contract), ISSUE-059 (tier-A context budget). These are
  pre-identified expansion enablers/blockers.
- `project-harness/DECISIONS.md` — esp. DEC-068 (one deployment per studio — no multi-tenant), which
  bounds the design space.
- `src/npc_engine/engines/` — the actual engine inventory (dialogue, gossip, emotion, mood,
  memory_consolidation, quest, quest_generation, events, faction_politics, story_pacing, routine,
  skill, military, clique, chapter, interaction, llm, tts, …). Read each engine's module docstring +
  public surface to know what exists.
- `src/npc_engine/type_registry/base_nodes/` + `base_edges/` — the graph vocabulary you can extend
  with new YAML (the primary OCP extension seam).
- `demo_game/` — `run.py`, `run_scenes.py`, `seed.py`, `client.py`, `ui/` — what the demo shows today.
- Any README / docs/ / pitch / vision files found at repo root or `docs/`.

If the docs are silent or contradictory on a point, make an **educated guess**, proceed, and record
it in `OPEN_QUESTIONS.md` (do not stall).

Optional (only after the docs): light competitive grounding via WebSearch on the NPC-AI-middleware
category (e.g. Inworld, Convai, character engines) to calibrate the feature bar — but the **primary
driver is the documentation's stated desires**, not the market.

---

## 2. Analysis lenses (parallel agents)

Launch these in parallel. Each is read-only and writes its own deliverable. **Tooling note (learned
the hard way):** `architect`/reviewer agents are read-only with NO Write tool — if you use one, the
orchestrator must persist its returned output to the target file. `general-purpose` agents can write
their own files; prefer them for the writing lenses. Pass each agent the §1 reading list, the §3
schema, and its mandate below.

### X0 — Business intent (`general-purpose`) → `BUSINESS_INTENT.md`  *(run FIRST; others depend on it)*
Extract the product thesis from the docs: who is the customer (game studios), what is the promised
value (NPCs with persistent memory/relationships/emotion as licensable middleware), the integration
model (DEC-068: one local deployment per studio/game), and every feature ambition the docs state or
strongly imply. Produce: a one-paragraph thesis, a bulleted "explicit commitments" list (with file
cites), a bulleted "implied ambitions" list, and the success criteria a studio would judge the engine
by. This is the rubric every other lens scores against.

### X1 — Existing-engine feature gaps (`general-purpose`) → `ENGINE_GAPS.md`
For EACH engine in `src/npc_engine/engines/`, assess against BUSINESS_INTENT + the competitive bar:
what is missing, shallow, or stubbed? Examples of the *kind* of gap to hunt (derive the real list
from the code): dialogue has no long-term player-specific memory recall surfaced in-conversation?
emotion model is fixed VAD with no personality modulation? gossip can't target beliefs/secrets
selectively? quests are template-bound with no branching/consequence chains? no relationship/affinity
engine distinct from raw relation deltas? memory has no forgetting/salience decay curve? Cite
`file:line`. For each gap output a §3 mini-spec.

### X2 — Missing engines / new domains (`general-purpose`) → `NEW_ENGINES.md`
Propose entire engines the vision implies but that don't exist. Reason from BUSINESS_INTENT + the
graph's latent capabilities. Candidate territory to evaluate (keep, drop, or add your own, each
justified): a dedicated **relationship/affinity** engine; **economy/trade** simulation; **reputation
propagation** as a first-class engine; **NPC goal/planning (GOAP-style) autonomy**; **daily-life
scheduling / world-simulation** tick; **dynamic world-event/director** engine; **dialogue-driven
knowledge extraction** (NPCs learn facts from the player); **player-modeling** (NPC theory-of-mind of
the player); **group/crowd dynamics** beyond cliques; **localization / multi-language**;
**voice/STT** input. For each: purpose, the new `type_registry` nodes/edges (as concrete YAML
sketches), engine inputs/outputs, how it composes with existing engines, OCP fit, and a §3 mini-spec.
Respect the layer model and DEC-068 (no multi-tenant).

### X3 — Architecture & feasibility fit (`architect`) → returned inline; orchestrator saves to `FEASIBILITY.md`
For the candidate expansions from X1/X2, assess fit against the current architecture: does the OCP
registry / `type_registry` YAML / Protocol seams support it as a new-file add, or does it require
editing closed modules (cross-ref L7 findings: distortion registry L7-01, location writer L7-02,
backend Literal L7-03 (now fixed), emotion-model protocol L7-06)? Identify shared enablers that
unblock multiple expansions (e.g. ISSUE-057 location hierarchy, ISSUE-055 stable-id seeding, ISSUE-059
tier-A bounding, an `EmotionModelProtocol`, a distortion-strategy registry). Flag any expansion that
needs a schema or layer change (those need a human DECISIONS call). Give each a rough effort
(S/M/L/XL) and a "prerequisite enablers" list.

### X4 — Demo-game expansion (`general-purpose`) → `DEMO_EXPANSIONS.md`
Two sub-goals. (a) **Showcase coverage:** cross-reference FEATURES.md against what `demo_game/`
actually demonstrates — which shipped engine capabilities are NOT visible in the demo, and what
demo additions would surface them (the demo is the studio's first impression). (b) **Demo as
product:** richer scenarios, more NPCs/locations (ties to ISSUE-057 hierarchy), interactive UI
features in `demo_game/ui/`, a "sandbox" mode, recording/marketing affordances, an integrator
"hello-world" quickstart that proves the one-deployment pitch. Note current demo limits (e.g.
ISSUE-060 ACT-3 bug, scripted-only flow). Each idea as a §3 mini-spec.

### X5 — Synthesis & prioritization (orchestrator, after X0–X4) → `EXPANSION_ROADMAP.md`
Consolidate every proposal into one ranked table scored on: **business-fit** (traceability to
BUSINESS_INTENT), **value** (studio-perceived impact), **effort** (from X3), **architecture-fit**
(new-file-add vs closed-module-edit), and **dependency** (what unblocks what). Produce: a sequenced
phase plan (Phase 1 = highest value + lowest friction + unblocks others), an explicit **Top 5
do-next** with one-line justifications, and a dependency graph (which enablers precede which features).
Call out the 2–3 "keystone enablers" that unlock the most downstream value.

---

## 3. Shared mini-spec schema (every proposed expansion uses this)

```
### <EXP-NN>: <short title>
Type: existing-engine-gap | new-engine | demo
Business rationale: <which BUSINESS_INTENT commitment/ambition this serves; cite the doc>
What it does: <one paragraph, concrete>
Current state: <what exists today; file:line of the gap or the seam to build on>
Graph/schema additions: <new type_registry nodes/edges as YAML sketch, or "none">
API surface: <new/changed HTTP or WS routes, or engine-internal only>
Composition: <how it interacts with existing engines/services; layer it lives in>
Architecture fit: <new-file-add via which OCP seam | requires editing X | needs DECISIONS approval>
Prerequisite enablers: <ISSUE-0NN / other EXP-NN that must land first, or "none">
Effort: S | M | L | XL        Value: low | med | high      Business-fit: low | med | high
Risks / unknowns: <technical or product risks>
First slice: <the smallest shippable increment that proves the idea>
Open questions: <route to OPEN_QUESTIONS.md if it needs a human call>
```

---

## 4. Rules of engagement

- **Read-only.** Do not modify source, tests, prompts, configs; do not run the app, migrations, or
  Docker. This is analysis. (The only writes are the `project-harness/expansion/*.md` deliverables.)
- **Documentation-grounded.** Every proposal traces to BUSINESS_INTENT (which traces to the docs).
  No feature justified only by "it'd be cool."
- **Respect the architecture.** Proposals must fit the layer model + SOLID/OCP rules, or explicitly
  flag the rule/schema change for a human DECISIONS call. Honor DEC-068 (single deployment, no
  multi-tenant) — do not propose multi-tenant features.
- **Concrete over abstract.** Cite `file:line`; sketch real `type_registry` YAML and route shapes.
- **Educated guesses, logged.** When the docs are ambiguous, assume the most business-aligned answer,
  proceed, and record the assumption + alternatives in `OPEN_QUESTIONS.md`. Never stall overnight.
- **Prioritize ruthlessly.** A long unranked idea list is a failure. The value is the *sequencing*.

## 5. Phase plan (autonomous — no human checkpoints)

1. **X0 first** — produce BUSINESS_INTENT.md (the rubric).
2. **X1, X2, X4 in parallel** (+ X3 feasibility, which may start once X1/X2 have draft candidates).
3. **X5 synthesis** — orchestrator merges into EXPANSION_ROADMAP.md.
4. **Compile OPEN_QUESTIONS.md** — every assumption made + every human-only decision, each with the
   educated-guess default used.
5. **Final orchestrator message** — a tight executive summary: the thesis, the Top 5 do-next, the
   keystone enablers, and the list of open questions awaiting the human. End there (do not implement).

## 6. Morning-review readiness checklist (the run must satisfy)

- [ ] All six deliverables exist under `project-harness/expansion/` and cross-reference each other.
- [ ] Every proposal uses the §3 schema and cites real files/schema.
- [ ] EXPANSION_ROADMAP.md has a scored table + Top 5 + dependency ordering + keystone enablers.
- [ ] OPEN_QUESTIONS.md lists each human decision with an educated-guess default (nothing blocked).
- [ ] No source/config/test was modified; app was not run.
- [ ] Final summary message is a human-readable executive brief.
