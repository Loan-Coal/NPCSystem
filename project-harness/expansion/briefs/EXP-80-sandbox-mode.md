# EXP-80 — Free-play / sandbox mode (auto-tick timer)

**Goal / rationale:** BUSINESS_INTENT success criterion 7 ("the world runs off-screen") and the
"living world" thesis. The interactive pygame window only advances time on the C key
(`game_window.py:334-339`) — there is no autonomous tick. A sandbox mode with a timer thread
makes the world breathe under the player without manual input, showing buyers the off-screen
simulation at work.

**First slice (this worker's scope):** A `SandboxLoop` class in a new `demo_game/sandbox_loop.py`
that runs a background thread: every N seconds (default 8s, configurable), it calls
`EngineClient.advance_clock(1)` to tick the world. `GameWindow` gains a sandbox toggle (press `S`)
and an "AUTO-TICK: ON/OFF" status line near the clock display. No new UI panels — minimal change.

**Current state (verify):**
- `demo_game/ui/game_window.py:334-339` — C-key handler calls `_on_advance_clock()`; the clock
  is only advanced manually. No auto-tick exists.
- `demo_game/client.py:261` — `EngineClient.advance_clock(delta: int)` → `POST /v1/clock/advance`.
- `demo_game/ui/game_window.py` — check existing `_tick_pollers` and the `pygame` event loop for
  the right place to start/stop the sandbox thread and render the status line.
- Confirm `GameWindow.__init__` signature — add a `sandbox_loop: SandboxLoop | None = None`
  injection param (DI via constructor, not module-level state).

**Files (SandboxLoop = new file → zero conflict on existing code except game_window):**
- NEW `demo_game/sandbox_loop.py` — `SandboxLoop` class with `start()` / `stop()` / `is_running`
  using `threading.Thread` + `threading.Event` for clean shutdown. Calls `client.advance_clock(1)`
  on each interval. Module + class + public-method docstrings required. Keep ≤300 lines.
- EDIT `demo_game/ui/game_window.py` — add `S` key toggle to start/stop `SandboxLoop`, render
  "AUTO-TICK: ON" / "AUTO-TICK: OFF" status line (one line near the existing clock readout).
  DI: accept `sandbox_loop` param in `GameWindow.__init__`; `game_window.py` does NOT instantiate
  `SandboxLoop` itself — caller (entry point / `main.py`) does. Follow existing DI patterns.
- NEW `demo_game/tests/test_sandbox_loop.py` — unit test with a mocked client.

**Graph/API surface:** none new (consumes `POST /v1/clock/advance` already in `EngineClient`).

**Architecture fit:** demo-only, zero `src/` changes. `SandboxLoop` is a new standalone file;
the single edit to `game_window.py` adds ≤15 lines (toggle key + status render). DI via
constructor preserves testability. Thread shutdown is clean (Event-based, never daemon).

**Test plan (write FIRST):** `demo_game/tests/test_sandbox_loop.py` — inject a mock `EngineClient`
that records `advance_clock` calls; start a `SandboxLoop` with a 0.05s interval; sleep 0.2s;
stop it; assert `advance_clock` was called ≥ 3 times and that the loop stops calling after
`stop()`. Also assert no exception on double-stop. Run: `pytest demo_game/tests/test_sandbox_loop.py -q`.

**Done when:** The unit test is green. Against a live stack, pressing `S` in the pygame window
toggles auto-tick, the status line updates, and the WORLD tab refreshes show new events firing
without the player pressing C. (Carry-forward: `SandboxLoop` is the reusable auto-tick primitive
for EXP-82 proactive demo and EXP-89 mood-contagion visualiser; its `start/stop` API is stable.)
