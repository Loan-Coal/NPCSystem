# NPC Engine — Eval Suite Design & Coverage Analysis (overnight orchestration prompt)

**Purpose:** Design the test/eval strategy that lets us *credibly* claim NPC Engine is a
**game- and story-agnostic** RPG middleware engine — not a backend for one demo. Map current
behavioral-eval coverage across ALL engines, expose where the suite structurally cannot test an
engine today, design the world matrix and cross-engine scenario format needed to fix that, and
produce a scored, sequenced roadmap a human implements phase by phase. Gaps in engines surface
as engines that would produce bad/empty/incoherent output under eval — **eval-driven gap-finding**,
not code re-reading.

**Mode:** fully autonomous (overnight, no human checkpoints) · parallel split-role agents ·
**READ-ONLY except the `.md` deliverables below.** Do NOT modify source, tests, prompts, configs,
seeds; do NOT run migrations or Docker. Running the *existing* eval suite to capture a baseline is
permitted ONLY if a server is already reachable at localhost:8000 — otherwise derive coverage
statically. **Cost: unconstrained — be thorough. You are the orchestrator.**

**This run STOPS before implementation.** Its output is design docs + roadmap phases. No new seeds,
no runner code, no eval cases are written this run — they are *specified* precisely enough that a
later session builds them without re-deriving context.

> Companion to `EXPANSION_ANALYSIS.md` (what to build next) and `EVAL_STRATEGY.md` (the rubric).
> This run decides *how we prove the engines work, everywhere*. Reference those; do not duplicate them.

---

## 0. Deliverables & acceptance

Write everything under `project-harness/eval-design/` (create the dir). Additionally, APPEND
(never overwrite) a clearly-marked new section to `project-harness/EVAL_STRATEGY.md` and to
`project-harness/EXPANSION_ANALYSIS.md`, and add the new phases to `project-harness/ROADMAP.md`.
The run is complete only when all of these exist, are concrete (cite `file:line`, specify real
worlds/triggers/assertions/judge prompts), and cross-reference each other:

1. `EVAL_COVERAGE_MAP.md` — per engine in `src/npc_engine/engines/`: what behavioral eval coverage
   exists today (map to specific `evals/cases/*.yaml`), and the testability verdict: **testable
   now / blocked by harness / no path**. Must state the keystone finding explicitly (see §2 L0).
2. `HARNESS_EXTENSION_SPEC.md` — the design for evolving `evals/runner.py` from a dialogue-only
   black box into a multi-step, graph-state-asserting scenario runner. The keystone deliverable.
3. `WORLD_MATRIX.md` — the set of eval worlds (existing + proposed), each with the engines it
   exercises and the assumptions it is engineered to expose. MUST include at least one deliberately
   contrasting **non-fantasy** world (you choose the genre/social structure; justify the choice by
   what hardcoded fantasy assumption it stresses).
4. `ENGINE_EVAL_PLANS.md` — per engine, a tiered set of eval specs (§3 schema). Tier 1 (demo-critical)
   goes deep; Tiers 2–3 get a first-pass plan. Every Tier-1 engine gets at least one **cross-world
   invariant** (agnosticism probe).
5. `EVAL_ROADMAP.md` — the synthesis: every eval-build task scored (value × effort × unblocks) and
   sequenced into phases, with a Top-5 do-next and a dependency graph. Harness extension and the
   contrasting world are likely keystone enablers — say so and order accordingly.
6. `OPEN_QUESTIONS.md` — decisions only the human can make, each with the educated-guess default you
   assumed during the run (mirror EXPANSION_ANALYSIS attestation style). Never stall overnight.

**Plus appends:** a new dated section in `EVAL_STRATEGY.md` (the extended rubric + world matrix
summary + harness model), a back-reference section in `EXPANSION_ANALYSIS.md` linking eval-driven
gaps to its `ENGINE_GAPS.md`/`EXP-NN` items, and the new phases appended to `ROADMAP.md`.

**Acceptance:** every eval spec is concrete enough to implement cold (names world, setup, trigger
sequence, assertion target, matcher, exact judge rubric). No "add tests for X." No vague coverage
claims. No source/test/config/prompt/seed changes. The roadmap, not the idea list, is the value.

---

## 1. Ground truth — read these first (priority order)

The harness reality is the anchor. Read these before proposing anything:

- `evals/runner.py` — **read in full.** Confirm the dialogue-only constraint: every case POSTs to
  `/v1/dialogue`; cases without `input.player_message` are SKIPPED (the lines that print
  "case targets a non-dialogue endpoint, not supported by this runner"). This is the keystone fact.
- `evals/matchers.py`, `evals/summary.py`, `evals/report.py` — the matcher vocabulary, the
  guard-battery / guarantee logic, the report shape. Know what assertion kinds exist before inventing.
- `evals/retrieval_runner.py`, `evals/retrieval_matchers.py`, `evals/retrieval_summary.py` — the
  separate retrieval eval path (a precedent for a non-dialogue eval runner — study how it works).
- `evals/cases/*.yaml` — the current corpus (overwhelmingly dialogue voice + anti-hallucination
  guards). Catalogue which engine each case actually exercises.
- `seeds/worlds/seed_tavern_world.py`, `seeds/worlds/seed_village_world.py` — the two existing
  worlds. Note both are medieval-fantasy (the agnosticism weakness).
- `src/npc_engine/engines/**` — the full engine inventory. Read each engine's module docstring +
  public surface to know what it does and what a "correct output" would be.
- `src/npc_engine/api/**` — the HTTP/WS route surface. This is the *vocabulary of scenario steps*:
  which endpoints let an eval drive a tick, advance the clock, trigger gossip, generate a quest,
  execute a trade, and READ resulting graph state (the runner already uses
  `GET /v1/graph/nodes/Character/{id}` — find the rest).
- `src/npc_engine/type_registry/base_nodes/` + `base_edges/` — the graph vocabulary; check it for
  fantasy-specific assumptions that would break agnosticism.
- `src/npc_engine/prompts/**` — check runtime prompts for hardcoded genre/setting assumptions
  (the dialogue/gossip/quest prompts are the likeliest place agnosticism leaks).
- `project-harness/EVAL_STRATEGY.md`, `EXPANSION_ANALYSIS.md` (+ any `expansion/*.md` already
  produced), `FEATURES.md`, `ROADMAP.md`, `ISSUES.md`, `DECISIONS.md` (esp. DEC-068 single-deploy).

If docs are silent or contradictory, make an educated guess, proceed, log it in `OPEN_QUESTIONS.md`.

---

## 2. Analysis lenses (parallel agents)

Each lens is read-only and writes (or returns for the orchestrator to write) its deliverable. Pass
each agent the §1 reading list, the §3 schema, and its mandate. Tooling note: `architect`/reviewer
agents have NO Write tool — the orchestrator persists their output. `general-purpose` agents write
their own files; prefer them for the writing lenses.

### L0 — Baseline & harness reality (run FIRST; others depend on it) → feeds EVAL_COVERAGE_MAP.md
Establish the ground truth the rest builds on. From `evals/runner.py`, state precisely what the
harness can and cannot test today (the dialogue-only constraint, the silent-skip behavior, the
guard-battery guarantee logic). If a server is already up, run the existing suite and capture the
baseline pass/skip counts; otherwise derive coverage statically from the cases + runner. Output: the
keystone finding, and a table of every engine → (has cases? / runnable today? / silently skipped?).

### L1 — Per-engine coverage & testability (`general-purpose`) → EVAL_COVERAGE_MAP.md
For EACH engine, map existing `evals/cases` to it, classify **testable now / blocked by harness /
no path**, and define what a *correct* observable output looks like (response field? graph node/edge
mutation? WS event? scheduled tick effect?). This defines the assertion target each future eval needs.

### L2 — Harness extension design (`architect` → orchestrator saves HARNESS_EXTENSION_SPEC.md)
Design the evolution of `evals/runner.py` (or a sibling scenario runner, à la `retrieval_runner.py`)
into a multi-step engine that can: (a) declare an ordered trigger sequence of API/WS/clock steps;
(b) assert on **graph state after the action** via existing read endpoints, not just the chat reply;
(c) keep the existing dialogue cases working unchanged (backward-compatible case schema). Specify the
new YAML case fields, the step types, the new matcher kinds needed (e.g. graph-node-field, edge-exists,
edge-delta, ws-event-received), and the layer/file placement honoring the repo's 300-line + SRP rules.
Flag anything that needs a new API read endpoint as a prerequisite (route it to OPEN_QUESTIONS / a
ROADMAP enabler). This is the keystone — most eval coverage is blocked on it.

### L3 — World matrix & agnosticism design (`general-purpose`) → WORLD_MATRIX.md
Design the eval world set. Keep tavern + village; add at least one deliberately contrasting
**non-fantasy** world chosen to expose hardcoded assumptions (candidate territory — pick & justify:
near-future space station, modern-day city/corporate, post-apocalyptic, non-feudal society). For each
world: NPC archetypes, factions/social structure, epoch/world-state, the events/gossip chains it
sets up, and — critically — **which engines it exercises and which assumption it stresses**. Define
the **agnosticism probe** concept: a cross-world invariant is a behavior an engine must reproduce
structurally identically across genres, where the only difference is graph data, never code. Identify
the highest-value invariants (e.g. gossip distortion hedging, reputation-gated tone, emotion coloring)
and which contrasting world best falsifies a fantasy assumption.

### L4 — Per-engine eval plans, tiered (`general-purpose`) → ENGINE_EVAL_PLANS.md
Produce eval specs (§3 schema) per engine. **Tier 1 (demo-critical) goes deep:** dialogue, gossip,
emotion + mood, quest + quest_generation, faction_politics, economy. **Tiers 2–3 get a first-pass
plan** (you finalize the tier-2/3 assignment by tracing each engine to business value in
BUSINESS_INTENT / FEATURES). Every Tier-1 engine gets ≥1 cross-world invariant. Each spec must name
its assertion target and whether it works today or needs a HARNESS_EXTENSION item. Where a spec would
predictably fail because the engine is incomplete, mark it as an eval-driven gap and link it to
EXPANSION_ANALYSIS's `ENGINE_GAPS.md` / `EXP-NN`.

### L5 — Synthesis & roadmap (orchestrator, after L0–L4) → EVAL_ROADMAP.md + appends
Consolidate into one scored, sequenced plan. Score each eval-build task on **value** (does it prove a
demo-critical or agnosticism claim?), **effort** (S/M/L/XL), **unblocks** (does it enable other evals?),
and **dependency**. Phase 1 = the keystone enablers (harness extension + contrasting world) plus the
Tier-1 deep evals that ride on them. Produce a Top-5 do-next, a dependency graph, and the 2–3 keystone
enablers. Then append the new phases to `ROADMAP.md` and the summary sections to `EVAL_STRATEGY.md`
and `EXPANSION_ANALYSIS.md` as specified in §0.

---

## 3. Shared eval-spec schema (every proposed eval uses this)

```
### <EVAL-NN>: <short title>
Engine(s): <which engine(s)>            Tier: 1 | 2 | 3
Capability under test: <the specific behavior/contract being verified>
World(s): <which world(s); name the contrasting world if this is a cross-world invariant>
Setup: <seed state / context_overrides / reputation / world epoch>
Trigger sequence: <ordered API/WS/clock steps to drive the engine; "single /v1/dialogue POST" if so>
Assertion target: <response field | graph node/edge state after action | WS event | log/seed>
Matchers: <existing matcher kind(s), or "NEW: <name>" + one-line spec for HARNESS_EXTENSION_SPEC>
Judge rubric: <the exact LLM-judge prompt text, or "deterministic — no judge">
Agnosticism probe: <the cross-world invariant asserted, or "n/a">
Harness support: <works today | needs HARNESS_EXTENSION item <id>>
Expected result today: <pass | fail | silently-skipped | not-yet-runnable>
Gap flagged: <engine incompleteness this exposes → ENGINE_GAPS / EXP-NN, or "none">
First slice: <smallest version that proves the eval is wired correctly>
```

---

## 4. Rules of engagement

- **Read-only except the §0 deliverables + the three appends.** No source/test/config/prompt/seed
  edits. Do not run the app/Docker/migrations (one exception: running the *existing* eval suite for a
  baseline IF a server is already up).
- **Eval-driven gaps only.** An engine gap is something an eval would expose, not an opinion from
  reading code. Tie every flagged gap to a concrete failing-or-impossible eval spec.
- **Agnosticism is the thesis.** Every Tier-1 engine needs a cross-world invariant. A claim of
  "game-agnostic" backed only by two fantasy worlds is rejected — the contrasting world is mandatory.
- **Respect the architecture.** Harness extension must honor the layer model, the 300-line/SRP/Pydantic
  rules in `project-harness/CLAUDE.md`, and DEC-068. Flag any schema/API change for a human DECISIONS call.
- **Concrete over abstract.** Cite `file:line`; write real trigger sequences, real assertion targets,
  real judge prompts. A spec a future session can't implement without re-deriving context is a failure.
- **Educated guesses, logged.** Ambiguity → assume the most demo/business-aligned answer, proceed,
  record in OPEN_QUESTIONS.md with the default used.
- **Build on, don't duplicate.** Cross-reference EVAL_STRATEGY.md and EXPANSION_ANALYSIS.md; extend them.

## 5. Phase plan (autonomous — no human checkpoints)

1. **L0 first** — establish the harness reality (the keystone finding).
2. **L1, L3, L4 in parallel**; **L2 (harness design)** may start once L0/L1 expose the constraint.
3. **L5 synthesis** — orchestrator merges into EVAL_ROADMAP.md and performs the three appends.
4. **Compile OPEN_QUESTIONS.md** — every assumption + every human-only decision, each with its default.
5. **Final orchestrator message** — a tight executive brief: the keystone finding, the world matrix
   (incl. the contrasting world chosen + why), the Top-5 do-next, the keystone enablers, and the open
   questions. End there (do not implement).

## 6. Morning-review readiness checklist (the run must satisfy)

- [ ] All six deliverables exist under `project-harness/eval-design/` and cross-reference each other.
- [ ] EVAL_COVERAGE_MAP states the dialogue-only keystone finding with `file:line` evidence.
- [ ] HARNESS_EXTENSION_SPEC defines new case fields, step types, matcher kinds, and file placement,
      backward-compatible with existing dialogue cases.
- [ ] WORLD_MATRIX includes ≥1 non-fantasy contrasting world with a justified assumption-stress rationale.
- [ ] ENGINE_EVAL_PLANS covers every engine; Tier-1 engines are deep and each has a cross-world invariant.
- [ ] EVAL_ROADMAP has a scored table + Top-5 + dependency graph + named keystone enablers.
- [ ] The three appends (EVAL_STRATEGY.md, EXPANSION_ANALYSIS.md, ROADMAP.md) are present and marked.
- [ ] OPEN_QUESTIONS lists each human decision with a default (nothing blocked).
- [ ] No source/config/test/prompt/seed modified; app not run (except optional baseline).
- [ ] Final summary message is a human-readable executive brief.
