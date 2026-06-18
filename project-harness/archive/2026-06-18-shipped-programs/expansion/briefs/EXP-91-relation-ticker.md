# EXP-91 — Relationship-Delta Live Ticker (Demo)

**Phase:** 2 · **Effort:** S · **Deps:** EXP-50 (done)
**Touches:** new `demo_game/ui/relation_ticker.py`, `demo_game/ui/game_window.py`
**Does NOT touch:** `demo_game/client.py` (orchestrator adds get_npc_relationship pre-dispatch)

---

## Orchestrator pre-dispatch action (BEFORE this worker starts)

Same as EXP-81: the orchestrator must add `get_npc_relationship` to `demo_game/client.py`
before dispatching this worker. Do not add it yourself — one method, shared by both EXP-81
and EXP-91.

```python
def get_npc_relationship(self, npc_id: str, other_id: str) -> dict | None:
    """Fetch RELATES_TO edge properties via GET /v1/npc/{npc_id}/relationship/{other_id}.

    Args:
        npc_id: Source character node ID.
        other_id: Target character node ID.

    Returns:
        Dict with trust, fear, affection, interaction_count, or None on 404.

    Raises:
        EngineClientError: On any non-404 4xx or 5xx response.
    """
    resp = self._client.get(
        f"/v1/npc/{npc_id}/relationship/{other_id}",
        timeout=self._graph_timeout,
    )
    if resp.status_code == 404:
        return None
    self._raise_for_status(resp, f"GET /v1/npc/{npc_id}/relationship/{other_id}")
    return resp.json().get("data")
```

---

## Purpose

After a dialogue turn, the demo should show trust/fear/affection changing live in the
UI — making the relationship engine *visible*. The ticker polls
`GET /v1/npc/{npc_id}/relationship/player_demo` (the EXP-50 route), stores a baseline
at session start, and displays deltas (e.g., `Mira: trust +2, affection +1`) in the
status overlay whenever values change.

Polling on every frame would flood the API. Use a TTL cache: re-poll only after
`RELATION_POLL_TTL_S = 4.0` seconds since the last fetch for a given NPC.

---

## New file: `demo_game/ui/relation_ticker.py`

```
Module: relation_ticker
Layer: demo_game
Purpose: Polls the relationship API for the active NPC→player_demo edge and surfaces
         trust/fear/affection deltas in the demo UI status overlay.
Dependencies: demo_game.client
Used by: demo_game.ui.game_window
```

```python
RELATION_POLL_TTL_S: float = 4.0
PLAYER_ID: str = "player_demo"
```

### `RelationTicker`

```python
@dataclass
class RelationSnapshot:
    """Immutable snapshot of a single RELATES_TO edge read."""
    trust: int
    fear: int
    affection: int
    interaction_count: int
```

`class RelationTicker`:

```
Attributes:
    _client: EngineClient
    _baseline: dict[str, RelationSnapshot]   — set on first successful fetch per NPC
    _current: dict[str, RelationSnapshot]    — last fetched value per NPC
    _last_poll: dict[str, float]             — monotonic timestamp of last poll per NPC
```

Public methods:

- `tick(npc_id: str) -> None` — if TTL expired for npc_id, poll client and update
  `_current[npc_id]`. If no baseline yet for npc_id, set `_baseline[npc_id] = _current[npc_id]`.
  Swallow `EngineClientError` silently (ticker is best-effort; never crash the frame loop).

- `get_delta_text(npc_id: str) -> str | None` — return a formatted string like
  `"trust +2  fear +0  affection +1"` comparing `_current` vs `_baseline`. Return None
  if no data yet. Only include fields whose delta ≠ 0 OR include all three always (your
  choice; all-three is simpler and more readable).

- `reset_baseline(npc_id: str) -> None` — promote current to baseline (call on NPC selection
  change so deltas reflect this session's changes, not stale ones from a prior NPC).

All three methods ≤ 40 lines each. Use `time.monotonic()` for TTL.

---

## Edit: `demo_game/ui/game_window.py`

`game_window.py` is currently 350 lines (DEC-074 waiver). Keep new code minimal.

1. Add to imports (TYPE_CHECKING block):
   ```python
   from demo_game.ui.relation_ticker import RelationTicker
   ```

2. In `GameWindow.__init__`, add:
   ```python
   self._relation_ticker: RelationTicker = RelationTicker(client)
   ```

3. In `GameWindow._draw_status_overlay()`, after the sandbox auto-tick line, add:
   ```python
   if self._active_npc_id:
       self._relation_ticker.tick(self._active_npc_id)
       delta_text = self._relation_ticker.get_delta_text(self._active_npc_id)
       if delta_text:
           rel_surf = self._font_nav.render(delta_text, True, (120, 200, 240))
           self._screen.blit(rel_surf, (8, WINDOW_H - NAV_BAR_H - 52))
   ```

4. Wire `reset_baseline` on NPC selection change. Find where `_active_npc_id` is set
   (likely in the event loop or NPC list click handler) and call
   `self._relation_ticker.reset_baseline(old_npc_id)` before updating.

Check that `_active_npc_id` attribute exists — if it's named differently, adapt. Do NOT
rename existing attributes.

---

## Tests: `demo_game/tests/test_relation_ticker.py`

All pure, no live API.

| Test | Scenario |
|------|----------|
| `test_tick_sets_baseline_on_first_fetch` | no prior data → baseline = current after first tick |
| `test_tick_respects_ttl_skips_refetch` | called twice within TTL → client called once |
| `test_tick_refetches_after_ttl_expires` | called with time advanced past TTL → client called twice |
| `test_get_delta_text_returns_none_before_any_tick` | no data yet → None |
| `test_get_delta_text_shows_zero_delta_on_same_values` | current == baseline → all zeros still shown |
| `test_get_delta_text_formats_positive_and_negative_deltas` | trust +3, fear -1 → includes both |
| `test_reset_baseline_promotes_current` | after reset, delta = 0 again |
| `test_tick_swallows_engine_client_error` | client raises → no exception propagates |

---

## Pre-merge checklist

- [ ] All new tests pass
- [ ] `relation_ticker.py` ≤ 300 lines
- [ ] Module and class docstrings present
- [ ] `game_window.py` line count checked — if it exceeds 350, add a DEC entry
- [ ] No layer violations (demo_game/ui imports demo_game.client only)
- [ ] No prompt strings added
