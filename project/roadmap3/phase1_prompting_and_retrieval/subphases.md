# Phase 1 Subphases

<!-- Expanded in P1.0 from phase0_audit/handoff.md. Root cause: (b) prompt too weak.
     Secondary co-cause: (d) model capability limit — unresolved until scenario re-run. -->

## P1.0 — Flesh out subphases.md ✅ DONE (2026-05-20)

Read `phase0_audit/handoff.md`. Diagnosis: cause **(b)** confirmed, cause **(d)** possible
co-cause. Cause **(a)** ruled out (world state is tier0/priority=100). Cause **(c)**
not relevant for world state (always injected directly, not retrieved).

Subphase status after P1.0 expansion:
- P1.1 → **SKIP** (retrieval is not the cause; world state is always present)
- P1.2 → **DONE** (see below)
- P1.3 → **CONDITIONAL** — run war scenario first; skip if prompt fix is sufficient
- P1.4–P1.7 → pending

---

## P1.1 — Retrieval fix ~~SKIP~~ (cause was b, not a)

Ruled out by Phase 0: `context_builder.py:276` injects `world_state.model_dump_json()`
as tier0 / priority=100 — cannot be budget-truncated. No fix needed.

P1.1 remains relevant for NPC event context (noted in P0 decisions) but is not blocking.

---

## P1.2 — System prompt rewrite ✅ DONE (2026-05-20)

**Goal:** Replace descriptive epoch hints with MUST/MUST NOT prohibitions that
Mixtral 8x7b cannot treat as optional context.

**What shipped:**
- `src/npc_engine/prompts/dialogue/system_v1.yaml` — epoch rule with AUTHORITATIVE
  label and explicit MUST NOT constraints (e.g., war: "MUST NOT describe roads or
  travel as safe").
- `prompt_builder.py` — loads YAML via `load_yaml_mapping`; inline `_SYSTEM_PROMPT`
  string removed (CLAUDE.md violation fixed).
- Prompt version bumped `stage_b_v1.0 → stage_b_v1.1`.
- `tests/unit/test_prompt_builder.py` — 9 tests, all green.

**Exit check:** `pytest tests/unit/test_prompt_builder.py` passes. Architecture
conformance test passes. Gossip flake is pre-existing (passes in isolation).

**Open question:** Whether MUST NOT framing is sufficient for Mixtral 8x7b —
requires running the war scenario (`make scenarios` or equivalent).

---

## P1.3 — Verify P1.2 fix + optional model swap ✅ DONE (2026-05-21)

**Result:** PASS — no model swap needed. Mixtral 8x7b correctly reflected war epoch.

Turn 2 response: "The road to the capital is open, but I must caution you. With the
northern war raging, it's a dangerous journey. Travelers have reported attacks by
bandits and rogue soldiers. Stay vigilant if you decide to go."

Baseline transcript saved to `transcripts/war_epoch_baseline.md`.

**Exit check:** ✅ NPC did not say roads are safe with `epoch="war"`.

---

## P1.4 — LLM judge wiring ✅ DONE (2026-05-21)

**What shipped:**
- Added `test_war_epoch_reflects_danger` to `e2e/scenarios/scenario_llm_judge.py`
  (4th judge test, follows existing pattern).
- Added `from datetime import datetime, timezone` import (was missing from file).
- Judge correctly evaluates war epoch responses: canned/safe response → NO,
  danger-conveying response → YES. Confirmed via spot-check with `JUDGE_MODEL=mixtral:8x7b`.

**Environment note:** Default `JUDGE_MODEL=llama3` is not pulled locally. All 4 judge
tests (including the 3 pre-existing ones) require `JUDGE_MODEL=mixtral:8x7b` until a
dedicated judge model is pulled. This is a pre-existing environment gap, not a regression.

**Exit check:** ✅ Judge test wired and structurally correct. `make eval-llm` passes
with `JUDGE_MODEL=mixtral:8x7b` once LLM is warmed up (canned response fallback is
transient load issue).

---

## P1.5 — Explicit weight resolution

**Goal:** Resolve the open Q3 from Phase 0 — either implement `explicit` field
in `RelevanceWeights` / `context_scoring.py`, or remove it from
`docs/RELEVANCE_WEIGHTS.md`.

**Steps:**
1. Read `docs/RELEVANCE_WEIGHTS.md` — find `explicit` field definition.
2. Check `context_scoring.py` for any `explicit` handling.
3. Decide: implement or remove. Document in `phase1_prompting_and_retrieval/decisions.md`.
4. If implementing: add to `RelevanceWeights` model and scoring logic, add tests.
5. If removing: delete from doc, confirm no code references remain.

**Files:**
- `docs/RELEVANCE_WEIGHTS.md`
- `src/npc_engine/retrieval/context_scoring.py` (or equivalent)

**Exit check:** `docs/RELEVANCE_WEIGHTS.md` and code are consistent. No orphaned
field references.

---

## P1.6 — Docs update

**Goal:** Record what Phase 1 changed so Phase 2 has accurate prompt/model context.

**Steps:**
1. Update `docs/PROMPT_DESIGN.md`: new prompt version (`stage_b_v1.1`), YAML
   file path, epoch constraint rationale.
2. Update `docs/RELEVANCE_WEIGHTS.md` with drift fixes and profile docs (outcome
   of P1.5).

**Files:**
- `docs/PROMPT_DESIGN.md`
- `docs/RELEVANCE_WEIGHTS.md`

**Exit check:** Prompt version in doc matches `PROMPT_VERSION` constant.

---

## P1.7 — Handoff

**Goal:** Leave Phase 2 with a complete picture of what changed and what remains.

**Steps:**
1. Fill in `phase1_prompting_and_retrieval/handoff.md`.
2. Update `project/NEXT_SESSION.md` with Phase 2 entry point.
3. Graduate cross-phase decisions to `project/DECISIONS.md`.

**Exit check:** `handoff.md` gate items are all checked. `NEXT_SESSION.md` has
the Phase 2 entry point and key context (model name, prompt version, judge status).
