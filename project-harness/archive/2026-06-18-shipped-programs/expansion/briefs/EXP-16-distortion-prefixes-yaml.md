# EXP-16 — Distortion Prefixes → YAML

**Goal / business rationale**
Move hardcoded distortion prefix strings from Python strategy files into a YAML config
file so designers can tune gossip flavour text without touching code. Directly unblocked
by EXP-15 (STRATEGY_REGISTRY now exists). BUSINESS_INTENT: richer, tunable gossip layer.

---

## First slice

Add `src/npc_engine/prompts/gossip/distortion.yaml` with one key per strategy, create a
`prefix_loader.py` helper in `engines/gossip/strategies/`, and update the three prefix-
based strategy files (`exaggeration`, `role_swap`, `timeline_shift`) to read their prefix
from the loader instead of a hardcoded `_PREFIX` constant.

`omission` has no prefix — leave it unchanged.

---

## Current state

**`src/npc_engine/engines/gossip/strategies/exaggeration.py:13`**
```python
_PREFIX = "It was utterly catastrophic: "
```

**`src/npc_engine/engines/gossip/strategies/role_swap.py:13`**
```python
_PREFIX = "They say the opposite happened: "
```

**`src/npc_engine/engines/gossip/strategies/timeline_shift.py:13`**
```python
_PREFIX = "Long ago, "
```

No `prompts/gossip/` directory exists yet. Existing `prompts/` examples:
`src/npc_engine/prompts/dialogue/system_v1.yaml` (reference for YAML format).

---

## Files

**New:**
- `src/npc_engine/prompts/gossip/distortion.yaml` — prefix strings per strategy key
- `src/npc_engine/engines/gossip/strategies/prefix_loader.py` — loads + caches the YAML;
  exposes `get_distortion_prefix(strategy_key: str) -> str`

**Edit:**
- `src/npc_engine/engines/gossip/strategies/exaggeration.py` — replace `_PREFIX` const with
  `_PREFIX = get_distortion_prefix("exaggeration")` (called at module load time)
- `src/npc_engine/engines/gossip/strategies/role_swap.py` — same pattern
- `src/npc_engine/engines/gossip/strategies/timeline_shift.py` — same pattern

**Do NOT touch:**
- `distortion_strategy.py`, `__init__.py`, `omission.py`, `gossip_distort.py`, or any
  coordination file.

---

## Graph / API surface

Engine-internal. No routes or graph schema involved.

---

## Architecture fit

OCP seam: new config file + new utility module. The strategy files get a small edit
(one-liner import swap), but no variant logic changes. This is config extraction, not
a new variant — compatible with OCP because the closed contract (callable protocol) is
unchanged.

Layer: `engines/gossip/strategies/prefix_loader.py` → layer **engines** (pure function,
no I/O beyond `pathlib.Path` file read at import time; acceptable per CLAUDE.md pattern).

No schema change. No DECISIONS approval required.

---

## Test plan

**Failing test to write first** (`tests/unit/test_prefix_loader.py`):
```python
def test_get_distortion_prefix_exaggeration():
    prefix = get_distortion_prefix("exaggeration")
    assert "catastrophic" in prefix.lower()

def test_get_distortion_prefix_unknown_raises():
    with pytest.raises(KeyError):
        get_distortion_prefix("nonexistent")
```

Also add to `tests/unit/test_distortion_strategies.py` (or create if absent):
```python
def test_exaggeration_uses_yaml_prefix():
    result = exaggeration("troops marched north")
    assert result.startswith(get_distortion_prefix("exaggeration"))
```

Unit test command: `pytest tests/unit/test_prefix_loader.py tests/unit/test_distortion_strategies.py -v`

---

## Done when

1. `distortion.yaml` exists with keys: `exaggeration`, `role_swap`, `timeline_shift`.
2. All three strategy files import their prefix from `prefix_loader.py`; no `_PREFIX`
   literal remains in those files.
3. Unit tests above pass.
4. `pytest tests/unit/` green; no regressions.
