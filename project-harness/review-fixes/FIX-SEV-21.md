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
