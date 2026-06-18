# EXP-95: In-Window Scenario Picker

**Goal / business rationale**
Replace the 3-separate-`make`-targets flow with a single `make demo` that shows a pygame start
screen. An evaluator picks an arc without needing to know CLI commands.
Traces to BUSINESS_INTENT §1 (unified sales-artifact entry point): one launch surface for
Munich Demo Arc, Village Crisis, Tavern Intrigue, or Free-Play.

**First slice**
A pygame splash/menu screen shown before the game window. Keyboard-navigable (1–4 keys + Enter).
On scripted arc selection, launches the appropriate runner as a subprocess and exits.
On Free-Play, proceeds to `game_window.run()`. KE-6 MERGE seeding ensures arc re-seeds don't
create duplicate nodes.

---

## Current state (verified against codebase)

| Location | What's there |
|---|---|
| `demo_game/__main__.py:16–25` | Parses `--size`, calls `game_window.run(w, h)` directly — **no menu** |
| `demo_game/run.py:496` | `main()` callable; invoked by `make demo-run` as `python -m demo_game.run` |
| `demo_game/scenarios/run_village_crisis.py:334` | `main()` callable; invoked by `python -m demo_game.scenarios.run_village_crisis` |
| `demo_game/scenarios/run_tavern_intrigue.py:333` | `main()` callable; invoked by `python -m demo_game.scenarios.run_tavern_intrigue` |
| `demo_game/ui/game_window.py:1` | `run(window_w, window_h)` entry; existing panels; free-play interactive |
| `demo_game/ui/` | Existing panel modules; `start_menu.py` fits here as a peer |
| `Makefile:194–196` | `demo: docker-compose up -d; $(PYTHON) -m demo_game` |

---

## Files

**New:**
- `demo_game/arc_choice.py` — `ArcChoice(enum.Enum)` with values `MUNICH`, `VILLAGE`,
  `TAVERN`, `FREE_PLAY`.
- `demo_game/ui/start_menu.py` — `StartMenu` class; `show(window_w: int, window_h: int) -> ArcChoice`;
  renders 4-option menu with pygame (coloured selection highlight); keyboard nav via 1–4 keys or
  arrow keys + Enter; Escape / Q → quit. No imports from `src/npc_engine/`.

**Edit (minimal wiring only):**
- `demo_game/__main__.py` — after `_parse_args()`, call `StartMenu().show(w, h)`:
  - `ArcChoice.FREE_PLAY` → `game_window.run(w, h)` (existing path)
  - `ArcChoice.MUNICH` → `subprocess.run([sys.executable, "-m", "demo_game.run"], check=False)`
  - `ArcChoice.VILLAGE` → `subprocess.run([sys.executable, "-m", "demo_game.scenarios.run_village_crisis"], check=False)`
  - `ArcChoice.TAVERN` → `subprocess.run([sys.executable, "-m", "demo_game.scenarios.run_tavern_intrigue"], check=False)`

---

## Graph / API surface

No engine changes. No `src/` imports. Demo-only (`demo_game/`).

---

## Architecture fit

OCP add-by-new-file: `arc_choice.py` and `start_menu.py` are new. `__main__.py` change is
a 5–8 line wiring addition at the entry point — no existing logic removed or replaced.
No imports from `src/npc_engine/`. No schema/DECISIONS needed. `demo_game/` layer only.

Note: each scripted runner writes to stdout/stderr and exits; the subprocess call is fire-and-
wait. The game window is not launched alongside a running subprocess. This is intentional for
the first slice.

---

## Test plan

Write `demo_game/tests/test_start_menu.py` **first** (failing):

```python
# test 1 — enum completeness
def test_arc_choice_has_four_values():
    assert len(ArcChoice) == 4

# test 2 — StartMenu instantiates without pygame display
def test_start_menu_init_no_display(monkeypatch):
    monkeypatch.setattr("pygame.display.set_mode", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("pygame.display.set_caption", lambda *a: None)
    StartMenu()  # should not raise

# test 3 — FREE_PLAY dispatch calls game_window.run
def test_dispatch_free_play_opens_game_window(monkeypatch):
    monkeypatch.setattr("demo_game.ui.start_menu.StartMenu.show", lambda *a: ArcChoice.FREE_PLAY)
    mock_run = MagicMock()
    monkeypatch.setattr("demo_game.ui.game_window.run", mock_run)
    # call __main__ dispatch logic; assert mock_run called once

# test 4 — scripted arc dispatch calls subprocess
def test_dispatch_munich_calls_subprocess(monkeypatch):
    monkeypatch.setattr("demo_game.ui.start_menu.StartMenu.show", lambda *a: ArcChoice.MUNICH)
    mock_sp = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_sp)
    # call dispatch logic; assert subprocess.run called with "-m", "demo_game.run"
```

Run: `pytest demo_game/tests/test_start_menu.py -v`

---

## Done when

- `pytest demo_game/tests/test_start_menu.py` passes (4 tests)
- `make demo` (with engine running) shows the start menu before the game window
- Pressing `1` launches Munich demo runner in terminal; pressing `4` (or Free-Play) opens the
  interactive game window
- `make check` and `make test-demo` both green
