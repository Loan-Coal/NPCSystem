# CR-L09 — Simplicity / subtraction

Lens L9, dispatched last. Branch `eval-ab-context-arms`, HEAD `d46ae42`, 2026-08-28. Read-only —
the only file written is this one. Fifteen lenses have reported; their measurements are the raw
material here and are **cited, not re-derived**. Every row marked **delete now** was re-verified
this session with a command whose output is pasted or summarised below.

**The ledger is the deliverable.** It is the one artifact this review builds toward, and it is a
*proposal*: CLAUDE.md forbids deleting a file you did not create without human approval, so every
row is written to be actionable by one person in one sitting.

---

## 0. Verification pass (what I re-ran, and where the siblings' numbers moved)

| Claim | Sibling | Re-measured here | Verdict |
|---|---|---|---|
| 175 unreferenced archive files / 16,724 lines | CR-L11-07 | **177 files / 17,699 lines** (basename cross-reference over every tracked `.md/.py/.yaml/.txt/.ps1/.sh/.json/.toml` outside `archive/` and `review-2026-08/`) | Confirmed, **larger** than claimed |
| `scan_fix_diff.py` can be deleted outright | CR-L11-02 | **False.** `scripts/expand_loop.sh:387` invokes it; `tests/unit/harness/test_loop_gates.py:26` imports it | **Corrected** — it is loop machinery, not a standalone orphan |
| 14 session prompts / 3,463 lines | CR-L11-08 | 14 files / **3,463 lines** exactly; but `ROADMAP.md:3077,3452` links **2** of them (`PROMPT_P23_UNBLOCK.md`, `EVAL_P25_TO_P31_PLAN.md`) | Confirmed; deletable set is **12 files / 2,791 lines** |
| `engines/deception/` has zero external importers | CR-L01-12 | Confirmed — only its own `__init__.py` and `tests/unit/engines/test_deception_engine.py:35` | Confirmed |
| `engines/currency/` is an empty namespace | CR-L01-12 | Confirmed — `__init__.py` only, 12 lines, docstring still reads `Public surface: (list re-exports here)` | Confirmed |
| `live_openapi.json` has no consumers | CR-L08-09 | Confirmed — **zero** hits in `*.py`, `*.yml`, `Makefile`, `*.sh`, `*.ps1`; markdown-only mentions | Confirmed |
| 15 `session_kwarg` tautology tests | CR-L14-01 | Confirmed — 15 test functions, and `grep -rn "run_tick(session" tests/` → **0** | Confirmed |
| `check-base-rate` / `check-engine-coverage` have no `make` target | CR-L03-04, CR-L11-02 | Confirmed — both `MISSING`; **but both have live 227/234-line test files that run inside `make test-cov`** | Confirmed, with a material addition |
| Sequence subsystem is isolated | CR-L03-12 | **Partly false** — `evals/__main__.py`, `scenario_adapters.py`, `world_map.py`, `reset_fidelity_record.py` and two `e2e/scripts/` reference it | **Corrected** — requires unwiring, not a clean cut |
| 7 dead `verify-v13`/`verify-v14-p*` Makefile aggregates | CR-L06 §6 | Confirmed — `grep -rn "verify-v13\|verify-v14" .github/ scripts/ .claude/` → **empty** | Confirmed |

Commands, abbreviated:

```
$ git ls-files project-harness/archive | grep '\.md$' | wc -l          → 215
$ <basename cross-reference, excluding archive/ and review-2026-08/>
  archive md: 215  loc 29168
  referenced outside archive/review: 38  loc 11469
  UNREFERENCED: 177  loc 17699          ISSUES_RESOLVED.md in referenced set? True

$ for t in check-base-rate check-engine-coverage review-cases check-variance variance-score; do
      grep -qE "^$t:" Makefile && echo "$t EXISTS" || echo "$t MISSING"; done
  check-base-rate MISSING / check-engine-coverage MISSING / review-cases MISSING
  check-variance MISSING / variance-score MISSING

$ grep -rn "run_tick(session" tests/ --include=*.py | wc -l            → 0
$ grep -rn "live_openapi" --include=*.py --include=Makefile --include=*.sh --include=*.ps1 --include=*.yml .
                                                                       → (empty)
$ grep -rn "verify-v13\|verify-v14" .github/ scripts/ .claude/         → (empty)
```

**One new fact that changes a ranking.** The ten longest tracked paths in the repository are *all*
inside `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/` (67 files), and 43
tracked paths exceed 100 characters:

```
$ git ls-files | awk '{print length($0), $0}' | sort -rn | head -3
118 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-40-slice2-negotiation-backed-trade-handler.md
116 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-21-slice2-world-state-quest-trigger-wire.md
112 project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/EXP-211-212-player-memory-and-forgetting.md
$ git ls-files | awk 'length($0)>100' | wc -l                          → 43
```

That directory is precisely what CR-L16-01 measured as the cause of `git clone` failing on Windows
with `Filename too long`. **Deleting the unreferenced archive is not only the largest subtraction
available — it also fixes half of the fresh-clone blocker for free.** No sibling lens connected
these two facts.

---

## 1. The ranked subtraction ledger

Ranked by (lines removed × confidence) ÷ risk, with confidence Confirmed = 1.0 / Likely = 0.7, and
risk scored 1 (nothing references it) / 2 (one known reference to update) / 4 (a subsystem seam) /
8 (needs a human decision or a CI change first). Where two lenses proposed different actions, the
resolution is in §2 and the ledger carries the resolved verdict only.

| Rank | What | Lines removed | Files | Risk | What breaks | Verdict |
|---:|---|---:|---:|---|---|---|
| 1 | **Unreferenced `project-harness/archive/` markdown** — 177 files whose basename appears nowhere outside `archive/` and this review. Keeps the 38 that something still links, `ISSUES_RESOLVED.md` among them (CR-L11-07, DEC-130) | **17,699** | 177 | **1** | Nothing. By construction no tracked file names them; git retains the history, which is what git is for. Also removes the 43 over-100-char paths that break `git clone` on Windows (CR-L16-01) | **delete now** |
| 2 | **12 one-shot session prompts and handoffs** — `PROMPT_P25_*`, `PROMPT_P26_INTEGRATION`, `HANDOFF_TRACK_A/B`, `MORNING_HANDOFF_*`, `eval_roadmap_session_prompt`, `SEED_REPRODUCTION_..._BRIEF`, `OVERNIGHT_LOOP_PLAN`, `EVAL_P20_TO_P24_UNBLOCK_PLAN`. Each written in exactly one commit, never touched again (CR-L11-08) | **2,791** | 12 | **1** | Nothing. Keeps the 2 that `ROADMAP.md:3077,3452` links. Add `PROMPT_*`/`HANDOFF_*`/`MORNING_HANDOFF_*` to `.gitignore` so the next program does not mint five more | **delete now** |
| 3 | **Overnight-loop retirement, whole** — `expand_loop.sh` (681), `loop_clock.py`, `loop_compat.sh`, `loop.config.sh`, `loop_gates.py`, `classify_gate_failure.py`, `gate_baseline.py`, `gate_attribution.py`, `gate_confirm.py`, `scan_fix_diff.py`, `roadmap_cursor.py` + core (2,220); `OVERNIGHT_LOOP.md`, `OVERNIGHT_LOOP_PLAN.md`, `human_verification.md`, `soft_review.md`, `.claude/commands/expand-linear-next.md` (1,541); `test_loop_gates.py`, `test_roadmap_cursor.py` (720); `Run-OvernightCombined.ps1` (697) | **5,178** | 18 | **8** | `ROADMAP.md`'s `LOOP:QUEUE` fence grammar and every test asserting it; `make roadmap-verify`; `.claude/commands/expand-parallel.md`; `HUMAN_TASKS.md`. **Dead 13 days** (last log 2026-08-15 09:25). All 12 HALTs were the harness tripping over its own self-tests; 3 of 140 commits touched `src/` (CR-L11-03/09) | **delete after** a `DECISIONS.md` entry retiring the loop — or restart it against an engine roadmap and fix ISSUE-126 first. **The one thing that must not happen is a third month of carrying it undecided.** |
| 4 | **`CLAUDE.md` 476 → 248** — the dead contracts (`GraphUnavailableError`→503, `TokenBudgetExceededError`, `MistralAdapter`, "sole composition root"), the 3 decorative docstring fields, the 4 never-violated import rules, the Issues-log template (moved into `ISSUES.md`'s header, not lost), the 0-of-118 log-field mandate, and the 26 false claims corrected in place (CR-L05 subtraction proposal) | **228** | 1 | **2** | Nothing at runtime. **Highest leverage per line in the ledger**: ~2,600 tokens off every session's mandatory preamble, against ~1.0M tokens already spent on this file across 193 transcripts (CR-L05-09). Sequence the Issues-template move first so it is not dropped | **delete now** |
| 5 | **106 `*_delegates` / `*_opens_one_session` repository tests + the 105 passthrough bodies they guard** — the executed counterfactual is decisive: gutting 105 repository methods produced 66 failures, *every one inside the delegate tests themselves*; zero engine, API, scheduler or conformance test noticed the graph read layer had started returning nothing (CR-L14-02) | **~2,070** | ~30 | **8** | Nothing that runs today. **But this is a net loss unless `tests/integration` runs against a Dockerised Neo4j in `make check` first** — `pytest tests/integration -q` currently prints `9 passed, 34 skipped`, so the Cypher these repositories exist to reach is exercised by nothing in CI | **delete after** Neo4j is in CI and `tests/integration` stops skipping. Not before. |
| 6 | **Trend / regression stack** — `regression_gate` (188), `instrument_gate` (147), `baseline_selection` (199), `comparability` (97), `trend_store` (248), `trend_row_builder` (262), `record_trend_and_gate` (168). `wc -l evals/trend/trend_v1.jsonl` → **1**, and that row's `harness_version` (`f22f61a5d877`) no longer matches HEAD's (`21dcfa8dbc86`), so it is already incomparable (CR-L03-05) | **1,309** | 7 | **8** | `scripts/Run-EvalHarness.ps1` steps 7–8; `docs/REGRESSION_POLICY.md`; DEC-191/194/197. Six weeks, zero verdicts | **delete after** one decision: land two comparable runs *this program* or delete. CR-L03-09's single full-corpus generation produces the second row and settles it — do that first, then re-ask |
| 7 | **Sequence subsystem** — `evals/sequence_*.py` (808) + its 6 test files (906). `make eval-sequence` exists; **no committed artifact, no report, no trend field** has ever been produced. `docs/SEQUENCE_STATS_POLICY.md` (227) diverges on 7 of 18 normative claims, 3 of them describing behaviour that does not exist. The `case_seq_*` battery it consumes has zero files (CR-L03-12) | **1,714** (+227 doc) | 12 | **4** | `evals/__main__.py`'s `eval-sequence` verb, `scenario_adapters.py`, `world_map.py`, `reset_fidelity_record.py`, two `e2e/scripts/`. **Not the clean cut CR-L03-12 implies** — I traced the consumers; the reset-fidelity half is genuinely wired to e2e | **delete after** splitting `reset_fidelity` out and keeping it. Archive the rest with its policy doc |
| 8 | **mock/oracle labelling scaffolding** — `oracle_labeller` (281), `oracle_matrix` (201), `oracle_adjudicate` (140), `mock_labeller` (142), `mock_adjudicate` (136), `build_label_order` (141), `migrate_panel_judged` (207) | **1,248** | 7 | **4** | `make mock-calibrate`, `make mock-calibrate-oracle`, `tests/unit/evals/test_oracle_labeller.py`. **Partial defence CR-L11-02 misses**: the oracle-matrix path is the only mechanism that verifies the calibration arithmetic end to end (`Makefile:475` pins an expected κ of 0.247 to 3 dp). That is a real self-test of the instrument | **delete after** — take the mock-**random** half now (`mock_labeller`, `mock_adjudicate`, `build_label_order`, `migrate_panel_judged` = 626 lines, no such defence); **keep the oracle trio** (622) |
| 9 | **`check_engine_coverage.py` + `engine_coverage_contract.py` + their test** — a 44-unit classification taxonomy with **no `make` target**, no CI job, no verdict about behaviour, and whose own doc claim is contradicted in-code (`context_slots.py:146-147` says `active_quest` is "Pinned at 89 and never serialized" while `ENGINE_EVAL_COVERAGE.md` pins it for Rule 11) | **658** | 3 | **2** | `docs/ENGINE_EVAL_COVERAGE.md:3-4`, `docs/CAPABILITY_CASES.md:69` and `ROADMAP.md` advertise `make check-engine-coverage`; those 3 doc lines go with it | **delete now** — my half of the escalated L3/L11 conflict (§2, Conflict A) |
| 10 | **10 single-caller `engines/ports/` Protocols** — `TraitReadPort` (0 implementors, 1 caller, 1 method), `emotion_bootstrap_port`, `emotion_port`, `player_model_port`, `story_pacing_port`, `routine_port`, `faction_politics_port`, and the three `quest_port` protocols. Each re-declares one signature for one caller (CR-L14-03) | **~552** | 10 | **4** | `engines/ports/__init__.py` public surface, the composition root, `check_layers`' allow-list. Keeps the ports with real fan-in — `ClockPort` (16 callers), `WorldStateGraphPort` / `RelationReadPort` / `PlayerLocationReadPort` (6 each) | **delete after** the DIP rule in CLAUDE.md is rewritten to "a Protocol requires 2+ implementors or 3+ callers" — otherwise the next session correctly re-adds them, per the rule |
| 11 | **`live_openapi.json`** — 182 KB, tracked, last regenerated 2026-06-24, 128 paths against 132 live. **Zero** consumers in `*.py`, `*.yml`, `Makefile`, `*.sh`, `*.ps1`; markdown mentions only | **182 KB** | 1 | **1** | Nothing. If the artifact is wanted, CR-L12-07's version is the right one: regenerate in CI on every push, fail on an undocumented diff. A stale committed snapshot is worse than none — a partner studio doing API discovery gets a wrong contract with no generator to refresh it | **delete now** |
| 12 | **3 abandoned harness policy docs** — `EVAL_STRATEGY.md` (175, last touched 2026-05-28, an uncorrected duplicate of `docs/EVAL_METHODOLOGY.md` carrying 3 dead commands/paths — CR-L13-10), `SKILLS_QUEUE.md` (232, dead 90 days while `CLAUDE.md:306` still names it normatively — CR-L07-08), `BATCH5_RESPONSE_MODEL.md` (108) | **515** | 3 | **1** | `docs/SCORER_TRUST_POLICY.md:75` defers its minimum-n rule to `EVAL_STRATEGY.md`. That is not a reason to keep an abandoned file — it is the finding that **sample-size adequacy has no owner anywhere in the repo** (CR-L03 §3). Move the pointer, delete the file | **delete now** |
| 13 | **`engines/deception/` (140) + `engines/currency/` (12) + `test_deception_engine.py` (98)** — the only two of 39 `engines/` subpackages with zero external importers; `currency/` is an empty namespace whose `__init__.py` docstring still reads `Public surface: (list re-exports here)` | **250** | 6 | **1** | `docs/ENGINES.md`'s "~40 engines" count, which is the number a scope conversation starts from. `contracts/currency_engine.yaml` describes transfer behaviour that lives in `api/helpers/action_helpers.py` — repoint the contract, do not delete it | **delete now** |
| 14 | **15 `session_kwarg` tautology tests (~150) + 49 phantom `**_` docstring lines + 27 `tick_scheduler.py` docstring lines** — the SEV-24 migration removed `session=` from every tick engine; the tests and docstrings guarding it were not removed and still pass. Verified: `grep -rn "run_tick(session" tests/` → **0** (CR-L14-01) | **~200** | ~17 | **1** | Nothing at runtime. Not cosmetic: 22 engine docstrings and 27 scheduler lines currently tell the next author to write `run_tick(self, session, *, tick_id)`, which raises `TypeError` on its first tick and is then swallowed by `tick_scheduler.py:387`. **A live trap, removed by subtraction** | **delete now** |
| 15 | **7 dead `verify-v13` / `verify-v14-p0..p5` Makefile aggregates** — referenced by no CI job, no script, no `.claude/` command. Each is a strict subset of what `make check` already runs | **~14** | 1 | **1** | Nothing. Shrinks the 100-target `Makefile` surface that CR-L13 §3 had to audit doc-by-doc | **delete now** |
| 16 | **4 gate names out of `make check`** — `check-human-gates` (green with the feature it guards deleted), `check-test-quality` (`main()` returns 0 unconditionally), `check-conservation` + `check-label-survival` (both audit `k3_73e6c36`, one commit, unchanged since 2026-08-09). Scripts stay; only the `Makefile:200` names go (CR-L06-01/03/09) | **0 code**, 4 target names | 1 | **2** | The "14 green" count drops to 10, which is the point — 5 of 14 can print a problem and exit 0. `check-label-survival` prints *"New (unlabelled) rows: 528"* and exits 0 today | **delete now** from `make check`; re-invoke `check-conservation`/`check-label-survival` from `make eval-generate`, where a *new* artifact is the input |
| 17 | **`mutation_probe.py` (211) + `seed_reproduction_probe.py` (271)** — `make check-mutations` and `make seed-probe` exist; no commit in 967 cites either output. `seed_reproduction.json` records `NOT_MET` at 0.628 against a 0.95 gate, measured 2026-08-14 under `ollama_version 0.32.9` while the current run records `0.32.15` (CR-L03-11) | **482** | 2 | **2** | `make check-mutations`, `make seed-probe`. **A caveat that outranks half the deletion**: 0.628 reproduction means the 6.4 pp effects the regression gate is tuned for sit *inside* the noise floor. That probe is not waste — its result is being ignored | **delete now** `mutation_probe.py` (211); **keep and justify** `seed_reproduction_probe.py` — re-measure under the current runtime and record the model digest |
| 18 | **18 dead `keyword_none` expectation blocks + 3 `moderation_everyone_*` case files** — 50% of `keyword_none` expectations and 79.5% of individual keywords are guaranteed passes against the 975-response corpus. The moderation trio forbids `gore`, `torture`, `beheading` — words a fantasy-tavern NPC on `qwen2.5:7b` has never emitted (CR-L03-08) | **~171** | 3 files + 18 blocks | **2** | Every base-rate table in `docs/`. These are the mechanism behind the 1.000 null pass rate on the YAML guard set — i.e. **behind the CRITICAL** (CR-L03-01). Until they can fail, adding cases only raises Pe and lowers κ | **delete now** — pure subtraction that makes a broken instrument less broken |
| 19 | **`check_conservation` Identity 2** — `all_slots = compare_slots`, then `ok=(compare_slots == all_slots)`. Executed by CR-L06: deleting all 345 `judged.jsonl` rows still prints `Identity 2 [OK]: compare reads all 0 unique record_ids OK`. The tautology is pinned by `test_check_conservation.py:190-191` | **~30** | 2 | **2** | The printed report format and 2 test assertions. Note the shape: it was rewritten into `x == x` **by a commit labelled a bug fix** (`9c907a9`) | **delete now** unless someone restores the pre-`9c907a9` two-population computation; a green line that means nothing is worse than a missing one |
| 20 | **`scripts/migrations/add_faction_support.py`** — its sole `CREATE CONSTRAINT faction_id_unique` is now issued on every process startup by `schema_bootstrap.py:23-29` via `main.py:166` (since `6b91e4f`, 2026-06-04). `docs/API.md:492` and `docs/DATA_MODELS.md:653` still tell operators to run it (CR-L04-02) | **89** (+2 doc lines) | 1 | **1** | Nothing — nothing imports or calls it; it is only ever run by hand, per docs that are wrong | **delete now** |
| 21 | **12 constant-restating tests + 2 duplicated helper families** — `assert MAX_PLAYER_MESSAGE_CHARS == 1000`, `assert EMBED_DIMENSION == 384`, `assert KNOWLEDGE_STATE_KNOWS == "knows"` (CR-L14-06, ~120); byte-identical `_draw_no_data` across 4 `demo_game/ui/` panels (CR-L08-07, ~45); the third copy of the Neo4j→native converter with a **divergent** error path (CR-L14-05, ~30) | **~195** | ~9 | **1–2** | Nothing for the constant tests. The converter deletion is the valuable one: today the same driver value serialises as `str(value)` via `context_builder_helpers` and as the raw object via `graph_reader`, silently and with no log | **delete now** |
| 22 | **`TokenBudgetExceededError`** — `class TokenBudgetExceededError(Exception)` at `utils/errors.py:301`, a bare `Exception` violating the typed-hierarchy rule, referenced by nothing in `src/` and imported-but-unused by one test. CLAUDE.md and `docs/PROMPT_DESIGN.md:91` both promise `context_builder` raises it; the mechanism was deleted on 2026-06-11 by `45b781d` and the promise has stood for **78 days** through 5 edits of CLAUDE.md | **4** (+2 doc claims) | 1 | **1** | One unused test import. Tiny, and the cleanest illustration in the repo of a rule outliving its machinery | **delete now** — pair with row 4 |
| 23 | **71% of unchecked roadmap items** — 46 of 65 belong to the eval-harness meta-program; 8 of 8 active `## Active`/`## Program` headings are eval or harness; zero are product. `packaging/` took 1 file-touch in 200 commits and `make package` has **never** been buildable on any commit (CR-L12-01/02, CR-L02-07) | **0 code**, 46 backlog items | 0 | **8** | The whole roadmap. This is the row the other 22 exist to make room for | **delete after** one human decision: name an external integrator and a date, per CR-L12-06. Descoping without that just moves items to a side file — which is what `UNREAL_DEFERRED.md` already is |

---

## 2. Deduplication — the sibling conflicts, resolved

### Conflict A (escalated to a human by CR-L11): wire or delete `check_base_rate` + `check_engine_coverage` (810 lines)

**Neither lens is right, because the two scripts are different in kind. Split the conflict.**

- **`check_base_rate.py` + `base_rate_contract.py` (386 lines) — WIRE IT. CR-L03-04 wins.**
  This script measures the exact property that produced the review's second CRITICAL. Run today it
  prints `ALL n=975 rate=0.943 above_band` against its declared `[0.55, 0.85]` band, with 9 of 10
  families out of band and 4 flagged `<- CONSTANT: no variance to move`. That is the base-rate
  breach underneath CR-L03-01's "a fixed string scores 0.949, the engine scores 0.897". CR-L11's own
  catch table concedes the pattern: the two instruments that would have falsified the headline
  (`hedge_responder_probe`, `check_base_rate`) exist, are correct, and were pointed away from the
  number. **Deleting an instrument because nobody wired it is deleting the wrong end of the
  problem.** The wiring is a two-line `Makefile` edit; keep `advisory` mode until EVAL-P26, as
  `base_rate_contract.py:42` already specifies.
- **`check_engine_coverage.py` + `engine_coverage_contract.py` + test (658 lines) — DELETE IT.
  CR-L11-02 wins.** It classifies 44 units into a taxonomy. It produces no verdict about behaviour,
  its exit code has never gated anything, and its own governing doc is already contradicted in-code
  (`context_slots.py:146-147` vs `ENGINE_EVAL_COVERAGE.md`'s Rule 11 pin). A taxonomy no decision
  consumes is a 658-line comment.
- **Forcing function:** CR-L11's "this week" is the right instrument. If `check-base-rate` is not in
  the `Makefile` by the next commit that touches `evals/cases/`, it joins its sibling. A gate with
  no invocation has a shelf life and 17 days is most of it.

**One recommendation, not two: wire one, delete the other, this week.**

### Conflict B: CR-L11 and CR-L08 on archived markdown

CR-L08-05/06 correctly cautions that `project-harness/archive/` is "mostly-frozen-but-partly-live"
and that `ISSUES_RESOLVED.md` is canonical and actively appended. CR-L11-07 proposes deleting 175
files. **No real conflict once the population is measured precisely, which neither lens did.** L8's
"224 files" counts untracked review-evidence under a gitignored path; the tracked, deletable
population is **215**, of which the basename cross-reference finds **177 unreferenced (17,699
lines)** and **38 referenced (11,469 lines)** — and `ISSUES_RESOLVED.md` lands in the *referenced*
set automatically. **CR-L11's deletion wins; CR-L08's exception is already satisfied by the method.**

### Conflict C: CR-L03 and CR-L06 on `check_conservation` / `check_label_survival`

- CR-L03-07: *fix* them — repoint the hardcoded `_DEFAULT_GEN_DIR` at the newest generation, render
  the missing `excluded` term in Identity 1's arithmetically-false printed line.
- CR-L06-09: *remove both from `make check`*, invoke them from the eval-regeneration path, keep the
  scripts.

**Not actually in conflict — they answer different questions, and the order matters. CR-L06 wins on
placement, CR-L03 wins on the fix, in that sequence.** Doing CR-L03's repoint while the gates still
sit in `make check` converts two guaranteed-green lines into two lines that go red on stale data at
every commit, for a pre-flight check nobody asked for at commit time — `Makefile:173-175` says so
itself: *"Run before spending a regeneration or a labelling pass."* Move them out first; repoint as
part of wiring them into `make eval-generate`. CR-L06-02's separate finding — Identity 2 is `x == x`
— is additive and is ledger row 19.

### Conflict D: CR-L11-02 proposes deleting `scan_fix_diff.py` outright

**Corrected by verification. Its line count stands; its verdict does not.**
`scripts/expand_loop.sh:387` invokes it and `tests/unit/harness/test_loop_gates.py:26` imports it.
It cannot be deleted independently — it moves into the loop-retirement bundle (row 3). The same
correction applies to CR-L11-03's 525-line "tolerance layer" (`loop_gates.py`, `gate_baseline.py`,
`gate_confirm.py`, `classify_gate_failure.py`, `gate_attribution.py`): all five are `expand_loop.sh`
call sites. **The tolerance layer cannot be subtracted while the loop it serves is undecided. One
decision, one bundle.**

### Conflict E: CR-L03-12 treats the sequence subsystem as a clean 808-line cut

**Corrected.** Traced this session: `evals/__main__.py`, `evals/scenario_adapters.py`,
`evals/world_map.py`, `evals/reset_fidelity_record.py`, `e2e/scripts/measure_reset_fidelity.py` and
`e2e/scripts/reset_fidelity_markdown.py` all reference it. The reset-fidelity half is genuinely
wired to e2e and its measured artifact (`evals/reset_fidelity.json`) matches its doc row-for-row —
CR-L03's own §5 table marks `RESET_FIDELITY` as the one policy doc whose every measured number is
true. **Split it: keep reset-fidelity, archive the order-effect / sequence-rates half with its
policy doc.** Row 7 reflects the split.

### Conflict F: CR-L12 vs the implication of CR-L11's ratio framing on `demo_game/`

CR-L11 counts `demo_game/` (36,961 lines) as shipped product; CR-L12-08 found it is load-bearing for
the *eval* program. **CR-L12 wins outright** and it goes in §4, not the ledger.

### Conflict G: CR-L05's CLAUDE.md cut vs CR-L04's ISSUES.md read-mandate rewrite

Compatible, and they should land in one commit. CR-L05 moves the 38-line Issues-log template into
`ISSUES.md`'s own header; CR-L04-03 rewrites `CLAUDE.md:268` from *"Every session reads it"* (1,799
lines, ~35,346 tokens, ~2.5 h of linear reading) to *"grep `ISSUES.md` for the module you are about
to touch"*. Row 4 carries both.

---

## 3. Grand total

| Tier | Rows | Lines | Files |
|---|---|---:|---:|
| **(a) Zero-risk** — unreferenced artifacts; a `grep` proves nothing names them | 1, 2, 4, 11, 12, 13, 14, 15, 18, 20, 21, 22 | **~22,156** | ~208 |
| **(b) Low-risk** — dead code, unwired gates, one identified reference each to update | 9, 16, 17 (mutation probe), 19, mock-random half of 8 | **~1,525** | ~14 |
| **(c) Requires a decision** — whole subsystems, roadmap descoping, or a CI change first | 3, 5, 6, 7, oracle half of 8, 10, 23 | **~10,850** | ~74 |
| | | **~34,531 lines / ~296 files** | |

Plus **182 KB** of JSON with no consumer (row 11), **46 roadmap items** (row 23), and **4 target
names** out of `make check` (row 16).

Calibration, so the number is not read as bigger than it is:

- Tier (a) alone is **45% of `project-harness/`'s 48,988 markdown lines**, and removes ~2,600 tokens
  from every session's mandatory preamble.
- The full 34,531 is **16%** of the 214,008-line tree (107,323 machinery : 106,685 product,
  CR-L11 §1). It is **not** a fix for the 1.01:1 ratio. Executing every row moves it to roughly
  **0.78:1** — better, and still nowhere near a product-led repository.
- **32,461 of the 34,531 lines (94%) are process and measurement machinery.** Only ~2,070 lines
  (row 5) and ~552 (row 10) come out of `src/` or `tests/`, and both are gated on a prerequisite.
  **Subtraction alone does not make this a product again.** Row 23 does, and row 23 removes no lines
  at all.

---

## 4. The three things I would NOT delete

A subtraction lens that deletes everything is as useless as one that deletes nothing. These three
look like waste by the review's own metrics and are not.

### 1. `tests/` — the ~61,300 engine-facing lines, not the whole 80,324

CR-L11 correctly classes `tests/unit/{evals,scripts,harness}` + `tests/integration/evals` (18,984
lines, 23.6%) as machinery, and this ledger takes ~2,270 more out of the engine half (rows 5, 14,
21). What remains — roughly **61,300 lines / 4,048 tests in 333 s** — stays, and the argument is not
sentiment:

- CR-L15 §4 tested the coverage claim honestly and it survived: import-only inflation is **under
  ~2%** of the 87.86% headline. Among the 10 largest `src/` modules, **zero** show the
  high-percentage-never-called pattern. The one bad module (`intent_queries.py`, 34.6%) is
  *honestly low* — it drags the average down, not up.
- CR-L14's own executed counterfactual is the strongest evidence *for* keeping the engine tests:
  when a mismatched `run_tick` signature was injected, the thing that caught it was
  **`MilitaryEngine`'s own four unit tests** — not `BaseEngine`, not mypy, not any gate.
- It is the only mechanism in the tree with a demonstrated relationship to catching regressions
  before they ship, and it costs 333 s.

The critique that lands is CR-L15-01's, and it is a fix, not a deletion: ~169 s of "unit" tests make
real unmocked `httpx` calls to Ollama and the live API, so the coverage number is partly a property
of what infrastructure happened to be running. **Inject the fakes the file's own two mocked tests
already use.** S-effort, and it makes the suite worth more rather than smaller.

### 2. `demo_game/` — 36,961 lines, 8 file-touches in 200 commits, and not a subtraction candidate

It looks like the single largest dead weight in the repo: frozen since `e975215` (2026-06-13, 76
days), zero commits during the loop's entire life, and it is a **pygame** app while
`BUSINESS_REQUIREMENTS.md:21-22` names Unity and Unreal as the target clients. Delete it and the
harness:product ratio improves dramatically.

**Delete it and the eval program stops working.** CR-L12 §5 traced this and it is decisive:

- `Makefile:627` builds the eval baseline fixture `evals/fixtures/eval_world_baseline.json` by
  running `python -m demo_game.snapshot`.
- `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` always creates.
- `tests/unit/api/test_client_paths_phase2.py:17`, `test_interaction_phase1.py:25` and
  `tests/unit/config/test_seed_chain_quests.py:19` import from `demo_game` — and those run inside
  `make test-cov`, which **is** CI-gated.
- It runs today: `1116 passed in 9.28s`; `python -m demo_game.runners.run --dry-run` completes
  12 acts.

It was silently repurposed from sales demo into the eval program's world-fixture generator. It is
also the only working demonstration of the product that exists. The right action is the opposite of
subtraction: **CR-L12-08's 9-second `test-demo` addition to `make check`** — currently 36,961 lines
and 1,116 tests are verified by nobody, while `check-conservation` (1 s, tautological) and
`check-label-survival` (1 s, inert) are in the gate.

### 3. `check_layers` (192 lines) — and with it, `type` / `type-evals`

In a review whose headline is that the gate battery is theatre, the temptation is to cull the
battery. **The two or three gates that are not theatre are exactly what must survive the cull**, and
`check_layers` is the clearest:

- It is one of only two gates in `make check` that **passes a counterfactual**. CR-L06 §4 executed
  it: injecting `from npc_engine.api import routes` into a `graph/` file produces
  `layer violation: 'graph' (rank 2) imports 'api' (rank 6)`.
- It holds **2 of the 9 genuine catches in 967 commits** (`d24f442` at introduction, 3 upward
  imports; `a397661`, `relation_phase_writer` importing `engines`) — and they are the only two
  *architectural* catches in the entire record.
- It costs ~1 s and is one of the 6 gates CI actually runs.
- CR-L04 §5 independently found the resulting decomposition healthy: `graph/` and `engines/` medians
  of 103.5 and 86.5 lines, intra-package fan-out ≈1.35/file. That is what an enforced layer model
  buys.

The same defence covers the mypy gates: the 256→0 burn-down (`9ee2e73`) is real and is now a
permanent property of 627 files. Delete these along with the tautologies and the review will have
removed the only load-bearing thing it found.

**Coda — the probe set, the fourth thing, and the one I would grow.** CR-L11's own table contains
the argument: in 967 commits, **exactly one** mechanism ever caused a change to shipped runtime
behaviour, and it was `probe_context_ceiling.py` (`96d83eb`) — a probe written 15 days ago that **no
gate runs**. `hedge_responder_probe.py` produced the number the second CRITICAL rests on.
`evals/mde.py` is a module whose entire job is to tell you a planned experiment is pointless before
you spend ten hours on it. `evals/synthetic_label_guard.py` stops mock labels overwriting human
verdicts. `evals/judge_config.py:114-127` enforces judge≠generator at import with a typed exception.
That is ~1,200 lines with a 1-for-1 catch record, against a gate battery at 0-for-967 on behaviour.
**Probes measure the engine against reality; gates check file shape.** CR-L11-05's `make measure` is
the right move, and it is a rename, not a new mechanism.

---

## 5. The counterfactual: if this had shipped only `src/npc_engine/` + `tests/` + a thin README

**Honest answer: five things would be worse, all of them modest; two would be much better; and the
second of those is the whole ballgame.**

**Worse — what the harness genuinely bought:**

1. **The layer model would not exist as an enforced artifact.** `check_layers` caught 3 upward
   imports at introduction and 1 since. Without it, `engines`↔`graph` tangles the way every
   unenforced layer model does, and CR-L04's healthy decomposition would not be there. This is the
   single clearest thing the process paid for.
2. **mypy would not be at 0.** `9ee2e73` burned 256 → 0 and it has held across 627 files.
3. **`ISSUES.md` / `DECISIONS.md` / `ROADMAP.md` / `PATTERNS.md` / `CLAUDE.md` compound.** Five
   files, 13,493 lines, read every session (CR-L11 §6). A thin-README project re-derives decisions.
   Discount it, though: 53% of DECs are never cited outside `project-harness/`, and 4 of a sampled
   12 are stale or unimplemented (CR-L07-06).
4. **The eval vocabulary is genuinely unusual and would not exist.** Judge≠generator enforced at
   import; the harness detecting its own single-rater tautology and *refusing to print a number*;
   cluster-resampled bootstrap with a stated √k justification; unprompted FWER disclosure;
   `evals/mde.py`. CR-L03 — the most sceptical lens in this review — says so in writing.
5. **The token-budget defect would still be live** (`96d83eb`: budget 1,062 against three NPCs
   needing 995–1,151). **Half credit only** — it was found by a hand-run probe, not by the harness.
   A thin-README project with the same curious maintainer finds it the same afternoon.

**Better — and this is the part that decides the question:**

1. **Three of the four CRITICALs would still be here, and the fourth would not exist.** Gossip
   distortion is a no-op, a fixed string beats the engine on the guard battery, the documented
   Neo4j→503 contract has never existed — none was caught by 14 gates run on every phase for three
   months; all were found by direct inspection in hours. And the `GraphUnavailableError` family was
   **manufactured by process**: CLAUDE.md mandates "document the fallback in the docstring",
   `check-docstrings` verifies a docstring is *present* and is content-blind (`"""Layer: banana"""`
   → 0 findings), so four files now carry compliant docstrings asserting a contract no code
   implements (CR-L11-06). A thin-README project has one fewer defect of that class, not more.
2. **There would be an integrator, and therefore a product.** CR-L12-06 names the mechanism and it
   is not rhetorical: 967 commits, one author, zero external contributors, and a tree-wide grep for
   `design partner|pilot|licensee|LOI` returning nothing outside in-game dialogue about bribing a
   gate guard. With no external clock, "done" is defined by the harness — and the harness is the
   thing being built. The evidence that this actually happened: the entire game-client program was
   moved into a side file on 2026-07-31 and has had **zero commits since**; 8 of 8 active roadmap
   programs are eval or harness; `packaging/` took 1 file-touch in 200 commits; `make package` has
   **never been buildable on any commit**, because the spec's `datas` entries named two paths that
   did not exist on the day it was written; and there are 0 lines of C# or C++ for the two named
   target clients.

**The trade, stated plainly.** The harness bought a good architecture boundary, a clean type tree,
and a genuinely sophisticated measurement vocabulary — for roughly a third of the project's lifetime
authorship and **81% of every commit since 2026-08-01**. It did not catch the defects it was built
to catch; it manufactured one; and its largest single effect was to supply a substitute definition
of "done" that let the product go 28 days without a roadmap entry while the instrument measuring it
got sharper every week.

A thin-README version of this project would have a worse architecture, no eval science, and a
shipping demo. Measured against what a game studio would pay for, **the trade went the wrong way** —
and it is still going, because rows 1–22 remove 34,531 lines without changing it. Only row 23 does.

---

## Findings

### [CR-L09-01] Delete the 177 unreferenced archive files — it is the largest subtraction available and it also fixes the Windows clone blocker

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git ls-files project-harness/archive | grep '\.md$' | wc -l` → **215 files / 29,168 lines**. A basename cross-reference of each against every tracked `.md/.py/.yaml/.txt/.ps1/.sh/.json/.toml` file outside `archive/` and `review-2026-08/` returns **177 unreferenced (17,699 lines)** and 38 referenced (11,469), with `ISSUES_RESOLVED.md` correctly in the referenced set. Larger than CR-L11-07's 175/16,724. Separately and not connected by any sibling lens: `git ls-files | awk '{print length($0), $0}' | sort -rn | head -10` returns ten paths all under `project-harness/archive/2026-06-18-shipped-programs/expansion/briefs/` (67 files), and `git ls-files | awk 'length($0)>100' | wc -l` → **43** — exactly the paths CR-L16-01 measured as making `git clone` fail on Windows with `Filename too long`.
- **Cost of inaction:** Every `git grep` at session start returns hits from 29,168 lines of superseded prose, and 60% of the markdown that makes `project-harness/` look like the largest thing in the repo is material nothing reads. Meanwhile every new Windows contributor or evaluator hits a dead stop at step zero, and the fix (`git config core.longpaths true`) is documented nowhere in the tree.
- **Fix sketch:** Delete the 177 unreferenced files in one commit, keeping the 38 that something links. Re-run the cross-reference at deletion time including `review-2026-08/` in the exclusion set, since this review cites archived files by name.
- **Effort:** S
- **Removes:** ~17,699 lines / 177 files
- **Blast radius:** None found by construction; verify once more at deletion time. Requires human approval per CLAUDE.md's "deleting a file you did not create" rule.

### [CR-L09-02] Resolve the escalated gate conflict by splitting it: wire `check-base-rate`, delete `check-engine-coverage`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CR-L03-04 proposes wiring both `make` targets (810 lines); CR-L11-02 proposes deleting both unless wired this week, and escalated the disagreement for a human. Verified: `for t in check-base-rate check-engine-coverage review-cases check-variance variance-score; do grep -qE "^$t:" Makefile ...` → all five **MISSING**. The two scripts are not equivalent. `check_base_rate.py` run today prints `ALL n=975 rate=0.943 above_band` against its declared `[0.55, 0.85]` band with 4 families flagged `<- CONSTANT: no variance to move` — the measurement directly underneath CR-L03-01's CRITICAL. `check_engine_coverage.py` produces a 44-unit classification table whose own governing doc is already contradicted in-code (`retrieval/context/context_slots.py:146-147` says `active_quest` is "Pinned at 89 and never serialized" while `docs/ENGINE_EVAL_COVERAGE.md` pins it for Rule 11). Both carry live test files (227 and 234 lines) that run inside `make test-cov`, so neither is unexecuted — only unconsumed.
- **Cost of inaction:** The 0.943 base-rate breach stays invisible while the branch it sits on (`eval-ab-context-arms`) runs A/B arms against it, and 658 lines of taxonomy accrue maintenance under the 300-line, docstring and layer rules for a verdict nobody reads. Both costs compound with every case file added.
- **Fix sketch:** Add `check-base-rate:` to the `Makefile` in advisory mode (2 lines; flip to blocking after EVAL-P26 as `base_rate_contract.py:42` specifies). Delete `scripts/check_engine_coverage.py`, `scripts/engine_coverage_contract.py`, `tests/unit/scripts/test_check_engine_coverage.py` and the 3 doc lines advertising the target.
- **Effort:** S
- **Removes:** ~658 lines / 3 files; adds 2 Makefile lines
- **Blast radius:** `docs/ENGINE_EVAL_COVERAGE.md:3-4`, `docs/CAPABILITY_CASES.md:69`, `ROADMAP.md`. Expect `check-base-rate` to print an out-of-band result on its first run — that is the point.

### [CR-L09-03] Decide the overnight loop's status — 5,178 lines have been carried for 13 days with no owner

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Measured this session: scripts 2,220 lines (`expand_loop.sh` 681, `_roadmap_cursor_core.py` 311, `roadmap_cursor.py` 187, `gate_baseline.py` 169, `loop_compat.sh` 161, `loop_clock.py` 147, `loop_gates.py` 135, `scan_fix_diff.py` 120, `loop.config.sh` 88, `gate_attribution.py` 74, `gate_confirm.py` 74, `classify_gate_failure.py` 73), docs 1,541 (`human_verification.md` 574, `OVERNIGHT_LOOP_PLAN.md` 384, `soft_review.md` 305, `expand-linear-next.md` 170, `OVERNIGHT_LOOP.md` 108), tests 720, plus `Run-OvernightCombined.ps1` 697 — **5,178 lines / 18 files**. CR-L11-09: last loop log 2026-08-15 09:25, 13 days ago; ISSUE-126 (`--dry-run` never terminates) open 26 days at `ISSUES.md:709`. CR-L11-03: all 12 `CLASSIFICATION=HALT` entries name one of 5 harness self-tests; **no node-id under `tests/unit/{engines,graph,retrieval,api}` appears anywhere in `human_verification.md`**. CR-L11-04: `grep -rn "soft_review"` outside `OVERNIGHT_LOOP.md:63` and the loop's own scripts returns nothing — ~60 findings read by nobody, one of which is still open as CR-L03-02.
- **Cost of inaction:** The bundle is not separable — I verified that `scan_fix_diff.py` and the whole 525-line tolerance layer are `expand_loop.sh` call sites, so CR-L11-02/03's individual deletions cannot execute independently. Carrying it undecided costs maintenance on 5,178 lines under the 300-line, docstring and layer rules for a system whose documented dry-run mode still hangs, and whose recorded precedent (2 of 2 confirmed regressions committed anyway, `human_verification.md:262,270`) says its safety layer would not stop a real one.
- **Fix sketch:** Write one `DECISIONS.md` entry: retired, or restarted against an engine-work roadmap. If retired, delete all 18 files together and strip the `LOOP:QUEUE` fence grammar from `ROADMAP.md`. If restarted, fix ISSUE-126 first (a ~3-line change marking the task in the dry-run path) and prove `gate_confirm` by injecting a deliberate `src/` regression.
- **Effort:** S (fix ISSUE-126) / M (the retirement decision and its execution)
- **Removes:** ~5,178 lines / 18 files, if retired
- **Blast radius:** `ROADMAP.md`'s `LOOP:QUEUE` fence and the `roadmap_cursor` tests asserting it, `make roadmap-verify`, `.claude/commands/expand-parallel.md`, `HUMAN_TASKS.md`.

### [CR-L09-04] Cut `CLAUDE.md` 476 → 248 — it is the highest-leverage line-for-line subtraction in the repo

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -l project-harness/CLAUDE.md` → **476**, auto-loaded into every session. CR-L05 checked 109 claims in it: **26 FALSE, 6 unverifiable**, and **22 of 28 rules marked (strict) are enforced by nothing**. Three describe machinery that has never existed: `git log -S "raise GraphUnavailableError" -- src/` → **0 commits, ever**; `TokenBudgetExceededError`'s raise site was deleted by `45b781d` on 2026-06-11 and the rule has stood for 78 days through 5 subsequent edits of this file; `MistralAdapter` has never appeared in a `.py` file in 967 commits. The measured proof that sessions have already stopped believing it is CR-L05-03: on the two docstring fields a gate checks, compliance is **100%/100%**; on the three it does not, **65%/66%/28%** — and the *ungated* `demo_game/` tree scores **81%** on the full 5-field format, higher than the gated one.
- **Cost of inaction:** ~5,197 tokens per session, ~1.0M spent on this file to date across 193 transcripts, buying a rule set that is 22/28 unenforced and 26 claims that are false. The file has grown 346 → 476 lines across 14 commits with **zero lines ever removed**, and its one dated self-correction (`:57`) drifted stale in 17 days.
- **Fix sketch:** Execute CR-L05's subtraction proposal — delete the Documentation section down to the 2 fields the gate checks, the 4 never-violated import rules, the dead contracts, the 0-of-118 log-field mandate; move the Issues-log template into `ISSUES.md`'s header rather than losing it; correct the 26 false claims in place; and apply CR-L04-03's rewrite of `:268` from "Every session reads it" to a grep instruction.
- **Effort:** M
- **Removes:** 228 lines (~10,400 chars, ~2,600 tokens/session)
- **Blast radius:** The Issues-log template must land in `ISSUES.md`, not be dropped. Nothing else references `CLAUDE.md` by line number. This is a deliberate act on the file that says "these rules are not suggestions" and should carry its own `DECISIONS.md` entry.

### [CR-L09-05] Delete the 12 one-shot session prompts and `.gitignore` the pattern before the next program mints five more

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `git ls-files project-harness | grep -E "(PROMPT_|HANDOFF_|MORNING_HANDOFF|_PLAN\.md|session_prompt)"` returns **14 files / 3,463 lines**, matching CR-L11-08 exactly. `grep -n` against `ROADMAP.md` shows it links exactly **2** of them (`PROMPT_P23_UNBLOCK.md` at `:3077`, `EVAL_P25_TO_P31_PLAN.md` at `:3452,3510,3542,3605`), leaving **12 files / 2,791 lines** whose task is finished and which nothing names. `EVAL_P20_TO_P24_UNBLOCK_PLAN.md` (367) is *not* linked despite CR-L11-08 assuming both plan docs were. The growth rate is ~5 per program: EVAL-P25..P31 produced 5 in `d46ae42`+`b9717ef` alone, two days ago.
- **Cost of inaction:** They are mined by `git grep` as if they were current policy — the exact mechanism behind CR-L04-02's two docs still telling operators to run a script dead since 2026-06-04. An untracked fifteenth (`PROMPT_CODEBASE_REVIEW_2026-08.md`) is the only one currently outside git, and it is the one actually being used — which is the right pattern, accidentally.
- **Fix sketch:** Add `project-harness/PROMPT_*.md`, `HANDOFF_*.md`, `MORNING_HANDOFF_*.md` to `.gitignore`, delete the 12 tracked files, and fold anything from `EVAL_P20_TO_P24_UNBLOCK_PLAN.md` still live into `ROADMAP.md`, which is the file people read.
- **Effort:** S
- **Removes:** 2,791 lines / 12 files
- **Blast radius:** Check `DECISIONS.md` cross-links before deleting; `ROADMAP.md`'s 5 references are all to the 2 files being kept.

### [CR-L09-06] Delete the 15 `session_kwarg` tests and 76 phantom docstring lines — they are a live trap, not cosmetic debt

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `grep -rn "def test.*session_kwarg" tests/ --include=*.py | wc -l` → **15**; `grep -rn "run_tick(session" tests/ --include=*.py | wc -l` → **0**. Every one of the 15 passes because it never passes `session=` — the `**_` they were written to guard was removed by the SEV-24 migration. CR-L14-01 additionally counts **22 engine `run_tick` docstrings documenting a `**_` parameter with 0 matching `**kwargs` in any signature**, and 27 lines in `scheduler/tick_scheduler.py` promising `run_tick(session, tick_id)` against `grep -rn "async def run_tick" -A2 src/npc_engine/engines/ | grep -c session` → **0**.
- **Cost of inaction:** This is not stale prose. The next person to add a tick engine reads `tick_scheduler.py:96-134` and 22 engine docstrings, all stating the scheduler passes a session, and writes `run_tick(self, session, *, tick_id)`. The scheduler calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`), so that engine raises `TypeError` on its first real tick — and `BaseEngine`'s `(*args, **kwargs)` annotation will not catch it (CR-L14-04, executed: mypy stays clean with an incompatible engine wired in), while `_run_distributed_interval` swallows the `TypeError` at `:387` so the engine silently never runs. That is CR-L01-03's memory-consolidation failure mode, pre-loaded for the next author.
- **Fix sketch:** Delete the 15 tests; strip the `**_:` lines from the 22 `Args:` blocks; rewrite the 27 `tick_scheduler.py` parameter docstrings to the real `run_tick(*, tick_id)` contract. Pair with CR-L14-07's one-line addition to `docstring_audit.py` — "an `Args:` entry must name a parameter that exists in the signature" — which would have caught all 22.
- **Effort:** S
- **Removes:** ~200 lines across ~17 files
- **Blast radius:** Docstrings and tests only; no runtime behaviour changes.

### [CR-L09-07] Do not subtract `demo_game/` — gate it instead; it is the eval program's fixture generator

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `demo_game/` is 36,961 lines with 8 file-touches in 200 commits, last feature commit `e975215` on 2026-06-13, and it is pygame while `BUSINESS_REQUIREMENTS.md:21-22` names Unity and Unreal — every metric in this review marks it as the largest deletion candidate in the tree. CR-L12 §5 establishes it is load-bearing for the *eval* program instead: `Makefile:627` builds `evals/fixtures/eval_world_baseline.json` from `python -m demo_game.snapshot`; `evals/anti_hallucination_runner.py:30` depends on the player id `demo_game.seed` creates; and `tests/unit/api/test_client_paths_phase2.py:17`, `test_interaction_phase1.py:25`, `tests/unit/config/test_seed_chain_quests.py:19` import it inside CI-gated `make test-cov`. It runs: `1116 passed in 9.28s`. Yet `grep -c "test-demo\|demo_game\|package" .github/workflows/ci.yml` → **0** and `make check` (`Makefile:200`) omits `test-demo`.
- **Cost of inaction:** 36,961 lines whose failure mode is silent. A `demo_game` regression breaks the eval baseline fixture and three CI-gated unit tests, and the first symptom is an unexplained eval number rather than a red demo test. The likeliest trigger is the `chore: restore the line endings my own edits rewrote` class of sweep-up commit, which already accounts for half of `demo_game`'s recent churn. Meanwhile `check-conservation` (1 s, tautological) and `check-label-survival` (1 s, inert) *are* in the gate.
- **Fix sketch:** Add `test-demo` to `make check` and to the CI test job — 9.25 s against a 595 s baseline, and all 1,116 tests pass today. If `demo_game` is genuinely not worth gating, then move `snapshot.py`, `client.py`, `dialogue.py` and `seeds/` into a small `fixtures/` package that *is* gated, and let the pygame UI rot honestly — but do not delete it while the eval baseline depends on it.
- **Effort:** S (CI) / M (the extraction)
- **Removes:** 0 lines — this is a deliberate non-deletion
- **Blast radius:** `.github/workflows/ci.yml`, `Makefile:200`; `make check` +9 s.

---

## 6. Needs a human decision (not an engineering task)

1. **Conflict A's forcing function** — wire `check-base-rate` this week or delete it (§2, CR-L09-02).
2. **The overnight loop: retired or restarted?** 5,178 lines, dead 13 days, ISSUE-126 open 26 days.
   Row 3 cannot execute without this answer, and CR-L11-02/03's individual deletions are blocked
   behind it.
3. **The trend stack: one more generation, or delete?** CR-L03-09's single full-corpus run over all
   92 cases produces the second comparable row *and* the capability number the battery is missing.
   Do that run before deciding row 6.
4. **Row 23 — name an external integrator and a date.** Every other row in this ledger is
   housekeeping. This one is the review.
5. **Deletion approval.** Per CLAUDE.md, deleting a file you did not create requires human approval.
   Rows 1, 2, 11, 12, 13 and 20 are where that bites hardest — ~200 files, all verified
   unreferenced, none created by this session.

## Pre-merge checklist

- [x] Read-only — no source file created, edited or deleted; this evidence file is the only write
- [x] Every **delete now** row re-verified this session with a pasted or summarised command
- [x] Three sibling claims **corrected** by verification (archive count up; `scan_fix_diff` not
      standalone; sequence subsystem not isolated) rather than repeated
- [x] All seven cross-lens conflicts resolved to **one** recommendation each, including the one
      CR-L11 escalated for a human
- [x] No fifth CRITICAL added — the four are spent
- [x] Grand total split three ways, with the calibration stating what it does *not* fix
- [x] Three defended non-deletions, each with the evidence that defends them
- [x] No `ISSUES.md` entries filed — this is a read-only lens; the orchestrator owns backlog creation
