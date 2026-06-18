# FIX-SEV-06 — `from __future__ import annotations` autofix + `run_tick` return type-arg

**Severity:** MEDIUM (mechanical) · **Lens:** L3 (L3-05 REGRESSED, L3-11), L8 (L8-03)

## Problem
1. **REGRESSED:** 138 of 469 `.py` files (29%) still lack `from __future__ import annotations`, despite the
   prior review marking it "Fix now (ruff one-liner)". Worst dirs: `auth/` (6/6), `schema/` (11/11),
   `mutation/` (3/3), `type_registry/` (12/13), plus several API route files (L3-05).
2. `base_engine.py` `async def run_tick(...) -> dict:` uses a bare `dict` (no type params); `mypy --strict`
   flags `[type-arg]` and CLAUDE.md requires fully-parameterised return types (L3-11).

## Current shape (verify against code now)
- 138 files missing the future import — enumerate with: `grep -L "from __future__ import annotations" $(git ls-files 'src/**/*.py')`.
- `src/npc_engine/engines/base_engine.py:23` — `-> dict:`.

## Steps
1. Add the `from __future__ import annotations` import to all missing files. Prefer the ruff rule that
   enforces it (`required-imports`, e.g. `[tool.ruff.lint.isort] required-imports = ["from __future__ import annotations"]`) + `ruff check --fix` so it stays enforced — otherwise this regresses a third time. Confirm `make lint`/`check-rules` now enforces it.
2. Change `run_tick` return to the concrete type it actually returns — prefer a typed model if the return
   is a fixed shape; if it is genuinely heterogeneous per engine, `-> dict[str, Any]:` is the minimum.

## Verification
- `grep -L "from __future__ import annotations" $(git ls-files 'src/**/*.py')` returns empty.
- `make check` — lint enforces the import; mypy 0; full suite green (future-annotations can change runtime annotation evaluation — run `make test`).

## Blast radius
Repo-wide import insertion (low-risk, additive) + one engine signature. Adding the ruff enforcement rule touches `pyproject.toml`/ruff config (lint config, not CI — within scope, but note it in the commit).
