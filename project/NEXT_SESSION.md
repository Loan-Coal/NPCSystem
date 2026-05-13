# Next Session Instructions

## Phase 4 — Authoring engines. Feature 4.4 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

## Phase 4.1–4.3 completion status (committed 2026-05-13)

- 4.1: Faction politics engine (deterministic rules + decay).
- 4.2: Quest generation engine (slot-filling, LLM flavor, graph validation).
- 4.3: Story pacing engine (WorldState max_event_severity + quest_generation_rate).
- 686 unit tests green.

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 4.4 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 4 row: 4.1–4.3 ✅, 4.4 IN_PROGRESS.

---

## Feature 4.4 — Economy engine (basic)

Read `project/ROADMAP.md` lines 701–719 first (the authoritative spec).

**Context:** Items already have `OWNS` edges (from 3.6). This feature adds pricing: a
deterministic service that computes an item's value at a given location, applying modifiers for
rarity, active events, and faction membership. A trade endpoint handles offer/accept logic using
unified valuation. No LLM. No new graph nodes or edges (prices are computed, not persisted).

### Architecture

New files in `engines/economy/` (currently a stub re-export package — keep backward compat):
- `pricing_rules.yaml`:
  ```yaml
  base_prices:
    sword: 50
    potion: 20
    map: 10
    default: 5
  location_modifiers:
    - location_type: frontier
      item_type: weapon
      multiplier: 1.5
    - location_type: market
      item_type: any
      multiplier: 0.9
  event_modifiers:
    - event_type: war
      item_type: weapon
      multiplier: 2.0
    - event_type: plague
      item_type: potion
      multiplier: 3.0
  faction_discount: 0.1   # 10% discount for faction members
  ```
- `pricing_rules_loader.py` — `PricingRules` frozen dataclass; `load_pricing_rules(path) -> PricingRules`.
- `pricing_engine.py` — `PricingEngine(rules: PricingRules)`:
  - `compute_price(item_type, location_type, active_event_types, is_faction_member) -> int`:
    Pure function. Applies base price * location modifier * event modifier * (1 - faction_discount
    if member). Returns int (floor). No I/O.
- `trade_engine.py` — `TradeEngine(pricing_engine, graph_reader, currency_writer, item_writer)`:
  - `evaluate_offer(session, buyer_id, seller_id, item_id, offered_price) -> TradeResult`:
    a. Compute fair price via PricingEngine (needs location lookup via graph).
    b. Accept if offered_price >= fair_price. Reject otherwise with fair_price hint.
    c. On accept: call `transfer_item_atomic` + `transfer_currency_atomic` in one transaction.
    d. Return `TradeResult(accepted, fair_price, final_price)`.

New `graph/pricing_queries.py` — Cypher constants:
- `CYPHER_GET_CHARACTER_LOCATION_TYPE` — given character_id, return location_type of current location.
- `CYPHER_GET_ACTIVE_EVENTS_AT_LOCATION` — event types at location in last N ticks.
- `CYPHER_CHECK_FACTION_MEMBERSHIP` — given two character_ids, check if they share a faction.

New `TradeResult` frozen dataclass in `engines/economy/trade_models.py`:
```python
@dataclass(frozen=True)
class TradeResult:
    accepted: bool
    fair_price: int
    final_price: int | None
    rejection_reason: str | None
```

Wiring:
- `api/dependency_singletons.py` — add `get_pricing_engine()` and `get_trade_engine()` with `@lru_cache`.
- **No tick wiring.** Trade runs when API route is called.
- New routes `api/routes/economy.py`:
  - `GET /v1/admin/economy/price?item_type=&location_id=&character_id=` → `{"price": N}`.
  - `POST /v1/admin/economy/trade` — body: `{buyer_id, seller_id, item_id, offered_price}` → TradeResult.

### Steps

1. Add `engines/economy/pricing_rules.yaml`.
2. Implement `engines/economy/pricing_rules_loader.py` and `engines/economy/pricing_engine.py`.
3. Add `engines/economy/trade_models.py`.
4. Add `graph/pricing_queries.py`.
5. Implement `engines/economy/trade_engine.py` (reuse `currency_writer.transfer_currency_atomic`
   and `item_writer.transfer_item_atomic` — already exist).
6. Add `get_pricing_engine()` and `get_trade_engine()` singletons.
7. Add `api/routes/economy.py` and wire into `main.py`.
8. Unit tests `tests/unit/test_economy_engine.py`:
   - `test_pricing_rules_loader_loads_yaml` — loads real rules.yaml, asserts fields.
   - `test_compute_price_base_only` — no modifiers → base price returned.
   - `test_compute_price_location_modifier` — frontier + weapon → 1.5x.
   - `test_compute_price_event_modifier` — war event → 2x on weapon.
   - `test_compute_price_faction_discount` — member gets 10% off.
   - `test_compute_price_stacked_modifiers` — location + event stack multiplicatively.
   - `test_trade_engine_accepts_fair_offer` — offered >= fair → accepted, transfers executed.
   - `test_trade_engine_rejects_low_offer` — offered < fair → rejected, no transfer.
9. E2E scenario `e2e/scenarios/scenario_economy.py`:
   - Seed buyer (with currency), seller (with item), location.
   - Call `GET /v1/admin/economy/price` → record fair_price.
   - Call `POST /v1/admin/economy/trade` with offered_price = fair_price → assert accepted.
   - Assert buyer now owns item and seller has currency.
   - Cleanup.

### Definition of done (4.4)
- `pricing_rules.yaml` with base prices, location/event/faction modifiers.
- `PricingEngine.compute_price` — pure function, no I/O.
- `TradeEngine.evaluate_offer` — reuses existing atomic writers.
- API routes registered and functional.
- 8 unit tests green.
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: economy engine (Phase 4.4)`

---

## After 4.4 is committed — Phase 4 complete

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 4.4 as DONE, Phase 4 as COMPLETE.
2. `project/STATUS.md` — Phase 4 ✅ Complete.
3. Replace this file with Phase 5 instructions once the Phase 5 plan is written.
4. Read `project/ROADMAP.md` lines 723+ for Phase 5 scope.

---

## Open issues to be aware of (do NOT fix unless blocking)

- ISSUE-013: `how_long_ago` bucket gap 7–27 days (P3)
- ISSUE-005: `adjust_reputation_for_event` not wired (P3)
- ISSUE-006: `Character.faction` string field not migrated (P3)
- ISSUE-004: `edge_updater.py` mypy warning (P3)
- ISSUE-011: `.env` uses Docker DNS (P3)
