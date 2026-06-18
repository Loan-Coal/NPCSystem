# EXP-204 — Need/mood fed into dialogue context (slice 1: needs)

**Goal / rationale:** NPC simulation computes needs every tick, but the dialogue context builder never
surfaces them — so NPCs never reference their own state ("I'm exhausted", "I'm starving"). Surfacing the
top unmet need makes NPCs feel alive. Serves the BUSINESS_INTENT "living NPCs" ambition; part of the
"simulation is invisible to dialogue" throughline.

**First slice (your scope):** Add the NPC's top unmet **need** as one optional context line (Tier B pool
item) in the dialogue context builder. **Needs only this slice** (mood via EmotionStore is slice 2, per
DEC-099 which makes EmotionStore the canonical emotion source). Optional/trim-first so it never breaks
the token budget.

**Current state (verified):**
- `src/npc_engine/graph/need_queries.py:18` — `async get_needs_for_character(session, character_id)
  -> list[dict[str, Any]]` already exists (returns Need nodes).
- `src/npc_engine/retrieval/context_builder.py` — builds the dialogue context; has **no** call to
  `get_needs_for_character`. Find where Tier B / optional pool items are assembled and add the need line
  there (it must be trimmable — Tier B is always optional per CLAUDE.md prompt-budget rule).

**Files:**
- EDIT `src/npc_engine/retrieval/context_builder.py` — fetch needs for the NPC, pick the highest-urgency
  unmet need (name a threshold constant if you gate "unmet"), format a short context line, add it as an
  optional Tier B item. Keep the added function ≤40 lines, nesting ≤3, no raw dict crossing a boundary
  (use a small typed model if you pass structured data).
- NEW/EXTEND test: `tests/unit/test_context_builder.py` —
  `test_top_unmet_need_appears_in_context`.

**Graph/API surface:** retrieval-internal. No schema, no route. Reuses `need_queries`.

**Architecture fit:** closed-edit to `context_builder.py` (additive). Layer: retrieval → graph (allowed).
`retrieval/` must not call the LLM or open transactions — only read via `need_queries`.

**Test plan (RED first):** with `get_needs_for_character` mocked to return an urgent need, assert the
built context contains the need line; with no needs, assert it's absent and nothing else changes. Watch
fail, implement. Run: `pytest tests/unit/test_context_builder.py -q`.

**Done when:** an NPC with an unmet need gets a need line in its dialogue context (trimmable Tier B);
test passes; budget rule respected; no schema change.
