# Changelog

All notable changes to NPC Engine will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **Pre-history:** Phase 0 refactor history (27 services, issues 001–003, phases 0.1–0.5)
> is recorded in
> [project-harness/archive/STATUS_history_through_2026-05-28.md](project-harness/archive/STATUS_history_through_2026-05-28.md).
>
> Entries below dated before 2026-06 refer to a `project/` directory that is now
> `project-harness/`. They are left as written — a changelog records what happened,
> not where the files sit today.

---

## [Unreleased]

> **This section is not a complete log.** It was last touched 2026-08-14 and the repo has
> moved 161 commits since. Rather than reconstruct them and schedule the next drift, the
> authoritative records are named here (R4.6):
> [project-harness/ROADMAP.md](project-harness/ROADMAP.md) for what shipped and what is
> next, [project-harness/DECISIONS.md](project-harness/DECISIONS.md) for why, and
> `git log` for the rest. A release entry is written when a release is cut.

### Added
- **2026-08 remediation programme** (branch `remediation-2026-08`, phases R0–R4): gate
  integrity, eval measurement, product correctness and subtraction. Highlights —
  `/setup/*` no longer serves a plaintext API key unauthenticated (R0.1, DEC-231); Neo4j
  bolt is reachable from the host so `tests/integration` runs at all (R0.2, DEC-232); the
  gates that could not fail were deleted or made to (R1); the anti-hallucination *claim*
  was retired while its apparatus was kept as a regression test (DEC-250); Neo4j
  unavailability maps to HTTP 503 instead of a canned reply (R3.2); and `BaseEngine`'s
  signature-free `run_tick` became three real protocols checked at the wiring site (R3.5).
  Full sequence and per-task evidence in `project-harness/ROADMAP.md`.
- `make openapi` — prints the live OpenAPI schema; replaces the tracked `live_openapi.json`,
  deleted in R4.7 after it was measured four routes stale.
- `make harness-status` — prints what `make check` runs and every baseline's live value,
  so no document has to keep a copy of a number (R4.6).
- Optional `seed` on `LLMGenerateProtocol.generate()`, `generate_structured()` and `stream()`,
  honoured by all three adapters (`ollama` → `options.seed`, `openai` → `body["seed"]`, `mock`
  records it). Carried from `engines/dialogue/llm_config.yaml` through `EngineModelParams` and
  `DialogueLLMClient`; recorded in `RunConfig.seed` (EVAL-P20.0 / DEC-176)
- `scripts/seed_reproduction_probe.py` + `make seed-probe` — measures byte-identical `npc_response`
  reproduction between two same-seed generation runs; exits non-zero below the gate
- `docs/overview.md` — entry-point TOC for game developers and contributors

### Fixed
- **Wall-clock values no longer leak into LLM prompts.** `context_builder._build_tier0_items`
  serialized the whole world state with no field stripping, putting `world.last_updated_at` into
  every prompt; `NON_PROMPT_NODE_FIELDS` also omitted `emotion_updated_at_tick` and
  `expires_at_tick`. All Tier-0 items now strip through that set. Measured effect: between-run
  `retrieved_context` drift fell from 145/145 records to 0/145, and eval reproduction rose from
  25.0% to 62.5%. Restores CLAUDE.md's "Idempotent assembly" rule (DEC-176)
- `CONTRIBUTING.md` — setup, test commands, and pre-merge checklist
- `CHANGELOG.md` — this file
- `project/proposals/archive/` — completed proposals archived here

### Changed
- `project/STATUS.md` — added project health snapshot header with badge placeholders
- `project/PATTERNS.md` — added Common Anti-Patterns section (migrated from `docs/LLM_GENERATION_GUIDE.md`)
- `README.md` — fixed broken link (`project_md_files/ARCHITECTURE.md` → `docs/ARCHITECTURE.md`)

### Removed
- `docs/LLM_GENERATION_GUIDE.md` — outdated code-generation meta-doc; unique content preserved in `project/PATTERNS.md`
- `project/proposals/WRITE_PATH_CONVERGENCE_P0.md` — implemented in Phase 0; moved to `archive/`
- `project/proposals/refactor.md` — implemented in Phase 0.2; moved to `archive/`
