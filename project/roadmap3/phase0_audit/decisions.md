# Phase 0 Decisions

<!-- Append entries here as decisions are made during Phase 0 execution. -->
<!-- Never edit or delete prior entries. This is an append-only log. -->
<!-- Format for each entry is shown below. -->

<!--
## [YYYY-MM-DD] Decision title

**Context:** What prompted this decision.
**Options considered:** Brief list.
**Decision:** What was chosen.
**Consequences:** What this commits to or forecloses.
**Cross-phase?** Yes — graduate to project/DECISIONS.md | No — stays here
-->

## [2026-05-20] P0.1/P0.2 Diagnosis — failure mode (b): prompt too weak, not retrieval

**Context:** P0.1 baseline capture and P0.2 prompt inspection run on `scenario_war_breaks_out.py`.

**Evidence collected:**
- `context_builder.py:276` inserts `world_state.model_dump_json()` as a `tier0 / priority=100`
  ContextItem — it cannot be budget-truncated out regardless of other context pressure.
- Graph API confirmed `epoch: "war"` was present in the Neo4j node immediately after the
  WorldState upsert (Turn 2 window).
- LLM response Turn 1 (epoch=age_of_peace): *"relatively safe during these times of **peace**"*
- LLM response Turn 2 (epoch=war): *"relatively safe during these times of **war**"*
- The NPC acknowledged the epoch but kept the same threat assessment ("relatively safe"),
  ignoring the behavioral rule: *"war: active conflict nearby — you are tense, wary, roads are
  dangerous"*.

**Options considered:**
- (a) WorldState never reaches prompt — **ruled out** (tier0 / priority=100, confirmed in code)
- (b) Prompt instruction too weak for Mixtral 8x7b to follow — **confirmed**
- (c) Retrieval fills context with stale/wrong events — not tested (not relevant, world state
  is not retrieved via RAG, it is always injected directly)
- (d) Model incapable of structured behavioural change from JSON context — possible co-cause;
  cannot distinguish from (b) without model swap

**Decision:** Root cause is (b). The system prompt names the epoch field and lists the expected
behaviour, but does not mark world state as *authoritative* or give explicit negative
constraints ("you MUST NOT say roads are safe if epoch=war"). Mixtral 8x7b treats it as a hint
rather than a rule.

P0.3 (retrieval diagnostic) and P0.4 (relevance weight audit) are skipped for world-state
context — world state is tier0 and always present. Both subphases remain relevant for NPC
event context (Phase 1 work) but are not blocking the primary diagnosis.

**Consequences:** Phase 1 must strengthen the epoch behavioural instruction. If a stronger
instruction still fails, escalate to P0.5 model swap (Llama 3.1 8B Instruct or Qwen 2.5 7B).

**Cross-phase?** Yes — graduate to project/DECISIONS.md
