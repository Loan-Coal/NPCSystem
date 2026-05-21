# Phase 1 Handoff

<!-- Last updated: 2026-05-21 after P1.4 complete. P1.5–P1.7 pending. -->

## Gate Status

1. Existing tests pass:
   [x] YES — 958 unit tests, 0 failures (run: `pytest tests/unit/ -q`)

2. New tests pass:
   [x] YES — 9 tests in `tests/unit/test_prompt_builder.py` all green.
   `test_war_epoch_reflects_danger` in `scenario_llm_judge.py` is structurally
   correct; requires a running server + `qwen2.5:7b` pulled to execute.

3. E2E baseline:
   [x] NO REGRESSION
   War scenario passes: `pytest e2e/scenarios/scenario_war_breaks_out.py -v -s --scenarios-only`
   Transcript saved to `transcripts/war_epoch_baseline.md` (2026-05-21).

4. Manual sign-off:
   [x] SIGNED OFF
   Evidence: Turn 2 — guard asked "Is the road to the capital safe to travel?"
   with `epoch="war"`. Response: "The road to the capital is open, but I must
   caution you. With the northern war raging, it's a dangerous journey. Travelers
   have reported attacks by bandits and rogue soldiers. Stay vigilant if you
   decide to go." — no safe-road language; danger/tension throughout.

5. LLM judge (HARD gate from Phase 1):
   [ ] PASS — PENDING (requires server + qwen2.5:7b pulled)
   Verdict: run `JUDGE_MODEL=qwen2.5:7b make eval-llm` against a live server.
   Judge correctly evaluates responses when model is available — confirmed via
   spot-check (canned → NO, danger-conveying → YES).

6. Coverage on new code:
   N/A for YAML prompt file. `prompt_builder.py` changes covered by 9 unit tests.

---

## What Shipped

- [x] Retrieval fix (cause a) — **SKIP**: world state is tier0/priority=100 in
  `context_builder.py:276`; cannot be budget-truncated. Retrieval was not the cause.
- [x] System prompt rewrite (cause b) — prompt version: `stage_b_v1.1`
  File: `src/npc_engine/prompts/dialogue/system_v1.yaml`
  Key change: epoch rule rewritten with `AUTHORITATIVE` label and `MUST NOT`
  prohibitions. Inline `_SYSTEM_PROMPT` Python string removed.
- [x] Model swap — new model: `qwen2.5:7b` (Ollama, ~4.7 GB Q4, fits in 12 GB VRAM).
  Previous: `mixtral:8x7b` (26 GB). Config: `src/npc_engine/engines/dialogue/llm_config.yaml`.
  Pull: `ollama pull qwen2.5:7b`
- [x] LLM judge wired — `test_war_epoch_reflects_danger` added to
  `e2e/scenarios/scenario_llm_judge.py`. Default `JUDGE_MODEL` fixed to `qwen2.5:7b`.
  Run: `make eval-llm` (requires live server).
- [ ] explicit weight resolution — **PENDING** (P1.5)
- [ ] docs/PROMPT_DESIGN.md updated — **PENDING** (P1.6). Currently says `Stage B: v1.0`; must reflect `stage_b_v1.1`.
- [ ] docs/RELEVANCE_WEIGHTS.md updated — **PENDING** (P1.6, outcome of P1.5).

---

## What Was Deferred

**active_conditions gap** — `context.world.active_conditions` (e.g. `["bandit_activity"]`,
`["thief_spotted_market"]`) is passed to the LLM but has no MUST NOT enforcement rules.
The prompt says "also read this list" — the model infers behavior from the string value,
which is the same weak-hint problem that P1.2 fixed for epoch. Epoch now has hard rules;
active_conditions does not. Address in a future phase if runtime event injection proves
insufficient for scene-level behavioral changes.

**Dedicated judge model** — judge currently uses the same `qwen2.5:7b` as the dialogue
engine. Fine for local dev; a production setup may want a smaller, faster judge model
(e.g. `llama3.2:3b`) on a separate Ollama instance to avoid head-of-line blocking.

---

## What Phase 2 Needs to Know

Model in use: `qwen2.5:7b` via Ollama (`http://localhost:11434`)
Prompt version: `stage_b_v1.1`
Prompt file: `src/npc_engine/prompts/dialogue/system_v1.yaml`
Prompt builder: `src/npc_engine/engines/dialogue/prompt_builder.py`

API routes confirmed working during Phase 1 scenario runs:
- `POST /v1/dialogue` — ✅ working (war scenario, judge scenario)
- `POST /v1/graph/nodes/{type}` — ✅ working (world state upsert in war scenario)
- `GET /v1/admin/memories/{char_id}` — ✅ working (judge test 1)
- `POST /v1/admin/memories/consolidate/{char_id}` — ⚠️ returns 500 (judge test 1 fails);
  consolidation endpoint has a pre-existing bug. Not blocking Phase 2 unless consolidation
  is on the critical path.

Known gap discovered: `active_conditions` behavioral rules are soft (see deferred above).
If Phase 2 scenario requires NPCs to react to specific runtime events beyond epoch,
that gap must be addressed before P1 can be called fully closed.

---

## What Phase 3 Needs to Know

**Recommended target engine for QLoRA adapter:** `dialogue` — the epoch MUST NOT
constraints work at the prompt level but a fine-tuned model would internalize them
structurally, removing reliance on prompt verbosity. Phase 1 showed prompting alone
is sufficient for epoch-level rules; Phase 3 training data should use war scenario
transcripts as positive examples.

**Training data signals from Phase 1:**
- `transcripts/war_epoch_baseline.md` — positive example: war epoch, correct danger framing.
- The `test_war_epoch_reflects_danger` judge criteria is a ready-made eval signal.

---

## Decisions Graduated to project/DECISIONS.md

None yet — all Phase 1 decisions remain in
`project/roadmap3/phase1_prompting_and_retrieval/decisions.md`. Graduate to
`project/DECISIONS.md` during P1.7 if any are cross-phase.

---

## Remaining Subphases Before Phase 1 Close

### P1.5 — Explicit weight resolution

**What to do:** Open `docs/RELEVANCE_WEIGHTS.md`. The `explicit` field is documented
but may not be implemented in `context_scoring.py`. Decide: implement or remove.

- If **implement**: add `explicit` to the `RelevanceWeights` model and scoring logic;
  add unit tests.
- If **remove**: delete from `docs/RELEVANCE_WEIGHTS.md`; confirm no code references
  remain.

**Entry command:** `grep -r "explicit" src/npc_engine/retrieval/ docs/`

### P1.6 — Docs update

1. `docs/PROMPT_DESIGN.md` line: `> **Current versions:** Stage A: v1.0 | Stage B: v1.0`
   → update Stage B to `v1.1`. Add YAML file path, epoch constraint rationale.
2. `docs/RELEVANCE_WEIGHTS.md` — update after P1.5 resolution.

**Exit check:** `grep PROMPT_VERSION src/npc_engine/engines/dialogue/prompt_builder.py`
output must match the version string in the doc.

### P1.7 — Handoff close

1. Return to this file and check the two remaining gate items (LLM judge, docs).
2. Update `project/NEXT_SESSION.md` with Phase 2 entry point (see template below).
3. Graduate any cross-phase decisions to `project/DECISIONS.md`.

---

## NEXT_SESSION.md Template (fill at P1.7)

```
Roadmap V3 — Phase 2: Demo Game Skeleton + Graph Visualization

Entry criteria:
- Phase 1 handoff signed off: YES
- make eval-llm passes (JUDGE_MODEL=qwen2.5:7b): [YES/NO]
- War scenario manual sign-off: YES (2026-05-21)
- docs/PROMPT_DESIGN.md reflects stage_b_v1.1: [YES/NO after P1.6]

Key context:
- Model: qwen2.5:7b (Ollama) — pull: ollama pull qwen2.5:7b
- Prompt version: stage_b_v1.1
- Prompt file: src/npc_engine/prompts/dialogue/system_v1.yaml
- LLM judge: make eval-llm (JUDGE_MODEL=qwen2.5:7b)
- active_conditions behavioral rules: NOT enforced (gap — see Phase 1 handoff)
- Memory consolidation endpoint: pre-existing 500 bug (not blocking Phase 2)
```
