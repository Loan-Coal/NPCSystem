# FIX-SEV-34 — Fix stale onboarding docs (README + CLAUDE.md command table)

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** S
**Category:** docs · **Absorbs:** GAME-08, HARN-12

## Problem
`README.md:43-58` Quick Start references `mixtral:8x7b` (wrong model), `cd npc_engine` (path no longer exists), `python data/seed.py` (wrong invocation), and lists already-done "what's next: rate limiting". `project-harness/CLAUDE.md` Key commands table omits real targets that exist today: `demo-village`, `demo-tavern`, `seed-*-world`, `eval-report`, `demo-snapshot`.

## Steps
1. In `README.md` Quick Start section:
   - Replace `mixtral:8x7b` with `qwen2.5:14b` (or `openai/gpt-4o` as alternative)
   - Remove `cd npc_engine`
   - Replace `python data/seed.py` with `make demo-seed`
   - Correct the sequence to: `docker-compose up -d` → `make demo-seed` → `make demo`
   - Remove "what's next: rate limiting" bullet (already implemented)
2. In `project-harness/CLAUDE.md` Key commands table: add rows for:
   - `make demo-village` — seed and run village eval world
   - `make demo-tavern` — seed and run tavern eval world
   - `make seed-village-world` — seed village eval world only
   - `make seed-tavern-world` — seed tavern eval world only
   - `make eval-report` — generate eval summary report
   - `make demo-snapshot` — snapshot current demo state

## Verification
- `grep "mixtral" README.md` → 0 matches
- `grep "cd npc_engine" README.md` → 0 matches
- `grep "demo-village" project-harness/CLAUDE.md` → match

## Blast radius
Docs only; no code changes.
