# FIX-SEV-05 — Lock the shared `emotion_store` / `session_store`

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** M
**Category:** concurrency · **Absorbs:** ENG-02, PY-09
**Note:** changes a public store interface with callers outside its module → per CLAUDE.md "ask before changing a public interface," coordinate before merging.

## Problem
Both stores are process-wide singletons mutated from independent async handlers with no `asyncio.Lock`, violating the strict rule. Read-modify-write across awaits drops updates.

## Current shape
- `engines/emotion/emotion_store.py:12-39`:
  ```python
  class EmotionStore:
      def __init__(self) -> None:
          self._states: dict[str, EmotionState] = {}
      def set(self, npc_id, state) -> None:
          self._states = {**self._states, npc_id: state}   # not atomic across awaits
  ```
  Singleton wired at `dependency_singletons.py:96-113`; shared by DialogueHandler, GossipHandler (`apply_event_shock`), MoodContagionEngine.
- `engines/dialogue/session_store.py:12-40`: no lock in `append_turns`, `clear_all_turns_for_npc`, `get_active_npc_ids`.
- `rg "asyncio\.Lock\(\)" src/` → 8 matches, none in these two files.

## Target shape
All mutating and reading methods acquire a per-instance `asyncio.Lock`; the lock is documented in the class docstring.

## Steps
1. Add `self._lock = asyncio.Lock()` in each `__init__`.
2. Convert `set`/`get`/`append_turns`/`clear_all_turns_for_npc`/`get_active_npc_ids` to `async def` and wrap bodies in `async with self._lock:`. (Or add an `async def mutate(npc_id, fn)` that does the read-modify-write under lock and keep getters sync if they only read an immutable snapshot — but the safest is lock both.)
3. Update all callers (DialogueHandler, GossipHandler.apply_event_shock, MoodContagionEngine, tick_scheduler consolidation path) to `await` the now-async methods.
4. Add the lock to each class docstring per the rule.

## Verification
- New async stress test: `asyncio.gather(*[store.apply_event_shock(npc_id, sev) for _ in range(N)])` → final cumulative valence/arousal equals serial application.
- Session test: two concurrent `append_turns` for the same NPC via `gather` → resulting turn count is exactly the sum.
- Existing dialogue/gossip tests still green after the await-conversion.

## Blast radius
Emotion consistency during gossip ticks, memory-vividness inputs, session turn management. Coordinate the await-signature change with SEV-06 (same scheduler path).
