# EXP-222 — Cinematic / recording mode (demo)

**Goal / rationale:** The scripted runner is the sales artifact, but its output is dev-style logging. A
`--cinematic` mode that paces and formats the output makes a clean recording for studios. Pure demo-side.
Builds on EXP-205 (proactive ACT-11, done) so the full arc is recordable.

**First slice (your scope):** Add a `cinematic: bool` flag to the scripted `DemoRunner` and a
`--cinematic` CLI arg that switches the print/pacing helpers to a formatted, recording-friendly output
(headers per ACT, cleaner spacing). No engine/API change.

**Current state (verified):**
- `demo_game/run.py` — the scripted `DemoRunner` and its print helpers; no `--cinematic` flag exists.
  Add the flag + arg and thread it into the output helpers. (EXP-205 added ACT-11 here; build on current
  run.py. This is the only file this item edits besides its test.)

**Files:**
- EDIT `demo_game/run.py` — add `cinematic: bool = False` to `DemoRunner` (or its config), a `--cinematic`
  argparse flag, and route print/pacing through a helper that formats output when cinematic is on (plain
  when off — back-compat). Keep functions ≤40 lines (extract a formatter helper); no magic numbers
  (name any pacing/width constants).
- NEW/EXTEND test: `demo_game/tests/` — `test_cinematic_formats_output` (cinematic on → formatted markers
  present) + `test_default_output_unchanged` (cinematic off → same as today).

**Graph/API surface:** none — demo-side. No schema.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema. Only
`run.py` + the test in scope. run.py may already carry a size waiver (DEC-051 family) — keep functions small.

**Test plan (RED first):** run the scripted runner (dry/cached path) with cinematic on → assert formatted
markers; off → unchanged. Watch fail, implement. Run: `pytest demo_game/tests/ -k cinematic -q`.

**Done when:** `--cinematic` produces a formatted, recording-friendly run; default output unchanged;
tests pass; no `src/` import.
