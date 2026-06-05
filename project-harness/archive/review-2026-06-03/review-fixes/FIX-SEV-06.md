# FIX-SEV-06 — Cap memory-consolidation fan-out with a Semaphore

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** M
**Category:** concurrency / performance · **Absorbs:** PY-10
**Coordinate with:** SEV-05 (same scheduler path / store await changes).

## Problem
The consolidation tick iterates all active NPCs with sequential `await self.consolidate(...)` (each an LLM call) while holding the scheduler lock, with no `Semaphore(MAX_CONCURRENT_TICKS)` — violating the strict semaphore rule and stalling the server.

## Current shape
- `engines/memory_consolidation/memory_consolidation_engine.py:181-186`:
  ```python
  for npc_id in npc_ids:
      memory_id = await self.consolidate(session, npc_id=npc_id, game_time=game_time)
  ```
- Driven by `scheduler/tick_scheduler.py:546-548` under `self._lock` (`:297`).

## Target shape
Consolidations run concurrently, bounded by `asyncio.Semaphore(settings.MAX_CONCURRENT_TICKS)`.

## Steps
1. In the consolidation loop, build a semaphore from config:
   ```python
   sem = asyncio.Semaphore(self._settings.MAX_CONCURRENT_TICKS)
   async def _one(npc_id: str) -> str | None:
       async with sem:
           return await self.consolidate(session, npc_id=npc_id, game_time=game_time)
   results = await asyncio.gather(*(_one(n) for n in npc_ids))
   consolidated = [n for n, mid in zip(npc_ids, results) if mid is not None]
   ```
2. Confirm each `consolidate` uses an independent transaction or a session-safe pattern (Neo4j sessions are not concurrency-safe — if all share one `session`, give each task its own session from the driver, or keep the writes serialized while parallelizing only the LLM calls). Decide and document in DECISIONS.
3. Ensure the scheduler lock is not held longer than necessary — the gather should run inside the lock only if state consistency requires it; otherwise release before the LLM-bound work.

## Verification
- Test: mock `consolidate` with a 10ms delay; 40 NPCs → wall-clock ≈ `(40 / MAX_CONCURRENT_TICKS + 1) * 10ms`, not `400ms`.
- No "session in use" / concurrency errors against the real driver under an integration test with several active NPCs.

## Blast radius
Server liveness during consolidation ticks; any client awaiting `/clock/advance`.
