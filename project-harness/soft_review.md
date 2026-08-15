
## 2026-08-05 14:16:46 — phase EVAL-P0

**5 findings from EVAL-P0.2 diff:**

1. **Import path mismatch in engine_adapter.py** — Line 31 imports from `npc_engine.retrieval.embedding`, but retrieval_runner.py originally imported from `npc_engine.retrieval.embedding_index` and `npc_engine.retrieval.vector_store_factory` (two separate modules). Verify these new consolidated import paths actually exist in npc_engine; if the real modules haven't been refactored, this will fail at runtime.

2. **test_src_free.py guard checks wrong filenames** — Line 104 asserts files `retrieval_runner.py`, `runner.py`, and `matchers.py` exist. But:
   - retrieval_runner.py imports from `retrieval_matchers`, not `matchers.py`
   - `runner.py` isn't created by this task and likely doesn't exist
   
   Guard test will fail when run unless these files match expectations.

3. **Type hints collapse to `Any`** — `build_retrieval_stack() → tuple[Any, Any]` and `known_event_ids(..., session: Any)` are correctly generic to avoid importing npc_engine types, but callers have no type guidance on what's returned or what session type is accepted. Consider TypeVar or forward refs to preserve some contract.

4. **No input validation** — `known_event_ids(session, npc_id)` passes both directly to npc_engine without checking session is a Neo4j AsyncSession or npc_id is a valid node ID. Boundary validation at the adapter's entry point would fail fast.

5. **Unsafe dict access in retrieval_runner** — Line 103 does `ranked: list[str] = [r["id"] for r in vector_results]` without guarding that each result dict contains "id". If embedding index changes its response schema, this raises KeyError silently until runtime.

## 2026-08-06 13:55:08 — phase EVAL-P1

Now reviewing the EVAL-P1.4 / EVAL-P1.3 / EVAL-P1.1 diffs. Here are my findings:

## Concrete Findings

1. **Module docstring missing** in `evals/context_capture.py:1-40`. Adds a new module `context_capture` that doesn't follow the standard module-docstring pattern (should have `Module:`, `Layer:`, `Purpose:`, `Dependencies:`, `Used by:` fields per CLAUDE.md §Documentation). The file has a partial docstring but doesn't conform to the strict format.

2. **Exception handling overly broad** in `evals/context_capture.py:183`. `except Exception: return ()` silently swallows all errors (network timeouts, malformed JSON, etc.) when capturing retrieval context. Should catch specific exceptions (httpx.HTTPError, json.JSONDecodeError) and log failures, per CLAUDE.md §Error handling "never swallow errors."

3. **Immutability violation** in `evals/generate_runner.py:525-526`. Uses `.model_copy(update={...})` to patch fields on GenerationRecords during the k-repeat loop. This is correct, but the pattern chains multiple `update` calls on the same record — should verify no in-place mutation happens in nested context_capture calls.

4. **TranscriptVersionError exception not used** in tests. The new `TranscriptVersionError` is defined in `evals/eval_records.py:250-264` but there's no integration test confirming `read_transcript()` actually raises it when version mismatches occur (v1 → v2). Schema version enforcement works, but error path is untested.

5. **Project-rule violation: Makefile output directory change is silent**. `eval-generate` switched default `--out` from `e2e/transcripts/` to `evals/generations/` without updating downstream consumers. Judge pass still reads from legacy location by default — coupling risk if eval-generate output path diverges. Should verify judge_runner defaults match or add explicit path coordination in CI recipes.

## 2026-08-06 23:52:52 — phase EVAL-P3

**EVAL-P3 Diff Review: 5 Findings**

1. **CLI can't score knowledge meaningfully** — `deterministic_pass.py:237` hardcodes `npc_known_events={}`, so the CLI always reports 100% knowledge_rate (assuming event mentions). The main() function has no parameter to supply NPC known-events, limiting real-world CLI use to entity scoring only. Documented limitations should be in the module docstring, not buried in the score_transcript() params.

2. **Redundant denominator field** — `summary.py:127-128` introduces `evaluated_cases` (total_cases - skipped_cases) then immediately sets `total_turns = evaluated_cases`, making the two fields identical. While this clarifies intent, the docstring at line 49 should explain why both fields exist instead of just renaming total_turns.

3. **API response format assumption** — `graph_vocabulary.py:100` assumes the JSON response has a `"data"` key without validation: `resp.json()["data"]`. If the endpoint returns unexpected structure, this raises an uncaught KeyError. No docstring states the expected response schema.

4. **Missing entity-rate edge case test** — All alias tests use known entities. No test covers a scenario where an entity mention has no alias in the table at all (e.g., an NPC name spoken for the first time). This is documented as "out of scope" but should have an explicit test confirming zero mentions for unaliased text.

5. **Knowledge scorer false-positive risk not tested** — `knowledge_scorer.py:18-22` warns that beliefs/goals/memories aren't in npc_known_event_ids, causing false violations. No test verifies this edge case or documents which knowledge sources ARE included. The docstring should reference a test that demonstrates the risk.

**All tests pass.** No file exceeds 300 lines. Module docstrings present.

## 2026-08-07 00:57:53 — phase EVAL-P4

## Findings (EVAL-P4 commits)

**1. Layer not defined (CLAUDE.md violation)**  
Module docstrings declare `Layer: evals (evaluation harness)`, but evals is not in CLAUDE.md's official layer model (which lists: api, auth, data, engines, scheduler, services, cache, retrieval, graph, mutation, world, config, common, type_registry, schema, utils). Either add evals to CLAUDE.md or reassign files to data/.

**2. Precision computed but unused**  
retrieval_join.py:126 computes `precision_at_k`, but only `recall` determines `retrieval_hit` (line 129). Precision is exposed in `PerRecordResult` but never used. Design choice is undocumented.

**3. RECALL_HIT_THRESHOLD=0.0 not tested for value**  
Threshold set to 0.0 means any recall > 0 is a hit. Tests validate boundary cases (0 vs >0) but not the threshold value itself. If threshold changes, no test catches it.

**4. record_id format not validated**  
`_case_id_from_record_id()` assumes format `<case_id>:<judge_kind>:<index>` but doesn't validate. Malformed record_ids (e.g., no colon) silently produce incorrect case_id values.

**5. Hard-coded case count in regression test**  
`test_guard_case_total_is_37()` requires manual update whenever cases are added/deleted, making it brittle despite being intentional.

## 2026-08-07 17:34:02 — phase EVAL-P1

Looking at EVAL-P1.6 (persist judge pass verdicts), here are 5 concrete findings:

**1. Missing path validation for --json-out** — `main()` validates `--transcript` exists upfront but skips validation for `--json-out`. If the parent directory can't be created (permission, path issues), file I/O fails deep in `_write_judged_jsonl()` with a generic exception instead of a clear error message. Should check write-ability early or catch and report clearly (inconsistent with line 234-235 error handling for transcript).

**2. Unexplained rsplit magic in case_id extraction** — Line in `_write_judged_jsonl()`:
```python
"case_id": r.record_id.rsplit(":", _RECORD_ID_COLON_SEGMENTS)[0],
```
The constant `_RECORD_ID_COLON_SEGMENTS=2` extracts the prefix correctly but lacks a comment explaining why this works. The name `_RECORD_ID_COLON_SEGMENTS` is ambiguous (could mean segment count, not rsplit maxsplit). One-line comment needed per CLAUDE.md rule.

**3. Test gap: nested directory creation untested** — `test_json_out_writes_one_row_per_judged_record()` writes to `tmp_path / "judged.jsonl"` (single level), never testing `mkdir(parents=True, exist_ok=True)` on deeply nested paths like `tmp_path / "a/b/c/judged.jsonl"`.

**4. No test for write failures** — Test suite doesn't cover permission errors, disk full, or path-is-a-file scenarios when calling `_write_judged_jsonl()`. If `path.write_text()` fails, the exception propagates uncaught, crashing the judge run.

**5. Inconsistent encoding constant usage in tests** — `test_judged_records.py` hardcodes `encoding="utf-8"` instead of using the module-level `_JSONL_ENCODING` constant. Test should import and use the same constant.

## 2026-08-08 09:06:46 — phase EVAL-P5

## Code Review: EVAL-P5.6 Batch Export + Import

**5 findings (ordered by severity):**

1. **File size violation** — `label_import.py` is 309 lines, exceeds the 300-line hard limit in CLAUDE.md. Must split before merge. Consider extracting index builders (`_build_transcript_index`, `_build_judged_index`) into a separate `label_import_io.py` module.

2. **Missing defensive check for judged_index lookup** (label_import.py:461) — `scorer_verdict: bool = judged_index[record_id]` can crash with bare `KeyError` if `record_id` exists in transcript but not in judged. Should use `.get()` or raise a domain error like `UnknownRecordIdError`. Current error message would be opaque.

3. **No test for mismatched indices** — Test suite covers unknown record_id in transcript, but not the reverse case: record_id in transcript that's missing from judged_index. Add a test to ensure this raises a clear validation error, not a bare KeyError.

4. **Missing JSON key validation in index builders** (label_import.py:514, 533) — If a JSONL line lacks `"record_id"`, both `_build_transcript_index` and `_build_judged_index` crash with bare `KeyError` instead of a validation error. Wrap in try/except to provide context (e.g., "Line X of Y missing 'record_id'").

5. **Vocabulary path existence check could fail silently** (label_export.py:293–294) — If `args.vocabulary` is provided but file doesn't exist, the check `if args.vocabulary.exists()` silently leaves `vocab_dict = None`. Should raise an error instead of silently skipping, since user explicitly specified a path.

**Pre-merge checklist:** Fix (1) and (2); add test for (3); add validation for (4). Item (5) is lower priority but recommended.

## 2026-08-08 10:07:04 — phase EVAL-P7

**FINDINGS (EVAL-P7.1/P7.2/P7.3):**

1. **Async/sync mismatch (HIGH)**: `run_list()`, `run_detail()`, and `case_detail()` in app.py are declared `async def` but perform only blocking sync I/O (`.read_text()`, `.glob()`, JSON parsing). FastAPI will not error but this wastes thread resources. Either change routes to `def` (sync) or delegate I/O to a thread pool via `asyncio.to_thread()`.

2. **Edge case: integer coercion on missing field**: In `app.py:239` and `app.py:153/194`, code does `int(r.get("repetition", 0))` without validation. If `repetition` is `None` or a non-numeric string, this raises. Should validate at parse time or use safer coercion (e.g., `int(r.get("repetition") or 0)`).

3. **Redundant template loading**: `_load_template()` is called once per request (3 routes), re-reading disk each time. Should cache template objects at module init to avoid I/O on every request.

4. **Missing docstring on detail._compute_kappa_parts()**: Private function with a complex calculation (Cohen's kappa). Should document what each variable (tp/fp/fn/tn/pe) represents for maintainability.

5. **Division-by-zero potential**: `run_detail()` at line 245 computes `passes / total` without checking if `total == 0` first (already handled), but `_compute_kappa_parts()` at line 199 assumes `abs(1.0 - pe) > 1e-12` to avoid division by zero — good safeguard, but undocumented. Add a comment.

**Summary**: Code is solid overall (good module structure, proper docstrings, 80%+ test coverage). Three concrete fixes: (1) convert sync routes or use thread pools, (2) validate integer conversions, (3) cache templates.

## 2026-08-08 10:41:32 — phase EVAL-P8

Reviewing the EVAL-P8 diff for `compare.py` and tests:

## Findings

1. **Missing import path verification:** `compare.py` imports from `case_stats` and `paired_stats` (lines 25-26) as if they're in the same directory/package, but the diff shows only `evals/__main__.py` being modified to add the `compare` subcommand. Need to verify these modules exist in `evals/` and are importable — the imports will fail at runtime if they're elsewhere.

2. **Silent malformed-line skipping (line 133-134):** `_read_judged_rows()` catches all exceptions and silently passes, including JSON decode errors. This hides data corruption. A single corrupted line means that case's stat becomes incomplete, yet `compare_runs()` reports the intersection size without flagging the silent data loss. Recommend logging skipped lines or raising on structural corruption.

3. **Majority-vote threshold edge case (line 202):** `before.passes * 2 > before.k` fails when k=0 (empty run). A run with zero rows produces zero CaseStat objects → empty `before_map`, but the logic doesn't guard against division by zero in `pass_rate()` or undefined pass rates. Empty runs should either be rejected upfront or produce a warning in the report.

4. **Test doesn't verify `paired_result` type:** Line 101-104 check `paired_result.p_value`, `verdict`, `improved`, `regressed`, but the actual `PairedResult` model/interface is not shown in the diff. If `PairedResult` is from `paired_stats.py` (not in this diff), there's no contract visible that guarantees these fields exist. The tests pass by assumption.

5. **Overlong case_id column truncation:** Line 323 formats case_id with `<50` width. If a record_id is longer (e.g., nested UUID:judge_type:repetition strings), it silently truncates in output. No guard or ellipsis (e.g., `<50.47`) to signal truncation. Edge case but silent data loss in human output.

**Pre-merge checklist status:**  
- ✅ Tests present (5 happy-path + 1 empty run test)  
- ⚠️ Import paths unverified  
- ⚠️ Silent error skipping  
- ⚠️ No guard for k=0 runs  
- ⚠️ PairedResult contract not shown in diff

## 2026-08-08 11:55:34 — phase EVAL-P9

## Review Summary: EVAL-P9 Commits

**5 Findings:**

1. **File size violation (CRITICAL)** — `evals/case_drafts.py` is **359 lines**, exceeds CLAUDE.md hard limit of 300. Extract protocol/models/helpers to a separate module or split into sub-modules.

2. **Function length violation (HIGH)** — `main()` in `case_drafts.py` (lines 290–358) is ~69 lines, exceeds CLAUDE.md strict limit of 40. Break into `_parse_args()` and `_run_generation()`.

3. **Code duplication** — `_GUARD_PREFIXES` and `_CAPABILITY_PREFIX` duplicated in both `summary.py` and `case_stats.py` with "mirrored to avoid circular import" comment. Extract to shared `batteries.py` or `_constants.py` instead.

4. **Incomplete test coverage** — `classify_battery()` (case_stats.py) has only one test (`test_unclassifiable_case_raises`). Missing positive tests for `"guard"` and `"capability"` classifications.

5. **Unclear Protocol contract** — `HttpClient` protocol (case_drafts.py:56) defines only `.get()`, but code depends on response having `.raise_for_status()` and `.json()`. Either document response interface or use `TypeVar` + response type parameter.

**Tests pass; logic is sound.** Violations are structural (size/nesting) and maintainability (duplication), not functional.

## 2026-08-09 23:18:48 — phase EVAL-P11

## EVAL-P11.1 Review: Scorer Trust Policy

### Findings

**1. Import path issue in test**  
`tests/unit/evals/test_trust_policy.py` line 13 uses bare `from scorer_trust_policy import ...`. This will only work if tests are run with `evals/` in the path. Should be `from evals.scorer_trust_policy import ...` to match the module's documented location.

**2. Premature "Used by" reference**  
Module docstring claims `scorer_trust_policy.py` is "Used by: evals/report.py" but no such caller exists in the diff or repo. Remove the reference or add it when `report.py` actually calls the function.

**3. Missing interval validation**  
`check_publication()` accepts `interval: tuple[float, float]` but doesn't validate that `interval[0] <= kappa <= interval[1]`. If the caller passes a mismatched interval, no error is raised. Consider adding a guard if interval correctness matters to policy enforcement.

**4. Boundary test approx precision**  
`test_refusal_names_scorer_kappa_and_interval()` checks `"0.10" in text or "0.1" in text` to validate interval bounds appear in the string. The current `PolicyRefusal.__str__()` uses Python's default float formatting, which will output `0.1` not `0.10`. Test passes by accident. Clarify intent or use f-string formatting if exact decimal places matter.

**5. Policy enforcement gap**  
Documentation states "Report generators **must** call `check_publication`" and "Bypassing it is a policy violation" but there's no code-level enforcement — a caller can still import `kappa` directly and format it without calling the function. Consider adding a `@dataclass` decorator or module-level guard if this is a security boundary.

✅ Tests pass, layer rules observed, docstrings complete, immutability enforced. Core logic is correct.

## 2026-08-10 10:07:22 — phase EVAL-P13

Now I'll generate my review findings:

## Findings on EVAL-P13.1 (metrics branch)

**Commit:** 04e2b33 — EVAL-P13.1 methodology writeup  
**Files changed:** docs/EVAL_METHODOLOGY.md (+251), project-harness/ROADMAP.md (+2/-2)

### 1. **Misleading claim about McNemar formula (line 79)**
The formula uses `2^n` (written as `2^n` in the doc), but modern Python implementations use bitwise operations or exponentiation. The actual formula in `paired_stats.py:mcnemar_exact()` uses `math.pow(2, n)`, not bitshift. Minor, but the pseudocode notation differs from how it ships.

### 2. **Trust policy table renders inconsistently (line 184–191)**
The methodology documents κ range `0.40 – 0.60` using an en-dash in the table, but the actual implementation and docstring in `scorer_trust_policy.py` (line 74) use `0.40 <= kappa < 0.60`. The bound *should* be less-than on the upper end (not ≤), but the markdown table uses a visual range that could be misread as inclusive on both ends. The code is correct; the table formatting is ambiguous.

### 3. **Missing docstring reference link (line 72)**
The methodology claims "McNemar chi-squared approximation is only reliable when discordant pairs exceed 25", citing a "rule of thumb" without a reference. This is standard literature, but nowhere in `paired_stats.py` or its test is this threshold documented or cited — only verified empirically in `test_mcnemar_exact_matches_worked_example`. No *hard* edge case, but the methodology claims something untraceable to the code.

### 4. **Judge model name changed post-documentation (line 231)**
The anti-metric section names `mixtral:8x7b` as the default judge model. Check: does `judge_config.py` actually ship with this as default, or has it drifted? This is a data claim about current state that rots if judge_config changes without updating the doc.

### 5. **`evaluated_cases` definition uses informal notation (line 132)**
The doc writes `evaluated_cases = total_cases - skipped_cases` in pseudocode, but the actual line in `summary.py` is a Pydantic computed field or property. Readers looking for the implementation may misread the *location* as the code itself rather than a docstring; worth clarifying "this formula is implemented via" rather than assigning.

---

**Assessment:** Documentation is thorough and cross-linked correctly to existing shipping code. No correctness failures, but 2–3 ambiguities in presentation and 1 data claim that requires periodic re-verification (judge model). All cited tests pass.

## 2026-08-10 10:35:57 — phase EVAL-P14

API Error: Connection closed mid-response. The response above may be incomplete.

## 2026-08-12 00:46:44 — phase EVAL-P16

**Finding 1: Boundary CI `is_boundary_ci` logic may be too loose with 1e-9 epsilon**

In `paired_stats.py:73`, the boundary check uses `_BOUNDARY_CI_EPSILON = 1e-9`. For κ values that cluster near 1.0 (perfect agreement), consecutive bootstrap percentiles could round within 1e-9 of each other by floating-point accident. Test `test_bootstrap_resamples_cases_not_rows` expects the CI to cover κ=0 at n_clusters=4, but if the bootstrap fails to generate variance and returns [0.999999999, 1.0], the interval would be misclassified as "at boundary" rather than genuinely wide. **Verdict: Latent edge case** — unlikely with 2000 resamples, but not impossible with fewer.

**Finding 2: `_pick_rate_str` silent fallback on None battery_rate masks data quality**

In `summary.py:166-173`, when `battery_rate is None`, the function silently falls back to simple Wilson CI calculated from `passes/turns`. But `BatteryRate` can be None only when `_group_results_by_case` returns an empty dict (line 207-209 in `battery_rates.py`). This occurs when all result dicts are skipped *or* the battery is empty. The fallback **never logs or warns** that design-effect correction was unavailable, so a report showing "17/20 (85%)" could mean either "20 non-repeated cases" or "Rao-Scott failed silently." **Verdict: Missing observability** — not a correctness bug but a reporting blind spot.

**Finding 3: McNemar test rejects *all* concordant pairs without explanation in PairedResult.verdict**

In `paired_stats.py:212-228`, when `improved + regressed == 0`, the function returns `verdict="no_detectable_change"` with `p_value=1.0`. However, this covers two distinct situations: (a) all matched pairs stayed passing, and (b) all matched pairs stayed failing. The verdict "no_detectable_change" conflates regression-evasion (the run is worse but all regressions are in the discard pile) with stability. Test `test_paired_compare_all_concordant_returns_p1` at line 232 confirms this is intentional, but it means the string verdict alone cannot distinguish "no change + all cases improved" from "no change + all cases regressed." **Verdict: Verdict ambiguity** — not a bug if the caller inspects the full result, but the Literal type should document this fusion.

**Finding 4: UndefinedKappaError.__init__ should freeze its attributes**

`calibration.py:142-151`: The exception stores `pe`, `tp`, `fp`, `fn`, `tn` as instance attributes but does not make them read-only. A caller could mutate `err.tp = 999` after catching. **Verdict: Violates immutability rule** (common/coding-style.md) — should use `@dataclass(frozen=True)` or slots-based exception with properties.

**Finding 5: `_extract_case_clusters` uses `dict.setdefault` but does not preserve insertion order across Python versions**

`calibration.py:298-304`: The function uses `dict.fromkeys(groups.values())` to preserve first-occurrence order, but `groups` is built via `setdefault`, which relies on dict insertion-order guarantee (Python 3.7+). The code is correct for modern Python but the comment only says "Preserves insertion order of first occurrence" without naming the version contract. The test `test_bootstrap_resamples_cases_not_rows` assumes stable ordering; if the code ever ran on Python 3.6 it would silently produce different cluster orderings and hence different bootstrap intervals. **Verdict: Undocumented version contract** — not a bug in this project but fragile.

---

**Summary:** 5 findings (1 latent edge case, 1 observability gap, 1 verdict ambiguity, 1 immutability violation, 1 undocumented version dependency). Most are low-severity but the immutability violation (Finding 4) is a rules violation per CLAUDE.md §Coding principles.

## 2026-08-12 02:45:53 — phase EVAL-P17

**EVAL-P17 Diff Review**

Looking at EVAL-P17.6 commits (ea47583 through de3aa28), here are 5 concrete findings:

1. **Unconventional test imports** (style inconsistency): New tests at lines 195 and 203 import `main` locally inside functions with `# noqa: E402` suppression. All existing tests in the file (`format_report`, `check_conservation`) import at module level. Should consolidate at module top for consistency.

2. **Misleading test docstring** (documentation): `test_violation_exits_nonzero()` (line 193) promises "exits 0 on a clean fixture" but only verifies the non-zero exit; the clean-fixture case is tested by the *next* function. Docstring should focus on this test's scope only.

3. **Return value is count, not boolean** (potential confusion): `check_conservation.py:287–289` returns the count of failing identities (0–3), not a standard 0/1 exit code. While this works correctly in make (any non-zero fails), it's unconventional and could confuse shell script consumers. Correct for this gate, but worth documenting.

4. **Gate placement correctness** ✓: `check-conservation` is correctly positioned in `Makefile:186` in the validation-gate chain (after rules/type checks, before coverage), consistent with gate-ordering convention.

5. **Identity 4 deferral documented correctly** ✓: Code only sums identities 1–3 in the exit code (intentional); docstring and comments correctly reflect the deferral. No missed edge case.

**Summary:** No correctness bugs. Style and documentation issues are minor.

## 2026-08-15 09:27:40 — phase EVAL-P13

Reviewing EVAL-P13.2 (dashboard headline card). Found **3 concrete issues**:

---

## Findings

**1. CRITICAL — Broken imports in `headline.py` (lines 19-21)**  
```python
from calibration import UndefinedKappaError, _kappa_from_matrix
from rate_stats import wilson_interval
from scorer_trust_policy import check_publication
```
These are bare module names. `app.py` uses absolute imports (`from evals.dashboard.detail import ...`). These should be:
```python
from evals.calibration import UndefinedKappaError, _kappa_from_matrix
from evals.rate_stats import wilson_interval
from evals.scorer_trust_policy import check_publication
```
Will fail at runtime with `ModuleNotFoundError`.

---

**2. MEDIUM — Private API import (`headline.py` line 20)**  
`_kappa_from_matrix` has a leading underscore (private). Importing private functions creates brittleness. Either import the public API or duplicate the logic into `headline.py` if it's genuinely independent.

---

**3. MEDIUM — Missing validation in `_rate_html()` (lines 128–134)**  
No check that `0 <= passes <= total` before calling `wilson_interval()`. If data is corrupted (e.g., `passes > total`), `wilson_interval()` may return nonsense or crash silently. Add:
```python
if not (0 <= passes <= total):
    return _NA_RATE
```

---

**Other notes:**  
- File length (191 lines) ✅ within 300-line limit.  
- Module/function docstrings present ✅.  
- Layer compliance ✅ (evals layer, no LLM calls).  
- Tests look structurally sound; both fixtures and assertions are clear.
