# FIX-SEV-04 — Move Cypher and transaction control back into `graph/`

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** L (multi-session)
**Category:** layer-violation / data-integrity · **Absorbs:** ARCH-01, ARCH-06, GRAPH-01, GRAPH-02, ARCH-09
**Depends on:** SEV-31 (layer model + contract checker — do that first so this is enforceable). **Folds in:** SEV-17, SEV-30.

## Problem
Two strict rules are broken pervasively: "No Neo4j queries outside `graph/`" and "`graph_writer.py` is the only file that opens/commits transactions; sub-writers receive `AsyncSession`."

## Current shape (enumerated instances)
**Raw Cypher / `session.run` in engines (16):** `engines/gossip/{gossip_handler,knowledge_propagator,pair_selector,edge_updater}.py`, `engines/skill/skill_progression_engine.py`, `engines/events/{event_handler,awareness_seeder,location_scoper}.py`, `engines/faction_politics/faction_politics_engine.py`, `engines/military/military_battle_service.py`, `engines/quest_generation/{quest_generation_engine,slot_validator}.py`, `engines/interaction/quest_verifier.py`, `engines/clique/clique_formation_engine.py`, `engines/story_pacing/pacing_queries.py`, `engines/routine/routine_queries.py`, `engines/idempotency/neo4j_queries.py`. Also `retrieval/{graph_rag,embedding_reconciler}.py`, `world/{world_reader,world_writer}.py`, `scheduler/{tick_scheduler,tick_lease}.py`.
**Transactions opened/committed outside `graph_writer.py`:** `graph/{belief,faction,reputation,schedule,goal,item,owes,secret,memory,quest_node}_service.py`, `graph/relation_delta_writer.py:60`, `graph/currency_writer.py:118`, `graph/item_writer.py:62`; **in engines:** `engines/events/event_handler.py:181` + `:255 tx.commit()`, `engines/faction_politics/faction_politics_engine.py:134,182`, `engines/quest/quest_lifecycle_engine.py:94,119,247`.
**Magic label/rel-type strings** live inside this Cypher (`:Character`, `:Event`, `KNOWS_ABOUT`, `:Quest {status:'completed'}` — the last also duplicates the quest-status enum).

## Target shape
Each Cypher constant + its `session.run` lives in a `graph/<domain>_queries.py` function taking `AsyncSession`/`tx`. Engines call typed functions. Transaction lifecycle is owned by `graph_writer.py` (or the request-scoped session in the API composition root). Labels/rel-types come from shared constant modules (`graph/labels.py`, `graph/relationships.py`).

## Steps (incremental, one domain per session)
1. Land SEV-31 first: assign every package a layer rank and extend `scripts/check_contracts.py` to fail on engine Cypher keywords and `begin_transaction` outside `graph/`. This gives a red→green target.
2. Create `graph/labels.py` / `graph/relationships.py` constant modules; replace inline label/rel-type literals; replace `'completed'` with the quest-status enum.
3. For each engine domain (start with gossip — highest churn): move `CYPHER_*` + `session.run` into `graph/<domain>_queries.py`; the engine imports and calls those, passing the session it received.
4. Remove `begin_transaction`/`commit` from `graph/` sub-writers and from engines; have them accept an injected `tx`. Centralize tx open/commit in `graph_writer.py` / the API dependency that owns the session.
5. Fold in SEV-17 (`cypher_identifier()` on dynamic labels) and SEV-30 (event witness writes inside the same tx) as you touch those files.
6. If `world/` is a legitimate layer, document it in CLAUDE.md (DECISIONS) rather than folding into `graph/`; otherwise fold `world_reader`/`world_writer` into `graph/`.

## Verification
- `rg "MATCH \(|MERGE \(|CREATE \(|session\.run|tx\.run" src/npc_engine/engines src/npc_engine/world` → only delegated graph-function calls.
- `rg "begin_transaction|\.commit\(" src/npc_engine/engines` → 0; `rg "begin_transaction" src/npc_engine/graph` → only `graph_writer.py`.
- `make check-contracts` fails before the move, passes after; a forced mid-transaction error test rolls back fully.

## Blast radius
Most engines + the `world/` package. Large but mechanical once the contract checker defines "done." Do it domain-by-domain behind green tests.
