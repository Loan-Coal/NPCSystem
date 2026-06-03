# NPCSystem — Engine Roadmap (Phase 14 →)

**Status:** Phases 0–13 complete. This file is the **forward** roadmap only.

- Full history (Phases 0–13, engine audit, session log through S13.3) →
  `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md`.
- The 2026-06-01 Munich hackathon roadmap → `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md`.

**Sprint sequence:** the 2026-06-03 codebase review (BLOCK, 43 findings) means the
**review-remediation backlog likely precedes feature work** — see "Remediation backlog" below.
Default feature order if remediation is sequenced separately: **14 → 15 → 16**; Phase 17 (SDKs)
is a deferred commercial milestone.

---

## ⚠️ Remediation backlog (from the 2026-06-03 audit)

The audit returned **BLOCK**: 2 CRITICAL + 16 HIGH + 16 MEDIUM + 9 LOW. The actionable specs live in
`project-harness/review-fixes/` (FIX-SEV-01…18, organized into work Blocks A–F with a dependency-ordered
critical path in `review-fixes/INDEX.md`); the synthesis is `project-harness/REVIEW_FINDINGS.md`.

**This backlog is not yet phased.** Headline items that gate the product story:

- **SEV-01 (CRITICAL):** anti-hallucination guarantee unmeasured (matchers pass on empty/fallback/
  synonym/refusal; live eval 27/31). The moat is asserted, not proven.
- **SEV-02 (CRITICAL):** `demo_game` imports `npc_engine` internals — not a standalone client.
- **SEV-15/25 (HIGH):** `make lint` (38 ruff) + `make type` (254 mypy) red, not in CI.
- **SEV-04/03/14/12/11 (HIGH):** layer erosion, prompt-injection surface, `dict[Any,Any]` API boundary,
  no multi-tenant isolation, game cannot be won/lost.

**Decision owed (next session):** phase the remediation backlog vs. the feature phases below before building.

---

## Phase 14 — Proactive NPC-Initiated Dialogue
**Goal:** NPCs open conversations on their own — the autonomous world feels agentic, not reactive.
**Sessions:** 3–4
**Leverages:** Phase 1 tick driver + dialogue engine + S6.4 WS streaming.
**Note:** `agenda_engine.py` only resolves *political* agendas (vote tally → passed/failed). It does
**not** form conversational intent — S14.1 is net-new logic, not a wiring job.

- [ ] **S14.1** Intent-formation tick step — new file `engines/agenda/conversation_intent_service.py`
  (separate file per OCP): on tick, score whether an NPC wants to open dialogue with a co-located
  player from need thresholds / unresolved goals / recently witnessed events.
  - Exit: a hungry/threatened NPC produces a queued intent under autopilot.
- [ ] **S14.2** Intent queue + bounded backpressure — persist pending intents (graph or session store);
  cap per-NPC and global rate via config.
  - Exit: intents survive a tick and never grow unbounded.
- [ ] **S14.3** Delivery channel — push the proactive line over the WS dialogue path
  (or a `GET /v1/dialogue/pending` poll).
  - Exit: the client receives an unsolicited NPC line.
- [ ] **S14.4** Demo integration — surface an NPC hailing the player.
  - Exit: stand still in the demo → an NPC initiates a conversation.

## Phase 15 — Retrieval-Quality Evals
**Goal:** Prove the embedding/rerank stack retrieves the *right* memories, not just that tone is right.
**Sessions:** 2–3
**Leverages:** existing `embedding_index`, `cross_encoder_reranker`, `subgraph_retriever`,
`context_relevance_engine`, `context_scoring` — large stack, but only tone is currently evaluated.
**Tie-in:** overlaps SEV-01 (proving the moat) — sequence with the remediation backlog.

- [ ] **S15.1** Retrieval-inspection surface — `GET /v1/debug/retrieval?npc_id&query` returning the
  ranked context-item IDs (graph_admin scope).
  - Exit: endpoint returns deterministic ranked IDs for a seeded query.
- [ ] **S15.2** Precision matcher + cases — extend `evals/runner.py` (currently dialogue-only) to POST
  to the retrieval endpoint; add a `retrieval_precision` matcher computing precision@k / recall against
  a labeled relevant-set. ~6 cases over the seeded worlds.
  - Exit: `make eval-retrieval` reports precision@k.
- [ ] **S15.3** Headline retrieval metric — fold into `evals/summary.py` alongside the hallucination number.
  - Exit: a one-command run prints retrieval precision.

## Phase 16 — Content Moderation / Rating Guardrails
**Goal:** Configurable per-world content ceiling (ESRB/PEGI) — a buyer compliance checkbox.
**Sessions:** 2–3
**Leverages:** the S0.1 input chokepoint (`MAX_PLAYER_MESSAGE_CHARS` + injection guard).

- [ ] **S16.1** Config + schema — `CONTENT_RATING` setting (`everyone|teen|mature`, `Literal`) +
  per-world override; bounded enum.
  - Exit: rating is resolvable per world.
- [ ] **S16.2** Input moderation — extend the existing input guard to reject/redact over-ceiling player
  input at the API boundary.
  - Exit: over-ceiling input rejected with 422.
- [ ] **S16.3** Output moderation — prompt rule (in `prompts/` per layer rules) + post-generation check
  so NPC output respects the ceiling.
  - Exit: mature content suppressed under `everyone`; an eval case proves it.

## Phase 17 — Engine SDKs (Unity / Unreal) — DEFERRED MILESTONE
**Goal:** Drop-in plugins wrapping the REST/WS API — highest commercial ROI.
**Sessions:** 8+ (its own milestone, not a sprint task). Own-game milestone (Phase 7) is complete, so
this is now unblocked, but it is sequenced after the sprint above.

- [ ] **S17.1** OpenAPI contract freeze + versioned client spec.
- [ ] **S17.2** Unity C# package (REST + WS, auth, models).
- [ ] **S17.3** Unreal plugin (parity).
- [ ] **S17.4** Sample integration scene per engine + docs.

---

## Engine Scope Decisions (reference)

| Engine | Status | Decision |
|--------|--------|----------|
| gossip, emotion, need, mood, routine, agenda | works, ticks | Showcased (Phases 1, 6) |
| quest_generation, quest (lifecycle) | works | Showcased (Phases 2–3) |
| memory_consolidation | works | Showcased (S6.3 — headline feature) |
| chapter, story_pacing | works | Promoted to gameplay (Phase 7) |
| faction_politics, oath, treaty | complete | Completed + showcased (S2.3, S2.4, S6.2) |
| military | implemented | Implemented S6.5 (ISSUE-031) |
| reputation + gossip | works | Productized (Phase 8 networked reputation) |
| secrets, leverage, pledges, beliefs | works | One consequence surfaced (S6.2) |
| succession, clique | works, niche | Graveyard — kept in code |
| investigation, skill | works, niche | Graveyard — out of scope |

---

## Testing Strategy (forward)

`make test` + `make test-demo` green before every merge. New retrieval/moderation work ships with tests.
**Note (SEV-15/25):** `make lint` and `make type` are currently red and outside CI — fixing them
(FIX-SEV-15/14) is part of the remediation backlog, and `make check` cannot pass until then.

---

## Session Log (Phase 14 →)

| # | Date | Phase | What was done | Exit state |
|---|------|-------|---------------|------------|
| — | — | — | (Phases 0–13 log archived in `proposals/archive/ROADMAP_through_phase13_2026-06-03.md`) | — |
