# EXP-216 — Trade dispatch → NegotiationStore (PARTIAL: wire the default)

**Goal / rationale:** `NegotiationBackedSyncTradeHandler` is already built but unwired — the composition
root still defaults to the minimal stub, so `propose_trade` never opens a real negotiation. Wiring the
default makes the economy interactive. Serves BUSINESS_INTENT "economy/trade depth."

**First slice (your scope):** Make the composition root use `NegotiationBackedSyncTradeHandler` as the
default sync trade handler instead of `MinimalSyncTradeHandler`. Smallest change that flips the default.

**Current state (verified):**
- `src/npc_engine/engines/interaction/trade_handler_sync.py:104` — `NegotiationBackedSyncTradeHandler`
  exists (built, takes `NegotiationStore`).
- `src/npc_engine/engines/interaction/dispatch.py:34` (or the composition root `api/dependencies.py`) —
  the default is still `MinimalSyncTradeHandler`. Find where the sync trade handler is constructed/injected
  and swap the default to `NegotiationBackedSyncTradeHandler`, passing the already-available
  `NegotiationStore` (it is already injected into `DialogueHandler`). Verify the exact wiring point
  before editing — prefer `api/dependencies.py` (the sole composition root) over editing `dispatch.py`
  if the choice is made there.

**Files:**
- EDIT the composition root (`src/npc_engine/api/dependencies.py`, or `dispatch.py` if that's where the
  default is selected) — inject `NegotiationBackedSyncTradeHandler` with the existing `NegotiationStore`.
- NEW/EXTEND test: `tests/unit/` — assert the composed/dispatched sync trade handler is the
  Negotiation-backed one (or that `propose_trade` routes to `NegotiationStore.create_session`).

**Graph/API surface:** none new. No schema, no route. DI change only.

**Architecture fit:** composition-root edit (DIP — `api/dependencies.py` is the sole composition root).
No new file needed unless a small factory helps. No schema.

**Test plan (RED first):** assert the active sync trade handler is `NegotiationBackedSyncTradeHandler`
(or that a proposed trade creates a negotiation session via the store). Watch fail (currently minimal),
implement. Run: `pytest tests/unit/ -k trade -q`.

**Done when:** the default sync trade handler is Negotiation-backed; a proposed trade opens a negotiation
session; test passes; no schema change.
