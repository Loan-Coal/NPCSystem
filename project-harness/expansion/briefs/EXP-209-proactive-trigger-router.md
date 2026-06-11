# EXP-209 — Unified proactive-trigger surface (slice 1)

**Goal / rationale:** `ProactiveDialogueEngine` and `IntentFormationEngine` both exist and tick, but
nothing composes their signals into a single "should this NPC initiate, and why" decision. A trigger
router makes NPC initiative coherent (memory + need + event signals → one chosen trigger). Closes the
agentic-NPC headline. Serves BUSINESS_INTENT "agentic NPCs that act on their own state."

**First slice (your scope):** A **new pure module** `trigger_router.py` that takes candidate proactive
triggers (each with a source + priority/score) and selects the highest-priority one to surface (or None).
New-file-only — do NOT edit the existing engines or the scheduler this slice (wiring is slice 2). Prove
with unit tests.

**Current state (verified):**
- `src/npc_engine/engines/proactive_dialogue/` — contains `ProactiveDialogueEngine` and
  `IntentFormationEngine` (read their module docstrings + public surface to learn the shape of an intent/
  trigger they emit; model your `ProactiveTrigger` input on that shape). They are wired in the tick
  scheduler already; you are ONLY adding the composition layer as a new file.

**Files:**
- NEW `src/npc_engine/engines/proactive_dialogue/trigger_router.py` — define a Pydantic v2
  `ProactiveTrigger` model (source: Literal/enum e.g. "memory"|"need"|"event", priority: int, payload)
  and a pure function `select_trigger(candidates: list[ProactiveTrigger]) -> ProactiveTrigger | None`
  returning the highest-priority candidate (ties broken deterministically; empty → None). Name any
  priority constants. Module docstring with `Does NOT:` + `Dependencies injected:` lines.
- NEW test: `tests/unit/test_trigger_router.py`.

**Graph/API surface:** engine-internal. No schema, no route.

**Architecture fit:** pure new-file-add (OCP); no closed-engine edit; layer = engines. No DEC needed.

**Test plan (RED first):** `test_select_trigger_picks_highest_priority` + `test_select_trigger_none_when_empty`
+ deterministic tie-break. Watch fail (function missing), implement. Run:
`pytest tests/unit/test_trigger_router.py -q`.

**Done when:** `select_trigger` composes candidate triggers deterministically; tests pass; no existing
engine edited; docstrings present; functions ≤40 lines.
