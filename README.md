# NPC Engine

A game backend service that gives non-player characters persistent knowledge, relationships, and emotional state — driving natural conversations and off-screen world simulation via Neo4j + local LLM.

## What's done

| Area | Status |
|---|---|
| Graph layer (Character, Event, Location, WorldState nodes + edges) | ✅ |
| Type registry (base_nodes/*.yaml, base_edges/*.yaml, extension fields, enum extensions) | ✅ |
| Auth middleware (Bearer token, scope inheritance graph_admin ⊃ graph_write) | ✅ |
| Idempotency (header-enforced, Neo4j-persisted) | ✅ |
| Dialogue engine (context tiers A/B, LLM call, response parse, relation mutation) | ✅ |
| Dialogue context cache (in-memory, TTL + graph-version invalidation) | ✅ |
| Graceful degradation tiers (full → graph_only → canned) | ✅ |
| Gossip engine (deterministic distortion, KNOWS_ABOUT propagation) | ✅ |
| Event engine (event pool, location scoping, awareness seeding) | ✅ |
| Emotion engine (valence/arousal/label, decay, dialogue mood update) | ✅ |
| Quest lifecycle (offer → accept → progress → evaluate → reward) | ✅ |
| Embedding reconciler (UNION ALL label-filtered scan, is_active exclusion) | ✅ |
| Scheduler (realtime + game_driven clock, tick lease) | ✅ |
| Generic graph API (registry-driven, pagination, generic node/edge CRUD) | ✅ |
| Schema introspection endpoint (`GET /v1/schema/registry`) | ✅ |
| Eval harness (Layer 1+2 matchers, markdown report, `make eval`) | ✅ |
| E2E scenario tests (transcript output, `make scenarios`) | ✅ |
| Docs (ARCHITECTURE.md, DATA_MODELS.md, BUSINESS_REQUIREMENTS.md, RELEVANCE_WEIGHTS.md) | ✅ |
| Migration scripts (001_remove_current_location_id, 002_remove_event_participants) | ✅ |
| Proposals (delta_log_options, prompt_inventory) | ✅ |

## What's next

- **Task 5 Phase 2** — Extract prompts into versioned YAML files (`proposals/prompt_inventory.md` is ready; awaiting approval).
- **delta_log cap** — Pick one of the three options in `proposals/delta_log_options.md` and implement it.
- **Archetype-aware canned responses** — `dialogue_handler.py` currently passes `archetype="default"` to the canned tier; wire in a lightweight graph lookup to pick the right archetype YAML.
- **Structured output strategy** — `proposals/structured_output_strategy.md` (GBNF/Outlines recommendation) not yet written.
- **Custom type engine consumption** — `custom_node_types` and `custom_edge_types` are parsed but not consumed by gossip/dialogue/event engines; startup warning is in place.
- **Production hardening** — Redis-backed session/emotion stores, multi-instance concurrency, TLS, rate limiting.
- **LLM judge (Layer 3 eval)** — `tone_judge` matcher is a stub; wire in LLM-as-judge for subjective tone/empathy checks.

## Quick start

```bash
# Requirements: Python 3.14+, Neo4j 5, Ollama with qwen2.5:7b

docker-compose up -d   # start Neo4j + API server
make demo-seed         # seed demo world (idempotent)
make demo              # open interactive pygame window

# Run unit tests:
make test

# Run eval cases (requires running server):
make eval
```

## Quoting eval metrics

Any published rate or kappa in this file (guard rate, capability rate, per-scorer
calibration kappa, ...) must carry a machine-checked citation immediately after it:

```
<value> of guard turns pass.
<!-- metric gen_id="<gen_id>" field="guard_rate" value="<value>" n="<n>" -->
```

`field` is `adversarial_rate`, `anti_hallucination_rate`, `capability_rate`, or
`kappa:<scorer>`.

There is deliberately no `guard_rate`. It was retired by DEC-243: it aggregated two
populations scored by different expectation sets — `case_adv_*`/`case_neg_*` on the YAML
battery, `ah_demo_*` on `refusal_judge` and `anti_hallucination_grounded` — so one number
meant two things. Measured on `k3_77688e7_regen1` the two sit 6.4 pp apart (0.8468 over
n=111 against 0.9106 over n=123), and the easier battery was more than half the
denominator. Cite the population you mean; a citation naming `guard_rate` fails the build.
`tests/unit/evals/test_readme_numbers_are_sourced.py` resolves every citation against the
committed artifact it names and fails the build on any mismatch — see
`docs/SCORER_TRUST_POLICY.md` for what kappa licenses publication in the first place, and
`docs/EVAL_METHODOLOGY.md` for what each metric measures and does not measure. Never quote
a number here without one of these comments.

## Key files

| File | Purpose |
|---|---|
| [npc_engine/main.py](npc_engine/main.py) | FastAPI app entry point and lifespan |
| [npc_engine/config.py](npc_engine/config.py) | All environment settings |
| [npc_engine/engines/dialogue/](npc_engine/engines/dialogue/) | Dialogue orchestration, degradation tiers |
| [npc_engine/type_registry/](npc_engine/type_registry/) | Schema contracts and runtime registry |
| [npc_engine/retrieval/](npc_engine/retrieval/) | Context assembly, cache, embedding reconciler |
| [prompts/canned/](prompts/canned/) | Canned response YAML files per archetype |
| [evals/](evals/) | Eval runner, matchers, cases, reports |
| [tests/scenarios/](tests/scenarios/) | E2E story scenarios with transcript output |
| [proposals/](proposals/) | Design proposals (delta_log, prompt inventory) |
| [docs/RELEVANCE_WEIGHTS.md](docs/RELEVANCE_WEIGHTS.md) | Relevance weight formula and examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture doc |
