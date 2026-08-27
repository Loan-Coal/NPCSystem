# Engine Eval Coverage — what a judge can actually measure

**Status:** EVAL-P25.1. Gated by `scripts/check_engine_coverage.py`
(`make check-engine-coverage`), tested by `tests/unit/scripts/test_check_engine_coverage.py`.
**Measured:** 2026-08-27, against the working tree.

## Why this table exists before any case is authored

DEC-214 spent a whole session remediating A/B arms that were declared before their supply
had been measured. The same rule applied to cases is: **measure observability before
authoring**. A capability case written against an engine that never reaches
player-visible NPC speech passes unconditionally — the NPC says something plausible, the
matcher finds a token, and the case scores a point that carries no information. That
pushes the judged battery's pass base rate back toward 1.0, and a base rate at the ceiling
is precisely what crushes kappa (`project-harness/EVAL_P25_TO_P31_PLAN.md` §0:
`affirms_judge` sits at 96.3% raw agreement and kappa 0.530 because almost every row is a
pass).

So an unclassified engine is not a documentation gap. It is a case-authoring hazard, and
it is gated as one.

## The classification criterion

Exactly one bucket per unit, decided by **where the engine's output lands**, not by how
important the engine is:

| bucket | test applied | what it means for cases |
|---|---|---|
| `dialogue_observable` | the engine's output reaches the **serialized dialogue context** — a `CONTEXT_SLOTS` row with `default_enabled=True` (`src/npc_engine/retrieval/context/context_slots.py`), or the speech path itself | a `case_pos_*` can be authored against it |
| `state_observable` | the effect is real but is verifiable only by reading the graph back | belongs in a deterministic check or an `evals/scenario_adapters*.py` scenario, never the judged battery |
| `not_observable` | infrastructure — no behaviour of its own that a response could carry. **The reason is mandatory** and the gate enforces it | out of scope; already covered by unit/integration tests |

`serialize_context` emits exactly the slots with `default_enabled=True`, and a slot with
`default_enabled=False` is **absent from the JSON entirely** — so a `default_enabled=False`
slot is a decisive `state_observable` verdict, not a judgement call. That is what settles
`oath` below.

## Two findings this audit produced, recorded because they change what is authorable

**1. `beliefs` is serialized but no prompt rule reads it.** `system_v1.yaml` names
`context.world`, `context.player_reputation`, `context.npc.emotion`, `context.npc.profile`,
`context.npc_known_events`, `context.recent_session_turns`, `context.npc.goals` (Rule 7),
`context.propagated_reputation` (Rule 13), `context.retrieved_context` (Rule 17) and
`context.npc.memories` (Rule 15). It never names `context.npc.beliefs`. Beliefs are
produced, ranked, charged to the token budget and serialized — and nothing instructs the
model to speak from them. Eight of the sixteen pre-EVAL-P26.2 capability cases are grounded
in a `BELIEVES` edge, as are eight of the thirty authored in EVAL-P26.2. They are the
hardest cases in the set, and this is why. Logged as
ISSUE-231; **not fixed here** — this session touches no `src/` file.

**2. `proactive_dialogue` produces NPC speech that the case runner cannot reach.** It is
`dialogue_observable` by the criterion above and by nothing else: the package's own
docstring says it does not wire into the scheduler, and `evals/` has no proactive turn
shape. Classified honestly and logged as ISSUE-232 rather than quietly demoted, because
demoting it would hide a judgeable engine behind an infrastructure excuse.

## The table

<!-- ENGINE-COVERAGE-TABLE: BEGIN -->
| Unit | Kind | Classification | Evidence | Why not observable |
| --- | --- | --- | --- | --- |
| `dialogue` | package | `dialogue_observable` | the speech path itself: prompt_builder, response_parser, dialogue_handler | — |
| `emotion` | package | `dialogue_observable` | slot `emotion` (tier0, pinned); system_v1 Rule 3 reads context.npc.emotion.current_mood | — |
| `mood` | package | `dialogue_observable` | mood contagion writes the same per-NPC emotion state the `emotion` slot serializes; Rule 3 | — |
| `events` | package | `dialogue_observable` | slot `event:` to context.npc_known_events; Rule 5 makes that list the anti-hallucination whitelist | — |
| `gossip` | package | `dialogue_observable` | slot `event:` carrying distorted_summary and knowledge_state; Rules 5 and 9 branch on rumor vs fact | — |
| `memory` | package | `dialogue_observable` | slot `memories` to context.npc.memories; Rule 15 | — |
| `memory_consolidation` | package | `dialogue_observable` | writes Memory nodes into the same `memories` slot; Rule 15 | — |
| `knowledge_learning` | package | `dialogue_observable` | writes Belief nodes into slot `beliefs` (serialized; NO prompt rule reads it, ISSUE-231) | — |
| `deception` | package | `dialogue_observable` | writes is_deception Belief nodes into slot `beliefs` (serialized; no prompt rule, ISSUE-231) | — |
| `need` | package | `dialogue_observable` | slot `top_need` to context.npc.top_need, tierB default_enabled | — |
| `planning` | package | `dialogue_observable` | forms goals into slot `goals` (Rule 7) and dispatches moves seen in slot `location:` | — |
| `routine` | package | `dialogue_observable` | moves characters, changing slot `location:` and slot `nearby_npcs` | — |
| `reputation` | package | `dialogue_observable` | slot `propagated_reputation`; Rule 13 branches on knowledge_state for each act | — |
| `relationship` | package | `dialogue_observable` | derive_standing feeds the STANDING= line; Rule 16 sets tone from it | — |
| `faction_politics` | package | `dialogue_observable` | drifts world.faction_standings, inside the pinned tier0 `world` slot; Rule 1 | — |
| `quest` | package | `dialogue_observable` | slot `active_quest` (pinned, default_enabled); Rule 11 sets action.target_id from it | — |
| `interaction` | package | `dialogue_observable` | negotiation_context.inject_active_negotiation adds active_negotiation post-serialization | — |
| `proactive_dialogue` | package | `dialogue_observable` | generates an in-character NPC line via LLM — but is unwired from the scheduler and unreachable from the case runner (ISSUE-232) | — |
| `agenda` | package | `state_observable` | resolves agenda/vote nodes and scores intents; no context slot carries either | — |
| `chapter` | package | `state_observable` | writes a narrative chapter label to the graph; no CONTEXT_SLOTS row carries it | — |
| `clique` | package | `state_observable` | derives clique membership from affection; not serialized (slot `group_memberships` is default_enabled=False) | — |
| `currency` | package | `state_observable` | bounded currency transfers, audited in the graph; no context slot | — |
| `director` | package | `state_observable` | DirectorDecision gates the events engine; the decision itself never enters context | — |
| `economy` | package | `state_observable` | deterministic prices in the graph; reaches speech only through interaction's negotiation item, which is that engine's row | — |
| `investigation` | package | `state_observable` | investigation nodes and clue links, graph-verified only | — |
| `military` | package | `state_observable` | battle resolution and resource yield through MilitaryGraphPort; no context slot | — |
| `oath` | package | `state_observable` | slot `active_pledges` exists but is default_enabled=False, so serialize_context omits it entirely (ISSUE-200 orphan) | — |
| `player_model` | package | `state_observable` | perceived_trust/perceived_intent persist via graph/player_model_writer; no CONTEXT_SLOTS row | — |
| `quest_generation` | package | `state_observable` | slot-filling and graph validation are graph-checkable; its text reaches speech only as quest's `active_quest` slot | — |
| `scheming` | package | `state_observable` | scheme nodes and step advancement; detection deferred, nothing serialized | — |
| `skill` | package | `state_observable` | XP and levels through SkillGraphPort; no context slot | — |
| `story_pacing` | package | `state_observable` | writes pacing multipliers to WorldState; they gate other engines rather than being spoken | — |
| `succession` | package | `state_observable` | grants vacant titles on the graph; no context slot | — |
| `treaty` | package | `state_observable` | treaty expiry and condition checks on the graph; no context slot | — |
| `base_engine` | module | `not_observable` | abstract async engine contract with no domain behaviour — nothing to elicit | defines the tick interface only |
| `contracts` | package | `not_observable` | per-engine metadata schema validated fail-fast at startup | startup configuration, never part of a turn |
| `embedding_invalidation` | module | `not_observable` | best-effort index invalidation helper | changes index freshness, has no speech behaviour of its own |
| `embedding_refresh` | module | `not_observable` | pairs invalidation with insert behind the corpus-freeze flag (DEC-210) | affects which nodes RAG can retrieve; retrieval exposure is measured by make eval-arm-probe gate 4, not by a case |
| `idempotency` | package | `not_observable` | Neo4j-backed transport replay persistence and expiry | transport plumbing; a replayed request is the same turn, not a different NPC |
| `llm` | package | `not_observable` | backend adapters and the registry/factory | every judged response passes through it, so it has no behaviour a case could isolate; model identity is pinned by evals/model_identity |
| `llm_config_models` | module | `not_observable` | Pydantic models for per-engine LLM config YAML | typed config only, loads no files and selects no adapter |
| `llm_runtime_config` | module | `not_observable` | loads and validates per-engine LLM config at startup | startup completeness check; no runtime behaviour in a turn |
| `ports` | package | `not_observable` | structural graph-access Protocols (DEC-122 / SEV-24) | type declarations with no runtime behaviour at all |
| `tts` | package | `not_observable` | Piper/mock TTS adapters and emotion-to-voice modulation | synthesises audio from text already judged; the eval corpus is text |
<!-- ENGINE-COVERAGE-TABLE: END -->

## The split, and what it means

**18 `dialogue_observable` of 44 units** — 16 `state_observable`, 10 `not_observable`.

The large `not_observable` bucket is the correct outcome, not a failure to find coverage.
`ports` is Protocol declarations; `contracts` and `llm_runtime_config` are startup
validation; `idempotency` is transport plumbing; `tts` synthesises audio from text that
was already judged. Manufacturing cases for any of them would produce cases that pass
unconditionally — the exact defect this phase exists to remove.

The 16 `state_observable` engines are **not** out of scope for evaluation. They are out of
scope for the *judged* battery. Their home is a deterministic matcher or a scenario
adapter, where kappa is 1.0 by construction and the reliability tax is zero
(EVAL_P25_TO_P31_PLAN.md §1).

## What EVAL-P26.2 may author against

Of the 18 `dialogue_observable` units, the ones with **seeded, per-NPC, addressable**
content in the three worlds — and therefore the ones a case can be grounded in today —
are: `events` and `gossip` (KNOWS_ABOUT with knowledge_state and distorted_summary),
`memory` (REMEMBERS), `knowledge_learning` and `deception` (BELIEVES), `planning`
(PURSUES), `reputation` (propagated_reputation), and `dialogue` itself. `emotion`, `mood`,
`routine`, `relationship`, `faction_politics`, `need`, `quest` and `interaction` are
dialogue-observable but carry no per-NPC seeded fact to elicit, so a case against them
would be measuring the prompt, not the engine.

See `docs/REASONING_DIMENSIONS.md` for the dimensions those grounded engines are authored
across, and `docs/CAPABILITY_CASES.md` for the per-case contract.
