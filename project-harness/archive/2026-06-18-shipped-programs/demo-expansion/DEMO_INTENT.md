# DEMO_INTENT.md — what the demo must prove + baseline inventory

**Lens:** D0 (Demo intent & baseline). Runs FIRST. D1 (dormant engines), D2 (content),
D3 (economy), D4 (feasibility) and D5 (roadmap) all score their proposals against the
rubric in §3 and the verdict in §4.
**Scope:** read-only analysis of `demo_game/` (pygame-ce client, zero `src/npc_engine`
imports) + the seed worlds. All claims cite `file:line`.

---

## 1. What the demo must prove

The demo is the **only** artifact a studio sees before they believe the engine. It has to
land two audiences at once, and today it serves the first far better than the second.

### 1a. As a sales artifact (a studio's first impression of the middleware)

The product is "NPCs with persistent memory, relationships, and emotional state via a
knowledge graph + LLM dialogue, licensable as middleware." The demo must, in one
unassisted session, make a technical buyer believe **four moat claims** that ordinary
LLM-NPC bolt-ons cannot make:

1. **Persistent, queryable memory** — an NPC recalls a *prior* interaction across sessions,
   not just within a context window. *(Surfaced: `remembers_you_beat.py`; ACT 10 of
   `run.py:445-447`; `MemoryPanelWidget` `ui/memory_panel.py:54`.)*
2. **Knowledge has provenance and degrades** — the same event reaches three NPCs at three
   distances and comes out as witness / rumour / garbled hearsay, and the graph *proves*
   the distortion path. *(Surfaced: gossip chain `run.py:116-170`, `ui/gossip_chain.py:32`,
   `ui/knowledge_sidebar.py:34`; degradation colour `dialogue.degradation_color`.)*
3. **Relationships and emotion are state, not flavour** — trust/affection deltas persist and
   re-color later dialogue; emotion shifts in response to world events.
   *(Surfaced: `_apply_relation_band` `game_controller.py:517`, `ui/relation_ticker.py:54`,
   `ui/emotion_panel.py:46`, `emotion_poller.py`.)*
4. **The world is consequential and auditable** — events propagate on a clock, reputation
   travels NPC-to-NPC ("she never met you but she heard"), rumours can be planted and
   *locally* corrected, and runs are deterministic (seeded). *(Surfaced: ACT 6–8 of
   `run.py:283-424`; `spread_rumor`/`correct_rumor`/`trace_rumor` on
   `client.py:1424/1483/1461`; anti-hallucination + determinism beats.)*

For the sales framing the demo is **strong today** — this is its center of gravity.

### 1b. As an actual game (something a person would choose to play)

A game needs **objectives, agency, consequence, replayability, and enough content to
sustain a session**. Measured against that:

- **Objective:** exactly one — reach standing ≥ 50 with ≥ 2 of 3 factions
  (`game_end_checker.py:17-18,86-103`). No sub-goals, no scoring, no grade.
- **Agency:** the player has real verbs (dialogue, bribe, spread/correct rumour, generate &
  accept quests, trade, give item, travel) wired through `GameController`
  (`game_controller.py:163-272`) — this is the demo's most underused strength.
- **Consequence:** thin. Verbs move faction standing and NPC relation bands, but almost
  everything funnels into the *single* standing threshold. Bribing always helps; nothing the
  player does can make things *worse* except the scripted Iron Legion (which the player
  cannot actually influence — see §4).
- **Replayability:** four menu arcs (`start_menu.py:37-42`) but three are **linear scripted
  tours** (`run.py`, `run_village_crisis.py`, `run_tavern_intrigue.py`) with fixed beats and
  cached LLM output; only Free Play is interactive, and it has no win state of its own beyond
  the same faction threshold. Replaying changes nothing.
- **Content to sustain a session:** ~5 NPCs, 3 locations, 3 factions, a handful of quests in
  the playable world (§2). A motivated player exhausts the surface in ~10 minutes.

**Educated guess (→ OPEN_QUESTIONS.md):** the intended shape is a **20–30 minute authored
campaign with branching, not an open sandbox.** The scripted-arc skeleton and the
single dramatic Iron-Legion lose condition both point at "directed scenario," so D2/D3
should deepen an authored loop rather than build a colony-sim sandbox.

---

## 2. Baseline inventory of the CURRENT playable loop

### 2.1 Win / lose conditions — `game_end_checker.py` (+ `game_end_poller.py`)

| Condition | Rule | Constants (`file:line`) |
|-----------|------|--------------------------|
| **WIN** | standing ≥ `50` with ≥ `2` of the 3 demo factions | `WIN_STANDING_THRESHOLD=50` `game_end_checker.py:17`; `WIN_MIN_FACTIONS=2` `:18`; logic `check_win` `:86-103` |
| **Demo factions** | `merchants_guild`, `city_guard`, `thieves_guild` | `DEMO_FACTIONS` `:21` |
| **LOSE** | `iron_legion` holds `loc_guard_barracks` (a `CONTROLS` edge) | `LOSE_LOCATION_ID="loc_guard_barracks"` `:27`; `LOSE_FACTION_ID="iron_legion"` `:28`; `check_lose` `:106-117` |
| **Tie-break** | lose checked before win; simultaneous → "lose" (dramatic) | `evaluate_game_end` `:146-151` |
| **Arc tracking** | first faction to cross 50 picks the win-ending subtitle | `ARC_WIN_SUBTITLES` `:31-42`; `detect_first_allied_faction` `:63-83` |

**Polling surface** (`game_end_poller.py`): a daemon thread polls every `interval_s=3.0`
(`:47,54`) via `client.get_npc_reputation(player_id)` and
`client.get_graph_edges("CONTROLS", src_id="iron_legion")` (`:104-107`), then freezes the
first-allied faction once any crosses threshold (`:118-122`). Errors are swallowed and the
prior state retained (`:125-126`).

**Critical observation for D3:** the *lose* condition is structurally unreachable by player
action. The comment at `game_end_checker.py:25-26` notes the legion can only ever control
`loc_guard_barracks`, and battle resolution is a **scripted clock tick** (ACT 5,
`run.py:261-279`), not something the player's choices feed. So today there is effectively
**one win condition and a decorative lose condition** — the thinnest possible economy.

### 2.2 Scenarios — beat/arc structure

| Entry point | Mode | Structure | `file:line` |
|-------------|------|-----------|-------------|
| `run.py` (Munich / `make demo-run`) | **Scripted, linear** | 10 ACTs, ~40 `Scene` objects with `delay_before_ms` pacing; LLM responses disk-cached | `run.py:101-459`; scene classes `run_scenes.py` |
| `run_village_crisis.py` (`make demo-village`) | **Scripted, linear** | 5 beats: blight (world state) → bandit raid (event) → 5 NPC voices | `run_village_crisis.py:178-277` |
| `run_tavern_intrigue.py` (`make demo-tavern`) | **Scripted, linear** | 5 beats: theft event → witness/rumour/hearsay across 3 voices | `run_tavern_intrigue.py:177-276` |
| Free Play (`make demo`) | **Interactive** | Real game window + `GameController` verbs + `GameEndPoller` win/lose + optional `SandboxLoop` auto-tick | `game_controller.py`, `ui/game_window.py:73`, `sandbox_loop.py:20` |

The three scripted arcs are **demo reels, not gameplay** — fixed beats, no branching, output
playable from cache (`--cached`). The only true *game* is Free Play, and it inherits the §2.1
single-objective economy. Scene primitives available for authoring: `NarratorCue`, `SeedCheck`,
`EventFire`, `ClockTick`, `DialogueBeat`/`StreamingDialogueBeat`, plus `run.py`-only
`BribeScene`, `QuestDisplay`, `EmotionDisplay`, `SpreadRumorScene`, `CorrectRumorScene`,
`RumorTraceDisplay`, `PropagatedReputationAct`, `MemoryConsolidate`, `WorldFeed`,
`DeterminismBeat`, `AntiHallucinationBeat`, `RemembersYouBeat` (`run.py:30-52`).
**No branching primitive exists** — `arc_choice.py` is only a 4-value menu enum (§2.5).

### 2.3 Worlds & content counts

| World | NPCs | Locations | Factions | Quests | Other content | Source |
|-------|------|-----------|----------|--------|---------------|--------|
| **Demo / Munich** (playable Free Play) | **5** (`mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`, `old_henryk`) | **3** (`loc_tavern`, `loc_market_square`, `loc_guard_barracks`) | **3** playable + `iron_legion` (`_MILITARY_FACTIONS`) | **6** (`aldric_deliver_quest` + 2 source + 2 chain-target + `demo_*`) | 2 leverage nodes, 1 army, per-NPC beliefs/goals/memories/secret/needs | `seed.py:460-470,478-500,636,914-960`; quests `:848-960` |
| **Village** (`vw_`, eval/scripted only) | **5** (`vw_elder`, `vw_guard`, `vw_healer`, `vw_farmer`, `vw_fence`) | **4** (`vw_village_square`, `vw_gate`, `vw_healer_hut`, `vw_farmland`) | 1+ (`vw_village_council`, `vw_farmers`) | 0 quests; 3 events (`vw_crop_blight`, `vw_bandit_raid`, `vw_missing_child`) | beliefs/goals/memories | `seed_village_world.py:10-11,258-261,374-376` |
| **Tavern** (`tw_`, eval/scripted only) | **3** (`tw_innkeeper`, `tw_wanderer`, `tw_merchant`) | **2** (`tw_tavern`, `tw_market`) | 2 (`tw_merchants`, `tw_innkeepers`) | 0 quests; 3 events (`tw_theft_at_market`, `tw_market_fire`, `tw_travelling_performer`) | beliefs/memories | `seed_tavern_world.py:231-232,236-237,242-250,308-310` |

**Headline counts (playable Free-Play world):** **5 NPCs · 3 locations · 4 factions
(3 alliable) · ~6 quests · 0 player-facing branch points · 1 win condition · 1 (inert)
lose condition.** Village/Tavern are **scripted-only reels**, not Free-Play playable worlds
(no quests, no win economy wired) — D2 should note that promoting them to playable worlds is
itself content work.

### 2.4 UI panels — what is already surfaced

Right panel is a **14-tab Tab-cycling view** (`ui/right_panel.py:58-74`):
`GRAPH`, `KNOWLEDGE`, `PLAYER STATUS`, `CHAIN`, `TRADE`, `INVENTORY`, `ACTIONS`, `INSPECT`,
`WORLD`, `EMOTION`, `NEEDS`, `GOALS`, `POLITICS`, `MEMORY`.

Backing widgets (each `ui/*_panel.py` / `ui/*.py`): `WorldPanelWidget` (`world_panel.py:83`),
`EmotionPanelWidget` (`emotion_panel.py:46`), `NeedsPanelWidget` (`needs_panel.py:57`),
`GoalsPanelWidget` (`goals_panel.py:62`), `PoliticsPanelWidget` (`politics_panel.py:51`),
`MemoryPanelWidget` (`memory_panel.py:54`), `InspectPanelWidget` (`inspect_panel.py:37`),
`InventoryPanelWidget` (`inventory_panel.py:30`), `TradePanelWidget` (`trade_panel.py:33`),
`QuestPanelWidget` (`quest_panel.py:28`), `KnowledgeSidebarWidget` (`knowledge_sidebar.py:34`),
`GossipChainWidget` (`gossip_chain.py:32`), `ActionsPanelWidget` (`actions_panel.py:56`),
`ActionBarWidget` (`action_bar.py:23`), `RelationTicker` (`relation_ticker.py:54`).
Shared widgets: `InputBox`, `ScrollableLog`, `NpcListWidget`, `DegradationBadge`,
`EventBanner` (`widgets.py:98/176/297/376/445`). Left side: `LeftPanelRenderer`
(`left_panel.py:44`). Container: `GameWindow` (`game_window.py:73`).

**Implication for D1:** the demo already has a **mature panel/tab framework**. Surfacing a
new dormant engine (treaty/oath/chapter) is "append an enum value + write one
`*_panel.py` + a poller" — the pattern is proven 14× over. This makes Pillar-1 mechanics
*cheap on the UI side*; the cost is the REST route enabler, not the pygame surface.

### 2.5 Pollers — live-state surfaces (background threads → panels)

Ten pollers, each a daemon polling the engine and feeding a panel:
`game_end_poller.py` (win/lose), `emotion_poller.py` (EMOTION), `gold_poller.py` (player
gold / PLAYER STATUS), `npc_needs_poller.py` (NEEDS), `npc_goals_poller.py` (GOALS),
`npc_politics_poller.py` (POLITICS), `npc_memory_poller.py` (MEMORY), `world_poller.py` +
`world_state_poller.py` (WORLD feed + world state), `npc_initiative_poller.py` (NPC-initiated
action). **Pattern (D1 reuse):** thread + `threading.Lock` + `get_state()` snapshot +
swallow-and-retain on error, exactly as `game_end_poller.py:36-127`.

### 2.6 Branching — `arc_choice.py`

`ArcChoice` is a **4-value enum** (`MUNICH`, `VILLAGE`, `TAVERN`, `FREE_PLAY`,
`arc_choice.py:14-24`) consumed only by `start_menu.py:37-42`. It selects which **subprocess
arc** to launch — it is **arc selection, not in-game branching**. There is **no player-facing
choice/consequence branch primitive anywhere in the loop.** This is the single biggest
content gap for D2: "branching arcs via `arc_choice.py`" requires *building* the branch seam,
not extending an existing one.

### 2.7 EngineClient reachability surface (the hard boundary)

`EngineClient` (`client.py`) exposes ~50 REST methods already — dialogue (REST + WS),
graph nodes/edges CRUD, world state, reputation (get/put/adjust), emotion, relationship,
clock, engine status, events, beliefs, goals, memories (+ consolidate), secrets, `PART_OF`,
the full **quest lifecycle** (`generate/offer/accept/objective/evaluate/reward`,
`client.py:846-1102`), interaction + interaction-band, item price, **trade**
(`post_trade :1185`), **pledges** (`post_pledge :1226`, `get_pledges_for_npc :1257`),
**leverage** (`get_leverage_for_npc :1277`), needs, pending intents, items, and **rumor
warfare** (`spread_rumor :1424`, `trace_rumor :1461`, `correct_rumor :1483`).
**Reachability note for D1/D4:** of the four named dormant engines, only **`treaty`** has a
route (`api/routes/treaties.py`) — and **no `EngineClient` method calls it**, so even treaty
is type-(B) "enabler needed" until a client method is added. `oath`, `story_pacing`,
`chapter` have **no route at all** in `api/routes/` (confirmed: the dir has `treaties.py`,
`pledges.py`, `quest.py`, `reputation.py`, etc. but no `oaths.py`/`story_pacing.py`/
`chapter.py`). Note `pledges.py` exists and `post_pledge`/`get_pledges_for_npc` are already on
the client — D1 should check whether "oath" is partly reachable via the **pledge** surface
before declaring it fully blocked.

---

## 3. The rubric (every other lens scores against this)

Score each proposal on six dimensions. **D5 reuses this table verbatim.**

| Dimension | Scale | What it measures |
|-----------|-------|------------------|
| **Player-value** | low / med / high | Does it add objective, agency, or consequence a player *feels*? Does it make the loop replayable? |
| **Demo/sales-fit** | low / med / high | Does it showcase a **moat** claim from §1a (persistent memory, knowledge provenance, relationships-as-state, consequential auditable world)? Generic game-feel that any engine could show scores *low* here even if player-value is high. |
| **Reachability** | A / B / C | **A** = pure demo-side (an `EngineClient` method already exists + UI/loop work only). **B** = needs an engine-side enabler (new `api/routes/*.py` + `EngineClient` method) — engine work, tracked separately. **C** = needs a schema or layer/DECISIONS human call. *(This is the reachability gate from §0; A-items can ship now.)* |
| **Effort** | S / M / L / XL | Demo-side build cost. UI is cheap (proven 14-panel pattern, §2.4); content authoring (LLM-voiced NPCs, quest chains) and new branch seams are the expensive parts. |
| **Dependency** | list / none | Which other proposal or enabler must land first (e.g. a branch primitive before any branching arc; a route enabler before a dormant-engine panel). |
| **Content cost** | low / med / high | Authoring load: new NPC voice descriptors, quest objectives, scenario beats, branch text. Distinct from engineering effort because it scales with session length, not code. |

**Scoring guidance for D5:** Phase 1 = high player-value × high demo-fit × reachability **A**
× low dependency. Front-load type-(A) pure-demo wins (they need zero engine work and the panel
pattern is proven). A proposal that is high player-value but **demo-fit low** (e.g. a generic
inventory crafting loop) is a *deprioritize* — it makes a game but not a showcase of *this*
engine. A proposal that is high demo-fit but reachability **B/C** routes to FEASIBILITY's
keystone-enabler list, not Phase 1.

---

## 4. Blunt verdict

**The single biggest reason this reads as a demo, not a game: there is exactly one thing
to achieve and exactly one way the player's choices matter — push two faction standings past
50 — and the one dramatic failure state (`iron_legion` taking the barracks) is scripted,
player-inert, and unreachable by anything the player does.** Every rich verb the engine
exposes — bribe, rumour warfare, quests, trade, leverage, memory — collapses into the same
single scalar gate, so distinct actions have no *distinct* consequences and no reason to
choose one path over another. The result is a beautiful, moat-proving **interaction
showcase** with no **stakes, no branching, and no replay incentive**: you watch the engine be
clever, you nudge two numbers to 50, you win the same way every time. Turning it into a game
means giving the player **multiple, mutually-tensioned objectives with real failure modes**
(D3), **branching authored content that those objectives drive** (D2), and **the dormant
relationship-stakes engines — treaty/oath/chapter — surfaced as the things that raise and
break those stakes** (D1).

---

## Cross-references
- **D1 (`DORMANT_ENGINES.md`)** — uses §2.4 panel pattern + §2.5 poller pattern + §2.7
  reachability boundary (only `treaty` has a route, none have a client method; check `pledge`
  surface for `oath`).
- **D2 (`CONTENT_PLAN.md`)** — uses §2.3 counts as the baseline to grow; must *build* the
  branch seam (§2.6 — `arc_choice.py` is not it); note Village/Tavern are scripted-only.
- **D3 (`ECONOMY_DEPTH.md`)** — deltas `game_end_checker.py` constants (§2.1); must make the
  lose condition player-reachable and add ≥2 distinct failure states + multi-objective win.
- **D4 (`FEASIBILITY.md`)** — applies the §3 reachability A/B/C gate; keystone enablers are
  the missing `oath`/`story_pacing`/`chapter` routes + a `treaty` client method.
- **D5 (`DEMO_EXPANSION_ROADMAP.md`)** — reuses the §3 six-dimension rubric and the §4 verdict
  as the north star ("multiple tensioned objectives + branching + stakes engines").
