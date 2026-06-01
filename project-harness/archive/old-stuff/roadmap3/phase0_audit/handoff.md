# Phase 0 Handoff

## Gate Status

1. Existing tests pass:
   [x] YES — `make test` / `pytest tests/` green (771+ tests) before any Phase 0 code changes.

2. New tests pass:
   [x] N/A — no new code written in Phase 0.

3. E2E baseline:
   [x] N/A — Phase 0 *produces* the baseline; regression gate applies from Phase 1.
   Baseline files saved: `e2e/transcripts/scenario_war_breaks_out_20260520T135008Z.md`,
   `e2e/transcripts/scenario_war_breaks_out_20260520T140310Z.md` (two runs captured).

4. Manual sign-off:
   [x] SIGNED OFF by Lohann Colle — 2026-05-20
   Evidence: Two full scenario runs reviewed. Turn 1 (peace) and Turn 2 (war) responses
   both read. World state epoch change IS reflected in language ("times of peace" → "times
   of war") but NOT in threat assessment ("relatively safe" persists across both turns).

5. LLM judge (SOFT gate in Phase 0):
   [ ] COULD NOT RUN — Ollama LLM judge not available during this session.
   Verdict saved to: not yet created.

6. Coverage:
   [x] N/A — no new code written.

---

## Primary Diagnosis

**Cause: (b)** — world state reaches the prompt (tier0, priority=100, always included) but
the system-prompt behavioral instruction is too weak for Mixtral 8x7b to act on it
materially.

**Evidence:**
- `context_builder.py:276` always injects `world_state.model_dump_json()` as tier0 /
  priority=100 — cause (a) ruled out conclusively.
- Neo4j graph node confirmed `epoch: "war"` was present after the WorldState upsert.
- LLM did read the epoch (response text changed from "times of peace" to "times of war").
- LLM did NOT change its threat assessment — kept "relatively safe" in both turns.
- System prompt instruction: *"war: active conflict nearby — you are tense, wary, roads are
  dangerous"* is a hint-style description, not an authoritative constraint. Mixtral treats
  it as optional context rather than a behavioral rule.

**Secondary cause:** Possibly (d) — model capability limit. Cannot distinguish from (b) alone
without running P0.5 model swap. Treat as co-cause pending Phase 1 prompt-strengthening.

---

## What Shipped

- [x] Two scenario transcript baselines saved to `e2e/transcripts/`
- [x] Diagnosis written in `decisions.md`
- [ ] Relevance weight audit written in `decisions.md` — deferred to Phase 1
- [ ] Model swap recommendation written in `decisions.md` — deferred to Phase 1 exit
- [ ] LLM judge baseline recorded — Ollama unavailable; defer to Phase 1 P0.6 catch-up

---

## What Was Deferred

- **P0.3 retrieval diagnostic** — not needed for world state (tier0, always present).
  Still relevant for NPC event context retrieval; do during Phase 1 P1.1.
- **P0.4 relevance weight audit** — weights are configurable via env; no broken weight
  found. Revisit in Phase 1 if event context proves sparse.
- **P0.5 model swap** — run during Phase 1 if strengthened system prompt still fails.
- **P0.6 LLM judge baseline** — run when Ollama is available with a judge-capable model.
- **`dialogue_prompt_assembled` DEBUG log capture** — `LOG_LEVEL=DEBUG` did not propagate
  to the background uvicorn process through the Claude Code runner. Epoch presence was
  confirmed via code review (`context_builder.py:276`) and LLM response text instead.
  ISSUE: investigate env var propagation to background processes.

---

## What Phase 1 Needs to Know

**Root cause is (b) — prompt-only fix is the first lever to pull.**

The system prompt in `src/npc_engine/engines/dialogue/prompt_builder.py` (per CLAUDE.md
the prompt string must move to `prompts/` YAML — this is also a Phase 1 task) needs:

1. **Stronger epoch constraint** — current wording is descriptive; rewrite as an explicit
   prohibitive rule, e.g.:
   ```
   WORLD STATE IS AUTHORITATIVE. If epoch="war", you MUST NOT describe roads or travel
   as safe. Respond with tension and caution regardless of other context.
   ```

2. **Epoch → persona bridge** — connect the epoch rule to the NPC's persona/archetype so
   the constraint feels in-character, not mechanical.

3. **Move prompt to `prompts/` YAML** — `_SYSTEM_PROMPT` is currently a raw string in
   `prompt_builder.py`, violating the CLAUDE.md "no prompt strings outside `prompts/`"
   rule. Phase 1 must relocate it to a versioned YAML file before shipping new prompt text.

**Model swap target:** Llama 3.1 8B Instruct (preferred) or Qwen 2.5 7B Instruct.
Run P0.5 at Phase 1 exit if prompt-only fix does not move the needle. Latency not yet
measured (Ollama degraded during this session).

**Relevance weight `explicit`:** Not implemented yet; remove from docs or implement in
Phase 1 P1.2 relevance weight work.

---

## Decisions Graduated to project/DECISIONS.md

- `[2026-05-20] P0.1/P0.2 Diagnosis — failure mode (b)` from `phase0_audit/decisions.md`

---

## NEXT_SESSION.md Update

```
Phase 1 — Prompting & Retrieval Fixes

Entry criteria:
- Phase 0 handoff signed off: YES
- Diagnosis confirmed: cause (b) — system prompt too weak, world state IS in prompt
- Baseline transcripts in e2e/transcripts/: YES (two runs)

Key context:
- Fix target: `_SYSTEM_PROMPT` in prompt_builder.py — strengthen epoch constraint from
  descriptive hint to authoritative prohibitive rule
- Must also move prompt string to prompts/ YAML (CLAUDE.md rule violation, currently inline)
- World state is always tier0 / priority=100 — no retrieval fix needed for world state
- Model swap (P0.5) is the fallback if prompt fix alone is insufficient; use Llama 3.1 8B
- LLM judge baseline (P0.6) still outstanding — run when a judge model is available
```
