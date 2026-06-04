# FIX-SEV-37 — Demo low-severity cluster (magic strings, print, config, QUIT)

**Severity:** LOW · **Confidence:** Confirmed · **Effort:** S
**Category:** demo · **Absorbs:** DEMO-05, DEMO-08, DEMO-10..14

## Problem
Six distinct violations in `demo_game/`:
1. Magic string `"I'd like to trade."` appears in 3 control-flow sites
2. ~15 `print()` calls in pollers violate the structured-logging rule
3. `NPC_API_KEY` dev default hardcoded (config, not source code)
4. Module-level `DemoConfig()` instantiation (should be lazy accessor)
5. No client-side cap on `player_message` length
6. QUIT event dispatched after `running=False`

## Current shape
- `demo_game/constants.py`: verify `"I'd like to trade."` not yet a constant
- `demo_game/gold_poller.py` and other pollers: `print()` calls
- Config file in `demo_game/`: hardcoded `NPC_API_KEY` default
- `demo_game/game_controller.py`: module-level `DemoConfig()` somewhere at import
- Main game loop: QUIT dispatched regardless of `running`

## Steps
1. `demo_game/constants.py`: add `TRADE_INTENT_MESSAGE = "I'd like to trade."` and replace all 3 uses across `demo_game/`.
2. All pollers (`gold_poller.py` and any others with `print()`): replace with `import logging; logger = logging.getLogger(__name__)` and `logger.info(...)` / `logger.warning(...)`.
3. In demo config: change hardcoded `NPC_API_KEY` default to `os.environ["NPC_API_KEY"]` (KeyError at startup if absent is the correct fail-fast behavior).
4. In `game_controller.py` or wherever `DemoConfig()` is module-level: wrap in a `get_demo_config()` function with `@functools.lru_cache(maxsize=None)`.
5. In `demo_game/client.py` or message-sending caller: cap `player_message` at `MAX_PLAYER_MESSAGE_CHARS` (import from `config.py` or define `DEMO_MAX_MESSAGE_CHARS = 1000` in `demo_game/constants.py`).
6. In main game loop: guard QUIT dispatch with `if running: ...` before dispatching.
7. Update any stale test docstrings (e.g., the "8 methods" comment).

## Verification
- `rg '"I.d like to trade."' demo_game/` → 0 matches (constant used instead)
- `rg "^    print(" demo_game/` → 0 matches
- `rg 'NPC_API_KEY.*change_this' demo_game/` → 0 matches
- `make test-demo` passes

## Blast radius
`demo_game/` only; no engine code touched.
