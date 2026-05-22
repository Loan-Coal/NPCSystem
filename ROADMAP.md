# NPCSystem — Hackathon Roadmap
## June 6, 2026 · AI / Robotics / Smart Cities Hackathon (Hong Kong)

---

## Goal

Finish top 5% at the hackathon to qualify for the HK investor program. Deliverable:
a pre-recorded 5-minute demo video + 3–5 business slides + a tight narrated pitch.

The demo is the only thing that matters. Every session this fortnight is in service of it.

## What's already built (don't redo this)

- FastAPI backend with HTTP + WebSocket API
- Neo4j knowledge graph (characters, events, locations, factions, relationships)
- 3-tier dialogue engine: Tier A (LLM + RAG + graph context), Tier B (graph templates), Tier C (canned)
- Deterministic gossip distortion engine with KNOWS_ABOUT propagation
- Event, emotion, quest, and scheduler engines
- Pygame demo: 5 NPCs across 3 locations, live graph panel, W/C keypresses
- 951 passing unit tests, eval harness with LLM judge

## Constraints

- ~20–25 working sessions over 14 days, solo + Claude Code
- No Unity. No QLoRA fine-tuning. No production hardening.
- Demo must be pre-recorded with `make demo-run` (`demo_game/run.py`) for reproducible playback
- LLM responses on the demo path must be hash-cached for instant, identical playback

---

## Phase 1 — Scenario Lock + Cache Foundation
**Days 1–2 · ~4 sessions**

> Lock the exact demo scenario first. Everything else — prompts, sidebar, polish — targets this fixed script. If the scenario moves, all downstream work moves with it.

**Goal:** docs/DEMO_SCRIPT.md is signed off; LLM responses on the demo path are cached; a single command plays the full gossip chain in under 5 seconds.

### Steps

- [x] **S1.1** Fill in `docs/DEMO_SCRIPT.md`: all `[FILL IN]` resolved — voice notes, player lines, narration, second event (market fire, beat 4 = Aldric).
- [x] **S1.2** ~~Add `OpenAIAdapter`~~ — **deferred** (cut-list item #4; stay on Ollama + cache).
- [x] **S1.3** `LLMCache` complete in `demo_game/run.py`. Added delay-skip for `--cached` mode; playback now 1.5 s.
- [x] **S1.4** End-to-end live run complete (all 4 beats). Also fixed: seed LOCATED_AT edges, pre-seeded distorted KNOWS_ABOUT for Mira/Henryk, added `market_fire` event, fixed 3 client method mismatches in run.py. Cache committed.

**Exit criteria:** `make demo-run ARGS=--cached` runs the full gossip chain with zero LLM calls and completes in < 10 seconds.

---

## Phase 2 — Prompt Engineering
**Days 3–4 · ~4 sessions**

> The engine shows the right data. The prompts make NPCs feel alive. These are separate problems. Solve the data problem first (Phase 1), then solve the voice problem.

**Goal:** Every NPC on the demo path sounds distinct, anchored to their world state, and doesn't hallucinate knowledge they shouldn't have.

### Steps

- [ ] **S2.1** Audit `prompts/` directory: list every prompt file, identify which ones fire on the demo path, document what's present vs what's missing (voice, world-state anchoring, knowledge guards).
- [ ] **S2.2** Add per-NPC `voice_descriptor` block to the system prompt. At minimum the three demo-path NPCs:
  - `mira_innkeeper` — warm, observant, hears everything from the tavern, cautious about politics
  - `captain_sorn` — clipped military diction, direct, references duty and chain of command
  - `old_henryk` — rambling, mixes rumour with memory, unreliable narrator
- [ ] **S2.3** Add "what I don't know" guard: explicit authoritative prohibition — NPC must NOT reference any event or fact unless it appears in their injected context. Zero hallucinated knowledge on the demo path.
- [ ] **S2.4** Strengthen world-state anchor: replace descriptive hint ("the world is at war") with authoritative conditional prohibition ("If epoch=war, you must acknowledge the conflict directly when asked about the north. Do not speak of peace."). See `DECISIONS.md` entry on this pattern.
- [ ] **S2.5** Write/extend LLM judge evals (`e2e/scenarios/`) for the three demo-path NPCs. One test per NPC. Criteria: mira references the war obliquely and invites gossip; captain_sorn confirms the war directly; old_henryk's account is distorted (wrong faction, wrong location, or inflated casualty count).
- [ ] **S2.6** Iterate on prompts until all 3 judge evals pass. Update the cache after each accepted prompt version.

**Exit criteria:** `make eval-llm-demo` shows 5/5 (existing 2 + 3 new) judge tests passing with cached responses.

---

## Phase 3 — Scripted Demo Flow + Gossip Sidebar
**Days 5–7 · ~5 sessions**

> The money shot: the player talks to NPC C and gets a garbled version of what NPC A saw. The sidebar makes the invisible visible — what this NPC thinks happened vs what actually happened.

**Goal:** Demo is recordable in rough form. Gossip-comparison sidebar is working. Keypresses replaced by programmatic scene execution.

### Steps

- [ ] **S3.1** Flesh out `demo_game/run.py` (already scaffolded): add remaining scenes from the signed-off `docs/DEMO_SCRIPT.md`; fill in all `[FILL IN]` dialogue lines; wire the second event and Beat 4. `make demo-run --dry-run` must print the full sequence cleanly.
- [ ] **S3.2** Replace manual W/C keypresses in the demo path: `demo_run.py` calls the engine API directly to fire events and advance the clock. The interactive keypress bindings in `demo_game/ui/game_window.py` are **preserved** — do not remove them. `demo_run.py` is a separate code path.
- [ ] **S3.3** Build gossip knowledge sidebar in `demo_game/ui/`: new `KnowledgeSidebarWidget`. Click any NPC → shows two columns side by side:
  - Left: **"What [NPC] knows"** — pull from `GET /v1/graph/edges/KNOWS_ABOUT` filtered to this character, plus any distorted event properties stored on the edge
  - Right: **"Ground truth"** — pull from `GET /v1/graph/nodes/{event_id}` (the actual event properties)
  - Diff rendering: matching text = white; distorted values = amber; fields the NPC is missing = grey + strikethrough
- [ ] **S3.4** Wire sidebar toggle: `Tab` key switches between the graph panel and the gossip sidebar. Active panel shown in a header strip at the top of the right pane.
- [ ] **S3.5** Record rough take #0: run `demo_run.py` end-to-end with narration, record the screen. This is a practice run — not the final cut. Write down everything that looks wrong.

**Exit criteria:** Rough recording exists. Gossip sidebar shows at least one distorted field in amber. Demo runs end-to-end without a crash.

---

## Phase 4 — Visual Polish
**Days 8–10 · ~4 sessions**

> Functional beats pretty, but functional + polished beats both. Reference: Caves of Qud / RimWorld aesthetic — dark bg, amber/teal text, clean grid layout.

**Goal:** The pygame window looks like a real product, not a debug tool.

### Steps

- [ ] **S4.1** Typography pass: load a TTF monospace font (Terminus or similar, include in `demo_game/assets/`). Apply to all text in the window. Base size 14px, headings 16px, status labels 12px. No more pygame default font.
- [ ] **S4.2** Colour palette: define a `PALETTE` constant in `demo_game/constants.py`. Dark navy/teal background (`#0D1B2A`), amber primary text (`#D4A017`), white secondary (`#E8E8E8`), grey inactive (`#6B7280`), red alert (`#C0392B`), green safe (`#27AE60`). Apply to all panels.
- [ ] **S4.3** NPC name labels: always-visible character name above each NPC entry in the left panel. Selected NPC gets an amber `▶` prefix. Current location shown in a header bar at the top of the left panel.
- [ ] **S4.4** Dialogue display: boxed response panel with a 1px amber border, speaker name on each turn (`[MIRA]` / `[YOU]`), degradation tier badge (small label bottom-right: `LLM` / `GRAPH` / `CANNED`), smooth text scroll.
- [ ] **S4.5** Event flash: when `demo_run.py` fires an event, show a 2-second banner at the bottom of the screen — amber text on dark red bg — matching the existing "War declared!" overlay but applied to any event.
- [ ] **S4.6** Layout audit: no overlapping panels, consistent 8px gutters everywhere, sidebar and dialogue column widths are locked and don't reflow.

**Exit criteria:** Record take #1. Watch it back. The window looks intentional. No visible layout bugs.

---

## Phase 5 — Slides, Recording, Wrap
**Days 11–14 · ~6 sessions**

> The demo is the product. The slides are the frame. The pitch is the ask.

**Goal:** Final cut video is 5:00 ± 15 seconds. Slide deck is done. Q&A answers are written. Pitch has been rehearsed twice.

### Steps

- [ ] **S5.1** Write `docs/SLIDES.md`: content outline for 5 slides. (1) Problem — NPCs are stateless puppets; the 100M-player RPG market is underserved. (2) Solution — persistent NPC memory, gossip propagation, licensable middleware API. (3) Market + competition — Inworld AI, Convai, why we're different (deterministic distortion, graph-backed knowledge, no hallucinated facts). (4) Traction — 951 passing tests, working demo, open architecture. (5) Ask — what you want from the investor program (distribution, studio intros, seed capital amount if relevant).
- [ ] **S5.2** Build the actual slide deck from `docs/SLIDES.md` in the tool of your choice (Google Slides, Keynote, Canva). Export as PDF. Commit the PDF to `docs/slides.pdf`.
- [ ] **S5.3** Final demo recording: at least 3 takes. Use OBS or similar. Resolution 1080p, 30fps. Narrate live during playback following the narration script in `docs/DEMO_SCRIPT.md`. Target take length: 4:45–5:00 (leaves 15 s buffer).
- [ ] **S5.4** Video edit: pick best take. Trim start/end. Add 2–3 captions at the gossip sidebar moment ("What Henryk *thinks* happened" / "What *actually* happened"). Export final cut.
- [ ] **S5.5** Write `docs/QA_PREP.md`: written answers to these questions:
  - How are you different from Inworld AI / Convai?
  - What prevents a big studio from building this internally?
  - How do you handle LLM hallucinations? (Answer: deterministic graph-backed distortion + knowledge guards)
  - What's your go-to-market? (Answer: SDK/API licensing to indie studios first)
  - Why now? (Answer: LLM quality crossed the threshold; context windows are large enough)
  - What's the moat? (Answer: the knowledge graph + gossip distortion model; not the LLM)
  - What are you raising and what's the use of funds?
  - What does a pilot with a studio look like?
- [ ] **S5.6** Full pitch rehearsal × 2: video + slides + pitch deck live. Time it. Adjust narration pacing if over/under.

**Exit criteria:** Final video is exported and timed at 5:00 ± 15 s. Q&A prep doc is complete. Pitch has been rehearsed twice cold.

---

## Risks and Contingencies

| Risk | Contingency |
|------|-------------|
| Gossip chain doesn't propagate reliably via engine | Seed the `captain_sorn → mira` and `mira → old_henryk` KNOWS_ABOUT edges directly in `demo_game/seed.py`; remove randomness from the demo path |
| OpenAI API key unavailable for recording | Stay on Ollama; run one live pass to warm the cache; record from cache |
| Gossip sidebar takes > 5 sessions to build | Replace with a static side-by-side text file shown in a terminal window next to pygame; same visual effect |
| Prompt engineering doesn't converge in Phase 2 | Fall back to graph-only Tier B responses for demo; they still illustrate the knowledge graph mechanic |
| Recording takes longer than expected | Record one clean unedited take; trim start/end only; skip caption edit |
| Phase 4 polish exceeds time budget | Skip smooth transitions; keep colour palette + typography only |
| Entire Phase 4 slips | Ship Phase 3 exit state; palette + font are a 1-session change if needed |

### Cut list (if behind — cut in this order)

1. Video caption edit (Phase 5.4 captions) — just trim start/end
2. Visual transitions (Phase 4.5) — keep palette + font
3. Full Phase 4 — functional > polished
4. Cloud LLM adapter (Phase 1.2) — stay on Ollama + cache
5. Gossip sidebar dynamic diff colouring — plain text is fine

### If everything breaks the night before

Fall back to the existing interactive demo (W/C keypresses + live graph). It demonstrates the mechanic. Add a terminal window showing `watch -n1 'curl /v1/graph/edges/KNOWS_ABOUT | jq'` to show knowledge spreading. Not beautiful but sufficient.

---

## Session Log

| # | Date | Phase | What was done | Exit state |
|---|------|-------|---------------|------------|
| 1 | 2026-05-22 | P1 | DEMO_SCRIPT.md filled; seed + run.py wired; gossip chain pre-seeded; market_fire added | S1.1–S1.4 ✅; `--cached` 1.5 s |
| 2 | | P2 | | |
| 3 | | P2 | | |
| 4 | | P2 | | |
| 5 | | P2 | | |
| 6 | | P2/P3 | | |
| 7 | | P3 | | |
| 8 | | P3 | | |
| 9 | | P3 | | |
| 10 | | P3/P4 | | |
| 11 | | P4 | | |
| 12 | | P4 | | |
| 13 | | P4/P5 | | |
| 14 | | P5 | | |
| 15 | | P5 | | |
| 16 | | P5 | | |
| 17 | | P5 | | |
| 18 | | P5 | | |
| 19 | | P5 | Buffer / re-record | |
| 20 | | P5 | Buffer / Q&A prep | |
