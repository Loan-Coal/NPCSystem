# EXP-84 — Gossip telephone-diff view (distortion-type badges)

**Goal / rationale:** The CHAIN tab already renders each NPC's `distorted_summary` snippet and
distortion percentage, but never labels *which* distortion strategy fired (OMISSION, EXAGGERATION,
ROLE_SWAP, TIMELINE_SHIFT). Surfacing the distortion type per hop makes the "telephone game" claim
immediately legible to a buyer — the gossip mechanics are visible, not magic.

**First slice (this worker's scope):** Add a `distortion_type` badge label to each hop in
`GossipChainWidget._draw_chain`. The KNOWS_ABOUT edges already carry `distortion_type` in the
seeded data (`seed.py:580-614`). All that's needed is reading and rendering it.
No new routes, no new data fetch — the field is already in the edge dict passed to `set_chain`.

**Current state (verify against code before editing):**
- `demo_game/ui/gossip_chain.py:89-122` — `_draw_chain` renders `[NPC Name] (XX%)` header +
  truncated `distorted_summary` snippet in grey. Does NOT read or display `distortion_type`.
- Edge dict structure passed from `set_chain` (`gossip_chain.py:51-62`): receives
  `src_id`, `distortion_level`, `distorted_summary`. Confirm the caller (wherever `set_chain`
  is invoked) also passes `distortion_type` — if it does, rendering is trivial; if not, add it
  to the caller's edge dict construction.
- `grep -r "distortion_type" demo_game/` to find where the edge data is fetched and assembled.

**Files:**
- EDIT `demo_game/ui/gossip_chain.py` — add `distortion_type` label rendering in `_draw_chain`
  (one or two lines after the `pct_surf` blit at `:108`). Keep under 300 lines; keep under 40
  lines per function.
- NEW `demo_game/tests/test_gossip_chain_distortion_type.py` — unit test with a fake edge list.

**Graph/API surface:** none (demo-only, consumes existing fetched edge data).

**Architecture fit:** demo-only, zero `src/` change. Edits only `gossip_chain.py` (the CHAIN tab
widget). OCP: no new class — adding a label to existing rendering is NOT an OCP variant add.

**Test plan (write FIRST):** `demo_game/tests/test_gossip_chain_distortion_type.py` — construct a
`GossipChainWidget` with minimal pygame mock surfaces; call `set_chain` with two test edges
including `distortion_type: "EXAGGERATION"` and `"OMISSION"`; assert `draw` does NOT raise, and
that the rendered surface was written to (width > 0). For the text-content assertion, mock
`font.render` and verify it was called with a string containing `"EXAGGERATION"` or `"OMISSION"`.
Run: `pytest demo_game/tests/test_gossip_chain_distortion_type.py -q`.

**Done when:** The CHAIN tab shows a distortion-type label (e.g. `[EXAGGERATION]`) beside the
percentage for each hop, the unit test is green, and (against a seeded stack) the three-hop
northern_war_begins chain shows each hop's distortion strategy. (Carry-forward: distortion-type
labels are now surfaced; diff-highlight and multi-event support are the follow-up slice.)
