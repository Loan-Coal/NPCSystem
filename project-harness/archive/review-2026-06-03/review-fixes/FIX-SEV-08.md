# FIX-SEV-08 — Make quest reward application atomic and possession-checked

**Severity:** HIGH · **Confidence:** Confirmed (deliver exploit) / Likely (double-grant window) · **Effort:** M
**Category:** data-integrity / correctness · **Absorbs:** ENG-04, ENG-05

## Problem
A player can collect a delivery-quest reward without surrendering the delivered item: completion is counter-based, the take-item leg is best-effort (swallowed), and rewards are granted before (and in a separate transaction from) the `rewards_applied` flag.

## Current shape — `engines/quest/quest_lifecycle_engine.py`
- Completion (`:417-426`) checks `objective_progress >= target_count` (a counter), not actual item possession.
- Rewards granted at `:514-527` (`apply_currency_transfer`/`apply_item_transfer`, idempotency-keyed).
- Deliver-collection (take item from player) at `:533-546`:
  ```python
  try:
      await apply_item_transfer(source_id=player_id, destination_id=state.reward_source_id,
                                item_id=obj.target_id, quantity=obj.target_count, ...)
  except Exception:
      _logger.warning("deliver transfer failed for item %s — item may already be gone", obj.target_id)
  ```
- `rewards_applied=True` persisted later in a separate transaction (`:548-553` → `_persist_state_and_event`).

## Target shape
Possession is verified before rewards; deliver-collection + reward grant + `rewards_applied` are one atomic transaction; a failed collection raises and rolls back the rewards.

## Steps
1. **Verify possession** before granting: query the player's inventory for `obj.target_id` ≥ `obj.target_count`; if absent, raise `QuestTransitionError` (from `utils/errors.py`) — do not complete.
2. **Single transaction**: open one tx (owned by `graph_writer.py` per SEV-04), perform deliver-collection, then reward grants, then set `rewards_applied=True`, then commit. On any failure, the tx rolls back — no partial grant.
3. **Remove the swallow**: replace `except Exception: warning` with a raise (or log-and-raise `QuestTransitionError`). "may already be gone" must not be treated as success.
4. Keep idempotency keys as defense-in-depth but stop relying on them as the sole double-spend guard; document that reliance is removed.

## Verification
- Integration test: player lacking the deliver item → `apply_rewards` raises `QuestTransitionError`, balances unchanged, quest not completed.
- Integration test: kill the session between collection and flag persist (now impossible — single tx) → retry leaves balances unchanged.
- Happy-path delivery still grants once and takes the item once.

## Blast radius
Every delivery/fetch quest; the currency/item economy a licensing studio relies on. Depends on SEV-04 for clean transaction ownership.
