# FIX-SEV-17 — Split `dependencies_advanced.py` into per-engine submodules

**Severity:** MEDIUM · **Decision:** DEC-115 (per-engine submodules) · Resolves ISSUE-105

## Problem
`api/dependencies_advanced.py` is a second, undeclared composition root holding `@lru_cache` factories for
~11 engine families and is over the DEC-076 growth cap. DEC-115: split into per-engine submodules so the
single-root spirit holds and no file exceeds 300 lines.

## Current shape (verify against code now)
- `src/npc_engine/api/dependencies_advanced.py` — factories for clique, treaty, oath, skill, chapter, mood,
  succession, agenda, military, need-decay, negotiation engines.
- Imported by `get_tick_scheduler()` in `dependencies_engines.py` (deferred import block ~lines 461-472).
- `api/dependency_singletons.py` re-exports from both.

## Steps
1. Create a package `api/dependencies/` (or `api/deps_advanced/`) with one module per engine family
   (e.g. `factions.py`, `social.py`, `progression.py` — group cohesively, ≤300 lines each), each with the
   required module docstring (`Does NOT:` + `Dependencies injected:`).
2. Move the factories; have the package `__init__` (or `dependencies_advanced.py`) re-export the public
   `get_*` names so `dependencies_engines.py` and `dependency_singletons.py` imports stay unchanged.
3. Update DEC-076/DEC-115 notes; mark ISSUE-105 fixed.

## Verification
- App boot smoke + tick scheduler builds all engines: `pytest tests/ -k "dependencies or tick_scheduler or singletons" -q`.
- `make check` (layer check + 300-line rule both green).

## Blast radius
`api/dependencies_advanced.py` → new submodules; `dependencies_engines.py` / `dependency_singletons.py`
imports (keep re-export names stable). No behavior change.
