# FIX-SEV-09 — Fix gossip: canonical events must not distort; corrected rumors must stop spreading

**Severity:** HIGH · **Confidence:** Confirmed (canonical) / Likely (corrected) · **Effort:** S
**Category:** correctness · **Absorbs:** ENG-01, ENG-11

## Problem
One query (`CYPHER_SELECT_EVENT`) is missing a column and a filter, so (a) canonical true facts are always distorted and written as `rumor`, and (b) an NPC whose rumor was corrected still re-propagates the lie.

## Current shape — `engines/gossip/gossip_handler.py`
- `:41-48`:
  ```cypher
  MATCH (a:Character {id: $sharer_id})-[k:KNOWS_ABOUT]->(e:Event)
  ... RETURN e.id AS event_id, e.summary AS summary, e.severity AS severity
  ORDER BY e.occurred_at DESC LIMIT 1
  ```
  Never returns `is_canonical`, so `:141` `event_record.get("is_canonical", False)` is always `False` → the canonical-skip branch in `engines/gossip/gossip_distort.py:93` is never taken (`is_canonical` is a real property: `type_registry/base_nodes/event.yaml:19`).
  No `knowledge_state` filter → a corrected event (receiver state set to `'corrected'` by `graph/rumor_trace_service.py:31-34`) is still selected as the freshest known event and re-shared.

## Target shape
The sharer-selection query returns `is_canonical`, excludes `corrected` events, and prefers canonical/undistorted events.

## Steps
1. Edit `CYPHER_SELECT_EVENT` `RETURN` to add `coalesce(e.is_canonical, false) AS is_canonical`.
2. Add to the `MATCH`/`WHERE`: `AND coalesce(k.knowledge_state, '') <> 'corrected'`.
3. (Optional, recommended) bias `ORDER BY` to prefer canonical / lower-distortion events so true facts spread over lies.
4. Keep the `event_record.get("is_canonical", False)` read — it now receives the real value.
5. (When SEV-04 lands, this query moves to `graph/gossip_queries.py`.)

## Verification
- Integration: seed a canonical Event, run `run_tick`; assert the resulting `KNOWS_ABOUT` edge has `distortion_type IS NULL` and `knowledge_state='knows'`. Parametrize `is_canonical` True/False.
- Integration: `correct_rumor_at_npc` on an NPC, run a gossip tick; assert they do **not** propagate the corrected event.

## Blast radius
Every gossip tick; the demo gossip path (`captain_sorn → mira_innkeeper → old_henryk`); the ACT-7 rumor-warfare "correct" win condition.
