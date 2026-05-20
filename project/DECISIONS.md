# Decisions Log

Architectural and design decisions. Each entry records the context, the options
considered, the choice, and the consequences.

Rules:
- Append-only. Never delete entries.
- Use dated headers.
- Keep each entry short — context, options, choice, consequences. No essays.

---

## Decision: No `services/` Layer Exists
**Date:** 2026-04-30
**Service / area:** N/A (bootstrap)
**Context:** The refactor prompt specifies a `services/` layer between `engines/` and `retrieval/`, but the actual codebase has no such directory. The `mutation/` directory partially fills this role.
**Options considered:**
  1. Create a `services/` directory and move `mutation/` into it — cleaner alignment with the specified layer model.
  2. Treat `mutation/` as the `services/` layer with its current name — less churn.
**Choice:** Option 2. Will revisit if a service explicitly needs to live in services/ and mutation/ is the wrong home.
**Consequences:** Layer model documentation should acknowledge mutation/ as the services layer.

---

## Decision: Root cause of world-state non-compliance is (b) — weak prompt, not retrieval
**Date:** 2026-05-20
**Service / area:** `engines/dialogue`, `prompts/`
**Context:** Phase 0 audit ran `scenario_war_breaks_out.py` twice. WorldState epoch changed
from `age_of_peace` to `war` mid-session. LLM acknowledged the epoch in its language but
kept the same threat assessment, ignoring the behavioral rule in the system prompt.
**Options considered:**
  1. (a) WorldState never reached the prompt — ruled out; `context_builder.py:276` injects it
     as tier0 / priority=100, always present.
  2. (b) System prompt instruction too weak for Mixtral 8x7b to act on materially — confirmed.
  3. (c) RAG retrieval filling context with wrong events — not relevant here; world state is
     direct-injected, not retrieved.
  4. (d) Model capability limit — possible co-cause; cannot distinguish from (b) without P0.5
     model swap.
**Choice:** Treat (b) as primary cause. Phase 1 first lever: rewrite epoch instruction as an
authoritative prohibitive constraint, not a descriptive hint. Run model swap (P0.5) at Phase 1
exit if prompt-only fix is insufficient.
**Consequences:**
- Phase 1 must strengthen the epoch rule AND move `_SYSTEM_PROMPT` from inline Python string
  to a versioned YAML file under `prompts/` (CLAUDE.md rule: no prompt strings outside prompts/).
- If prompt fix alone doesn't move the needle, escalate to Llama 3.1 8B Instruct swap.

---

## Decision: Misplaced Domain Exceptions Deferred to Owning Services
**Date:** 2026-05-01
**Service / area:** utils (service #1)
**Context:** `RelationDeltaExceededError`, `TokenBudgetExceededError`, and `ContextBudgetError` live inside mutation/ and retrieval/ rather than utils/errors.py, violating ERR-02.
**Options considered:**
  1. Move them to errors.py immediately — requires touching mutation/ and retrieval/ before those services are scheduled.
  2. Defer migration to when each owning service is refactored — lower blast radius.
**Choice:** Option 2. Each deferred migration was tracked in STATUS.md Deferred P1 and completed during the relevant service session.
**Consequences:** All three exceptions are now in utils/errors.py; re-exported via __all__ in their original modules for backward compat.

---

## Decision: config_validators.py Extracted (STRUCT-01)
**Date:** 2026-05-01
**Service / area:** config (service #3)
**Context:** Adding full DOC-02 docstrings to config.py validators would push it past 200 non-blank lines (STRUCT-01). Pydantic @field_validator classmethods cannot move to a different class.
**Options considered:**
  1. Skip Args/Returns on validator classmethods.
  2. Extract validator logic into standalone functions in `config_validators.py`; keep thin-delegate classmethods in `config.py`.
**Choice:** Option 2. config.py is now ~130 non-blank lines; validators are independently testable.
**Consequences:** `config_validators.py` is a new module at the config layer.

---

## Decision: Layer Violations V1–V6 Fixed During Owning Service Sessions
**Date:** 2026-04-30
**Service / area:** N/A (bootstrap)
**Context:** Six pre-existing layer violations detected during audit. Fixing all upfront would require touching many files outside the scheduled service.
**Options considered:**
  1. Fix all violations immediately before starting the refactor.
  2. Fix each violation when we reach the owning service.
**Choice:** Option 2. All V1–V6 resolved by end of refactor (see STATUS.md).
**Consequences:** Tests passed throughout. No violation was introduced during the refactor.

---

## Decision: No Separate Gateway Service (Feature 0.3 scope reduction)
**Date:** 2026-05-05
**Service / area:** Phase 0.3 — Gateway
**Context:** ROADMAP Feature 0.3 specified building a `gateway/` package in front of
internal services. During route inventory, we found that `main.py` already mounts all
routes in a single FastAPI app with global `ApiKeyMiddleware` — i.e., the app already
is what a gateway would be. Adding a wrapping FastAPI app would mean two apps, two
middleware stacks, and in-process HTTP forwarding via mount, all for one process.
**Options considered:**
  1. Build `src/npc_engine/gateway/` as a second FastAPI app that re-mounts the
     existing routers. Cons: pure duplication; two apps for one process; no isolation
     benefit; double middleware overhead.
  2. Harden `main.py` as the canonical public entry point — route audience split,
     rate limiting, request logging — without a separate gateway package.
**Choice:** Option 2.
**Reasoning:** A separate gateway is justified when there are multiple processes or
services to unify behind one interface. We have one process. Adding architectural
ceremony to satisfy a pattern that doesn't fit the actual topology is overengineering.
**Consequences:** Cross-cutting concerns (auth, rate limiting) live as middleware on
the existing app. If the project later splits into multiple services, revisit then.

---

## Decision: Route Audience Split (/v1/ vs /v1/admin/)
**Date:** 2026-05-05
**Service / area:** Phase 0.3 — Gateway
**Context:** All routes previously lived under a single `/v1/` prefix. Game-engine
clients and designer tooling used the same surface with different auth scopes.
**Options considered:**
  1. Keep everything under `/v1/` and rely on scope-based access control alone.
  2. Split into `/v1/` (game engine) and `/v1/admin/` (designer tooling) so the
     audience split is visible in the URL structure and enforceable at the
     reverse-proxy/network layer.
**Choice:** Option 2.
**Reasoning:** The URL split makes it possible to restrict admin routes in a Docker
network or nginx config without having to enumerate individual paths. It also makes
the intended consumer of each route immediately visible in the URL.
**Consequences:** Any existing client targeting `/v1/batch/*`, `/v1/graph/admin/*`,
or `/v1/schema` must update to the new `/v1/admin/*` paths. These are all
designer/tooling clients, not game-engine clients.

---

## Decision: Defer `src/` Layout Move; Use pyproject.toml When It Happens
**Date:** 2026-05-05
**Service / area:** Phase 0.2 repo reorganization
**Context:** Moving source to `src/npc_engine/` with a standard pythonpath would require updating ~800 bare imports across ~130 files. No pyproject.toml exists; project uses requirements.txt + CWD-relative test execution.
**Options considered:**
  1. Do the src/ move now with full import rename (~800 changes).
  2. Move to src/npc_engine/ but use `pythonpath = ["src/npc_engine"]` in pytest.ini (zero import changes, non-standard).
  3. Defer the src/ move entirely; do all other reorg tasks first.
**Choice:** Option 3. All other Phase 0.2 tasks proceed without touching source. When the src/ move happens, a proper `pyproject.toml` will be written (setuptools or hatchling) and all bare imports renamed to `npc_engine.xxx`.
**Consequences:** Source still lives at `npc_engine/` root. pytest.ini at repo root adds `npc_engine/` to pythonpath so tests run from root without CWD dependency.

---

## Decision: context_builder.py exceeds 300-line limit (Phase 6)
**Date:** 2026-05-18
**Service / area:** retrieval/context_builder.py (Phase 6)
**Context:** After Phase 6 additions (two-pass reranking, query expansion, trust scoring, second-hop events, quest state, cross-encoder gating), context_builder.py is 367 lines. The CLAUDE.md hard limit is 300 lines.
**Options considered:**
  1. Split the tier_a assembly block into `_build_secondary_tier_a_items(...)` — saves ~30 lines in main body but adds ~20-line helper with 12 parameters. Net −10 lines; the helper has no cohesion beyond "things we append to tier_a_raw".
  2. Extract Stage 4 gather into `_fetch_enrichment(session, npc_id, player_id, event_ids)` — saves 12 lines, adds 15-line helper. Net +3 lines; still over 300.
  3. Accept the overrun with a justifying comment and this DECISIONS entry — no artificial splits.
**Choice:** Option 3. `build_serialized_context` is a single async orchestration function: every line is part of one logical pipeline. Splitting it would distribute one function across two modules with no encapsulation benefit. The 67-line overrun is entirely new Phase 6 gather/wiring logic.
**Consequences:** context_builder.py stays at ~367 lines. If the function grows further (Phase 7+), split then — a 500-line orchestration file is unacceptable; 367 is defensible.

---

## Decision: `how_long_ago` 7–27 day gap treated as "a few days ago"
**Date:** 2026-05-11
**Service / area:** world/time_utils.py (Phase 3.1)
**Context:** The ROADMAP spec defines named buckets for 0, 1, 2–6 days, 28 days (one season), and >28 days, but leaves 7–27 days undefined.
**Options considered:**
  1. Add a new bucket "a week or two ago" for 7–27 days — introduces wording not in the spec.
  2. Extend "a few days ago" to cover 2–27 days — consistent with existing bucket, spec-compatible.
**Choice:** Option 2. "a few days ago" covers delta_days 2–27. Logged as ISSUE-013 for future refinement.
**Consequences:** Distances of 7–27 days return "a few days ago", which is slightly imprecise but not misleading. Can be narrowed when the spec is updated.
