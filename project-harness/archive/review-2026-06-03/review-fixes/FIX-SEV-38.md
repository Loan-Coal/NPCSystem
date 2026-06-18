# FIX-SEV-38 — Eval-matcher weaknesses and mock LSP gaps

**Severity:** LOW · **Confidence:** Confirmed/Likely · **Effort:** M
**Category:** eval · **Absorbs:** TEST-05, TEST-08..12, PROMPT-05, PROMPT-08, PROMPT-10, PROMPT-12

## Problem
- `evals/matchers.py:20-34` duplicates judge-prompt string that also appears in `e2e/helpers/llm_judge.py:32-46` — two copies outside `prompts/`.
- `MockLLMAdapter` never raises `LLMTimeoutError`/`LLMRequestError` and never returns garbage → fallback contract untested by unit tests (LSP violation).
- `tone_judge` fails-open: returns `False` on judge infra failure, masking the failure as a content pass.
- `context_block_expected` matcher is silently ignored by the runner when there is no context to check.
- `keyword_any` with a single-item list is near-tautological; no minimum-specificity guard.
- LLM-judge tests hard-assert despite "treat failures as warnings" docstring.

## Steps

### 1. Extract duplicated judge prompt
Move the shared judge-prompt string from `evals/matchers.py` and `e2e/helpers/llm_judge.py` to `prompts/eval/tone_judge.yaml`; load via the standard prompt YAML loader in both files.

### 2. Strengthen `MockLLMAdapter` (LSP)
Add two modes to `MockLLMAdapter` in `tests/conftest.py` (or wherever it lives):
- `MockLLMAdapter(raise_on_generate=LLMTimeoutError)` — raises on first call
- `MockLLMAdapter(return_garbage=True)` — returns `{"__garbage__": True}` which fails Pydantic validation

Write tests exercising the fallback path with each mode.

### 3. Fix `tone_judge` fail-open
Replace `except: return False` (or equivalent) with:
```python
except Exception as exc:
    logger.warning("tone_judge_infra_failure", error=str(exc))
    return JudgeResult(score=None, error="infra_failure")
```
Callers treat `score=None` as "inconclusive" (not a pass): log WARNING, do not count as passing guard turn.

### 4. Fix `context_block_expected` silent ignore
If the runner encounters `context_block_expected` and has no context to check, raise `EvalConfigError("context_block_expected matcher requires runner context")` rather than silently skipping.

### 5. Add `keyword_any` minimum-specificity guard
At eval-config load time: if a `keyword_any` matcher has fewer than 2 items, raise `EvalConfigError("keyword_any requires at least 2 keywords to be meaningful")`.

### 6. Wrap LLM-judge assertions
Replace hard-assert LLM-judge calls in eval tests with `pytest.warns` or a soft check that logs but does not fail the test run (matching the "treat as warning" docstring).

## Verification
- `rg 'prompts/eval/tone_judge.yaml' evals/ e2e/` → match in both files
- `tests/unit/test_eval_matchers_sev38.py`:
  - `context_block_expected` with no context → `EvalConfigError`
  - `keyword_any` with 1 item → `EvalConfigError`
  - `tone_judge` infra failure → `JudgeResult(score=None, error="infra_failure")`, WARNING logged
- `make test` passes.

## Blast radius
Eval infrastructure and test utilities only; no production code changes.
