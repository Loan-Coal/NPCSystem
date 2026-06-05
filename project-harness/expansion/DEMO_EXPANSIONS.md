# Demo-Game Expansions — lens X4

**Scope:** Read-only analysis of `demo_game/` (a standalone pygame-ce client, zero
imports from `src/`) against `project-harness/FEATURES.md` (shipped capability
inventory) and `project-harness/expansion/BUSINESS_INTENT.md` (product rubric).
Two sub-goals: (a) showcase-coverage gap; (b) demo-as-product expansions.

**What the demo is today (two surfaces):**
1. **Scripted runner** (`make demo-run` → `demo_game/run.py`): a linear 7-act scene
   list (`run.py:98-415`) plus two eval-world story arcs
   (`scenarios/run_village_crisis.py`, `scenarios/run_tavern_intrigue.py`).
2. **Interactive pygame window** (`make demo` → `demo_game/ui/game_window.py`): a
   14-tab right panel (`ui/right_panel.py:58-74`), NPC dialogue (WS-streamed),
   8 contextual action buttons (`ui/actions_panel.py:26-35`), 9 background pollers,
   3 locations / 5 NPCs (`constants.py:19-49`), and a win/lose overlay
   (`ui/game_window.py:393-419`).

**Key limits (cited in prompt + ISSUES):** ISSUE-060 (ACT-3 bribe uses `STANDS_WITH`
faction→faction for a player→faction edge → 404 → scripted `demo-run` exits
non-zero at ACT 3); ISSUE-059 (knowledge-heavy NPCs degrade to canned dialogue —
the headline gossip/memory features stop surfacing live); ISSUE-057 (no `PART_OF`
location hierarchy); scripted-only narrative flow (no free-running sandbox); no
proactive/NPC-initiated dialogue surface anywhere in `demo_game/`; no integrator
hello-world sample (Glob for `quickstart|hello_world|example_client|sample`
returned nothing).

---

## Showcase coverage gap table

Columns: FEATURES.md capability | demo surface today (`file:line` in `demo_game/`) | gap.

| FEATURES.md capability | Demo surface today | Gap |
|---|---|---|
| **dialogue** — structured output (response + relation deltas + action + facial expr), tiered degradation | WS streaming `game_controller.py:163-187`, `dialogue_ws.py`; degradation badge `game_window.py:155-158`; scripted `StreamingDialogueBeat` `run_scenes.py:152-203` | **facial_expression** parsed (`game_controller.py:312`) but not rendered as a portrait/expression; `action` not visibly surfaced; degradation shown only as a colour badge, not labelled "FULL/GRAPH-ONLY/CANNED" for buyers |
| **gossip** — distortion (omission/exaggeration/role_swap/timeline_shift), seeded RNG, propagation | CHAIN tab `ui/gossip_chain.py`; scripted Sorn→Mira→Henryk arc `run.py:137-167`; rumor warfare ACT 7 `run.py:327-405`; interactive Spread/Correct Rumor `actions_panel.py` | **distortion_type / distortion_level not surfaced** in a per-hop diff view; seeded-RNG determinism (replayability — a headline sell) is never shown; no side-by-side "what Sorn said vs what Henryk believes" |
| **emotion** — valence/arousal, decay, mood label | EMOTION tab `ui/emotion_panel.py`; `emotion_poller.py`; scripted `EmotionDisplay` `run_scenes.py:274-295` | decay-over-time not visualised (no trend); only current snapshot shown |
| **mood** — mood contagion between co-located/related NPCs | **none** | **fully unshowcased** — no panel, no scene shows one NPC's mood shifting a neighbour's |
| **memory_consolidation** — session turns → durable Memory node; arousal-triggered | MEMORY tab `ui/memory_panel.py`; Consolidate Memory action `actions_panel.py`; scripted `MemoryConsolidate` `run_scenes.py:326-343` | **persistence across sessions never demonstrated** — the headline "NPCs remember you" pitch (BUSINESS_INTENT §2) is invisible: nothing recalls a memory in a later conversation |
| **quest** — lifecycle + atomic reward/currency/item transfer | PLAYER STATUS quest panel `ui/quest_panel.py`; quest accept/complete/reward `game_controller.py:489-499`; scripted `QuestDisplay` `run.py:177` | atomic single-transaction reward transfer (a reliability sell) not made visible |
| **quest_generation** — engine-generated quests (LLM) | Generate Quest action `actions_panel.py`, `game_controller.py:197-203` | adequately shown |
| **events** — materialization, awareness seeding, location scoping | WORLD tab `ui/world_panel.py`; `world_poller.py`; scripted `EventFire`/`WorldFeed` | location-scoped awareness (who-can-know-what by location) not made legible |
| **faction_politics** — standings, pledges, treaties | POLITICS tab `ui/politics_panel.py` (pledges + leverage); `npc_politics_poller.py`; bribe action | **treaties not surfaced**; reputation/standing only via bribe; ISSUE-060 breaks the scripted standing path |
| **story_pacing / chapter** — narrative pacing + chapter labels over ticks | **none** | **fully unshowcased** — no chapter/pacing readout |
| **routine / skill / military / clique** | military only: scripted battle `run.py:258-276` + Army seed `seed.py:517-544` | **routine, skill, clique fully unshowcased**; military only in scripted runner, not interactive |
| **interaction** — player action reporting, trade/quest/give proposals | TRADE/INVENTORY tabs; Give item action; `quest_trade_controller.py`; proposal dispatch `game_controller.py:529-547` | adequately shown |
| **llm** — pluggable backend (register adapter + factory line) | **none** | **unshowcased** — the "swap LLM with one file" sell (BUSINESS_INTENT §2) has no demo affordance (would be an integrator-doc concern) |
| **tts** — pluggable text-to-speech | audio playback `audio_player.py`, `game_controller.py:318-320` (WS `audio_bytes`) | works but is incidental; not announced as a feature |
| **scheduler** — realtime + game_driven clock, tick lease | `C` key / scripted `ClockTick`; world poller | tick-lease / off-screen-while-away framing not made explicit |
| **retrieval** — graph RAG, tiered context, token-budget enforcement | **none directly** (INSPECT tab shows graph data, not retrieval) | **retrieval quality unshowcased** — no "these memories were retrieved for this answer" view; ties to Phase 15 precision@k ambition |
| **B.1 auth / rate-limit / idempotency** | Bearer header `client.py:53`; idempotency headers for quests `client.py:821-849` | auth/rate-limit invisible (correct for a player, but an integrator hello-world should show the 401 path) |
| **B.5 reliability — degrade to canned / 503, redacted errors** | error envelope parse `client.py:1401-1420`; degradation badge | **degradation is shown as failure colour, not as a feature** ("the player never sees a crash") — the resilience sell is buried |
| **Anti-hallucination guard** (cross-cutting) | implicit in rumor-correction ACT 7 (`run.py:369-405`) | **never framed as "the NPC refuses to answer what it doesn't know"** — the #1 buyer success criterion has no dedicated demo beat |
| **Proactive / NPC-initiated dialogue** (ROADMAP Phase 14, BUSINESS_INTENT success criterion 2) | **none** (grep `proactive|hail|initiat|idle|ambient` → only `widgets.py`) | **fully unshowcased + not yet built in engine** — flagged as top engine-dependent demo opportunity |

**Count of unshowcased (or materially under-surfaced) capabilities: 9.**
Fully unshowcased: **mood contagion, story_pacing/chapter, routine, skill, clique,
pluggable-LLM affordance, retrieval-quality view, proactive dialogue** (8), plus
**cross-session memory persistence** which is implemented but never demonstrated as
a player-visible recall (the single highest-value miss against the product thesis).

---

## Mini-specs (EXP-80 — EXP-99)

### EXP-80: Free-play / sandbox mode (drop the scripted rails)
Type: demo
Business rationale: BUSINESS_INTENT success criterion 7 ("the world runs off-screen") and §1 thesis ("off-screen living world… even when the player is not present"). A buyer wants to *see* the world breathe without a script; the scripted runner proves beats, not aliveness.
What it does: A `make demo-sandbox` mode (and an in-window "SANDBOX" toggle) that auto-advances the clock on a timer (e.g. every N seconds → `POST /v1/clock/advance`), lets the player roam/talk freely, and surfaces a live event/gossip feed as the world changes underneath them. No predetermined scene list — the demo becomes an open world the buyer can poke.
Current state: Demo is scripted-only (`run.py:98-415` is a fixed `SCENES` list) OR interactive-but-manual (the pygame window only advances time on the `C` key, `game_window.py:334-339`). No autonomous time progression exists.
Graph/schema additions: none — demo consumes existing API.
API surface: `POST /v1/clock/advance` (have: `client.py:261`), `GET /v1/system/events` (have: `client.py:315`), `POST /v1/dialogue` / WS (have).
Composition: new `demo_game/sandbox_loop.py` (timer thread that ticks the clock); `game_window.py` gains a SANDBOX toggle + auto-tick status line; reuse existing `world_poller` for the live feed.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none (works today); pairs powerfully with EXP-82 once Phase 14 lands.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: live LLM latency makes auto-tick feel sluggish; mitigate with a configurable tick interval and the existing `--cached` replay path. ISSUE-059 may make hub NPCs go canned mid-sandbox (degrades the impression).
First slice: a timer thread that calls `advance_clock(1)` every 8s and refreshes `world_poller`; no new UI beyond a "auto-tick: on" status line.
Open questions: should sandbox auto-tick advance structured time (day/season) or only ticks? → OPEN_QUESTIONS (affects how dramatic the off-screen change looks).

### EXP-81: Cross-session memory recall demo ("the NPC remembers you")
Type: demo
Business rationale: BUSINESS_INTENT §2 first commitment — "persistent knowledge/relationships/emotion per NPC across the whole world" — and §1 thesis "remember shared history". This is the product's headline claim and it is currently *implemented but never demonstrated* (see gap table).
What it does: A scripted (and interactive) beat that (1) tells an NPC something distinctive, (2) consolidates the session into a Memory node, (3) ends the session / "leaves", (4) returns in a fresh session and asks an open question, and the NPC recalls the earlier exchange — proven by showing the Memory node in the MEMORY tab alongside the recalled line.
Current state: Consolidation is shown (`run_scenes.py:326-343`, MEMORY tab) but recall-in-a-later-conversation is never staged; the demo never closes a session and reopens to prove persistence.
Graph/schema additions: none — demo consumes existing API.
API surface: `POST /v1/dialogue` (have), `POST /v1/admin/memories/consolidate/{npc_id}` (have: `client.py:656`), `GET /v1/admin/memories/{character_id}` (have: `client.py:634`).
Composition: a new scripted act in `run.py`/`run_scenes.py` (a `MemoryRecallBeat`); in the window, a "New session" button that rotates `session_id` so recall is visibly cross-session.
Architecture fit: demo-only, no src/ changes (assuming retrieval surfaces the Memory; verify against ISSUE-059).
Prerequisite enablers: **ISSUE-059** (if the NPC degrades to canned, recall won't surface — recall depends on retrieval working). Likely the single most demo-blocking issue.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: ISSUE-059 directly threatens this; the recalled memory must actually be retrieved into context, which is the exact path that currently overflows the budget for knowledge-rich NPCs.
First slice: scripted-only `MemoryRecallBeat` against a *low-knowledge* NPC (sidesteps ISSUE-059) to prove the concept for a recording.
Open questions: is cross-session continuity keyed by `session_id` or `player_id`? Confirm the engine's recall semantics → OPEN_QUESTIONS.

### EXP-82: Proactive / NPC-initiated dialogue surface
Type: demo
Business rationale: BUSINESS_INTENT §3 ambition ("agentic NPCs that initiate, not just react") and success criterion 2 ("an NPC can be hailed proactively — standing still produces an unsolicited in-character line"). ROADMAP Phase 14.
What it does: When the player idles in a location (no input for N seconds), or when a world event fires nearby, the co-located NPC emits an unsolicited line ("You again — did you hear about the fire?"). Renders as an NPC-initiated bubble in the dialogue log.
Current state: **No proactive surface anywhere** (grep confirmed). All dialogue is player-initiated via `submit_dialogue` (`game_controller.py:163`).
Graph/schema additions: none in the demo — but **the engine feature does not exist yet** (Phase 14, DEFERRED). Needs an engine route, e.g. `POST /v1/npc/{id}/proactive` or a WS push.
API surface: **needs new engine route** (see the engine-lens proactive-dialogue EXP; demo consumes it once it exists). Until then, a demo-only stub could fake it by calling `/v1/dialogue` with a synthetic system prompt — but that misrepresents the feature, so not recommended.
Composition: new `demo_game/idle_watcher.py` (idle timer) + `game_controller` hook to fetch/stream the proactive line; left panel renders an "NPC speaks first" variant.
Architecture fit: **depends on engine EXP** (Phase 14 proactive-dialogue route).
Prerequisite enablers: engine proactive-dialogue feature (Phase 14). Pairs with EXP-80 sandbox.
Effort: M (demo side)   Value: high   Business-fit: high
Risks / unknowns: blocked on engine work; faking it client-side would be a misleading sales artifact.
First slice: once the engine route lands, an idle-timer that fetches one proactive line after 15s of inactivity.
Open questions: what triggers a proactive line (idle vs nearby-event vs relationship-threshold)? → OPEN_QUESTIONS, routes to the engine lens.

### EXP-83: Integrator hello-world quickstart (minimal standalone client)
Type: demo
Business rationale: BUSINESS_INTENT success criterion 5 ("integrator hello-world is fast and clean… standalone client, zero engine imports") and the §1 one-deployment pitch. The pygame app proves zero-`src/`-imports but is far too large to read as a "10 lines to first NPC line" proof.
What it does: A single ~60-line `demo_game/quickstart.py` (or top-level `examples/hello_npc.py`) that: reads base_url + api_key from env, POSTs one `/v1/dialogue`, prints the structured response, and shows the 401 path if the key is wrong. The minimal "clone → up → seed → talk" artifact a studio evaluator runs first. Add `make hello`.
Current state: **No such file** (Glob returned nothing). The smallest existing client is `client.py` (1400+ lines) wrapped by a 400+-line pygame window.
Graph/schema additions: none — demo consumes existing API.
API surface: `POST /v1/dialogue` only (have: `client.py:74`), plus a `GET /health` ping to prove the stack is up.
Composition: new standalone `demo_game/quickstart.py` using only `httpx` (or even stdlib) — deliberately NOT importing the heavy `EngineClient`, to model what an integrator writes from scratch; `Makefile` `hello` target; a README "Hello, NPC" section.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none for a happy-path call; a *clean* end-to-end run depends on the fresh-boot fix (BUSINESS_INTENT §3 first-run-clean) and on Batch 5 typed responses for codegen, but the sample itself works against the running stack today.
Effort: S   Value: high   Business-fit: high
Risks / unknowns: must stay tiny and dependency-light or it stops being a "hello world". Keep it copy-paste runnable.
First slice: the 60-line happy-path script + `make hello`; defer the 401-demo and README section.
Open questions: target language — Python sample only, or also a curl one-liner + a stub Unity/C# snippet to match the SDK pitch? → OPEN_QUESTIONS.

### EXP-84: Gossip distortion diff view ("telephone" side-by-side)
Type: demo
Business rationale: BUSINESS_INTENT §2 "deterministic, replayable gossip distortion" and the gossip headline feature. The CHAIN tab shows the chain but not the *content drift* per hop, which is the visually compelling part.
What it does: A per-hop view rendering each NPC's `distorted_summary` + `distortion_type` + `distortion_level` side by side, so the audience sees the war report mutate Sorn→Mira→Henryk. A "diff" highlight on changed phrasing.
Current state: CHAIN tab (`ui/gossip_chain.py`) shows the edge chain; `run_scenes.py:477-481` prints hop npc/tick/state to stdout. The `distorted_summary` payload is already seeded (`seed.py:580-614`) and fetchable via `KNOWS_ABOUT` edges, but never rendered as drifting text.
Graph/schema additions: none — demo consumes existing API.
API surface: `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=...` (have: `client.py:142`, already used at `game_window.py:210`); `GET /v1/admin/gossip/trace/{event_id}` (have: `client.py:1349`).
Composition: extend `ui/gossip_chain.py` to render `distorted_summary` text per hop with distortion-type badges; reuse the existing chain fetch.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none.
Effort: S   Value: high   Business-fit: high
Risks / unknowns: text length per hop may overflow the narrow right panel; needs wrapping/scroll (widgets already support scroll).
First slice: render the three seeded summaries for `northern_war_begins` in CHAIN; defer the diff-highlight.
Open questions: none.

### EXP-85: Anti-hallucination "I don't know" demo beat
Type: demo
Business rationale: BUSINESS_INTENT success criterion 1 (the #1 buyer bar: "NPCs never assert facts they don't know") and FEATURES.md anti-hallucination guard. This is the most important sell and has no dedicated beat.
What it does: A scripted act that asks an NPC about something it provably does NOT have a `KNOWS_ABOUT` edge for, and shows the NPC declining/deflecting in-character rather than inventing — paired with an INSPECT view proving the absence of the edge. Then asks an NPC who *does* know, for contrast.
Current state: Implicit only in the rumor-correction arc (`run.py:369-405`, where a corrected NPC "no longer knows"). No explicit "ask about the unknown" beat with graph proof.
Graph/schema additions: none — demo consumes existing API.
API surface: `POST /v1/dialogue` (have), `GET /v1/graph/edges/KNOWS_ABOUT` (have), INSPECT data via `inspect_worker`.
Composition: new `AntiHallucinationBeat` in `run_scenes.py`; in the window, lean on the existing INSPECT tab to show the missing edge.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none (uses existing knowledge guard).
Effort: S   Value: high   Business-fit: high
Risks / unknowns: LLM may still confabulate on a weak prompt; pick a target/topic with a strong, well-tested guard so the beat is reliable for recording.
First slice: one scripted ask-the-ignorant-NPC beat + cached transcript.
Open questions: which NPC/topic pair most reliably triggers a clean refusal? → verify against the eval battery, else OPEN_QUESTIONS.

### EXP-86: Degradation-as-a-feature banner ("the player never sees a crash")
Type: demo
Business rationale: BUSINESS_INTENT success criterion 6 ("degradation is invisible to the player") and FEATURES.md B.5 reliability contracts. Currently degradation reads as failure (a colour), not as a resilience selling point.
What it does: A reframed badge + an optional "chaos" toggle that forces an LLM-timeout/budget condition and shows the NPC still answering (graph_only / canned) with a tasteful "engine degraded gracefully — no crash" annotation, instead of a red error.
Current state: Degradation surfaced as a colour badge only (`game_window.py:155-158`, `dialogue.py::degradation_color`); reads as an error state, not a feature.
Graph/schema additions: none — demo consumes existing API.
API surface: existing `/v1/dialogue` `degradation_level` field; no forcing route exists, so the "chaos toggle" may need an engine test hook (otherwise demonstrate only the natural canned path).
Composition: `dialogue.py` / left panel badge relabelled to FULL / GRAPH-ONLY / CANNED with a one-line explanation; optional chaos toggle in `game_window`.
Architecture fit: demo-only for relabelling; chaos-forcing toggle **depends on an engine test hook** (otherwise omit).
Prerequisite enablers: ISSUE-059 ironically already forces canned for hub NPCs — could be (mis)used to show degradation, but fixing 059 is the real goal.
Effort: S (relabel) / M (chaos toggle)   Value: med   Business-fit: high
Risks / unknowns: must not look like the demo is broken; framing/copy is everything.
First slice: relabel the badge with the tier name + tooltip; defer the chaos toggle.
Open questions: is there a safe engine hook to force a timeout for the demo? → OPEN_QUESTIONS.

### EXP-87: Richer world — more NPCs / locations on a location hierarchy
Type: demo
Business rationale: BUSINESS_INTENT §3 production-scale ambition (≥10k nodes, ≥200 gossip pairs/tick) and the "living world" thesis. A 5-NPC / 3-location world looks like a toy; depth sells middleware.
What it does: Expand the seed world to ~12-15 NPCs across a nested geography (market → district → city) using `PART_OF` edges, enabling region-scoped gossip and travel that *feel* spatial. Adds visible depth to every existing panel for free.
Current state: 3 flat locations, 5 NPCs (`constants.py:19-49`, `seed.py:347-387`); locations have no parent/child relation.
Graph/schema additions: **needs the engine `PART_OF` edge type** (ISSUE-057) before the hierarchy is real; the *extra NPCs/locations alone* need no schema change and can land first.
API surface: `POST /v1/graph/nodes/*`, `POST /v1/graph/edges/*` (have: `client.py:435,456`); seeder reuse.
Composition: extend `seed.py` data tables (`_LOCATIONS`, `_NPCS`, `_NPC_LOCATED_AT`) and `constants.py` maps; nav bar already scales by `len(LOCATIONS)` (`game_window.py:312`).
Architecture fit: flat expansion is demo-only; the *hierarchy* depends on engine ISSUE-057.
Prerequisite enablers: **ISSUE-057** (for `PART_OF`); none for just adding more flat NPCs/locations.
Effort: M (more NPCs) / L (with hierarchy)   Value: med   Business-fit: high
Risks / unknowns: more NPCs = more knowledge accumulation = higher ISSUE-059 exposure; the win/lose objective logic (`game_end_checker`) assumes the current 3 factions and may need rebalancing.
First slice: add 3-4 flat NPCs + 1 location to the seed; defer `PART_OF` until ISSUE-057.
Open questions: does the win/lose game-end logic generalise beyond 3 factions? → OPEN_QUESTIONS.

### EXP-88: Recording / marketing mode (deterministic cinematic playback)
Type: demo
Business rationale: BUSINESS_INTENT §1 "first impression and sales artifact" framing of the demo. A repeatable, latency-free recording is what goes on the website / into a pitch.
What it does: A `--cinematic` mode building on the existing `--cached` replay: fixed pacing, larger fonts, a title card per act, and (optionally) auto-screenshot/auto-record hooks so a clean run can be captured without manual driving. Determinism comes from the existing LLM cache (`run.py:58-92`).
Current state: `--cached` replay exists (`run.py:464-466`, `LLMCache`) and `make demo-snapshot` snapshots state, but there is no cinematic/recording-friendly presentation layer; pacing/fonts are dev-oriented.
Graph/schema additions: none — demo consumes existing API.
API surface: none new — pure presentation over the cached path.
Composition: a `cinematic` flag on `DemoRunner` and/or `game_window` (title cards, slower reveal, bigger fonts via `FontLoader`); optional pygame `image.save` per beat.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: a clean end-to-end scripted run — **blocked by ISSUE-060** (ACT-3 abort) for the full 7-act capture; partial captures (ACTs 1-2) work today.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: ISSUE-060 must be fixed to record the full scripted arc; until then only the eval-world arcs (`run_village_crisis`, `run_tavern_intrigue`) run clean enough to record end-to-end.
First slice: title cards + slower pacing on the cached path for the village arc.
Open questions: video capture in-process (pygame frame dump) vs external (OBS)? → OPEN_QUESTIONS.

### EXP-89: Mood-contagion visualiser
Type: demo
Business rationale: FEATURES.md lists **mood** (contagion between co-located/related NPCs) as ✅ shipped, yet it is fully unshowcased — a free win against the "living world" thesis (BUSINESS_INTENT §1).
What it does: A view (or an EMOTION-tab extension) showing two co-located NPCs' moods, then fires an event and advances the clock to show one NPC's negative mood "infecting" the neighbour — emotion values shifting in tandem across a tick.
Current state: EMOTION tab shows a single active NPC's snapshot (`ui/emotion_panel.py`, `emotion_poller.py`); no multi-NPC or contagion view; `emotion_poller` tracks one `active_npc` at a time (`game_window.py:124`).
Graph/schema additions: none — demo consumes existing API.
API surface: `GET /v1/npc/{id}/emotion` (have: `client.py:238`) polled for two NPCs; `POST /v1/clock/advance` to trigger contagion.
Composition: a multi-NPC emotion poller (or poll two NPCs) + a small contagion panel; reuse `emotion_panel` rendering.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: contagion magnitude per tick may be subtle; needs a strong event (the seeded market fire) and tuned NPCs to read clearly on screen.
First slice: poll two co-located NPCs' emotions and show them side by side; defer the explicit contagion annotation.
Open questions: which seeded NPC pair has a relationship strong enough for visible contagion? → verify against engine mood-contagion params, else OPEN_QUESTIONS.

### EXP-90: Retrieval-explainer panel ("why did the NPC say that?")
Type: demo
Business rationale: BUSINESS_INTENT §3 ambition (provable retrieval quality, Phase 15) and success criterion 3 ("retrieval returns the right memories"). Buyers distrust black-box LLMs; showing the retrieved context builds trust.
What it does: After a dialogue turn, a panel lists the graph items (memories, KNOWS_ABOUT facts, beliefs) that were retrieved into the NPC's context for that answer — turning the answer from "magic" into "grounded in these N facts".
Current state: **No retrieval view.** INSPECT shows raw graph data, not what was *retrieved for a specific turn*; the dialogue response carries no retrieved-context manifest the demo can read.
Graph/schema additions: none in the demo, but **needs the engine to expose the retrieved context** in the dialogue response (a `context_manifest` / `retrieved_node_ids` field). Today's `DialogueResponse` does not appear to surface this.
API surface: **needs a new/extended engine response field** (retrieved-context manifest on `/v1/dialogue`); demo consumes it once present.
Composition: new `demo_game/ui/retrieval_panel.py` + a poller/parser; `dialogue.py` parses the manifest.
Architecture fit: **depends on engine EXP** (expose retrieval manifest).
Prerequisite enablers: engine change to return retrieved context; relates to Batch 5 typed responses and ISSUE-059 (retrieval is the affected path).
Effort: M (demo) + engine dependency   Value: high   Business-fit: high
Risks / unknowns: blocked on engine surfacing the manifest; without it, the demo can only approximate via INSPECT.
First slice: once the field exists, list retrieved node ids/labels under the last NPC line.
Open questions: does `/v1/dialogue` already return any retrieved-context metadata? Confirm before building → OPEN_QUESTIONS / engine lens.

### EXP-91: Relationship-delta live ticker (trust/affection/fear changing per turn)
Type: demo
Business rationale: BUSINESS_INTENT §2 "structured dialogue output: … relation_deltas" and §4 criterion 10 (bounded relation mutation). Relationship change is core to "NPCs that remember shared history" but is invisible to the player.
What it does: A small ticker that, after each turn, animates the trust/affection/fear deltas the engine returned (e.g. "+5 trust, -2 fear") and shows the running relationship value, so the audience sees the relationship evolve as they talk.
Current state: `relation_deltas` are parsed and *applied* to the negotiation band (`game_controller.py:517-527`, `_apply_relation_band`) but never *shown* to the player as a delta.
Graph/schema additions: none — demo consumes existing API.
API surface: `relation_deltas` already in the dialogue response (parsed at `game_controller.py:315`); optionally `GET /v1/npc/{id}/state` for the running value.
Composition: extend the left panel / a small overlay to render the last turn's deltas; reuse the existing parse.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none.
Effort: S   Value: med   Business-fit: med
Risks / unknowns: deltas can be zero on many turns (looks inert); pair with prompts known to move the relationship.
First slice: render the last turn's `relation_deltas` as a transient "+N trust" toast.
Open questions: none.

### EXP-92: Determinism / replay proof toggle ("same seed → same gossip")
Type: demo
Business rationale: BUSINESS_INTENT §2 "deterministic, replayable gossip distortion (seeded RNG logged)" and §4 criterion 7 (deterministic replay from logged seed) — a concrete reliability/QA sell for studios.
What it does: A side-by-side run showing that re-running the same gossip tick with the same logged seed produces identical distortion, vs a different seed producing different drift — proving the engine is reproducible for QA/debugging.
Current state: Not shown anywhere; the demo never references seeds or reruns a tick for comparison.
Graph/schema additions: none in the demo, but **needs the engine to accept/return the RNG seed** on a gossip tick (the seed is logged server-side per CLAUDE.md but may not be settable/returnable via the API).
API surface: **likely needs an engine route extension** to set/return the gossip seed; demo consumes it.
Composition: a comparison scene in `run.py` / a window panel; depends on the seed surface.
Architecture fit: **depends on engine EXP** (expose gossip seed via API).
Prerequisite enablers: engine seed-surfacing.
Effort: M + engine dependency   Value: med   Business-fit: med
Risks / unknowns: blocked on the engine exposing the seed; without it this cannot be demoed honestly.
First slice: deferred until the engine exposes the seed.
Open questions: is the gossip RNG seed settable/returnable via any route today? → OPEN_QUESTIONS / engine lens.

### EXP-93: Fix ISSUE-060 so the scripted 7-act demo runs to completion
Type: demo
Business rationale: BUSINESS_INTENT success criterion 5 ("the scripted demo runs end-to-end") — currently fails. A sales artifact that exits non-zero mid-run is a direct credibility hit.
What it does: Replaces the broken player→faction standing path (`put_npc_reputation` emitting a `STANDS_WITH` faction→faction edge → 404) with the engine's canonical player→faction reputation mechanism, so ACT 3 (and any later acts it unmasks) complete.
Current state: ISSUE-060 — `run_scenes.py:239` (`BribeScene`) → `client.py::put_npc_reputation` (`client.py:1248-1272`, emits `STANDS_WITH`) vs `stands_with.yaml` (`faction→faction`). ACTs 1-2 run with live full-tier dialogue; ACT 3 aborts.
Graph/schema additions: **demo-side fix preferred** (route through the existing reputation/`adjust` mechanism — `adjust_npc_reputation` at `client.py:1274` already targets a player→faction reputation route); only escalates to schema if no player→faction reputation representation exists.
API surface: `POST /v1/admin/characters/{id}/reputation/{faction}/adjust` (have: `client.py:1274`) — likely the correct replacement for `put_npc_reputation` in the bribe path.
Composition: `client.py::put_npc_reputation` / `BribeScene` (`run_scenes.py:210-244`) re-pointed at the reputation-adjust path; then run `make demo-run` to find any further act breakage.
Architecture fit: demo-only if the adjust route covers player→faction standing; otherwise depends on a schema decision (ISSUE-060 "To fix" step 1).
Prerequisite enablers: a decision on the canonical player→faction standing representation (ISSUE-060).
Effort: S (if `adjust` works) / M (if a new edge type is needed)   Value: high   Business-fit: high
Risks / unknowns: "likely additional act bugs lurk beyond ACT 3" (ISSUE-060) — the full arc hasn't completed in a while; budget for downstream fixes.
First slice: swap `BribeScene` to `adjust_npc_reputation` and run the scripted demo to the next failure.
Open questions: is the player→faction standing the engine already reads via `adjust`, or is a `Character→Faction` reputation edge type required? → OPEN_QUESTIONS (decision, route to DECISIONS.md).

### EXP-94: Facial-expression / portrait rendering for NPCs
Type: demo
Business rationale: BUSINESS_INTENT §2 "structured dialogue output: … facial_expression" — the engine returns it, the demo ignores it visually. Visible expression is a high-impact, low-cost "alive" signal for a sales demo.
What it does: Render a per-NPC portrait (or a simple emoji/expression glyph) that changes with the `facial_expression` field the engine returns each turn (neutral/angry/afraid/pleased), so NPCs visibly react.
Current state: `facial_expression` is parsed into the fake-raw turn (`game_controller.py:312`) but never rendered; NPCs are text-only.
Graph/schema additions: none — demo consumes existing API.
API surface: `facial_expression` already in the dialogue response.
Composition: a small `demo_game/ui/portrait.py` mapping expression → glyph/sprite; left panel renders it next to the NPC name.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none.
Effort: S (glyphs) / M (sprite art)   Value: med   Business-fit: med
Risks / unknowns: needs art assets for real portraits; emoji/glyph fallback keeps effort S and avoids an asset pipeline.
First slice: map the `facial_expression.type` to a coloured glyph beside the NPC name.
Open questions: ship demo art assets, or keep it glyph-only to stay asset-free? → OPEN_QUESTIONS.

### EXP-95: In-window scenario picker (unify scripted arcs + free-play)
Type: demo
Business rationale: BUSINESS_INTENT §1 sales-artifact framing — one launch surface that lets an evaluator pick "guided tour" (scripted) or "explore" (sandbox) without learning three `make` targets.
What it does: A start screen / menu in the pygame window offering: Munich demo arc, Village Crisis, Tavern Intrigue, or Free-Play (EXP-80). Removes the need to know `make demo-run` / `demo-village` / `demo-tavern` and seeds the right world per choice.
Current state: Three separate scripted entry points (`run.py`, `scenarios/run_village_crisis.py`, `scenarios/run_tavern_intrigue.py`) + a separate interactive window; no unifying launcher; each needs its own seed (`make seed-*-world`).
Graph/schema additions: none — demo consumes existing API.
API surface: existing seed + dialogue routes; per-arc seed selection.
Composition: a new `demo_game/ui/start_menu.py` + `__main__` wiring; reuse existing runners/seeders.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: EXP-80 (for the Free-Play option); seed-world idempotency (have).
Effort: M   Value: med   Business-fit: med
Risks / unknowns: each arc currently assumes its own seeded world (vw_/tw_ prefixes); switching arcs at runtime needs a (re)seed step, which is slow.
First slice: a menu that launches the three existing scripted arcs (no in-window free-play yet).
Open questions: can multiple eval worlds coexist in one graph, or must the picker reseed per choice? (DEC-068 = one world per graph) → OPEN_QUESTIONS.

### EXP-96: Story-pacing / chapter readout
Type: demo
Business rationale: FEATURES.md lists **story_pacing / chapter** (🟡 implemented) — currently unshowcased. Surfacing narrative arc/chapter gives buyers a "directed-but-emergent" story signal.
What it does: A small readout (in the WORLD tab) showing the current chapter label / pacing state the engine derives over the tick timeline, updating as ticks advance.
Current state: Not surfaced anywhere in `demo_game/`.
Graph/schema additions: none in the demo, but **needs the engine to expose chapter/pacing state** via a route (unclear one exists; story_pacing is 🟡/thin).
API surface: **needs an engine route** exposing chapter/pacing (verify; may not exist).
Composition: extend `ui/world_panel.py` to render the chapter label; a poller if a route exists.
Architecture fit: **depends on engine exposing pacing state**.
Prerequisite enablers: engine pacing/chapter route.
Effort: S (demo) + engine dependency   Value: low   Business-fit: med
Risks / unknowns: story_pacing is thin (🟡); the data may not be query-able yet.
First slice: deferred until a pacing route exists.
Open questions: is there any chapter/pacing read endpoint today? → OPEN_QUESTIONS / engine lens.

### EXP-97: Live gossip-pairs / off-screen-activity counter
Type: demo
Business rationale: BUSINESS_INTENT §4 criterion 7 ("the world runs off-screen at scale", ≥200 pairs/tick) and the off-screen-simulation thesis. A visible "23 NPCs gossiped this tick" counter makes the invisible simulation tangible.
What it does: After each clock advance, show how many gossip pairs fired / events materialised this tick (an activity heartbeat), proving the world simulates whether or not the player is talking.
Current state: WORLD tab shows engine status + recent events (`ui/world_panel.py`, `world_poller.py`) but no per-tick gossip-activity metric.
Graph/schema additions: none in the demo, but **needs the engine to report per-tick gossip-pair counts** (engine-status `/v1/system/engines` may carry last_tick info — `client.py:301` — but not a pairs-fired count).
API surface: `GET /v1/system/engines` (have) — may need extension for a pairs-this-tick metric.
Composition: extend `world_panel`/`world_poller` to read and display the metric.
Architecture fit: demo-only if the metric exists in engine status; otherwise **depends on engine exposing it**.
Prerequisite enablers: engine per-tick activity metric (verify against `/v1/system/engines` payload).
Effort: S + possible engine dependency   Value: med   Business-fit: high
Risks / unknowns: at the 5-NPC demo scale the count is tiny (unimpressive); pairs best with EXP-87 (bigger world).
First slice: show event-materialised count per tick from the existing world feed; defer pairs-fired until the metric is confirmed.
Open questions: does `/v1/system/engines` already report gossip pairs per tick? → OPEN_QUESTIONS / engine lens.

### EXP-98: Treaty / faction-standing board
Type: demo
Business rationale: FEATURES.md **faction_politics** (standings, pledges, **treaties**) is 🟡 and only partially shown (POLITICS tab covers pledges + leverage, not treaties or faction-vs-faction standings).
What it does: A board view of inter-faction standings (the seeded `STANDS_WITH` faction→faction edges, e.g. merchants vs thieves -60) and any treaties, so the audience sees the political map the gossip/reputation systems run on.
Current state: POLITICS tab shows pledges + leverage only (`ui/politics_panel.py`, `npc_politics_poller.py`); faction-faction standings are seeded (`seed.py:360-363`) but never rendered; treaties absent.
Graph/schema additions: none — demo consumes existing API.
API surface: `GET /v1/graph/edges/STANDS_WITH` (have: `client.py:142`), `GET /v1/reputation/*` (FEATURES B.2); treaties via admin domain routes if present.
Composition: extend `ui/politics_panel.py` (or a new faction board) reading faction-faction `STANDS_WITH` edges.
Architecture fit: demo-only, no src/ changes.
Prerequisite enablers: none for standings; treaty rendering depends on a treaties read route (verify).
Effort: S (standings) / M (with treaties)   Value: low   Business-fit: med
Risks / unknowns: treaty data may not be query-able (faction_politics is 🟡).
First slice: render the two seeded faction-faction `STANDS_WITH` standings as a small board.
Open questions: is there a treaties read endpoint? → OPEN_QUESTIONS.

### EXP-99: Needs-driven behaviour demo (rest/hunger → NPC state)
Type: demo
Business rationale: FEATURES.md **routine** (🟡) + the seeded Need nodes (`seed.py:473-489`) imply NPC autonomy; the NEEDS tab shows levels but never connects needs → behaviour, leaving the "agentic" ambition (BUSINESS_INTENT §3) flat.
What it does: Advance the clock to show needs decaying (rest/hunger dropping), then show a need crossing a threshold affecting the NPC (mood shift, a goal forming, or a dialogue tone change) — connecting the needs data to visible consequence.
Current state: NEEDS tab shows current need levels + decay_rate (`ui/needs_panel.py`, `npc_needs_poller.py`); decay-over-ticks and need→behaviour linkage are not shown.
Graph/schema additions: none in the demo; the need→behaviour coupling depends on whether the engine's routine/needs engine actually drives behaviour (🟡 — may be data-only).
API surface: `GET` Need nodes via generic graph (have: `client.py:1211`), `POST /v1/clock/advance` (have).
Composition: extend `needs_panel` to show decay across ticks; annotate when a need crosses a threshold.
Architecture fit: demo-only for the decay visualisation; need→behaviour linkage **depends on the engine routine engine** being live.
Prerequisite enablers: engine routine/needs-consequence behaviour (verify it's wired, not just stored).
Effort: M   Value: low   Business-fit: med
Risks / unknowns: needs may be decorative if the routine engine doesn't yet consume them (FEATURES marks routine 🟡); decay visualisation works regardless.
First slice: show need levels dropping across several clock advances (decay), no behaviour claim.
Open questions: does the engine actually act on needs (routine engine consumes them), or are Need nodes currently inert data? → OPEN_QUESTIONS / engine lens.

---

## Top 3 (highest value)

1. **EXP-81 — Cross-session memory recall** ("the NPC remembers you"): demonstrates
   the #1 product claim that is implemented but invisible today. Blocked by
   ISSUE-059 for knowledge-rich NPCs — fixing 059 unlocks the headline.
2. **EXP-80 — Free-play / sandbox mode**: converts a scripted artifact into a
   "poke the living world" experience; directly serves the off-screen-simulation
   thesis and is buildable today with no engine changes.
3. **EXP-83 — Integrator hello-world quickstart**: the smallest, highest-leverage
   sales asset — proves the one-deployment "clone → up → seed → talk" pitch
   (success criterion 5) in ~60 lines; effort S.

Honourable mention: **EXP-93** (fix ISSUE-060 so the scripted demo doesn't exit
non-zero) is a credibility prerequisite for any recorded full-arc demo.

---

## Notes / assumptions

- (ASSUMPTION) The interactive window is the primary "demo as product" surface;
  the scripted runner is the recording/pitch surface. Most product ideas target
  the window; cinematic/anti-hallucination beats target the scripted runner.
- (ASSUMPTION) EXP-82 (proactive), EXP-90 (retrieval manifest), EXP-92 (seed
  replay), EXP-96 (pacing), EXP-97 (pairs metric) require engine-side surfaces
  that may not exist; each is marked "depends on engine EXP" and routed to
  OPEN_QUESTIONS / the engine lens rather than assumed buildable.
- All `file:line` citations are against `demo_game/` (a standalone client); no
  `src/` change is proposed except where an idea is explicitly flagged as
  engine-dependent.
