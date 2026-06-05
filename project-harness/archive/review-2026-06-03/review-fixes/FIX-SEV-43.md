# FIX-SEV-43 — Contract guards are near-no-ops

**Severity:** LOW · **Confidence:** Confirmed · **Effort:** M
**Category:** testing · **Absorbs:** TEST-08

## Problem
`make check-contracts` validates only YAML shape (required fields present); `guard_contract_test_sync` passes when a same-named test file appears in the diff — it never asserts the file exists on disk, nor that it references the contract's name/symbols. A contract can point to a test file that was deleted or never exercises the contract, and CI stays green.

## Current shape
- Contract checker script (verify path): validates YAML field presence only
- `guard_contract_test_sync` hook/script: `if test_path in diff_files: pass` — file existence and content not checked

## Steps

### 1. Extend contract checker to assert test paths exist
In the contract-checker script, after validating YAML shape, for each path in `tests:`:
```python
if not Path(test_path).exists():
    errors.append(f"  {contract_file}: tests path not found: {test_path}")
```
Exit 1 if any errors.

### 2. Extend `guard_contract_test_sync` to assert contract symbol appears in test
When a contract YAML is changed:
1. Resolve the test file path from the contract's `tests:` list.
2. Assert the file exists (`exit 1` with clear message if not).
3. Open the test file and search for the contract's `name:` value as a substring.
4. Exit 1 with file + contract name if the symbol is absent.

### 3. Add tests for the checkers themselves
`tests/unit/test_contract_guards_sev43.py`:
- `test_missing_test_file`: contract YAML with `tests: [tests/unit/nonexistent.py]` → checker exits 1 with path in message.
- `test_sync_missing_symbol`: test file exists but does not reference the contract name → sync guard exits 1.
- `test_valid_contract`: a well-formed contract with an existing test referencing its name → both pass.

## Verification
- `make check-contracts` with a contract pointing to a missing test path → exit 1
- `make check-contracts` on the real tree → exit 0
- `tests/unit/test_contract_guards_sev43.py` passes

## Blast radius
CI check scripts only; no production code.
