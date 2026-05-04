# Architectural Decisions

_(Populated as refactor proceeds. Append only. Use dated headers.)_

## 2026-04-30

### Decision: Dependency Map Established — No `services/` Layer Exists

**Date:** 2026-04-30
**Service:** N/A (bootstrap)
**Context:** The refactor prompt specifies a `services/` layer between `engines/` and `retrieval/`, but the actual codebase has no such directory. The `mutation/` directory (delta_log_manager, modifier_bounds_validator) partially fills this role. There is no other shared domain operations layer.
**Options considered:**
  1. Create a `services/` directory during the refactor and move mutation/ into it — cleaner alignment with the specified layer model
  2. Treat `mutation/` as the `services/` layer with its current name — less churn, avoids mass-rename
**Choice:** Option 2 for now (treat mutation/ as services layer). Will revisit if a service explicitly needs to live in services/ and mutation/ is the wrong home.
**Consequences:** Layer model documentation should acknowledge mutation/ as the services layer. Any future service that fits services/ should go in mutation/ or prompt a decision to create services/.

---

### Decision: Misplaced Domain Exceptions Deferred to Owning Services

**Date:** 2026-05-01
**Service:** utils (service #1)
**Context:** `RelationDeltaExceededError`, `TokenBudgetExceededError`, and `ContextBudgetError` are domain exceptions that currently live inside mutation/ and retrieval/ modules rather than utils/errors.py, violating ERR-02 ("all domain errors defined in utils/errors.py").
**Options considered:**
  1. Move them to errors.py now — would require updating all callers in the same commit, touching mutation/ and retrieval/ before those services are scheduled for refactor
  2. Defer migration to when each owning service is refactored — lower blast radius, keeps each service session self-contained
**Choice:** Option 2 — defer.
**Consequences:** utils/errors.py is not yet the complete canonical exception registry. Each deferred migration is tracked in STATUS.md Deferred P1.

---

### Decision: config.py Validators Extracted to config_validators.py (STRUCT-01)

**Date:** 2026-05-01
**Service:** config (service #3)
**Context:** config.py had ~196 non-blank lines before DOC-02 remediation. Adding full Args/Returns/Raises docstrings to 11 field validators would push it to ~226 non-blank lines, exceeding the STRUCT-01 limit of 200. Pydantic `@field_validator` classmethods cannot be moved to a different class, so a direct move was not possible.
**Options considered:**
  1. Skip Args/Returns on validator classmethods (accept a DOC-02 gap for obvious signatures)
  2. Extract the validator logic into standalone functions in `config_validators.py`; keep thin-delegate classmethods in `config.py`
**Choice:** Option 2 — extract. Validator logic now lives in `config_validators.py` with full DOC-02 docstrings. `config.py` classmethods are one-liner delegates. `config.py` is now ~130 non-blank lines. Validators are independently testable as pure functions (TEST-02 benefit).
**Consequences:** `config_validators.py` is a new module at the config layer. Any caller importing validator logic directly must use `config_validators`; callers of `Settings` are unaffected.

---

### Decision: Layer Violations V1–V6 Are Pre-existing, Not Introduced

**Date:** 2026-04-30
**Service:** N/A (bootstrap)
**Context:** Six layer violations were detected during the audit (see STATUS.md). All are pre-existing. They will be fixed during the refactor of the relevant service, not before.
**Options considered:**
  1. Fix all violations immediately before starting the service-by-service refactor
  2. Fix each violation when we reach the service that owns it
**Choice:** Option 2 — fix violations in the owning service's session.
**Consequences:** The codebase will have known violations until the relevant service is refactored. This is acceptable because the tests currently pass (5 pre-existing failures, none caused by these violations directly).
