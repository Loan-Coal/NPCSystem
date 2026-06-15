# FIX-SEV-21 — Migrate graph sub-writers to caller-owned transactions

**Severity:** MEDIUM (large refactor) · **Decision:** DEC-119 (migrate all) · **Multi-phase**

## Problem
CLAUDE.md: only `graph_writer.py` opens/commits transactions; sub-writers receive a session/tx. In reality
14+ `graph/` files call `session.begin_transaction()` themselves, so multi-write operations across writers
can't be made atomic. DEC-119: migrate every sub-writer to accept an `AsyncTransaction` and let a
coordinator own the transaction. (SEV-01 already did this for the scheme writers — use it as the template.)

## Current shape (verify against code now)
- `transaction_coordinator.run_in_tx(session, work)` exists (used by scheme code) — the target pattern.
- Sub-writers opening their own tx (grep `begin_transaction` under `src/npc_engine/graph/`): `belief_service`,
  `goal_service`, `item_service`, `memory_service`, `currency_writer`, `relation_writer`, … (14+).
- `scheme_writer.py` (SEV-01) already accepts `tx`/`session` — the reference implementation.

## Steps (one writer-family per commit)
1. For each sub-writer: add an `AsyncTransaction` parameter (or a `tx`/`session` dual like `scheme_writer.add_scheme_step`),
   move the Cypher to run on the passed `tx`, and stop calling `begin_transaction()` internally.
2. Update callers to open a transaction via `run_in_tx` (or pass an existing open tx) so related writes commit atomically.
3. Migrate incrementally — keep each writer-family's tests green before moving to the next.

## Verification
- Per-writer unit tests (fake `AsyncTransaction` records `tx.run`/commit); integration tests where a graph
  harness exists; `make check` after each family.
- Final: grep confirms no `begin_transaction(` outside `graph_writer.py` / `transaction_coordinator.py`.

## Blast radius
Most of `graph/` + their callers in `engines/`/`services/`. **Large, high-regression — phase by writer
family across many commits.** Resolves the L2-01/L2-03 systemic finding.

## Resolution (DONE 2026-06-15, munich-demo)
Migrated in 6 writer-family commits, each gated by `make check` (lint/rules/layers/docstrings/mypy) and the
full 2209-test unit suite:

1. Relation — `relation_delta_writer`, `relation_phase_writer`, `relation_phase_reader`, `relation_reader`,
   `graph_writer.ensure_relation_edge` (`8841abc`). `apply_relation_delta` decomposed into
   `_load_canonical_delta_log` + `_apply_relation_delta_tx` to stay under the 40-line R006 gate.
2. Currency/item — `currency_writer.transfer_currency_atomic`, `item_writer.transfer_item_atomic`,
   `item_service.create_item`/`transfer_ownership` (`41eae17`).
3. Character-knowledge — `belief_service`, `goal_service`, `memory_service`, `knowledge_writer`,
   `secret_service` (`1d6840d`).
4. Faction/reputation — `FactionService` (6 methods), `ReputationService` (4, incl. the 3-write atomic
   `adjust_reputation_with_event`), `reputation_nudge` (`b3efedb`).
5. Quest/schedule — `quest_node_service.create_quest`, `ScheduleService` (3), `owes_service` (2) (`eaed6a0`).
6. Player-model — `player_model_writer.upsert_player_model` (this commit).

**Outcome:** every sub-writer runs its writes through `transaction_coordinator.run_in_tx` (an inner
`_work(tx)` closure) instead of `session.begin_transaction()`. `grep begin_transaction( src/npc_engine/graph/`
now matches **only** `transaction_coordinator.py`; no engine opens a transaction. Note neo4j's
`async with tx:` already committed on clean exit, so the migration is behavior-preserving.

**Scope note:** public `(session, …)` signatures were intentionally preserved, so engine call-sites were not
touched and engines still receive an `AsyncSession`. Removing the session from engines entirely (engines
depend on small repository Protocols; the Neo4j adapter owns the session) is the follow-on **Track D /
GraphRepository facade** — the actual graph/engine decoupling seam.

Several unit-test fake transactions gained a `commit()` method (read-path fakes that the coordinator now
commits): `test_relation_phase_reader`, `test_knowledge_writer`, `test_quest_generation_engine`.
