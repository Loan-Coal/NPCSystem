# EXP-210 — Proactive line delivery queue (slice 1, DEC-098)

**Goal / rationale:** Tick-generated proactive lines never reach a connected player. DEC-098 approves an
in-process async queue (owned in `engines`, drained by the `api` WS handler) as the layer-clean delivery
mechanism. This slice builds the queue primitive; the WS drain wiring is slice 2.

**First slice (your scope):** A **new module** `proactive_queue.py` with a `ProactiveQueue` class wrapping
`asyncio.Queue` — `enqueue(line)` and `drain()`/`get_nowait`-style consumption, keyed by recipient
(player_id and/or npc_id). New-file-only — do NOT edit `dialogue_ws.py` or the scheduler this slice.
Prove with unit tests.

**Current state (verified):**
- `src/npc_engine/api/dialogue_ws.py:126` — `push_proactive_line(ws, line)` helper already exists (the
  slice-2 consumer will call this when draining the queue). Read it to match the line/payload shape.
- DEC-098 (DECISIONS.md) authorizes the in-process queue pattern; `engines` owning an `asyncio.Queue`
  that `api` drains is a downward (allowed) dependency — no upward import.

**Files:**
- NEW `src/npc_engine/engines/proactive_dialogue/proactive_queue.py` — `ProactiveQueue` class:
  async `enqueue(recipient_id, line)`; `drain(recipient_id) -> list[line]` (non-blocking, returns
  buffered lines). Use a typed payload model (Pydantic v2) — no raw dict across the boundary. Wrap shared
  mutation in an `asyncio.Lock` if needed and document it in the class docstring. Module docstring with
  `Does NOT:` + `Dependencies injected:` lines.
- NEW test: `tests/unit/test_proactive_queue.py`.

**Graph/API surface:** engine-internal primitive. No schema, no route.

**Architecture fit:** pure new-file-add (OCP); layer = engines. DEC-098 covers the pattern. No schema.

**Test plan (RED first):** `test_enqueue_then_drain_returns_lines`, `test_drain_empty_returns_empty`,
`test_drain_is_per_recipient`. Watch fail, implement. Run: `pytest tests/unit/test_proactive_queue.py -q`.

**Done when:** `ProactiveQueue` buffers and drains proactive lines per recipient; tests pass; no
`dialogue_ws.py`/scheduler edit (slice 2); docstrings present; async-safe.
