# HANDOFF — Track B (EVAL-P25.1, EVAL-P25.2, EVAL-P26.2)

**Session:** 2026-08-27, branch `eval-ab-context-arms`.
**Why this file exists:** Track A ran concurrently. `Makefile`, `ROADMAP.md`, `ISSUES.md`
and `DECISIONS.md` would have collided (`.PHONY` is a single continued line), so nothing in
this session touched them. Everything below is for a serial integration step to apply
verbatim.

**Zero `src/` files were touched.** `git status` before applying anything: the tree may
still carry a concurrent EVAL-P10 session's uncommitted `src/` work (ISSUE-139).

---

## 0. The one thing that is time-sensitive

`resolve_harness_version` hashes the recursive set of `.yaml` case files, and `compare.py`
**refuses** to pair two runs whose `harness_version` differs. This session added 30 case
files, so `harness_version` has moved. That is the comparability key working correctly, and
it means:

> **The case set must be frozen before the EVAL-P28 labelling run. One more case authored
> after labelling begins invalidates the pairing.**

---

## 1. What landed

| file | status |
|---|---|
| `docs/ENGINE_EVAL_COVERAGE.md` | new — 44 units classified, 18 / 16 / 10 |
| `scripts/check_engine_coverage.py` | new — the gate |
| `tests/unit/scripts/test_check_engine_coverage.py` | new — 15 tests incl. the RED anchor |
| `docs/REASONING_DIMENSIONS.md` | new — D1–D5, contracts and prefixes |
| `docs/CAPABILITY_CASES.md` | edited — dimension section, live village/tavern grounding tables, corrected `HAS_GOAL`/`HAS_MEMORY`/`HAS_SECRET` rows, case count |
| `evals/cases/case_pos_{evk,cause,prov,var}_*.yaml` | new — 30 cases |

**Measured results.** `make lint check-evals-rules type-evals test-cov-evals` clean
(1007 passed, coverage 79.76% against a 75% floor). `check-docstrings` and
`check-conservation` clean. `pytest tests/unit/evals/test_capability_coverage.py
tests/unit/evals/test_capability_echo_resistance.py tests/unit/evals/test_case_annotations.py`
→ 57 passed. `make hedge-probe` → **6/46, rate 0.130, gate met (< 0.30)**; all six are the
pre-existing `GAMEABLE_BASELINE` cases and none of the 30 authored here is beaten by the
echo or by the canned hedge.

Not done, and deliberately: `make check` is **not** wired to the new gate (§2), and no
`case_seq_*` multi-turn case was authored (EVAL-P27 owns that).

---

## 2. Makefile — recipes to add

Add the target (near the other `check-*` gates):

```makefile
# check-engine-coverage: EVAL-P25.1. Fail when a unit exists under src/npc_engine/engines/
# with no classification row in docs/ENGINE_EVAL_COVERAGE.md. Measuring observability before
# authoring is DEC-214's supply-before-declaration rule applied to cases: a case grounded in
# an engine that never reaches NPC speech passes unconditionally.
check-engine-coverage:
	$(PYTHON) scripts/check_engine_coverage.py
```

Add `check-engine-coverage` to the `check` target's prerequisite list, after
`check-evals-rules`:

```makefile
check: lint check-rules check-evals-rules check-engine-coverage check-layers check-docstrings type type-evals check-harness check-human-gates check-test-quality check-conservation check-label-survival test-cov test-cov-evals
```

Add `check-engine-coverage` to the `.PHONY` continued line.

---

## 3. ROADMAP.md — checkboxes to tick

Three, all in Program 4. Tick the box only; leave the body text as written.

- **`- [x] **EVAL-P25.1**`** (line ~3468). Landed complete: doc, gate, tests, RED anchor
  confirmed failing before the row exists. One deviation from the body text — *"wire into
  `make check`"* is **not** done; it is §2 of this handoff, for integration.
- **`- [x] **EVAL-P25.2**`** (line ~3473). Landed complete. One deviation: the prefixes are
  `case_pos_cause_*` / `case_pos_prov_*` / `case_pos_var_*`, compound rather than bare — see
  DEC-220 below for why.
- **`- [x] **EVAL-P26.2**`** (line ~3489). Landed under its ratchet clause at 30 authored
  (16 → 46). Closes ISSUE-147.

The `⏸️ *(human authoring)*` marker on EVAL-P26.2 was relaxed deliberately, with the live
graph as the grounding source and the echo/hedge gates as the guard. **The maintainer
should review the authored set before EVAL-P26.3 is ticked** — that is the review this
relaxation is predicated on.

---

## 4. DECISIONS.md — full text of new entries

### DEC-220: dimension case-id prefixes are compound under `case_pos_`, not bare

**Date:** 2026-08-27
**Phase:** EVAL-P25.2
**Status:** Accepted

`EVAL_P25_TO_P31_PLAN.md` §3 proposed `case_cause_*`, `case_prov_*`, `case_var_*`. They
ship as `case_pos_cause_*`, `case_pos_prov_*`, `case_pos_var_*` (and `case_pos_evk_*`)
instead.

**Why.** Every capability gate in this repo keys off the literal string `case_pos_`:
`scripts/hedge_responder_probe.py::_CASE_GLOB` and `_CAPABILITY_PREFIX`,
`evals/case_stats.py::_CAPABILITY_PREFIX`, `evals/runner.py`, `evals/summary.py`, and both
`tests/unit/evals/test_capability_coverage.py` and `test_capability_echo_resistance.py`. A
bare `case_cause_*` file would be a case that **no gate checks** — not echo-tested, not
hedge-probed, not counted in the capability rate, and invisible to the base-rate gate
EVAL-P25.3 is building. Compound prefixes keep every existing gate binding while leaving
each dimension greppable and countable (`ls evals/cases/case_pos_cause_*`).

**Alternative rejected.** Teaching six call sites a second prefix. That is six edits to
working code, in two concurrently-running sessions, to gain nothing the compound prefix
does not already give.

### DEC-221: dimension cases use deterministic matchers only

**Date:** 2026-08-27
**Phase:** EVAL-P26.2
**Status:** Accepted

All 30 cases authored in EVAL-P26.2 use `schema`, `keyword_any` and `keyword_none`. None
uses `tone_judge`, `refusal_judge` or `affirms_judge`.

**Why, three reasons that point the same way.**

1. `test_capability_echo_resistance.py` **excludes** judge-decided cases from the
   gameability ratchet, because with the judge stubbed offline they can never register as
   beaten. A judge-decided case is therefore a case whose ungameability is *unmeasured*, and
   the module asserts the excluded set is exactly two names — a new one would have to be
   added to that list, growing a known hole.
2. Two of the four scorers are REFUSED against `docs/SCORER_TRUST_POLICY.md`
   (`refusal_judge` κ 0.247, `affirms_judge` κ 0.530). New supply routed through a
   suppressed scorer produces rows that cannot be reported.
3. Deterministic matchers are κ = 1.0 by construction (EVAL_P25_TO_P31_PLAN.md §1), so
   these 30 cases add difficulty to the battery **without** adding judge-reliability tax.

**Consequence, stated so it is not discovered later.** These cases cannot express "did the
NPC engage in the right register" — only "did the right tokens appear". The provenance
dimension (D3) recovers most of that by pairing a fact list with a hedging-marker list and
requiring both, which is a deterministic proxy for epistemic framing. Where a genuinely
semantic judgement is needed, that is EVAL-P28.3's repaired judges, not this phase.

### DEC-222: `dialogue_observable` is decided by the serialized-context test

**Date:** 2026-08-27
**Phase:** EVAL-P25.1
**Status:** Accepted

An engine is `dialogue_observable` iff its output reaches the **serialized** dialogue
context — a `CONTEXT_SLOTS` row with `default_enabled=True`
(`src/npc_engine/retrieval/context/context_slots.py`) — or it is the speech path itself.
Importance, size, and "the player can tell" are explicitly not the test.

**Why this exact test.** `serialize_context` emits precisely the `default_enabled=True`
slots, and a `default_enabled=False` slot is absent from the JSON *entirely* rather than
present-and-empty. So the criterion is mechanically checkable rather than a judgement call.
It is what settles `oath`: the `active_pledges` slot exists, is produced, is ranked and is
charged to the token budget, and is then discarded at serialization (an ISSUE-200 orphan).
Under any looser test `oath` would read as judgeable and its cases would pass
unconditionally.

### DEC-223: grounding is verified against the live graph, and live wins over the seed file

**Date:** 2026-08-27
**Phase:** EVAL-P26.2
**Status:** Accepted

Every one of the 30 cases had its grounding read back from the running stack before its
expectation was written, through `GET /v1/admin/{beliefs,goals,memories}/{npc_id}` and
`GET /v1/admin/debug/retrieval` (which assembles a turn's context the way a dialogue turn
does). Where the live graph disagreed with the seed source, **the live text is what the
case is grounded in**.

**Why it is not academic.** It caught two live disagreements in one session:
`tw_wanderer`'s performer edge is `knowledge_state: knows` carrying the plain event
summary, where `seeds/worlds/seed_tavern_world.py` writes `"fact"` with a `"Mira Solen is
here…"` distorted summary (ISSUE-234); and `npc_known_events` is query-relevance filtered,
so `tw_innkeeper`'s witnessed theft is simply absent from context on a general question
(ISSUE-233). A case authored from the seed file would have scored on text the model never
sees — a fabricated case that fails for a reason unrelated to capability.

`make draft-cases` was **not** used: it sends no auth header and its
`GROUNDED_EDGE_TYPES` names three relationship types that do not exist (ISSUE-148).

---

## 5. ISSUES.md — full text of new entries

## ISSUE-230: `make check` does not run the EVAL-P25.1 engine-coverage gate
**Found:** 2026-08-27, during EVAL-P25.1
**Severity:** P2 (annoying)
**Where:** `Makefile` (`check` target and `.PHONY`), `scripts/check_engine_coverage.py`
**Description:** The gate exists, passes, and has a confirmed RED anchor, but nothing runs
it automatically. A new engine package can be added with no classification row and no gate
will notice — which is exactly the hazard the gate was built for.
**Why deferred:** Track A held the `Makefile` for the duration of this session;
`.PHONY` is a single continued line and a concurrent edit would collide.
**To fix:** apply §2 of `project-harness/HANDOFF_TRACK_B.md` verbatim, then run
`make check-engine-coverage` and confirm exit 0.

## ISSUE-231: `context.npc.beliefs` is serialized into every prompt and no rule reads it
**Found:** 2026-08-27, during EVAL-P25.1
**Severity:** P1 (blocking a measurement)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`;
`src/npc_engine/retrieval/context/context_slots.py` slot `beliefs`
**Description:** `system_v1.yaml` names `context.world`, `context.player_reputation`,
`context.npc.emotion`, `context.npc.profile`, `context.npc_known_events`,
`context.recent_session_turns`, `context.npc.goals` (Rule 7),
`context.propagated_reputation` (Rule 13), `context.retrieved_context` (Rule 17) and
`context.npc.memories` (Rule 15). It never names `context.npc.beliefs`. Beliefs are
produced, ranked, charged to the token budget and serialized — with nothing instructing the
model to speak from them. `goals` has Rule 7 and `memories` has Rule 15; `beliefs` has
neither. Eight of the sixteen pre-EVAL-P26.2 capability cases, and eight of the thirty authored
in EVAL-P26.2, are grounded in a `BELIEVES` edge. This is a strong candidate cause for the
belief-grounded subset of ISSUE-145.
**Why deferred:** the fix is a `src/` prompt change, and this session's charter was zero
`src/` files. It is also a prompt edit, which moves `dialogue_prompt_hash` and makes runs
incomparable — that needs to be sequenced against EVAL-P29's prompt-variant work rather
than dropped in.
**To fix:** add a beliefs rule to `system_v1.yaml` in the shape of Rule 7, land it as a
declared prompt variant once EVAL-P29 exists, and measure it as a prompt arm rather than
shipping it silently.

## ISSUE-232: `proactive_dialogue` produces NPC speech no eval can reach
**Found:** 2026-08-27, during EVAL-P25.1
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/proactive_dialogue/`
**Description:** The engine generates an in-character NPC line via LLM, so it is
`dialogue_observable` by the DEC-222 test — but its own package docstring records that it
does not wire into the scheduler, and `evals/` has no proactive turn shape. It is a
judgeable engine with zero judged coverage and no way to author one today.
**Why deferred:** reaching it needs both a scheduler wiring (a `src/` change) and a new
turn shape in the harness, which is EVAL-P27 territory.
**To fix:** either wire slice 2 and add a proactive turn shape to the runner, or record a
decision that proactive lines are out of eval scope and demote the row in
`docs/ENGINE_EVAL_COVERAGE.md` with that decision cited.

## ISSUE-233: `npc_known_events` is query-filtered, so an NPC's event edge can be absent
**Found:** 2026-08-27, during EVAL-P26.2
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/retrieval/context/` (event retrieval);
observed via `GET /v1/admin/debug/retrieval`
**Description:** `tw_innkeeper` holds `KNOWS_ABOUT tw_theft_at_market` at
`knowledge_state: witnessed`, and `npc_known_events` came back **empty** for
"What is the talk in here?" and for "What has been happening in town lately?", and
non-empty only once the message named the market. So "the NPC holds the edge" does not
imply "the fact is in the prompt", and a capability case can fail for a retrieval reason
that has nothing to do with capability. This silently changes what a case measures.
**Why deferred:** it is a retrieval-layer behaviour and possibly the intended one; deciding
that is a `src/` question this session could not open.
**To fix:** decide whether an NPC's own `KNOWS_ABOUT` edges should be unconditionally
pinned (they are the prompt's anti-hallucination whitelist under Rule 5) rather than
relevance-ranked; if they stay ranked, say so in `docs/CAPABILITY_CASES.md` so authors
choose eliciting messages accordingly. `case_pos_prov_tw_innkeeper_theft_witnessed`
currently works around it by naming the market in the prompt.

## ISSUE-234: the live tavern graph disagrees with `seed_tavern_world.py`
**Found:** 2026-08-27, during EVAL-P26.2
**Severity:** P2 (annoying)
**Where:** `seeds/worlds/seed_tavern_world.py::_KNOWS_ABOUT`; live Neo4j
**Description:** The seed file writes `("tw_wanderer", "tw_travelling_performer", "fact",
None, 0, "Mira Solen is here — a singer of some renown in the capital…")`. The live edge
is `knowledge_state: "knows"` carrying the plain event summary
`"A celebrated bard from the capital has arrived in town and is performing at the inn"` —
no Mira Solen, different knowledge_state. The live tavern world also holds more edges than
the file declares (`tw_wanderer` and `tw_innkeeper` both know the theft *and* the
performer). Either the seeder normalises on write, or the live world drifted from an
earlier seed, or gossip propagation has since run against it. Any case authored from the
file would score on text the model never sees.
**Why deferred:** diagnosing it means reading the seeder's write path and the world's
history, which is a separate task from authoring.
**To fix:** determine whether `knowledge_state: "fact"` is normalised to `"knows"` on
write and whether `distorted_summary` is being dropped; if the world drifted, re-seed and
re-verify. Until then, DEC-223 stands: author from the live graph.

## ISSUE-235: the D1–D4 coverage rules are documented but not gated
**Found:** 2026-08-27, during EVAL-P25.2
**Severity:** P3 (nice-to-fix)
**Where:** `docs/REASONING_DIMENSIONS.md`; `tests/unit/evals/test_capability_coverage.py`
**Description:** Each dimension carries a coverage rule ("at least one `case_pos_cause_*`
per world", "each world with both a direct and a gossip edge gets one case of each
polarity", "at least one declared variance set per world"). Nothing enforces them, so a
world can lose its only causality case without turning anything red. The variance
dimension's central claim — that member token sets are disjoint — is likewise asserted in
prose and checked by hand.
**Why deferred:** EVAL-P26.3 owns `edit tests/unit/evals/test_capability_coverage.py`, and
touching that file here would collide with it.
**To fix:** in EVAL-P26.3, add a per-dimension ratchet in the shape of
`UNCOVERED_BASELINE`, plus a test that no two members of a declared variance set share a
scoring token.

## ISSUE-236: `case_pos_vex_spymaster_accord_brokering` carries a dead keyword
**Found:** 2026-08-27, during EVAL-P26.2 (reading the case set for authoring precedent)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/case_pos_vex_spymaster_accord_brokering.yaml`, `keyword_any` list
**Description:** The list contains the stem `negotiat`. Since EVAL-P19.2, single-word
keywords match on a **word boundary** via `keyword_matching.contains_keyword`, so
`negotiat` cannot match `negotiate` or `negotiating` and can never fire. It is one of ten
tokens in a `keyword_any`, so the case still works — the entry is simply dead weight that
overstates the case's surface.
**Why deferred:** editing an existing case moves `harness_version` in a way that also
changes what the case meant for prior runs; per this session's charter that is a separate
decision, not an authoring fix.
**To fix:** replace `negotiat` with `negotiate` and `negotiating`, in a commit that also
records the `harness_version` move. Worth doing as part of the ISSUE-157 dead-keyword
triage rather than alone.

---

## 6. ISSUE-147 — close it

`## ISSUE-147: capability battery is 16 cases against a target of ~35` is satisfied.
Mark it `## [FIXED] ISSUE-147: …`, add
`**Fixed:** 2026-08-27, in EVAL-P26.2 (Track B)`, and move the entry to
`project-harness/archive/ISSUES_RESOLVED.md` per CLAUDE.md.

Evidence for the close: **46 `case_pos_*` files** (21 demo, 15 village, 10 tavern) against
the ~35 target, and the issue's own two named gaps are both closed — depth beyond one fact
per NPC (a second and third grounded fact for `vw_elder`, `vw_guard`, `vw_healer`,
`tw_merchant`, `tw_wanderer`, `captain_sorn`, `mira_innkeeper`, `garrick_deserter`,
`bren_smith`, `old_henryk`), and the village and tavern worlds, which had **zero**
capability coverage and now have 15 and 10.
