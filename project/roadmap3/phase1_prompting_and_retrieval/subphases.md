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

## P1.3 — Verify P1.2 fix + optional model swap

**Entry point for next session.**

**Goal:** Confirm the hardened epoch rule changes NPC behavior in the war scenario.
If it does, skip model swap. If it does not, pull the Phase 1 target model.

**Steps:**
1. Run `make scenarios` (or `python e2e/scenarios/scenario_war_breaks_out.py`).
2. Inspect Turn 2 response with `epoch="war"`. Ask: does the NPC say roads are
   safe/dangerous? Does tone reflect armed conflict?
3. If NPC response materially changes vs Phase 0 baseline → **prompt fix is
   sufficient** → skip model swap, proceed to P1.4.
4. If NPC response is still "relatively safe" or ignores epoch → **model swap
   required** → pull Qwen2.5-7B-Instruct or Llama 3.1 8B Instruct via Ollama,
   update `dialogue/llm_config.yaml`, rerun scenario.

**Files:**
- `e2e/scenarios/scenario_war_breaks_out.py` — existing scenario script
- `src/npc_engine/engines/dialogue/llm_config.yaml` — model config (if swap needed)
- `e2e/transcripts/` — save new transcript for comparison with Phase 0 baseline

**Expected output:**
- Transcript showing Turn 2 NPC response with clear danger/tension framing.
- Pass/fail verdict written to `phase1_prompting_and_retrieval/decisions.md`.

**Exit check:** NPC does not say roads are safe when `epoch="war"`. LLM judge
(soft gate) if available.

---

## P1.4 — LLM judge wiring

**Goal:** Wire `e2e/helpers/llm_judge.py` into `make scenarios` as a hard gate.

**Steps:**
1. Confirm `e2e/helpers/llm_judge.py` exists and is callable.
2. Update war and reputation scenario files to include judge assertions.
3. Add `make scenarios-judge` target for inner dev loop.
4. Update CI / `Makefile` so `make scenarios` runs judge assertions.

**Files:**
- `e2e/helpers/llm_judge.py`
- `e2e/scenarios/scenario_war_breaks_out.py`
- `e2e/scenarios/scenario_reputation_*.py` (if they exist)
- `Makefile`

**Exit check:** `make scenarios` fails when epoch constraint is violated; passes
when NPC correctly reflects world state.

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
