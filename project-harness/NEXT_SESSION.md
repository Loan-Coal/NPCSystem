# Next Session Handoff

**Branch:** `munich-demo`
**Last completed:** S4.9 ✅ — GossipChainWidget + CHAIN tab. 254/254 tests green.
**Phase 4 is COMPLETE.**
**Next task:** Phase 5 — recording prep + slides

---

## Phase 4 exit criteria — status

- [x] Window looks intentional (Caves of Qud aesthetic — dark navy, amber text)
- [x] Trade price displays ([Trade] preset → 2-click price negotiation)
- [x] Quest card appears in PLAYER STATUS tab ([ACCEPT QUEST] button)
- [x] Gossip chain in CHAIN tab (distortion % colour-coded)
- [x] No layout bugs reported
- [ ] **Record take #1** ← next action

---

## Pre-recording checklist

Run these before hitting record:

1. **Verify ISSUE-046:** Start engine + `make demo-seed`, then:
   ```
   curl "http://localhost:8000/v1/economy/price?item_type=spice&character_id=aldric_merchant"
   ```
   If 404 or wrong schema → update `get_item_price()` and `_handle_trade_click()` to match.

2. **Warm cache:** `make demo-run` (live run, no `--cached`) to populate LLM cache for all 4 beats.

3. **Verify cached run:** `make demo-run ARGS=--cached` — must complete in < 10 s with zero LLM calls.

4. **Window size:** Run at `1280x720` (default). If recording at 1080p, use `--size 1920x1080`.

5. **Manual smoke test** — open `make demo` and verify:
   - Tab cycles through all 4 tabs
   - [Trade] button → price overlay after first click, result overlay after second
   - PLAYER STATUS tab shows quest card and [ACCEPT QUEST] button
   - CHAIN tab shows Sorn → Mira → Henryk chain

---

## Phase 5 sequence

| Step | Spec | Status |
|---|---|---|
| S5.1 | Write `docs/SLIDES.md` — 5-slide content outline | pending |
| S5.2 | Build slide deck → export `docs/slides.pdf` | pending |
| S5.3 | Record final demo (3 takes, 1080p, narrated) | pending |
| S5.4 | Video edit: pick best take, add 2–3 captions | pending |
| S5.5 | Write `docs/QA_PREP.md` — written Q&A answers | pending |
| S5.6 | Pitch rehearsal × 2 (video + slides + pitch) | pending |

**S5.1 — slide content (5 slides):**
1. **Problem** — NPCs are stateless puppets; 100M-player RPG market underserved
2. **Solution** — persistent NPC memory, gossip propagation, licensable middleware API
3. **Market + competition** — Inworld AI, Convai; why different (deterministic distortion, graph-backed knowledge, no hallucinated facts)
4. **Traction** — 254 passing demo tests, working live demo, open architecture
5. **Ask** — distribution/studio intros/seed capital via the investor program

---

## What changed this session (S4.9)

### New files
- `demo_game/ui/gossip_chain.py` — `GossipChainWidget` (vertical chain rendering, distortion colours)
- `demo_game/tests/test_gossip_chain.py` — 6 tests (init, set_chain sorting, empty/data draw)

### Modified files
- `demo_game/ui/right_panel.py` — `CHAIN` enum value; `GossipChainWidget` instance; `set_chain_data()`; CHAIN draw branch; docstring updated; 4 tabs now
- `demo_game/ui/game_window.py` — chain pre-fetch at startup via `get_graph_edges("KNOWS_ABOUT", dst_id="northern_war_begins")`
- `demo_game/tests/test_right_panel.py` — 4 tests updated for 4-tab enum (count, values, cycle-back after 4, show_sidebar cycle)
- `project-harness/ROADMAP.md` — S4.9 ✅
- `project-harness/NEXT_SESSION.md` — this file

### Test counts
- Before S4.9: 247 tests
- +6 test_gossip_chain
- +1 test_right_panel (new cycle_tab_player_status_to_chain)
= 254 total ✅

---

## Full Phase 4 — COMPLETE

| Step | Status |
|---|---|
| S4.6 Layout foundation + game_window split | ✅ |
| S4.0 Quest Tier 1 + 3-panel tab | ✅ |
| S4.1 JetBrains Mono + FontLoader | ✅ |
| S4.2 PALETTE + gradient | ✅ |
| S4.3 NPC ▶ prefix + portrait zone | ✅ |
| S4.4 Dialogue border + preset buttons + trade price | ✅ |
| S4.5 EventBanner + WorldStatePoller diff | ✅ |
| S4.7 Trade Iteration 2 | ✅ |
| S4.8 Quest Tier 2 (offer + accept) | ✅ |
| S4.9 Gossip chain visualization | ✅ |
