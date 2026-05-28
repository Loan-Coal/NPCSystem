# Phase 0 Subphases (Full Detail)

---

## P0.1 — Environment Check & Baseline Capture (0.5 half-day)

**Goal:** Confirm the test suite is green, the stack runs, and a first baseline
output exists before any code is touched.

**Steps:**

1. Run `make test` (or `python -m pytest tests/`). All 771+ tests must pass.
   If any fail, stop — do not proceed until they are green. Note the failure in
   `decisions.md` and check `project/ISSUES.md` to see if it is a known issue.

2. Start the Docker Compose stack: `make dev` (or equivalent). Confirm Ollama
   is responding: `curl localhost:11434/api/tags` should return model list.

3. Check `.env.dev` for `LOG_LLM_PROMPTS`. Note its current value in `decisions.md`.
   Also check whether `MISTRAL_ADAPTER_URL` or any non-Ollama adapter URL is set
   (answers open question Q1).

4. Run the war scenario:
   ```
   python -m pytest e2e/scenarios/scenario_war_breaks_out.py -v -s 2>&1 | tee /tmp/war_run_1.txt
   ```
   Run it three times, saving each output. This captures variance from
   non-deterministic LLM output.

5. Save the three raw API response JSONs (from scenario output or `transcripts/`)
   to `e2e/baselines/war_outbreak_baseline_run{1,2,3}.json`.

6. Run `scenario_dialogue_reputation.py` once and save to
   `e2e/baselines/reputation_baseline.json`.

**Files to read:**
- `.env.dev` — check LOG_LLM_PROMPTS and adapter URLs
- `e2e/scenarios/scenario_war_breaks_out.py` — understand what it asserts

**Files to write:**
- `e2e/baselines/war_outbreak_baseline_run1.json`
- `e2e/baselines/war_outbreak_baseline_run2.json`
- `e2e/baselines/war_outbreak_baseline_run3.json`
- `e2e/baselines/reputation_baseline.json`
- `project/roadmap3/phase0_audit/decisions.md` — LOG_LLM_PROMPTS current value;
  MistralAdapter active/orphaned (resolves Q1)

**Expected output:**
- Green test run confirmed.
- Three war-scenario outputs saved. Observe whether `npc_response` varies across
  runs and whether any response mentions "war" or "unsafe roads" without being
  asked directly.

**Exit check:** `e2e/baselines/` directory contains 4 JSON files. `make test`
exit code is 0. `decisions.md` has an entry for Q1 resolution.

---

## P0.2 — Prompt Logging & Inspection (0.5 half-day)

**Goal:** Capture the exact string that reaches the LLM for the war scenario.
Determine whether world state is visible in the final prompt at all.

**Steps:**

1. Read `src/npc_engine/engines/dialogue/llm_client.py` in full. Find where
   `log_prompts` is used. Does it log the prompt string and system prompt?
   Note what is and is not logged.

2. If `log_prompts=True` already produces a log line with the full prompt
   string (CONTEXT=... PLAYER_MESSAGE=...), skip step 3.

3. If the full assembled prompt is not logged, add ONE `logger.debug()` line
   at the end of `prompt_builder.py::build_dialogue_prompt`:
   ```python
   logger.debug("dialogue_prompt built", prompt_version=PROMPT_VERSION, prompt=result)
   ```
   (Replace `result` with the actual return variable name.) This is the only
   code change permitted in Phase 0 and only if needed.

4. Set `LOG_LLM_PROMPTS=true` (or equivalent log level) and re-run the war
   scenario. Capture the log output.

5. In the log, find the `CONTEXT=` block. Inspect it:
   - Is there a `world` key with `epoch` field? What is its value?
   - Are `active_conditions` populated with the war event?
   - If the context JSON is truncated, note at what token budget it was cut.

6. Read `src/npc_engine/retrieval/context_builder.py` — specifically the
   section that assembles the WorldState node. Confirm it is assigned to Tier 0
   (never trimmed). If it is in Tier A or B, note this as a likely cause (b).

**Files to read:**
- `src/npc_engine/engines/dialogue/llm_client.py` (full)
- `src/npc_engine/engines/dialogue/prompt_builder.py` (full — already read during audit)
- `src/npc_engine/retrieval/context_builder.py` — WorldState assembly section

**Files to possibly write (only if step 3 is triggered):**
- `src/npc_engine/engines/dialogue/prompt_builder.py` — 1 DEBUG log line

**Expected output:**
A log excerpt showing the CONTEXT block. You should be able to answer:
- "The world state epoch is / is not present in the serialized context."
- "The WorldState node is in Tier [0/A/B/not present]."

**Exit check:** A log file or copy of the CONTEXT block from a war scenario run
is saved to `e2e/baselines/war_prompt_capture.txt`. The diagnosis can proceed
to P0.3 with this artifact.

---

## P0.3 — Retrieval Diagnostic (1 half-day)

**Goal:** Classify the failure as cause (a), (b), (c), or (d) using the prompt
capture from P0.2 and static code reading.

**Steps:**

1. From the P0.2 prompt capture, check whether `context.world.epoch` equals
   `"war"` (or the equivalent condition value):

   **If the world epoch is absent or wrong:**
   → **Cause (a)** — WorldState not retrieved. Read `context_builder.py` to
     find the Cypher query that fetches WorldState. Check if the war event
     actually updates `WorldState.epoch` or if it creates an Event node only.
     Read the world state route (`src/npc_engine/api/routes/clock.py` or
     similar) to confirm what field the war event sets.

   **If the world epoch is present as `"war"` but active_conditions are empty:**
   → Partial retrieval. The WorldState singleton is fetched but the linked Event
     nodes are not populated. This is a retrieval gap (cause a/b hybrid).

   **If world epoch is `"war"` and the prompt contains the war condition:**
   → Proceed to cause (c/d) analysis below.

2. **Budget check (cause b):** Read `context_builder.py` to confirm WorldState
   is Tier 0. If it is Tier A or B, check whether the 380-token Tier 0 budget
   is exhausted before WorldState is added. (Tier 0 budget per `PROMPT_DESIGN.md`:
   world=80, biography+emotion=120, relation=30, session=150.)

3. **Cause (c/d) analysis:** If world state is in the final prompt:

   Read `prompt_builder.py::_SYSTEM_PROMPT` (already read during audit). The
   current system prompt says:
   ```
   1. WORLD STATE — read `context.world.epoch`: ...
   - "war": active conflict nearby — you are tense, wary, roads are dangerous
   ```
   This is descriptive framing, not adversarial/authoritative framing.

   - **Cause (c):** Model follows the framing in general but occasionally
     reverts to default helpfulness when the question is indirect ("are the
     streets safe?"). Test: does the model answer correctly when asked directly
     ("I heard there is a war — is it safe to travel?") vs. indirectly? If
     direct works and indirect fails → cause (c).

   - **Cause (d):** Prompt doesn't establish that world state is authoritative
     ground truth that overrides the model's trained defaults. The current
     framing says "you are tense" — it describes the NPC's mood, not an
     instruction to treat the war as real. Adding "THESE CONDITIONS ARE
     OBJECTIVE FACTS — do not contradict them" framing is a cause-(d) fix.
     Test: current prompt never says "the context is authoritative" — this
     alone is strong evidence for (d).

4. Write the diagnosis in `decisions.md`:
   ```
   ## [date] Phase 0 diagnosis
   Primary cause: (a/b/c/d) — [one paragraph of evidence]
   Secondary cause (if applicable): ...
   Phase 1 priority: [retrieval fix / prompt fix / both]
   ```

**Files to read:**
- P0.2 prompt capture artifact
- `src/npc_engine/retrieval/context_builder.py` — WorldState Tier assignment
  and Cypher query
- `src/npc_engine/api/routes/clock.py` or equivalent — what `POST /v1/clock/advance`
  sets on WorldState
- `src/npc_engine/engines/dialogue/prompt_builder.py` — system prompt framing

**Files to write:**
- `project/roadmap3/phase0_audit/decisions.md` — diagnosis entry

**Expected output:**
A written diagnosis (a/b/c/d) with specific evidence from the log and code.

**Exit check:** `decisions.md` contains a diagnosis entry with primary cause
and Phase 1 priority. If cause is (a) or (b), the specific Cypher query or
budget configuration that needs to change is named.

---

## P0.4 — Relevance Weight Audit (0.5 half-day)

**Goal:** Document all drift between `docs/RELEVANCE_WEIGHTS.md` and the
implementation in `context_scoring.py` / `context_config_models.py`.

**Steps:**

1. Read `src/npc_engine/schema/context_config_models.py` — the `RelevanceWeights`
   frozen dataclass. List all fields and their types.

2. Read `src/npc_engine/retrieval/context_scoring.py` — the `rank_tier_items()`
   function. List all scoring components actually computed.

3. Compare against `docs/RELEVANCE_WEIGHTS.md`. For each item in the doc:
   - Is the field present in `RelevanceWeights`? ✓/✗
   - Is the scoring logic present in `context_scoring.py`? ✓/✗

4. Known drift to confirm (found during V3 planning):
   - `explicit` weight: listed in docs as a 6th component with example value
     0.10; absent from `RelevanceWeights` model and scoring logic.
   - Built-in profiles `investigation`, `political`, `social` exist in code but
     are not documented in `RELEVANCE_WEIGHTS.md`.
   - Doc example "balanced" profile: {recency:0.20, severity:0.20, proximity:0.15,
     relation:0.20, quest:0.15, explicit:0.10} sums to 1.00 only with `explicit`.
     Without it, the 5-field sum would be 0.90. Verify whether the doc example
     is internally inconsistent.

5. Record all drift in `decisions.md` with a recommendation for Phase 1 action.

**Files to read:**
- `src/npc_engine/schema/context_config_models.py`
- `src/npc_engine/retrieval/context_scoring.py`
- `docs/RELEVANCE_WEIGHTS.md`

**Files to write:**
- `project/roadmap3/phase0_audit/decisions.md` — weight audit findings entry

**Expected output:**
A table in `decisions.md` showing each doc-listed weight vs. implementation
status, and a recommendation: implement `explicit` in Phase 1 or remove from docs.

**Exit check:** `decisions.md` contains the weight audit table. Resolves Q3
from `open_questions.md` (human must confirm the recommendation before Phase 1
acts on it, but the analysis is complete).

---

## P0.5 — Model Swap Benchmarking (0.5 half-day)

**Goal:** Measure Mixtral 8x7B latency to inform the Phase 1 model swap decision.

**Steps:**

1. During the P0.1 and P0.3 scenario runs, note: time-to-first-token and
   total response time (visible in test output or `transcripts/`). Record 3
   samples.

2. Note Mixtral 8x7B cold load time (from Ollama startup to first request
   completing).

3. Look up published quality benchmarks for Qwen2.5-7B-Instruct and Llama 3.1
   8B Instruct on instruction-following tasks (MT-Bench or equivalent). Note
   sources.

4. Write a decision entry in `decisions.md`:
   - If total response time is >10s: recommend swapping in Phase 1 early.
   - If total response time is ≤5s: swap is lower urgency; quality is the
     deciding factor.
   - Recommend a specific target model based on benchmarks.

**Files to write:**
- `project/roadmap3/phase0_audit/decisions.md` — model swap recommendation

**Exit check:** `decisions.md` has a model swap entry with 3 latency samples
and a recommended target. This entry is marked `Cross-phase? Yes` (it graduates
to `project/DECISIONS.md`).

---

## P0.6 — LLM Judge Baseline & Handoff (0.5 half-day)

**Goal:** Record the LLM judge verdict against baseline outputs and write the
Phase 0 handoff document.

**Steps:**

1. Run `e2e/helpers/llm_judge.py` against the war scenario outputs saved in
   P0.1. The simplest invocation is via the existing `scenario_llm_judge.py`
   with `@pytest.mark.llm_eval`:
   ```
   python -m pytest e2e/scenarios/scenario_llm_judge.py -m llm_eval -v -s
   ```
   If this scenario tests a different flow, run `llm_judge.py` manually against
   the P0.1 transcript JSON instead.

2. Save the verdict JSON to `e2e/baselines/llm_judge_phase0.json`.
   Include: input scenario, judgment prompt used, YES/NO verdict, and reasoning
   text from the judge LLM.

3. Note: Gate 5 is SOFT in Phase 0. A FAIL verdict does not block phase close
   but must be explained.

4. Fill in `project/roadmap3/phase0_audit/handoff.md`:
   - Gate status for all 6 gates.
   - The written diagnosis (copy from decisions.md).
   - What Phase 1 needs to know: specifically, whether cause is (a/b) requiring
     retrieval fixes, or (c/d) requiring prompt-only fixes, or both.
   - Phase 1 priority order.
   - Replacement text for `project/NEXT_SESSION.md`.

5. Update `project/NEXT_SESSION.md` (replace entirely — do not append).

**Files to write:**
- `e2e/baselines/llm_judge_phase0.json`
- `project/roadmap3/phase0_audit/handoff.md` (fill in the template)
- `project/NEXT_SESSION.md` (replace entirely)

**Exit check:** `handoff.md` is filled in (not a template). `NEXT_SESSION.md`
is a fresh replacement. Phase 0 is closed.
