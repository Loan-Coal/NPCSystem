# FIX-SEV-24 — Delete stale nested infra files under `src/npc_engine/`

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** S
**Category:** hygiene · **Absorbs:** ARCH-07, ARCH-08, HARN-05, HARN-16
**Note:** Deletion approved by owner.

## Problem
Six infra files under `src/npc_engine/` dated May 11 drift from root canonical copies and actively cause harm:
- `src/npc_engine/docker-compose.yml` — uses `uvicorn main:app` (module path no longer exists)
- `src/npc_engine/Dockerfile` — drops `internal`/`public` network isolation from root version
- `src/npc_engine/mypy.ini` — pins `python_version = 3.11` while the stack is 3.14; mypy picks up the nested ini if run from that directory, silently inflating type error counts
- `src/npc_engine/requirements.txt` — may diverge from root
- `src/npc_engine/game_schema.yaml` — stale snapshot of `game_schema.yaml`
- `src/npc_engine/README.md` — references nonexistent `make seed` and a moved tracker

## Steps
1. `git rm src/npc_engine/docker-compose.yml src/npc_engine/Dockerfile src/npc_engine/mypy.ini src/npc_engine/requirements.txt src/npc_engine/game_schema.yaml src/npc_engine/README.md`
2. Confirm no tool in `Makefile` or CI references these paths:
   - `rg "src/npc_engine/docker-compose" .` → 0 matches
   - `rg "src/npc_engine/mypy.ini" .` → 0 matches
3. Add a DECISIONS entry (DEC-0XX): "Root-level `docker-compose.yml`, `Dockerfile`, `mypy.ini`, `requirements.txt`, `game_schema.yaml` are canonical. Nested copies under `src/npc_engine/` were deleted on 2026-06-04."
4. Run `make check` to confirm nothing broke.

## Verification
- `git ls-files src/npc_engine/docker-compose.yml` → no output
- `git ls-files src/npc_engine/mypy.ini` → no output
- `make check` passes

## Blast radius
Repo tracking + docs only. No Python source changes.
