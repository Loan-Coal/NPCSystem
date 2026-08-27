# CR-L05 — `CLAUDE.md` and rules-as-written

Lens L5. Branch `eval-ab-context-arms`, HEAD `d46ae42`, 2026-08-28. **Read-only** — no source file
was created, edited or deleted; this evidence file is the only write. Subject:
`project-harness/CLAUDE.md`, 476 lines, auto-loaded into every session via the one-line root
`CLAUDE.md` (`@project-harness/CLAUDE.md`).

Every rule in the file is treated here as a **claim to be tested**, not as a rubric.

---

## Required measurements

### 1. Claims verification — 109 checked / 26 FALSE / 6 unverifiable

**Method.** Walked the file top to bottom and extracted every discrete checkable assertion: the
stack table, all 13 `make` targets, all 13 rows of the file-locations table, the demo-world NPC
table, the 15-package layer block and its 10 explicit rank annotations, the 6 allowed-dependency
rows, the 4 forbidden cross-layer patterns, the code-style/documentation/testing sections, and all
**28** rules marked **(strict)**. Each was verified by running the command, reading the source, or
computing the count. Unverifiable = the rule has no operational definition, not "I did not check".

| Metric | Count |
|---|---|
| Claims checked | **109** |
| Claims **FALSE** | **26** |
| Claims unverifiable | **6** |
| Claims TRUE | 77 |

Two sections verified **100% TRUE and worth keeping verbatim**: the *Key commands* table (13/13 —
`make -n <target>` exits 0 for all 12 targets plus `docker-compose.yml` present) and the *Test
layout* block (`tests/{unit,integration,contract}`, root `conftest.py`, `e2e/{scenarios,scripts}`,
`e2e/transcripts/` gitignored at `.gitignore:24` — all 7 paths exist). All 13 rows of *Key file
locations* resolve. All 10 rank annotations match `scripts/check_layers.py:32-56` exactly.

#### Every FALSE claim, with the measured truth

| # | CLAUDE.md line | Claim | Measured truth | How measured |
|---|---|---|---|---|
| 1 | `:22` | "no OpenAI adapter ships today" | `src/npc_engine/engines/llm/openai_adapter.py` exists (`class OpenAICompatibleAdapter(LLMClientProtocol)`), is registered at `engines/llm/factory.py:107 register_backend("openai", _build_openai)`, and has settings `OPENAI_API_URL`/`OPENAI_API_KEY` at `config.py:114-115` (SHIP-02 / DEC-126) | `find src -iname "*openai*"`; `grep -rn openai src/` |
| 2 | `:23` | "Python 3.14" as the platform | `pyproject.toml:8 requires-python = ">=3.11"`; `mypy.ini:2 python_version = 3.11`. Only `.github/workflows/ci.yml` uses 3.14 (5 jobs). Two of the repo's own config files target 3.11 (concurs CR-L16-06) | `grep -n requires-python pyproject.toml; grep -n python_version mypy.ini` |
| 3 | `:53` | demo seeder = "5 NPCs, 3 locations, **3 factions**" | 5 NPCs OK, 3 locations OK, **4 factions** — `demo_game/seeds/seed.py:896` adds `("iron_legion", "Iron Legion", "military", …)` under `_MILITARY_FACTIONS` | AST/regex scan of `seed.py` |
| 4 | `:57` | "`evals/matchers.py:62-63` resolves `parents[1] / "prompts" / "eval"`" | The resolution is at **`evals/matchers.py:72-73`**. Lines 62-63 today are `score: bool \| None` / `error: str = ""`. This line is the file's **own explicit self-correction, dated 2026-08-10** — it drifted within 17 days | `sed -n '58,75p' evals/matchers.py` |
| 5 | `:86-101` | The layer block enumerates the package set | `check_layers.py` `LAYER_RANK` has **18** entries. CLAUDE.md lists 15 and omits **`observability/` (rank 1)** and **`setup/` (rank 1)**, both real first-level packages in `src/npc_engine/` | `ls src/npc_engine/`; `sed -n '30,56p' scripts/check_layers.py` |
| 6 | `:104` | "Allowed dependencies (**enforced by `make check-layers`**)" followed by 6 explicit rows | The gate enforces a numeric rank ordering (`importer_rank < imported_rank` ⇒ violation, `check_layers.py:117-125`), **not** these rows. Every same-rank (peer) import is green under the gate and absent from the table | Read `check_layers.py`; counterfactual already executed by CR-L06 §4 |
| 7 | `:111` | "`config/common/type_registry/schema/utils` → **nothing**" | **52** intra-`npc_engine` imports originate in those five packages (type_registry 21, schema 18, utils 9, common 4), e.g. `type_registry/base_contract_loader.py:18` → `common.yaml_utils`, `:21` → `utils.errors`. All are rank-1→rank-1 and **all pass `make check-layers`** | `grep -rn "from npc_engine\." src/npc_engine/{config,common,type_registry,schema,utils}/` |
| 8 | `:128` | "Hard limit: **300 lines** of non-test code per file. If you exceed this, split before merging" | **42** non-test `.py` files exceed 300 lines today: src 13, demo_game 18, evals 7, scripts 2, seeds 2. 38 are permanently grandfathered; the 4 in `scripts/`+`seeds/` are scanned by no gate at all. `python scripts/check_rules.py` → `OK - no new violations (133 grandfathered).` | Ran `_iter_py`/`_oversized_functions` from `scripts/check_rules.py` over every tree |
| 9 | `:146` | "Use `from __future__ import annotations` at the top of **every** module" | **96** files lack it: `demo_game` 20/183, `tests` 74/544, `evals` 2/110. `src/npc_engine` is **627/627 compliant** — the only tree mypy covers | AST scan |
| 10 | `:162-172` | Mandatory 5-field module docstring (`Module:/Layer:/Purpose:/Dependencies:/Used by:`) | **176 of 627 (28%)** src files carry all five. Per field: `Layer:` **100%**, `Purpose:` **100%**, `Module:` 65%, `Used by:` 66%, `Dependencies:` **28%**. `scripts/docstring_audit.py:44-48` checks exactly `Layer:` and `Purpose:` — see CR-L05-03 | AST scan of all 627 files |
| 11 | `:255` | "Every public function has at least one happy-path test and one failure test" | 11 of 18 engine failure branches are driven by **no** test (CR-L01 §2, Confirmed); `graph/intent/intent_queries.py`'s real logic is mocked out at every caller (CR-L15-02) | Sibling evidence, Confirmed |
| 12 | `:333` | Pre-merge checklist: "`STATUS.md` (or task tracking file) is updated" | **No `STATUS.md` exists anywhere in the repo.** `find . -name "STATUS.md" -not -path "./.git/*"` → empty. Only `project-harness/archive/STATUS_history_through_2026-05-28.md` | `find` |
| 13 | `:331` | Pre-merge checklist: "…is in `PATTERNS.md`" | Root `PATTERNS.md` does not exist; the file is `project-harness/PATTERNS.md`, and the canonical-locations section at `:262` names only ISSUES/DECISIONS/ROADMAP | `ls` |
| 14 | `:385` | DIP: "engines import `LLMClientProtocol`, never **`MistralAdapter`**" | `MistralAdapter` has **never existed in any `.py` file in 967 commits**. `git log -S "MistralAdapter" --all` → 15 commits, every one a markdown-only edit; `grep -rn Mistral --include=*.py src/ demo_game/ evals/` → 0 | `git log -S`; grep |
| 15 | `:387` | "`api/dependencies.py` is the **sole** composition root for the API layer" | Six composition modules: `dependencies.py` (296 L), `dependencies_infra.py`, `dependencies_stores.py` (7 concrete constructions), `dependency_singletons.py` (122 L), `dependencies_engines/{core,quest,tick_slots}.py`, `dependencies_advanced/{politics,progression,social}.py`. The path is also wrong (`src/npc_engine/api/dependencies.py`) | `ls src/npc_engine/api/ \| grep depend` |
| 16 | `:396` | "no function or method may exceed **40 lines**" | **199** live violations: src 102, evals 42, demo_game 46, scripts 7, seeds 2. 144 grandfathered; **55 are scanned by no gate** (`check_rules._collect` applies `_oversized_functions` only to `src`, line 126) | Ran `_oversized_functions` over every tree |
| 17 | `:399-401` | "No magic numbers… No raw numeric thresholds like `if trust > 50`" | 13 raw numeric comparisons in `engines/` alone, including `engines/emotion/emotion_state.py:51 if arousal >= 70 and valence < -20` — the forbidden shape verbatim | regex scan |
| 18 | `:405-407` | "Pydantic v2 for all data… **No raw `dict` crossing a module boundary**" | **537 of 1,582 (33%)** public functions in `src/npc_engine/` are annotated to return a raw `dict`/`dict[str, …]` | AST scan of return annotations |
| 19 | `:416-418` | "all domain errors are typed exceptions in `utils/errors.py` **with structured fields**" | Violated **inside the named file, twice**: `utils/errors.py:301 class TokenBudgetExceededError(Exception)` and `:345 class ContextBudgetError(Exception)` — neither derives from `NPCSystemError` (`:29`) nor carries a field. Concurs CR-L01/CR-L08 | `grep -n "^class " src/npc_engine/utils/errors.py` |
| 20 | `:421-423` | "Neo4j unavailable → raise `GraphUnavailableError` → API **503**" | `grep -rn "raise GraphUnavailableError" src/` → **0**. `grep -rn "503" src/npc_engine/api/` → **0**. Never true at any point: `git log -S "raise GraphUnavailableError" -- src/` → **0 commits**. 14 of 18 engine fallbacks unwired (CR-L01 §1) | grep + `git log -S` |
| 21 | `:424-425` | "**No try/except around internal invariants**" | `scheduler/tick_scheduler.py:239` (catch-all around all 27 engines), `engines/dialogue/degradation.py:107` and `:119`, `retrieval/context/context_budget_enforcer.py:348` (CR-L01 §3, Confirmed) | Sibling evidence |
| 22 | `:444-445` | "`asyncio.gather()` calls that could spawn unbounded coroutines **must** be capped with `asyncio.Semaphore`" | 6 `asyncio.gather` sites in src; 2 are semaphore-bounded (`intent_formation_engine.py:107`, `memory_consolidation_engine.py:214`). `engines/chapter/chapter_engine.py:230-235` runs **three nested gathers with no semaphore** | `grep -rn "asyncio.gather\|asyncio.Semaphore" src/` |
| 23 | `:451-453` | "Include `npc_id`, `player_id`, `tick`, and `duration_ms` in **all** engine log entries" | **0 of 118** engine log calls carry all four. Only 28 of 118 carry even `npc_id`. Compliance rate **0%** | AST/regex scan of `src/npc_engine/engines/**` for `LOGGER.<level>(` + 400-char kwarg window |
| 24 | `:457-458` | RNG seed logged "for any gossip pair selection, **event sampling**, or distortion probability call" | Gossip logs its seed; event sampling does not (CR-L01-11, Confirmed) | Sibling evidence |
| 25 | `:462-464` | "`context_builder.py` **raises** `TokenBudgetExceededError` if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET`" | Raised **nowhere in `src/`**. The class's only reference outside its own definition is an import in `tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`. The mechanism existed (`f3d1a0a` 2026-06-03, SEV-07) and was **deleted on 2026-06-11** by `45b781d` "delete dead token_budget_enforcer". The rule has described removed code for **78 days**, through 5 subsequent edits of CLAUDE.md | `grep -rn TokenBudgetExceededError`; `git log -S "raise TokenBudgetExceededError"` |
| 26 | `:475-476` | "**every** route except `GET /health` passes through `auth/middleware.py`" | `auth/middleware_helpers.py:66-72` exempts five classes: `/health`, `/readiness`, **`/setup/*` in every env including prod** (covering `POST /setup/validate` and `POST /setup/config`, `api/routes/setup/setup.py:54,97`), and `/docs`,`/redoc`,`/openapi.json`,`/dashboard/*` in dev. The rule names one of five, and the unconditional one is the mutating one | Read `middleware_helpers.py:46-73` |

#### Unverifiable (6) — no operational definition exists, so the rule cannot be tested or enforced

`:381-382` SRP ("every module belongs to exactly one category — data model, reader, writer,
handler/orchestrator, utility, protocol, adapter, or test"); `:384` OCP ("never edit existing engine
files to add a new variant" — requires per-commit intent); `:388-389` ISP ("protocols must be
small" — no threshold); `:390-392` LSP (requires differential mock-vs-real testing that does not
exist); `:414-415` fail-fast ("validate **all** external inputs" — "all" not enumerable);
`:256` "Functions touching Neo4j have integration tests against a **real test DB**" (needs a live
Neo4j; not run in this read-only pass).

---

### 2. Token cost of the mandatory context load

Measured with `wc -c`. Every one of these files is injected before the user's first token — the
project file by `@`-import, the user-level rules and memory by the harness (all appear in this
session's own system-reminder).

| File | Chars | Est. tokens (chars ÷ 4) |
|---|---|---|
| root `CLAUDE.md` | 27 | 7 |
| `project-harness/CLAUDE.md` | **20,786** | **5,197** |
| `~/.claude/rules/common/*.md` (9 files) | 10,628 | 2,657 |
| `~/.claude/rules/README.md` | 4,310 | 1,078 |
| project `memory/MEMORY.md` | 844 | 211 |
| **Total mandatory preamble** | **36,595** | **≈ 9,150** |

- **9,150 tokens ≈ 4.6% of a 200k context**, before a single file is read.
- `project-harness/CLAUDE.md` alone is **5,197 tokens ≈ 2.6%**.

**Strategic number.** 967 commits; **193 session transcripts** exist for this project
(`ls ~/.claude/projects/c--Users-lohan-Documents-hackathons-NPCSystem/*.jsonl | wc -l` → 193),
i.e. ~5 commits per session. At **one** load per session that is **≈ 1.77M tokens** of mandatory
preamble to date, of which **≈ 1.00M** is `project-harness/CLAUDE.md`. This is a **floor**: the
preamble is re-injected on every compaction, and CR-L10-07 establishes the commit stream is
loop-driven (many sessions compact more than once).

The file has only ever grown. Per-commit `wc -l` across the 14 commits that touch it:

```
2026-05-28 82a22af 346
2026-06-01 ccec168 448
2026-06-04 e7c265e 454
2026-06-04 d24f442 464
2026-06-15 59b7e70 468
2026-06-23 c1c7607 475
2026-07-31 b69da87 475
2026-08-10 8c7fdc6 476   <- HEAD
```

**+130 lines in 3 months, 0 lines ever removed.** The 2026-08-10 edit was the `prompts/eval/`
self-correction — which is already stale (FALSE claim #4 above).

---

### 3. Dead rules — never violated in 967 commits

Method: `git log -S "<literal>" --all -- <paths>` for each mechanically searchable rule, plus the
two baseline files, `archive/ISSUES_RESOLVED.md` (155 archived entries) and `ISSUES.md` (68 open).

| Rule | Search | Result |
|---|---|---|
| `:417` "Never `raise Exception("message")`" (gated as **R004**) | `git log -S "raise Exception(" -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. The gate has never had anything to catch |
| `:152` "No wildcard imports" | `git log -S "import *" -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. Ungated |
| `:153` "No relative imports beyond one level" | `git log -S "from .." -- src/ demo_game/ evals/` | **0 commits, ever.** 0 live. Ungated |
| `:119` "No HTTP calls between services" | `git log -S "httpx" -- src/npc_engine/services/` | **0 commits, ever.** 0 live. Ungated |
| `:385` DIP `MistralAdapter` example | `git log -S "MistralAdapter" --all` | 15 commits, **all markdown**. The class has never existed in Python |
| `:421-423` `GraphUnavailableError` → 503 | `git log -S "raise GraphUnavailableError" -- src/`; `git log -S "status_code=503" -- src/npc_engine/api/` | **0 and 0.** The contract has never once been implemented |
| `:462-464` `TokenBudgetExceededError` raise | `git log -S "raise TokenBudgetExceededError"` | Added `f3d1a0a` 2026-06-03, **deleted `45b781d` 2026-06-11**. Dead for 78 days |
| `:397` Nesting ≤ 3 | AST | 4 violations in 2,248 src functions (**0.2%**). Ungated but genuinely obeyed |

**Four rules (wildcard imports, deep relative imports, inter-service HTTP, `raise Exception(`) have
zero violations across the entire 967-commit history and are free to delete** — three of them are
enforced by nothing anyway, and the fourth (R004) is a gate that has never fired. **Three more
(`MistralAdapter`, `GraphUnavailableError`→503, `TokenBudgetExceededError`) are dead in the worse
sense: they describe machinery that does not exist.**

---

### 4. Aspirational rules — violated 20+ times

Ranked by live violation count. A rule with three digits of violations is not a rule.

| Rank | Rule | Live violations | What it actually is |
|---|---|---|---|
| 1 | `:405-407` Pydantic v2 / no raw `dict` crossing a boundary | **537** of 1,582 public src functions (33%) | An unstated preference. Nothing measures it; a third of the public surface contradicts it |
| 2 | `:162-172` 5-field module docstring | **451** of 627 src files non-conforming (72%) | A 2-field rule with 3 decorative fields |
| 3 | `:396` Function length ≤ 40 lines | **199** (144 baselined, 55 outside every gate) | A frozen debt register. CR-L06 §3 measures the burn-down at 1.43/month ⇒ **7.8 years to zero** |
| 4 | `:451-453` 4-field engine log entries | **118 of 118** (0% compliance) | A sentence nobody has ever implemented |
| 5 | `:146` `from __future__ import annotations` on every module | **96** files | True in the one tree mypy covers, false everywhere else |
| 6 | `:451` "Never `print()`" | **59 files** — 20 in `evals/` (grandfathered) + 39 of 47 in `scripts/` (ungated) | A src-only rule stated repo-wide. The gate scripts that enforce it violate it |
| 7 | `:128` 300-line file limit | **42** files | A floor with a permanent exemption list |
| 8 | `:399-401` No magic numbers | 13 in `engines/` alone, incl. the forbidden shape verbatim | Advice |
| 9 | `:397` Nesting ≤ 3 | 24 repo-wide (4 in src) | Borderline — genuinely obeyed in src |

---

### 5. Gate coverage of the 28 **(strict)** rules

| # | Strict rule (line) | Gated by | Live violations | Verdict |
|---|---|---|---|---|
| 1 | SRP `:381` | none | unmeasurable | **theatre** |
| 2 | OCP `:384` | none | unmeasurable | **theatre** |
| 3 | DIP `:385-387` | none (mypy is a weak proxy) | 6 composition roots; example class never existed | **aspirational** |
| 4 | ISP `:388` | none | unmeasurable | **theatre** |
| 5 | LSP `:390` | none | unmeasurable | **theatre** |
| 6 | Function length `:396` | `check-rules` **R006** (src+evals only) | 199 | **aspirational** |
| 7 | Nesting `:397` | none | 4 in src | **live** |
| 8 | No magic numbers `:399` | none | 13+ | **aspirational** |
| 9 | Pydantic v2 / no raw dict `:405` | none | 537 | **aspirational** |
| 10 | Enums/Literal `:408` | none | unmeasured | **theatre** |
| 11 | Fail fast at boundaries `:414` | none | unmeasurable | **theatre** |
| 12 | Custom exception hierarchy `:416` | `check-rules` **R004** (literal `raise Exception(` only) | 0 by the gate; **2 by the rule** (`errors.py:301,345`) | **theatre** — the gate matches a string never written and misses both real violations, in the file the rule names |
| 13 | Never swallow errors `:419` | `check-rules` **R003** (src+evals) | 3 baselined + 10 silent sites (CR-L01 §3) | **aspirational** |
| 14 | Engine boundary fallbacks `:421` | none | 14 of 18 unwired; 0 raises; 0 `503` | **dead** |
| 15 | No try/except around invariants `:424` | none | 4 named sites | **aspirational** |
| 16 | Constructor injection `:429` | none | ~0 | **live** |
| 17 | Session ownership `:433` | none | 0 — `graph/infra/transaction_coordinator.py:43,46` is the only file calling `begin_transaction()`/`commit()` | **live** |
| 18 | Async all the way `:442` | none | unmeasured | **theatre** |
| 19 | Semaphore for batch `:444` | none | 4 of 6 gathers uncapped | **aspirational** |
| 20 | Lock for shared state `:446` | none | 0 (`emotion_store.py:28`, `session_store.py:41`) | **live** |
| 21 | Structured logging / never print `:451` | `check-rules` **R002** (src+evals) | 59 files print; 0/118 log calls carry the 4 fields | **aspirational** |
| 22 | LLM prompt redaction `:454` | **runtime validator** `config_logging_validators.py:56` | 0 | **live (genuinely gated)** |
| 23 | RNG seed logging `:457` | none | 1 of 3 sites | **aspirational** |
| 24 | Token budget enforced `:462` | none | mechanism deleted 2026-06-11 | **dead** |
| 25 | Structured output validated `:465` | none | `engines/dialogue/response_parser.py` exists | **live** |
| 26 | Idempotent assembly `:467` | none | 0 (no `datetime`/`uuid`/`random` in `prompt_builder.py`) | **live** |
| 27 | Input caps `:472` | **runtime** `dialogue_models.py:51` + `clock.py:37 Field(ge=1, le=MAX_DELTA_TICKS)` (`config.py:51 = 1000`) | 0 | **live (genuinely gated)** |
| 28 | Auth on all routes `:475` | tests only | 4 undeclared exemption classes | **aspirational** |

**Totals: 28 strict rules — 5 gated (R002, R003, R006 + 2 runtime validators), 1 gated by a gate
that does not gate (R004), 22 ungated.**

Applying **CR-L06 §4**'s executed counterfactuals to the gate side: of the 14 targets in `make
check`, **6 fail the counterfactual** (`check-human-gates`, `check-conservation` I2,
`check-test-quality`, `check-docstrings`, `check-harness`, `check-label-survival`). Of the rules
above, the one carried by `check-docstrings` (#10 in the FALSE table) is therefore **gated by a
gate proven not to gate**: CR-L06 executed `docstring_audit.audit` against a scratchpad file whose
docstring read `"""Layer: banana\nPurpose: \n"""` and got **0 findings**.

Three of the five real gates (R002/R003/R006) are **ratchets whose baseline equals their live set
exactly** — verified by importing `check_rules._collect()` and `_collect_evals()` at HEAD:
`{'R001': 31, 'R006': 102}` (133) and `{'R001': 7, 'R002': 20, 'R003': 3, 'R006': 42}` (72). Every
current violation is pre-approved. The gates can only catch the 967th-commit-plus-one.

---

### 6. Contradictions and self-conflicts

| # | Conflict | Both references |
|---|---|---|
| 1 | "**Hard limit**: 300 lines… split before merging" vs. an enforcement mechanism that permanently exempts 38 files and reports `OK` | `CLAUDE.md:128` vs `scripts/check_rules.py:186` ("split it **or add a DECISIONS.md waiver**") + `rules_baseline.txt` (133 rows). CLAUDE.md **never mentions grandfathering**, so a session reading only CLAUDE.md believes the limit is hard and a session running only the gate believes the tree is clean |
| 2 | The pre-merge checklist mandates updating a file that does not exist | `CLAUDE.md:333` (`STATUS.md`) vs `find . -name STATUS.md` → empty |
| 3 | The pre-merge checklist names `PATTERNS.md` unqualified while the canonical-locations section deliberately qualifies its three siblings and omits this one | `CLAUDE.md:331` vs `CLAUDE.md:262-264` |
| 4 | `SKILLS_QUEUE.md` is named as a normative destination for questions; CR-L07-08 measures it dead for ~90 days | `CLAUDE.md:306` vs CR-L07-08 |
| 5 | "Allowed dependencies (**enforced by `make check-layers`**)" — the gate enforces a different (weaker, rank-based) rule that permits 52 imports the table forbids | `CLAUDE.md:104-111` vs `scripts/check_layers.py:117-125` |
| 6 | The exception-hierarchy rule is violated inside the file it names as the single source of truth | `CLAUDE.md:416-418` vs `src/npc_engine/utils/errors.py:301,345` |
| 7 | vs **`HARNESS_GATES.md`**: CLAUDE.md's rules are enforced by a `make check` that HARNESS_GATES describes as 5 targets; it is 14 (`Makefile:200`). HARNESS_GATES also states the rules baseline is "57 today" (it is 133) and the mypy baseline "256 today" (it is `0`) | CR-L13-01, CR-L06 §5 — both headline numbers wrong, in opposite directions |
| 8 | vs **user-level `~/.claude/rules/common/coding-style.md`**: "200-400 lines typical, **800 max**" and "Functions are small (**<50 lines**)" — both looser than CLAUDE.md's 300/40, loaded in the same preamble, with no precedence statement in either file | user rules vs `CLAUDE.md:128,396` |
| 9 | vs **user-level `development-workflow.md`**: step 0 is *mandatory* "GitHub code search first: run `gh search repos` and `gh search code` before writing anything new". CR-L06 §5 measured `gh: command not found` on this machine. A mandatory first step is unexecutable | user rules vs environment |
| 10 | vs **user-level `testing.md`**: "Minimum Test Coverage: 80%" applies to everything; the repo's actual floors are `--cov-fail-under=80` for `tests/` (`Makefile:53`) and **75** for evals (`Makefile:139`), with `demo_game/` (36,961 LOC, 1,116 tests) under **no** coverage floor and in neither `make check` nor CI (CR-L06 §7, CR-L15-06) | user rules vs `Makefile:53,139` |
| 11 | "These rules are not suggestions. **Violating them is a bug**" vs. 26 of the file's own claims being false and 22 of 28 strict rules being ungated | `CLAUDE.md:3-4` vs §1 and §5 above |

---

## Subtraction proposal — `CLAUDE.md` 476 → **248 lines**

The governing principle: **a rule that is unenforced, dead, or contradicted by the code is worse
than no rule**, because it is the evidence a session uses to conclude the whole file is decorative.
The measured proof that this has already happened is CR-L05-03: on the two docstring fields a gate
checks, compliance is **100%**; on the three it does not, **28–66%**. Sessions obey gates and read
past prose.

### Delete (228 lines)

| Lines | Section | Lines removed | Why the deletion is safe |
|---|---|---|---|
| `155-215` | **Documentation** (whole section) | **58** (keep 3) | Replace with: *"Every module docstring carries `Layer:` and `Purpose:`; `__init__.py` also `Public surface:`. Enforced by `make check-docstrings`."* That is precisely what `docstring_audit.py:44-48` checks and what the tree achieves (100%/100%/100%). The 5-field format is at 28%; the `__init__.py` template block, the "what does NOT need documentation" list and the closing homily are 58 lines of prose that changed nothing measurable |
| `266-306` | **Issues log** template + id/archive protocol | **38** (move, don't delete) | Pure boilerplate that belongs in `ISSUES.md`'s own header, where the live examples already are. It is loaded into every session but consulted in the small minority that log an issue |
| `219-231` | **TDD discipline** (RED/GREEN/REFACTOR) | **13** | Duplicated near-verbatim in the user-level `~/.claude/rules/common/testing.md`, which loads in the same preamble. Paying twice |
| `253-258` | **Test requirements per module** | **6** | 4 claims: one FALSE (`:255`, 11 untested failure branches), one unverifiable (`:256`), two unmeasured. No gate |
| `379-392` | **SOLID** (SRP/OCP/ISP/LSP + DIP) | **12** (keep 2) | SRP/OCP/ISP/LSP are all **unverifiable — no operational definition, no gate, no violation ever recorded**. DIP survives as two lines with the `MistralAdapter` example (never existed) and the "sole composition root" clause (6 roots) removed |
| `421-423` | **Engine boundary fallback contracts** | **3** | Describes a contract implemented **0 times in 967 commits** (`git log -S "raise GraphUnavailableError"` → 0). Either implement it as CR-L01-08 proposes, or stop asserting it |
| `462-464` | **Token budget enforced** | **3** | Describes code **deleted on 2026-06-11** (`45b781d`). 78 days stale through 5 subsequent edits of this file |
| `457-458` | **RNG seed logging** | **2** (narrow to 1) | Two of its three named sites do not log a seed. Narrow to the one that does, or delete pending CR-L01-11 |
| `451-453` | **Structured logging** 4-field mandate | **2** (keep the `print()` line) | 0/118 compliance. Keep "use `utils/logging.py`, never `print()`"; delete the never-honoured field list |
| `152-153` | wildcard / deep-relative import bans | **2** | **0 violations in 967 commits**, no gate. Free to delete |
| `119` | "No HTTP calls between services" | **1** | **0 violations in 967 commits**, no gate |
| `417` (clause) | "Never `raise Exception("message")`" | **1** | **0 occurrences in 967 commits.** Replace the whole bullet with the *enforceable* form: *"Every class in `utils/errors.py` derives from `NPCSystemError` and carries structured fields"* — which is violated twice today and is one grep to gate |
| `26-44` | Key commands | **0 — keep** | 13/13 verified TRUE. Do not touch |
| `235-246` | Test layout | **0 — keep** | 7/7 verified TRUE. Do not touch |
| various | 26 FALSE claims corrected in place | ~**+8/−8** | Net zero lines, but this is the highest-value edit in the list |
| `364-371` | Token efficiency | **0 — keep** | 8 lines; the only section that pays for itself in a 9,150-token preamble |

**476 − 228 = 248 lines.**

### What survives, and why

Orientation and stack (**corrected**: OpenAI adapter ships, Python 3.11/3.14 split, 4 factions);
the 13 key commands and 13 key file paths (all verified TRUE — this is the file's single highest
value-per-token content, since it saves every session a `ls`/`make help` round trip); the demo-world
table (verified TRUE, and the "IDs are stable — do not rename" instruction is load-bearing); the
layer model **plus `observability` and `setup`**, with the allowed-dependency table replaced by the
one sentence the gate actually enforces (*"a package may import only packages of equal or lower
rank; ranks live in `scripts/check_layers.py`"*); the 4 forbidden cross-layer patterns minus the
dead one; code style minus the 3 dead import rules; test layout; the PM canonical-locations
paragraph; task discipline with the 3 dead checklist items removed; asking-before-doing; token
efficiency; and **the 13 strict rules that are either gated or measured obeyed** (function length,
never-swallow, print, nesting, ctor injection, session ownership, lock, redaction, structured
output, idempotent assembly, input caps, auth, Pydantic — the last three rewritten to state what is
true).

Every deleted rule that is worth keeping should be re-introduced **as a gate, not as prose**. Three
are one-grep gates that would have caught live violations today: `class .*\(Exception\)` in
`utils/errors.py` (2 hits), `-> dict` on public src functions (537 hits), and an
`asyncio.gather`-without-`Semaphore` check (4 hits).

---

## Findings

### [CR-L05-01] Delete or implement the three strict contracts whose machinery does not exist in `src/`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** Three rules marked **(strict)** describe mechanisms with zero implementation.
  (a) `CLAUDE.md:421-423` "Neo4j unavailable → raise `GraphUnavailableError` → API 503":
  `grep -rn "raise GraphUnavailableError" src/` → **0**; `grep -rn "503" src/npc_engine/api/` → **0**;
  `git log -S "raise GraphUnavailableError" -- src/` → **0 commits, ever**. Two service docstrings
  (`military_battle_service.py:59`, `military_resource_service.py:47`) quote the contract as fact
  (CR-L01 §1, rows 13/14: "unwired — docstring is fiction").
  (b) `CLAUDE.md:462-464` "`context_builder.py` raises `TokenBudgetExceededError`": the class at
  `utils/errors.py:301` is raised nowhere; its only non-definition reference in the repo is
  `tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`. `git log -S "raise TokenBudgetExceededError"`
  shows it was added by `f3d1a0a` (2026-06-03, SEV-07) and **deleted by `45b781d` on 2026-06-11**
  ("delete dead token_budget_enforcer").
  (c) `CLAUDE.md:385,387` DIP: `MistralAdapter` has never existed in a `.py` file
  (`git log -S "MistralAdapter" --all` → 15 commits, all markdown), and "`api/dependencies.py` is
  the **sole** composition root" is contradicted by six modules (`ls src/npc_engine/api/ | grep depend`).
- **Cost of inaction:** These are not stale comments; they are the file's own worked *examples* of
  what a "strict" rule looks like. A session that checks one and finds it fictional has been taught
  that "(strict)" is decorative, which is the mechanism behind the 22-of-28-ungated result in §5
  and the 100/100/28/66 docstring split in CR-L05-03. (b) has been wrong for 78 days across five
  edits of the file — the drift rate is already established.
- **Fix sketch:** Delete `:421-423` and `:462-464` outright (6 lines), or implement them under
  CR-L01-06/CR-L01-08 and keep the text. Rewrite the DIP bullet to two lines naming
  `LLMClientProtocol` and the real composition-root set.
- **Effort:** S (delete) / L (implement)
- **Removes:** ~10 lines of CLAUDE.md; unblocks deleting `TokenBudgetExceededError` (`errors.py:301`)
- **Blast radius:** Two `military_*_service.py` docstrings and `ports/dialogue_graph_port.py:73`
  quote contract (a) and must be corrected in the same change.

### [CR-L05-02] The 4-field engine-log mandate has 0% compliance across 118 call sites

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `CLAUDE.md:451-453` (strict): "Include `npc_id`, `player_id`, `tick`, and
  `duration_ms` in **all** engine log entries." Scanned every `LOGGER|_logger|logger|_LOGGER.<level>(`
  call under `src/npc_engine/engines/**` and inspected the following 400 characters of kwargs:

  ```
  engine log calls: 118; with npc_id: 28; with all 4 (npc_id,player_id,tick,duration_ms): 0
  ```

  **0 of 118.** No gate checks it; `check_rules.py`'s R002 only asks whether `print(` appears.
- **Cost of inaction:** Already realised, not future. CR-L01 §3 ranks `tick_scheduler.py:239` the
  #1 silent-failure site precisely because a dead engine produces a 200 with nothing correlatable;
  the field set this rule mandates is exactly what would make that observable. Every new engine
  written under this rule adds another uncorrelated log line, and the cost compounds with the 27
  tick slots.
- **Fix sketch:** Either add a bound-context helper in `utils/logging.py` that injects
  `npc_id`/`tick`/`duration_ms` at the engine boundary and gate on its use, or delete the field list
  from `:453` and keep only "use `utils/logging.py`, never `print()`" (true in `src/`: 0 real
  `print(` calls).
- **Effort:** S (delete) / M (bound-context helper)
- **Removes:** 2 lines of CLAUDE.md
- **Blast radius:** If implemented, touches the log call sites of all 27 engines.

### [CR-L05-03] Compliance tracks the gate, not the rule — measured 100/100/28/66 on one docstring

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `CLAUDE.md:162-172` mandates a **five**-field module docstring. `scripts/docstring_audit.py:44-48`
  checks **two** of them. Field-by-field compliance across all 627 `src/npc_engine/**/*.py`:

  | Field | In the rule | Checked by the gate | Compliance |
  |---|---|---|---|
  | `Layer:` | yes | **yes** | **627/627 = 100%** |
  | `Purpose:` | yes | **yes** | **627/627 = 100%** |
  | `Module:` | yes | no | 409/627 = 65% |
  | `Used by:` | yes | no | 414/627 = 66% |
  | `Dependencies:` | yes | no | **180/627 = 28%** |

  All five fields present: **176/627 = 28%.** The control: `demo_game/`, which
  `make check-docstrings` does **not** scan at all, sits at **150/183 = 81%** on the full 5-field
  format — *higher than the gated tree*, because it was written before the gate defined a lower bar.
  And CR-L06 §4 executed the counterfactual on the gate itself: a docstring reading
  `"""Layer: banana\nPurpose: \n"""` produces **0 findings**.
- **Cost of inaction:** This is the cleanest available measurement of what an unenforced rule is
  worth in this repo: **zero to +38 points**, and the gate's *definition* actively displaces the
  rule's. Every ungated rule in §5 (22 of 28) should be assumed to decay to its gated subset. It has
  been decaying since `38f7e87` (2026-06-04).
- **Fix sketch:** Cut `CLAUDE.md:162-172` to the two fields the gate checks plus `Public surface:`
  for `__init__.py` (at 102/102). If `Dependencies:`/`Used by:` are genuinely wanted, add them to
  `docstring_audit.py`'s `required` list and ratchet — do not leave them as prose.
- **Effort:** S
- **Removes:** ~58 lines of CLAUDE.md (the whole Documentation section collapses to 3)
- **Blast radius:** None if cutting. If gating the extra fields, 451 src files fail on day one and
  need a baseline.

### [CR-L05-04] The 300-line and 40-line "hard limits" are floors with permanent exemption lists, and CLAUDE.md never says so

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `CLAUDE.md:128` "Hard limit: **300 lines** of non-test code per file. If you exceed
  this, split before merging." `CLAUDE.md:396` "no function or method may exceed **40 lines**."
  Measured by importing `scripts/check_rules.py` and running its own scanners over every tree:

  ```
  src/npc_engine     files= 627  >300lines= 13  fns>40lines= 102
  demo_game          files=  96  >300lines= 18  fns>40lines=  46
  evals              files= 110  >300lines=   7  fns>40lines=  42
  scripts            files=  47  >300lines=   2  fns>40lines=   7
  seeds              files=   4  >300lines=   2  fns>40lines=   2
  ```

  **42 files and 199 functions over the limit**, and `python scripts/check_rules.py` prints
  `OK - no new violations (133 grandfathered).` The baseline set equals the live set **exactly**
  (`_collect()` → `{'R001': 31, 'R006': 102}`; `_collect_evals()` → `{'R001': 7, 'R002': 20, 'R003': 3, 'R006': 42}`).
  `check_rules._collect()` line 126 applies `_oversized_functions` only to `src`, so **46 demo_game
  + 7 scripts + 2 seeds = 55 function-length violations are outside every gate**; `scripts/` and
  `seeds/` are outside the file-size gate too (CR-L08-04). CR-L08-01 documents `demo_game/client.py`
  growing to 1,901 lines — **+481 while the gate stayed green** — against a DEC-034 waiver of ~750.
  CR-L06 §3 measures the R006 burn-down at 1.43/month ⇒ **7.8 years to zero**. CLAUDE.md contains
  **no mention of grandfathering, baselines, or waivers** for R006 at all.
- **Cost of inaction:** Two failure modes already realised. A session reading only CLAUDE.md
  believes 300/40 are hard and wastes effort splitting; a session running only `make check` believes
  the tree is clean. Meanwhile the four largest files grew past their own DECISIONS.md waivers by
  2–3× with no gate noticing (CR-L08-01/02/08).
- **Fix sketch:** State the ratchet in CLAUDE.md in one sentence next to `:128` and `:396` —
  *"enforced as a no-new-violations ratchet against `scripts/rules_baseline.txt`; the current
  exemption count is N"* — and extend `_collect()`'s `_oversized_functions` loop to `demo` (line
  126) so the 46 demo_game violations at least become visible debt.
- **Effort:** S (document) / M (extend scope + rebaseline)
- **Removes:** 0 lines; adds ~2
- **Blast radius:** Extending R006 to `demo_game/` adds 46 rows to `rules_baseline.txt`.

### [CR-L05-05] The R004 gate matches a string never written in 967 commits, and misses both real violations inside the file its rule names

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `CLAUDE.md:416-418` (strict): "all domain errors are typed exceptions in
  `utils/errors.py` **with structured fields**. Never `raise Exception("message")`."
  The gate is `check_rules.py:49 _RAISE_EXC_RE = re.compile(r"raise\s+Exception\(")`.
  `git log -S "raise Exception(" -- src/ demo_game/ evals/` → **0 commits, ever**; R004 is absent
  from both baseline files. The gate has never had anything to catch.
  The **substantive** half is violated twice, inside the file the rule names as the single source of
  truth: `src/npc_engine/utils/errors.py:301 class TokenBudgetExceededError(Exception)` and
  `:345 class ContextBudgetError(Exception)` — neither derives from `NPCSystemError` (`:29`) nor
  carries a structured field. `grep -n "^class " src/npc_engine/utils/errors.py | grep -v "Error)"`
  returns exactly those two plus the base.
- **Cost of inaction:** The repo currently believes this rule is gated. It is gated on the one form
  nobody has ever written, and unpoliced on the form that is live today. `ContextBudgetError` is
  the exception silently caught at `context_budget_enforcer.py:348` (CR-L01 §3, rank 2) — a
  fieldless bare-`Exception` subclass is exactly why that catch carries no diagnostic payload.
- **Fix sketch:** Replace `_RAISE_EXC_RE` with an AST check over `utils/errors.py` that every
  `ClassDef` whose name ends `Error` has `NPCSystemError` (or a subclass) in its bases. That is a
  ~15-line addition to `check_rules.py` and it goes red on 2 classes today.
- **Effort:** S
- **Removes:** ~1 line of CLAUDE.md (the dead `raise Exception(` clause); adds ~15 to `check_rules.py`
- **Blast radius:** Fixing the 2 classes touches `context_budget_enforcer.py` and the CR-L01-06
  decision about whether `TokenBudgetExceededError` survives at all.

### [CR-L05-06] "Auth on all routes except `GET /health`" understates the unauthenticated surface by four classes, one of them unconditional in prod

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `CLAUDE.md:475-476` (strict): "every route except `GET /health` passes through
  `auth/middleware.py`." `src/npc_engine/auth/middleware_helpers.py:66-72`:

  ```python
  if path in (HEALTH_PATH, READINESS_PATH):
      return True
  if path.startswith(SETUP_PATH_PREFIX):        # "/setup" — every env, prod included
      return True
  if path in DOCS_PATHS or path.startswith(DASHBOARD_PATH_PREFIX):
      return env == "dev"
  ```

  `/setup/*` covers `POST /setup/validate` and `POST /setup/config`
  (`api/routes/setup/setup.py:54,97`) — two **mutating** endpoints, unauthenticated in production.
  The code's own docstring justifies it ("localhost-only by bind (DEC-131)"), a constraint CLAUDE.md
  does not mention. CR-L13-09 separately records `/setup/*` as an entirely undocumented API surface.
  The rule also says "`GET` /health" while the code exempts by path only, ignoring method.
- **Cost of inaction:** The security rule most likely to be quoted in a licensing or integration
  conversation is the one that is wrong, and it is wrong in the permissive direction. A studio
  integrator reading `:475` will not know to check the bind address before exposing the container.
  CR-L16-07 measures the `app` container running as root with no healthcheck, so the localhost-bind
  assumption is the only thing holding.
- **Fix sketch:** Rewrite `:475-476` to enumerate the five exemption classes and state the DEC-131
  localhost-bind precondition for `/setup/*` explicitly, or move `/setup/*` behind a first-run
  bootstrap token.
- **Effort:** S (document) / M (token)
- **Removes:** 0; replaces 2 lines with 4
- **Blast radius:** `docs/API.md` (already missing the `/setup/*` surface per CR-L13-09) and the
  Unity first-launch wizard flow.

### [CR-L05-07] The layer model omits two real ranked packages and its dependency table is not what `check-layers` enforces

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CLAUDE.md:86-101` lists 15 packages; `scripts/check_layers.py:32-56` `LAYER_RANK`
  has **18**, adding `"observability": 1` and `"setup": 1` — both real directories in
  `ls src/npc_engine/`. A session adding a file to `observability/` has no layer entry to consult.
  `CLAUDE.md:104` claims the six dependency rows are "**enforced by `make check-layers`**", but the
  gate's rule is numeric (`check_layers.py:117-125`: violation iff `importer_rank < imported_rank`),
  which permits every same-rank import. Row `:111` "`config/common/type_registry/schema/utils` →
  **nothing**" is contradicted by **52** live intra-rank-1 imports — e.g.
  `type_registry/base_contract_loader.py:18` → `common.yaml_utils`, `:19` → `type_registry.*`,
  `:21` → `utils.errors` — **all of which pass the gate**. Separately, `CLAUDE.md:116` "No Neo4j
  queries outside `graph/`" is true today (0 hits) but its gate scans only 5 of 15 packages:
  `check_rules._CYPHER_SCAN_DIRS = ('engines','world','retrieval','services','scheduler')`, leaving
  `api/`, `auth/`, `data/`, `cache/`, `mutation/` unscanned (concurs CR-L06 §7).
- **Cost of inaction:** The layer model is the file's most-consulted section and the only one with a
  gate that CR-L06 §4 verified actually goes red. Two undocumented packages and a table that
  overstates what is enforced mean the section's authority is spent on rows that are decorative,
  and the one real constraint (rank ordering) is never stated.
- **Fix sketch:** Add `observability/` and `setup/` rows with `[config peer, rank 1]`; replace the
  six-row table with the sentence the gate implements — *"a package may import only packages of
  equal or lower rank; the ranks are in `scripts/check_layers.py`"* — and widen `_CYPHER_SCAN_DIRS`
  to all non-`graph` packages.
- **Effort:** S
- **Removes:** ~5 lines of CLAUDE.md (6 table rows → 1 sentence)
- **Blast radius:** Widening `_CYPHER_SCAN_DIRS` may surface new R005 rows; measured as 0 today.

### [CR-L05-08] The stack table is 18 days from its last edit and already wrong in three places

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `CLAUDE.md:22` states "no OpenAI adapter ships today", but
  `src/npc_engine/engines/llm/openai_adapter.py` defines `OpenAICompatibleAdapter(LLMClientProtocol)`,
  registered at `engines/llm/factory.py:107 register_backend("openai", _build_openai)`, with
  `OPENAI_API_URL`/`OPENAI_API_KEY` at `config.py:114-115` under SHIP-02/DEC-126.
  `CLAUDE.md:23` states Python 3.14 while `pyproject.toml:8` says `requires-python = ">=3.11"` and
  `mypy.ini:2` says `python_version = 3.11` (CR-L16-06 measures this as two incompatible targets).
  `CLAUDE.md:53` says the seeder creates "3 factions"; `demo_game/seeds/seed.py:896` adds a fourth
  (`iron_legion`). And `CLAUDE.md:57` — the file's **only explicitly dated self-correction**
  ("Corrected 2026-08-10… `evals/matchers.py:62-63` resolves `parents[1] / "prompts" / "eval"`") —
  now points at the wrong lines: the resolution is at `evals/matchers.py:72-73`; lines 62-63 are
  `score: bool | None` / `error: str = ""`. It drifted in **17 days**.
- **Cost of inaction:** The stack table is what a new session reads to decide whether a capability
  exists. "No OpenAI adapter ships today" will cause a session to build one that already exists —
  the single most expensive class of error this file can cause. The self-correction case establishes
  the drift rate for **any** `file:line` citation in this document: under three weeks.
- **Fix sketch:** Correct the three claims; replace the `matchers.py:62-63` citation with a
  line-number-free reference (`evals/matchers.py`, `_PROMPT_YAML_PATH`). As a standing rule, cite
  symbols, never line numbers, in a document edited 14 times in 3 months.
- **Effort:** S
- **Removes:** 0; corrects 4 claims
- **Blast radius:** None.

### [CR-L05-09] 9,150 tokens of mandatory preamble per session, ~1.8M to date, for a rule set that is 22/28 ungated

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -c` over the auto-loaded set: root `CLAUDE.md` 27 + `project-harness/CLAUDE.md`
  **20,786** + `~/.claude/rules/common/*.md` 10,628 + `~/.claude/rules/README.md` 4,310 +
  project `MEMORY.md` 844 = **36,595 chars ≈ 9,150 tokens** (chars ÷ 4), **4.6% of a 200k window**
  before the first file read. `project-harness/CLAUDE.md` alone is 5,197 tokens (2.6%).
  193 session transcripts exist for this project
  (`ls ~/.claude/projects/c--Users-lohan-Documents-hackathons-NPCSystem/*.jsonl | wc -l` → 193) across
  967 commits ⇒ **≈ 1.77M tokens** of preamble to date at one load per session (a floor — the
  preamble is re-injected on compaction), of which **≈ 1.00M** is the project file.
  Per-commit `wc -l` shows the file at 346 → 476 lines over 14 commits with **zero lines ever
  removed**. §5 measures that 22 of its 28 strict rules are enforced by nothing, and CR-L06 §4 shows
  one of the remaining gates fails its counterfactual.
- **Cost of inaction:** Roughly half of the largest fixed cost in every session buys rules that
  nothing checks and 26 claims that are false. The cost is monotonic — the file has only ever
  grown, and its growth rate (+130 lines/3 months) exceeds its correction rate (1 self-correction,
  itself now stale).
- **Fix sketch:** Execute the subtraction proposal above: 476 → 248 lines, ~10.4k chars, ~2.6k
  tokens — a **50% cut** in the project file's share of the preamble. Additionally, `TDD discipline`
  (`:219-231`) is duplicated in the user-level `rules/common/testing.md` loaded in the same
  preamble; deleting one copy is free.
- **Effort:** M
- **Removes:** **228 lines** of `project-harness/CLAUDE.md` (~10,400 chars, ~2,600 tokens/session)
- **Blast radius:** The Issues-log template (38 lines) must land in `ISSUES.md`'s header, not be
  lost. Nothing else references CLAUDE.md by line number.

### [CR-L05-10] Three pre-merge checklist items instruct sessions to satisfy things that do not exist

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CLAUDE.md:316-335` requires the checklist result be written into every task's final
  summary, and closes "If any item is not satisfied, the task is not done."
  `:333` "`STATUS.md` (or task tracking file) is updated" — `find . -name "STATUS.md" -not -path "./.git/*"`
  returns **nothing**; the only match anywhere is `project-harness/archive/STATUS_history_through_2026-05-28.md`.
  `:331` "Any new pattern reused twice is in `PATTERNS.md`" — root `PATTERNS.md` does not exist
  (`project-harness/PATTERNS.md` does), and the canonical-locations paragraph at `:262-264`
  deliberately qualifies its three siblings while omitting this one.
  `:323` "No file exceeds 300 lines of non-test code" — 42 files do (CR-L05-04); an honest session
  can never tick this box.
- **Cost of inaction:** A mandatory checklist with unsatisfiable items trains every session to tick
  boxes it has not verified — precisely the habit that produced the 29 false claims across `docs/`
  (CR-L13 §1) and the 26 here. The parenthetical escape hatch "(or task tracking file)" makes `:333`
  unfalsifiable, which is worse than deleting it.
- **Fix sketch:** Delete `:333`; change `:331` to `project-harness/PATTERNS.md`; change `:323` to
  "no **new** file exceeds 300 lines (`make check-rules` is green)".
- **Effort:** S
- **Removes:** 1 line; corrects 2
- **Blast radius:** None.

---

## Pre-merge checklist for this task

- [x] No source file created, edited or deleted — read-only lens honoured; the only write is this file
- [x] Every FALSE claim carries a `file:line` or a pasted command with real output
- [x] All three required integers reported (109 / 26 / 6)
- [x] Token cost measured, not estimated by eye (`wc -c`; method stated as chars ÷ 4)
- [x] Dead-rule claims backed by `git log -S` over the full 967-commit history, not a HEAD grep
- [x] No CRITICAL added — the review's three are already spent
- [x] No rule restated as a finding; every finding is a measurement *about* a rule
- [x] Adjacent work attributed to the sibling lens that owns it (CR-L01, CR-L06, CR-L08, CR-L13, CR-L15, CR-L16) rather than re-derived
- [ ] No `ISSUES.md` entries filed — this is a read-only review lens; the orchestrator owns backlog creation
