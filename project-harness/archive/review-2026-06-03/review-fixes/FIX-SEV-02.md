# FIX-SEV-02 — Remove `npc_engine` imports from `demo_game` (CRITICAL)

**Severity:** CRITICAL · **Confidence:** Confirmed · **Effort:** M
**Category:** layer-violation / product · **Absorbs:** DEMO-01
**Depends on:** none. **Blocks:** any "demo is a standalone licensable client" claim.

## Problem
`demo_game` is documented as a pure REST/WS client with **zero imports from `src/`**, but it imports engine internals at 3 sites and runs interaction-dispatch domain logic in-process.

## Current shape
- `demo_game/game_controller.py:49` → `from npc_engine.engines.interaction import dispatch_interaction`
- `demo_game/game_controller.py:518` → `from npc_engine.engines.interaction.models import InteractionProposal as _EngineProposal`; then `:518-526` builds `_EngineProposal(...)` and calls `dispatch_interaction(eng_proposal)` **inside the demo process**.
- `demo_game/run.py:49` → `from npc_engine.engines.dialogue.prompt_builder import PROMPT_VERSION as _PROMPT_VERSION` (used only as a cache-key constant).

## Target shape
Interaction resolution happens server-side via HTTP; the demo holds only its own local models and constants.

## Steps
1. **Add an API endpoint** `POST /v1/interaction/dispatch` in `src/npc_engine/api/routes/interaction.py` that accepts `{kind, target_id, payload}`, validates via a Pydantic request model, calls `dispatch_interaction` server-side, and returns the result through `ok_response` (ideally a typed `response_model=` — see SEV-14).
2. **Add a client method** `EngineClient.dispatch_interaction(kind, target_id, payload)` in `demo_game/client.py` calling the new endpoint.
3. **Define a demo-local model**: a small Pydantic `InteractionProposal` in `demo_game/` (do **not** import the engine model). Map `turn.interaction_proposal` → the new client call.
4. **Inline the constant**: replace the `PROMPT_VERSION` import in `run.py` with a demo-side `DEMO_CACHE_VERSION` constant in `demo_game/constants.py` (the cache key only needs to change when *demo* behavior changes).
5. Remove all three `npc_engine` imports.
6. If for hackathon speed the coupling must stay temporarily, record an explicit layer-rule waiver in `project-harness/DECISIONS.md` — currently undocumented.

## Verification
- `rg "from npc_engine|import npc_engine" demo_game` → 0 hits.
- `make demo-run ARGS=--dry-run` runs in a fresh venv that has only `demo_game/` + the HTTP API on `PYTHONPATH` (no `src/`).
- `make test-demo` green; the new endpoint has a contract test.

## Blast radius
Trade/quest/give-item proposal resolution; the demo-as-product story. The new endpoint also benefits real integrating studios (they need the same dispatch).
