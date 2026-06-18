# FIX-SEV-13 — Hard-raise idempotency enforcement in staging/prod

**Severity:** MEDIUM · **Decision:** DEC-111 (hard-raise)

## Problem
With `IDEMPOTENCY_ENFORCE_HEADER=false` (the shipped default) every mutating endpoint is replay-able. In
staging/prod the config layer only **warns**; a deploy copying the dev `.env` ships replay-able mutations.
DEC-111: make it a hard startup failure outside dev, mirroring the API-key / Neo4j-password gates.

## Current shape (verify against code now)
- `src/npc_engine/config.py:270-280` — `_validate_production_safety` model_validator; at :275-279 it
  `logging.getLogger(__name__).warning("idempotency_enforcement_disabled ...")` when
  `not self.IDEMPOTENCY_ENFORCE_HEADER and self.ENV != "dev"`.
- Pattern to mirror: `config_validators.check_neo4j_password(value, env)` (pure, raises ValueError).

## Steps
1. Add `check_idempotency_enforced(enabled: bool, env: str) -> bool` to `config_validators.py` — raise
   `ValueError` when `not enabled and env != "dev"`; return `enabled` otherwise. Docstring per format.
2. In `config.py` `_validate_production_safety`, replace the `logging.warning(...)` block with a call to
   `check_idempotency_enforced(self.IDEMPOTENCY_ENFORCE_HEADER, self.ENV)`.
3. Find any existing test/fixture that builds `Settings(ENV="staging"|"prod")` WITHOUT
   `IDEMPOTENCY_ENFORCE_HEADER=True` — it will now raise; set the flag in those fixtures.

## Verification
- New tests in `tests/unit/test_config_validators.py`: dev+false passes; staging+false raises; prod+false
  raises; staging+true passes. `pytest tests/unit/test_config_validators.py -k idempotency -q`.
- `make check` (grep the suite first for staging/prod Settings construction so nothing newly breaks).

## Blast radius
`config_validators.py` + `config.py` + config tests. **Breaking** for staging/prod deploys that copied the
dev `.env` (intended — note it in the commit). No interface/schema change.
