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

## What's next

**[project-harness/ROADMAP.md](project-harness/ROADMAP.md) holds the current phase and the
next task**; open problems are in
[project-harness/ISSUES.md](project-harness/ISSUES.md).

This section used to list seven items by hand. It is a pointer now because five of the
seven had been delivered and nobody had come back to cross them off: prompts moved into
versioned YAML under [prompts/](prompts/), `tone_judge` became a live LLM judge rather
than a stub, and three of the remaining items cited a `proposals/` directory the repo no
longer has. A hand-maintained roadmap in a README competes with the roadmap and loses
(R4.6).

## Quick start

```bash
# Requirements: Python 3.14+, Neo4j 5, Ollama with qwen2.5:7b

# On Windows, BEFORE cloning. Without it the checkout aborts with
# "fatal: unable to checkout working tree" and leaves the tree incomplete:
# some paths under project-harness/archive/ exceed the 260-character default.
git config --global core.longpaths true

cp .env.example .env   # .env is gitignored; only .env.example is tracked
pip install -e .[dev]

docker-compose up -d   # start Neo4j + API server
make demo-seed         # seed demo world (idempotent)
make demo              # open interactive pygame window

# Run unit tests:
make test

# Run integration tests (needs the test compose override, DEC-232 — the base
# compose alone does not publish bolt to the host):
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d neo4j
NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password   make test-integration

# Run eval cases (requires running server):
make eval
```

## The anti-hallucination guarantee is not currently published

Retired as a claim on 2026-09-02 (DEC-250). Measured on that date, through the same
expectation set the engine is scored with and with both LLM judges live: a canned hedge that
asserts nothing scores **37/37 = 1.000** on the adversarial battery, against the engine's
0.8468 — and `tone_judge`, one of the four expectations injected into every guard case, has
κ=0.8493 with a 95% CI of [−0.0100, 1.0000].

The battery therefore does not distinguish the engine from a fixed string, and the judge
licenses no publication. **No anti-hallucination rate is published anywhere, and none should be
quoted.** The battery, the judges and the calibration are retained as regression tests — a
smoke alarm, not a measuring instrument. The citation policy below still governs any number
that is quoted.

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
| [src/npc_engine/main.py](src/npc_engine/main.py) | FastAPI app entry point and lifespan |
| [src/npc_engine/config.py](src/npc_engine/config.py) | All environment settings |
| [src/npc_engine/engines/dialogue/](src/npc_engine/engines/dialogue/) | Dialogue orchestration, degradation tiers |
| [src/npc_engine/type_registry/](src/npc_engine/type_registry/) | Schema contracts and runtime registry |
| [src/npc_engine/retrieval/](src/npc_engine/retrieval/) | Context assembly, cache, embedding reconciler |
| [prompts/canned/](prompts/canned/) | Canned response YAML files per archetype |
| [evals/](evals/) | Eval runner, matchers, cases, reports |
| [e2e/scenarios/](e2e/scenarios/) | E2E story scenarios with transcript output |
| [docs/overview.md](docs/overview.md) | Repo layout, stack, and where things live |
| [docs/RELEVANCE_WEIGHTS.md](docs/RELEVANCE_WEIGHTS.md) | Relevance weight formula and examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture doc |
| [project-harness/ROADMAP.md](project-harness/ROADMAP.md) | Current phase and the next task |

`make check-readme-paths` fails on any link in this file that points at nothing, so the
table cannot drift back to a source layout the repo no longer has (R4.6).
