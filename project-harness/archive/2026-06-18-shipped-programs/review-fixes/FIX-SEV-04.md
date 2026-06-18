# FIX-SEV-04 — `KnowledgeState` Literal across 4 sites

**Severity:** HIGH · **Lens:** L3 (L3-10)

## Problem
The knowledge-state values `"knows"` and `"rumor"` are hardcoded string literals at four independent
sites with no `Literal`/`Enum`. A typo at any site is a silent runtime bug; a third state cannot be added
safely. CLAUDE.md strict: fixed value sets use `Literal`/`Enum`, never raw strings.

## Current shape (verify against code now)
- `src/npc_engine/engines/.../knowledge_propagator.py:48,84`
- `src/npc_engine/engines/gossip/gossip_handler.py:272`
- `src/npc_engine/retrieval/subgraph_retriever.py:39`
- `src/npc_engine/api/.../npc_state.py:47`

## Steps
1. Add `KnowledgeState = Literal["knows", "rumor"]` and `KNOWS = "knows"` / `RUMOR = "rumor"` named
   constants in a shared low-layer module (e.g. `type_registry/` or `common/` — pick the one already
   holding similar contracts; do not create an upward dependency).
2. Replace the 4 raw-string sites with the constants; type any model field / function param/return that
   carries the value as `KnowledgeState`.

## Verification
- `pytest tests/ -k "knowledge or gossip or npc_state or subgraph" -q`.
- `make check` (mypy 0, layer check green — verify the new constants module sits at/below every consumer's layer).

## Blast radius
4 source files + one shared constants module. No schema change (graph stores the same string values).
