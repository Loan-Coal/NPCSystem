# EXP-202 — Standing → dialogue tone (slice 1)

**Goal / rationale:** Reputation/relationship state now runs (EXP-21 wired, EXP-201 phase), but the NPC's
dialogue tone doesn't reflect how it actually *stands* with the player — so the social sim is invisible
in conversation. Surfacing Standing in the prompt makes relationships *heard*. Core throughline item.

**First slice (your scope):** Derive the player↔NPC `Standing` band from the relation scalars already in
the dialogue context and inject a single STANDING tone line into the prompt, plus one tone rule in the
dialogue system prompt YAML. **Dialogue-side only this slice** — the secret-share gate (replacing the
random `SECRET_BASE_PROBABILITY` in gossip with a Standing threshold) is slice 2; do NOT touch gossip here.

**Current state (verified):**
- `src/npc_engine/engines/relationship/standing.py:61` — `derive_standing(*, trust, fear, affection)
  -> Standing` (pure, band enum). Reuse it.
- `src/npc_engine/engines/dialogue/prompt_builder.py` — builds the dialogue prompt. The player relation
  edge (trust/fear/affection) is available in the assembled context (player_relation_edge / tier-A
  player-relation item). Verify where the scalars are reachable in this module before deriving.
- `src/npc_engine/prompts/dialogue/system_v1.yaml` — the dialogue system prompt (tone rules live here;
  `player_reputation` band guidance is around line 38). Add ONE tone rule keyed to STANDING.

**Files:**
- EDIT `src/npc_engine/engines/dialogue/prompt_builder.py` — derive `Standing` from the player relation
  scalars when present and add a concise `STANDING: <band>` context line the system prompt can react to.
  Keep functions ≤40 lines, nesting ≤3. If the scalars aren't reachable in prompt_builder, STOP and
  report (do NOT reach into `context_builder.py` — that's owned by another item).
- EDIT `src/npc_engine/prompts/dialogue/system_v1.yaml` — add one rule: tone should track STANDING
  (e.g. warmer when ALLIED/FRIENDLY, guarded when HOSTILE). Bump `PROMPT_VERSION` if the file carries one.
- NEW/EXTEND test: `tests/unit/test_prompt_builder.py` — `test_standing_line_in_prompt_when_relation_present`
  (assert the STANDING line appears for given scalars and is absent when no relation edge).

**Graph/API surface:** none — engine-internal prompt assembly. No schema, no route.

**Architecture fit:** closed-edit to `prompt_builder.py` (additive) + prompt YAML (prompts live in YAML —
compliant). No layer change. Do NOT add prompt strings in Python — the rule text goes in `system_v1.yaml`;
`prompt_builder.py` only assembles the `STANDING: <band>` data line (a value, not instruction prose).

**Test plan (RED first):** with a relation edge of high trust/affection, assert the built prompt contains
`STANDING:` with the expected band; with no edge, assert it's absent. Watch fail, implement.
Run: `pytest tests/unit/test_prompt_builder.py -q`.

**Done when:** the dialogue prompt carries a STANDING line derived via `derive_standing`, the system YAML
has a tone rule referencing it, tests pass, no gossip/secret code touched (that's slice 2).
