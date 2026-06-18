# Demo-Game Expansions — lens X4 (refresh 2026-06-11)

**Scope:** Read-only analysis of `demo_game/` (a standalone pygame-ce client, zero
imports from `src/`) against `project-harness/archive/stale-2026-06/FEATURES.md`
(shipped capability inventory) and `project-harness/expansion/BUSINESS_INTENT.md`
(product rubric). Two sub-goals: (a) showcase-coverage gap; (b) demo-as-product
expansions.

**Codebase state at time of refresh:** Branch `munich-demo`, 2026-06-11.
`make check` green (1967 passed, 22 skipped, 85.70% coverage). Phases 0–26 complete.

**What the demo is today (two surfaces):**
1. **Scripted runner** (`make demo-run` → `demo_game/run.py`): a linear 10-act scene
   list (`run.py:101-458`). Covers: gossip chain (ACT 1), quest + emotion (ACT 2),
   bribe (ACT 3), memory consolidation (ACT 4), military tick + world feed (ACT 5),
   networked reputation (ACT 6), rumor warfare (ACT 7), determinism proof (ACT 8,
   `DeterminismBeat` / `determinism_beat.py`), anti-hallucination guard (ACT 9,
   `AntiHallucinationBeat`), cross-session memory recall (ACT 10, `RemembersYouBeat`
   / `remembers_you_beat.py`). Two additional eval-world arcs:
   `scenarios/run_village_crisis.py`, `scenarios/run_tavern_intrigue.py`.
2. **Interactive pygame window** (`make demo` → `demo_game/ui/game_window.py`): 14-tab
   right panel (`ui/right_panel.py:58-74`), NPC dialogue (WS-streamed), 8 action
   buttons, 9 background pollers, 3 locations / 5 NPCs (`constants.py:19-49`),
   win/lose overlay, `SandboxLoop` auto-tick (`sandbox_loop.py`) toggled via `S` key,
   4-arc start menu (`arc_choice.py`, `ui/start_menu.py`).

**Key status changes since prior lens:**
- ISSUE-057 (`PART_OF` location hierarchy) — **FIXED** 2026-06-10, EXP-87
  (`type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` created;
  `client.post_part_of()` added at `client.py:776`).
- ISSUE-059 (tier-A context unbounded) — **FIXED** in EXP-30 (pinned-core +
  ranked-pool model; `TokenBudgetExceededError` on tier0+tierA now structurally
  impossible per `BUSINESS_INTENT.md:67`).
- ISSUE-060 (ACT-3 bribe wrong edge) — **open** (still P2).
- ISSUE-083 (voice tone_judge residual) — **partially fixed** (S25.1 softened
  ECHO_GUARD; captain_sorn failure narrowed to voice-judge strictness).
- EXP-80 (sandbox mode) — **IMPLEMENTED**: `SandboxLoop` at `sandbox_loop.py`;
  toggled by `S` key in `game_window.py`.
- EXP-81 (cross-session memory recall) — **IMPLEMENTED**: `RemembersYouBeat` in
  `run.py:443-447` (ACT 10).
- EXP-83 (integrator quickstart) — **IMPLEMENTED**: `demo_game/quickstart.py` (61
  lines, httpx only, idempotent seed + one dialogue turn).
- EXP-85 (anti-hallucination beat) — **IMPLEMENTED**: `AntiHallucinationBeat` in
  `run.py:435-440` (ACT 9).
- EXP-92 (determinism proof) — **IMPLEMENTED**: `DeterminismBeat` in `run.py:417-424`
  (ACT 8), calls `POST /v1/batch/gossip_tick` twice with `tick_override=42`.

---

## Showcase coverage gap table

Columns: FEATURES.md capability | Route exists? | Shown in demo today (`file:line`) | Gap

| Shipped capability | Route? | Shown in demo today | Gap |
|---|---|---|---|
| **dialogue** — structured output (response + relation_deltas + action + facial_expression), tiered degradation | Yes (`POST /v1/dialogue`, WS) | WS streaming `game_controller.py`; degradation badge `left_panel.py`; scripted `StreamingDialogueBeat` `run_scenes.py:152-203` | `facial_expression` parsed (`game_controller.py:312`) but not rendered; `action` not shown; degradation badge not labelled FULL/GRAPH-ONLY/CANNED for buyer comprehension |
| **gossip** — distortion (omission/exaggeration/role_swap/timeline_shift), seeded RNG, propagation | Yes (`POST /v1/admin/gossip/spread`, trace, correct) | CHAIN tab `ui/gossip_chain.py`; Sorn→Mira→Henryk arc ACT 1; rumor warfare ACT 7; determinism proof ACT 8 | **distortion_type per-hop not surfaced** as readable diff; `distorted_summary` is in the KNOWS_ABOUT edge but CHAIN tab doesn't render it |
| **emotion** — valence/arousal, decay, mood label | Yes (`GET /v1/npc/{id}/emotion`) | EMOTION tab `ui/emotion_panel.py`; scripted `EmotionDisplay` `run_scenes.py:274-295` | Decay-over-time trend not visualised; only current snapshot shown |
| **mood** — mood contagion between co-located/related NPCs | No dedicated route (engine-internal per tick) | None | **Fully unshowcased** — no panel, no scripted beat shows contagion between NPCs |
| **memory_consolidation** — session turns → durable Memory node; arousal-triggered | Yes (`POST /v1/admin/memories/consolidate/{npc_id}`) | MEMORY tab `ui/memory_panel.py`; ACT 4 `MemoryConsolidate`; ACT 10 `RemembersYouBeat` cross-session recall | ACT 10 proves recall end-to-end; **first run cannot show recall** (no prior session exists) — the beat gracefully skips on first run (`remembers_you_beat.py:54-63`) |
| **quest** — lifecycle + atomic reward/currency/item transfer | Yes (`/v1/quest/*`) | PLAYER STATUS quest panel; accept/complete/reward `game_controller.py:489-499`; scripted `QuestDisplay` | Atomic single-transaction reward transfer not made visible to buyer |
| **quest_generation** — engine-generated quests (LLM) | Yes (`POST /v1/admin/quests/generate`) | Generate Quest action `actions_panel.py`, `game_controller.py:197-203` | Adequately shown |
| **events** — materialization, awareness seeding, location scoping | Yes (`/v1/system/events`) | WORLD tab `ui/world_panel.py`; scripted `EventFire` + `WorldFeed` | Location-scoped awareness (who can know what by location) never made legible |
| **faction_politics** — standings, pledges, treaties | Yes (pledges, treaties, reputation admin routes) | POLITICS tab: pledges + leverage (`ui/politics_panel.py`); bribe (ACT 3) | **Treaties not surfaced** anywhere; faction-vs-faction `STANDS_WITH` standings seeded but never rendered; ISSUE-060 breaks the scripted standing path |
| **story_pacing / chapter** — narrative pacing + chapter labels over ticks | Unclear — no visible `/v1/system/chapter` or pacing route in `src/npc_engine/api/routes/` | None | **Fully unshowcased** and likely needs a new route to query |
| **routine / skill / military / clique** | Military: engine-internal; no standalone read routes for routine/skill/clique | Military only: scripted battle ACT 5 `run.py:258-276` + Army seed | **Routine, skill, clique fully unshowcased**; military in scripted runner only, not interactive |
| **interaction** — player action reporting, trade/quest/give proposals | Yes (`POST /v1/interaction`) | TRADE/INVENTORY tabs; Give Item action; `quest_trade_controller.py` | Adequately shown |
| **llm** — pluggable backend | No demo affordance (config-level only) | None | **Unshowcased** — no integrator-facing demo of adapter swap |
| **tts** — pluggable TTS | Hook in `dialogue_ws.py` (`audio_bytes`) | `audio_player.py` plays audio when bytes present | Works but incidental; not framed as a feature |
| **scheduler** — realtime + game_driven clock, tick lease | Yes (`POST /v1/clock/advance`, `GET /v1/clock/state`) | `C` key, SandboxLoop, scripted `ClockTick`; world poller | Off-screen-while-away framing never explicit; tick-lease mechanism invisible |
| **retrieval** — graph RAG, tiered context, token-budget enforcement | Yes (`GET /v1/admin/debug/retrieval`) | None (INSPECT shows raw graph, not retrieval) | **Retrieval quality fully unshowcased** — no "these are the facts retrieved for this answer" view; Phase 15 precision@k ambition has no demo anchor |
| **B.1 auth / rate-limit / idempotency** | Yes (middleware) | Bearer header `client.py:53`; quest idempotency headers `client.py:909-937` | Auth/rate-limit invisible to player (correct) but integrator hello-world at `quickstart.py` does not exercise the 401 path |
| **B.5 reliability — degrade to canned / 503** | Yes (engine-internal degradation) | Degradation badge (`left_panel.py`) | Badge reads as failure colour, not as a resilience feature ("player never crashes") |
| **Anti-hallucination guard** | Yes (engine-internal; eval battery) | ACT 9 `AntiHallucinationBeat` (`run.py:435-440`) | Scripted runner only; **not surfaced in the interactive window** — buyer cannot poke the guard themselves |
| **Proactive / NPC-initiated dialogue** (ROADMAP Phase 14) | Yes (`GET /v1/dialogue/pending`) | `NpcInitiativePoller` polled at `game_window.py:166`; intent bubble overlay via `intent_ui.py` | **Route and poller exist, but bubble is not wired in run.py scripted demo** — only present in interactive window, never staged as a named act |
| **Location hierarchy (PART_OF)** | Yes (`POST /v1/admin/locations/{id}/part_of`, `client.post_part_of()`) | None in demo surfaces (seeder calls `post_part_of` in `seed.py`) | PART_OF edges are seeded but never displayed or used to scope anything in the demo UI |
| **Temporal memory (occurred_at_game_time / is_historical)** | Yes (`POST /v1/admin/memories/{id}` accepts `occurred_at_game_time` + `is_historical`) | None — MEMORY tab shows memory content only | Phase 26 temporal cognition is invisible to buyer |
| **Debug retrieval endpoint** | Yes (`GET /v1/admin/debug/retrieval`) | None | Valuable integrator tool never surfaced even in developer mode |

**Count of unshowcased or materially under-surfaced capabilities: 10.**
Fully unshowcased: **mood contagion, story_pacing/chapter, routine/skill/clique,
retrieval-quality view, proactive dialogue in scripted runner, location hierarchy in
UI, temporal memory, degradation-as-feature framing** (8 distinct clusters),
plus **treaties** and **debug retrieval** as integrator-facing gaps.

---

## Mini-specs (EXP-70 through EXP-99)

Items EXP-70 through EXP-79 are new; items EXP-80 through EXP-99 retain their
original numbering with status annotations.

---

### EXP-70: Proactive dialogue act in the scripted demo runner
Type: demo
Business rationale: BUSINESS_INTENT success criterion 10 ("NPCs proactively initiate
in-character") and §3 ambition ("agentic NPCs that initiate, not just react"). The
engine route (`GET /v1/dialogue/pending`) and the interactive poller both exist
(`npc_initiative_poller.py`, `intent_ui.py`), but the scripted runner never stages
this as a named act — leaving the highest-differentiation engine feature invisible to
a studio evaluating from a recording.
What it does: A new scripted `ProactiveDialogueBeat` in `run.py` / `run_scenes.py`:
(1) advance clock one tick (triggers `proactive_dialogue_engine`), (2) poll
`GET /v1/dialogue/pending?player_id=player_demo`, (3) print and assert at least one
intent came back, (4) respond to the NPC via `POST /v1/dialogue`. Result: the
scripted demo shows an NPC hailing the player unprompted.
Current state: `NpcInitiativePoller` background-polls the route every 5s in the
interactive window (`game_window.py:166-169`), and displays the intent bubble via
`game_window.py:287-301` when intents arrive. The scripted runner has no equivalent.
`run.py:101-458` contains no ProactiveDialogue or pending-intent scene.
Graph/schema additions: none — demo consumes existing API.
API surface: `GET /v1/dialogue/pending` (have: `client.get_pending_intents()` at
`client.py:1317`), then `POST /v1/dialogue` (have).
Composition: new `ProactiveDialogueBeat` in `demo_game/run_scenes.py`; wired as ACT 11
in `run.py`. No new files.
Architecture fit: pure demo-side.
Prerequisite enablers: proactive_dialogue_engine must be wired into tick_scheduler
(ROADMAP Phase 14 — verify it's live, not a stub); `NpcInitiativePoller` already
confirms the route is reachable.
Effort: S   Value: high   Business-fit: high
Risks / unknowns: if the proactive_dialogue_engine produces no intents for the demo
NPCs (depends on goal/need thresholds), the beat will fail gracefully (empty list);
add a seed-side nudge (goal urgency=100 for one NPC) to guarantee a hit.
First slice: one scripted scene that polls the pending endpoint post-tick and prints
what arrives (pass/skip, no hard assert initially).
Open questions: is `proactive_dialogue_engine.run_tick` wired and live (not a stub)?
Confirm against `src/npc_engine/engines/` → OPEN_QUESTIONS.md.

---

### EXP-71: Retrieval-explainer panel ("why did the NPC say that?")
Type: demo
Business rationale: BUSINESS_INTENT §3 "provable retrieval quality (Phase 15)" and
success criterion 2 ("retrieval returns the right memories"). This is the strongest
anti-black-box signal for a technical buyer and is currently completely invisible.
The debug retrieval route (`GET /v1/admin/debug/retrieval`) already exists.
What it does: After each dialogue turn in the interactive window, a new RETRIEVAL tab
(or INSPECT extension) shows the context items that were assembled for that NPC+query:
tier, key, text snippet, token estimate — pulled from `GET /v1/admin/debug/retrieval`.
Turns "the NPC said X" into "the NPC said X because the engine retrieved facts A, B, C".
Current state: `GET /v1/admin/debug/retrieval` is fully implemented
(`src/npc_engine/api/routes/debug_retrieval.py`), returns `ContextItemView` list with
`key`, `tier`, `priority`, `text`, and `total_tokens`. No `EngineClient` method
wraps it; no demo UI panel reads it. The `EngineClient` has no `get_retrieval_debug()`
method at all.
Graph/schema additions: none.
API surface: needs new `EngineClient.get_retrieval_debug(npc_id, query)` wrapping
`GET /v1/admin/debug/retrieval?npc_id=&query=`; then a panel to display it.
Composition: (1) add `get_retrieval_debug(npc_id, query)` to `demo_game/client.py`;
(2) new `demo_game/ui/retrieval_panel.py`; (3) add RETRIEVAL tab to `RightPanel` enum
in `ui/right_panel.py`; (4) wire a post-dialogue callback to refresh the panel.
Architecture fit: pure demo-side (the route already exists in the engine).
Prerequisite enablers: none.
Effort: M   Value: high   Business-fit: high
Risks / unknowns: the panel may need to be refreshed after dialogue completes
(async — need a callback from `game_controller.on_npc_response`); the retrieval query
in the debug endpoint is a free-text string, so use the last player_message as the
query signal.
First slice: add the `EngineClient` method and a raw text dump of top-5 context items
below the last NPC line, without a dedicated tab.
Open questions: does `GET /v1/admin/debug/retrieval` accept `npc_id` + `query` as
query params? Confirm schema in `debug_retrieval.py:16-60` — yes (`npc_id: str`,
`query: str` as `Query` params). No open question.

---

### EXP-72: Gossip distortion diff view ("telephone game" side-by-side)
Type: demo
Business rationale: BUSINESS_INTENT §2 "deterministic, replayable gossip distortion"
and the gossip moat claim. The CHAIN tab shows the hop chain but not content drift per
hop — the visually compelling half. Replaces/supersedes original EXP-84.
What it does: Per-hop view in the CHAIN tab rendering each NPC's `distorted_summary`
+ `distortion_type` side by side (Sorn: "war began" → Mira: "skirmish rumoured" →
Henryk: "merchants fighting"), proving the telephone effect with real engine output.
Current state: CHAIN tab (`ui/gossip_chain.py`) shows the edge chain (NPC, tick,
knowledge_state) but not the `distorted_summary` text. The `KNOWS_ABOUT` edges fetched
at `game_window.py:237-240` carry `distorted_summary` in the response. EXP-84 was
retained in the old spec; this entry supersedes it with corrected `file:line`.
Graph/schema additions: none.
API surface: `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=northern_war_begins` (have:
`client.get_graph_edges()` at `client.py:142`, called at `game_window.py:237-240`);
`GET /v1/admin/gossip/trace/{event_id}` (have: `client.trace_rumor()` at
`client.py:1461`).
Composition: extend `ui/gossip_chain.py` to render `distorted_summary` and
`distortion_type` per row; the chain data already in `RightPanelRenderer._chain_data`.
Architecture fit: pure demo-side.
Prerequisite enablers: none.
Effort: S   Value: high   Business-fit: high
Risks / unknowns: text length per hop may overflow the right panel; ScrollableLog
widgets already support scroll, so wrapping is straightforward.
First slice: add one line of `distorted_summary` (truncated at 80 chars) below each
NPC row in the CHAIN tab.
Open questions: none.

---

### EXP-73: Faction standing board (faction vs faction + player standings)
Type: demo
Business rationale: BUSINESS_INTENT §2 "faction standing dynamics" and the political
layer that the gossip/reputation system runs on. The POLITICS tab covers NPC-level
pledges and leverage, but the inter-faction political map (who hates whom) and the
player's faction trajectory are buried. Replaces/supersedes EXP-98.
What it does: A new FACTION tab (or extension of POLITICS) showing: (a) faction-
faction `STANDS_WITH` edges (seeded at `seed.py:360-363`); (b) player's current
standing with each faction; (c) any active treaties between factions (via
`GET /v1/treaties/factions/{faction_id}`). Makes the political backdrop legible
without any engine changes.
Current state: POLITICS tab shows only pledges + leverage for the active NPC.
Faction-faction standings are seeded but never rendered. Treaties route exists
(`src/npc_engine/api/routes/treaties.py:96-110`, `GET /v1/treaties/factions/{id}`)
but no `EngineClient` method wraps it and no UI reads it.
Graph/schema additions: none.
API surface: `GET /v1/graph/edges/STANDS_WITH` (have: `client.get_graph_edges()` at
`client.py:142`); new `EngineClient.get_faction_treaties(faction_id)` wrapping
`GET /v1/treaties/factions/{faction_id}`.
Composition: extend `ui/politics_panel.py` or add new `ui/faction_board.py`; add a
FACTION tab to `RightPanel` enum; add `get_faction_treaties()` to `client.py`.
Architecture fit: pure demo-side.
Prerequisite enablers: none (treaties route live; standings reachable via generic graph).
Effort: S (standings only) / M (with treaties)   Value: med   Business-fit: med
Risks / unknowns: treaty data may be sparse in the demo seed (no treaties seeded by
default in `seed.py`); faction standings work regardless.
First slice: render the two seeded faction-faction `STANDS_WITH` edges as a small
board in the POLITICS tab.
Open questions: are any treaties seeded by `demo_game/seed.py`? Quick grep: no
`post_treaty` or `create_treaty` call in `seed.py`. Standings are present. Note in
OPEN_QUESTIONS.md.

---

### EXP-74: Temporal memory readout (occurred_at vs recorded_at)
Type: demo
Business rationale: BUSINESS_INTENT §3 "temporal NPC cognition" (Phase 26
`occurred_at_game_time` / `is_historical`) and success criterion 1 (anti-hallucination
at the temporal layer). Phase 26 fixed a real eval failure but the fix is invisible
to a buyer — they see the same MEMORY tab as before.
What it does: Extend the MEMORY tab to show two time fields per memory:
`created_at_game_time` (when recorded) and `occurred_at_game_time` (when it happened)
side by side. Flag `is_historical=True` memories with an "HISTORICAL" badge. For
old_henryk, this makes his past-war memory visually distinct from the current-war
rumour, showing the temporal grounding that prevents conflation.
Current state: MEMORY tab (`ui/memory_panel.py`) shows content + vividness +
emotional_charge but not the two temporal fields. `get_memories()` (`client.py:685`)
returns raw dict including all fields. `NpcMemoryPoller` passes data through.
Graph/schema additions: none — fields already exist on Memory nodes (Phase 26).
API surface: `GET /v1/admin/memories/{character_id}` (have: `client.get_memories()`
at `client.py:685`); no new route needed.
Composition: update `ui/memory_panel.py` to render `occurred_at_game_time` and
`is_historical` when present; no polling or client changes.
Architecture fit: pure demo-side.
Prerequisite enablers: none (Phase 26 already landed).
Effort: S   Value: med   Business-fit: med
Risks / unknowns: the time dict format (`{year, season, day, time_of_day}`) needs
compact formatting to fit in the panel row.
First slice: add `occurred_at` and HISTORICAL badge to each memory row in MEMORY tab.
Open questions: none.

---

### EXP-75: Location hierarchy display (PART_OF parent breadcrumb)
Type: demo
Business rationale: BUSINESS_INTENT §2 "location hierarchy (PART_OF edges between
Location nodes)" — ISSUE-057 was fixed 2026-06-10, the client method exists
(`client.post_part_of()` at `client.py:776`), but the hierarchy is never shown in
the demo UI. Buyers cannot see the spatial depth the engine now supports.
What it does: In the location navigation bar (left panel, `left_panel.py`), show a
parent breadcrumb below the location name (e.g. "The Tavern / Market District / City
of Vren") by reading `PART_OF` edges upward from the active location.
Current state: The location bar shows the flat `LOCATION_DISPLAY_NAMES` name only
(`left_panel.py`). `PART_OF` edges are created by the seeder
(`seed.py` calls `post_part_of`) but never read or rendered. No `EngineClient` method
reads the hierarchy. The route exists via `client.get_graph_edges("PART_OF", ...)`.
Graph/schema additions: none.
API surface: `GET /v1/graph/edges/PART_OF?src_id={location_id}` (have:
`client.get_graph_edges()` at `client.py:142`).
Composition: small addition to `left_panel.py` to read and render the parent chain.
Architecture fit: pure demo-side.
Prerequisite enablers: PART_OF edges seeded by `seed.py` (verify — `seed.py` calls
`post_part_of` per BUSINESS_INTENT `117`).
Effort: S   Value: low   Business-fit: med
Risks / unknowns: if no PART_OF edges are seeded for the three demo locations the
breadcrumb is empty (silent graceful no-op).
First slice: show parent name in the location bar if a PART_OF edge exists; silent
no-op otherwise.
Open questions: does `demo_game/seed.py` actually call `post_part_of` for the three
demo locations? Verify at seed.py — flag to OPEN_QUESTIONS if absent.

---

### EXP-76: Degradation-as-feature relabelling (FULL / GRAPH-ONLY / CANNED)
Type: demo
Business rationale: BUSINESS_INTENT §2 "tiered graceful degradation: never a hard
error to the player" and success criterion 3. The degradation badge reads as a failure
colour, not as a product feature. Replaces/supersedes EXP-86.
What it does: Relabel the degradation badge from a colour-only signal to a named tier:
FULL (green) / GRAPH-ONLY (amber) / CANNED (red + "engine degraded gracefully"). A
one-line tooltip "The player never saw a crash" makes the resilience sell explicit.
Current state: Badge is a coloured dot derived from `degradation_level` field in the
dialogue response; rendered in `left_panel.py`; no textual tier name shown.
`DegradationBadge` widget in `ui/widgets.py` accepts a level int and maps it to colour.
Graph/schema additions: none.
API surface: `degradation_level` already in the `DialogueResponse` schema.
Composition: update `DegradationBadge` in `ui/widgets.py` to render a short tier
label alongside the dot; no new files.
Architecture fit: pure demo-side.
Prerequisite enablers: none.
Effort: S   Value: med   Business-fit: high
Risks / unknowns: must not look like the demo is in an error state; copy is critical.
First slice: add the tier name string to the badge render; defer tooltip.
Open questions: what integer values map to which tiers? Verify `degradation_level`
enum in `src/npc_engine/api/schemas.py` before mapping.

---

### EXP-77: Facial-expression glyph rendering
Type: demo
Business rationale: BUSINESS_INTENT §2 "structured dialogue output: facial_expression"
— the engine returns it, the demo ignores it visually. Even a simple glyph makes NPCs
feel reactive in a way that impresses buyers. Replaces/supersedes EXP-94.
What it does: Map `facial_expression.type` (neutral/angry/afraid/pleased/suspicious
etc.) to a coloured glyph beside the NPC name in the dialogue log — no art required.
Current state: `facial_expression` is parsed at `game_controller.py:312` into the
response turn but never rendered. The left panel only shows the NPC name + dialogue
text.
Graph/schema additions: none.
API surface: `facial_expression` already in the dialogue response.
Composition: extend `left_panel.py` / `NpcListWidget` to render a glyph from a
`EXPRESSION_GLYPHS` dict constant.
Architecture fit: pure demo-side.
Prerequisite enablers: none.
Effort: S   Value: med   Business-fit: med
Risks / unknowns: `facial_expression` may sometimes be absent or None; default to
neutral glyph.
First slice: add a one-char emoji/ASCII glyph next to the last NPC response header.
Open questions: does the dialogue response always include `facial_expression`? Verify
`DialogueResponse` schema — if nullable, handle None gracefully.

---

### EXP-78: Relationship-delta live ticker (trust / affection / fear per turn)
Type: demo
Business rationale: BUSINESS_INTENT §2 "structured dialogue output: relation_deltas"
and §4 success criterion 10 (bounded mutation). Relationship drift is the core of
"NPCs that remember shared history" but is currently invisible. Replaces/supersedes
EXP-91.
What it does: After each turn, a transient toast (3s) at the bottom of the dialogue
log shows the relation_deltas returned — "+5 trust, -2 fear". The running totals from
`GET /v1/npc/{id}/relationship/{other_id}` are shown in a small side strip.
Current state: `relation_deltas` are parsed and applied to the negotiation band at
`game_controller.py:515-527` (`_apply_relation_band`) but never shown to the player
as a labelled delta.
Graph/schema additions: none.
API surface: `relation_deltas` already in the dialogue response; `GET /v1/npc/{id}/
relationship/{other_id}` (have: `client.get_npc_relationship()` at `client.py:257`).
Composition: extend `left_panel.py` to render a delta toast after each turn; extend
`relation_ticker.py` or add a small strip to the NPC header.
Architecture fit: pure demo-side.
Prerequisite enablers: none.
Effort: S   Value: med   Business-fit: med
Risks / unknowns: deltas can be zero on many turns; pair with dialogue scenarios known
to move the relationship (bribe/quest/trust-building).
First slice: render last turn's `relation_deltas` as a short "+N trust" transient string.
Open questions: none.

---

### EXP-79: Cinematic / recording mode (title cards + deterministic pacing)
Type: demo
Business rationale: BUSINESS_INTENT §1 "first impression and sales artifact". A
pitch-ready recording needs fixed pacing, act titles, and no dev UI noise. Replaces/
supersedes EXP-88.
What it does: A `--cinematic` flag on `DemoRunner`: larger font output, act title
cards printed before each scene group, 200ms delay between lines (configurable),
and optional `pygame.image.save` per named beat for screenshot-based video capture.
The LLM cache (`LLMCache` at `run.py:60-91`) guarantees deterministic content.
Current state: `--cached` replay exists but output is dev-formatted (no title cards,
raw `> ok` lines). Font sizes and timing are hardcoded for terminal readability, not
presentation. `make demo-snapshot` snapshots state but not a recording surface.
Graph/schema additions: none.
API surface: none new — pure presentation over cached path.
Composition: add a `cinematic: bool` flag to `DemoRunner`; update `print_step` /
`print_ok` / `print_cue` to use richer formatting when cinematic=True; add
`--cinematic` CLI arg.
Architecture fit: pure demo-side.
Prerequisite enablers: a clean end-to-end run — ISSUE-060 (ACT-3 abort) still blocks
the full Munich arc; village/tavern arcs run clean.
Effort: M   Value: med   Business-fit: high
Risks / unknowns: ISSUE-060 must be fixed to record the full 10-act arc. Until then
only the eval-world arcs (`run_village_crisis`, `run_tavern_intrigue`) run clean.
First slice: title card per act for the village arc; defer screenshot capture.
Open questions: video capture in-process (pygame frame dump) vs external (OBS)?
→ OPEN_QUESTIONS.md.

---

### EXP-80: Free-play / sandbox mode — IMPLEMENTED
Type: demo
**Status: IMPLEMENTED** as of EXP-80 batch. `SandboxLoop` at
`demo_game/sandbox_loop.py` auto-advances `advance_clock(1)` every `interval_s`
seconds. `S` key toggles it in `game_window.py`. `ArcChoice.FREE_PLAY` exists in
`arc_choice.py` and is selectable from `ui/start_menu.py`.
Business rationale: BUSINESS_INTENT success criterion 7 and §1 off-screen-simulation
thesis.
What it does: (implemented) Auto-tick background thread; toggled by S in window;
reachable as FREE_PLAY arc from the start menu.
Current state: Fully implemented. The `SandboxLoop` thread exists and is wired.
Gap remaining: The `SandboxLoop` uses `print()` for errors (`sandbox_loop.py:81`)
rather than structured logging — ISSUE-053 baseline. Sandbox mode is not announced
in `docs/DEMO_SCRIPT.md` or the README.
API surface: `POST /v1/clock/advance` (have: `client.advance_clock()` at `client.py:261`).
Composition: done.
Architecture fit: demo-only.
Prerequisite enablers: none — implemented.
Effort: DONE   Value: high   Business-fit: high
Risks / unknowns: none material.
First slice: n/a.
Open questions: none.

---

### EXP-81: Cross-session memory recall demo — IMPLEMENTED
Type: demo
**Status: IMPLEMENTED** as ACT 10 in `demo_game/run.py:443-447` via
`RemembersYouBeat` (`demo_game/remembers_you_beat.py`). The beat calls
`client.get_npc_relationship(npc_id, player_id)` and then
`client.post_dialogue(player_message=_MEMORY_MESSAGE)`, printing relationship
trust/fear/affection and the first 120 chars of the NPC recall.
Business rationale: BUSINESS_INTENT §2 first commitment — "persistent knowledge /
relationships / emotion".
What it does: (implemented) Fetches RELATES_TO edge, prints trust/fear/affection/
interaction_count, fires "Do you remember the last time we spoke?" and shows the NPC
response.
Current state: Fully implemented. On first run the beat gracefully skips (no prior
relationship edge yet, `remembers_you_beat.py:54-63`).
Gap remaining: The interactive pygame window has no equivalent "start new session"
button or cross-session recall UI surface — the scripted runner demonstrates it but
a buyer cannot interactively prove it in the window.
API surface: `client.get_npc_relationship()` at `client.py:257`; `client.post_dialogue()`.
Composition: done (scripted); **window enhancement** remains a follow-up
(a "New Session" button in `ui/actions_panel.py` that rotates `session_id`).
Architecture fit: demo-only.
Prerequisite enablers: none (ISSUE-059 FIXED in EXP-30).
Effort: DONE (scripted) / S (window button)   Value: high   Business-fit: high
Risks / unknowns: none.
First slice: n/a for scripted; window button is the residual slice.
Open questions: none.

---

### EXP-82: Proactive / NPC-initiated dialogue window surface
Type: demo
Business rationale: BUSINESS_INTENT §3 ambition ("agentic NPCs that initiate")
and success criterion 10. The `NpcInitiativePoller` and intent bubble overlay exist
in the interactive window. See also EXP-70 (scripted runner surface).
What it does: When the window poller returns a pending intent, display an intent
bubble with the NPC name + trigger phrase (from `intent_ui.TRIGGER_PHRASES`) and
highlight the relevant NPC in the list; clicking the NPC auto-fills the dialogue
input with the trigger phrase so the player can respond.
Current state: `NpcInitiativePoller` polled at `game_window.py:166-169`;
`INTENT_BUBBLE_DISPLAY_SECONDS` / `TRIGGER_PHRASES` defined in `intent_ui.py`.
Intent bubble fields (`_intent_bubble_text`, `_intent_bubble_npc`) tracked at
`game_window.py:111-112`; display logic exists at `game_window.py:287-301`.
The bubble currently only shows the trigger phrase — it does not highlight the NPC
or pre-fill the input.
Graph/schema additions: none.
API surface: `GET /v1/dialogue/pending` (have: `client.get_pending_intents()` at
`client.py:1317`).
Composition: extend `game_window.py` event loop to highlight the intent NPC and
pre-fill input when the bubble is tapped.
Architecture fit: pure demo-side.
Prerequisite enablers: proactive_dialogue_engine must produce intents for demo NPCs
(verify it's wired, not a stub — see EXP-70 open question).
Effort: S   Value: high   Business-fit: high
Risks / unknowns: blocked if proactive engine produces no intents at demo scale.
First slice: confirm intent arrives after one clock tick; render the bubble with NPC
highlight.
Open questions: see EXP-70 open question re: engine stub status.

---

### EXP-83: Integrator hello-world quickstart — IMPLEMENTED
Type: demo
**Status: IMPLEMENTED** as `demo_game/quickstart.py` (61 lines, httpx only, no
`EngineClient` import). Calls `/health`, seeds one location + NPC + event idempotently,
posts one `/v1/dialogue` turn, prints the NPC reply.
Business rationale: BUSINESS_INTENT success criterion 5.
Current state: Fully implemented. No `make hello` target yet in the Makefile — that
was in the first-slice plan and remains outstanding.
Gap remaining: (1) `make hello` Makefile target not confirmed present (verify);
(2) the 401-demo path is not shown (wrong key → clear error); (3) `quickstart.py`
calls `.get("response_text")` but the actual field is `npc_response` per the
`DialogueResponse` schema — may print an empty string; (4) README "Hello, NPC"
section not written.
API surface: `GET /health`, `POST /v1/dialogue`.
Composition: done (script); Makefile target + README section outstanding.
Architecture fit: demo-only.
Effort: DONE (script) / S (Makefile + README + field fix)   Value: high   Business-fit: high
Risks / unknowns: field name bug (`response_text` vs `npc_response`) may silently
print empty on first run.
First slice: fix the field name (`npc_response`), add `make hello`, add one README line.
Open questions: is `make hello` already present in `Makefile`? Verify.

---

### EXP-84: (merged into EXP-72)
This spec is superseded by EXP-72 (Gossip distortion diff view) which uses the
correct current `file:line` references.

---

### EXP-85: Anti-hallucination beat in scripted runner — IMPLEMENTED
Type: demo
**Status: IMPLEMENTED** as ACT 9 in `demo_game/run.py:435-440` via
`AntiHallucinationBeat` (`demo_game/run_scenes.py`, imported in `run.py:37`). The beat
asks Aldric about the northern war (Aldric has no `KNOWS_ABOUT northern_war_begins`
edge) and verifies the engine deflects.
Business rationale: BUSINESS_INTENT success criterion 1 — the #1 buyer bar.
Current state: Implemented in scripted runner.
Gap remaining: **Not surfaced in the interactive window.** A buyer running the
window cannot interactively prove the guard. An INSPECT+KNOWLEDGE combination could
show the absence of the `KNOWS_ABOUT` edge, but there is no dedicated "test the guard"
UI affordance.
Composition: done (scripted); window surface remains optional.
Effort: DONE (scripted)   Value: high   Business-fit: high
First slice: n/a.
Open questions: none.

---

### EXP-86: (merged into EXP-76)
This spec is superseded by EXP-76 (Degradation-as-feature relabelling).

---

### EXP-87: Richer world — more NPCs / locations on a location hierarchy
Type: demo
Business rationale: BUSINESS_INTENT §3 production-scale ambition and "living world"
thesis. A 5-NPC / 3-location world looks like a toy; depth sells middleware.
What it does: Expand the seed world to ~12-15 NPCs across a nested geography (market
→ district → city) using `PART_OF` edges (now supported — ISSUE-057 FIXED). Adds
visible depth to every existing panel.
Current state: 3 flat locations, 5 NPCs (`constants.py:19-49`, `seed.py`).
`PART_OF` infrastructure is live. EXP-75 surfaces the hierarchy in the UI.
Graph/schema additions: none needed (PART_OF type registered). Demo-side: expand
`_LOCATIONS` / `_NPCS` / `_NPC_LOCATED_AT` tables in `seed.py`; update
`constants.py:LOCATION_NPC_MAP` and `LOCATION_DISPLAY_NAMES`.
API surface: `POST /v1/graph/nodes/*`, `POST /v1/graph/edges/*` (have), `post_part_of`
(have: `client.py:776`).
Composition: extend `seed.py` data tables; extend `constants.py`; nav bar scales
automatically.
Architecture fit: demo-only.
Prerequisite enablers: none (ISSUE-057 FIXED); pairs with EXP-75 (hierarchy display).
Effort: M (more NPCs) / L (with hierarchy)   Value: med   Business-fit: high
Risks / unknowns: more NPCs = more knowledge accumulation; ISSUE-059 is FIXED so this
is no longer a blocker. Win/lose logic (`game_end_checker.py`) assumes 3 factions —
must be reviewed before adding new factions.
First slice: add 3 flat NPCs + 1 location; defer `PART_OF` hierarchy until EXP-75 UI
is ready.
Open questions: does the win/lose logic generalise beyond 3 factions?
→ OPEN_QUESTIONS.md.

---

### EXP-88: (merged into EXP-79)
This spec is superseded by EXP-79 (Cinematic / recording mode).

---

### EXP-89: Mood-contagion visualiser
Type: demo
Business rationale: FEATURES.md mood contagion ✅ shipped but fully unshowcased.
"Living world" claim (BUSINESS_INTENT §1).
What it does: Extend the EMOTION tab (or add a CONTAGION tab) showing two co-located
NPCs' emotions; advance clock and show one NPC's negative mood shifting the
neighbour's value, annotated with "mood contagion fired".
Current state: EMOTION tab shows single active NPC snapshot only (`ui/emotion_panel.py`,
`emotion_poller.py`). Poller tracks one NPC at a time (`EmotionPoller.set_active_npc`).
No multi-NPC view exists.
Graph/schema additions: none.
API surface: `GET /v1/npc/{id}/emotion` (have: `client.get_npc_emotion()` at
`client.py:238`); `POST /v1/clock/advance`.
Composition: poll two co-located NPCs' emotions (or extend `EmotionPoller` to track a
list); add a two-row section to `ui/emotion_panel.py`.
Architecture fit: pure demo-side.
Prerequisite enablers: none.
Effort: M   Value: med   Business-fit: med
Risks / unknowns: contagion magnitude per tick may be subtle; needs a strong event
(market fire seed) and relationship weight to be visible.
First slice: poll two co-located NPCs and show side-by-side current emotion values;
defer contagion annotation.
Open questions: which seeded NPC pair has a relationship strong enough for visible
contagion? → verify against engine mood-contagion params.

---

### EXP-90: (merged into EXP-71)
This spec is superseded by EXP-71 (Retrieval-explainer panel), which uses the correct
current `file:line` for `debug_retrieval.py`.

---

### EXP-91: (merged into EXP-78)
This spec is superseded by EXP-78 (Relationship-delta live ticker).

---

### EXP-92: Determinism / replay proof toggle — IMPLEMENTED
Type: demo
**Status: IMPLEMENTED** as ACT 8 in `demo_game/run.py:417-424` via `DeterminismBeat`
(`demo_game/determinism_beat.py`). Calls `POST /v1/batch/gossip_tick` twice with
`tick_override=42`, extracts `seeds_used` from both responses, prints a two-column
comparison table, asserts `seeds_match=True`.
Business rationale: BUSINESS_INTENT §2 "deterministic, replayable gossip distortion".
Current state: Implemented in scripted runner. Calls `_GOSSIP_TICK_PATH =
"/v1/batch/gossip_tick"` directly via the underlying `_client` (bypasses
`EngineClient` wrapper — a minor SOLID smell but acceptable for a demo beat).
Gap remaining: Not surfaced in the interactive window; the window has no "replay this
tick" affordance.
Effort: DONE (scripted)   Value: med   Business-fit: med
First slice: n/a.
Open questions: none.

---

### EXP-93: Fix ISSUE-060 (scripted demo ACT-3 abort)
Type: demo
Business rationale: BUSINESS_INTENT success criterion 5 — a demo that exits non-zero
mid-run is a direct credibility hit.
What it does: Replace the broken `put_npc_reputation` call in `BribeScene`
(`run_scenes.py`) with `client.adjust_npc_reputation()` (`client.py:1386`) which
targets `POST /v1/admin/characters/{id}/reputation/{faction}/adjust` — the canonical
player→faction standing route.
Current state: ISSUE-060 open (P2). `BribeScene.execute()` (`run_scenes.py:210-244`)
calls `client.put_npc_reputation` (`client.py:1360`) which emits a `STANDS_WITH`
edge between two Characters, but `stands_with.yaml` requires faction→faction (not
character→faction). The 404 aborts ACT 3. `client.adjust_npc_reputation()` at
`client.py:1386` is the correct method and already exists.
Graph/schema additions: none if `adjust_npc_reputation` covers player→faction (likely;
verify the `STANDS_WITH` schema for character→faction semantics).
API surface: `POST /v1/admin/characters/{id}/reputation/{faction}/adjust` (have:
`client.adjust_npc_reputation()` at `client.py:1386`).
Composition: update `BribeScene.execute()` in `run_scenes.py` to call
`adjust_npc_reputation` instead of `put_npc_reputation`; re-run `make demo-run` to
find downstream failures.
Architecture fit: pure demo-side (single method swap + verification run).
Prerequisite enablers: none.
Effort: S (if adjust works) / M (if schema change needed)   Value: high   Business-fit: high
Risks / unknowns: ISSUE-060 notes "additional act bugs may lurk beyond ACT 3" —
budget for downstream fixes once ACT 3 passes.
First slice: swap the method and run `make demo-run --dry-run` to surface any later
failures.
Open questions: does `stands_with.yaml` accept character→faction, or is a new
`player_stands_with_faction.yaml` edge type needed? → DECISIONS.md first.

---

### EXP-94: (merged into EXP-77)
This spec is superseded by EXP-77 (Facial-expression glyph rendering).

---

### EXP-95: In-window scenario picker (unify scripted arcs + free-play)
Type: demo
Business rationale: BUSINESS_INTENT §1 sales-artifact framing — one launch point for
evaluators.
What it does: A start screen offering Munich demo, Village Crisis, Tavern Intrigue,
or Free-Play.
Current state: `ArcChoice` enum exists (`arc_choice.py:14-24`) with MUNICH / VILLAGE /
TAVERN / FREE_PLAY values. `ui/start_menu.py` exists. `__main__.py` likely wires
arc selection. The menu is already substantially implemented.
Graph/schema additions: none.
API surface: existing seed + dialogue routes per arc.
Composition: verify `__main__.py` routes all four arcs; ensure the start menu is
accessible from `make demo`.
Architecture fit: demo-only.
Prerequisite enablers: EXP-80 (FREE_PLAY implemented).
Effort: S (verify/complete) / M (if not yet wired)   Value: med   Business-fit: med
Risks / unknowns: DEC-068 = one world per graph; switching arcs at runtime requires
a reseed step (slow).
First slice: verify the four arcs route correctly from `__main__.py`.
Open questions: can multiple eval worlds coexist in one graph? → OPEN_QUESTIONS.md.

---

### EXP-96: Story-pacing / chapter readout
Type: demo
Business rationale: FEATURES.md **story_pacing/chapter** (🟡) is fully unshowcased.
What it does: A small readout in the WORLD tab showing the current chapter label /
pacing state.
Current state: Not surfaced anywhere in `demo_game/`. No visible
`/v1/system/chapter` or pacing read route in `src/npc_engine/api/routes/` (not in
the route glob). `story_pacing` engine is 🟡 (thin).
Graph/schema additions: none in demo.
API surface: **needs an engine route** exposing chapter/pacing state; unclear one
exists. Verify `src/npc_engine/engines/story_pacing/` before implementing.
Composition: extend `ui/world_panel.py`; depends on route existing.
Architecture fit: **depends on engine exposing pacing state**.
Prerequisite enablers: engine pacing/chapter read route.
Effort: S (demo) + engine dependency   Value: low   Business-fit: med
Risks / unknowns: story_pacing is thin (🟡); may not be query-able.
First slice: deferred until an engine route is confirmed.
Open questions: is there any chapter/pacing read endpoint today?
→ OPEN_QUESTIONS.md.

---

### EXP-97: Live gossip-activity counter per tick
Type: demo
Business rationale: BUSINESS_INTENT §4 criterion 7 ("world runs off-screen at scale").
What it does: After each clock advance, show how many gossip pairs fired this tick.
Current state: `GET /v1/system/engines` (have: `client.get_engine_status()` at
`client.py:323`) returns `last_tick_id`, `error_count` etc. but not a pairs-fired
count. WORLD tab `ui/world_panel.py` renders engine status already.
Graph/schema additions: none in demo.
API surface: `GET /v1/system/engines` (have) — may need engine extension for
`gossip_pairs_this_tick`.
Composition: extend `world_panel`/`world_poller` to display the count.
Architecture fit: demo-only if metric exposed; otherwise **depends on engine**.
Prerequisite enablers: engine per-tick activity metric.
Effort: S + possible engine dependency   Value: med   Business-fit: high
Risks / unknowns: at 5-NPC demo scale the count is small; pairs best with EXP-87.
First slice: show event-materialised count from the existing world feed; defer
pairs-fired.
Open questions: does `/v1/system/engines` report gossip pairs per tick?
→ OPEN_QUESTIONS.md.

---

### EXP-98: (merged into EXP-73)
This spec is superseded by EXP-73 (Faction standing board).

---

### EXP-99: Needs-driven behaviour demo
Type: demo
Business rationale: FEATURES.md **routine** (🟡) + seeded Need nodes (`seed.py`).
What it does: Advance the clock to show need decay and connect a need crossing a
threshold to a visible NPC behaviour (mood shift or goal formation).
Current state: NEEDS tab (`ui/needs_panel.py`, `npc_needs_poller.py`) shows current
need levels. Decay-over-ticks not shown. Need→behaviour coupling unclear (routine
engine 🟡).
Graph/schema additions: none.
API surface: `GET` Need nodes via `client.get_needs_for_npc()` at `client.py:1299`;
`POST /v1/clock/advance`.
Composition: extend `needs_panel` to show decay across ticks; annotate threshold
crossings.
Architecture fit: demo-only for decay; need→behaviour **depends on routine engine**.
Prerequisite enablers: verify routine engine is wired and consumes Need nodes.
Effort: M   Value: low   Business-fit: med
Risks / unknowns: Need nodes may be decorative if routine engine doesn't consume them.
First slice: show need levels dropping across several clock advances (decay only).
Open questions: does the engine actually act on needs? → OPEN_QUESTIONS.md.

---

## Top 3 (highest value, buildable today)

1. **EXP-72 — Gossip distortion diff view**: the highest-leverage S-effort demo
   enhancement — data is already in the `KNOWS_ABOUT` edge payload; CHAIN tab just
   needs to render `distorted_summary` per hop. Directly surfaces the gossip moat.

2. **EXP-71 — Retrieval-explainer panel**: the debug route already exists; adding one
   `EngineClient` method and a panel turns the LLM from "magic box" to "grounded in
   these N facts" — directly addresses the top buyer trust gap. Effort M; no engine
   changes needed.

3. **EXP-70 — Proactive dialogue act in scripted runner**: the route and the
   interactive-window poller both exist; staging a named "ACT 11 — NPC hails the
   player" beat makes the highest-differentiation engine feature visible in a recording.
   Effort S (assuming the proactive engine is live).

Honourable mention: **EXP-93** (fix ISSUE-060 ACT-3 abort) is a prerequisite for
any full-arc recording; one method swap in `run_scenes.py`.
Previously-highest: **EXP-81 and EXP-85 are now implemented** (ACTs 10 and 9 of the
scripted runner). **EXP-80 and EXP-92 are also implemented**.

---

## Items that need engine-side route enablers (not pure demo-side)

| EXP | What the engine needs |
|-----|-----------------------|
| EXP-70 | Verify `proactive_dialogue_engine` is live (not a stub) |
| EXP-82 | Same as EXP-70 |
| EXP-96 | A chapter/pacing read route does not appear to exist |
| EXP-97 | `GET /v1/system/engines` may need a `gossip_pairs_this_tick` field |

All other EXPs (EXP-71 through EXP-79, EXP-87, EXP-89, EXP-93, EXP-95, EXP-99)
are pure demo-side or require only a new `EngineClient` wrapper method.

---

## Notes / assumptions

- (ASSUMPTION) The interactive window is the primary "demo as product" surface;
  the scripted runner is the recording/pitch surface. Most UI proposals target the
  window; ACT-N beats target the scripted runner.
- (FACT) EXP-80, EXP-81, EXP-83, EXP-85, EXP-92 are IMPLEMENTED. Their former
  "top 3" slots are vacated; EXP-72, EXP-71, EXP-70 are the new top 3.
- (FACT) ISSUE-057 (PART_OF) and ISSUE-059 (tier-A budget) are both FIXED.
  ISSUE-060 (ACT-3 abort) remains open.
- All `file:line` citations are against `demo_game/` (a standalone client); no
  `src/` change is proposed except where explicitly flagged as engine-dependent.
- EXP-84, EXP-86, EXP-88, EXP-90, EXP-91, EXP-94, EXP-98 are superseded by
  updated EXP-70 through EXP-79 entries which carry corrected `file:line`.
