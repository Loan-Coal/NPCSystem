# Demo Script — NPCSystem Hackathon Demo
## June 6, 2026 · Target runtime: 5:00 ± 15 seconds

---

## Characters

| NPC ID | Display name | Location | Role in demo | Voice / personality |
|--------|-------------|----------|--------------|---------------------|
| `captain_sorn` | Captain Sorn | Guard Barracks | **Source** — direct witness of the war event | Clipped military diction. Direct, no hedging. References duty and chain of command. Names the enemy without emotion. |
| `mira_innkeeper` | Mira | The Tavern | **First relay** — hears it from Sorn, passes on | Warm and observant. Cautious about politics. Frames hard news as rumor she heard from "a guard who passed through." |
| `old_henryk` | Old Henryk | Market Square | **Terminal node** — distorted third-hand account | Rambling. Mixes rumour with memory. Gives wrong details with full confidence — he was there for the last war, so he knows these things. |
| `aldric_merchant` | Aldric | Market Square | Second event NPC — reacts to market fire | Calculating but rattled. References the south warehouse fire from his past. Fear and commercial instinct compete. |
| `lira_fence` | Lira | The Tavern | Background NPC | Cool, opportunistic. The fire is an opportunity, not a disaster. |

---

## Locations

| ID | Display name | Who is here |
|----|-------------|-------------|
| `guard_barracks` | Guard Barracks | Captain Sorn |
| `tavern` | The Tavern | Mira, Lira |
| `market_square` | Market Square | Old Henryk, Aldric |

---

## Inciting Events

### Event 1: Northern War Begins

| Field | Value |
|-------|-------|
| Event ID | `northern_war_begins` |
| Engine call | `PATCH /v1/world-state` → `epoch=war, active_conditions=["northern_war_active"]` |
| Who knows immediately | `captain_sorn` (seeded via `KNOWS_ABOUT` at seed time) |
| Gossip path | `captain_sorn` → `mira_innkeeper` → `old_henryk` |
| Distortion introduced | Mira garbles the faction name (legion → guard). Henryk inflates casualties 5×, misremembers the location, and reduces the enemy to a vague "northmen." |
| Demo timing | T+0:30 (programmatic, not keypress) |

### Event 2: Market Fire

| Field | Value |
|-------|-------|
| Event ID | `market_fire` |
| Description | Fire breaks out in Market Square — stalls burning, cause unknown |
| Who is affected | `aldric_merchant` (fear↑, panic — echoes his south warehouse fire memory), `lira_fence` (opportunity↑ — chaos means cover) |
| Emotional / quest effect | Aldric's fear spikes; he may reference wanting to move goods before the city guard locks the square down |
| Demo timing | T+3:00 |

---

## Gossip Chain Detail

```
captain_sorn
  KNOWS_ABOUT northern_war_begins
  └─ ground truth: { location: "northern_border", faction: "iron_legion", casualties: 200 }

  → gossip tick 1 → mira_innkeeper
  KNOWS_ABOUT northern_war_begins (distorted hop 1)
  └─ mira's version: { location: "northern_border", faction: "iron_guard", casualties: 200 }

  → gossip tick 2 → old_henryk
  KNOWS_ABOUT northern_war_begins (distorted hop 2)
  └─ henryk's version: { location: "the king's pass", faction: "the northmen", casualties: 1000 }
```

The sidebar will show this diff. "What Henryk thinks" vs "What actually happened."
Amber fields in the sidebar: `faction` (all hops), `location` (hop 2), `casualties` (hop 2).

---

## Dialogue Beats

> Each beat is one exchange (player says → NPC responds). Aim for NPC responses under 60 words — punchy, not novelistic.

### Beat 1 — Captain Sorn @ Guard Barracks (T+1:30)

**Context:** War event has just been injected. Sorn has direct KNOWS_ABOUT.

- **Player says:** `"Captain, what's happening in the north?"`
- **Expected NPC response (summary):** Sorn confirms the war directly. Names the Iron Legion crossing the northern border. References his duty — the city watch is on alert. No hedging.
- **Narration (spoken live):** "Captain Sorn has first-hand knowledge — the engine injected the war event directly into his context graph as a KNOWS_ABOUT edge. Watch how he speaks with authority."

### Beat 2 — Mira @ The Tavern (T+2:00)

**Context:** One gossip tick has fired. Mira received a distorted relay from Sorn.

- **Player says:** `"Mira, have you heard any news from the north?"`
- **Expected NPC response (summary):** Mira references conflict up north. She says she heard it from a guard passing through — she's cautious. She names the wrong faction: "the Iron Guard" instead of Iron Legion.
- **Narration (spoken live):** "One gossip tick later. Mira heard it second-hand from a guard. Notice the faction name is already off — the Iron Guard, not the Iron Legion. The distortion engine has done its first hop."

### Beat 3 — Old Henryk @ Market Square (T+2:30)

**Context:** Two gossip ticks have fired. Henryk has a garbled third-hand account. This is the money shot.

- **Player says:** `"Henryk, I heard there was trouble up north?"`
- **Expected NPC response (summary):** Henryk has it badly wrong. He says a thousand men fell at the king's pass, at the hands of "the northmen." He delivers it with full confidence — he ran dispatches through that pass in the last war, so he knows these things.
- **Narration (spoken live):** "Now open the sidebar. Left column: what Henryk just told you. Right column: what Captain Sorn actually witnessed. The engine tracked every distortion hop — wrong faction, wrong location, casualties inflated five times over."

### Beat 4 — Aldric @ Market Square (T+3:30)

**Context:** Market fire has just fired. Aldric's emotional state has shifted.

- **Player says:** `"Aldric, are you alright? Was that fire near your stall?"`
- **Expected NPC response (summary):** Aldric is rattled. He references the fire. There's an echo of the south warehouse fire he remembers — he wants his goods moved before the guard locks the square. Fear and commercial calculation, competing.
- **Narration (spoken live):** "Second event: fire in the market square. Aldric has a memory of a warehouse fire in his past — the engine surfaces that context. His emotional state has shifted. A different NPC, Lira, reacts to the same event as an opportunity."

---

## Narration Script

> Spoken live over the pre-recorded video. Timestamps are approximate.

```
[0:00]
"Most game NPCs forget you the moment you leave the room. NPCSystem gives them
persistent memory, relationships, and the ability to gossip — and lie."
"The global NPC AI market hits $2 billion by 2028. No one has cracked persistent
knowledge propagation at the middleware level. We have."

[0:30]
"This is a live backend — Neo4j knowledge graph, gossip propagation engine,
dialogue system. Five NPCs across three locations. Watch what happens when
I trigger a war event."

[0:45]
[Event fires on screen]
"Northern war breaks out. Captain Sorn has it — he's at the barracks, he
has a direct KNOWS_ABOUT edge in the graph. No one else knows yet."

[1:00]
"I advance the gossip clock."
[Clock ticks on screen]
"The engine walks the social graph. Sorn tells Mira at the tavern. Mira
tells Old Henryk at the market. Each hop introduces distortion — deterministically,
reproducibly."

[1:30]
[Beat 1 — Sorn dialogue]
"Ask Sorn directly."
[Response appears]
"Captain Sorn has first-hand knowledge — the engine injected the war event
directly into his context graph as a KNOWS_ABOUT edge. Watch how he speaks
with authority."

[2:00]
[Beat 2 — Mira dialogue]
"Now Mira — she heard it second-hand."
[Response appears]
"One gossip tick later. The faction name is already off — the Iron Guard,
not the Iron Legion. The distortion engine has done its first hop."

[2:30]
[Beat 3 — Henryk dialogue]
"Old Henryk. Third hand."
[Response appears]
"Now open the sidebar."
[Tab to gossip sidebar]
"Left column: what Henryk thinks happened. Right column: ground truth.
Wrong faction, wrong location, casualties inflated five times over.
The engine tracked every hop. The player can see exactly where the story broke."

[3:00]
[Second event fires]
"Second event — fire in the market square."
[Beat 4 — Aldric dialogue]
"Aldric has a memory of a warehouse fire from his past. The engine surfaces
that context. His emotional state has shifted. A different NPC reacts to
the same event as an opportunity."

[3:45]
"This is middleware. Studio integration is a single API call. The knowledge
graph, gossip engine, and dialogue system license as a bundle."

[4:00]
[Slides begin]
[Slide 1 — Problem]
[Slide 2 — Solution]
[Slide 3 — Market + competition]
[Slide 4 — Traction]
[Slide 5 — Ask]

[5:00]
End.
```

---

## Engine API calls fired by `demo_game/run.py`

In sequence:

```python
# 1. Verify seed state
GET /v1/graph/nodes/captain_sorn
GET /v1/graph/edges/KNOWS_ABOUT?source=captain_sorn

# 2. Fire war event
PATCH /v1/world-state  { "epoch": "war", "active_conditions": ["northern_war_active"] }

# 3. Advance gossip clock x 3
POST /v1/scheduler/advance  { "delta_ticks": 1 }   # x 3

# 4. Dialogue beats 1–3
POST /v1/dialogue/captain_sorn   { "player_input": "Captain, what's happening in the north?" }
POST /v1/dialogue/mira_innkeeper { "player_input": "Mira, have you heard any news from the north?" }
POST /v1/dialogue/old_henryk     { "player_input": "Henryk, I heard there was trouble up north?" }

# 5. Sidebar data
GET /v1/graph/edges/KNOWS_ABOUT?source=old_henryk
GET /v1/graph/nodes/northern_war_begins

# 6. Second event — market fire
PATCH /v1/world-state  { "epoch": "war", "active_conditions": ["northern_war_active", "market_fire_active"] }

# 7. Dialogue beat 4
POST /v1/dialogue/aldric_merchant  { "player_input": "Aldric, are you alright? Was that fire near your stall?" }
```

---

## Sign-off checklist (complete before recording)

- [ ] All `[FILL IN]` placeholders above are resolved ✓ (this file is now complete)
- [ ] Gossip distortion values are fixed in seed data (not random per run)
- [ ] `make demo-run ARGS=--cached` plays end-to-end without error
- [ ] LLM judge evals 3/3 pass for demo-path NPCs
- [ ] Sidebar shows amber distortion on at least 2 fields
- [ ] Narration script has been read aloud at pace — total under 5:00
- [ ] Second event produces visible emotional shift or quest offer
