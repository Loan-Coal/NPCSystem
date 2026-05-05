# Next Session Instructions

## Phase 0.3 Complete

Route audience split and hardening done. Routes are now:
- `/v1/` — game-engine public surface (dialogue, NPC, quest, clock, action, graph CRUD)
- `/v1/admin/` — designer/tooling (batch ticks, graph admin, schema introspection)

`pytest tests/unit/` must be green before starting Phase 0.4.

## Current state

Run from repo root:
```bash
pytest tests/ -q
```

Expected: all pass (294+ tests). If anything fails in the new tests, check:
- `test_rate_limit_middleware.py` — uses `Settings(RATE_LIMIT_ENABLED=..., ...)` constructor; verify the field name matches config.py
- `test_v1_route_versioning.py` — calls `create_app()` with monkeypatched env; verify `get_settings.cache_clear()` is called before each test

## Phase 0.4 — Per-engine LLM config (next)

**Goal:** Each engine has its own `llm_config.yaml`. Different parameters, different
fallback policies per engine. Startup fails if a registered engine lacks a config.

**Key file:** `project/ROADMAP.md` Feature 0.4 section — read it first.

**Steps per ROADMAP:**
1. Create `engines/<engine>/llm_config.yaml` for every engine that calls an LLM.
2. Write `src/npc_engine/engines/llm_config_loader.py` with `get_config(engine_name)`.
3. Each engine's LLM call site reads from its own config.
4. Schema validation: startup fails if a registered engine lacks a config file.
5. Unit tests: schema validation, missing file, invalid values.
6. Integration test: engines read distinct configs.
7. Update `docs/ARCHITECTURE.md` with per-engine config pattern.

**Stop and ask if:** Any engine currently reads from a global config in a way that
would require changing its public interface.

## Known open items

- `project/proposals/route_audience_improvements.md` — 6 improvement proposals from
  Phase 0.3 implementation. Review before Phase 0.4.
- `ISSUES.md` — check for any entries before starting.
