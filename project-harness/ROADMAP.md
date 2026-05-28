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

- [ ] **S3.0** Phase 3 prep — test consolidation + multi-demo:
  - Fix ROADMAP.md Phase 2.5 checkboxes (R2.1, R2.2 already done)
  - Add e2e scenario for `voice_descriptor` from graph (`scenario_voice_from_graph.py`)
  - Add e2e scenario for generalized `active_conditions` (`scenario_active_conditions.py`)
  - Migrate 19 YAML eval cases into pytest e2e suite (`scenario_yaml_evals.py`); keep CLI runner
  - Add `make eval-e2e` target
  - Add 2 new demo storylines: `demo_game/scenarios/run_village_crisis.py` + `run_tavern_intrigue.py`
  - Add `make demo-village` and `make demo-tavern` targets
  - Add `llm-eval-as-e2e` and `multi-demo-scenario` skills to SKILLS_QUEUE.md
  - Rewrite NEXT_SESSION.md for S3.1 handoff

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
| 2 | 2026-05-24 | P2 | S2.1–S2.5 complete. Fixed `distorted_summary` serialization bug; raised event priority 80→89; fixed 5 dead context key refs; added VOICE_DESCRIPTOR; single source of truth for context budget; 3 judge evals written | S2.6 in progress — 2/5 passing; cache bust + re-eval pending |
| 3 | 2026-05-26 | P2/P2.5 | S2.6 complete: 5/5 judge evals passing; cache rebuilt (0.5 s cached mode). Eval strategy planned: Phase 2.5 added to roadmap; ISSUE-005/006/007 logged; docs/EVAL_STRATEGY.md created; PROMPT_DESIGN.md updated with voice-in-graph + gossip hedging plan; docs/next_session.md written for R1.1. | Next: R1.1 (implement tone_judge) — see docs/next_session.md |
| 4 | 2026-05-26 | P2.5 | R1.1 complete: `tone_judge` live, 7/7 eval green, 2 voice cases added. Fixed `make eval` (Makefile PYTHON hoisted — cmd.exe grep failure on Windows). ISSUE-005 closed. | 7/7 green; R1.2 next |
| 5 | 2026-05-26 | P2.5 | R1.2 complete: `keyword_none` matcher added; 10 negative cases (`case_neg_*.yaml`); ISSUE-007 closed | 17/17 green |
| 6 | 2026-05-27 | P2.5 | R1.3 complete: `seeds/worlds/` created (tavern + village, full inner life); `requires_world` enforcement added to runner; ISSUE-008/009 closed; 13 demo cases + 3 fixed cases annotated | 17/17 green; R1.4 next |
| 7 | 2026-05-27 | P2.5 | R1.4 + R2.1 + R2.2 complete: voice_descriptor moved to graph; Rule 9 (gossip hedging) added; Rule 1 generalized; seeds consolidated under seeds/worlds/; WorldState ID="world" everywhere (DEC-021/022/023); Phase 2.5 exit criteria all met | Phase 2.5 ✅ COMPLETE |
| 8 | 2026-05-28 | P3 | S3.0: ROADMAP fixed; e2e gaps filled (voice_from_graph + active_conditions); YAML evals migrated to pytest; village + tavern demo scenarios; 2 skills added | S3.0 ✅; S3.1 next |
| 9 | | P3 | | |
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
