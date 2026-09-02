---
name: npc-testing
description: NPC Engine TDD discipline, test layout, and per-module test requirements. Load before writing tests or fixing a bug in this repo.
---

# NPC Engine — testing

Binding (DEC-249). `project-harness/CLAUDE.md` names each rule in one line and points here.
Gated by `make check-test-quality` and the `test-cov*` targets.

### TDD discipline

For new code:
1. Write the failing test.
2. Confirm it fails for the right reason (not import error, not typo).
3. Write the minimum code to pass.
4. Refactor with tests green.

Bug fixes:
1. Write a regression test that reproduces the bug.
2. Confirm it fails.
3. Fix the bug.
4. Confirm the test passes.

### Test layout

```
tests/
  unit/test_<module>.py
  integration/test_<module>.py
  contract/
  conftest.py        (at repo root)

e2e/
  scenarios/
  scripts/
  transcripts/       (gitignored)
```

- Unit tests: no I/O, no DB, no network. Mock all infrastructure.
- Integration tests: may use test DB, test LLM mock, test vector store. No real
  external services.
- E2E tests: spin up the full stack via Docker Compose. Run as scenarios.

### Test requirements per module

- Every public function has at least one happy-path test and one failure test.
- Functions touching Neo4j have integration tests against a real test DB, not mocks.
- Functions calling an LLM have unit tests with the mock adapter.
- Deterministic functions with >2 input parameters have property tests.
