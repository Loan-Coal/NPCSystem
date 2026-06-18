# EXP-81 — Cross-session "Remembers You" Demo Beat

**Phase:** 2 · **Effort:** M · **Deps:** EXP-30 (done), EXP-50 (done)
**Touches:** new `demo_game/remembers_you_beat.py`, `demo_game/run.py`
**Does NOT touch:** `demo_game/run_scenes.py`, `demo_game/client.py`

---

## Orchestrator pre-dispatch action (BEFORE this worker starts)

The orchestrator must add `get_npc_relationship` to `demo_game/client.py` before
dispatching this worker (and EXP-91, which needs the same method). Do not add it in
this worker — the orchestrator owns client.py edits for this batch.

```python
def get_npc_relationship(self, npc_id: str, other_id: str) -> dict | None:
    """Fetch RELATES_TO edge properties between two characters via EXP-50 route.

    Args:
        npc_id: Source character node ID.
        other_id: Target character node ID.

    Returns:
        Dict with trust, fear, affection, interaction_count fields, or None on 404.

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

Prove that NPC memory of the player persists across sessions. The engine stores a
`RELATES_TO` edge from every NPC to characters they've interacted with. That edge
carries `trust`, `fear`, `affection`, and `interaction_count`. With EXP-30 landed,
these values are now in Tier-A context (via `player_relation` — see EXP-11). The demo
beat shows:

1. The raw relationship values before the dialogue turn.
2. A dialogue from `mira_innkeeper` that should reference the prior relationship
   (if trust > 0, she speaks warmly; if 0, she's neutral/curious).

Use `mira_innkeeper` → `player_demo`. If no edge exists yet (fresh world, no prior
conversations), the beat prints "no prior relationship" and skips the dialogue — dry
and graceful.

---

## New file: `demo_game/remembers_you_beat.py`

```
Module: remembers_you_beat
Layer: demo_game
Purpose: RemembersYouBeat demo scene — fetches NPC→player RELATES_TO edge and fires
         a "do you remember me?" dialogue turn to showcase cross-session memory.
Dependencies: demo_game.client, demo_game.constants
Used by: demo_game.run
```

Single `@dataclass` class `RemembersYouBeat(Scene)`:

```python
@dataclass
class RemembersYouBeat(Scene):
    """Fetch the NPC→player RELATES_TO edge and fire a memory-recall dialogue."""
    npc_id: str = "mira_innkeeper"
    player_id: str = "player_demo"
```

`execute(self, runner: DemoRunner) -> None`:

1. Print step header.
2. If dry_run, return.
3. Call `runner.client.get_npc_relationship(self.npc_id, self.player_id)`.
4. If None: `runner.print_ok("[skip] No prior relationship edge — run demo again after first session")` and return.
5. Print relationship values: trust, fear, affection, interaction_count.
6. Post dialogue: `runner.client.post_dialogue(player_id=self.player_id, npc_id=self.npc_id, player_message=_MEMORY_MESSAGE)`.
7. Print the first 120 chars of `npc_response`.

Module-level constant `_MEMORY_MESSAGE: str = "Do you remember the last time we spoke?"`.

Keep `execute` ≤ 40 lines. No try/except — errors propagate (standard scene contract).

---

## Edit: `demo_game/run.py`

1. Add to the imports block:
   ```python
   from demo_game.remembers_you_beat import RemembersYouBeat
   ```

2. Append ACT 9 to the SCENES list (after the current last item):
   ```python
   NarratorCue(name="act9_narrator", delay_before_ms=800,
       text="ACT 9 — Memory: The innkeeper recalls your history."),
   RemembersYouBeat(name="act9_remembers_you"),
   ```

---

## Tests: `demo_game/tests/test_remembers_you_beat.py`

All tests use a mock runner (no live API calls).

| Test | What it asserts |
|------|----------------|
| `test_execute_skips_on_no_edge` | `get_npc_relationship` returns None → dialogue NOT called |
| `test_execute_prints_relation_and_calls_dialogue` | edge returned → `post_dialogue` called with correct npc_id/player_id |
| `test_execute_dry_run_skips_all_api_calls` | dry_run=True → no API calls |
| `test_execute_uses_memory_message_constant` | `post_dialogue` called with `_MEMORY_MESSAGE` |

---

## TDD order

1. Write `test_execute_skips_on_no_edge` → confirm it fails (ImportError).
2. Scaffold `RemembersYouBeat` in new file → test goes red (expected assert).
3. Implement `execute()` → tests green.
4. Add run.py import + SCENES entry.
5. Run `make test-demo`; gate on zero new failures.

---

## Pre-merge checklist

- [ ] All new tests pass
- [ ] `remembers_you_beat.py` ≤ 300 lines, `execute()` ≤ 40 lines
- [ ] Module docstring present
- [ ] No layer rule violations (demo_game imports demo_game.client only)
- [ ] No prompt strings added (dialogue message is a Python constant, not a YAML prompt — this is a demo client call, not an LLM prompt template)
