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

## [2026-05-21] P1.3 correction — model swap did occur

**Context:** The P1.3 entry above recorded "Keep Mixtral 8x7b" — this captured an
intermediate evaluation state before the model swap was committed. The authoritative
record is `llm_config.yaml` (`model: qwen2.5:7b`) and git commit a507530 ("swap to
qwen2.5:7b"). The prompt fix was verified with Mixtral, then the model was swapped.

**Decision:** Acknowledge the correction. The NPC dialogue engine is on `qwen2.5:7b`.

**Cross-phase?** No — stays here.

## [2026-05-21] P1.5 — Implement explicit field via request-level explicit_node_ids

**Context:** `explicit` was documented in `RELEVANCE_WEIGHTS.md` and `DATA_MODELS.md`
as a 6th scoring component but was absent from `RelevanceWeights`, all weight profiles,
`context_scoring.py`, and `context_relevance_engine.py` — a complete doc-only stub.
User confirmed: implement with a strong, testable mechanism.

**Options considered:**
- Request-level `explicit_node_ids` in `DialogueRequest` — game engine passes node IDs per turn.
- Graph node property flag (persistent, stale-flag risk).
- Keyword-match automatic score (fuzzy, duplicates vector similarity).
- Topic classifier extension (coarse, type-level not node-level).

**Decision:** Option A — `explicit_node_ids: tuple[str, ...]` added to `DialogueRequest`.
Node IDs in the set score `explicit=1.0`; all others score `0.0`. Threaded through
`build_serialized_context()` → `rank_tier_items()` → `_build_candidate()`. Mirrors
the existing `active_quest` per-request signal pattern. `RelevanceWeights.explicit`
defaults to `0.0` so all existing profiles remain valid without modification.

**Consequences:** Game engine (Phase 2) must populate `explicit_node_ids` to use this
feature; it is inert (no-op) otherwise. Primary use is Tier A graph nodes whose IDs
the game engine can determine at call time. Graduate to project/DECISIONS.md at P1.7
since Phase 2 must know about the API field.

**Cross-phase?** Yes — graduate to project/DECISIONS.md at P1.7.

## [2026-05-21] Model upgrade to qwen2.5:14b

**Context:** Previous model was qwen2.5:7b (~4.7 GB Q4). User requested upgrade to
best available Ollama model fitting in 12 GB VRAM for improved instruction-following
and JSON schema adherence in dialogue generation.

**Options considered:**
- `qwen2.5:14b` (~8.5 GB Q4_K_M) — direct lineage upgrade, best instruction-following in class.
- `gemma3:12b` (~8 GB Q4) — strong creative, weaker strict-JSON adherence.
- `phi4:14b` (~9.8 GB Q4) — tight on 12 GB, less proven for roleplay.

**Decision:** `qwen2.5:14b`. Only change: `model` field in
`src/npc_engine/engines/dialogue/llm_config.yaml`. Engine is model-agnostic via
the Ollama backend — no other code changes required.

**Consequences:** War scenario must be re-run after pull to confirm MUST NOT epoch
constraints still hold with the 14b model. Pull: `ollama pull qwen2.5:14b`.

**Cross-phase?** Yes — graduate to project/DECISIONS.md at P1.7.
