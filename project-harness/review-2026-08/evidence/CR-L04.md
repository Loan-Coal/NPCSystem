# CR-L04 — Maintainability

Lens L4. Branch `eval-ab-context-arms` @ `d46ae42`. Windows 11, Git Bash + PowerShell.
Stack live throughout (`npcsystem-app-1`, `npcsystem-neo4j-1`), untouched. Clone/boot
mechanics (git longpaths, `.env`) are already Confirmed by CR-L16 and are cited, not
re-derived. Doc-vs-reality drift in README/CONTRIBUTING is already Confirmed by CR-L13/L16
and is cited only where it feeds a maintainability number this lens owns.

## Required measurements

### 1. Time-to-first-useful-change (walked, not simulated)

Target change: fix `evals/retrieval_runner.py:269-276` (`main`'s docstring lies about its
own CLI — asserts "no options"/"Must be empty" when `--gen-dir` and `--retrieval-profile`
exist) — this is a real, still-open, correctly-scoped P3 (`ISSUES.md:64-77`, `ISSUE-202`),
verified live at `evals/retrieval_runner.py:271-291`.

| # | Step | Documented where | Worked as written? | Time |
|---|---|---|---|---|
| 1 | `git clone` | — (undocumented) | **NO** — Windows `MAX_PATH`; needs `core.longpaths` (CR-L16, Confirmed) | ~1 min once known |
| 2 | `cp .env.example .env` | `CONTRIBUTING.md` only; `README.md` Quick Start omits it entirely | **NO** as README presents it (CR-L16, CR-L16-02, Confirmed) | ~1 min |
| 3 | `docker-compose up -d --build` | `README.md:45` | YES once (1)+(2) fixed — measured by CR-L16: image build + neo4j healthy | ~90 s + ~15 s (CR-L16, cited) |
| 4 | Read root `CLAUDE.md` (1 line) + `project-harness/CLAUDE.md` | auto-loaded every session (`@`-import) | YES, forced | 476 lines / 2,944 words ≈ **20–23 min** at 130 wpm technical reading |
| 5 | Read `project-harness/ISSUES.md` — CLAUDE.md:268-269: *"Every session reads it."* | mandatory, no partial-read clause | Technically possible, practically extreme — see CR-L04-03 | 1,799 lines / 19,080 words / 141,383 chars ≈ **145–150 min** linear read |
| 6 | Read `CONTRIBUTING.md` "Before you commit" | root | Partially broken: `project/CLAUDE.md` (×3), `project/ISSUES.md`, `project/DECISIONS.md` all 404 (`project/` does not exist, confirmed `ls project/` → `No such file or directory`); `python -m npc_engine.scripts.seed` → `ModuleNotFoundError` (confirmed live, real seed path is `python -m demo_game.seeds.seed` per `Makefile:595`) | ~5 min read + ~2 min recovering from the broken command |
| 7 | Find a task | `ISSUES.md` (already open in step 5) | YES — `ISSUE-202` | ~1 min (amortized into step 5) |
| 8 | Edit the docstring | `evals/retrieval_runner.py:271-291` | YES, one-paragraph edit, no behaviour change, matches `ISSUES.md`'s own "To fix" | ~5 min |
| 9 | `make demo-seed` (real seed path) | `Makefile:594-595` | **YES — measured live**: `time make demo-seed` → `real 0m9.161s` (idempotent re-run, `created=101 skipped=71`) | 9.2 s |
| 10 | `make check` (14 targets, pre-merge checklist) | `project-harness/CLAUDE.md` "Pre-merge checklist" | YES (measured elsewhere, cited, not re-run: ~595 s / 94% two coverage runs) | ~10 min |
| 11 | Mark `ISSUE-202` `[FIXED]`, move to `archive/ISSUES_RESOLVED.md` | CLAUDE.md "When you fix an issue" | YES, mechanical | ~5 min |
| 12 | Commit (conventional format) + push | `git-workflow.md` | YES | ~3 min |

**Total, realistic practice** (skim `ISSUES.md` for the one relevant entry via search
rather than reading linearly, as every actual session in this repo's own git history
appears to do — see CR-L04-03): environment fixes (~5 min, one-time) + CLAUDE.md read
(~22 min) + ISSUES.md skim (~3 min) + CONTRIBUTING detour (~7 min) + edit/seed/check/commit
(~28 min) ≈ **1.1 hours**.

**Total, literal CLAUDE.md compliance** (steps 4 and 5 read cover-to-cover as the text
requires, nothing skipped): ~5 min env fixes + 22 min + 148 min + 7 min + 28 min ≈
**3.4 hours**, of which **72%** is reading two markdown files, not writing code.

Either number is dominated by process reading, not the change itself (step 8, the only step
that touches the actual product, is 5 of ~180-330 minutes).

### 2. Files-per-feature — "add a `mood`-like field the dialogue prompt can read"

`character.yaml` already ships `current_mood`/`mood_intensity` (added by
`39fbbb8`/`12c9e5a`, EXP-14), so this is not hypothetical — it is the as-shipped trace,
enumerated by `grep -rl current_mood src/ tests/ docs/`:

| # | File | Role |
|---|---|---|
| 1 | `src/npc_engine/type_registry/base_nodes/character.yaml` | field declaration |
| 2 | `src/npc_engine/graph/emotion/mood_queries.py` | Cypher read/write |
| 3 | `src/npc_engine/graph/infra/embedding_load_queries.py` | embedding-scan projection |
| 4 | `src/npc_engine/graph/infra/embedding_sync_queries.py` | embedding-sync projection |
| 5 | `src/npc_engine/retrieval/context/context_builder.py` | Tier assembly |
| 6 | `src/npc_engine/retrieval/context/context_compression.py` | prompt-budget trimming |
| 7 | `src/npc_engine/retrieval/dialogue_context/dialogue_context_cache.py` | cache key/invalidation |
| 8 | `src/npc_engine/engines/ports/dialogue_context_port.py` | protocol surface |
| 9 | `src/npc_engine/engines/dialogue/dialogue_handler.py` | orchestration |
| 10 | `src/npc_engine/prompts/dialogue/system_v1.yaml` | prompt text itself |
| 11 | `src/npc_engine/data/seed_data.py` | demo seed values |
| 12 | `tests/unit/conformance/test_architecture_conformance.py` | layer conformance |
| 13 | `tests/unit/engines/test_dialogue_handler_fallback_v14.py` | engine unit test |
| 14 | `tests/unit/engines/test_player_relation_context.py` | context unit test |
| 15 | `tests/unit/retrieval/test_context_builder.py` | retrieval unit test |
| 16 | `tests/unit/retrieval/test_context_metrics_observability_v14.py` | observability test |
| 17 | `tests/unit/retrieval/test_context_prompt_hygiene.py` | prompt hygiene test |
| 18 | `tests/unit/retrieval/test_context_serializer_generated.py` | serializer test |
| 19 | `tests/unit/retrieval/test_dialogue_context_cache.py` | cache test |
| 20 | `docs/DATA_MODELS.md` + `docs/ENGINE_EVAL_COVERAGE.md` (2 files, counted as 1 line) | docs |

**20 files** (1 schema + 1 prompt YAML + 9 src + 8 tests + 2 docs). Cross-check with a
second, smaller feature shape — the `GOAL_TARGETS` edge (`d26f1a3` + later wiring) — lands
at **8 files** once fully wired into an engine (`type_registry` yaml, `graph/needs_goals/
goal_targets_writer.py`, `graph/repositories/planning_repository.py`,
`engines/ports/planning_port.py`, `engines/planning/goal_former.py`, `__init__.py`, 2 test
files) — and **0 doc files** (`grep -n GOAL_TARGETS docs/*.md` → no hits; see CR-L04-05).
A field or edge that stops at type_registry + one graph query file, with no dialogue/prompt
surface, is the ~4-8-file floor; one that a player-facing prompt must read is ~20.

### 3. Migration down paths

`scripts/migrations/` actually contains **7** scripts (the review brief's "8" does not match
any count found in the repo — `ls`/`find` both return 7; the number appears nowhere except
`project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md:179` itself).

| Migration | Idempotent? | Down path? | Applied-state tracked? |
|---|---|---|---|
| `add_faction_support.py` | Yes (`CREATE CONSTRAINT … IF NOT EXISTS`) | No | No — **and now dead**, see CR-L04-02 |
| `add_investigation_schema.py` | Yes (same pattern) | No | No |
| `add_phase7_schema.py` | Yes (MERGE/SET) | No | No |
| `add_political_schema.py` | Yes (constraint + count-then-backfill) | No | No |
| `add_social_schema.py` | Yes | No | No |
| `add_strategy_schema.py` | Yes | No | No |
| `migrate_faction_strings.py` | Yes (MERGE), fail-fast on unresolved faction ids | No — and the source field (`Character.faction`) is never removed, so the migration never actually completes (CR-L04-05) | No |

None of the 7 records anywhere that it ran (no migrations table, no `SHOW CONSTRAINTS`
diffing against a manifest, no entry in any doc listing "applied to prod on \<date\>"). The
only cross-check available is manual: `SHOW CONSTRAINTS`/`MATCH … RETURN count()`, run by
hand, against a script's own preconditions.

**If a schema change goes wrong in a customer's deployment, the recovery procedure is: there
is none in writing.** `rollback` appears in the repo only for the in-request Cypher
transaction coordinator (`DECISIONS.md:1416,1454`, request-scoped tx abort-on-exception) —
zero hits for schema-level rollback, backup/restore, or disaster recovery in any `docs/*.md`
or `project-harness/*.md` (checked, not just grepped for "migration"). An operator's only
option today is a full Neo4j volume restore from an external backup this repo does not
document taking.

### 4. Schema evolution

`type_registry/` = 91 YAML files (34 `base_nodes/` + 57 `base_edges/`), not the 124 in the
review brief — verified by `find`. Plus `game_schema.yaml` (`schema_version: "1.0"`, never
incremented — `grep -c schema_version` → 1 literal string, unused as a real version gate).

`node_validator.validate_node_write` (`src/npc_engine/type_registry/node_validator.py:17-33`)
validates **on write only** — it looks up `registry.node_models[node_type]` and calls
`model_cls.model_validate(props)`. There is no read-time re-validation and no migration
trigger. Consequence, traced directly from the code: if a field goes from `required: false`
to `required: true` in an existing `base_nodes/*.yaml`, every **pre-existing** node of that
type that lacks the field is untouched — it simply is not re-validated until something tries
to *write* it again, at which point `pydantic.ValidationError` surfaces at whatever call site
made the write, not at deploy time and not as a migration failure. No gate in
`scripts/check_*.py` (10 checkers enumerated) detects "required field added without an
accompanying migration or a `DECISIONS.md`-documented backfill plan." Of the 91
`base_nodes`/`base_edges` YAML files, only 7 additions across the project's history ever got
a companion migration script (the 7 in `scripts/migrations/`) — the other ~84 were shipped
as `required: false` additions by convention (DECISIONS.md:600 states this explicitly:
*"Making them optional preserves backward compatibility"*), not because tooling enforces it.
Schema evolution here is a **convention**, not a **mechanism**.

### 5. Cohesion/coupling — `graph/` vs `engines/`

| Package | Files | Median lines | Mean | p90 | Max | Files <50 lines | Files >300 lines | Internal (`from npc_engine.X`) import sites |
|---|---|---|---|---|---|---|---|---|
| `graph/` (200 files, 26 subpackages) | 200 | 103.5 | 113.0 | 218 | 339 (`intent/intent_queries.py`, already flagged CR-L15-02) | 48 (24%) | 1 | 270 imports across 89 files (fan-out ≈1.35/file, ≈3.0/importing file) |
| `engines/` (219 files) | 219 | 68 (86.5 excl. `__init__.py`) | 91.4 (108.7 excl.) | 209 (219 excl.) | 470 (`dialogue/dialogue_handler.py`, already flagged CR-L07-03) | 87 (39.7%), 47/178 (26.4%) excl. `__init__.py` | 6 (all already flagged: CR-L07-03, CR-L06/CR-L08 ratchet) | 305 imports across 121 files |

41/219 `engines/` files and 26/200 `graph/` files are `__init__.py` (mandatory per-package
docstrings, CLAUDE.md's own rule) — excluding those, the two packages' size distributions are
close (median 86.5 vs 103.5 lines). **Judgment: 200 and 219 files is domain decomposition by
26 and ~40 subpackages respectively, not 300-line-rule shrapnel** — the under-50-line tail is
explained almost entirely by mandatory `__init__.py` boilerplate, and intra-package import
fan-out (≈1.3-1.4 imports per file) is modest, not a coupling smokescreen. The 7 files over
300 lines are pre-existing grandfathered violations already tracked by other lenses
(CR-L06/L07/L08/L15) — no new finding needed here.

### 6. Agent cold-start cost

| Source | Auto-loaded into every session? | Size |
|---|---|---|
| Root `CLAUDE.md` (`@`-import stub) | Yes | 27 chars |
| `project-harness/CLAUDE.md` | Yes (via the `@`-import) | 20,786 chars / 476 lines |
| User-level `~/.claude/rules/common/*.md` (9 files) + `rules/README.md` | Yes (shown in every session's system context) | 14,938 chars |
| `MEMORY.md` index | Yes | 844 chars |
| **Auto-loaded subtotal** | | **36,595 chars ≈ 9,149 tokens (÷4)** |
| `project-harness/ISSUES.md` (CLAUDE.md:268: *"Every session reads it"*) | Not auto-injected — but self-mandated as the session's own first action | 141,383 chars ≈ **35,346 tokens** |
| **If the mandate is honored literally** | | **≈ 44,495 tokens before any exploration or code is read** |

Against a 200K-token window: auto-loaded content alone is **4.6%**; honoring the ISSUES.md
mandate literally brings mandatory pre-work reading to **≈22.3%** of the budget. Against a
1M-token window the auto-loaded fraction drops to 0.9%, but ISSUES.md is still 35K real
tokens an agent must either spend or silently skip.

---

## Findings

### [CR-L04-01] No migration in `scripts/migrations/` has a down path or applied-state record

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** All 7 files in `scripts/migrations/` read in full. None contains `rollback`/`down`/`revert`/`undo` (`grep -rniE "down|rollback|revert|undo" scripts/migrations/*.py` → 0 hits). No migrations table, manifest, or "applied on \<date\>" record exists anywhere (`grep -rniE "migration.*(log|applied|version|history)"` across `scripts/` and `graph/` → 0 hits). Confirmed by reading every script (see measurement 3 table).
- **Cost of inaction:** This is middleware sold to studios who run it on their own Neo4j data. A bad schema change (wrong constraint, bad backfill value) has no undo — recovery is an out-of-band Neo4j volume restore that is itself undocumented anywhere in `docs/` or `project-harness/`. First customer-side schema incident becomes a support emergency with no runbook.
- **Fix sketch:** Add one `MIGRATIONS.md` (or a section in `docs/API.md`) recording, per script: date applied, environments applied to, and the manual undo Cypher (even "no safe undo, see backup policy" is better than silence). Down paths are optional for pure-additive constraint scripts but mandatory for the field-moving one (`migrate_faction_strings.py`).
- **Effort:** M
- **Blast radius:** Documentation-only; touches no running code.

### [CR-L04-02] `add_faction_support.py` has been fully superseded and dead since 2026-06-04, but two docs still tell operators to run it

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `scripts/migrations/add_faction_support.py:57` creates
  `CREATE CONSTRAINT faction_id_unique IF NOT EXISTS FOR (f:Faction) REQUIRE f.id IS UNIQUE`.
  The identical statement is now issued automatically on **every process startup** by
  `src/npc_engine/graph/infra/schema_bootstrap.py:23-29` (`_CORE_LABELS` includes
  `("Faction", "faction_id_unique")`) via `main.py:166`
  (`await ensure_core_constraints(session=session)`). `git log -S"faction_id_unique"` shows
  this was added in `6b91e4f` ("SEV-10 add core-node uniqueness constraints", 2026-06-04) —
  a month after the migration script (`6cfe763`, 2026-05-06) — with no `DECISIONS.md` entry
  addressing the overlap (`grep -n SEV-10 project-harness/DECISIONS.md` → 0 hits). Yet
  `docs/DATA_MODELS.md:653` and `docs/API.md:490-492` both still present the script as the
  way the constraint gets applied.
- **Cost of inaction:** Operators following the docs run a no-op and may believe they've done
  something the app already guarantees; the doc keeps a false impression of a manual schema
  step alive indefinitely (~3 months and counting as of this review).
- **Fix sketch:** Delete `add_faction_support.py` (or mark it a documented no-op pointing at
  `schema_bootstrap.py`); update the two doc references.
- **Effort:** S
- **Removes:** ~89 lines / 1 file
- **Blast radius:** None — nothing imports or calls this script; it is only ever invoked manually per docs.

### [CR-L04-03] CLAUDE.md's literal "every session reads ISSUES.md" costs ~35K tokens / ~2.5 hours if honored

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `project-harness/CLAUDE.md:268-269`: *"The file `project-harness/ISSUES.md`
  is the persistent issue log. Every session reads it. Every session updates it."* — no
  qualifier permitting a partial read or grep-only pass. `wc -l/-w/-c
  project-harness/ISSUES.md` → 1,799 lines / 19,080 words / 141,383 chars, i.e. **≈35,346
  tokens (chars÷4)** — 6.8× the size of the `CLAUDE.md` that states the rule, and on its own
  ≈17.7% of a 200K-token context budget. At a realistic 130 wpm technical-reading speed that
  is **145-150 minutes** of linear reading before any code is touched (see measurement 1).
- **Cost of inaction:** The instruction is either (a) followed literally, burning ~2.5 hours
  or ~35K tokens of every single session on a file that is 68 open issues of accreted detail,
  most irrelevant to the task at hand, or (b) silently not followed (an agent skims/greps
  instead), which is the practical reality but means the rule as written is fiction — the
  same failure mode CR-L07/CR-L13 already document for other harness claims (stale IDs,
  broken links). Either way the written process and the lived process have diverged.
- **Fix sketch:** Change the instruction to "grep ISSUES.md for the module/file you are about
  to touch" or split it into a short "Open P1s" head section (auto-surfaced) plus a full
  archive-style body that is searched, not read.
- **Effort:** S
- **Blast radius:** Process-only; no code change.

### [CR-L04-04] README's "Migration scripts" line names two files that do not exist anywhere in the repo

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md` "What's done" table: *"Migration scripts (001_remove_current_location_id, 002_remove_event_participants)"*. `find . -iname "001_*" -o -iname "002_remove*"` → no results, in the working tree or `project-harness/archive/`. The actual 7 migrations (`add_faction_support.py` etc.) use a completely different naming scheme and none removes a field.
- **Cost of inaction:** A reader trying to find or run these two referenced migrations cannot — the entry describes work that either never landed under that name or was deleted without updating the table (joins the pattern CR-L13 already documents for this README).
- **Fix sketch:** Replace the two names with the real 7-script list, or drop the parenthetical.
- **Effort:** S
- **Blast radius:** Documentation-only.

### [CR-L04-05] `migrate_faction_strings.py` migrates data but never retires the field it migrates away from

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `scripts/migrations/migrate_faction_strings.py` reads `Character.faction`
  string properties and creates `MEMBER_OF` edges (`CYPHER_CREATE_MEMBER_OF`), but nothing in
  the script, `character.yaml`, or any later commit removes or deprecates the `faction`
  string field — `type_registry/base_nodes/character.yaml` still declares
  `faction: { type: str, required: false }` today. `grep -rl "MEMBER_OF"` shows 10 live `src/`
  call sites plus 2 integration tests still reading the graph through both representations.
  No `docs/DATA_MODELS.md` note or `DECISIONS.md` entry marks the string field deprecated.
- **Cost of inaction:** Two sources of truth for the same relationship persist indefinitely;
  a future writer can set `Character.faction` without creating the edge (nothing enforces
  the two stay in sync post-migration), silently reintroducing the exact drift the migration
  was written to fix.
- **Fix sketch:** Either add a `DECISIONS.md` entry explaining the string field is
  intentionally kept as a display cache (if true), or schedule its removal and mark it
  deprecated in `character.yaml`'s field description now.
- **Effort:** S
- **Blast radius:** `character.yaml` consumers that read `faction` directly (`grep` shows the
  seeders and a few query files) would need the edge-based read path first.

### [CR-L04-06] No gate catches a required-field schema change shipped without a migration

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Gap
- **Evidence:** `node_validator.validate_node_write` (`src/npc_engine/type_registry/node_validator.py:17-33`) validates only at write time, per node, with no batch/startup re-validation of existing graph data. None of the 10 `scripts/check_*.py` gates (`check_base_rate`, `check_conservation`, `check_dead_keywords`, `check_engine_coverage`, `check_harness_honesty`, `check_human_gates`, `check_label_survival`, `check_layers`, `check_rules`, `check_test_quality` — full enumerated list) inspects git diffs of `base_nodes/*.yaml`/`base_edges/*.yaml` for a `required: false → true` transition. Marked Likely rather than Confirmed because it is an absence-of-behavior claim verified by enumerating all 10 gate scripts by name, not by exhaustively reading each one's full body.
- **Cost of inaction:** A future contributor can flip a field to `required: true` (the exact scenario `DECISIONS.md:600` already discusses avoiding) and nothing in `make check` will flag that existing customer graphs now contain invalid nodes until a write path trips a `pydantic.ValidationError` in production.
- **Fix sketch:** A lightweight gate script that diffs `base_nodes|base_edges/*.yaml` for `required` value flips and fails the build unless a matching migration script (or a `DECISIONS.md` entry) is present in the same PR.
- **Effort:** M
- **Blast radius:** New CI gate only; no existing code touched.

---

## Return summary

Severity counts: HIGH 2, MEDIUM 4, LOW 0 (6 findings total).

Top 3: CR-L04-01 (no migration down path / no applied-state tracking, HIGH), CR-L04-03
(CLAUDE.md's literal "every session reads ISSUES.md" costs ~35K tokens / ~2.5h, HIGH),
CR-L04-02 (`add_faction_support.py` dead since 2026-06-04, docs still prescribe it, MEDIUM).
