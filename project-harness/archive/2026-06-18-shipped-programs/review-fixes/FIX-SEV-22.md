# FIX-SEV-22 — `DistortionType` → `str` validated against the live strategy registry

**Severity:** MEDIUM · **Decision:** DEC-120 (str + registry validator)

## Problem
Gossip distortion strategies are an open `STRATEGY_REGISTRY`, but `DistortionType` is still a closed
`Literal` and `REGISTRY_KEYS` is frozen at import time. A 5th strategy added via a new file is rejected by
the Literal and unreachable through the frozen keys — defeating the registry's add-by-new-file OCP intent.

## Current shape (verify against code now)
- `src/npc_engine/engines/gossip/gossip_distort.py:35` — `DistortionType = Literal["omission","exaggeration","role_swap","timeline_shift"]`.
- `:42` — `distortion_type: DistortionType | None` (field on `GossipDistortion`, a Pydantic model).
- `src/npc_engine/engines/gossip/distortion_strategy.py:47` — `STRATEGY_REGISTRY: dict[str, DistortionStrategy]`.
- `:54` — `REGISTRY_KEYS: tuple[str, ...] = tuple(STRATEGY_REGISTRY)` (frozen at import).
- `gossip_distort.py` dispatch uses `REGISTRY_KEYS` indexing (lines ~215, 226).

## Steps
1. Change `DistortionType` to `str` (keep the alias name for readability) and type
   `distortion_type: str | None` on `GossipDistortion`.
2. Add a Pydantic field validator on `GossipDistortion.distortion_type`: accept `None` or any key in
   `STRATEGY_REGISTRY`; raise on unknown values (fail-fast at the boundary).
3. Make the live registry the source of truth: replace the module-level frozen `REGISTRY_KEYS` with a small
   accessor (e.g. `registry_keys() -> tuple[str, ...]` returning `tuple(STRATEGY_REGISTRY)`) and update the
   dispatch sites to call it, so a newly-registered strategy is reachable. (Keep deterministic ordering —
   sort keys for stable seed→index mapping.)

## Verification
- Test: register a temporary strategy into `STRATEGY_REGISTRY`, build `GossipDistortion(distortion_type="<new>")`
  (accepted) and confirm the dispatch can select it; `GossipDistortion(distortion_type="bogus")` raises.
- `pytest tests/ -k "distort or gossip" -q` then `make check` (mypy — the seed→index mapping must stay typed).

## Blast radius
`gossip_distort.py`, `distortion_strategy.py` + gossip/distortion tests. Watch the seed→index determinism
(eval battery depends on stable distortion selection). No graph-schema change (same string values stored).
