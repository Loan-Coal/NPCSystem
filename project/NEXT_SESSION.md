# Next Session Instructions

## Current state

Roadmap V3 — **Phase 2: Prompt Engineering.** Phase 1 complete and signed off 2026-05-22.

Run baseline checks before touching any code:

```bash
make demo-run ARGS=--dry-run   # expect 19 scenes, no [FILL IN], clean output
make demo-run ARGS=--cached    # expect < 10 s, zero LLM calls, 4 cached beats
make test-demo                 # expect 107 pass (demo_game tests)
make eval-llm-demo             # expect 2/2 PASS (qwen2.5:14b + Ollama running)
```

---

## Entry criteria (all green as of 2026-05-22)

| Criterion | Status |
|---|---|
| `docs/DEMO_SCRIPT.md` fully filled in — all `[FILL IN]` resolved | YES |
| `make demo-run ARGS=--cached` < 10 s, zero LLM calls | YES — 1.5 s |
| `make demo-run ARGS=--dry-run` clean, 19 scenes | YES |
| Warm cache committed (4 beat files in `.cache/demo/`) | YES |
| 107 demo_game tests pass (`make test-demo`) | YES |
| `make eval-llm-demo` — 2/2 PASS (qwen2.5:14b) | YES |
| Engine test suite baseline: 20 failed / 951 passed / 17 skipped | CONFIRMED |

---

## Key context from Phase 1 that Phase 2 needs

### 1. Gossip chain is pre-seeded, not live-propagated (DEC-006)

`captain_sorn`, `mira_innkeeper`, and `old_henryk` each have a KNOWS_ABOUT edge to
`northern_war_begins` seeded in `demo_game/seed.py`. The distorted summaries are:

- **Sorn (ground truth):** "The northern armies have crossed the border"
- **Mira (hop 1 — faction garbled):** "A soldier mentioned the northern armies — or the Iron Guard, he called them — have moved on the border. Rumor only, mind you."
- **Henryk (hop 2 — location wrong, inflated):** "It was utterly catastrophic: the northmen have poured through the king's pass, thousands dead, they say..."

**Phase 2 goal:** The LLM must read these `distorted_summary` values from the KNOWS_ABOUT edge context and produce dialogue that reflects them. Currently, all three NPCs sound similar — the distorted_summary is not surfacing in their responses. This is the core prompt engineering problem.

### 2. Current prompt state — minimal

`prompts/` only contains `canned/` templates (default, elder, guard, merchant). There is no:
- Per-NPC voice descriptor
- Knowledge guard ("only reference facts in your context")
- World-state anchor (epoch=war behavioral prohibition)
- System prompt in a YAML file

The system prompt currently lives as an inline Python string somewhere in `src/npc_engine/engines/dialogue/`. Per CLAUDE.md rules, it MUST move to a YAML file under `prompts/` before Phase 2 adds anything to it.

### 3. Observed LLM response quality after Phase 1

Live run responses from `make demo-run` (2026-05-22):
- **Sorn:** "The northern armies have crossed our border. We're on high alert and reinforcing..." ✓ (correct content, but generic military voice)
- **Mira:** "Aye, there are rumors that the northern armies have moved closer to our borders." ✗ (no faction distortion, no innkeeper warmth)
- **Henryk:** "Aye, lad, you've heard right. The northern armies have crossed the border and it..." ✗ (same content as Sorn — distorted_summary completely ignored, no rambling elder voice)

The demo's money shot (Henryk giving a garbled account) currently doesn't work. Phase 2 must fix this.

### 4. Admin endpoints for NPC inner life (not graph edges)

`GET /v1/admin/beliefs/{character_id}` returns the full belief list.
Always use admin endpoints (`/v1/admin/beliefs`, `/v1/admin/goals`, etc.) — NOT `GET /v1/graph/edges/BELIEVES`.

### 5. Edge schema (stable — do not change)

| What | Actual schema |
|---|---|
| NPC-NPC trust | `RELATES_TO` (not STANDS_WITH — that's Faction→Faction) |
| NPC-Event knowledge | `KNOWS_ABOUT` with `distorted_summary` field |
| Faction antagonism | `STANDS_WITH` negative int (not OPPOSES — that's Character→Character) |

### 6. Demo world (stable — do not rename IDs)

5 NPCs: `mira_innkeeper` (tavern), `aldric_merchant` (market_square),
`captain_sorn` (guard_barracks), `lira_fence` (tavern), `old_henryk` (market_square).
All now have LOCATED_AT edges. Idempotent re-seed: `make demo-seed` → `created=0 skipped=61`.

### 7. Active dialogue model

`qwen2.5:14b` — see `src/npc_engine/engines/dialogue/llm_config.yaml` (DEC-018).

---

## Open issues relevant to Phase 2

| ID | Severity | Summary |
|---|---|---|
| ISSUE-021 | P3 | `test_gossip_propagates_after_clock_advance` trivially true. Strengthen with edge-count diff. |
| ISSUE-020 | P3 | `DialogueTurn.emotion` mapped from `mood_update`, not a first-class field. |

---

## Phase 2 — Prompt Engineering entry point

Goal: every NPC on the demo path sounds distinct and anchored to their actual knowledge state.
Exit criterion: `make eval-llm-demo` shows 5/5 (existing 2 + 3 new) judge tests passing.

Steps (from ROADMAP.md):
- **S2.1** Audit `prompts/` and `src/npc_engine/engines/dialogue/` — find where the system prompt lives, what context fields are injected, whether `distorted_summary` is even in the prompt.
- **S2.2** Move system prompt to `prompts/system_prompt.yaml` (CLAUDE.md rule: no prompt strings in Python).
- **S2.3** Add per-NPC `voice_descriptor` to the system prompt for the 3 demo-path NPCs.
- **S2.4** Add "what I don't know" guard — NPC must not reference any fact not in their injected context.
- **S2.5** Strengthen world-state anchor — replace descriptive hint with authoritative prohibition.
- **S2.6** Write 3 new LLM judge evals; iterate until 5/5 pass; update the cache.

**Critical first check:** Verify whether `distorted_summary` from the KNOWS_ABOUT edge is actually being injected into the dialogue context. If it isn't, fix the context builder before touching voice prompts — voice work is meaningless without the right data.
