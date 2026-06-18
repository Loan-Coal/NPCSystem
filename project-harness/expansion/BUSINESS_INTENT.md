# Business Intent — NPC Engine (lens X0)

**Purpose:** This file is the product-thesis rubric for the expansion analysis. Every
downstream lens scores its proposals against the commitments, ambitions, success criteria,
and constraints captured here. Every claim is cited `file:line` against the repo's own docs.

**Codebase state at time of writing:** Phases 0–26 complete. `make check` green (1967 passed,
22 skipped, 85.70% coverage). Branch: `munich-demo`. Date: 2026-06-11.

**Source docs read (in priority order):**
- `project-harness/CLAUDE.md` (orientation, layer model, SOLID/OCP)
- `project-harness/ROADMAP.md` (forward roadmap — phases 0–26 complete, Phase X SDK deferred)
- `project-harness/archive/stale-2026-06/FEATURES.md` (capability inventory — cross-checked against live `src/npc_engine/engines/`)
- `project-harness/archive/review-2026-06-03/FINAL_REVIEW_FINDINGS.md` (9-lens review, expansion readiness §L7)
- `project-harness/archive/review-2026-06-03/review-evidence/final/L7-expansion.md` (expansion blockers ranked)
- `project-harness/archive/review-2026-06-03/review-evidence/final/L6-product.md` (capability matrix)
- `project-harness/ISSUES.md` (ISSUE-055, ISSUE-057, ISSUE-059 — verified FIXED)
- `project-harness/DECISIONS.md` (DEC-068 deployment model; DEC-013 route split; DEC-057 budget enforcer)
- `docs/BUSINESS_REQUIREMENTS.md`, `docs/overview.md`

---

## 1. Thesis

NPC Engine is a **game backend licensed to game studios as middleware** that makes
non-player characters feel alive by giving every NPC **persistent memory, relationships,
and emotional state** backed by a Neo4j knowledge graph and LLM-driven dialogue
(`project-harness/CLAUDE.md:10-12`, `docs/overview.md:1-3`). It runs an **off-screen living
world** — NPCs gossip, witness events, and change opinions even when the player is not
present — and surfaces this state through natural player↔NPC conversations grounded in
what each NPC actually knows (`docs/BUSINESS_REQUIREMENTS.md:5-9`). The engine is sold as a
**drop-in plugin for Unity and Unreal** games, exposed behind a clean HTTP + WebSocket API
so the game never imports engine internals (`docs/BUSINESS_REQUIREMENTS.md:11-13`,
`docs/overview.md:7-9`, `project-harness/CLAUDE.md:12`). The integration model is
**one local deployment per studio/game** (DEC-068): each studio runs its own Docker stack +
Neo4j as part of its game distribution; a single graph holds exactly one game world; isolation
is infrastructure-level, with no multi-tenant `world_id` in the schema
(`project-harness/DECISIONS.md:691-696`, `project-harness/archive/stale-2026-06/FEATURES.md:71-73`).

---

## 2. Explicit commitments (stated outright in the docs, each with file:line)

- **Persistent NPC knowledge, relationships, and emotional state across the whole game world**
  — `docs/BUSINESS_REQUIREMENTS.md:5-9`; `project-harness/CLAUDE.md:10-12`.

- **Off-screen simulation: NPCs gossip, witness events, form opinions while player is away**
  — `docs/BUSINESS_REQUIREMENTS.md:8-9`; gossip requirements `docs/BUSINESS_REQUIREMENTS.md:122-139`.

- **Unity (C#) + Unreal (C++) plugin integration via REST + WebSocket, Blueprint-friendly shapes**
  — `docs/BUSINESS_REQUIREMENTS.md:17-22`, `docs/overview.md:7-9`.

- **Engine SDKs (Unity package + Unreal plugin) named as the "highest commercial ROI" deferred milestone**
  — `project-harness/ROADMAP.md:37-43` (Phase X, DEFERRED pending OpenAPI contract freeze).

- **Anti-hallucination guarantee: NPCs answer only from known context (Rule 5 in system_v1.yaml)**
  — `project-harness/archive/stale-2026-06/FEATURES.md:31-33`; measured by a 23-case eval battery
  (`evals/cases/case_adv_*`, `case_neg_*`); matchers hardened to reject empty/canned/short answers
  (L6-product.md:65-73).

- **Structured dialogue output: npc_response + action + facial_expression + relation_deltas + mood_update**
  — `docs/BUSINESS_REQUIREMENTS.md:106-111`; `project-harness/archive/stale-2026-06/FEATURES.md:14`.

- **Tiered graceful degradation: full LLM → graph_only → canned fallback; never a hard error to the player**
  — `project-harness/archive/stale-2026-06/FEATURES.md:14,79-81`; `docs/BUSINESS_REQUIREMENTS.md:115`.
  NOTE: ISSUE-059 (tier-A unbounded → canned) was FIXED in EXP-30 (pinned-core + ranked-pool model;
  `TokenBudgetExceededError` on tier0+tierA now structurally impossible) — `project-harness/ISSUES.md:895-903`.

- **WebSocket token streaming so the player sees the NPC "thinking"**
  — `docs/BUSINESS_REQUIREMENTS.md:114`; `project-harness/archive/stale-2026-06/FEATURES.md:49` (`WS /v1/ws/dialogue`).

- **Pluggable LLM backend: add a backend by creating one file + registering it; no game-code change**
  — `docs/BUSINESS_REQUIREMENTS.md:241`; `project-harness/archive/stale-2026-06/FEATURES.md:26`
  (Ollama built-in; `LLMClientProtocol` + factory registry; no OpenAI adapter ships today —
  `project-harness/CLAUDE.md:22-23`).

- **Designer extensibility: new node/edge types and event templates via YAML, no core code edits**
  — `project-harness/archive/stale-2026-06/FEATURES.md:73-74`; `docs/BUSINESS_REQUIREMENTS.md:235,50-51`;
  type-registry OCP mechanism verified clean by L7-expansion.md:52-55 (L7-05 positive attestation).

- **API-key auth on every route except `GET /health`; 401/403 with no body detail; `/v1/admin/*` route split**
  — `project-harness/archive/stale-2026-06/FEATURES.md:41-42`; `project-harness/CLAUDE.md:462-464`;
  route split DEC-013 `project-harness/DECISIONS.md:255-263`.

- **Rate limiting (token bucket, SHA-256 keyed) + per-key WebSocket connection cap + idempotency header support**
  — `project-harness/archive/stale-2026-06/FEATURES.md:43-44`.

- **Bounded relation mutation: per-turn + windowed delta caps; clamp [0, 100]; audit delta_log**
  — `docs/BUSINESS_REQUIREMENTS.md:193-205`; `project-harness/CLAUDE.md:457-458`.

- **Deterministic, replayable gossip distortion (omission / exaggeration / role_swap / timeline_shift);
  RNG seed logged per tick**
  — `docs/BUSINESS_REQUIREMENTS.md:133-137`; `project-harness/archive/stale-2026-06/FEATURES.md:15`;
  `project-harness/CLAUDE.md:445-447` (RNG seed logging strict rule).

- **Quest lifecycle with atomic reward/currency/item transfer (single Neo4j transaction)**
  — `project-harness/archive/stale-2026-06/FEATURES.md:19`; L6-product.md:62-63.

- **Win AND lose reachable game loop**
  — `project-harness/archive/stale-2026-06/FEATURES.md:32`; L6-product.md:43-53.

- **Scheduler: realtime + game_driven clock; `POST /clock/advance` with `delta_ticks` bounded [1, 1000]**
  — `docs/BUSINESS_REQUIREMENTS.md:209-218`; `project-harness/CLAUDE.md:460`.

- **Reliability contracts: Neo4j down → `GraphUnavailableError` → HTTP 503; LLM timeout → canned;
  errors redacted at API boundary (no node ids / schema paths / stack traces leak)**
  — `project-harness/archive/stale-2026-06/FEATURES.md:77-82`; `project-harness/CLAUDE.md:410-416`.

- **Demo standalone client — zero imports from `src/npc_engine/` inside `demo_game/`**
  — `project-harness/CLAUDE.md:50-53`; verified clean L6-product.md:37-40 (SEV-02 holds).

- **Client-supplied stable IDs on typed admin endpoints (beliefs, goals, memories, secrets); MERGE semantics**
  — ISSUE-055 FIXED 2026-06-10 in KE-6 (`project-harness/ISSUES.md:866-873`).

- **Location hierarchy (PART_OF edges between Location nodes)**
  — ISSUE-057 FIXED 2026-06-10 in EXP-87 (`project-harness/ISSUES.md:875-882`);
  `type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` created.

---

## 3. Implied ambitions (strongly implied by the docs, not stated as formal commitments)

- **Agentic NPCs that initiate, not just react** — Phase 14 ("autonomous world feels agentic, not
  reactive") added `proactive_dialogue_engine`; wired into `tick_scheduler`
  (`project-harness/ROADMAP.md:11` Phase 14 reference). The docs frame this as a product differentiator
  beyond request/response loops.

- **Provable retrieval quality (precision@k / recall on a labeled relevant-set), not just tone** —
  the full retrieval stack (embedding index, cross-encoder reranker, subgraph retriever) exists, but
  only tone and anti-hallucination are measured by the eval battery. Phase 15 (retrieval-quality evals)
  implies "the right memories are retrieved" becomes a sellable headline metric
  (`project-harness/ROADMAP.md:11` Phase 15 reference).

- **Typed, frozen OpenAPI contract as an integrator deliverable** — SDK ambition (Phase X ROADMAP)
  explicitly sequences after "OpenAPI contract freeze + versioned client spec"
  (`project-harness/ROADMAP.md:39`). Phases 20 added `OkEnvelope[T]` + per-route `response_model=`
  (ISSUE-052 FIXED); `make check` enforces typed bodies via S20.6 contract test.

- **Content-rating compliance posture (ESRB/PEGI ceiling per world)** — Phase 16 is described as
  "a buyer compliance checkbox" in the Phase 14–26 archive; implies enterprise/store-certification
  readiness as a commercial feature.

- **A non-code designer surface for narrative designers** — the static-SPA `dashboard/` (DEC-053,
  `project-harness/DECISIONS.md:85-94`) with graph viewer, NPC authoring, and analytics implies a
  content-authoring tier alongside the runtime API, not just a developer API.

- **Production-scale multi-instance operation** — NFRs target ≥200 gossip pairs/tick, ≥10k nodes,
  99.5% uptime (`docs/BUSINESS_REQUIREMENTS.md:34-37`); Redis-backed session/emotion stores and
  multi-instance concurrency are listed as future hardening. These coexist with the current
  single-stream prototype reality under DEC-068.

- **OCP-clean extensibility as a commercial moat** — CLAUDE.md mandates add-by-new-file for distortion
  types, emotion models, and LLM backends; this is presented as a developer user story
  (`docs/BUSINESS_REQUIREMENTS.md:241`). Two of these three seams are still OCP-incomplete:
  distortion type is a closed if-chain (L7-01, `L7-expansion.md:8-17`) and there is no
  `EmotionModelProtocol` (L7-06, `L7-expansion.md:59-65`).

- **First-run-clean distribution** — under DEC-068, each studio clones and boots locally, so "a
  fresh checkout boots in minutes" is an implied product requirement
  (`project-harness/DECISIONS.md:694-695`). The CRITICAL L9-01 boot failure (deleted
  `game_schema.yaml`) was fixed before Phase 14 began.

- **Temporal NPC cognition** — Phase 26 introduced `occurred_at_game_time`/`is_historical` on Memory
  nodes and a HEARSAY vs MY_ACCOUNT context channel, enabling NPCs to distinguish long-past experience
  from current rumour (`project-harness/ISSUES.md:14-23`). The implied ambition is NPCs that reason
  about time, not just facts.

---

## 4. Success criteria (the rubric a studio judges the engine by)

Each criterion is grounded in stated commitments or measurable behaviors. Assumptions are flagged.

1. **NPCs never assert facts they don't know** — the anti-hallucination guarantee must be
   *measured, not asserted*; the 23-case guard battery must pass with zero hallucination failures
   and must reject empty/canned/short/deflection answers. Matchers and `summary.guarantee_demonstrated`
   are hardened for this (`project-harness/archive/review-2026-06-03/review-evidence/final/L6-product.md:65-73`,
   `project-harness/ISSUES.md:895-903`). ASSUMPTION: no committed hallucination-rate number exists;
   Phase 15 implies a precision@k/recall headline will be the eventual commercial target.

2. **Retrieval returns the right memories** — context assembled per dialogue turn contains the most
   relevant events/memories for this NPC at this tick, measured by precision@k / recall against a
   labeled relevant-set (`project-harness/ROADMAP.md:11` Phase 15 intent). ASSUMPTION: target
   precision@k is not yet defined in the docs.

3. **Degradation is invisible to the player** — LLM timeout / token-budget overflow / Neo4j outage
   degrade to canned fallback or HTTP 503 cleanly; no stack trace, no schema leak; archetype-specific
   canned lines served (ISSUE-081 FIXED). ISSUE-059 (knowledge-heavy NPC canned degradation) is FIXED
   in EXP-30 (`project-harness/ISSUES.md:895-903`).

4. **Client codegen works** — OpenAPI emits typed, non-empty response bodies for every route
   (enforced by the S20.6 contract test after Phases 20–21);
   a Unity/Unreal stub client can be auto-generated
   (`project-harness/archive/stale-2026-06/FEATURES.md:60-62`).

5. **Integrator hello-world is fast and clean** — `docker-compose up -d` → `make demo-seed` →
   first NPC line succeeds on a fresh checkout; `make demo-run` passes end-to-end; `demo_game/`
   has zero `npc_engine` imports (SEV-02 holds)
   (`project-harness/CLAUDE.md:27-44`, `project-harness/archive/review-2026-06-03/review-evidence/final/L6-product.md:37-40`).
   ASSUMPTION: no committed "minutes from clone to first NPC line" target exists.

6. **Off-screen world runs at stated scale** — gossip ≥200 NPC pairs/tick; knowledge graph
   ≥10k nodes; distortion deterministically replayable from logged RNG seed
   (`docs/BUSINESS_REQUIREMENTS.md:34-35`).

7. **Designers extend without engineers** — add a node/edge type via YAML, swap the LLM backend,
   advance the clock manually — all with zero game-code or core-engine edits
   (`docs/BUSINESS_REQUIREMENTS.md:233-241`,
   `project-harness/archive/stale-2026-06/FEATURES.md:73-74`).

8. **Relation values cannot be griefed into extremes** — per-turn + windowed delta caps with audit
   log; values clamp to [0, 100]; `RelationDeltaExceededError` raised with full context on overflow
   (`docs/BUSINESS_REQUIREMENTS.md:193-205`).

9. **Auth and input safety hold at every boundary** — every route except `/health` authed;
   `player_message` capped at `MAX_PLAYER_MESSAGE_CHARS`; `delta_ticks` bounded [1, 1000]; prompt
   injection fenced (SEV-03 prompt-injection guard remains partially unmitigated per the review —
   `project-harness/archive/review-2026-06-03/FINAL_REVIEW_FINDINGS.md:68`)
   (`project-harness/CLAUDE.md:459-464`).

10. **NPCs proactively initiate in-character** — the tick scheduler can produce an unsolicited,
    in-character NPC line without a player prompt; this is demonstrable in the scripted demo
    (Phase 14 proactive dialogue, wired in `tick_scheduler.py`)
    (`project-harness/ROADMAP.md:11` Phase 14 reference).

---

## 5. Bounds and non-goals

All cite `project-harness/DECISIONS.md` or `project-harness/CLAUDE.md` unless noted.

- **NO multi-tenant isolation in the graph** — DEC-068 closes this explicitly: one Docker+Neo4j
  per studio; one world per graph; do NOT add `world_id` to nodes or queries
  (`project-harness/DECISIONS.md:691-696`).

- **NO Unity/Unreal SDK shipped today** — Phase X (SDK) is the highest-ROI commercial milestone but
  explicitly DEFERRED until the OpenAPI contract is frozen; it is NOT in the current forward roadmap
  (`project-harness/ROADMAP.md:37-43`).

- **NO per-player authentication or OAuth** — auth is a shared-secret API key per deployment;
  per-player sessions and OAuth are out of scope (`docs/BUSINESS_REQUIREMENTS.md:76-79`).

- **NO voice synthesis or lip sync in-engine** — TTS is a pluggable hook (`TTSClientProtocol`) with
  graceful failure; rendering of expressions/animations is the game engine's responsibility
  (`docs/BUSINESS_REQUIREMENTS.md:118`, `project-harness/archive/stale-2026-06/FEATURES.md:24`).

- **NO LLM calls in `graph/` or `retrieval/`** — LLM lives in `engines/` only; hard layer rule
  enforced by `make check-layers` (`project-harness/CLAUDE.md:114-118`).

- **NO prompt strings in Python** — all LLM-facing content lives in versioned YAML under
  `src/npc_engine/prompts/`; root `prompts/` holds canned/eval only (L6-02 doc-drift noted;
  `project-harness/archive/review-2026-06-03/review-evidence/final/L6-product.md:169-188`).

- **NO niche engines in active development** — succession, clique, investigation, and skill engines
  are "kept in code, no active dev" (ROADMAP Engine Scope Decisions table,
  `project-harness/ROADMAP.md:49-59`).

- **NO HTTP calls between services** — services compose in-process; HTTP is only at the API boundary
  (`project-harness/CLAUDE.md:118`).

- **NO multi-instance/Redis scaling today** — session and emotion stores are in-process; Redis-backed
  stores are a future hardening milestone, not yet scoped
  (`docs/BUSINESS_REQUIREMENTS.md:32-37` NFRs vs current prototype state).

- **NO live runtime config mutation** — `Settings` is a frozen `lru_cache` singleton; live PATCH of
  engine cadence/budget is WONTFIX (ISSUE-051, DEC-054/055)
  (`project-harness/ISSUES.md:251-258`, `project-harness/DECISIONS.md:95-109`).

- **Large-file and structural limits are hard constraints on any expansion** — 300-line non-test file
  limit, 40-line function limit, ≤3 nesting levels; violations require a DECISIONS entry
  (`project-harness/CLAUDE.md:127-130`, `project-harness/CLAUDE.md:388-391`).

- **Schema and public-interface changes require human approval** — changing a graph node/edge schema,
  a public interface with external callers, CI config, or any layer rule requires a stop-and-ask
  (`project-harness/CLAUDE.md:344-354`).

---

## Open questions (for downstream lenses and OPEN_QUESTIONS.md)

1. No committed numeric target for hallucination rate or retrieval precision@k (success criteria 1 & 2).
2. No committed time bar for "hello-world from clone" (success criterion 5).
3. Two OCP seams are still incomplete: distortion type (closed if-chain, L7-01) and emotion model
   (no `EmotionModelProtocol`, L7-06) — which has the higher near-term expansion value?
4. Multi-instance ambitions (NFRs: 99.5% uptime, Redis) coexist with the DEC-068 single-deployment model —
   the scope of "production hardening" vs. single-game-deployment intent is an open commercial call.
5. The highest-ROI commercial milestone (SDK, Phase X) is gated on an OpenAPI contract freeze already
   achieved (Phases 20–21); what is the sequencing rationale for not yet promoting Phase X to active?
