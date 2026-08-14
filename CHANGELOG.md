# Changelog

All notable changes to NPC Engine will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **Pre-history:** Phase 0 refactor history (27 services, issues 001–003, phases 0.1–0.5)
> is recorded in [project/STATUS.md](project/STATUS.md).

---

## [Unreleased]

### Added
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
