# Next Session Instructions

## Current state

Roadmap V3 — **Phase 1: Prompting & Retrieval, subphases P1.5–P1.7 remaining.**

Run tests before touching any code:

```bash
pytest tests/unit/ -q
```

958 tests, all green as of 2026-05-21.

---

## Where we are

| Subphase | Status |
|---|---|
| P1.1 — Retrieval fix | SKIP — world state is tier0, never truncated |
| P1.2 — System prompt rewrite | ✅ DONE — `system_v1.yaml`, `stage_b_v1.1` |
| P1.3 — Verify fix + model swap | ✅ DONE — war scenario passes; switched to `qwen2.5:7b` |
| P1.4 — LLM judge wiring | ✅ DONE — `test_war_epoch_reflects_danger` added |
| P1.5 — Explicit weight resolution | ⏳ **ENTRY POINT** |
| P1.6 — Docs update | ⏳ pending P1.5 |
| P1.7 — Handoff close | ⏳ pending P1.6 |

---

## P1.5 — Entry point

**Goal:** Resolve whether the `explicit` field in `RelevanceWeights` is implemented
or a doc-only stub. Either implement it fully or remove it from the docs.

**Start here:**

```bash
grep -rn "explicit" src/npc_engine/retrieval/ docs/RELEVANCE_WEIGHTS.md
```

- If the field exists in the model but scoring ignores it → implement the scoring logic + tests.
- If the field is only in the doc → decide with the human, then either implement or delete from doc.
- Either way, `docs/RELEVANCE_WEIGHTS.md` and `context_scoring.py` must agree when P1.5 closes.

Decisions go in `project/roadmap3/phase1_prompting_and_retrieval/decisions.md`.

---

## Key context for the session

- **Model:** `qwen2.5:7b` via Ollama. Pull if not present: `ollama pull qwen2.5:7b`
- **Prompt version:** `stage_b_v1.1` (`PROMPT_VERSION` constant in `prompt_builder.py`)
- **Prompt file:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
- **LLM judge:** `make eval-llm` — requires running server + `JUDGE_MODEL=qwen2.5:7b`
- **War baseline transcript:** `transcripts/war_epoch_baseline.md`
- **Known gap:** `active_conditions` has no MUST NOT enforcement (only `epoch` does).
  Not blocking P1.5 but relevant for any future behavioral constraint work.
- **Pre-existing bug:** `POST /v1/admin/memories/consolidate/{char_id}` returns 500.
  Not blocking Phase 1 close unless consolidation is needed.

---

## After P1.5: P1.6 + P1.7

P1.6 — update two doc files:
1. `docs/PROMPT_DESIGN.md` — change `Stage B: v1.0` → `v1.1`, add YAML path and epoch rationale.
2. `docs/RELEVANCE_WEIGHTS.md` — reflect P1.5 outcome.

P1.7 — close Phase 1:
1. Fill remaining gate items in `project/roadmap3/phase1_prompting_and_retrieval/handoff.md`.
2. Graduate any cross-phase decisions to `project/DECISIONS.md`.
3. Update this file with Phase 2 entry point (template is at the bottom of `handoff.md`).
