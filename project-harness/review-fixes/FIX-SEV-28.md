# FIX-SEV-28 — WebSocket recv timeout + watchdog to clear `_is_waiting`

**Severity:** MEDIUM · **Confidence:** Likely · **Effort:** S
**Category:** demo · **Absorbs:** DEMO-06

## Problem
`demo_game/dialogue_ws.py:49-62` calls `ws.recv()` with no timeout. A server that streams and then dies without sending a `done`/`error` frame blocks the daemon thread on `recv()` forever → `GameController._is_waiting=True` forever → all user input locked for the rest of the session.

## Current shape
```python
# dialogue_ws.py ~49-62
while True:
    msg = ws.recv()        # no timeout — blocks indefinitely on stall
    ...
    if msg_data.get("type") == "done":
        break
```
`GameController._is_waiting` is set True before the WS call and only cleared on a clean `done`/`error` frame. No finally block, no watchdog.

## Steps
1. In `demo_game/constants.py`: add `NPC_DIALOGUE_TIMEOUT_S: float = 30.0` if absent.
2. In `dialogue_ws.py`: import `asyncio` and `NPC_DIALOGUE_TIMEOUT_S`.
3. Wrap `ws.recv()` with `asyncio.wait_for(ws.recv(), timeout=NPC_DIALOGUE_TIMEOUT_S)`; catch `asyncio.TimeoutError` → log a warning and `break`.
4. Wrap the entire WS loop in a `try/finally` that calls `game_controller.clear_waiting()`.
5. Add `clear_waiting(self) -> None` to `GameController` if it does not exist — single line: `self._is_waiting = False`.

## Verification
- `tests/unit/test_dialogue_ws_timeout.py`:
  - Mock `ws.recv()` to stall → after timeout `_is_waiting` is False.
  - Mock `ws.recv()` to raise `TimeoutError` → loop exits cleanly.
- `NPC_DIALOGUE_TIMEOUT_S` present in `demo_game/constants.py`.
- `make test-demo` passes.

## Blast radius
Demo dialogue WS path only; `GameController._is_waiting` cleanup path.
