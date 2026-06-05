# FIX-SEV-27 — Structured-output reliability: temperature + schema + repair retry

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** M
**Category:** prompt · **Absorbs:** PROMPT-03, PROMPT-07
**Depends on:** SEV-01 (done)

## Problem
1. `ollama_adapter.py:132-143` omits `temperature` → structured calls run at model default (~0.8); guard-sensitive output is non-deterministic.
2. Same path passes `format:"json"` (free-form) — the Pydantic model's JSON schema is discarded; the model can return any shape.
3. `llm_client.py:93-112` catches `ValidationError` → immediately serves canned fallback with no repair attempt. Combined with SEV-01 this means `keyword_none` evals pass on fallback silently.

## Current shape
- `src/npc_engine/engines/llm/ollama_adapter.py:132-143`: no `temperature` in request dict; `format: "json"` only
- `src/npc_engine/engines/llm/llm_client.py:93-112`: `except ValidationError: return fallback_response` with no retry
- `LLMClientProtocol`: no documented retry contract
- `MockLLMAdapter`: never raises `LLMTimeoutError`/`LLMRequestError` and never returns invalid JSON

## Steps

### 1. Add `STRUCTURED_OUTPUT_TEMPERATURE` config
In `config.py`: add `STRUCTURED_OUTPUT_TEMPERATURE: float = 0.1`.

### 2. Wire temperature and schema in `ollama_adapter.py`
In `generate_structured()`, update the request dict:
```python
request["temperature"] = settings.STRUCTURED_OUTPUT_TEMPERATURE
request["format"] = response_model.model_json_schema()
```

### 3. Add one repair retry in `llm_client.py`
```python
for attempt in range(2):
    try:
        raw = await self._adapter.generate_structured(prompt, response_model)
        return response_model.model_validate(raw)
    except ValidationError as exc:
        logger.warning("structured_output_validation_failed",
                       attempt=attempt, model=self._model_name, error=str(exc))
# both attempts failed → canned fallback
logger.error("structured_output_fallback_served", model=self._model_name)
return self._canned_fallback(response_model)
```

### 4. Update `LLMClientProtocol` docstring
Document: "one repair retry before canned fallback; logs WARNING per failed attempt and ERROR on fallback."

### 5. Update `MockLLMAdapter` for LSP compliance
Add optional modes:
```python
class MockLLMAdapter:
    def __init__(self, *, fail_first_call: bool = False, return_garbage: bool = False): ...
```
- `fail_first_call=True`: raises `ValidationError` on the first `generate_structured` call, succeeds on the second.
- `return_garbage=True`: returns `{"__garbage__": True}` which fails Pydantic validation.

## Verification
- `tests/unit/test_structured_output_sev27.py`:
  - `fail_first_call=True` mock → retry succeeds → canned fallback NOT served.
  - `return_garbage=True` (both calls) → canned fallback IS served → WARNING logged twice + ERROR once.
  - Normal call → temperature 0.1 is in the Ollama request payload.
- `make type` passes.

## Blast radius
All `generate_structured()` call sites; `LLMClientProtocol` implementors must be checked for LSP; `MockLLMAdapter` gains new modes (backward-compatible default).
