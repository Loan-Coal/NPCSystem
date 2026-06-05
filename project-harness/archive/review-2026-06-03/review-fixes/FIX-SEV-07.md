# FIX-SEV-07 — Raise `TokenBudgetExceededError` instead of silently dropping Tier-A context

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** S
**Category:** prompt-quality / correctness · **Absorbs:** ENG-03

## Problem
The strict rule: `context_builder` must raise `TokenBudgetExceededError` if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET` (only Tier B is trimmable). The wired-in enforcer instead silently drops mandatory Tier-A identity/session context.

## Current shape
- `retrieval/context_builder.py:445-450` calls `fill_to_budget`.
- `retrieval/context_budget_enforcer.py:157-292` `fill_to_budget` docstring: *"When budget is tight, lower-priority items are dropped … Never raises ContextBudgetError for budget reasons."* It raises only for Tier 0 alone (`:196-202`); Tier-A items `break` out of the greedy loop (`if running + tok > prompt_token_budget: break`).
- A compliant `retrieval/token_budget_enforcer.py` `enforce_budget` exists but is **not** wired in (and also drops Tier A at `:50-54`).

## Target shape
One canonical enforcer that computes `tier0 + tierA` tokens up front and raises `TokenBudgetExceededError` if it exceeds the budget; only Tier B/C may be trimmed.

## Steps
1. Decide the canonical enforcer in DECISIONS.md (recommend folding `token_budget_enforcer` semantics into `context_budget_enforcer` and deleting the loser).
2. Before the greedy fill, compute `tier0_tokens + tier_a_tokens`; if `> prompt_token_budget`, `raise TokenBudgetExceededError(...)` (from `utils/errors.py`).
3. Keep Tier-B/C greedy trimming.
4. Re-evaluate existing tests that assert silent Tier-A drop — they encode the wrong contract; update them to expect the raise.
5. Confirm the API maps `TokenBudgetExceededError` to a sensible status (it is an internal budgeting invariant — surface as 500 with a static message per SEV-16, and log the tier sizes).

## Verification
- Unit test feeding Tier-A items over budget asserts `TokenBudgetExceededError`.
- Unit test with only Tier-B over budget asserts trimming (no raise).
- `make test` green after updating the contradicting tests.

## Blast radius
Every dialogue turn with large mandatory context. Silent context loss currently increases hallucination and is near-undiagnosable — this is also a contributor to SEV-01 symptoms.
