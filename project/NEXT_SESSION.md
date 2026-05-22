# Next Session Instructions

## Current state

Roadmap V3 — **Phase 3: QLoRA Adapter.** Phase 2 is complete and signed off 2026-05-22.

Run baseline checks before touching any code:

```bash
pytest demo_game/tests/ -q    # expect 107 pass
pytest tests/unit/ -q         # ~20 pre-existing failures (ISSUE-019 pattern) — do not investigate
make eval-llm-demo            # expect 2/2 PASS (requires Ollama + qwen2.5:14b)
```

---

## Entry criteria (all green as of 2026-05-22)

| Criterion | Status |
|---|---|
| 107 demo_game tests pass (`make test-demo`) | YES |
| `make eval-llm-demo` — 2/2 PASS (qwen2.5:14b) | YES |
| Manual sign-off: W/C keys, status overlay, live graph | YES |
| `docs/DEMO.md` updated for interactive demo game | YES (P2.6) |
| Engine test suite baseline: 20 failed / 951 passed / 17 skipped | CONFIRMED |

---

## Key context from Phase 2 that Phase 3 needs

### 1. Inner life is served via typed admin endpoints, not graph edges

`GET /v1/admin/beliefs/{character_id}` returns the full belief list.
The `BELIEVES` graph edge is NOT populated by the typed endpoint.
Always use admin endpoints (`/v1/admin/beliefs`, `/v1/admin/goals`, etc.)
for reads and writes — NOT `GET /v1/graph/edges/BELIEVES`.

### 2. Edge schema (do not trust subphases.md names — use these)

| What you might expect | Actual schema | Notes |
|---|---|---|
| NPC-NPC trust via `STANDS_WITH` | `RELATES_TO` | `STANDS_WITH` is Faction→Faction only (int standing) |
| NPC-NPC knowledge via `KNOWS_ABOUT` | N/A | `KNOWS_ABOUT` is Character→Event only |
| Faction antagonism via `OPPOSES` | `STANDS_WITH` negative int | `OPPOSES` is Character→Character only |
| `RELATES_TO` trust negative value | Not possible | trust field is 0–100 |

### 3. `world_state` required fields

Beyond `epoch` and `active_conditions`: `faction_standings` (dict), `time_of_day`,
`weather`, `last_updated_at`, `last_graph_updated_at`.

### 4. Demo world (seeded, stable)

5 NPCs: `mira_innkeeper` (tavern), `aldric_merchant` (market_square),
`captain_sorn` (guard_barracks), `lira_fence` (tavern), `old_henryk` (market_square).
`captain_sorn` has `KNOWS_ABOUT northern_war_begins`.
Idempotent re-seed: `make demo-seed` → `created=0 skipped=53`.

### 5. demo_game/ run model

`demo_game/` at repo root — zero imports from `src/npc_engine/`.
Runs on host: `make demo` → `python -m demo_game`.
Requires `pygame-ce` (not `pygame` — no Python 3.14 wheel).
Config via `.env.demo` (gitignored). See `demo_game/requirements.txt`.

### 6. Active dialogue model

`qwen2.5:14b` — see `src/npc_engine/engines/dialogue/llm_config.yaml`.
Phase 3 QLoRA adapter targets this base.

---

## Open issues relevant to Phase 3

| ID | Severity | Summary |
|---|---|---|
| ISSUE-021 | P3 | `test_gossip_propagates_after_clock_advance` is trivially true (event node is always seeded). Strengthen with edge-count diff before/after advance. |
| ISSUE-020 | P3 | `DialogueTurn.emotion` mapped from `mood_update`, not a first-class engine field. Relevant if Phase 3 prompt changes affect mood output format. |

---

## Phase 3 — QLoRA Adapter entry point

Phase 3 trains a QLoRA adapter on `qwen2.5:14b` to improve NPC role-adherence and
world-state responsiveness. Refer to the Phase 3 spec when it is written.

Evidence from Phase 2:
- `captain_sorn` reliably references war/conflict when asked directly (LLM judge gate, 2/2 PASS).
- `old_henryk`'s gossip-hop response quality is untested — likely a training signal candidate.

Adapter swap when ready: single-line change in `llm_config.yaml` (engine is model-agnostic via Ollama).
