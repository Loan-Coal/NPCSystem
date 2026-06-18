# FIX-SEV-11 — Doc / docstring drift (3 spots)

**Severity:** LOW · **Lens:** L6 (L6-02, L6-04, L6-05)

## Problem
Three documentation/docstring drifts found by the demo lens:
1. `docs/ARCHITECTURE.md` says runtime prompts live at `prompts/<engine>/` (repo root); the real path is
   `src/npc_engine/prompts/<engine>/`. The root `prompts/` holds only canned YAMLs (L6-02).
2. `demo_game/ui/right_panel.py` module docstring's tab list omits the new INTRIGUE tab (G2.2) (L6-04).
3. `demo_game/game_controller.py` docstring lists `npc_engine.engines.interaction` as a dependency, but
   there is no such import (demo is standalone) (L6-05).

## Current shape (verify against code now)
- `docs/ARCHITECTURE.md:762` — `prompts/<engine>/`.
- `demo_game/ui/right_panel.py` — module docstring tab enumeration.
- `demo_game/game_controller.py` — module docstring "Dependencies:" line.

## Steps
1. Fix the ARCHITECTURE.md path to `src/npc_engine/prompts/<engine>/` (and clarify the root `prompts/` is canned YAML only).
2. Add INTRIGUE to the `right_panel.py` docstring tab list.
3. Remove the bogus `npc_engine.engines.interaction` dependency line from `game_controller.py` (keep the standalone invariant accurate).

## Verification
- `make test-demo` (docstrings don't affect tests but confirm nothing breaks) and `make check-docstrings`.
- Manual: grep confirms no remaining `prompts/<engine>` root-path reference in ARCHITECTURE.md.

## Blast radius
Docs/docstrings only. Zero runtime impact.
