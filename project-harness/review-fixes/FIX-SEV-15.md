# FIX-SEV-15 — Adopt full `mypy --strict` (fix all 274 errors, flip the gate)

**Severity:** MEDIUM (large/mechanical) · **Decision:** DEC-113 (full strict) · **Multi-phase**

## Problem
`make type` runs non-strict and reports 0 errors; `mypy --strict src/` surfaces **274 errors across 87
files** (bare `dict`/`list` type-args, missing annotations, `Any` returns, an `attr-defined` re-export gap).
DEC-113: fix all of them and flip the gate to strict so the contract surface is genuinely typed.

## Current shape (verify against code now)
- `pyproject.toml` `[tool.mypy]` — `strict = false`, `ignore_missing_imports = true`.
- `make type` runs `mypy src/` (non-strict). Enumerate the work: `mypy --strict src/ 2>&1 | tee /tmp/strict.txt`.

## Steps (phase by error class / directory — one commit per batch)
1. Snapshot `mypy --strict src/` and group errors by code (`type-arg`, `no-untyped-def`, `return-value`/`Any`,
   `attr-defined`, `no-any-return`).
2. Fix mechanically by group: parameterize bare `dict`→`dict[str, Any]` / typed models; add missing param/return
   annotations; fix the `batch.py` `get_gossip_handler` re-export (`attr-defined`); add `# type: ignore[code]`
   ONLY for genuine third-party gaps, each with a one-line reason.
3. When `mypy --strict src/` is clean, set `strict = true` in `pyproject.toml` and ensure `make type` uses it.

## Verification
- `mypy --strict src/` → 0 errors; `make check` green (the `type` gate now strict).
- Run `make test` after — strict fixes can change annotations Pydantic/FastAPI resolve at runtime.

## Blast radius
Repo-wide (87 files). **Largest item — sub-phase it** (e.g. per top-level package) across several commits;
keep each batch green. Touches `pyproject.toml` mypy config (not CI).
