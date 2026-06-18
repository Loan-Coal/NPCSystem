# EXP-40 slice-2 — NegotiationBackedSyncTradeHandler (real trade logic in dispatch)

**Goal / rationale:** EXP-40 slice-1 introduced `SyncTradeHandlerProtocol` + `MinimalSyncTradeHandler`
(echo-only, no real trade logic). Slice-2 creates a `NegotiationBackedSyncTradeHandler` that wraps the
existing `open_or_resume_trade` (from `engines/interaction/trade_handler.py`) with real
`PricingEngine`-computed center prices, so `dispatch.py` is no longer a data-echo stub.

**First slice status:** `SyncTradeHandlerProtocol` + `MinimalSyncTradeHandler` in
`src/npc_engine/engines/interaction/trade_handler_sync.py`. `dispatch.py` defaults to
`MinimalSyncTradeHandler`. All tests green.

**Slice-2 scope:**

`open_or_resume_trade` requires `player_id`, `seller_id`, and `center_price` — these are not in
`InteractionProposal`. Fix: extend `SyncTradeHandlerProtocol.handle` and `dispatch_interaction` to
accept `player_id: str` and `npc_id: str` parameters (both default to `""` for backward compat).

**Files:**
- EDIT `src/npc_engine/engines/interaction/trade_handler_sync.py`
  - Update `SyncTradeHandlerProtocol.handle` signature:
    `def handle(self, proposal: InteractionProposal, player_id: str = "", npc_id: str = "") -> InteractionState: ...`
  - Update `MinimalSyncTradeHandler.handle` to accept + ignore the new params (keeps existing tests green).
  - Add `NegotiationBackedSyncTradeHandler(store: NegotiationStore, pricing_engine: PricingEngine)`:
    - `handle(proposal, player_id, npc_id)`:
      - Validate `proposal.payload.get("item_type")` not None (raise `ValueError` if missing).
      - Call `pricing_engine.compute_price(item_type=proposal.payload["item_type"])` → `center_price: int`.
      - Call `open_or_resume_trade(proposal, player_id, npc_id, center_price, self._store)` → return result.
    - No async. `PricingEngine.compute_price` is synchronous.
- EDIT `src/npc_engine/engines/interaction/dispatch.py`
  - Update `dispatch_interaction(proposal: InteractionProposal, player_id: str = "", npc_id: str = "") -> InteractionState`.
  - Pass `player_id` and `npc_id` to `_trade_handler.handle(proposal, player_id, npc_id)`.
- EDIT `src/npc_engine/api/dependencies.py`
  - Add `get_negotiation_store()` `@lru_cache` factory returning `NegotiationStore()`.
  - Add `get_sync_trade_handler()` `@lru_cache` factory returning
    `NegotiationBackedSyncTradeHandler(store=get_negotiation_store(), pricing_engine=get_pricing_engine())`.
  - Add startup call: `set_trade_handler(get_sync_trade_handler())` in the lifespan or dependency init path.
    Note: `get_pricing_engine()` already exists in `dependencies_engines.py` — import it from there.
- EDIT `tests/unit/test_trade_dispatch.py` — update existing tests to pass `player_id="p1", npc_id="npc1"`
  where needed; add new test: `NegotiationBackedSyncTradeHandler` with mocked `PricingEngine` +
  `NegotiationStore` returns `STATUS_OPEN` on `propose_trade` with no move.

**Current state of touched files:**
- `trade_handler_sync.py`: `SyncTradeHandlerProtocol.handle(self, proposal)` (1 param).
- `dispatch.py:73`: `dispatch_interaction(proposal: InteractionProposal) -> InteractionState`.
- `dispatch.py:87`: `return _trade_handler.handle(proposal)`.
- `dependencies.py:226 lines`: no `NegotiationStore` entry yet.

**Graph/API surface:** Engine-internal + `api/dependencies.py` wiring. No new HTTP route.
No schema change. `NegotiationStore` is already in `engines/interaction/negotiation_store.py`.

**Architecture fit:** `NegotiationBackedSyncTradeHandler` is a new file addition (OCP). `dispatch.py`
edit is minimal (signature + forward). All three modules stay within 300-line limit.

**Import note:** `get_pricing_engine()` lives in `dependencies_engines.py` — import it there, not a
new definition.

**Done when:** `pytest tests/unit/test_trade_dispatch.py tests/unit/test_interaction_phase1.py -q`
green; `dispatch_interaction(proposal, "player1", "npc1")` for `propose_trade` returns `STATUS_OPEN`
(session opened via real `open_or_resume_trade`).
