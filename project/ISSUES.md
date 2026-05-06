# Issues Log

Persistent issues log. Read at the start of every session. Updated whenever
work is deferred or completed.

Rules:
- Never reuse IDs.
- Never delete entries. Mark as `[FIXED]` instead.
- Severity: P1 (blocking) | P2 (annoying) | P3 (nice-to-fix).
- New issues get the next monotonic ID.

---

## Open

(no open issues)

---

## Closed

## [FIXED] ISSUE-001: top_p and stop_sequences stored but not forwarded to adapters
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/llm/factory.py`, all adapter `generate`/`stream` call sites
**Description:** `EngineModelConfig.llm` declares `top_p` and `stop_sequences` fields
(required by ROADMAP 0.4 schema), but none of the LLM adapters accept these parameters.
The values are stored in config but silently ignored when building generation calls.
**Why deferred:** Adapters need interface updates (protocol + all implementations). Not
blocking — default adapter behaviour is acceptable for current backends.
**To fix:** Add `top_p: float` and `stop_sequences: list[str]` to `LLMClientProtocol.generate`
and `stream` signatures; update all adapters; forward from `DialogueLLMClient`.
**Fixed:** 2026-05-06, stability_refactor — added optional `top_p`/`stop_sequences` to all
three protocol methods; updated OllamaAdapter (forwarded to `options`), MistralAdapter
(forwarded to payload), MockLLMAdapter (accepted, ignored); `DialogueLLMClient` stores and
forwards both params; `DialogueHandler` passes them from `engine_model_config.llm`.

---

## [FIXED] ISSUE-002: currency_engine contract name vs economy/ directory mismatch
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/contracts/currency_engine.yaml`,
`src/npc_engine/engines/economy/`
**Description:** `_engine_dir_from_contract_name("currency_engine")` → `"currency"`,
but the actual engine directory is `engines/economy/`. If `currency_engine` ever
gains `uses_llm: true`, `get_config("currency")` will look in the wrong directory.
Currently `uses_llm: false` so there is no runtime failure.
**Why deferred:** Not blocking today. Renaming the directory requires touching imports.
**To fix:** Either rename the contract to `economy_engine` or rename the directory to
`engines/currency/` and update all imports. Coordinate with any planned economy feature work.
**Fixed:** 2026-05-06, stability_refactor — renamed `engines/economy/` → `engines/currency/`;
updated `__init__.py` docstring. No import changes needed (directory was empty stub).

---

## [FIXED] ISSUE-003: OLLAMA_MODEL in Settings is superseded by per-engine model declaration
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/config.py` (`OLLAMA_MODEL` field),
`src/npc_engine/engines/llm/factory.py` (`create_llm_client`)
**Description:** `Settings.OLLAMA_MODEL` was the global model name used by the Ollama
adapter. The new `create_llm_client_for_engine` reads the model from `engine_config.llm.model`
instead, making `OLLAMA_MODEL` redundant for all engines that use the new factory path.
`OLLAMA_MODEL` is still read by the legacy `create_llm_client` function which remains for
backward compat.
**Why deferred:** Removing it requires auditing all remaining callers of `create_llm_client`
and may affect tests that construct Settings with this field.
**To fix:** After all call sites migrate to `create_llm_client_for_engine`, remove
`OLLAMA_MODEL` from `config.py` and delete the legacy `create_llm_client` function.
**Fixed:** 2026-05-06, stability_refactor — confirmed zero callers of `create_llm_client`;
removed `create_llm_client`, `BACKEND_BUILDERS`, and all private `_create_*` helpers from
`factory.py`; removed `OLLAMA_MODEL` and `LLM_BACKEND` from `config.py`; rewrote
`test_llm_factory.py` to target `create_llm_client_for_engine`.

---

<!--
Template for a new issue:

## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 | P2 | P3
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.

When fixed, change the heading to:
## [FIXED] ISSUE-NNN: <short title>
And add:
**Fixed:** YYYY-MM-DD, in <commit/task>
-->
