# EXP-223 — Richer world: more NPCs / locations (demo)

**Goal / rationale:** The demo world is just 5 NPCs / 3 locations — too thin to feel like a game. Adding
NPCs and locations (within the existing factions) makes the world feel populated. Pure demo-side, via the
idempotent stable-id seed contract.

**First slice (your scope):** Add a handful of new NPCs (and 1–2 locations) to the demo seed, using the
existing seed pattern (stable client-supplied ids, idempotent). **Stay within the existing 3 factions** —
do NOT add new factions this slice (the win/lose checker assumes 3 — see constraint below).

**Current state (verified):**
- `demo_game/seed.py:~478-500` — seeds exactly the 5 original NPCs (`_NPCS` list). Extend it with new
  NPCs using the same create pattern + stable ids; assign them to existing factions/locations. Optionally
  add 1–2 locations (with `PART_OF` parents, reusing `post_part_of`).
- `demo_game/constants.py` — any NPC/location id or display-name constants live here; add the new ids.
- **CONSTRAINT:** `demo_game/game_end_checker.py` may assume exactly 3 factions for win/lose. VERIFY this
  before changing factions. This slice adds NPCs to EXISTING factions only (no new factions), so the
  checker should be unaffected — but read it to confirm, and if adding NPCs breaks a count assumption,
  STOP and report rather than editing the checker (that's a separate concern).

**Files:**
- EDIT `demo_game/seed.py` — append new NPCs (+ optional locations) to the seed lists, stable ids,
  idempotent (running `make demo-seed` twice stays duplicate-free).
- EDIT `demo_game/constants.py` — new id/display-name constants (named; no inline string ids).
- NEW/EXTEND test: `demo_game/tests/` — `test_seed_includes_new_npcs` (the new NPCs are in the seed set)
  + an idempotency assertion if the existing seed tests have one.

**Graph/API surface:** none new — uses existing create endpoints via the seed client. No schema.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema. Seed
contract is idempotent + stable-id (KE-6). Do NOT add a parallel seeding path; do NOT edit
`game_end_checker.py` (verify-only).

**Test plan (RED first):** assert the seed set now contains the new NPC ids (fails before they're added);
implement. Run: `pytest demo_game/tests/ -k seed -q`.

**Done when:** the demo seed has more NPCs (and optionally locations) within existing factions, idempotent
+ stable-id; tests pass; `game_end_checker.py` faction assumption confirmed intact; no `src/` import.
