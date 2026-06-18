# EXP-30 — Context: pinned-core + ranked pool (KEYSTONE)

**Goal / rationale:** Kill the ISSUE-059 failure where a knowledge-rich NPC's dialogue silently
degrades to canned because "Tier A" (mandatory) context is unbounded and the budget enforcer hard-raises.
Serves BUSINESS_INTENT success-criterion "degradation is invisible to the player." Decided in **DEC-070**.

**First slice (this worker's scope):** Replace the tier-A overflow *raise* with a **pinned-core + ranked
pool** fill. Add a `pinned: bool` flag to the context item model. The enforcer includes ALL pinned items
unconditionally, then fills the remaining budget from the non-pinned pool **ordered by `priority`
(descending) — priority-only for v1** (relevance multiplier is a later fast-follow), dropping the lowest.
Pinned set = `world`, `emotion`, persona, the session-window turns, `active_quest`. No schema change.

**Current state (verify against code before editing):**
- `src/npc_engine/retrieval/context_builder.py:272-359` — builds `ContextItem`s, assigns `tier`
  (`tier0`/`tierA`/`tierB`/`tierC`) and `priority` (world=100, emotion=95, session=99, active_quest=89,
  memories=90, beliefs=88, …). These priorities already exist — reuse them.
- `src/npc_engine/retrieval/context_budget_enforcer.py:76-84` — raises `ContextBudgetError` /
  `TokenBudgetExceededError` when `tier_a_tokens > tier_a_budget`; `:139-144` already priority-sorts
  tier B/C. `:192-217` (`fill_to_budget`) is the second enforcement path — fix BOTH.
- Locate the `ContextItem` Pydantic model (used by `context_builder`; likely `context_protocols.py` or
  `context_builder.py`) to add the `pinned: bool = False` field.

**Files:**
- EDIT `src/npc_engine/retrieval/context_builder.py` (tag pinned items: world/emotion/persona/session/active_quest), `src/npc_engine/retrieval/context_budget_enforcer.py` (pinned-core + ranked-pool fill, both paths), and the `ContextItem` model file (add `pinned`).
- NEW `tests/unit/test_context_pinned_pool.py`.
- (No other file — this is a self-contained retrieval-layer change. Conflict set = these 3 source files.)

**Graph/API surface:** none (engine-internal; `pinned` is an in-memory model field, not graph).

**Architecture fit:** edits two closed retrieval modules + one model — allowed (it's the module's own
responsibility, not an OCP variant add). Preserves and strengthens the "never drop persona/world" invariant.
Keep the session window bounded (last-N turns) so the pinned set itself can't exceed budget.

**Test plan (write FIRST):** `tests/unit/test_context_pinned_pool.py` — build a high-knowledge fixture whose
non-pinned tier-A items exceed the budget. Assert: (1) the enforcer does NOT raise; (2) every pinned item
(world, emotion, session, active_quest) is present in the output; (3) at least one low-priority non-pinned
item was dropped; (4) total tokens ≤ `prompt_token_budget`. Run: `pytest tests/unit/test_context_pinned_pool.py -q`.

**Done when:** the over-budget fixture no longer raises, pinned core is always present, lowest-priority pool
items drop first, and the test is green. (Carry-forward: this establishes the `pinned` flag convention that
EXP-17's `never_forget` mirrors; downstream memory/knowledge items now add to the pool, not an overflowing tier.)
