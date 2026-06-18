# FIX-SEV-09 — Staging/prod gate for `LOG_LEVEL` / verbose logging

**Severity:** MEDIUM · **Lens:** L1 (L1-12)

## Problem
The shipped `.env` sets `LOG_LEVEL=DEBUG` and `LOG_LLM_PROMPTS=true`. The prompt-redaction gate covers
`LOG_LLM_PROMPTS` specifically, but there is no staging/prod guard on `LOG_LEVEL` itself — a deployment
that copies the dev `.env` runs at DEBUG verbosity in production. This mirrors L1-04 (API_KEY_SECRET), which
already raises in staging/prod via `config_validators.py`.

## Current shape (verify against code now)
- `.env` — `LOG_LEVEL=DEBUG`, `LOG_LLM_PROMPTS=true`.
- `src/npc_engine/config/config_validators.py:40-44` — existing staging/prod raise for the dev API key (pattern to mirror).
- `src/npc_engine/config/config.py` — `LOG_LEVEL`, `ENV` fields.

## Steps
1. Add a model/field validator (in `config_validators.py`, same place as the API-key check) that raises a
   domain config error when `ENV in {"staging","prod"}` and `LOG_LEVEL == "DEBUG"` (or `LOG_LLM_PROMPTS` is
   true — confirm whether L1-04's check already covers the prompt flag; if not, fold it in).
2. Keep dev unaffected (DEBUG allowed when `ENV == "dev"`).

## Verification
- `pytest tests/ -k "config_validator or log_level" -q` — add tests: dev+DEBUG passes; staging+DEBUG raises; prod+DEBUG raises.
- `make check`.

## Blast radius
`config/config_validators.py` + `config/config.py`, one test file. No interface change. (Whether to ALSO
hard-fail on `IDEMPOTENCY_ENFORCE_HEADER=false` is a separate operational call — DEC-111, not this fix.)
