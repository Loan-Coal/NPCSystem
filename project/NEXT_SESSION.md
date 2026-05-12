# Next Session Instructions

## Phase 3 — World Depth. Feature 3.3 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.2 as DONE (committed), add Feature 3.3 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1 ✅, 3.2 ✅, 3.3 IN_PROGRESS.

---

## Feature 3.3 — Memory Consolidation Engine

Read `project/ROADMAP.md` lines 456–480 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** NPCs accumulate session turn history in `SessionStore`. Feature 3.3 introduces a
scheduled consolidation step: for each NPC with recent dialogue turns, an LLM call summarizes the
last N turns into a `Memory` node (using Feature 3.2's `create_memory`). Original turns can be
optionally cleared after consolidation.

### Architecture decisions (read before coding)

- Engine lives in `engines/memory_consolidation/memory_consolidation_engine.py`.
- Prompt template lives in `prompts/memory_consolidation/consolidation_v1.yaml`.
- `engines/memory_consolidation/memory_consolidation_engine.py` takes a `SessionStore`,
  an `LLMClientProtocol`, and a `MemoryEngine` (injected).
- It calls the LLM with the last-N turns to get a one-paragraph summary, then calls
  `memory_engine.create_from_arousal` — but since consolidation is rule-driven, pass
  `arousal=80` directly to `create_memory` (skip arousal gating, call graph layer directly).
- Wire it into `scheduler/tick_scheduler.py` similarly to `RoutineEngine` — optional
  injected engine, called once per advance on a configurable cadence.
- Configurable `CONSOLIDATION_TURN_THRESHOLD` in `config.py`: minimum turns before consolidating.
  Default: 10 turns.
- After consolidation, optionally clear the turns from SessionStore (configurable via
  `CONSOLIDATION_CLEAR_TURNS: bool`, default False for safety).

### Steps

1. **Prompt template** `prompts/memory_consolidation/consolidation_v1.yaml`:
   - System role: NPC memory archivist.
   - User message: list of turns formatted as dialogue.
   - Expected output: single paragraph plain-text summary (not JSON — the engine stores it as content).

2. **`engines/memory_consolidation/__init__.py`** and **`memory_consolidation_engine.py`** (≤150 lines):
   - `MemoryConsolidationEngine` with `consolidate(session, npc_id, game_time) -> str | None`.
   - Fetches turns from `SessionStore`; if count < threshold, returns None.
   - Calls LLM with the consolidation prompt.
   - Calls `graph.memory_service.create_memory` directly (vividness=75, emotional_charge=0).
   - Returns the new memory_id.

3. **`config.py`** — add `CONSOLIDATION_TURN_THRESHOLD: int = 10` and `CONSOLIDATION_CLEAR_TURNS: bool = False`.

4. **`scheduler/tick_scheduler.py`** — add optional `memory_consolidation_engine` parameter (like routine_engine), call on every N advances.

5. **Unit tests** `tests/unit/test_memory_consolidation_engine.py`:
   - Happy path: enough turns → LLM called → memory created.
   - Skip path: fewer turns than threshold → returns None, no LLM call.
   - LLM failure: validate graceful skip (no crash).

6. **E2E scenario** `e2e/scenarios/scenario_memory_consolidation.py`:
   - Seed character with 15 mock session turns.
   - Call consolidate.
   - Assert a Memory node now exists for the character.

### Definition of done (3.3)
- Prompt YAML exists in `prompts/memory_consolidation/`.
- `engines/memory_consolidation/` passes all unit tests.
- Config fields added and defaulted.
- Scheduler wired (optional injection, no forced calls in existing tests).
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: memory consolidation engine (Phase 3.3)`

---

## After 3.3 is committed — update this file for Feature 3.4

When Feature 3.3 is committed and `pytest tests/ -q` is green, rewrite this file to target
Feature 3.4 — Beliefs (separate from knowledge).

Read `project/ROADMAP.md` lines 481+ before writing 3.4 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3.3 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.3, log a new ISSUES.md entry describing the blocking scenario
and get approval before fixing.
