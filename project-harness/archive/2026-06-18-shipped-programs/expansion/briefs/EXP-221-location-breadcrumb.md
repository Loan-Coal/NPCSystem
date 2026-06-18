# EXP-221 — Location hierarchy breadcrumb (demo)

**Goal / rationale:** Locations now have a `PART_OF` hierarchy (ISSUE-057 fixed, edges seeded), but the
demo shows a flat location name — the nested world structure is invisible. A breadcrumb (e.g.
"Tavern ▸ Market District ▸ Kingsport") makes the world feel layered. Pure demo-side.

**First slice (your scope):** Render a PART_OF breadcrumb for the NPC's current location in the left
panel, built by walking `PART_OF` edges upward via the existing client graph-edge reader.

**Current state (verified):**
- `demo_game/ui/left_panel.py` — shows the location name but no PART_OF chain. Add a small breadcrumb
  line/section. (EXP-207 added a facial glyph here — follow the same panel-edit style; this is the only
  existing UI file you edit.)
- `demo_game/seed.py:~450` seeds `PART_OF` edges (`post_part_of`), so the data exists. The client already
  exposes a graph-edge reader (e.g. `client.get_graph_edges("PART_OF", ...)` — confirm the exact method).
  Walk upward from the current location to build the ancestor chain. Graceful no-op when a location has no
  PART_OF parent (render just the name, as today).

**Files:**
- EDIT `demo_game/ui/left_panel.py` — add a `_draw_location_breadcrumb()` helper (≤40 lines, ≤3 nesting)
  that queries PART_OF ancestors and renders "A ▸ B ▸ C"; degrade to the bare name when no parents.
- NEW/EXTEND test: `demo_game/tests/` — `test_location_breadcrumb_renders_chain` (mock edges → chain
  rendered) + `test_breadcrumb_bare_name_when_no_parent` (no PART_OF → just the name).

**Graph/API surface:** none new — uses existing graph-edge client method. Demo-side. No schema.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema. NOTE:
`left_panel.py` already has a DEC-036 size waiver — your small addition is covered; keep functions ≤40 lines.

**Test plan (RED first):** mock the PART_OF edges → assert breadcrumb chain in rendered output; no edges →
bare name. Watch fail, implement. Run: `pytest demo_game/tests/ -k 'left_panel or breadcrumb' -q`.

**Done when:** the left panel shows a PART_OF breadcrumb for nested locations and the bare name otherwise;
tests pass; no `src/` import.
