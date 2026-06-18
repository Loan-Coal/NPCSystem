# EXP-15 — Distortion Strategy Registry (OCP seam for gossip)

**Phase:** 2 · **Effort:** M · **Deps:** none
**Touches:** `src/npc_engine/engines/gossip/gossip_distort.py`, new `src/npc_engine/engines/gossip/distortion_strategy.py`, new strategy files
**Does NOT touch:** `demo_game/`, any `graph/`, any prompt YAML, `retrieval/`, `EXPANSION_INDEX.md`

---

## Purpose

`gossip_distort.py:93-103` contains a closed 4-branch `_apply_template` if-chain that
must be edited every time a new distortion type is added — violating the OCP constraint
in `BUSINESS_INTENT.md:94`. Replace it with a **name-keyed strategy registry** so new
distortion types are added by creating a new file, never editing the closed function.

**Hard invariant:** determinism must not change. The selection is
`distortion_types[seed % len(distortion_types)]` (`gossip_distort.py:162-163`). After
the refactor the seed→strategy mapping must be **identical** for all 4 existing types:
the registry must be keyed by stable names ("omission", "exaggeration", "role_swap",
"timeline_shift") in the same order as today's list.

---

## What already exists

- `gossip_distort.py:93-103` — `_apply_template(summary, distortion_type)`: 4-branch
  if-chain returning hardcoded English strings.
- `gossip_distort.py:162-163` — selection: `distortion_types` list + `seed % len`.
- `GossipDistortion` Pydantic model (`gossip_distort.py:20-27`) — frozen, output type.
- `DistortionType = Literal["omission", "exaggeration", "role_swap", "timeline_shift"]`
  (`gossip_distort.py:17`).

---

## Files

**New:**
- `src/npc_engine/engines/gossip/distortion_strategy.py` — `DistortionStrategy` Protocol
  (`__call__(summary: str) -> str`) + `STRATEGY_REGISTRY: dict[str, DistortionStrategy]`
  (ordered dict; order = deterministic seed→index mapping).
- `src/npc_engine/engines/gossip/strategies/__init__.py` — package docstring only.
- `src/npc_engine/engines/gossip/strategies/omission.py`
- `src/npc_engine/engines/gossip/strategies/exaggeration.py`
- `src/npc_engine/engines/gossip/strategies/role_swap.py`
- `src/npc_engine/engines/gossip/strategies/timeline_shift.py`
- `tests/unit/test_distortion_strategy_registry.py`

**Edited:**
- `src/npc_engine/engines/gossip/gossip_distort.py` — replace `_apply_template` + the
  `distortion_types` list with a `REGISTRY_KEYS` tuple that drives `seed % len` selection
  (preserving index order), then calls `STRATEGY_REGISTRY[key](summary)`.

---

## Architecture fit

OCP add-by-new-file: the 4 existing branches become 4 callable objects, each in its own
file, registered under their stable key. `gossip_distort.py` dispatches via
`STRATEGY_REGISTRY[key]` — adding a 5th type means writing a 5th file and adding one
entry to the registry (which may require a `DECISIONS.md` entry for re-ordering risk, but
no edit to `_apply_template`).

`DistortionType` Literal must be updated to include any new types added to the registry.
For this first slice it stays as `Literal["omission", "exaggeration", "role_swap", "timeline_shift"]`.

Layer: `engines/gossip/` — no layer violations.

---

## Strategy Protocol shape

```python
# distortion_strategy.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class DistortionStrategy(Protocol):
    """Apply a distortion to a raw event summary and return the distorted text."""
    def __call__(self, summary: str) -> str: ...

# STRATEGY_REGISTRY must preserve index order for determinism:
# index 0 → omission, 1 → exaggeration, 2 → role_swap, 3 → timeline_shift
STRATEGY_REGISTRY: dict[str, DistortionStrategy] = {
    "omission": ...,
    "exaggeration": ...,
    "role_swap": ...,
    "timeline_shift": ...,
}
REGISTRY_KEYS: tuple[str, ...] = tuple(STRATEGY_REGISTRY)  # stable index order
```

Each strategy file is a module with a single `class` or a module-level callable (prefer
a small `@dataclass` or a plain callable class implementing the Protocol).

---

## TDD

Write `tests/unit/test_distortion_strategy_registry.py` FIRST.

| Test | What it asserts |
|------|-----------------|
| `test_registry_keys_stable_order` | `REGISTRY_KEYS == ("omission", "exaggeration", "role_swap", "timeline_shift")` |
| `test_omission_halves_words` | omission strategy trims to half the words (existing logic) |
| `test_exaggeration_prefix` | exaggeration strategy adds catastrophic prefix |
| `test_role_swap_prefix` | role_swap strategy adds "opposite" prefix |
| `test_timeline_shift_prefix` | timeline_shift strategy adds "Long ago" prefix |
| `test_gossip_distort_registry_parity` | Call `gossip_distort(...)` with a fixed seed for each type; assert output == pre-refactor expected strings (golden test) |
| `test_registry_protocol_conformance` | Each registered object passes `isinstance(obj, DistortionStrategy)` |

Run only: `pytest tests/unit/test_distortion_strategy_registry.py -v`

---

## Done when

- `pytest tests/unit/test_distortion_strategy_registry.py` is green.
- `pytest tests/unit/test_gossip_distort.py` (existing tests) still green — no behavioral change.
- `gossip_distort.py` no longer contains the `_apply_template` function.
- `distortion_strategy.py` contains the Protocol + registry.
- 4 strategy files exist, each under 50 lines, with module docstrings.
- No existing file exceeds 300 lines.
- No prompt strings outside `prompts/`.
- Layer rules respected.
