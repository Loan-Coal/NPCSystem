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

## [2026-05-21] P1.3 — P1.2 fix verified; no model swap needed

**Context:** War scenario (`scenario_war_breaks_out.py`) run to confirm whether the
MUST NOT epoch framing in `system_v1.yaml` changed Mixtral 8x7b's behavior.

**Options considered:**
- Swap model to Qwen2.5-7B or Llama 3.1 8B if prompt fix insufficient.
- Keep Mixtral 8x7b if fix sufficient.

**Decision:** Keep Mixtral 8x7b. Turn 2 response ("The road to the capital is open,
but I must caution you. With the northern war raging, it's a dangerous journey.")
correctly conveys danger. Transcript saved to `transcripts/war_epoch_baseline.md`.

**Consequences:** P1.3 is complete. P1.4 proceeds as planned.

**Cross-phase?** No — stays here.

## [2026-05-21] P1.4 — War epoch judge test added; JUDGE_MODEL env var required

**Context:** Added `test_war_epoch_reflects_danger` to `scenario_llm_judge.py` as a
repeatable gate for the epoch constraint. Discovered that the default `JUDGE_MODEL=llama3`
is not available locally (only `mixtral:8x7b` is pulled). All 3 pre-existing judge tests
also fail for the same reason — this is a pre-existing environment issue, not a regression.

**Options considered:**
- Pull `llama3` as a second local model.
- Use `JUDGE_MODEL=mixtral:8x7b` (same model as the NPC engine).
- Document requirement and leave default.

**Decision:** Leave default as `llama3` (matches the scenario file header documentation).
Set `JUDGE_MODEL=mixtral:8x7b` when running `make eval-llm` locally until a dedicated
judge model is pulled. The judge correctly evaluates responses when pointed at Mixtral —
confirmed with a spot-check: canned response scored NO, proper danger response scores YES.

**Consequences:** `make eval-llm` requires `JUDGE_MODEL=mixtral:8x7b` in this environment.
CI / shared environments must pull the judge model or set this env var.

**Cross-phase?** No — stays here.
