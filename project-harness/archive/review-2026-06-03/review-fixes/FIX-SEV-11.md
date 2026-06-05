# FIX-SEV-11 — Make the game losable and winnable; fix victory attribution and neutral bribes

**Severity:** HIGH · **Confidence:** Confirmed (lose) / Likely (win) · **Effort:** M
**Category:** gameplay / correctness · **Absorbs:** GAME-01, GAME-02, GAME-04, GAME-05

## Problem
The lose condition is structurally unreachable, the win path is undiscoverable with the shipped economy, victory may be attributed to the wrong faction, and bribing a neutral NPC burns gold for nothing with positive feedback.

## Current shape
- `demo_game/game_end_checker.py:24` `LOSE_LOCATION_ID = "loc_market_square"`; `:103-114` `check_lose` returns `LOSE_LOCATION_ID in iron_legion_controls`.
- `demo_game/seed.py:523-544` seeds armies only at `loc_guard_barracks`; `military_battle_service.py:132-143` writes `CONTROLS` only at the battle location → Iron Legion can only ever control `loc_guard_barracks`.
- Win: `WIN_STANDING_THRESHOLD=50`, `WIN_MIN_FACTIONS=2`, `BRIBE_GOLD_COST=20`, `BRIBE_STANDING_GAIN=15` (`constants.py:80-81`), `_PLAYER_STARTING_GOLD=60` → needs 160 bribe-gold; earn loop (Aldric quest +50 `_ALDRIC_REWARD_AMOUNT`, spice trade +120 `_SPICE_VALUE`) is untutorialised. Objective bar (`world_panel.py:175`) only states the goal, not how to earn.
- `game_end_checker.detect_first_allied_faction:60-80` returns `max((standing, faction))` (highest standing, alphabetical tiebreak) — not first-to-cross.
- `game_controller.py:246-260` `spawn_bribe`: `NPC_FACTIONS.get(npc_id)` is `"neutral"` for `mira`/`old_henryk` (truthy) → bribes a non-win faction, status says "Bribed neutral: standing now 15".

## Target shape
Both terminal states are reachable via a discoverable path; victory attribution matches the intended semantic; neutral NPCs can't be bribed.

## Steps
1. **Make lose reachable:** either seed/advance an Iron Legion army to `loc_market_square` so a battle there can resolve, OR set `LOSE_LOCATION_ID = "loc_guard_barracks"` to match the only resolving battle. Pick one; seed accordingly.
2. **Make win discoverable:** add an on-screen objective hint chain ("Earn gold: complete Aldric's quest / trade spices, then bribe"). Optionally retune (`BRIBE_STANDING_GAIN` up or threshold down) for a 5-minute demo.
3. **Fix attribution:** track per-faction first-crossing in the poller across polls (capture the faction the moment it individually first crosses 50), not `max` over a later snapshot; document the tiebreak. Or rename the function if "most invested" is actually intended.
4. **Neutral guard:** `if not faction_id or faction_id == "neutral"` → no-op with a clear status ("Mira has no faction to bribe"); do not deduct gold.

## Verification
- Integration test drives quest→trade→bribe×N to `outcome=="win"`; a forced battle at the lose location → `DEFEAT` overlay.
- Unit test: merchants crosses 50 at poll N, city_guard at N+1 with higher standing → `arc_faction == merchants`.
- Unit test: bribing a neutral NPC → no-op status, gold unchanged.

## Blast radius
The whole objective system, win/lose overlays, ACT-7 tension. Coordinate with SEV-13 (world id) since both touch the demo war/rumor arc.
