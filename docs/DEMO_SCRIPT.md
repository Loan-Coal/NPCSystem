# Demo Script — NPCSystem Hackathon Demo
## June 6, 2026 · Target runtime: 5:00 ± 30 seconds
## Phase 6 complete — all engine beats covered

---

## Characters

| NPC ID | Display name | Location | Role in demo | Voice / personality |
|--------|-------------|----------|--------------|---------------------|
| `captain_sorn` | Captain Sorn | Guard Barracks | **Source** — direct witness; streamed dialogue, Act 1 | Clipped military diction. Direct. Names the enemy without emotion. No hedging. |
| `mira_innkeeper` | Mira | The Tavern | **First relay** — second-hand gossip; memory consolidation, Act 4 | Warm and observant. Cautious about politics. Frames hard news as rumour. |
| `old_henryk` | Old Henryk | Market Square | **Terminal node** — garbled third-hand account | Rambling. Mixes rumour with memory. Wrong details delivered with full confidence. |
| `aldric_merchant` | Aldric | Market Square | Quest + emotion change, Act 2 | Calculating but rattled. Fear and commercial instinct compete after the fire. |
| `lira_fence` | Lira | The Tavern | Bribe target + post-bribe response, Act 3 | Cool, opportunistic. The fire is an opportunity, not a disaster. |

---

## Locations

| ID | Display name | Who is here |
|----|-------------|-------------|
| `loc_guard_barracks` | Guard Barracks | Captain Sorn; Iron Legion + City Guard armies |
| `loc_tavern` | The Tavern | Mira, Lira |
| `loc_market_square` | Market Square | Old Henryk, Aldric |

---

## Act Structure (5-minute run)

| Act | Engines demonstrated | T (approx) |
|-----|---------------------|-----------|
| 1 — Gossip chain | Gossip, streaming dialogue (S6.4), world state | 0:00–2:30 |
| 2 — Quest + emotion | Quest engine (S2.5), emotion engine (S6.1) | 2:30–3:30 |
| 3 — Bribe + politics | Interaction engine, faction politics (S6.2) | 3:30–4:00 |
| 4 — Memory recall | Memory consolidation engine (S6.3) | 4:00–4:15 |
| 5 — Military engine | Military engine (S6.5), WORLD feed (S6.0) | 4:15–4:50 |

---

## Inciting Events

### Event 1: Northern War Begins

| Field | Value |
|-------|-------|
| Event ID | `northern_war_begins` |
| Engine call | `PUT /v1/graph/nodes/world_state` → `epoch=war, active_conditions=["northern_war_active"]` |
| Who knows immediately | `captain_sorn` (seeded via `KNOWS_ABOUT` at seed time) |
| Gossip path | `captain_sorn` → `mira_innkeeper` → `old_henryk` |
| Distortion introduced | Mira: faction name garbled (Legion → Guard). Henryk: location wrong, casualties ×5. |
| Demo timing | T+0:30 |

### Event 2: Market Fire

| Field | Value |
|-------|-------|
| Event ID | `market_fire` |
| Engine call | `PUT /v1/graph/nodes/world_state` → adds `market_fire_active` |
| Emotional effect | Aldric's fear spikes (warehouse-fire memory surfaces). Lira sees opportunity. |
| Demo timing | T+2:45 |

### Event 3: Battle at the Barracks (military engine)

| Field | Value |
|-------|-------|
| Trigger | `POST /v1/clock/advance` (military tick) |
| Armies | `army_iron_legion` (str=100) vs `army_city_guard_main` (str=60) at `loc_guard_barracks` |
| Outcome | Iron Legion wins; battle Event node emitted; WORLD feed updated |
| Demo timing | T+4:20 |

---

## Gossip Chain Detail

```
captain_sorn
  KNOWS_ABOUT northern_war_begins
  └─ ground truth: { faction: "iron_legion", location: "northern_border", casualties: 200 }

  → gossip tick 1 → mira_innkeeper
  KNOWS_ABOUT northern_war_begins (distorted hop 1)
  └─ mira's version: { faction: "iron_guard", location: "northern_border", casualties: 200 }

  → gossip tick 2 → old_henryk
  KNOWS_ABOUT northern_war_begins (distorted hop 2)
  └─ henryk's version: { faction: "the northmen", location: "king's pass", casualties: 1000 }
```

Open the KNOWLEDGE sidebar after Beat 3. Amber fields: `faction` (all hops), `location` (hop 2),
`casualties` (hop 2).

---

## Dialogue Beats (Acts 1–3)

> All five dialogue beats use WebSocket streaming (S6.4). Tokens appear word-by-word.

### Beat 1 — Captain Sorn @ Guard Barracks (T+1:05)

- **Player says:** `"Captain, what's happening in the north?"`
- **Expected:** Confirms war directly. Names the Iron Legion. References duty. No hedging.
- **Narration:** "Sorn has first-hand KNOWS_ABOUT. Watch streaming — tokens arrive in real time."

### Beat 2 — Mira @ The Tavern (T+1:35)

- **Player says:** `"Mira, have you heard any news from the north?"`
- **Expected:** Cautious second-hand account. Wrong faction name ("Iron Guard").
- **Narration:** "One hop later. Faction name already garbled — the distortion engine ran."

### Beat 3 — Old Henryk @ Market Square (T+2:05)

- **Player says:** `"Henryk, I heard there was trouble up north?"`
- **Expected:** Complete confidence, totally wrong. Thousands dead at king's pass.
- **Narration:** "Open the sidebar. Left: Henryk's version. Right: ground truth."

### Beat 4 — Aldric @ Market Square (T+3:05)

- **Player says:** `"Aldric, are you alright? Was that fire near your stall?"`
- **Expected:** Rattled. References warehouse fire memory. Fear + commercial calculation.
- **Narration:** "After the fire event, emotion panel shows Aldric's shift."

### Beat 5 — Lira @ The Tavern after bribe (T+3:55)

- **Player says:** `"Lira, did you hear about the fire? Seems like your kind of chaos."`
- **Expected:** Cool and opportunistic — but warmer since player's standing improved.
- **Narration:** "Same NPC, same event. Standing changed after the bribe. Tone follows."

---

## Narration Script

```
[0:00]
"Most game NPCs forget you the moment you leave the room. NPCSystem gives them
persistent memory, relationships, and the ability to gossip — and lie."
"The global NPC AI market hits $2 billion by 2028. No one has cracked persistent
knowledge propagation at the middleware level. We have."

[0:30]
"This is a live backend — Neo4j knowledge graph, five domain engines, streaming
dialogue. Five NPCs across three locations. Watch what happens when I trigger a war."
[Event fires on screen]

[1:00]
"Clock advances. The gossip engine walks the social graph. Sorn tells Mira, Mira
tells Henryk. Each hop introduces deterministic distortion."
[Clock ticks]

[1:05] — Beat 1 streaming
"Ask Captain Sorn. Watch the response stream token by token — WebSocket, no polling."
[Tokens appear]

[1:35] — Beat 2 streaming
"Mira heard it second-hand. The faction name is already wrong."
[Tokens appear]

[2:05] — Beat 3 streaming
"Old Henryk. Third hand. Open the knowledge sidebar."
[Sidebar opens — amber fields visible]
"Left: what Henryk thinks. Right: ground truth. The engine tracked every distortion hop."

[2:35] — Quest display
"Quest engine: Aldric has an active mission he generated from world context."

[2:50] — Market fire + Beat 4
"Second event — fire in the market. Aldric's emotion changes. His warehouse-fire memory
surfaces. Watch the emotion panel update."

[3:40] — Bribe
"Bribe the fence. Twenty gold. Player standing with the Thieves' Guild improves."
[Standing display]
"Political consequence: Lira's dialogue tone shifts on the very next exchange."
[Beat 5]

[4:00] — Memory consolidation
"Memory engine: Mira's session dialogue gets consolidated into a permanent Memory node.
Next session, she'll remember this conversation."

[4:20] — Military engine
"Military engine. Iron Legion, strength 100, faces City Guard, strength 60,
at the barracks. One clock tick."
[Clock advance]
"WORLD feed: battle resolved. Iron Legion wins. The war has reached the city gates."

[4:45]
"This is middleware. Studio integration is a single API call. The knowledge
graph, five engines, and streaming dialogue license as a bundle."

[5:00]
[Slides begin]
```

---

## Engine API calls fired by `demo_game/run.py`

In sequence:

```python
# 1. Verify seed state
GET /v1/graph/edges/KNOWS_ABOUT/captain_sorn/northern_war_begins

# 2. Fire war event (Act 1)
PUT /v1/graph/nodes/world_state  { "id": "world_demo", "epoch": "war", ... }

# 3. Advance gossip clock x3
POST /v1/clock/advance  { "delta_ticks": 1 }   # x3

# 4. Streaming dialogue — Sorn, Mira, Henryk (Act 1)
WS /v1/ws/dialogue  { "npc_id": "captain_sorn", "player_message": "..." }   # x3

# 5. Quest display (Act 2)
GET /v1/admin/quests/aldric_deliver_quest

# 6. Market fire event
PUT /v1/graph/nodes/world_state  { adds "market_fire_active" }

# 7. Streaming dialogue — Aldric (Act 2)
WS /v1/ws/dialogue  { "npc_id": "aldric_merchant", ... }

# 8. Emotion display — Aldric
GET /v1/npc/aldric_merchant/emotion

# 9. Bribe Lira (Act 3)
GET /v1/graph/nodes/Character/player_demo
GET /v1/graph/characters/player_demo/reputation
POST /v1/graph/edges/STANDS_WITH  { standing: +15 to thieves_guild }
PATCH /v1/graph/nodes/Character/player_demo  { currency_balance: -20 }

# 10. Streaming dialogue — Lira (Act 3)
WS /v1/ws/dialogue  { "npc_id": "lira_fence", ... }

# 11. Memory consolidation (Act 4)
POST /v1/admin/memories/consolidate/mira_innkeeper

# 12. Military tick (Act 5)
POST /v1/clock/advance  { "delta_ticks": 1 }

# 13. WORLD feed
GET /v1/system/events?limit=8
```

---

## Sign-off checklist (complete before recording)

- [ ] `make demo-run ARGS=--dry-run` prints all scene names without error
- [ ] `make demo-run ARGS=--cached` plays back end-to-end without error (after live warm)
- [ ] Streaming beats: tokens visible in terminal in real time
- [ ] Gossip sidebar: amber fields visible after Beat 3
- [ ] Emotion panel: Aldric shows fear/negative after market fire
- [ ] Bribe: standing with thieves_guild increases, gold decreases
- [ ] Memory: Mira memory_id returned (or turn-threshold message)
- [ ] WORLD feed: at least one `battle` event visible after military tick
- [ ] Narration script read aloud at pace — total under 5:15
