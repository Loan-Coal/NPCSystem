# NPC Engine — Demo-Game Full Expansion Review (orchestration prompt)

**Purpose:** Turn the pygame demo from a *playable skeleton* into an **actual content-rich game**,
grounded in the engine capabilities that already exist. Three pillars:
1. **Surface dormant engines as playable mechanics** — `treaty`, `oath`, `story_pacing`, `chapter`
   (and any other built-but-unsurfaced engine the scan finds) become things the player *does and sees*.
2. **Add content** — more NPCs/locations/quests, branching arcs, replayable scenarios.
3. **Deepen the win/lose economy** — beyond today's single faction-standing threshold.

Produce a prioritized, review-ready expansion roadmap a human can act on. **Stay in pygame.**

**Mode:** fully autonomous (no human checkpoints) · **parallel split-role agents** · **READ-ONLY**
(analysis + design docs only; do NOT modify source, tests, configs, seeds, or run the app).
**Cost:** unconstrained — be thorough. **You are the orchestrator.**

> Sibling to `archive/stale-2026-06/FINAL_REVIEW.md` (hardens what exists) and
> `archive/stale-2026-06/EXPANSION_ANALYSIS.md` (grows the *engine*). This one grows the **demo into a
> game** using engine capability that is already built — it is demo-side and content-side, not a
> ground-up engine expansion. Where a dormant engine has no REST surface, this review *names the
> engine-side enabler* but does not design the engine itself (that routes back to EXPANSION_ANALYSIS).

---

## 0. Hard constraints (these bound every proposal — internalize before designing)

- **PYGAME ONLY.** Do not propose Unity/Unreal/web work. The Unity/Unreal SDK is Phase X — explicitly
  **out of scope** here. If a mechanic is impossible in `demo_game/` (pygame-ce), say so and drop it;
  do not escalate it to an engine port.
- **DEMO IS A REST/WS CLIENT WITH ZERO `src/npc_engine` IMPORTS** (CLAUDE.md, SEV-02). Every player-
  facing mechanic must be reachable through `demo_game/client.py` (`EngineClient`) over HTTP/WS. This
  is the **reachability gate**: a dormant engine is only demo-surfaceable *today* if it already exposes
  an API route. If it does not, the proposal must flag the **engine-side route enabler** as a
  prerequisite (an engine task, not a demo task) and mark the demo work blocked on it.
- **VERIFY "ENGINE" MEANS GAMEPLAY, NOT INFRA.** Before proposing a mechanic for a candidate engine,
  confirm it is a *player-facing domain* engine — not infrastructure. (Known trap: `engines/contracts/`
  is the LLM prompt-contract / config loader — `contract_loader.py`, `*_engine.yaml` — **not** a
  gameplay engine; do not propose a "contracts mechanic".)
- **RESPECT THE WAIVERS & SIZE RULES.** `demo_game/` files already carry 300-line waivers
  (DEC-029/032/034/049/074/075) and several are large (`client.py` ~1524L, `seed.py` ~1265L). New demo
  code is still subject to the 300-line / 40-line / 3-nesting rules; if a proposal forces a large file,
  name the split.
- **Seeding is idempotent and stable-id (KE-6).** New content lands via the existing seed contract
  (`demo_game/seed.py` + `EngineClient` create calls with client-supplied `id`s), so `make demo-seed`
  twice stays duplicate-free. Do not propose a parallel seeding path.

---

## 1. Deliverables & acceptance

Write everything under `project-harness/demo-expansion/` (create the dir). The run is complete only
when all of these exist, are concrete (cite `file:line`, name the real `EngineClient` method or the
missing route, sketch the real pygame UI surface), and cross-reference each other:

1. `DEMO_INTENT.md` — what the demo must prove (sales artifact for studios **and** a game a person
   would actually play), plus a **baseline inventory** of the *current* playable loop: win/lose
   conditions, scenarios, worlds, UI panels, pollers, and the content counts (NPCs / locations /
   quests / arcs). Everything else scores against this. *(produced FIRST; others depend on it)*
2. `DORMANT_ENGINES.md` — **Pillar 1.** Per dormant gameplay engine: capability, REST-route status
   (route file or "NONE → enabler needed"), `EngineClient` method status, and the concrete pygame
   mechanic + UI panel that surfaces it. One §3 mini-spec each.
3. `CONTENT_PLAN.md` — **Pillar 2.** New NPCs/locations/quests, branching arcs, replayable scenarios —
   each as a §3 mini-spec built on the existing seam (see §2 D2). Quantify the target content volume.
4. `ECONOMY_DEPTH.md` — **Pillar 3.** Win/lose beyond the single faction-standing threshold:
   multi-objective victory, resource/currency loops, faction tension, time/tick pressure, multiple
   distinct failure states, scoring/grading. One §3 mini-spec per mechanic.
5. `FEASIBILITY.md` — the reachability gate applied to every proposal: pure demo-side (client + UI) vs
   needs an engine-side route enabler vs needs a schema/DECISIONS call. Effort S/M/L/XL + prerequisite
   enablers. Names the **keystone enablers** (the 2–3 engine routes that unlock the most demo value).
6. `DEMO_EXPANSION_ROADMAP.md` — the synthesis: every proposal scored and sequenced into phases, a
   **Top 5 do-next**, a dependency graph, and a one-line answer to *"what is the smallest set of phases
   that makes this feel like a real game, not a tech demo?"*
7. `OPEN_QUESTIONS.md` — decisions only the human can make (e.g. "is the demo a sandbox or a 30-minute
   authored campaign?"), each with your educated-guess default so nothing is blocked.

**Acceptance:** every proposal is a *mini-spec* concrete enough that a future `/expand-next`-style
session could start it without re-deriving context. No vague "add more quests." No source changes.

---

## 2. Ground truth — read these first (in priority order)

The review is **code-grounded**. Extract from, and cite, these:

- `project-harness/CLAUDE.md` — the demo-as-standalone-client rule, the layer model, the demo world
  table (5 NPCs, 3 locations, stable IDs), and the `make demo*` command surface.
- `project-harness/ROADMAP.md` (clean forward) + `project-harness/archive/ROADMAP_phase14-26_2026-06-11.md`
  — the parked demo items (S17.9 niche engines, S21.6 demo file-size) and the Phase X SDK boundary.
- **The demo itself:** `demo_game/game_controller.py` (main loop), `demo_game/game_end_checker.py`
  (the win/lose math to deepen — Pillar 3 starts here), `demo_game/run.py` + `run_scenes.py`,
  `demo_game/scenarios/` (`run_tavern_intrigue.py`, `run_village_crisis.py` — the beat/arc structure),
  `demo_game/arc_choice.py` (the branching seam — Pillar 2), `demo_game/ui/` (every panel — what is
  already surfaced), the `*_poller.py` set (the live-state surfaces), and `demo_game/seed.py` (content
  seam — Pillar 2).
- **`demo_game/client.py` (`EngineClient`)** — the REST/WS surface. This is the *hard boundary* on what
  mechanics are reachable today. For each dormant engine, search here for an existing method.
- **The dormant engines** (Pillar 1): `engines/treaty/treaty_engine.py`, `engines/oath/oath_engine.py`,
  `engines/story_pacing/story_pacing_engine.py`, `engines/chapter/chapter_engine.py` — read each module
  docstring + public surface to know what mechanic it *could* drive. Then check
  `src/npc_engine/api/routes/` for a matching route (known: `treaties.py` exists; `oath`,
  `story_pacing`, `chapter` have **no** route → enabler needed). **Also scan all of `engines/` for any
  other built engine with ~zero `demo_game/` references** (grep each engine name) and triage it the
  same way — keep gameplay engines, drop infra (e.g. `contracts`, `llm`, `idempotency`,
  `embedding_invalidation`).
- `seeds/worlds/seed_village_world.py` + `seed_tavern_world.py` — content/seed patterns to reuse for
  new NPCs/locations/quests.
- `project-harness/DECISIONS.md` (demo waivers, KE-6 seeding) + `project-harness/ISSUES.md` (open
  demo-relevant items, incl. ISSUE-083 voice residual).

If the docs/code are silent or contradictory, make an **educated guess**, proceed, and record it in
`OPEN_QUESTIONS.md` (do not stall). Optional, only after the code: light grounding on what makes a
*systemic NPC sim* (e.g. immersive-sim / colony-sim loops) feel like a game — but the **primary driver
is the built engine capability**, not the genre.

---

## 3. Analysis lenses (parallel agents)

Launch in parallel. Each is read-only and writes its own deliverable. **Tooling note:**
`architect`/reviewer agents are read-only with NO Write tool — if you use one, the orchestrator must
persist its returned output to the target file. `general-purpose` agents write their own files; prefer
them for the writing lenses. Pass each agent the §2 reading list, the §4 schema, the §0 constraints,
and its mandate.

### D0 — Demo intent & baseline (`general-purpose`) → `DEMO_INTENT.md`  *(run FIRST; others depend on it)*
Define what the demo must prove: (a) a **sales artifact** — a studio's first impression of "NPCs with
persistent memory, relationships, emotion"; (b) an **actual game** — objectives, agency, consequence,
replayability, enough content to sustain a session. Then inventory the **current** playable loop from
the code (cite `file:line`): the win/lose conditions in `game_end_checker.py`, the scenarios in
`scenarios/`, the worlds in `seed.py`/`seeds/worlds/`, the UI panels + pollers, and the live content
counts. Output the rubric every other lens scores against, and a blunt one-paragraph verdict: *what is
the single biggest reason this currently reads as a demo, not a game?*

### D1 — Dormant-engine surfacing (`general-purpose`) → `DORMANT_ENGINES.md`  *(Pillar 1)*
For each dormant **gameplay** engine (`treaty`, `oath`, `story_pacing`, `chapter`, + any others the
grep-scan surfaces; **drop infra** per §0): (1) the player-facing fantasy it enables (e.g. broker a
treaty between factions; swear/break an oath with consequence; let `story_pacing` drive escalating
beats; show `chapter` as an in-game act/season banner). (2) **Reachability:** does an API route exist
(`api/routes/`)? does `EngineClient` have a method? If a route is missing, state the **engine-side
enabler** needed (new `api/routes/<x>.py` + `EngineClient` method) as a prerequisite — do **not** design
the engine internals. (3) The concrete pygame mechanic + the UI panel/poller that surfaces it (model
on the existing `ui/*_panel.py` + `*_poller.py` patterns). One §4 mini-spec each, with `reachability:`
filled.

### D2 — Content & scenarios (`general-purpose`) → `CONTENT_PLAN.md`  *(Pillar 2)*
Design more content on the existing seams: new NPCs/locations/quests via `seed.py` (KE-6 stable-id,
idempotent); **branching arcs** via `arc_choice.py`; **replayable scenarios** via the scenario
picker/menu (`ui/start_menu.py` + `scenarios/`) so a player can replay with different outcomes. Specify
target counts (e.g. N NPCs, M locations, K quests, B branch points) and how the new content exercises
the surfaced engines from D1 (a treaty quest, an oath-driven betrayal arc, a chapter-paced campaign).
Each idea a §4 mini-spec. Note any content blocked by an enabler (e.g. location hierarchy `PART_OF` for
nested places).

### D3 — Win/lose economy depth (`general-purpose`) → `ECONOMY_DEPTH.md`  *(Pillar 3)*
Start from `game_end_checker.py` (today: standing ≥ threshold with ≥2 factions = win; capture = lose).
Propose depth: **multi-objective victory** (e.g. faction standing OR wealth OR quest-chain completion
OR a brokered treaty), a **resource/currency loop** (the `currency` engine is already heavily
surfaced — 13 demo files — exploit it), **faction tension** (gains with one faction cost another),
**time/tick pressure**, **multiple distinct failure states**, and a **score/grade** at the end. Keep
every condition checkable from REST-polled state the demo already reads (or name the poll it needs).
Each as a §4 mini-spec; show the change as a delta to `game_end_checker`'s constants/logic.

### D4 — Feasibility & enablers (`architect`) → returned inline; orchestrator saves `FEASIBILITY.md`
Apply the **reachability gate** to every D1–D3 proposal. Classify each as: **(A) pure demo-side** —
client method exists + UI/loop work only; **(B) needs an engine-side enabler** — a new `api/routes/*`
+ `EngineClient` method (name it; this is engine work, tracked separately); **(C) needs a schema or
layer/DECISIONS call** — flag for a human. Respect the demo zero-import rule and the demo file-size
waivers. Give each a rough effort (S/M/L/XL) + a prerequisite-enabler list. Identify the **2–3 keystone
enablers** (the engine routes that, once added, unlock the most demo mechanics — likely an `oath`/
`story_pacing`/`chapter` read route). Distinguish "demo can ship this now" from "blocked on engine work".

### D5 — Synthesis & prioritization (orchestrator, after D0–D4) → `DEMO_EXPANSION_ROADMAP.md`
Consolidate every proposal into one ranked table scored on: **player-value** (does it make the demo
feel like a game?), **demo-fit / sales impact** (does it showcase the engine moat?), **effort** (from
D4), **reachability** (A/B/C from D4), and **dependency**. Produce: a sequenced phase plan (Phase 1 =
highest player-value × lowest friction × unblocks others — favor type-(A) pure-demo wins first), an
explicit **Top 5 do-next** with one-line justifications, a dependency graph (which enablers precede
which mechanics), the **keystone enablers**, and the headline answer: *the smallest set of phases that
flips this from "tech demo" to "a game".*

---

## 4. Shared mini-spec schema (every proposed expansion uses this)

```
### <DEMO-NN>: <short title>
Pillar: dormant-engine | content | economy
Player fantasy: <what the player does/feels; one sentence>
Why it matters: <sales-artifact value AND/OR game-feel value; tie to DEMO_INTENT>
Current state: <what exists today; file:line of the seam to build on>
Engine capability used: <which engine + its public surface / route, file:line>
Reachability: A pure-demo (EngineClient method <name> exists) |
              B needs enabler (missing route: api/routes/<x>.py + EngineClient.<method>) |
              C needs schema/DECISIONS
Demo surface: <EngineClient method(s) called + the pygame UI panel/poller/loop change; cite ui/ or *_poller.py pattern>
Content/seed: <new seed.py nodes/edges or scenario beats, or "none">
Win/lose hook: <how it ties into game_end_checker, or "none">
Prerequisite enablers: <DEMO-NN / engine route / ISSUE-0NN that must land first, or "none">
Effort: S | M | L | XL     Player-value: low | med | high     Demo-fit: low | med | high
Risks / unknowns: <pygame feasibility, LLM latency in-loop, content authoring cost>
First slice: <the smallest shippable increment that proves the mechanic in the running demo>
Open questions: <route to OPEN_QUESTIONS.md if it needs a human call>
```

---

## 5. Rules of engagement

- **Read-only.** Do not modify source, tests, prompts, seeds, configs; do not run the app, migrations,
  or Docker. The only writes are the `project-harness/demo-expansion/*.md` deliverables.
- **Pygame only.** No Unity/Unreal/web proposals — that is Phase X, out of scope. If a mechanic can't
  live in pygame-ce, drop it.
- **Reachability is law.** Every mechanic is reachable via `EngineClient` over REST/WS, or it names the
  engine-side route enabler and is marked blocked. No proposal silently assumes a `src/` import.
- **Verify gameplay vs infra.** Confirm each candidate engine is player-facing before designing a
  mechanic (the `contracts` trap).
- **Code-grounded & concrete.** Cite `file:line`; name the real `EngineClient` method or the missing
  route; sketch the real `ui/` panel. No "add an AI director" hand-waving.
- **Educated guesses, logged.** When intent is ambiguous (sandbox vs authored campaign, session
  length, art budget), assume the most demo-aligned answer, proceed, and record it in
  `OPEN_QUESTIONS.md`. Never stall.
- **Prioritize ruthlessly.** A long unranked idea list is a failure. The value is the *sequencing* —
  and front-loading the type-(A) pure-demo wins that need no engine work.

## 6. Phase plan (autonomous — no human checkpoints)

1. **D0 first** — produce `DEMO_INTENT.md` (the rubric + current-loop baseline).
2. **D1, D2, D3 in parallel** (+ D4 feasibility, which may start once D1–D3 have draft candidates).
3. **D5 synthesis** — orchestrator merges into `DEMO_EXPANSION_ROADMAP.md`.
4. **Compile `OPEN_QUESTIONS.md`** — every assumption + every human-only decision, each with the
   educated-guess default used.
5. **Final orchestrator message** — a tight executive brief: the "demo vs game" verdict, the Top 5
   do-next, the keystone engine enablers, and the open questions awaiting the human. End there
   (do not implement).

## 7. Readiness checklist (the run must satisfy)

- [ ] All seven deliverables exist under `project-harness/demo-expansion/` and cross-reference each other.
- [ ] Every proposal uses the §4 schema, cites real files, and has `Reachability:` filled (A/B/C).
- [ ] Pillar coverage is complete: dormant engines (`treaty`/`oath`/`story_pacing`/`chapter` + scan),
      content (NPCs/locations/quests/arcs/replayable scenarios), economy (multi-objective win + ≥2
      distinct failure states).
- [ ] `FEASIBILITY.md` separates ship-now (A) from blocked-on-engine (B) from needs-decision (C), and
      names the keystone enablers.
- [ ] `DEMO_EXPANSION_ROADMAP.md` has a scored table + Top 5 + dependency ordering + the
      "smallest-set-to-feel-like-a-game" answer.
- [ ] No Unity/Unreal proposals; no `src/` import assumed without a named enabler.
- [ ] No source/seed/config/test modified; app not run. Final summary is a human-readable executive brief.
