# Phase 1 Decisions

<!-- Append entries here as decisions are made during Phase 1 execution. -->
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

## [2026-05-20] P1.2 — Move _SYSTEM_PROMPT to YAML + authoritative epoch rule

**Context:** CLAUDE.md rule "No prompt strings outside `prompts/`" was violated:
`_SYSTEM_PROMPT` was an inline Python string in `prompt_builder.py`. Phase 0 D2
also required the epoch instruction to be rewritten as a hard constraint.

**Options considered:**
- Keep inline string, add MUST/MUST NOT language in-place (violates CLAUDE.md rule).
- Move to YAML only, keep descriptive epoch framing (fixes structure, not behavior).
- Move to YAML and rewrite epoch rule (fixes both) — **chosen**.

**Decision:** Created `src/npc_engine/prompts/dialogue/system_v1.yaml` using the
`system` key schema from `chapter_label_v1.yaml`. Epoch rule rewritten with
`AUTHORITATIVE` label and explicit `MUST NOT` prohibitions (e.g., `epoch = "war":
MUST NOT describe roads or travel as safe`). Loaded via `load_yaml_mapping`.
Prompt version bumped `stage_b_v1.0 → stage_b_v1.1`.

**Consequences:** All future system prompt edits go through the YAML file.
Whether the MUST NOT framing is sufficient for Mixtral 8x7b cannot be confirmed
without running the war scenario — P1.3 (model swap) remains contingent on that result.

**Cross-phase?** No — stays here.
