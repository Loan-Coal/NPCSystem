# FIX-SEV-19 — Env-gate LLM prompt/secret logging

**Severity:** MEDIUM · **Effort:** S · **Category:** security / observability
**Absorbs:** PROMPT-06, SEC-05, SEC-11

## Problem
Full LLM prompts (player messages + serialized context) are logged whenever
`LOG_LLM_PROMPTS` is true, with NO `ENV == "dev"` guard. The strict rule is: log
prompts/responses only when `LOG_LLM_PROMPTS is True AND ENV == "dev"`.

## Current shape (verified)
- `src/npc_engine/config.py:162` — `LOG_LLM_PROMPTS: bool = False`
- `src/npc_engine/config.py:163` — `ENV: Literal["dev", "staging", "prod"] = "dev"`
- `src/npc_engine/engines/dialogue/dialogue_handler.py:100` — passes
  `log_prompts=settings.LOG_LLM_PROMPTS` (NO env check) into the llm client.
- `src/npc_engine/engines/dialogue/llm_client.py:42,62,88,138,202` — `_log_prompts`
  gates the actual DEBUG prompt logging on three paths (generate, stream, structured).
- `src/npc_engine/.env.example:68` — already `LOG_LLM_PROMPTS=false` (no change needed
  except a warning comment).

## Steps
1. In `dialogue_handler.py`, add a small public helper (importable for the test), e.g.
   `def resolve_log_prompts(settings: Settings) -> bool: return settings.LOG_LLM_PROMPTS and settings.ENV == "dev"`.
   Use it at line 100 instead of the bare `settings.LOG_LLM_PROMPTS`.
2. Confirm `llm_client.py` itself doesn't read `settings.LOG_LLM_PROMPTS` directly
   anywhere (it only uses the injected `_log_prompts` flag — keep it that way; the
   gating belongs at the composition point in dialogue_handler).
3. In `.env.example`, add a one-line comment above `LOG_LLM_PROMPTS=false`:
   `# Only takes effect when ENV=dev; ignored in staging/prod.`

## Verification
- `tests/unit/test_sev19_prompt_redaction.py`:
  - `resolve_log_prompts` returns True only for `LOG_LLM_PROMPTS=True AND ENV="dev"`.
  - False for `(True, "staging")`, `(True, "prod")`, `(False, "dev")`.
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev19_prompt_redaction.py -q`

## Blast radius
Dialogue logging only. No behavior change in dev; suppresses prompt logging in
staging/prod even if the flag is left on.
