# Next Session Handoff

**Branch:** `munich-demo`
**Last completed:** S3.4 — Tab toggle, GRAPH ↔ KNOWLEDGE sidebar, 147/147 demo tests
**Next task:** Visual Planning Phase — stress-test the Phase 4 UI ideas against the actual engine

---

## Session goal

This is a **planning-only session**. No code is written. The output is a prioritised, reality-checked plan for making the demo game visually compelling before recording the final take.

**The user's ideas to evaluate (stress-test each one):**
1. Scalable window size (the window is currently hardcoded 1280×720)
2. NPC profile images — one portrait per NPC
3. Location background images — one per location (Tavern, Market Square, Guard Barracks)
4. Action buttons instead of free-text input — e.g. a **Trade** button that invokes the trading engine live
5. Quest panel — surface the quest engine output visually
6. Any other engine the codebase has that could be shown in the demo but currently isn't

**For each idea, the planning session must:**
- Find the relevant code (engine endpoint, existing UI hook, or required new work)
- Identify the specific flaw or risk (timeline, complexity, visual clutter, demo flow disruption)
- Suggest a concrete improvement or scoped alternative
- Estimate session cost (1 session = ~2–3 hours of focused work)
- Give a clear YES / MAYBE / CUT verdict with reasoning

**Ground rule:** Every claim must be anchored to a real file, endpoint, or ROADMAP step — no hypotheticals.

---

## What to read at session start

Before planning anything, read these files to ground the session:

| File | What you'll find |
|------|-----------------|
| `demo_game/ui/game_window.py` | Full current layout — panels, constants, rendering pipeline |
| `demo_game/constants.py` | NPC IDs, location IDs, display names, tint colours |
| `demo_game/client.py` | Every API call the demo currently makes — tells you what the engine exposes |
| `src/npc_engine/api/` | All FastAPI routes — this is the authoritative list of what endpoints exist |
| `project-harness/ROADMAP.md` | Phase 4 steps S4.0–S4.6 already planned (quest banner, typography, palette, labels, dialogue box, event flash, layout audit) |
| `docs/DEMO_SCRIPT.md` | The 5-beat narrated scenario the demo must support |

Run a grep for `@router` across `src/npc_engine/api/` to inventory every live endpoint. That's the only source of truth for what buttons and panels are actually buildable.

---

## Current UI state (S3.4 exit)

```
┌─────────────────────────────────────┬───────────────────────────────┐
│  Location bar (tinted, 36px)        │  [GRAPH / KNOWLEDGE] header   │
│  World-state bar (epoch+conditions) │  (Tab toggles)                │
│  NPC list (36px rows, clickable)    │                               │
│  ─── "Talking to [NPC]" header ─── │  Right panel:                 │
│  Dialogue log (scrollable, wrapped) │  • GRAPH: live Neo4j viz      │
│  Degradation badge                  │  • KNOWLEDGE: 2-col diff      │
│  [text input box]                   │    (distorted vs truth)       │
├─────────────────────────────────────┴───────────────────────────────┤
│  Nav bar: [TAVERN] [MARKET SQUARE] [GUARD BARRACKS]                 │
└─────────────────────────────────────────────────────────────────────┘
```

Window size: 1280×720, hardcoded. Font: pygame SysFont monospace/sans. Colours: dark bg, amber accents — not yet the full Caves-of-Qud palette from Phase 4 roadmap.

**Key constants in `game_window.py` / `constants.py` to know before planning layout changes:**
- `WINDOW_W, WINDOW_H = 1280, 720`
- `LEFT_PANEL_RATIO = 0.60`
- `NAV_BAR_H = 48`, `LOC_BAR_H = 36`, `NPC_LIST_ROW_H = 36`, `PANEL_HEADER_H = 24`
- NPC IDs: `mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`, `old_henryk`
- Locations: `tavern`, `market_square`, `guard_barracks`

---

## Idea 1: Scalable window size

**What to evaluate:**
- `pygame.display.set_mode()` supports `pygame.RESIZABLE` flag. Check if derived constants (`_RIGHT_X`, `_RIGHT_W`, etc.) recompute on resize or are cached at init.
- `GraphPoller` is initialized with `_RIGHT_W, _RIGHT_H` at construction — it would need to be re-created on resize.
- Every widget (`ScrollableLog`, `KnowledgeSidebarWidget`, `NpcListWidget`) takes a `rect` argument at draw-time, so they should reflow cleanly if the layout constants are recalculated.
- Risk: `PYGAME_RESIZABLE` fires `VIDEORESIZE` events; handling mid-session resize requires re-initialising the graph poller surface. Is this worth the complexity before recording?
- Alternative: offer 2 fixed sizes (1280×720 and 1920×1080) switchable at launch via a CLI arg.

---

## Idea 2: NPC profile images

**What to evaluate:**
- One 64×64 or 80×80 portrait per NPC, displayed in the NPC list row next to the name.
- Current `NpcListWidget` rows are 36px tall. Portraits at 64px would require taller rows → expands the NPC list → compresses the dialogue log. Check the vertical budget in `_draw_left_panel`.
- Asset approach: no art exists yet. Use generated placeholder PNGs (any free AI image generator); swap the file later. `pygame.image.load()` + `pygame.transform.smoothscale()` to 64×64.
- Free asset sources to suggest: Kenney.nl (CC0 2D character sprites), OpenGameArt.org (CC0/CC-BY portraits), Itch.io "free assets" tag. For placeholder generation: Stable Diffusion, DALL-E, Midjourney.
- File layout: `demo_game/assets/portraits/{npc_id}.png`. Fall back to a coloured initial circle if the file is missing.
- Risk: portrait loading at startup vs. on-demand. At startup is simpler; on-demand wastes frames. Startup is fine for 5 NPCs.

---

## Idea 3: Location backgrounds

**What to evaluate:**
- Background image blitted behind the left or right panel, tinted with the existing `LOCATION_TINTS` colour.
- Current location bar already applies a tint strip. A background image would replace or extend that strip.
- File layout: `demo_game/assets/backgrounds/{location_id}.png` scaled to the panel size.
- Risk: a busy background image will make the dialogue text unreadable. Mitigation: semi-transparent dark overlay before drawing text, or restrict background to a small strip (top 100px of left panel).
- Free CC0 sources: Kenney.nl backgrounds, OpenGameArt "tavern" / "medieval market", Craftpix.net free section.
- Alternative: procedural background — just a gradient or a tileable dark texture in the existing palette. Zero asset dependency, still adds visual depth.

---

## Idea 4: Trading buttons (interactive, live engine call)

**What to evaluate:**
- First, grep `src/npc_engine/api/` for trade/economy endpoints. Identify the exact route signature and required payload.
- Check `demo_game/client.py` — is a trade method already stubbed? If not, what fields does the endpoint need?
- The button would live in the left panel, replacing or augmenting the text input. Possible layout: row of action buttons below the NPC list ("ASK", "TRADE", "BARTER"), clicking one submits a preset player action.
- Risk: if the trade endpoint returns a non-dialogue response format, `parse_dialogue_response()` won't handle it — need to check if trade returns a `npc_response` string or a structured trade object.
- Demo flow question: should the Trade button trigger a canned trade line from the NPC (using the dialogue engine with a trade-framed prompt) or hit a separate trade engine that returns trade offer data? These are very different UX and engineering stories.
- If the trade engine returns structured data (offer price, items), you need a new panel to display it. If it just returns NPC dialogue, you can route through the existing dialogue log.

---

## Idea 5: Quest panel

**What to evaluate:**
- `GET /v1/quests/{npc_id}` — confirm this route exists in `src/npc_engine/api/`. If it does, what does it return? (Quest node fields: title, description, status, reward?)
- ROADMAP S4.0 already plans a `[QUEST AVAILABLE]` banner after Aldric's Beat 4 response. The quest panel would extend this.
- Layout option A: third tab on the right panel (alongside GRAPH and KNOWLEDGE). Tab key cycles all three.
- Layout option B: inline in the left panel — a collapsible "QUESTS" section below the dialogue log.
- Risk: if the quest engine only fires quests on specific NPC interactions, the panel will be empty most of the time. Clarify: is `GET /v1/quests/aldric_merchant` live after Beat 4, or does it need the dialogue to fire first?
- Minimal viable: a `QuestBadge` or banner that appears when a quest node exists for the active NPC, with the quest title and a one-line description. No separate panel needed.

---

## Idea 6: What else the engine has that isn't shown

Ask the planning session to scan `src/npc_engine/api/` and `src/npc_engine/engines/` and list every engine that has a live API endpoint but is NOT currently called by `demo_game/client.py`. For each:
- What does it return?
- Can it be surfaced with 1 session of work?
- Does it tell a visual story in the 5-minute demo?

Known candidates from codebase (verify each is wired in the API):
- **Emotion engine** — NPCs have emotional state. Is there a `GET /v1/emotions/{npc_id}` endpoint? Could show a mood indicator next to the NPC portrait.
- **Reputation system** — `standing` values between NPCs/player. Could show a reputation bar.
- **Scheduler/tick engine** — `POST /v1/clock/advance`. Already used. Could visualise a clock.
- **Faction engine** — characters belong to factions. Could show faction badge next to NPC name.

---

## Phase 4 work already planned (don't duplicate)

These are already on the roadmap (S4.0–S4.6). The planning session should fit new ideas INTO this sequence, not alongside it:
- S4.0: Quest banner after Aldric Beat 4
- S4.1: TTF font (Terminus or similar) — `demo_game/assets/`
- S4.2: Full colour palette constant
- S4.3: NPC name labels, `▶` active indicator
- S4.4: Boxed dialogue panel, speaker name, degradation tier badge
- S4.5: Event flash banner
- S4.6: Layout audit

The new ideas (portraits, backgrounds, trading buttons, scalable size) need to slot into this sequence or replace lower-priority items.

---

## Assets: approach for this session

- No assets exist yet.
- For portraits and backgrounds: use any free AI image generator to create placeholder PNGs now; swap the actual art file later without changing code.
- The planning session should output a **specific file size and file path convention** for each asset type so implementation is unambiguous.
- Suggested free sources to research: [Kenney.nl](https://kenney.nl) (CC0), [OpenGameArt.org](https://opengameart.org) (CC0/CC-BY), [Itch.io free assets](https://itch.io/game-assets/free).

---

## Current test state

| Suite | Status |
|-------|--------|
| Unit tests (`make test`) | 984+ passing |
| Demo tests (`make test-demo`) | 147/147 passing |
| YAML evals (`make eval`) | 19 cases |
| LLM judge (`make eval-llm-demo`) | 5/5 passing (cached) |

## Gotcha: Docker prompt reload

After any edit to `system_v1.yaml`:
1. `docker cp src/npc_engine/prompts/dialogue/system_v1.yaml npcsystem-app-1:/app/...`
2. `docker restart npcsystem-app-1`
3. Delete `.cache/demo/` and run `make demo-run` to rebuild cache

See `project-harness/SKILLS_QUEUE.md` for skill workflows.
