# CONTENT_PLAN.md — Pillar 2: content, branching arcs, replayable scenarios

**Lens:** D2 (Content & scenarios). Scores against the rubric in `DEMO_INTENT.md` §3
(Player-value / Demo-fit / Reachability A/B/C / Effort S–XL / Dependency / Content-cost).
**Scope:** read-only design. All proposals build on the **existing** seed seam
(`demo_game/seed.py`, KE-6 stable-id, idempotent create calls through `EngineClient`) and the
existing scenario picker (`ui/start_menu.py` + `demo_game/scenarios/`). No parallel seeding path.

**Baseline (from `DEMO_INTENT.md` §2.3):** the playable Free-Play world is **5 NPCs · 3
locations · 4 factions (3 alliable) · ~6 quests · 0 player-facing branch points · 1 win · 1
(inert) lose**. Village/Tavern are **scripted-only reels**, not Free-Play playable worlds.

**Two load-bearing facts that shape every proposal below:**
1. **There is no in-game branch primitive.** `arc_choice.py` (`arc_choice.py:14-24`) is a 4-value
   menu enum that picks a *subprocess arc* — it is arc *selection*, not choice→consequence
   branching. "Branching arcs" is **build-from-scratch** (DEMO-D2-06), not extend-existing.
2. **`PART_OF` location hierarchy already works.** `client.post_part_of` (`client.py:776-803`)
   is live and already used by `_seed_location_hierarchy` (`seed.py:424-453`). Nested places are
   **reachability A**, not blocked.

D1 (`DORMANT_ENGINES.md`) runs in parallel; this lens references treaty/oath/story_pacing/chapter
capabilities *generically* and marks any content that needs a D1 enabler as a prerequisite.

---

## 0. Target-volume table

| Content type | Current | Target | Delta | Lands via |
|--------------|---------|--------|-------|-----------|
| NPCs (playable world) | 5 | **11** | +6 | `seed.py` `_NPCS` + `_NPC_INNER_LIFE` (DEMO-D2-01) |
| Locations | 3 | **7** | +4 | `seed.py` `_LOCATIONS` + `PART_OF` (DEMO-D2-02) |
| Location hierarchy depth | 1 city / 3 venues | 1 city / 2 districts / 6 venues | +1 tier | `post_part_of` (DEMO-D2-02) |
| Factions (alliable) | 3 (+1 inert) | **5** (+1) | +2 | `seed.py` `_FACTIONS` (DEMO-D2-03) |
| Quests (authored) | ~6 | **18** | +12 | `post_quest_offer` + `_CHAIN_QUESTS` pattern (DEMO-D2-04) |
| Quest chains (UNLOCKS) | 2 | **6** | +4 | `_QUEST_UNLOCKS_CHAINS` (DEMO-D2-04, D2-05) |
| Player-facing branch points | 0 | **≥12** | +12 | new `branch_node.py` primitive (DEMO-D2-06) |
| Replayable Free-Play worlds | 1 (Munich) | **3** (Munich, Village, Tavern) | +2 | promote eval worlds (DEMO-D2-08) |
| Authored campaign chapters | 0 | **3–4** | +3 | chapter-paced beats (DEMO-D2-10, needs D1) |
| Treaty/oath content hooks | 0 | **3** | +3 | treaty quest + oath arc (DEMO-D2-09, D2-11; need D1) |

**Reachability summary:** D2-01/02/03/04/05/07/08 are **type-(A) pure-demo** (every `EngineClient`
method exists today). D2-06 (branch primitive) is type-(A) on the demo side but is the **keystone
content enabler** every branching arc depends on. D2-09/10/11 are **type-(B)** — blocked on D1's
treaty/oath/chapter route+client enablers.

---

## 1. NPCs / locations / factions / quests (build on `seed.py`)

### DEMO-D2-01: Expand the cast 5 → 11 NPCs
Pillar: content
Player fantasy: The city feels populated — every district has its own voices, rivalries, and
people who *remember* you, not just five faces on a loop.
Why it matters: Game-feel — `DEMO_INTENT.md` §1b "a motivated player exhausts the surface in ~10
minutes." Sales — more nodes make the gossip-provenance moat (§1a claim 2) visibly *travel* across
a denser graph, and give relationship-as-state (claim 3) more surfaces to color.
Current state: `_NPCS` is 5 tuples (`seed.py:478-500`); `_NPC_INNER_LIFE` keyed by npc_id
(`seed.py:510-583`); inner life seeded by `_seed_npc_inner_life` (`seed.py:379-421`).
Engine capability used: generic node upsert + typed belief/goal/memory/secret endpoints —
`client.upsert_node` (`client.py:457`), `post_belief/goal/memory/secret` (`client.py:550/590/633/739`).
Reachability: **A** — `build_npc_payload` (`seed.py:109`) + `_seed_npc_inner_life` already do this;
adding rows to `_NPCS` and keys to `_NPC_INNER_LIFE` is the entire change.
Demo surface: zero UI change — `NpcListWidget` (`widgets.py:297`) and the per-NPC pollers already
render whatever NPCs exist. New NPCs appear in the list and are addressable in dialogue immediately.
Content/seed: +6 NPCs, each with voice_descriptor, 2 beliefs, 1 goal, 2 memories, 1 secret, needs,
and a faction. Proposed cast (stable ids):
 - `bren_smith` (blacksmith, city_guard-aligned, new `loc_forge`) — supplies the guard; resents tithes.
 - `nessa_priestess` (priestess, neutral, new `loc_temple`) — the moral counterweight; hears confessions (secrets).
 - `dorn_dockmaster` (dockmaster, merchants_guild, new `loc_docks`) — controls smuggling chokepoint; Lira's contact.
 - `vex_spymaster` (spymaster, new `crown_loyalists` faction) — the treaty/oath broker (feeds D2-09/11).
 - `tilda_herbalist` (herbalist, thieves_guild-adjacent, `loc_market_square`) — poison & cure; quest-giver.
 - `garrick_deserter` (deserter, iron_legion defector, `loc_tavern`) — the war made personal; Mira's hidden cellar guest (ties to her secret `seed.py:524`).
Win/lose hook: none directly; supplies actors for D2-04 quests and D3 multi-objective economy.
Prerequisite enablers: DEMO-D2-02 (the 3 new locations) must seed first so LOCATED_AT resolves.
Effort: M   Player-value: high   Demo-fit: med
Risks / unknowns: **content authoring cost is the real cost** — 6 voice_descriptors + 36 inner-life
items, hand-written to match the existing voice quality (`seed.py:480-499`). Pushes `seed.py` further
past its 300-line waiver (DEC noted); if it crosses a threshold, split NPC data into
`seed_npc_data.py` imported back (note in DECISIONS, mirrors the existing 300-line justification at
`seed.py:10-13`).
First slice: add `bren_smith` + `loc_forge` only — proves the 6→7 path end-to-end with one reseed.
Open questions: cast size ceiling vs LLM cache warming cost → OPEN_QUESTIONS (campaign length call).

---

### DEMO-D2-02: Locations 3 → 7 with a 2-tier district hierarchy
Pillar: content
Player fantasy: The city has *places* — a temple district, a dockside, a forge row — and travel
between them means something, not three rooms on a tab.
Why it matters: Game-feel (more space to explore) + sales: nested `PART_OF` proves the world is
**structured and auditable** (§1a claim 4) — gossip and reputation can be scoped to a district.
Current state: `_LOCATIONS` is 3 tuples (`seed.py:460-464`); `_seed_location_hierarchy` already
wires `loc_city` + 3 PART_OF children (`seed.py:424-453`).
Engine capability used: `client.post_part_of` (`client.py:776-803`) → `location_graph` route
(`api/routes/location_graph.py`); `build_location_payload` (`seed.py:52`).
Reachability: **A** — PART_OF is proven in-repo (`seed.py:450`). The enabler `DEMO_INTENT.md` §"note
any content blocked by an enabler" flags is **already satisfied**: nested places work today.
Demo surface: locations show in `WorldPanelWidget`/INSPECT (`world_panel.py:83`, `inspect_panel.py:37`)
and as travel targets in `GameController` travel verb (`game_controller.py:163-272`). No new panel.
Content/seed: +4 venues (`loc_forge`, `loc_temple`, `loc_docks`, `loc_north_gate`), +2 districts
(`loc_old_quarter`, `loc_harbor_district`); rewire `_seed_location_hierarchy` so venues PART_OF a
district and districts PART_OF `loc_city` (hierarchy_level 0=venue,1=district,2=city per
`client.py:789`).
Win/lose hook: `loc_north_gate` becomes a second strategically-controllable location for D3 (gives
the inert lose condition at `loc_guard_barracks` a sibling so capture is a real map).
Prerequisite enablers: none.
Effort: S   Player-value: med   Demo-fit: med
Risks / unknowns: travel UX in pygame must list >3 destinations without clutter — `ActionsPanelWidget`
(`actions_panel.py:56`) already scrolls, so low risk.
First slice: add `loc_temple` under a `loc_old_quarter` district — proves the 2-tier nest with one call.
Open questions: none.

---

### DEMO-D2-03: Factions 3 → 5 (add `crown_loyalists`, `dockside_smugglers`)
Pillar: content
Player fantasy: The political board is wider than guild/guard/thieves — there's a crown faction
that can broker peace and a smuggler ring that profits from the war.
Why it matters: D3's "gains with one faction cost another" tension needs ≥4 alliable factions to be
interesting; this also gives D1's treaty engine two *new* parties to broker between (sales claim 4).
Current state: `_FACTIONS` 3 tuples (`seed.py:466-470`), `_FACTION_STANDS_WITH` antagonism edges
(`seed.py:473-476`), `_MILITARY_FACTIONS` adds inert `iron_legion` (`seed.py:631-633`).
Engine capability used: `build_faction_payload` (`seed.py:80`) + `upsert_edge("STANDS_WITH")`
(`client.py:478`); `factions` route (`api/routes/factions.py`).
Reachability: **A**.
Demo surface: `PoliticsPanelWidget` (`politics_panel.py:51`) already renders factions/standings; new
factions appear automatically. Reputation shows via `get_npc_reputation` (`client.py:199`).
Content/seed: +2 factions; STANDS_WITH web: `crown_loyalists` opposes `iron_legion` (-90), neutral-ish
to guard (+30); `dockside_smugglers` allies `thieves_guild` (+50), opposes `city_guard` (-70).
Win/lose hook: extends `DEMO_FACTIONS` (`game_end_checker.py:21`) candidate set for D3 multi-faction
win; antagonism edges are the substrate for D3 tension (helping smugglers hurts guard standing).
Prerequisite enablers: none. D3 (`ECONOMY_DEPTH.md`) consumes these in its tension model.
Effort: S   Player-value: med   Demo-fit: med
Risks / unknowns: D3 must decide which factions count toward the win or the politics gets diffuse.
First slice: add `crown_loyalists` only (it is the treaty/oath broker faction for D2-09/11).
Open questions: none.

---

### DEMO-D2-04: Quests ~6 → 18 via the deterministic offer seam
Pillar: content
Player fantasy: Every NPC has something they want — fetch, deliver, investigate, broker, betray —
and finishing one opens the next, so the session has a spine.
Why it matters: Game-feel — quests are the demo's "objective" surface and today there's effectively
one (`DEMO_INTENT.md` §2.1). Sales — graph-verified `deliver`/`investigate` objectives prove the
world is **consequential and auditable** (claim 4) far better than a chat transcript.
Current state: `_seed_quests` offers the one deterministic Aldric quest (`seed.py:848-908`);
`_CHAIN_QUESTS`/`_SOURCE_CHAIN_QUESTS` show the multi-quest seed pattern (`seed.py:921-960`); full
lifecycle on the client — `post_quest_offer/accept/objective/evaluate/reward` (`client.py:963-1096`).
Engine capability used: quest lifecycle + chain `UNLOCKS` — `quest` route (`api/routes/quest.py`),
`quest_generation` route; objective types `deliver`/`investigate` (`seed.py:876-881`).
Reachability: **A** — the offer/objective/evaluate/reward path is fully wired and seed-proven.
Demo surface: `QuestPanelWidget` (`quest_panel.py:28`) + ACTIONS tab already accept/track quests via
`GameController` (`game_controller.py:163-272`). Zero new UI; just more quest nodes + HAS_QUEST edges.
Content/seed: +12 authored quests, 2 per NPC across the expanded cast, each with a typed objective
(`deliver`/`investigate`/`talk-to`) and a currency or item reward. Group into 6 chains via new
`_QUEST_UNLOCKS_CHAINS` entries (mirror `seed.py:914-917`). Example chain (smuggler arc):
`dorn_smuggle_run` → `lira_fence_handoff` → `sorn_intercept_choice` (this last one is a **branch
node**, see D2-06).
Win/lose hook: completing a full chain becomes a D3 *alternate win path* ("quest-chain victory") so
the player isn't funnelled into the faction-standing scalar (`game_end_checker.py:86-103`).
Prerequisite enablers: DEMO-D2-01 (NPCs to give the quests). D3 consumes the chain-completion win.
Effort: L   Player-value: high   Demo-fit: high
Risks / unknowns: **content cost is high** — 12 quests × (title, objective, reward, voice for the
offer). Objective verification beyond `deliver` may need an objective_type the engine doesn't graph-
verify (e.g. "persuade") → those degrade to talk-to-NPC checks. Confirm objective_type vocabulary
with D1/engine before authoring `investigate`-heavy quests.
First slice: one new 2-quest chain for `bren_smith` (deliver ore → guard report) — proves the
authored-chain path without the full 12.
Open questions: which objective_types the engine graph-verifies → OPEN_QUESTIONS.

---

### DEMO-D2-05: Faction-rival quest variants (same target, opposed givers)
Pillar: content
Player fantasy: Two factions want the same thing for opposite reasons — and you can only satisfy one.
Why it matters: Cheap, high-leverage *consequence*: it makes quests **mutually exclusive**, which is
the seed of branching without yet building the branch primitive. Directly feeds D3 faction tension.
Current state: quests are independent today; no opposed-giver pairing exists. STANDS_WITH antagonism
(`seed.py:473-476`) is the data that justifies the opposition.
Engine capability used: `post_quest_offer` (`client.py:963`) + reputation adjust
(`adjust_npc_reputation` `client.py:1386`) so completing for one giver moves standing on both.
Reachability: **A**.
Demo surface: QUESTS + POLITICS tabs; accepting quest A from giver X visibly drops standing with
giver Y's faction (already rendered by `PoliticsPanelWidget` + `RelationTicker` `relation_ticker.py:54`).
Content/seed: 2 opposed-giver quest pairs, e.g. `sorn_seize_contraband` (city_guard, +guard/-thieves)
vs `lira_move_contraband` (thieves_guild, +thieves/-guard), both targeting the same `contraband_crate`
item node. Player can hold only one.
Win/lose hook: the standing swing on completion is exactly the D3 tension delta — name the
reputation-adjust call so D3 wires it to `game_end_checker`.
Prerequisite enablers: DEMO-D2-04 (the quest seam) + DEMO-D2-03 (enough factions to oppose).
Effort: M   Player-value: high   Demo-fit: high
Risks / unknowns: needs the demo loop to *prevent* holding both — that's a `GameController` accept-
guard, a small loop change, not a UI build. Confirm accept guard is feasible (likely an ISSUE for D4).
First slice: the single contraband pair above.
Open questions: none.

---

## 2. Branching arcs (build the missing branch primitive)

### DEMO-D2-06: A real in-game branch primitive (`branch_node.py` + `BranchState`)  ⭐ keystone
Pillar: content
Player fantasy: I made a choice — spare the deserter or turn him in — and the *story and the world
state forked* because of it. Replaying, I pick the other path and a different ending unfolds.
Why it matters: This is **the single biggest content gap** (`DEMO_INTENT.md` §2.6, §4): "branching
authored content that those objectives drive." Without a branch primitive, every D2 arc and every
D3 alternate ending is unreachable. It is the keystone every other branching proposal depends on.
Current state: **nothing.** `arc_choice.py:14-24` is a menu enum, not a choice→consequence node.
Scenarios are linear `Scene` lists (`run_tavern_intrigue.py:177-276`) with no fork construct.
Engine capability used: **none new** — a branch resolves by reading/writing graph state the client
already exposes: set a belief/goal (`post_belief`/`post_goal` `client.py:550/590`), fire a reputation
delta (`adjust_npc_reputation` `client.py:1386`), or flip world_state (`put_world_state` `client.py:809`).
The branch primitive is **pure demo-side orchestration** over existing methods.
Reachability: **A** (demo-side build; no engine route needed). It is type-A but high-effort because
it's a *new construct*, not a parameter.
Demo surface: new demo modules (all `demo_game/`, zero `src/` imports):
 - `branch_node.py` — a `BranchNode` dataclass: `prompt_text`, `options: list[BranchOption]`, each
   option carrying `label` + a list of *effects* (typed: `SetBeliefEffect`, `RepDeltaEffect`,
   `WorldStateEffect`, `OfferQuestEffect`, `GotoBeatEffect`). Pure data + an `apply(client)` method.
 - `branch_state.py` — `BranchState`: immutable record of choices taken (for ending selection +
   replay diffing), persisted to `.cache/demo/branch_state.json` (mirror the quest cache
   `seed.py:864`).
 - `ui/branch_panel.py` — a modal choice widget modeled on `ActionsPanelWidget` (`actions_panel.py:56`):
   renders the prompt + numbered options, returns the chosen index (reuse `start_menu.py:111-144`
   keyboard-handling pattern).
Content/seed: branch nodes are authored content, not seed nodes — they live in scenario beat lists
(D2-07) and reference seed ids (e.g. `garrick_deserter` from D2-01). Each option's effects call only
existing `EngineClient` methods.
Win/lose hook: a `BranchOption` effect can set a flag that `game_end_checker` reads (D3 wires a new
ending-selection check, mirroring `detect_first_allied_faction` `game_end_checker.py:63-83`).
Prerequisite enablers: none (it is itself the enabler for D2-07/09/11 and D3 multi-ending).
Effort: L   Player-value: high   Demo-fit: med (game-feel; the *moat* is shown when effects mutate the
graph and an NPC later remembers the choice — pair with memory consolidation `client.py:707`).
Risks / unknowns: pygame modal input handling (blocking the main loop cleanly) — manageable, the
start-menu already does blocking modal input. Effect-replay determinism: `BranchState` must be the
sole source of truth so `--cached` playback is reproducible.
First slice: a single 2-option branch (spare/turn-in `garrick_deserter`) with one `RepDeltaEffect`
each, rendered in `branch_panel.py`, choice logged to `BranchState`. Proves the fork end-to-end.
Open questions: persist branch state per-save vs per-session → OPEN_QUESTIONS.

---

### DEMO-D2-07: Branching authored scenario beats (extend the Scene list with `BranchBeat`)
Pillar: content
Player fantasy: The scripted arcs aren't reels anymore — at key moments they *ask me*, and the rest
of the arc bends to my answer.
Why it matters: Converts the three linear "demo reels" (`DEMO_INTENT.md` §2.2) into replayable
*gameplay*. Sales: a buyer watching the same arc branch on the same engine is a stronger pitch than a
fixed tour.
Current state: `Scene`/`NarratorCue`/`DialogueBeat`/`EventFire`/`ClockTick` are linear, no fork
(`run_tavern_intrigue.py:79-170`); runner executes a flat list (`run_tavern_intrigue.py:296-306`).
Engine capability used: same as D2-06 (effects over existing client methods).
Reachability: **A** (depends on D2-06's primitive).
Demo surface: add a `BranchBeat(Scene)` whose `execute` shows `branch_panel.py`, applies the chosen
option's effects, and sets a `goto` label the runner honors (the runner's flat loop becomes a small
label-jump loop — a contained `run_*` change, not an engine change).
Content/seed: insert 3–4 `BranchBeat`s into each scripted arc (Munich/Village/Tavern). Tavern example:
after the theft (`run_tavern_intrigue.py:218-229`), branch "warn the merchant" vs "stay silent" → forks
which NPC trusts you next beat.
Win/lose hook: none directly (scripted arcs); the Free-Play branches (D2-06) carry the win hook.
Prerequisite enablers: **DEMO-D2-06** (branch primitive).
Effort: M   Player-value: high   Demo-fit: high
Risks / unknowns: `--cached` recording must cover *all* branches or playback misses; cache-warming
cost scales with branch count (author 2× the dialogue beats per fork).
First slice: one `BranchBeat` in the tavern arc with two outcomes, both cached.
Open questions: none.

---

## 3. Replayable scenarios (via the picker + menu)

### DEMO-D2-08: Promote Village & Tavern to playable Free-Play worlds
Pillar: content
Player fantasy: I can pick a whole different world to actually *play* — not just watch — with its own
NPCs, quests, and win condition.
Why it matters: `DEMO_INTENT.md` §2.3 flags Village/Tavern as **scripted-only reels with no quests,
no win economy**. Promoting them triples replayable worlds (1→3) — the cheapest large replayability win.
Current state: `seed_village_world.py` / `seed_tavern_world.py` seed NPCs/events but **0 quests** and
no win wiring (`DEMO_INTENT.md` §2.3); Free-Play assumes the Munich seed. The picker already lists all
three (`start_menu.py:37-42`) but routes Village/Tavern to *scripted* subprocesses.
Engine capability used: same quest/reputation seam as D2-04 (`client.py:963`+); win check reads
`get_npc_reputation` (`client.py:199`) exactly as `game_end_poller.py`.
Reachability: **A** — all methods exist; the work is authoring quests + a win config per world.
Demo surface: add a Free-Play sub-option per world in the picker (the menu pattern is `_MENU_OPTIONS`
`start_menu.py:37-42`); Free-Play loop is world-agnostic once the world is seeded with quests + a
win-faction set. The 14-tab panel framework (`right_panel.py:58-74`) needs no per-world change.
Content/seed: add a `_QUESTS` block + win-faction constants to each eval world seeder (e.g.
`vw_defend_village` chain for Village; `tw_recover_purse` chain for Tavern), mirroring `seed.py`'s
quest section. Keep `vw_`/`tw_` prefixes (no id collision with Munich).
Win/lose hook: each world gets its own win-faction set + threshold (D3 generalizes
`game_end_checker.DEMO_FACTIONS` `game_end_checker.py:21` to a per-world config so the checker isn't
Munich-hardcoded).
Prerequisite enablers: DEMO-D2-04 (quest authoring pattern); D3 must de-hardcode `game_end_checker`
faction/location constants to be world-parameterized.
Effort: L   Player-value: high   Demo-fit: med
Risks / unknowns: `game_end_checker` constants are Munich-specific (`game_end_checker.py:17-28`);
parameterizing them is a D3/D4 dependency, not pure content. Village has no factions today
(`DEMO_INTENT.md` §2.3) — needs faction seed first.
First slice: promote **Tavern** only (it already has 2 factions `seed_tavern_world.py:235-238`) — add
one quest chain + a `tw_merchants` win threshold.
Open questions: do the three worlds share a player save or reset per world → OPEN_QUESTIONS.

---

### DEMO-D2-09: Treaty-broker quest (exercises D1 treaty engine)
Pillar: content
Player fantasy: I shuttle between two warring factions, trade leverage and promises, and broker a
*treaty* that visibly changes the map — or watch it collapse if I overreach.
Why it matters: Surfaces the dormant **treaty** engine as *content a player drives* (orchestration
prompt Pillar 1×2). Sales: a brokered, graph-recorded treaty between factions is a flagship
"consequential, auditable world" proof (claim 4) no LLM-bolt-on can fake.
Current state: no treaty content; `treaties.py` route **exists** but **no `EngineClient` method calls
it** (`DEMO_INTENT.md` §2.7) — so treaty is type-(B) until a client method lands.
Engine capability used: treaty engine via `api/routes/treaties.py` (D1 names the exact surface);
quest scaffolding from D2-04; leverage already seeded (`_LEVERAGE_NODES` `seed.py:605-618`).
Reachability: **B** — needs `EngineClient.broker_treaty`/`get_treaties` (D1/D4 enabler) wrapping the
existing `treaties.py` route. The *quest content* around it is type-A; the treaty call is the blocker.
Demo surface: a treaty step inside a quest chain; a `ui/treaty_panel.py` (D1 designs it) shows
brokered/proposed/collapsed state. Branch node (D2-06) gates "propose vs walk away."
Content/seed: a 3-quest "Fragile Peace" chain given by `vex_spymaster`/`crown_loyalists` (D2-01/03):
gather leverage → propose terms (branch) → ratify or collapse. References existing `_LEVERAGE_NODES`.
Win/lose hook: a ratified treaty is a D3 **alternate win** ("diplomat victory"); a collapsed treaty
is a D3 **failure state** (war escalates) — the first player-reachable lose path
(`game_end_checker.py:106-117` is inert today).
Prerequisite enablers: **D1 treaty route+client enabler**; DEMO-D2-04, DEMO-D2-06 (branch).
Effort: L   Player-value: high   Demo-fit: high
Risks / unknowns: treaty engine's actual public surface (D1 confirms); without the client method this
is blocked. Content cost: a 3-quest chain + branch + two endings of dialogue.
First slice: once the treaty client method exists, a single "propose treaty" branch that flips
world_state epoch (`put_world_state` `client.py:809`) as a visible consequence.
Open questions: is treaty a 2-party or N-party engine (shapes the quest) → OPEN_QUESTIONS / D1.

---

### DEMO-D2-10: Chapter-paced campaign banner (exercises D1 chapter / story_pacing)
Pillar: content
Player fantasy: The session has *acts* — "Chapter II: The Gathering Storm" — and the world escalates
as I progress, so it feels authored, not aimless.
Why it matters: A chapter/act banner gives the loop **shape and pacing** (`DEMO_INTENT.md` §1b
"enough content to sustain a session") and frames replays as "reach Chapter III a different way."
Sales: shows `story_pacing`/`chapter` as a real director, not flavour.
Current state: no chapter concept in the demo; `chapter`/`story_pacing` engines have **no route at
all** (`DEMO_INTENT.md` §2.7) — type-(B), fully blocked until D1 names the enabler.
Engine capability used: chapter/story_pacing engine (D1 designs the route + client method).
Reachability: **B** — needs `api/routes/chapter.py` (or `story_pacing.py`) + `EngineClient.get_chapter`.
Demo surface: a thin top-of-window `ChapterBanner` widget (model on `EventBanner` `widgets.py:445`)
fed by a `chapter_poller.py` (mirror `game_end_poller.py:36-127` thread/lock/snapshot pattern).
Content/seed: 3–4 named chapters with entry conditions (e.g. Chapter II unlocks when ≥1 quest chain
completes). Chapters are config/content, not seed nodes, unless the engine stores them graph-side
(D1 decides).
Win/lose hook: reaching the final chapter can be a D3 *progression win*; failing to advance before a
tick deadline is a D3 *time-pressure failure*.
Prerequisite enablers: **D1 chapter/story_pacing route+client enabler** (a keystone per D4).
Effort: M (demo side, once the route exists)   Player-value: med   Demo-fit: med
Risks / unknowns: whether chapters are engine-authored or demo-authored (D1 call). If demo-authored,
this collapses to a pure-A content piece keyed off quest-chain completion counts.
First slice: a static 3-chapter banner driven by quest-chain completion count (pure-A fallback) while
the engine route is pending — upgrade to engine-driven when D1 lands the route.
Open questions: engine-driven vs demo-authored chapters → OPEN_QUESTIONS / D1.

---

### DEMO-D2-11: Oath-driven betrayal arc (exercises D1 oath / pledge)
Pillar: content
Player fantasy: I swear an oath to a faction — and later I'm tempted to break it. Breaking it has
teeth: NPCs who witnessed the pledge turn on me and *remember* the betrayal.
Why it matters: The most dramatic showcase of relationships-and-memory-as-state (§1a claims 1+3): an
oath sworn, recorded, then broken, with persistent fallout. High replay value (keep vs break).
Current state: no oath content; **`pledges.py` route exists** and `post_pledge`/`get_pledges_for_npc`
are **already on the client** (`client.py:1226/1257`) and seeded (`_PLEDGE_SEED` `seed.py:661-664`).
`DEMO_INTENT.md` §2.7 flags oath may be *partly reachable via the pledge surface* — confirm with D1.
Engine capability used: pledge surface (`client.py:1226`) for swear; oath engine (D1) for break-
consequence if pledge alone doesn't model breaking. Memory consolidation (`client.py:707`) records
the betrayal so NPCs recall it.
Reachability: **B if** breaking needs a dedicated oath route; **A if** the pledge surface +
reputation/memory deltas are sufficient (D1 confirms). Swearing is **A today** (`post_pledge` exists).
Demo surface: a "swear oath" action (`ActionsPanelWidget` `actions_panel.py:56`) + a branch node
(D2-06) later that offers "honor vs break"; broken-oath fallout via `adjust_npc_reputation`
(`client.py:1386`) + a seeded betrayal memory. Pledges already viewable (`get_pledges_for_npc`).
Content/seed: an oath the player can swear to `crown_loyalists` (D2-03) via `vex_spymaster`; a later
branch (D2-06) to break it for the smugglers; on break, rep deltas + a memory on each witness NPC.
Win/lose hook: honoring → faction-loyalty win contribution; breaking → a distinct D3 failure if it
collapses a treaty (D2-09) — two endings from one choice.
Prerequisite enablers: DEMO-D2-06 (branch), DEMO-D2-03 (`crown_loyalists`); **D1 confirmation** that
oath-break is reachable via pledge surface or names the oath route enabler.
Effort: M   Player-value: high   Demo-fit: high
Risks / unknowns: whether "break pledge" is modeled by the pledge route or needs an oath route — the
one open reachability question D1 must answer; until then, swearing ships (A) and breaking is blocked.
First slice: swear-only (pure-A via `post_pledge`), shown in a pledges view; add break-branch when D1
confirms the break path.
Open questions: does breaking a pledge have engine consequence or is it demo-modeled → OPEN_QUESTIONS / D1.

---

## 4. Cross-references
- **D0 (`DEMO_INTENT.md`)** — baseline counts (§2.3), rubric (§3), the "no branch primitive" verdict
  (§2.6, §4), reachability boundary (§2.7). This plan grows §2.3 and *builds* the §2.6 branch seam.
- **D1 (`DORMANT_ENGINES.md`)** — DEMO-D2-09/10/11 depend on D1's treaty/chapter/oath route+client
  enablers; this plan supplies the *content* those engines drive (treaty quest, chapter banner,
  oath arc). D1 confirms whether oath is reachable via the existing pledge surface (`client.py:1226`).
- **D3 (`ECONOMY_DEPTH.md`)** — D2-04 chain-completion, D2-05/03 faction tension, D2-09 treaty
  win/collapse, D2-11 oath honor/break, and D2-08 per-world win all feed D3's multi-objective win +
  distinct failure states; D3 must parameterize `game_end_checker` constants (`game_end_checker.py:17-28`).
- **D4 (`FEASIBILITY.md`)** — DEMO-D2-06 (branch primitive) is the content keystone; D2-09/10/11 are
  type-(B) blocked on D1 engine routes; everything else is type-(A) pure-demo. D4 confirms the
  `seed.py` 300-line split (D2-01) and the accept-guard loop change (D2-05).

---

## 5. Six-line summary
1. **Target counts:** 5→11 NPCs, 3→7 locations (+1 district tier), 3→5 alliable factions, ~6→18 quests
   in 6 chains, 0→≥12 player-facing branch points, 1→3 replayable Free-Play worlds, +3 chapters.
2. **Pure-demo (A) wins ship now:** D2-01 cast, D2-02 nested locations (PART_OF already works),
   D2-03 factions, D2-04/05 quests + rival variants — all use existing `EngineClient` methods + the
   idempotent KE-6 seed seam, zero new routes.
3. **Branching approach:** build a real in-game branch primitive (DEMO-D2-06: `branch_node.py` +
   `BranchState` + `ui/branch_panel.py`) that resolves player choices into *typed effects*
   (belief/rep/world-state/quest) over existing client methods — `arc_choice.py` is only a menu enum
   and cannot branch.
4. **Replayability mechanism:** `BranchBeat` forks the scripted Scene lists (D2-07), and the picker
   promotes Village/Tavern from scripted reels to playable Free-Play worlds with their own quests +
   win conditions (D2-08), so each replay yields a different outcome via a persisted `BranchState`.
5. **Exercising dormant engines:** a treaty-broker quest chain (D2-09), a chapter-paced campaign
   banner (D2-10), and an oath honor/break arc (D2-11) put treaty/chapter/oath/story_pacing in the
   player's hands — these are type-(B), blocked on D1's route+client enablers.
6. **Biggest dependency:** DEMO-D2-06 (branch primitive) is the keystone every branching arc and
   multi-ending depends on; the only blockers are D1's three engine routes and D3 de-hardcoding
   `game_end_checker` for per-world wins.
