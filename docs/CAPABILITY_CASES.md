# Capability Cases — Contract and Coverage

A **capability case** (`case_pos_*`) proves that an NPC *can* surface a fact it
demonstrably holds, given a fair player prompt. It is the positive counterpart to the
guard battery's adversarial and refusal tests.

## What a capability case asserts

A `case_pos_*` case must satisfy all three of the following:

1. **Grounded fact** — the NPC holds the fact through at least one of:
   - a `KNOWS_ABOUT` edge (direct or gossip-distorted event knowledge)
   - a `BELIEVES` edge (a held belief)
   - a `REMEMBERS` edge (a personal memory or witnessed event)
   - a `PURSUES` edge (an active goal)
   - a `KNOWS_SECRET` edge (a secret the NPC keeps)

   Facts invented by the model (hallucinations) do not qualify.

   > **Corrected 2026-08-10.** This list previously read `HAS_MEMORY`, `HAS_GOAL` and
   > `HAS_SECRET`. Those three relationship types do not exist — the registry
   > (`GET /v1/admin/schema/registry`) names them `REMEMBERS`, `PURSUES` and
   > `KNOWS_SECRET`. `evals/case_drafts.py::GROUNDED_EDGE_TYPES` still carries the wrong
   > three and returns HTTP 422 for them; see ISSUE-148.

   **Read the grounding through the typed admin endpoints**, not the generic graph
   reader: `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}`. The generic
   `GET /v1/graph/nodes/Belief` and `GET /v1/graph/edges/BELIEVES` routes return empty
   for seeded inner life (ISSUE-148), so "the graph says this NPC has nothing" is not a
   safe conclusion to draw from them.

2. **Eliciting message** — the `input.player_message` is a *fair* prompt that a
   player might naturally ask. It must not lead the NPC, supply the answer, or use
   insider phrasing from the knowledge-graph node.

3. **Dual-failure expectation** — the `expected` judges must fail on both:
   - **Refusal**: an NPC that says "I don't know" or deflects completely must fail.
   - **Fabrication**: an NPC that invents a *different* fact must also fail (use
     `keyword_any` with tokens from the grounded fact, or a `tone_judge` that
     requires engagement with the specific domain).

4. **Ungameable by a knowledge-free response** (EVAL-P20.2) — the case must FAIL when
   the "response" is an echo of its own `player_message`, and FAIL against the reference
   always-hedge responder. Both are enforced by
   `tests/unit/evals/test_capability_echo_resistance.py`.

   The practical rule that satisfies this: **draw `keyword_any` tokens from the grounded
   fact's text, never from the player prompt.** The audit found one canned hedge passing
   6 of 7 capability cases precisely because the two vocabularies were the same one —
   `case_pos_aldric_trade_disruption` asks about *war* and *trade* and then scores on
   `war` and `trade`.

   Measure it with `make hedge-probe` (`scripts/hedge_responder_probe.py`). It substitutes
   one canned response for every NPC answer and runs the real matchers over the result, so
   the number it prints is the number a live run would print for that text. The reference
   hedge is deliberately stocked with the battery's own surface vocabulary — a bland
   "I could not say" scores 0.143 and would let the gate read green while proving nothing.

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

`tests/unit/evals/test_capability_coverage.py` enforces this rule against a
`UNCOVERED_BASELINE` ratchet. **As of EVAL-P20.2 (2026-08-10) that baseline is empty**:
all 14 grounded demo NPCs have a case, so any NPC that loses one — or any newly-grounded
NPC seeded without one — turns the module red.

**Coverage is not capability.** The ratchet asks whether a case exists, never whether it
passes. Nine of the sixteen cases currently FAIL against the live engine because the
dialogue context arrives with no beliefs, goals or memories in it (ISSUE-145). That is the
capability battery reporting a real defect, which is what it is for.

## Seeded NPCs with grounded knowledge

### Demo world (`requires_world: demo`)

| NPC ID | Grounding edges | Notes |
|---|---|---|
| `mira_innkeeper` | `KNOWS_ABOUT northern_war_begins` (gossip) | Epistemic hedging required |
| `aldric_merchant` | `BELIEVES`, `HAS_GOAL`, `HAS_MEMORY` | Merchant/economic domain |
| `captain_sorn` | `KNOWS_ABOUT northern_war_begins` (direct) | Confident, no hedging |
| `lira_fence` | `KNOWS_ABOUT market_fire`, `HAS_GOAL`, `HAS_SECRET` | Criminal domain |
| `old_henryk` | `KNOWS_ABOUT northern_war_begins` (2-hop distorted) | Rambling, garbled OK |
| `sera_barmaid` | `REMEMBERS mem_sera_barmaid_0` | EXP-223 · what she overheard, not her own secret |
| `harwick_guard` | `BELIEVES bel_harwick_guard_71e419d6` | EXP-223 · the south gate unease |
| `nel_pickpocket` | `BELIEVES bel_nel_pickpocket_77ebc2b0`, `PURSUES goal_nel_pickpocket_0` | EXP-223 · Lira's tests |
| `bren_smith` | `BELIEVES bel_bren_smith_10b4fcfc`, `REMEMBERS mem_bren_smith_0` | H2.2 · the guard's tithe |
| `nessa_priestess` | `PURSUES goal_nessa_priestess_0`, `BELIEVES bel_nessa_priestess_9bfffc52` | H2.2 · temple neutrality |
| `dorn_dockmaster` | `BELIEVES bel_dorn_dockmaster_1a330af7` | H2.2 · manifest vs. real ledger |
| `vex_spymaster` | `PURSUES goal_vex_spymaster_0`, `BELIEVES bel_vex_spymaster_4fd4429b` | H2.2 · the accord |
| `tilda_herbalist` | `PURSUES goal_tilda_herbalist_0` | H2.2 · northwood bark supply |
| `garrick_deserter` | `BELIEVES bel_garrick_deserter_b070850f`, `REMEMBERS mem_garrick_deserter_0` | H2.2 · the Legion's conduct |

The nine rows above list the *specific* node each EVAL-P20.2 case is grounded in, because
"this NPC has some beliefs" is not enough to author against — the case has to name the one
fact it expects to surface, and that node id goes in `relevant_node_ids`.

**Secrets are deliberately absent from the grounding column.** A capability case grounded
in `KNOWS_SECRET` would reward an NPC for disclosing what it is meant to keep, which is
the guard battery's business. Where an NPC's most distinctive material is a secret
(`sera_barmaid`, `nel_pickpocket`), the case is grounded in the adjacent belief or memory
instead.

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
