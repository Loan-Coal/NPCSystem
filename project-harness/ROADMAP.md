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

- [x] **S2.1** Audit `prompts/` directory: list every prompt file, identify which ones fire on the demo path, document what's present vs what's missing (voice, world-state anchoring, knowledge guards). **Findings:** 5 dead context key refs in system_v1.yaml; no per-NPC voice; `distorted_summary` edge property was being overridden by raw event node facts in context serialization; PROMPT_TOKEN_BUDGET was hardcoded at 8000 while Ollama context was 4096.
- [x] **S2.2** Add per-NPC `voice_descriptor` block to the system prompt. At minimum the three demo-path NPCs:
  - `mira_innkeeper` — warm, observant, hears everything from the tavern, cautious about politics
  - `captain_sorn` — clipped military diction, direct, references duty and chain of command
  - `old_henryk` — rambling, mixes rumour with memory, unreliable narrator
  **Done:** `src/npc_engine/prompts/dialogue/npc_voices.yaml` created; `prompt_builder.py` updated to load and inject `VOICE_DESCRIPTOR` line; Rule 8 added to `system_v1.yaml`; PROMPT_VERSION bumped to `stage_b_v2.0`. Added "tone only" clarification to prevent voice overriding knowledge content.
- [x] **S2.3** Add "what I don't know" guard: explicit authoritative prohibition — NPC must NOT reference any event or fact unless it appears in their injected context. Zero hallucinated knowledge on the demo path. **Done:** Rule 5 in `system_v1.yaml` rewritten with explicit prohibition; also fixed all 5 dead context key refs (Rules 2–7 were effectively no-ops).
- [x] **S2.4** Strengthen world-state anchor: replace descriptive hint ("the world is at war") with authoritative conditional prohibition ("If epoch=war, you must acknowledge the conflict directly when asked about the north. Do not speak of peace."). **Done:** Rule 1 `epoch=war` block extended with `ADDITIONAL CONSTRAINT` paragraph in `system_v1.yaml`.
- [x] **S2.5** Write/extend LLM judge evals (`e2e/scenarios/`) for the three demo-path NPCs. One test per NPC. **Done:** 3 judge tests added to `e2e/scenarios/scenario_demo_game_judge.py`: `test_captain_sorn_direct_war_confirmation`, `test_mira_innkeeper_oblique_gossip`, `test_old_henryk_distorted_account`. All use `world` world state node (updated from `ws_main` in pre-Phase 3 cleanup, DEC-022).
- [x] **S2.6** Iterate on prompts until all 5 judge evals pass. Update the cache after each accepted prompt version. **Done (2026-05-26):** 5/5 passing. Cache rebuilt — 4 dialogue beats cached, `--cached` mode runs in 0.5 s. NPC responses confirmed quality: Sorn direct/factual, Mira oblique/warm, Henryk rambling with all distorted specifics (northmen/king's pass/thousands dead).

**Additional work outside original S2.x numbering:**
- Fixed `distorted_summary` serialization bug in `src/npc_engine/retrieval/subgraph_retriever.py`: added `_flatten_event_row()` helper that merges KNOWS_ABOUT edge properties (`knowledge_state`, `distorted_summary`) into the event dict and suppresses raw narrative fields (`summary`) when the NPC has a distorted account. Without this fix the LLM saw two conflicting accounts and defaulted to the clean factual one.
- Raised event `ContextItem` priority from `80 - index` to `89 - index` so events rank above traits (83), group memberships (82), and believed rumors (81). Socially-rich NPCs like `old_henryk` were having their KNOWS_ABOUT events truncated by the token budget.
- Single source of truth for context budget: added `OLLAMA_CONTEXT_LENGTH` to `config.py` with a `model_validator` that derives `PROMPT_TOKEN_BUDGET = OLLAMA_CONTEXT_LENGTH - 1200` when not explicitly overridden. Set to 4096 (pure VRAM limit on RTX 5070 Ti Laptop for qwen2.5:14b Q4_K_M). Updated `.env.example`.
- 5 unit tests for `_flatten_event_row` added in `tests/unit/test_subgraph_retriever.py`.

**Exit criteria:** `make eval-llm-demo` shows 5/5 (existing 2 + 3 new) judge tests passing with cached responses.

---

## Phase 2.5 — Eval + Prompt Breadth
**Days 5–7 (parallel with / between Phase 2 tail and Phase 3) · ~3–4 sessions**

> The current eval suite (5 YAML cases + 5 LLM judge tests) only validates the hardcoded demo path. This phase builds the eval infrastructure and prompt improvements needed to trust the system on arbitrary conversations from graph context — not just known scenarios.

**Goal:** `tone_judge` is implemented and active; negative test cases exist; `seeds/world/` has 2+ eval worlds; NPC voice is a graph property (not a YAML lookup); gossip hedging rule is in the system prompt.

### Steps

- [x] **S2.6** *(carry-over)* Iterate on prompts until all 5 judge evals pass. Update cache after each accepted prompt version.
  - Exit: `make eval-llm-demo` → 5/5 green. ✅ Done (2026-05-26)

- [x] **R1.1** Implement `tone_judge` matcher in `evals/matchers.py` (lines 46–49). Replace stub with real Ollama call using a small fast model. Add `judge_prompt` field to eval case YAML. See ISSUE-005.

- [x] **R1.2** Add 10+ negative eval cases in `evals/cases/` covering: knowledge hallucination, reputation gates, location-scoping, gossip hedging regex. See ISSUE-007.

- [x] **R1.3** Create `seeds/worlds/` with 3 eval world seed scripts:
  - `seeds/worlds/seed_tavern_world.py` — innkeeper, wanderer, merchant; events: theft, market fire, travelling performer (not war)
  - `seeds/worlds/seed_village_world.py` — healer, elder, farmer, guard, fence; events: crop blight, bandit raid, missing child
  - `seeds/worlds/seed_demo_world.py` — moved from `demo_game/seed.py` (DEC-021)
  - Each script wipes the graph and re-seeds via API. Eval cases declare `requires_world:` field.

- [x] **R1.4** Move NPC voice to Character node. Add `voice_descriptor` field to `character.yaml`. Pull in `get_character_with_relations()`. Read from serialized context in `prompt_builder.py`. Remove `_get_voice()` and `npc_voices.yaml` runtime load. Update all seed scripts. See ISSUE-006.

- [x] **R2.1** Add gossip hedging rule to `system_v1.yaml` (Rule 9): NPC with `knowledge_state=rumor` or `distortion_level>30` MUST use epistemic markers ("I heard...", "Word is..."). Verify with hedging regex cases from R1.2.

- [x] **R2.2** Generalize world-state Rule 1 in `system_v1.yaml`: replace hardcoded `epoch=war` block with a general pattern that applies to any active condition from context. Removes demo-specificity from the system prompt.

**Exit criteria:** ✅ ALL MET — `tone_judge` active; 10+ negative cases pass; `seeds/worlds/` has 3 eval worlds; `voice_descriptor` pulled from graph; gossip hedging regex test passes; world-state Rule 1 generalized.

**Phase 2.5 COMPLETE** (2026-05-27)

---

## Phase 3 — Scripted Demo Flow + Gossip Sidebar
**Days 5–7 · ~5 sessions**

> The money shot: the player talks to NPC C and gets a garbled version of what NPC A saw. The sidebar makes the invisible visible — what this NPC thinks happened vs what actually happened.

**Goal:** Demo is recordable in rough form. Gossip-comparison sidebar is working. Keypresses replaced by programmatic scene execution.

### Steps

- [x] **S3.0** Phase 3 prep — test consolidation + multi-demo:
  - Fix ROADMAP.md Phase 2.5 checkboxes (R2.1, R2.2 already done)
  - Add e2e scenario for `voice_descriptor` from graph (`scenario_voice_from_graph.py`)
  - Add e2e scenario for generalized `active_conditions` (`scenario_active_conditions.py`)
  - Migrate 19 YAML eval cases into pytest e2e suite (`scenario_yaml_evals.py`); keep CLI runner
  - Add `make eval-e2e` target
  - Add 2 new demo storylines: `demo_game/scenarios/run_village_crisis.py` + `run_tavern_intrigue.py`
  - Add `make demo-village` and `make demo-tavern` targets
  - Add `llm-eval-as-e2e` and `multi-demo-scenario` skills to SKILLS_QUEUE.md
  - Rewrite NEXT_SESSION.md for S3.1 handoff

- [x] **S3.1** Demo game flesh-out (expanded scope):
  - Verified `run.py` already complete per DEMO_SCRIPT; added Beat 5 (Lira — same fire, opportunistic lens)
  - Seed isolation: `seeds/worlds/seed_demo_world.py` → `demo_game/seed.py`; Makefile updated; Lira KNOWS_ABOUT market_fire edge added
  - UI fix: `ScrollableLog` word-wrap (`_wrap_text`); pixel-based scroll; no more horizontal text clipping
  - UI fix: per-NPC dialogue logs (`dict[npc_id, ScrollableLog]`); "Talking to [NPC]" header strip; switching NPC preserves history
  - 16 new widget tests + 1 new seed test; 125/125 demo tests green
  - Skills added: `per-npc-dialogue-log`, `pygame-word-wrap`; DEC-024 logged
- [x] **S3.2** Replace manual W/C keypresses in the demo path: `demo_run.py` calls the engine API directly to fire events and advance the clock. The interactive keypress bindings in `demo_game/ui/game_window.py` are **preserved** — do not remove them. `demo_run.py` is a separate code path. **Done: run.py already executes all scenes programmatically via DialogueBeat/EventFire/ClockTickScene — no keypresses remain on the demo path.**
- [x] **S3.3** Build gossip knowledge sidebar in `demo_game/ui/`: new `KnowledgeSidebarWidget`. Click any NPC → shows two columns side by side:
  - Left: **"What [NPC] knows"** — pull from `GET /v1/graph/edges/KNOWS_ABOUT` filtered to this character, plus any distorted event properties stored on the edge
  - Right: **"Ground truth"** — pull from `GET /v1/graph/nodes/{event_id}` (the actual event properties)
  - Diff rendering: matching text = white; distorted values = amber; fields the NPC is missing = grey + strikethrough
- [x] **S3.4** Wire sidebar toggle: `Tab` key switches between the graph panel and the gossip sidebar. Active panel shown in a header strip at the top of the right pane.
- [x] **S3.5a** Emotion polling: add `get_npc_emotion(npc_id)` to `client.py` (calls `GET /v1/npc/{npc_id}/emotion`). Add `EmotionPoller` background thread (same pattern as `WorldStatePoller`, polls every 5 s for active NPC). Update `DegradationBadge` to show live mood label with colour coding: green (valence > 0.3), amber (neutral), red (valence < −0.3). Files: `demo_game/client.py`, `demo_game/emotion_poller.py` (new), `demo_game/ui/game_window.py`, `demo_game/ui/widgets.py`. **Done 2026-05-28. 175/175 demo tests green.**
- [x] **S3.5b** Faction badge in NPC list: add a coloured 8px dot at the left edge of each NPC list row. `FACTION_COLOURS` + `NPC_FACTIONS` added to `constants.py`. `NpcListWidget.draw()` updated. DEC-028 logged. Files: `demo_game/constants.py`, `demo_game/ui/widgets.py`. **Done 2026-05-28.**
- [x] **S3.6** Record rough take #0: run `demo_run.py` end-to-end with narration, record the screen. This is a practice run — not the final cut. Write down everything that looks wrong.

**Exit criteria:** Rough recording exists. Gossip sidebar shows at least one distorted field in amber. Demo runs end-to-end without a crash.

---

## Phase 4 — Visual Polish
**Days 8–11 · ~7.25 sessions**

> Functional beats pretty, but functional + polished beats both. Reference: Caves of Qud / RimWorld aesthetic — dark bg, amber/teal text, clean grid layout. Each step is independently shippable — cut from the bottom if behind schedule.

**Goal:** The pygame window looks like a real product, not a debug tool. The engine's full breadth (quests, economy, emotion, factions) is visible to an audience.

### Steps

> **Plan note (2026-05-28):** S4.6 reordered to execute FIRST — all polish steps build on the flexible layout foundation. Right panel extended to 3-tab enum cycle (GRAPH → KNOWLEDGE → PLAYER STATUS). game_window.py split into left_panel.py + right_panel.py + thin GameWindow (DEC-024 trigger met at 472 lines). See DEC-030, DEC-031, DEC-032.

- [x] **S4.6** *(REORDERED FIRST)* Layout audit + `--size` CLI arg + game_window.py split: **Done 2026-05-28.** Split `game_window.py` (472 lines) → `left_panel.py` (226 lines) + `right_panel.py` (125 lines) + thin `GameWindow` coordinator (355 lines). `--size WxH` arg added to `__main__.py`. Layout attrs derived from `window_w, window_h` in `__init__`. 6 new layout tests; 181/181 demo tests green.
- [x] **S4.0** Quest engine — Tier 1 + 3-panel tab architecture: **Done 2026-05-29.** `RightPanel` enum (GRAPH → KNOWLEDGE → PLAYER STATUS) replaces `_show_sidebar: bool`. `QuestPanelWidget` added in `quest_panel.py`. `_seed_quests` added to `seed.py` (non-fatal). `post_quest_generate` + `get_quest` added to `client.py`. Quest loaded at GameWindow startup from `.cache/demo/aldric_quest.json`. 206/206 tests green.
- [x] **S4.1** Typography pass: JetBrains Mono Regular TTF committed to `demo_game/assets/fonts/`. `FontLoader` singleton (class-level cache, `FileNotFoundError` fallback). All 4 `pygame.font.SysFont` calls in `game_window.py.__init__` replaced with `FontLoader.get(N)`. 4 new tests (cache hit, fallback, size isolation, fallback uses `None` name). **Done 2026-05-29. 210/210 tests green.**
- [x] **S4.2** Colour palette + location bar gradient: `PALETTE` dict added to `constants.py` (8 keys, DEC-035). `_CLR_*` aliases in `widgets.py`, `quest_panel.py`, `left_panel.py`, `game_window.py` now reference `PALETTE`. Location bar extended 36px → 80px with cached per-location gradient surface. 4 new `test_constants.py` tests. **Done 2026-05-29. 214/214 tests green.**
- [x] **S4.3** NPC labels + portrait: amber `▶` prefix on selected NPC row in `NpcListWidget`. 96px portrait zone inserted between NPC list and dialogue header; PNG load with geometric fallback (faction-coloured circle + first initial). `demo_game/assets/portraits/` directory created. 2 new `▶` tests. **Done 2026-05-29. 216/216 tests green.**
- [x] **S4.4** Dialogue display + preset buttons + trade price (Iteration 1): 1px amber border on `ScrollableLog`, `[LABEL]:` speaker prefix format, `ActionBarWidget` (3 preset buttons in `action_bar.py`), trade price overlay in `left_panel.py`, `get_item_price` in `client.py`, `InputBox.set_text()`. 10 new tests (6 action bar, 2 client, 2 widget). ISSUE-046 logged for `/v1/economy/price` endpoint verification. **Done 2026-05-29. 226/226 tests green.**
- [x] **S4.5** Event flash banner: `WorldStatePoller` extended with `_baseline_polled` flag, `pop_new_conditions()`. `EventBanner` widget added to `widgets.py` (amber text on `PALETTE["red"]`, 36px strip). `LeftPanelRenderer.show_event_banner()` added. Banner wired into `_render()` in `game_window.py`. 8 new tests (4 banner, 4 poller). **Done 2026-05-29. 234/234 tests green.**
- [ ] **S4.6** Layout audit + `--size` CLI arg:
  - No overlapping panels, consistent 8px gutters, column widths locked.
  - Add `--size` arg to `demo_game/__main__.py` (e.g. `--size 1920x1080`). Derive all layout constants from `WINDOW_W, WINDOW_H` passed into `GameWindow.__init__` at startup. No `pygame.RESIZABLE`.
- [x] **S4.7** Trade engine — Iteration 2 (full result overlay): `post_trade()` added to `client.py`. Two-click state machine (`idle → offered_low → accepted`) in `game_window.py` + `left_panel.py`. Click 1 offers 80% of fair price; click 2 offers 100%. `_draw_trade_overlay()` renders 3-line result card (item, offered/fair, ACCEPTED/REJECTED with colour). State resets on NPC/location change. 2 new client tests. **Done 2026-05-29. 236/236 tests green.**
- [x] **S4.8** Quest engine — Tier 2 (lifecycle: offer + accept): `_quest_headers()` (SHA-256 idempotency), `post_quest_offer()`, `post_quest_accept()` added to `client.py`. `QuestPanelWidget` extended with `set_accept_callback()`, `set_status()`, `[ACCEPT QUEST]` button (amber border, green label, shown when status == "offered"). `RightPanelRenderer` gains `show_quest_panel`, `handle_quest_click()`, `set_quest_status()`, `set_quest_accept_callback()`. `game_window.py` saves `_quest_id`, auto-offers on startup if status=="available", wires accept callback. 11 new tests. **Done 2026-05-29. 247/247 tests green.**
- [x] **S4.9** Gossip chain visualization: `GossipChainWidget` in `gossip_chain.py` — vertical chain display with `[NPC]  (X%)` header + distorted summary snippet per node, colour-coded (white/amber/red). `CHAIN` added as 4th `RightPanel` enum value; tab now cycles GRAPH → KNOWLEDGE → PLAYER STATUS → CHAIN → GRAPH. Chain pre-fetched at startup via `get_graph_edges("KNOWS_ABOUT", dst_id="northern_war_begins")`. 4 broken right-panel tests updated. 6 new gossip chain tests. **Done 2026-05-29. 254/254 tests green.**

**Exit criteria:** Record take #1. Watch it back. The window looks intentional. No visible layout bugs. Trade price displays. Quest card appears after Beat 4.

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
| 2 | 2026-05-24 | P2 | S2.1–S2.5 complete. Fixed `distorted_summary` serialization bug; raised event priority 80→89; fixed 5 dead context key refs; added VOICE_DESCRIPTOR; single source of truth for context budget; 3 judge evals written | S2.6 in progress — 2/5 passing; cache bust + re-eval pending |
| 3 | 2026-05-26 | P2/P2.5 | S2.6 complete: 5/5 judge evals passing; cache rebuilt (0.5 s cached mode). Eval strategy planned: Phase 2.5 added to roadmap; ISSUE-005/006/007 logged; docs/EVAL_STRATEGY.md created; PROMPT_DESIGN.md updated with voice-in-graph + gossip hedging plan; docs/next_session.md written for R1.1. | Next: R1.1 (implement tone_judge) — see docs/next_session.md |
| 4 | 2026-05-26 | P2.5 | R1.1 complete: `tone_judge` live, 7/7 eval green, 2 voice cases added. Fixed `make eval` (Makefile PYTHON hoisted — cmd.exe grep failure on Windows). ISSUE-005 closed. | 7/7 green; R1.2 next |
| 5 | 2026-05-26 | P2.5 | R1.2 complete: `keyword_none` matcher added; 10 negative cases (`case_neg_*.yaml`); ISSUE-007 closed | 17/17 green |
| 6 | 2026-05-27 | P2.5 | R1.3 complete: `seeds/worlds/` created (tavern + village, full inner life); `requires_world` enforcement added to runner; ISSUE-008/009 closed; 13 demo cases + 3 fixed cases annotated | 17/17 green; R1.4 next |
| 7 | 2026-05-27 | P2.5 | R1.4 + R2.1 + R2.2 complete: voice_descriptor moved to graph; Rule 9 (gossip hedging) added; Rule 1 generalized; seeds consolidated under seeds/worlds/; WorldState ID="world" everywhere (DEC-021/022/023); Phase 2.5 exit criteria all met | Phase 2.5 ✅ COMPLETE |
| 8 | 2026-05-28 | P3 | S3.0: ROADMAP fixed; e2e gaps filled (voice_from_graph + active_conditions); YAML evals migrated to pytest; village + tavern demo scenarios; 2 skills added | S3.0 ✅; S3.1 next |
| 9 | 2026-05-28 | P3 | S3.1: Beat 5 (Lira), seed isolation (demo_game/seed.py), UI word-wrap, per-NPC dialogue logs | S3.1 ✅; S3.2 next |
| 10 | 2026-05-28 | P3 | S3.3: KnowledgeSidebarWidget + fetcher + background fetch wired in game_window; 14 new tests; DEC-026 + pygame-diff-rendering skill | S3.3 ✅; S3.4 next |
| 11 | 2026-05-28 | P3 | S3.4: Tab toggle, DEC-027 (exclusive scroll routing), ISSUE-045 (line-count), pygame-tab-panel-toggle skill | S3.4 ✅; S3.5 next |
| 12 | 2026-05-28 | P3 | S3.5a + S3.5b: EmotionPoller, faction badge, DEC-028/029; 175/175 tests green | S3.5 ✅; S3.2 marked ✅ (already done) |
| 13 | 2026-05-28 | P4 | Phase 4 planning: S4.6 reordered first, 3-tab RightPanel enum, game_window split plan, DEC-030/031/032/033; 3 skills queued | S4.6 next (layout foundation) |
| 14 | 2026-05-28 | P4 | S4.6: game_window split (left_panel.py + right_panel.py + thin GameWindow), --size CLI arg, layout attrs as instance attrs, 6 new layout tests; 181/181 green | S4.6 ✅; S4.0 next |
| 15 | 2026-05-29 | P4 | S4.0: RightPanel enum (3-tab), QuestPanelWidget, post_quest_generate/get_quest, _seed_quests (non-fatal), quest cache load at startup; 206/206 green | S4.0 ✅; S4.1 next |
| 16 | 2026-05-29 | P4 | S4.1: JetBrains Mono TTF asset, FontLoader singleton w/ fallback, replaced 4 SysFont calls in game_window.py, 4 new font tests; 210/210 green | S4.1 ✅; S4.2 next |
| 17 | 2026-05-29 | P4 | S4.2: PALETTE dict in constants.py, _CLR_* aliases in 4 UI files, location bar 36→80px with cached gradient, DEC-035, 4 new constant tests; 214/214 green | S4.2 ✅; S4.3 next |
| 18 | 2026-05-29 | P4 | S4.3: ▶ amber prefix on active NPC row, 96px portrait zone (PNG + geometric fallback), portraits/ dir; 216/216 green | S4.3 ✅; S4.4 next |
| 19 | | P4 | | |
| 13 | | P4/P5 | | |
| 14 | | P5 | | |
| 15 | | P5 | | |
| 16 | | P5 | | |
| 17 | | P5 | | |
| 18 | | P5 | | |
| 19 | | P5 | Buffer / re-record | |
| 20 | | P5 | Buffer / Q&A prep | |
