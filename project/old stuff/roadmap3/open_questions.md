# Open Questions

These are items found during the V3 audit that require human input before or
early in Phase 0. Each has a clear decision point and action if resolved.

---

## Q1 — Is MistralAdapter active, and should LlamaAdapter be deleted?

**Found:** Two adapters exist alongside OllamaAdapter:
- `src/npc_engine/engines/llm/mistral_adapter.py` — full HTTP adapter targeting
  `/generate`, `/generate_structured`, `/stream` endpoints (Mistral-compatible
  API, not Ollama API).
- `src/npc_engine/engines/llm/llama_adapter.py` — 14-line thin wrapper that
  inherits MistralAdapter with no behavioral changes.

Static analysis found no `llm_config.yaml` referencing either adapter by name
(all observed configs use OllamaAdapter). But static analysis cannot rule out
environment-variable-driven adapter selection at runtime.

**Question:** Is MistralAdapter currently pointed at any running local service
(e.g., a Mistral.rs or vLLM server separate from Ollama)? Or is it also
effectively unused?

**Action if MistralAdapter is active:** Phase 0 logging must cover both
Ollama and Mistral call paths.

**Action if both are orphaned:** Proposed Decision 4 (LlamaAdapter removal)
can be expanded to include MistralAdapter. Phase 0 includes deleting both
and their tests, simplifying the adapter surface before the model swap.

---

## Q2 — Does `settings.LOG_LLM_PROMPTS` already dump the full assembled prompt?

**Found:** `dialogue_handler.py` passes `log_prompts=settings.LOG_LLM_PROMPTS`
to `DialogueLLMClient`. The actual logging implementation is in
`engines/dialogue/llm_client.py`, which was not read during the audit.

**Question:** Does `LOG_LLM_PROMPTS=true` in `.env.dev` already produce a log
line with:
- (a) the raw `serialized_context` string before it is passed to `build_dialogue_prompt`?
- (b) the final assembled prompt string (including `CONTEXT=...` and `PLAYER_MESSAGE=...`)?

**Action if (b) is already logged:** Phase 0 diagnostic can start immediately
by setting `LOG_LLM_PROMPTS=true` and running the war scenario. No code changes
needed in Phase 0.1.

**Action if only (a), or neither:** Phase 0.2 must add a DEBUG-level log line
in `prompt_builder.py::build_dialogue_prompt` (after the f-string assembly)
and optionally in `context_builder.py::build_serialized_context` (before and
after budget enforcement). One or two lines; no architecture change.

---

## Q3 — Should the `explicit` relevance weight be implemented or removed?

**Found:** `docs/RELEVANCE_WEIGHTS.md` describes a 6th weight `explicit`
(boolean game-engine flag, example value 0.10 in the balanced profile). The
`RelevanceWeights` Pydantic model has 5 fields only; `explicit` is absent from
both the model and `context_scoring.py`. The built-in weight profiles in code
(`investigation`, `political`, `social`) are not documented in RELEVANCE_WEIGHTS.md.

**Question:** Is explicit per-node relevance tagging a feature we want for V3?

- If **yes**: Phase 1 scope includes adding the `explicit` field to
  `RelevanceWeights`, scoring logic in `context_scoring.py`, and updating
  `RELEVANCE_WEIGHTS.md` to document all four built-in profiles. The demo game
  can then pass `explicit=true` on nodes it wants the NPC to prioritize.
- If **no**: Phase 0 scope includes a one-line edit to `RELEVANCE_WEIGHTS.md`
  removing the `explicit` example and adding a note that it is deferred.
  (This counts as an open doc update, logged as a finding, not an edit in
  Phase 0 since Phase 0 is read-only for docs.)

**Note:** Phase 0 is read-only for all files outside `project/roadmap3/`. The
resolution of this question should be documented in `phase0_audit/decisions.md`
and actioned in Phase 1 (or Phase 0 if the human resolves it before Phase 0
ends).

---

## Q4 — Are Phase 7 L engines completely out of scope for the demo game?

**Found:** Phase 7 L deferred modules: investigation engine, political
simulation (succession/agenda), social simulation (needs/satisfaction), and
strategy/4X (military). These engines exist in `src/npc_engine/engines/` with
graph nodes defined but incomplete implementation.

**Question:** Should the demo game expose any Phase 7 L functionality (even
partially), or are these engines completely invisible to the demo?

- If **completely invisible:** Phase 2 demo game scope is limited to dialogue,
  gossip propagation, and economy — which are fully implemented and tested.
- If **partially exposed:** Phase 2 scope must include at least stub-level
  integration with the relevant engine, and Phase 3's fine-tuning candidate
  selection changes (investigation or political dialogue may be better
  fine-tuning targets than gossip).

This question affects Phase 2 scope significantly. Recommend deciding before
Phase 1 ends.

---

## Q5 — Is `scenario_war_breaks_out.py` the correct primary diagnostic scenario?

**Found:** The scenario exists in `e2e/scenarios/scenario_war_breaks_out.py`
and is the one cited in the context-not-respected report. However, the survey
also found `scenario_dialogue_reputation.py` (reputation-aware dialogue with
±80 standing), which tests a different world-state signal.

**Question:** Is the war scenario the canonical failing case, or are there
other scenarios where the same symptom (model ignores world state) is
reproducible and equally important?

**Action:** If additional failing scenarios are known, list them in
`phase0_audit/handoff.md` so Phase 1 can target fixes against all of them,
not just the war case. Phase 0 defaults to the war scenario as the primary
diagnostic; reputation scenario is a secondary check.
