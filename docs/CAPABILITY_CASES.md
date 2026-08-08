# Capability Cases — Contract and Coverage

A **capability case** (`case_pos_*`) proves that an NPC *can* surface a fact it
demonstrably holds, given a fair player prompt. It is the positive counterpart to the
guard battery's adversarial and refusal tests.

## What a capability case asserts

A `case_pos_*` case must satisfy all three of the following:

1. **Grounded fact** — the NPC holds the fact through at least one of:
   - a `KNOWS_ABOUT` edge (direct or gossip-distorted event knowledge)
   - a `BELIEVES` edge (a held belief)
   - a `HAS_MEMORY` edge (a personal memory or witnessed event)
   - a `HAS_GOAL` edge (an active goal)
   - a `HAS_SECRET` edge (a secret the NPC keeps)

   Facts invented by the model (hallucinations) do not qualify.

2. **Eliciting message** — the `input.player_message` is a *fair* prompt that a
   player might naturally ask. It must not lead the NPC, supply the answer, or use
   insider phrasing from the knowledge-graph node.

3. **Dual-failure expectation** — the `expected` judges must fail on both:
   - **Refusal**: an NPC that says "I don't know" or deflects completely must fail.
   - **Fabrication**: an NPC that invents a *different* fact must also fail (use
     `keyword_any` with tokens from the grounded fact, or a `tone_judge` that
     requires engagement with the specific domain).

## YAML contract

Every `case_pos_*` file must include:

```yaml
case_id: case_pos_<npc_id>_<short_slug>           # must start with case_pos_
description: >
  <One sentence describing the grounded fact and why the NPC should surface it.>
seed:
  npc_id: <npc_id>                                 # stable NPC node ID
  player_id: player_eval
  requires_world: <demo | village | tavern>        # world the NPC lives in
input:
  player_message: "<fair eliciting prompt>"
expected:
  - kind: schema                                   # structural sanity check (always include)
  - kind: keyword_any | tone_judge | affirms_judge # at least one content judge
    # ... judge-specific fields ...
notes: >
  Grounding: <edge_type>(<npc_id>, <fact_node_id>). Brief authoring notes.
```

Optional but encouraged:
- `relevant_node_ids: [<node_id>, ...]` — lists the graph nodes involved; used by the
  judge prompt builder for context retrieval.

## Coverage rule

Every `Character` node in the demo world with at least one grounded knowledge edge
must have at least one `case_pos_*` file referencing it with `requires_world: demo`.

The test `tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case`
enforces this rule and names uncovered NPCs as a work-list for authoring sessions.

## Seeded NPCs with grounded knowledge

### Demo world (`requires_world: demo`)

| NPC ID | Grounding edges | Notes |
|---|---|---|
| `mira_innkeeper` | `KNOWS_ABOUT northern_war_begins` (gossip) | Epistemic hedging required |
| `aldric_merchant` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY` | Merchant/economic domain |
| `captain_sorn` | `KNOWS_ABOUT northern_war_begins` (direct) | Confident, no hedging |
| `lira_fence` | `KNOWS_ABOUT market_fire`, `HAS_GOAL`, `HAS_SECRET` | Criminal domain |
| `old_henryk` | `KNOWS_ABOUT northern_war_begins` (2-hop distorted) | Rambling, garbled OK |
| `sera_barmaid` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | EXP-223 |
| `harwick_guard` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | EXP-223 |
| `nel_pickpocket` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | EXP-223 |
| `bren_smith` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |
| `nessa_priestess` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |
| `dorn_dockmaster` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |
| `vex_spymaster` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |
| `tilda_herbalist` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |
| `garrick_deserter` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY`, `HAS_SECRET` | H2.2 |

### Village world (`requires_world: village`)

Village NPCs with grounding are covered separately; see `seeds/worlds/seed_village_world.py`.

### Tavern world (`requires_world: tavern`)

Tavern NPCs with grounding are covered separately; see `seeds/worlds/seed_tavern_world.py`.

## Authoring guidance

- **Write the grounding first.** Confirm the NPC actually has the knowledge edge before
  writing the player message. Check `demo_game/seeds/seed.py` or `demo_game/seeds/seed_npc_data.py`.
- **Keyword lists over semantic judges** when the fact has strong surface tokens (war,
  trade, blight). Use `tone_judge` when the correct answer is about engagement style
  (e.g., criminal willingness), not specific tokens.
- **Complement, don't duplicate.** Check `case_neg_*` files for the same NPC — the
  capability case and its guard counterpart form a pair. The positive case should use a
  different player message than the negative guard.
- **`notes` field** must identify the grounding edge type and node ID so cases are
  traceable to the graph.
