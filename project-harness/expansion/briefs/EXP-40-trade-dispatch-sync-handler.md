# EXP-40 — Trade dispatch: replace stub with injectable SyncTradeHandler (first slice)

**Goal / rationale:** `engines/interaction/dispatch.py` routes `propose_trade` to `_stub_handler`
which returns an open-stub state and logs nothing useful. The API layer (`api/routes/interaction.py`)
has real async trade handlers, but `dispatch.py` is sync and called in-process from `demo_game`.
This first slice introduces a `SyncTradeHandlerProtocol` + `MinimalSyncTradeHandler` so the module
is no longer a dead stub, and future callers can inject a production handler. Business tie:
"structured dialogue `action` must drive real interactions" (`BUSINESS_INTENT.md:40`).

**First slice (worker scope):** New `trade_handler_sync.py` with `SyncTradeHandlerProtocol` (Protocol)
and `MinimalSyncTradeHandler` (deterministic, no-DB: validates the proposal structure, returns
`InteractionState(status=STATUS_PENDING, ...)` with the trade details echoed). Update `dispatch.py`
to accept an optional injected handler; default to `MinimalSyncTradeHandler()`. The stub is preserved
for `propose_quest` and `claim_completion` (unchanged) — only `propose_trade` and `give_item` are
upgraded in this slice.

**Current state (verified):**
- `src/npc_engine/engines/interaction/dispatch.py:30`: `_stub_handler` — returns `STATUS_OPEN`/`UI_DIRECTIVE_STUB`.
- `src/npc_engine/engines/interaction/dispatch.py:44–47`: `_DISPATCH` dict hardcodes `_stub_handler` for all kinds.
- `src/npc_engine/engines/interaction/models.py`: `InteractionProposal`, `InteractionState`, `STATUS_OPEN`,
  `STATUS_PENDING` (verify STATUS_PENDING exists — if not, add it as a `Literal` constant in models.py).
- `dispatch.py` module docstring confirms "in-process fallback" purpose.

**Files:**
- NEW `src/npc_engine/engines/interaction/trade_handler_sync.py`
  — `SyncTradeHandlerProtocol(Protocol)`: one method `handle(proposal: InteractionProposal) -> InteractionState`.
  — `MinimalSyncTradeHandler`: validates `proposal.payload` has `item_type`, returns
    `InteractionState(status=STATUS_PENDING, ui_directive="show_trade", metadata={"item_type": ..., "qty": ...})`.
  — No DB, no async, no LLM. Pure data transformation.
- EDIT `src/npc_engine/engines/interaction/dispatch.py`
  — Import `SyncTradeHandlerProtocol`, `MinimalSyncTradeHandler` from the new module.
  — Replace `_DISPATCH` hardcoded dict with a module-level `_trade_handler: SyncTradeHandlerProtocol = MinimalSyncTradeHandler()`.
  — `dispatch_interaction` for `propose_trade`/`give_item`: delegate to `_trade_handler.handle(proposal)`.
  — Add `set_trade_handler(handler: SyncTradeHandlerProtocol) -> None` for injection (test seam).
- NEW `tests/unit/test_trade_dispatch.py`
  — Test `dispatch_interaction(InteractionProposal(kind="propose_trade", ...))` returns `STATUS_PENDING`.
  — Test missing `item_type` payload raises `ValueError` from the handler (not stub silence).
  — Test injected mock handler is called.

**Graph/API surface:** Engine-internal only. No route change, no schema change.

**Architecture fit:** New-file-add for the handler. `dispatch.py` edit is minimal (import + delegate).
`SyncTradeHandlerProtocol` follows the ISP rule (one method, small).

**Test plan:**
Write `tests/unit/test_trade_dispatch.py` FIRST. Run:
`pytest tests/unit/test_trade_dispatch.py -q`

**Done when:** Tests green; `propose_trade` returns `STATUS_PENDING` with item echo; the stub path
remains for `propose_quest`/`claim_completion`. Next slice: inject `AsyncTradeHandler` wrapping the
real economy engine via `api/dependencies.py`.
