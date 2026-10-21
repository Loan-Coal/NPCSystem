# SEV-01 — WebSocket slot leak: the cap exhausts after 5 conversations

🔴 **CRITICAL** · Finding **L9-01** (live) · Confidence: Confirmed · Evidence: `evidence/L9.md`

## Problem

`_release_ws_slot` never runs for a normally-closed dialogue socket, so every completed streaming
conversation permanently consumes one of five per-key slots. Consequences, all observed live:

- `make demo-run` (live, not `--dry-run`) dies at **ACT 6 of 12**:
  `RuntimeError: WS dialogue error for mira_innkeeper: server rejected WebSocket connection: HTTP 403`.
- The **interactive demo dies after exactly 5 dialogue turns** — `game_controller.py:179-270` spawns a
  fresh `dialogue_ws_worker` thread, i.e. a fresh WS connection, *per send*. A human evaluator gets five
  lines of dialogue, then every further attempt 403s.
- It is a **server-side resource leak**, not just a demo bug. A shipped deployment degrades to "no
  streaming dialogue" after five conversations per API key; only a process restart recovers it.

## Current shape

`src/npc_engine/api/routes/dialogue/dialogue_ws.py`
- `:50` — `MAX_WS_CONNECTIONS_PER_KEY: int = 5`
- `:231-233` — after `_run_first_turn`, the handler enters an idle-drain loop that only ever **sends**:
  ```python
  while True:
      await drain_proactive_lines(...)
      await asyncio.sleep(0.5)
  ```
- `:234` — `except WebSocketDisconnect:`
- `:240-241` — `finally: await _release_ws_slot(key_id)`

Starlette surfaces a client-initiated close as `WebSocketDisconnect` **only on a `receive()`**. With an
empty proactive queue this loop never receives and never sends, so the exception never fires and the
`finally` never runs. The slot is held for the process lifetime.

The client side is correct and is **not** the bug: `demo_game/dialogue_ws.py:67` opens the socket in a
`with websockets.sync.client.connect(...)` block and `_recv_loop` returns on the `done` frame, so the
context manager closes it. Live logs show exactly five accepts spread over ~90s — each visibly finished
before the next began — then `ws_connection_cap_reached max=5` and a 403.

## Why every gate missed it

2026-06-03 L1-01 fixed "cap defined but never enforced" by adding a guard test on
`check_ws_connection_limit()` **in isolation**. The *release* half of the same accounting was never
exercised end to end. This is systemic pattern §3.4 verbatim.

## Steps

1. Make the idle loop disconnect-aware. Replace the sleep-only loop with a receive that can time out:
   ```python
   try:
       msg = await asyncio.wait_for(websocket.receive(), timeout=PROACTIVE_DRAIN_POLL_SECONDS)
   except TimeoutError:
       await drain_proactive_lines(...)   # nothing from the client; keep draining
       continue
   if msg["type"] == "websocket.disconnect":
       break
   ```
   Treat `TimeoutError` as "keep draining" and a `websocket.disconnect` message (or
   `WebSocketDisconnect`) as the exit, so a client close is observed within one poll interval.
   Introduce `PROACTIVE_DRAIN_POLL_SECONDS` as a named constant (0.5, matching today's sleep) — no
   hardcoded literal, per CLAUDE.md.
2. Keep `_release_ws_slot` in the `finally`; do not move it. The fix is making the loop *reach* the
   `finally`, not relocating the release.
3. Confirm the existing `except WebSocketDisconnect` path still handles a mid-turn disconnect.

## Verification

**Write this test first and confirm it fails for the right reason** (the 6th connect is rejected):

`tests/unit/api/test_ws_connection_slot_release.py` — open `MAX_WS_CONNECTIONS_PER_KEY + 1` sockets
**sequentially**, closing each fully before opening the next, and assert the last one is **accepted**.
The sequential-close case is exactly what the current guard test does not cover.

```
pytest tests/unit/api/test_ws_connection_slot_release.py -v
make check
```

Then verify live — this bug is invisible to `make check`:
```
make eval-stack-up          # rebuild: the app image is NOT bind-mounted
make demo-run               # live, NOT --dry-run
```
Expect all 12 ACTs to complete. Before the fix this dies at ACT 6.

## Blast radius

One handler function in `dialogue_ws.py`. No schema, no public route signature, no config change.
Behavioural risk: the loop now consumes client messages it previously ignored — confirm the protocol
sends nothing on that channel after the first turn, or route unexpected frames to the existing handler.

**Sequencing:** land this **before SEV-09**, which edits the same handler. Everything in this backlog
that needs live demo verification is blocked behind this fix.
