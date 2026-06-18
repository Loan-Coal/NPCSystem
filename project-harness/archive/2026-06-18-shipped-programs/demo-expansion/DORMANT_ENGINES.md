# DORMANT_ENGINES.md — Pillar 1: surfacing built-but-unused gameplay engines

**Lens:** D1 (Dormant-engine surfacing). Read-only analysis of `src/npc_engine/engines/`,
`src/npc_engine/api/routes/`, and `demo_game/`. Scores against the §3 rubric and §4 verdict
in `DEMO_INTENT.md` (D0). All claims cite `file:line`.

**Mandate:** for each dormant *gameplay* engine, a §4 mini-spec — player fantasy, reachability
(does a route + `EngineClient` method exist?), and a concrete pygame mechanic modelled on the
existing 14-tab `ui/right_panel.py` + 10-poller framework (D0 §2.4/§2.5). UI is cheap; the
cost is the REST route + `EngineClient` method.

---

## 1. Triage table

Every engine in `src/npc_engine/engines/` triaged. "demo refs" = `grep -ril <name> demo_game/`
(false positives noted). Route = a dedicated `api/routes/<x>.py`. Client = an `EngineClient`
method that calls it.

| Engine | Gameplay? | Route exists? | EngineClient method? | demo refs | Verdict |
|--------|-----------|---------------|----------------------|-----------|---------|
| **oath** (`oath_engine.py`) | **yes** — swear/break vows | **yes** `pledges.py` (create/list/break) | **partial** — `post_pledge`+`get_pledges_for_npc` exist; **no** `break_pledge` wrapper | 0 | **KEEP — type-A** |
| **treaty** (`treaty_engine.py`) | **yes** — faction pacts | **yes** `treaties.py` (create/list/expire/break) | **no** | 0 | **KEEP — type-B (client method only)** |
| **investigation** (`investigation_engine.py`) | **yes** — detective/whodunit | **no** | no | 0 | **KEEP — type-B (route+client)** |
| **military** (`military_engine.py`) | **yes** — battles write `CONTROLS` (= LOSE edge) | partial (`factions.py` CRUD, no battle route) | no (only reads `CONTROLS` edges) | 3* | **KEEP — type-B/C (ties to D3 lose-state)** |
| **chapter** (`chapter_engine.py`) | **yes** — act/season banner | **no** | no | 0 | **KEEP — type-B (route+client)** |
| **story_pacing** (`story_pacing_engine.py`) | meta (gates events/quests) | **no** (writes `WorldState` only) | reachable via `get_world_state` | 0 | **KEEP-lite — type-A read-only HUD** |
| **succession** (`succession_engine.py`) | yes — heir replaces dead leader | **no** | no | 0 | drop (no death/leader loop in demo world; high content cost, low demo-fit) |
| **clique** (`clique_formation_engine.py`) | yes — social sub-groups form | **no** | no | 0 | drop (needs ≫5 NPCs to read as cliques; low demo-fit at current scale) |
| **faction_politics** (`faction_politics_engine.py`) | partial — standing decay/rules | via `reputation`/`factions` (standings already shown POLITICS tab) | indirect | 8* | drop (already surfaced as POLITICS tab + standings; not dormant) |
| agenda / intent_formation | yes (NPC intent) | no | no | 0 | drop (surfaced indirectly via `npc_initiative_poller` GOALS/initiative) |
| planning | yes (NPC plans) | no | 1* (substring of "planning"? false) | 1 | drop (infra-ish; no player verb) |
| routine | yes (schedules) | `schedules.py` | no | 0 | drop (ambient; low demo-fit, no player agency) |
| skill | yes (NPC progression) | `skills.py` | 1* | 1 | drop (NPC-side stat; low player-value, no verb) |
| reputation | yes | `reputation.py` | yes | 11 | drop — already core to win loop, not dormant |
| events | yes | (fired via clock/scenes) | yes | 23 | drop — already surfaced (WORLD feed, scenes) |
| mood / mood_contagion | yes | (emotion surface) | yes | 6 | drop — surfaced via EMOTION tab + `emotion_poller` |
| need / need_decay | yes | (needs surface) | yes | 20 | drop — surfaced via NEEDS tab + `npc_needs_poller` |
| economy / pricing | yes | `economy.py`/`items.py` | yes (`post_trade`) | 19 | drop — surfaced via TRADE/INVENTORY |
| memory / consolidation | yes | `memories.py` | yes | many | drop — surfaced via MEMORY tab |
| gossip | yes | `gossip_spread.py`/`rumors.py` | yes | many | drop — surfaced (CHAIN tab, rumor warfare) |
| quest / quest_generation | yes | `quest*.py` | yes | many | drop — surfaced (quest lifecycle) |
| dialogue / proactive / context_relevance / knowledge_learning / relationship / interaction | yes | yes | yes | many | drop — core loop, surfaced |
| **contracts** | **NO** (LLM prompt-contract/config loader — D0 trap) | n/a | n/a | 0 | **DROP — infra** |
| **llm** | NO (adapter layer) | n/a | n/a | — | **DROP — infra** |
| **idempotency** | NO | n/a | n/a | 0 | **DROP — infra** |
| **embedding_invalidation** | NO | n/a | n/a | 0 | **DROP — infra** |
| **base_engine** | NO (ABC) | n/a | n/a | — | **DROP — infra** |
| **memory_consolidation** | NO (background compaction) | (`/memories/consolidate`) | yes | — | **DROP — infra (already wired)** |
| **tts** | NO (audio synth) | n/a | n/a | — | **DROP — infra, no gameplay** |
| **currency** | borderline | via economy | yes (`gold_poller`) | 19 | drop — surfaced (PLAYER STATUS gold) |

*Footnotes on false-positive demo refs:* `military`(3) = `iron_legion`/`CONTROLS` strings in
`game_end_checker.py`/`game_end_poller.py`/`run.py`, **not** the `MilitaryEngine` itself — the
engine that *writes* `CONTROLS` is unsurfaced; the demo only *reads* the edge. `faction`(27)/
`politics`(8) = seed factions + the existing POLITICS tab (already surfaced, not the dormant
`FactionPoliticsEngine`). `planning`(1)/`skill`(1) = incidental substrings. So the genuinely
**dormant gameplay engines are: oath, treaty, investigation, military, chapter, story_pacing.**

---

## 2. Reachability summary (the hard boundary, D0 §2.7)

- **oath** — the D0 lead is **confirmed**: `oath` is *largely* type-A. `EngineClient.post_pledge`
  (`client.py:1226`) and `get_pledges_for_npc` (`client.py:1257`) already call the `pledges.py`
  route. The only gap is **breaking** a pledge with consequence: the route
  `POST /pledges/characters/{id}/break` exists (`pledges.py:114`) but **no `EngineClient.break_pledge`
  wrapper** exists (grep confirms only `post_pledge`/`get_pledges_for_npc`). So "swear an oath +
  see it listed" ships today (A); "break it and feel the relationship hit" needs a ~10-line client
  method (trivially A-adjacent).
- **treaty** — type-B: full route `treaties.py` (create/list/expire/break) but **zero** client
  methods. Needs `EngineClient.create_treaty / get_faction_treaties / break_treaty`.
- **investigation** — type-B: `InvestigationEngine.get_investigation_context`
  (`investigation_engine.py:39`) is query-only and LLM-ready, but **no `api/routes/investigations.py`**
  and no client method. Needs route + method.
- **military** — type-B/C: `MilitaryEngine.run_tick` writes `CONTROLS`/battle Events
  (`military_engine.py:47`) but is a pure tick engine with **no command route** to let a player
  reinforce/attack. Surfacing *player influence* over a battle is the keystone that makes D0's
  inert lose condition reachable — but that's a D3 economy call (type-C: needs a DECISIONS entry on
  whether the player gets a military verb).
- **chapter** — type-B: `ChapterEngine` writes `CHAPTER` nodes (`chapter_engine.py:289`); no route,
  no client method. A read-only `GET /chapters/current` + client method surfaces it as a banner.
- **story_pacing** — type-A (read-only): writes `max_event_severity`/`quest_generation_rate` onto
  `WorldState` (`story_pacing_engine.py:79-85`), which `EngineClient.get_world_state` already reads.
  A "tension meter" HUD needs **no new route** — just read those two world fields.

---

## 3. Highest-value picks (preview; full specs in §4)

1. **DEMO-D1-01 (oath)** — type-A, high player-value, high demo-fit: a *promise that persists and
   breaks with a felt relationship cost* is the relationships-as-state moat (§1a.3) made into a
   player verb. Ships now.
2. **DEMO-D1-03 (investigation)** — type-B but the single best demo-fit: a "solve the crime" panel
   that surfaces alibi/rumor *contradictions* from the graph IS the knowledge-provenance moat
   (§1a.2) turned into gameplay. One route enables it.
3. **DEMO-D1-02 (treaty)** — type-B, high demo-fit: broker/break faction pacts as a second
   tensioned objective axis (feeds D3's multi-objective win). One client method (route exists).

---

## 4. Mini-specs

### DEMO-D1-01: Swear & Break an Oath (pledge verb with felt consequence)
Pillar: dormant-engine
Player fantasy: Swear a binding oath to an NPC (protect / serve / fealty / vendetta) — and when you break it, watch the relationship and their memory of you turn cold.
Why it matters: Directly showcases moat §1a.3 (relationships-and-emotion are *state, not flavour*): a pledge persists across ticks, and breaking it applies a durable relationship penalty the player *feels* in later dialogue. Adds a real agency/consequence verb to the loop D0 §4 calls single-axis.
Current state: `OathEngine.run_tick` (oath_engine.py:28) already expires/violates pledges on every tick; route `pledges.py` create/list/break all live; `EngineClient.post_pledge` (client.py:1226) + `get_pledges_for_npc` (client.py:1257) already exist. Nothing in `demo_game/` calls them (0 refs).
Engine capability used: `pledges.py` create (`:66`) / list (`:95`) / break (`:114`); `OathEngine` enforces expiry+violation each tick (oath_engine.py:46-64); `break_pledge` applies relationship consequences (pledges.py:120 docstring).
Reachability: **A** for swear+list (`post_pledge`/`get_pledges_for_npc` exist); the break path needs a ~10-line `EngineClient.break_pledge` wrapper of the existing route — so "A with a trivial client add", not B.
Demo surface: add `OATHS` tab to `ui/right_panel.py:58-74` enum + an `OathsPanelWidget` modelled on `ui/quest_panel.py:28` (list of active pledges from `get_pledges_for_npc`, with type/severity/sworn-tick). Add a `pledge_poller.py` modelled on `npc_goals_poller.py` (thread+Lock+`get_state` snapshot, swallow-and-retain per `game_end_poller.py:36-127`). Player verb: a "Swear oath" action in `ui/actions_panel.py:56` → `post_pledge`; a "Break oath" action → new `break_pledge`. On break, relation ticker (`ui/relation_ticker.py:54`) reflects the penalty.
Content/seed: none required for the verb. Optional: seed 1 pre-existing pledge (e.g. `lira_fence` →`mira_innkeeper` `protect`) so the panel is non-empty on first open — one edge in `seed.py`.
Win/lose hook: feeds D3 — a kept vs broken oath can gate a faction-standing bonus/penalty (e.g. breaking a `fealty` to `city_guard` docks `city_guard` standing). D1 only names the hook; D3 wires it into `game_end_checker.py`.
Prerequisite enablers: `EngineClient.break_pledge` (trivial). none else.
Effort: **S**   Player-value: **high**   Demo-fit: **high**
Risks / unknowns: pledge violation detection is tick-driven (`check_pledge_violations`) — in a paused Free-Play window the break must be explicit (player verb), which is the design here, so no LLM-in-loop latency. Confirm `break_pledge` route returns the relationship delta for the ticker (else poller re-reads relationship).
First slice: `OATHS` tab + `pledge_poller` showing existing pledges via `get_pledges_for_npc` (pure-A, zero engine work) — proves the engine is live before adding the swear/break verbs.
Open questions: should an oath sworn by the *player* (not an NPC↔NPC pledge) need a `player` Character node as pledger? → OPEN_QUESTIONS (player-as-pledger identity).

---

### DEMO-D1-02: Broker & Break Faction Treaties
Pillar: dormant-engine
Player fantasy: Negotiate a treaty between two rival factions (or break one) and watch the political map shift — alliances you broker hold the world together; treaties you sabotage tip it toward war.
Why it matters: Showcases moat §1a.4 (consequential, auditable world): a treaty is an inspectable graph artifact (`BOUND_BY` edges) with narrative terms + mechanical conditions the engine *checks every tick* (treaty_engine.py:54-58). Gives D3 a **second tensioned objective axis** (faction-peace vs faction-standing) beyond the single standing gate D0 §4 flags.
Current state: full route `treaties.py` (create `:71` / list `:96` / expire `:113` / break `:132`); `TreatyEngine.run_tick` enforces expiry+conditions (treaty_engine.py:50-58). **No `EngineClient` method** and 0 `demo_game/` refs — the one named engine with a route but no client (D0 §2.7).
Engine capability used: `treaties.py:71/96/132`; mechanical condition checks `check_treaty_conditions_mechanical` (treaty_engine.py:57).
Reachability: **B** — route exists, needs `EngineClient.create_treaty / get_faction_treaties / break_treaty` (mirror the `post_pledge` pattern, client.py:1226).
Demo surface: `TREATIES` tab in `ui/right_panel.py` + `TreatiesPanelWidget` modelled on `ui/politics_panel.py:51` (it already renders faction relations — extend with a treaties section). `treaty_poller.py` modelled on `npc_politics_poller.py`. Player verbs in `ui/actions_panel.py`: "Broker treaty" (pick 2 factions + terms) → `create_treaty`; "Break treaty" → `break_treaty`. POLITICS/CHAIN tabs already give the inspect surface for the resulting edges.
Content/seed: 1-2 seed treaties for a non-empty panel (e.g. `merchants_guild`↔`city_guard` trade pact) — `create_treaty` calls in `seed.py`. Optional `terms_narrative` strings (low content cost, no per-NPC voice authoring).
Win/lose hook: feeds D3 — "≥1 active treaty between the two factions you allied" as a second win sub-goal, OR "a broken treaty triggers a war event" as a failure path. D1 names; D3 wires.
Prerequisite enablers: `EngineClient` treaty methods (3 small wrappers).
Effort: **M** (client methods + panel + a multi-select "broker" dialog — the term-entry UI is the only non-trivial pygame bit)   Player-value: **med-high**   Demo-fit: **high**
Risks / unknowns: the "broker treaty" verb needs a small multi-faction + term-string input dialog (more than a one-click action) — model on the trade flow `ui/trade_panel.py:33`. `terms_conditions` (mechanical) authoring is optional; narrative-only treaties ship first.
First slice: `EngineClient.get_faction_treaties` + `TREATIES` tab read-only listing seed treaties (proves route reachable), before adding broker/break verbs.
Open questions: should treaty conditions be authored (mechanical, engine-checked) or narrative-only for the demo? → OPEN_QUESTIONS (treaty term depth).

---

### DEMO-D1-03: Investigation / "Solve the Crime" panel
Pillar: dormant-engine
Player fantasy: Step into an investigator role — pull evidence, witnesses and rumors about a crime event and let the graph *flag the contradictions* (this suspect's alibi doesn't match where the graph says they were; these two rumors disagree).
Why it matters: The single strongest demo-fit pick. `get_investigation_context` surfaces **alibi contradictions** (current location vs `WAS_AT` history) and **rumor contradictions** (`CONTRADICTS`-linked rumor pairs) — that IS moat §1a.2 (knowledge has provenance and degrades) turned into a player puzzle. It reuses the witnessed/rumor/secret graph the demo already shows in CHAIN/KNOWLEDGE tabs, now as *deduction*.
Current state: `InvestigationEngine.get_investigation_context` (investigation_engine.py:39) is stateless, query-only, LLM-narration-ready. **No route, no client method, 0 demo refs.** Depends on `witnessed.py`/`secrets.py`/`rumors.py` routes that DO exist (suggesting the underlying graph is seedable).
Engine capability used: `get_investigation_context` (investigation_engine.py:39-95) → evidence, witnesses, suspects, deductions, alibi_contradictions, rumor_contradictions.
Reachability: **B** — needs `api/routes/investigations.py` (`GET /investigations/{event_id}?investigator_id=`) + `EngineClient.get_investigation`. No schema change (reads existing Evidence/WITNESSED/SUSPECTS/Deduction/Rumor structures).
Demo surface: `INVESTIGATE` tab + `InvestigationPanelWidget` modelled on `ui/knowledge_sidebar.py:34` (it already renders provenance-colored knowledge) — render evidence/witnesses/suspects lists and **highlight contradictions in the degradation color** (`dialogue.degradation_color`, reused from gossip). Poller `investigation_poller.py` modelled on `npc_memory_poller.py`, keyed on a selected crime event. Player verb: "Investigate" action on a crime Event in the WORLD feed.
Content/seed: **med** — needs a crime event with Evidence + ≥2 witnesses whose `WAS_AT` history conflicts + ≥1 contradicting rumor pair, so the contradictions actually fire. The **tavern world's `tw_theft_at_market` event** (DEMO_INTENT §2.3) is a ready-made seed; promote/port it into the playable Munich world or add an analogous `demo_theft` event in `seed.py`.
Win/lose hook: feeds D2/D3 — "correctly accuse the suspect the contradictions implicate" as a quest objective (reuses quest lifecycle). none in D1 itself.
Prerequisite enablers: `api/routes/investigations.py` + `EngineClient.get_investigation`; a seeded crime event with conflicting alibis (content).
Effort: **M-L** (route is small; the *content* — a crime with deliberately conflicting graph state — is the real cost)   Player-value: **high**   Demo-fit: **high**
Risks / unknowns: contradictions only appear if the seed graph is authored to contradict (alibi history vs current location, CONTRADICTS rumor edges) — empty contradictions = a flat panel. LLM narration of deductions is optional (engine returns structured data; pygame can render it directly with no LLM-in-loop).
First slice: route + `INVESTIGATE` tab rendering the raw evidence/witness/suspect lists for one seeded crime — contradiction highlighting second.
Open questions: port `tw_theft_at_market` into Munich world or author a new demo crime? → OPEN_QUESTIONS / D2 content (crime-event sourcing).

---

### DEMO-D1-04: Chapter / Act banner (narrative arc HUD)
Pillar: dormant-engine
Player fantasy: The session reads like a story with named acts — a banner announces "Chapter II: The Broken Peace" as the world crosses narrative thresholds, giving the run shape and a sense of escalation.
Why it matters: Lower demo-fit (it's framing, not a moat verb) but high *game-feel*: D0 §4 says the loop has "no stakes, no shape." A chapter banner that the **engine derives from quest density + beat intensity** (chapter_engine.py:163-200) makes the world feel authored and progressing — and the LLM-labeled titles (chapter_engine.py:250) are a cheap, visible "the engine is narrating your world" beat.
Current state: `ChapterEngine.run_tick` (chapter_engine.py:112) opens/closes/labels `CHAPTER` nodes each tick. **No route, no client method, 0 demo refs.**
Engine capability used: `get_current_chapter` (chapter_engine.py:124) returns the open chapter {id, name, theme}.
Reachability: **B** — needs `GET /chapters/current` route + `EngineClient.get_current_chapter`. Read-only; no schema change.
Demo surface: not a tab — a **banner** modelled on `EventBanner` (`widgets.py:445`) rendered top-of-screen via `LeftPanelRenderer` (left_panel.py:44) or `game_window.py:73`. `chapter_poller.py` (low-frequency, e.g. interval_s=5) modelled on `world_state_poller.py`; on chapter-name change, flash the banner.
Content/seed: none (engine generates titles via LLM with rule-based fallback `chapter_labeler.py`).
Win/lose hook: none directly; a chapter transition is a natural place to fire a D3 escalation event.
Prerequisite enablers: `GET /chapters/current` route + client method.
Effort: **S-M**   Player-value: **med**   Demo-fit: **med**
Risks / unknowns: chapter transitions are tick-driven and quest-density-gated; in a short Free-Play session few transitions fire, so the banner may rarely change (mostly shows "Prologue"). Tuning `quest_threshold`/`window_ticks` for demo cadence is a content/config call. LLM labeling adds latency at transition only (off the dialogue path).
First slice: `GET /chapters/current` + a static banner showing the current chapter name (proves reachability); transition-flash animation second.
Open questions: tune transition thresholds for a 20-30 min session, or drive chapters off scripted scene beats instead of quest density? → OPEN_QUESTIONS (chapter cadence).

---

### DEMO-D1-05: Story-pacing "Tension Meter" HUD (read-only, type-A)
Pillar: dormant-engine
Player fantasy: A visible tension/escalation gauge that rises when major crises are active and the world "holds its breath" (suppressing new events) — making the engine's pacing logic legible.
Why it matters: Pure type-A (no new route) and showcases the *world is consequential* moat (§1a.4): `StoryPacingEngine` writes `max_event_severity` + `quest_generation_rate` onto `WorldState` (story_pacing_engine.py:79-85) when high-severity quests are active. Surfacing those two numbers proves the world self-regulates its drama — an "engine is alive" beat at near-zero cost.
Current state: engine writes to `WorldState` each tick (story_pacing_engine.py:64-99). `EngineClient.get_world_state` already reads `WorldState`. 0 demo refs, but **no enabler needed** — the fields ride on the existing world-state read.
Engine capability used: `WorldState.max_event_severity` / `quest_generation_rate` (set story_pacing_engine.py:79-85).
Reachability: **A** — `get_world_state` already returns the world node; confirm these two fields are serialized in the world-state response (if not, the only gap is including them — a field add, not a route).
Demo surface: extend `WorldPanelWidget` (`world_panel.py:83`) / WORLD tab with a "Tension" readout, or a small gauge in `LeftPanelRenderer`. Reuse the existing `world_state_poller.py` (no new poller) — just read the two extra fields it already fetches.
Content/seed: none.
Win/lose hook: none; informational. Pairs naturally with DEMO-D1-04 (chapter) as the "narrative HUD" cluster.
Prerequisite enablers: confirm `max_event_severity`/`quest_generation_rate` are in the world-state serialization (else a 1-field response add). none else.
Effort: **S**   Player-value: **low-med**   Demo-fit: **med**
Risks / unknowns: only moves when a high-severity quest is active — in a quiet session it sits flat (same caveat as chapter). Best paired with D3's escalation content so the meter visibly reacts. Verify world-state response includes the fields (D4 feasibility check).
First slice: read+display the two fields in the WORLD tab via the existing `world_state_poller` (zero new threads/routes).
Open questions: none blocking — confirm field serialization with D4.

---

### DEMO-D1-06: (deferred) Player-influenced battle → reachable LOSE state (military)
Pillar: dormant-engine
Player fantasy: Reinforce or undermine a faction's army before the Iron Legion assault, so the battle outcome — and whether the barracks falls — actually depends on what you did.
Why it matters: This is the keystone D0 §2.1/§4 names: the LOSE condition (`iron_legion` controlling `loc_guard_barracks`) is **structurally unreachable** because battle resolution is a scripted clock tick (`run.py:261-279`) the player can't influence. `MilitaryEngine.run_tick` already resolves battles by army strength and writes `CONTROLS` (military_engine.py:47) — giving the player a verb that changes army strength makes the dramatic failure real.
Current state: `MilitaryEngine.run_tick` (military_engine.py:27) resolves battles + writes `CONTROLS`; demo only *reads* `CONTROLS` for the lose check (game_end_poller.py:104-107). No player-facing route to alter army strength/allegiance.
Engine capability used: `resolve_battles` (military_engine.py:47) — strength comparison drives `CONTROLS` updates.
Reachability: **C** — needs a DECISIONS call: does the player get a *military verb* (reinforce/sabotage an army, or a bribe/quest that shifts army strength)? That's an economy/design decision, not a pure enabler. Route(s) to set Army strength or re-allegiance would follow.
Demo surface: (post-decision) a "Reinforce / Sabotage" action surfacing army strength, modelled on the bribe flow; the existing `game_end_poller` already renders the consequence (barracks control → lose). No new poller needed for the *outcome*; only for showing army strength pre-battle.
Content/seed: existing `iron_legion` army + barracks already seeded (seed.py per DEMO_INTENT §2.3).
Win/lose hook: **this is the hook** — makes `check_lose` (game_end_checker.py:106) player-reachable. Hand to **D3** as the primary lose-state lever.
Prerequisite enablers: DECISIONS entry on the military player-verb (schema: does an Army get a player-adjustable strength?); then a route to mutate army strength/allegiance.
Effort: **L-XL**   Player-value: **high**   Demo-fit: **med** (game-feel/stakes, not a graph-moat showcase)
Risks / unknowns: largest scope of the set; overlaps D3's economy redesign. Battle math + a player lever that isn't trivially "always reinforce" needs balancing. **Recommend D1 hands this to D3, not Phase-1 dormant-surfacing.**
First slice: read-only "Army Strength" readout next to the lose meter (proves the engine state is reachable) — the *verb* is D3's call.
Open questions: does the player get a direct military verb or only indirect influence (bribe a captain, complete a quest that reinforces)? → OPEN_QUESTIONS / D3 economy (lose-state lever design).

---

## Cross-references
- **D3 (`ECONOMY_DEPTH.md`)** — DEMO-D1-01 (oath break), D1-02 (treaty), D1-06 (military) all
  supply *lose/second-objective levers* D3 must wire into `game_end_checker.py`. D1-06 is handed
  to D3 as the primary mechanism to make the inert lose condition reachable.
- **D2 (`CONTENT_PLAN.md`)** — DEMO-D1-03 (investigation) needs an authored crime event with
  conflicting alibis/rumors; `tw_theft_at_market` (DEMO_INTENT §2.3) is a porting candidate.
- **D4 (`FEASIBILITY.md`)** — enabler list: `EngineClient.break_pledge` (D1-01), 3 treaty client
  methods (D1-02), `api/routes/investigations.py`+client (D1-03), `GET /chapters/current`+client
  (D1-04), world-state field-serialization check (D1-05). D1-06 is type-C (DECISIONS).
- **D5 (`DEMO_EXPANSION_ROADMAP.md`)** — Phase-1 = D1-01 (type-A, ship now) + D1-05 (type-A read).
  Phase-2 = D1-02, D1-03, D1-04 (one small route/client each). D1-06 routes to the D3 economy track.

---

## 6-line summary
- **Kept (6 dormant gameplay engines):** oath, treaty, investigation, military, chapter, story_pacing.
- **Dropped infra (7):** contracts (D0 trap), llm, idempotency, embedding_invalidation, base_engine, memory_consolidation, tts.
- **Dropped already-surfaced/low-fit (rest):** faction_politics, succession, clique, agenda, planning, routine, skill, reputation, events, mood, need, economy, gossip, quest, memory, dialogue, currency.
- **Confirmed D0 lead:** oath IS largely type-A — `post_pledge`+`get_pledges_for_npc` already reachable via the pledge surface; only `break_pledge` client wrapper is missing. treaty stays type-B (route, no client).
- **Top 3 surfacing opportunities:** (1) **DEMO-D1-01 oath** — type-A, high/high, ships now (relationships-as-state moat as a player verb); (2) **DEMO-D1-03 investigation** — best demo-fit, one route surfaces the knowledge-provenance moat as a "solve-the-crime" puzzle; (3) **DEMO-D1-02 treaty** — type-B second objective axis feeding D3's multi-objective win.
- **Keystone for D3:** DEMO-D1-06 (military) is the type-C lever that finally makes D0's inert LOSE condition player-reachable — handed to the economy lens, not Phase-1.
