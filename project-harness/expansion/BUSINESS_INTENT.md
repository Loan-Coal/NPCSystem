# Business Intent — NPC Engine (lens X0)

**Purpose:** This file is the product-thesis rubric for the expansion analysis. Every
downstream lens scores the codebase against the commitments, ambitions, success criteria,
and constraints captured here. Claims are cited `file:line` against the repo's own docs.

**Source docs read:** `project-harness/CLAUDE.md`, `project-harness/ROADMAP.md`,
`project-harness/FEATURES.md`, `project-harness/DECISIONS.md`,
`project-harness/FINAL_REVIEW_FINDINGS.md`, `docs/BUSINESS_REQUIREMENTS.md`,
`docs/overview.md`, `README.md`.

---

## 1. Thesis

NPC Engine is a **game backend / middleware licensed to game studios** that makes
non-player characters feel alive: it gives every NPC **persistent memory, relationships,
and emotional state** backed by a Neo4j knowledge graph and LLM-driven dialogue, and it
runs an **off-screen living world** (NPCs gossip, witness events, change opinions) even
when the player is not present (`docs/BUSINESS_REQUIREMENTS.md:5-9`,
`project-harness/CLAUDE.md` Orientation). The promised value is NPCs that respond in
character from what they actually know, remember shared history, and react to a changing
world — sold to studios as a **drop-in plugin for Unity and Unreal** behind a clean
HTTP + WebSocket API so the game never depends on engine internals
(`docs/BUSINESS_REQUIREMENTS.md:11-13`, `docs/overview.md:7-9`). The integration model is
**one local deployment per studio/game** (DEC-068): each studio clones and runs its own
Docker stack + Neo4j locally as part of its game distribution, and a single graph holds
exactly one game world — no multi-tenant `world_id`, isolation is infrastructure-level
(`project-harness/DECISIONS.md:637-642`, `project-harness/FEATURES.md:71-73`).

---

## 2. Explicit commitments (stated outright in the docs)

- **Persistent knowledge/relationships/emotion per NPC across the whole world** — `docs/BUSINESS_REQUIREMENTS.md:5-9`.
- **Off-screen simulation: NPCs gossip, witness events, change opinions while player is away** — `docs/BUSINESS_REQUIREMENTS.md:8-9`; gossip engine `docs/BUSINESS_REQUIREMENTS.md:122-139`.
- **Unity (C#) + Unreal (C++) plugin via REST + WebSocket, Blueprint-friendly shapes** — `docs/BUSINESS_REQUIREMENTS.md:11-22`, `docs/overview.md:7-9`.
- **Engine SDKs (Unity package + Unreal plugin) as the highest-ROI commercial milestone** — `project-harness/ROADMAP.md:87-95` (Phase 17, DEFERRED).
- **Anti-hallucination guarantee: NPCs answer only from known context** — `project-harness/FEATURES.md:31-33`; asserted-not-proven flag SEV-01 `project-harness/ROADMAP.md:24-25`, `project-harness/FINAL_REVIEW_FINDINGS.md:115`.
- **Structured dialogue output: response + action + facial_expression + relation_deltas + mood_update** — `docs/BUSINESS_REQUIREMENTS.md:106-111`, `project-harness/FEATURES.md:14`.
- **Graceful degradation: full → graph_only → canned; never a hard error to the player** — `project-harness/FEATURES.md:14,79-81`, `docs/BUSINESS_REQUIREMENTS.md:115`.
- **WebSocket token streaming so the player sees the NPC "thinking"** — `docs/BUSINESS_REQUIREMENTS.md:114`, `project-harness/FEATURES.md:49`.
- **Pluggable LLM backend: add a backend by creating one file + one factory line; no game-code change** — `docs/BUSINESS_REQUIREMENTS.md:236,241`, `project-harness/FEATURES.md:26` (Ollama built-in; no OpenAI adapter ships — `project-harness/CLAUDE.md` Stack).
- **Designer extensibility: new node/edge types and event templates via YAML, no core code edits** — `project-harness/FEATURES.md:73-74`, `docs/BUSINESS_REQUIREMENTS.md:235,50-51`.
- **API-key auth on every route except `GET /health`; 401/403 no-body; `/v1/admin/*` split** — `project-harness/FEATURES.md:41-42`, `project-harness/CLAUDE.md` Security; route split DEC-013 `project-harness/DECISIONS.md:202-211`.
- **Rate limiting + per-key WebSocket connection cap + idempotency header** — `project-harness/FEATURES.md:43-44`.
- **Bounded relation mutation (per-turn + windowed caps, clamp [0,100], audit delta_log)** — `docs/BUSINESS_REQUIREMENTS.md:193-205`.
- **Deterministic, replayable gossip distortion (omission/exaggeration/role_swap/timeline_shift), seeded RNG logged** — `docs/BUSINESS_REQUIREMENTS.md:133-137`, `project-harness/FEATURES.md:15`.
- **Quest lifecycle with atomic reward/currency/item transfer (single transaction)** — `project-harness/FEATURES.md:19`.
- **Win AND lose reachable game loop** — `project-harness/FEATURES.md:32`, `project-harness/FINAL_REVIEW_FINDINGS.md:115`.
- **Scheduler: realtime + game_driven clock (`POST /clock/advance`), tick lease** — `docs/BUSINESS_REQUIREMENTS.md:209-218`, `project-harness/FEATURES.md:28`.
- **Reliability contracts: Neo4j down → `GraphUnavailableError` → 503; LLM timeout → canned; errors redacted at boundary** — `project-harness/FEATURES.md:77-82`, `project-harness/CLAUDE.md` Error handling.
- **Forward feature roadmap: Phase 14 proactive NPC-initiated dialogue, Phase 15 retrieval-quality evals, Phase 16 content-rating guardrails** — `project-harness/ROADMAP.md:35-85`.

---

## 3. Implied ambitions (strongly implied, not stated as commitments)

- **Agentic NPCs that initiate, not just react** — Phase 14 goal "autonomous world feels agentic, not reactive"; intent-formation is net-new logic, not yet built (`project-harness/ROADMAP.md:35-53`). Implies a self-driving NPC behavior loop beyond request/response.
- **Provable retrieval quality (precision@k / recall on a labeled relevant-set), not just tone** — the whole stack (embedding_index, cross_encoder_reranker, subgraph_retriever) exists but only tone is evaluated; Phase 15 implies "the right memories are retrieved" is a sellable bar (`project-harness/ROADMAP.md:55-70`).
- **Client codegen / typed contract as a real integrator deliverable** — OpenAPI currently emits empty bodies for ~120 routes, so "client codegen is not yet usable"; the SDK ambition (Phase 17) implies a frozen, typed OpenAPI contract is required (`project-harness/FEATURES.md:60-62`, `project-harness/ROADMAP.md:92`, `project-harness/FINAL_REVIEW_FINDINGS.md:69-71`).
- **Buyer-facing compliance posture (ESRB/PEGI content ceiling per world)** — Phase 16 frames content moderation as "a buyer compliance checkbox" (`project-harness/ROADMAP.md:72-85`), implying enterprise/store-certification readiness.
- **A non-code designer surface (graph viewer, NPC authoring, draft approval, analytics)** — the static-SPA dashboard for narrative designers (`project-harness/DECISIONS.md:32-41`) implies a content-authoring tool tier alongside the runtime API.
- **Production-grade multi-instance operation** — README "What's next" lists Redis-backed session/emotion stores, multi-instance concurrency, TLS (`README.md:37`); NFRs target 99.5% uptime, ≥200 pairs/tick, ≥10k nodes (`docs/BUSINESS_REQUIREMENTS.md:34-37`). Implies scaling beyond single-stream prototype.
- **OCP-clean expansion seams for the stated roadmap** — CLAUDE.md mandates add-by-new-file for distortion types, emotion models, LLM backends; the review found these seams missing (closed if-chains, no `EmotionModelProtocol`, no `location_writer.py`), implying low-friction extensibility is a core selling point that is not yet met (`project-harness/FINAL_REVIEW_FINDINGS.md:50-52,72-74,93-94`).
- **First-run-clean distribution** — under DEC-068 each studio clones + boots locally, so "a fresh checkout boots" is an implied product requirement; the review found a fresh build cannot boot (`project-harness/FINAL_REVIEW_FINDINGS.md:18-21,62`).

---

## 4. Success criteria (the rubric a studio judges the engine by)

The concrete bar an integrating studio would hold the engine to:

1. **NPCs never assert facts they don't know** — anti-hallucination must be *measured*, not asserted; eval battery must fail on empty/fallback/synonym/refusal answers, not pass on deflections (`project-harness/ROADMAP.md:24-25`, `project-harness/FINAL_REVIEW_FINDINGS.md:40-44,115`). (ASSUMPTION: a published precision/recall + hallucination-rate number is the buyer-facing metric — Phase 15 implies this but no target number is committed.)
2. **An NPC can be hailed proactively** — standing still in the world produces an unsolicited, in-character NPC line (`project-harness/ROADMAP.md:36,52-53`).
3. **Retrieval returns the right memories** — precision@k / recall against a labeled relevant-set, surfaced as a one-command headline metric (`project-harness/ROADMAP.md:55-70`). (ASSUMPTION: target precision@k is undefined in docs.)
4. **Client codegen works** — OpenAPI emits typed response bodies for all routes so a Unity/Unreal client can be generated (`project-harness/FEATURES.md:60-62`, `project-harness/ROADMAP.md:92`).
5. **Integrator hello-world is fast and clean** — a fresh checkout boots (`docker-compose up -d` → seed → talk), the demo is a *standalone* client with zero imports from engine internals (SEV-02), and the scripted demo runs end-to-end (`project-harness/CLAUDE.md` Key commands, `project-harness/ROADMAP.md:26`, `project-harness/FINAL_REVIEW_FINDINGS.md:18-21,115`). (ASSUMPTION: target is "<10 min from clone to first NPC line" — no explicit time bar is committed in the docs.)
6. **Degradation is invisible to the player** — LLM timeout / token-budget overflow / Neo4j outage degrade to canned or 503 cleanly, never a stack trace; errors are redacted at the boundary (`project-harness/FEATURES.md:77-82`). (Note: ISSUE-059 currently degrades knowledge-heavy NPCs to canned — a live failure of this bar — `project-harness/FEATURES.md:80-81,87`.)
7. **The world runs off-screen at scale** — gossip ≥200 pairs/tick, graph ≥10k nodes, deterministic replay from logged seed (`docs/BUSINESS_REQUIREMENTS.md:34-35,242-243`).
8. **Designers extend without engineers** — add a node/edge type or event template via YAML, swap the LLM backend, advance the clock manually — all with no game-code or core-code change (`docs/BUSINESS_REQUIREMENTS.md:233-241`, `project-harness/FEATURES.md:73-74`).
9. **Auth and input safety hold** — every route but `/health` authed; player input capped; prompt-injection fenced (SEV-03 currently unmitigated — a gap against this bar) (`project-harness/CLAUDE.md` Security, `project-harness/FINAL_REVIEW_FINDINGS.md:68`).
10. **Relation values cannot be griefed into extremes** — per-turn + windowed delta caps with audit log (`docs/BUSINESS_REQUIREMENTS.md:193-205`).

---

## 5. Design constraints (any expansion must honor these)

All cite `project-harness/CLAUDE.md` unless noted.

- **Single-tenant deployment (DEC-068)** — one Docker+Neo4j stack per studio/game; one world per graph; do NOT add a multi-tenant `world_id` to the schema (`project-harness/DECISIONS.md:637-642`). Expansions assume single-world isolation is infrastructure-level.
- **Layer model, dependencies point downward only** — `api/auth/data → engines/scheduler → services/cache → retrieval → graph/mutation/world → config/common/type_registry/schema/utils`; enforced by `make check-layers` (CLAUDE.md Architecture).
- **Forbidden cross-layer patterns** — no LLM in `graph/` or `retrieval/` (LLM only in `engines/`); no Neo4j/Cypher outside `graph/`; no prompt strings outside `prompts/` (versioned YAML only); no HTTP calls between services (CLAUDE.md "Forbidden cross-layer patterns").
- **SOLID, OCP add-by-new-file (strict)** — new LLM backends, distortion types, emotion models are added by creating a new file, never editing a closed engine file; engines depend on `LLMClientProtocol`, concrete deps injected via `__init__`; `api/dependencies.py` is the sole composition root (CLAUDE.md Coding principles → SOLID).
- **300-line non-test file limit; 40-line function limit; ≤3 nesting levels** — splits required before merge, exceptions need a DECISIONS entry (CLAUDE.md Code style / Structure). (Note: 40-line/nesting rules are ungated and widely violated — `project-harness/FINAL_REVIEW_FINDINGS.md:72`.)
- **Pydantic v2 for all cross-boundary data; Literal/Enum for fixed sets; no raw `dict` across a module boundary** (CLAUDE.md Types and models). The API contract surface currently violates this (`ok_response → dict[str,Any]`, raw dicts in generic graph services — `project-harness/FINAL_REVIEW_FINDINGS.md:46-47,69-71,79`).
- **Custom exception hierarchy in `utils/errors.py`; never swallow errors; fail fast at boundaries; documented fallback contracts** (CLAUDE.md Error handling).
- **Async all the way; semaphore for batch; lock for shared `emotion_store`/`session_store`** (CLAUDE.md Async).
- **Token budget enforced (Tier0+TierA non-droppable, Tier B trimmed first); structured output validated through a Pydantic model; prompt assembly is pure/idempotent** (CLAUDE.md Prompt hygiene; DEC-057 `project-harness/DECISIONS.md:15-23`).
- **Schema/interface changes and new dependencies require human approval** — changing a public interface with external callers, the graph node/edge schema, CI config, or a layer rule all require a stop-and-ask (CLAUDE.md "Asking before doing").

---

## Open questions (for OPEN_QUESTIONS collection)

- No committed numeric target for hallucination rate or retrieval precision@k (success criteria 1 & 3).
- No committed time bar for integrator hello-world (success criterion 5).
- Multi-instance / production-scale ambitions (`README.md:37`) coexist with the single-stream prototype NFRs and DEC-068 single-tenant model — scope of "production hardening" vs. single-deployment intent is unresolved.
- "Highest commercial ROI" SDKs (Phase 17) are deferred behind an unphased remediation backlog (`project-harness/ROADMAP.md:9-31,87-90`) — sequencing of commercialization vs. hardening is an open business call.
