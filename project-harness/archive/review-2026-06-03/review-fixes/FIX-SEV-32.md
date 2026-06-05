# FIX-SEV-32 — Bulk-migrate module docstrings to canonical format

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** L
**Category:** docs · **Absorbs:** HARN-10

## Decision
Migrate all files to the **new canonical format** (with `Layer:`, `Purpose:`, `Dependencies:`, `Used by:`). This format is preferred because:
- `Layer:` makes architectural membership explicit in every file header without parsing imports.
- For LLM context retrieval, every file chunk carries its layer/coupling context.
- `Dependencies:` and `Used by:` make bidirectional coupling visible at a glance.

## Problem
161/336 src files lack the mandatory `Layer:` field; 25/45 `__init__.py` lack `Public surface:`. Older files use a "Does NOT / Dependencies injected" format. The drift makes layer membership invisible in file headers and allows docstring-based tooling to silently skip half the codebase.

## Steps

### 1. Write `scripts/docstring_audit.py`
Scan all `src/npc_engine/**/*.py`:
- For regular `.py` files: check for `Layer:` and `Purpose:` in the module docstring.
- For `__init__.py` files: also check for `Public surface:`.
- Output: JSON list of `{file, missing_fields[]}`.
- Exit 1 if any file has missing fields (use this as the CI gate).

### 2. Write `scripts/migrate_docstrings.py`
For each file flagged by the audit:
- Parse the existing module docstring (between `"""` markers at the top).
- Infer `Layer:` from the package path:
  ```
  api/, auth/, data/ → api
  engines/, scheduler/ → engines
  services/, mutation/, cache/, world/ → services
  retrieval/ → retrieval
  graph/ → graph
  config/, schema/, type_registry/, common/, utils/ → config
  ```
- Add missing fields as placeholders: `Dependencies: (auto-detected — review)` / `Used by: (auto-detected — review)`.
- For `__init__.py`: add `Public surface: (list re-exports here)` if absent.
- Write the updated file in-place with a single-pass regex/AST rewrite.
- Print each file path to stdout.

### 3. Run migration and review
```bash
python scripts/migrate_docstrings.py
```
Spot-check 10 files across layers to confirm correctness. Fill in placeholder `Dependencies:` / `Used by:` values for the most-trafficked modules by hand (those in `api/`, `engines/dialogue/`, `retrieval/`).

### 4. Add CI gate
- `Makefile`: add `check-docstrings: python scripts/docstring_audit.py`
- Add `check-docstrings` to the `check` target (after `check-layers` if SEV-31 is done, otherwise after `check-rules`).

### 5. Add DECISIONS entry
DEC-0XX: "Canonical module docstring format chosen: Module/Layer/Purpose/Dependencies/Used by. All src/ files migrated 2026-06-04. check-docstrings gate added to make check."

## Verification
- `python scripts/docstring_audit.py` → 0 files reported missing
- `make check-docstrings` passes
- Spot-check: open 5 random files across layers → `Layer:` field present and correct
- `make check` passes end-to-end

## Blast radius
All 161 flagged src/ files get updated docstrings. No behavior changes; purely documentation.
