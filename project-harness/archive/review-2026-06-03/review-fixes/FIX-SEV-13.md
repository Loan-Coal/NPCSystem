# FIX-SEV-13 — Restore canonical WorldState id `world` (un-regress DEC-022 / ISSUE-041)

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** S
**Category:** correctness (regression) · **Absorbs:** DEMO-02, GAME-10, DEMO-09

## Problem
The demo seeds/writes the WorldState node as `world_demo`, but the engine reader (`world/world_reader.py`) reads `world` (DEC-022). So epoch/active_conditions written by the demo are never read by NPCs — the war/rumor-warfare beat is cosmetic. This is exactly the bug ISSUE-041 closed. Additionally `put_world_state` clobbers unrelated fields on every call.

## Current shape
- `demo_game/seed.py:34` `_WORLD_STATE_ID = "world_demo"`; `build_world_state_payload:202` sets `"id": _WORLD_STATE_ID`.
- `demo_game/client.py:722-748` `put_world_state` docstring claims "merges on the canonical id `world` (DEC-022)" but body writes `{"id":"world_demo", ..., "faction_standings":{}, "time_of_day":"morning", ...}` — resetting `faction_standings`/`time_of_day` every call.
- `game_window.py:326` `W`-key war trigger calls `put_world_state`.
- DEC-022 + `world/world_reader.py` default = `"world"`.

## Target shape
Both demo constants use `"world"`; `put_world_state` patches only `epoch`/`active_conditions`.

## Steps
1. Set `demo_game/seed.py:34` `_WORLD_STATE_ID = "world"`.
2. Set `demo_game/client.py:739` `"id": "world"` (and remove the misleading docstring/body mismatch).
3. Make `put_world_state` patch only `epoch` and `active_conditions` (read-merge-write or a PATCH endpoint); stop hardcoding `faction_standings={}` / `time_of_day` / `weather`.
4. Re-seed the live DB.

## Verification
- `rg "world_demo" demo_game` → 0.
- Regression test asserting `put_world_state` request body `id == "world"`.
- Manual: seed, press `W` (declare war), confirm an epoch-gated dialogue line changes; set faction standings, press `W`, confirm standings survive.

## Blast radius
Every epoch/active_conditions-gated rule; the ACT-7 narrative payoff. One-line core change with high narrative impact. Coordinate with SEV-11 (same demo arc).
