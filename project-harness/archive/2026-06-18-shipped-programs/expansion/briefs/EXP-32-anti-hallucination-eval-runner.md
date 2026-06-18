# EXP-32 — Anti-hallucination eval runner + `make eval-anti-hallucination`

**Goal / rationale:** The labeled fixture `evals/cases/anti_hallucination_demo.json`
(41 cases, 5 NPCs, 3 categories: should_know / should_refuse / adversarial_cross_npc) was
created in the previous session (2026-06-10). This first slice wires it to a runner and
adds a `make eval-anti-hallucination` target so the suite can be run headlessly in CI.

**Business intent:** Demonstrate measurable anti-hallucination guarantees (grounded / refusal
accuracy, hallucination count = 0) as a headline metric for the demo pitch.

---

## First slice — scope

Wire the JSON fixture to a dedicated runner:
1. Load `evals/cases/anti_hallucination_demo.json`
2. For each case, call `POST /v1/dialogue` (skip if NPC not found — world not seeded)
3. Classify response against `expected_verdict`:
   - **grounded**: PASS if response contains ≥1 of `expected_fact_substrings` (keyword_any)
   - **refusal**: PASS if response contains ≥1 refusal indicator (see constant list below)
4. Aggregate: per-category totals + hallucination_count (refusal case where NPC asserted without basis)
5. Print a human-readable summary; exit 0 on all-pass, exit 1 on any failure.

**Refusal indicator constant** (`_REFUSAL_KEYWORDS`):
```python
_REFUSAL_KEYWORDS: tuple[str, ...] = (
    "don't know", "do not know", "haven't heard", "have not heard",
    "not sure", "not certain", "no idea", "can't say", "cannot say",
    "wouldn't know", "would not know", "doubt", "uncertain",
    "haven't come across", "haven't seen", "unaware",
)
```
A response is a correct refusal if `any(kw in response.lower() for kw in _REFUSAL_KEYWORDS)`.
A response is a hallucination if `expected_verdict == "refusal"` AND the response is
non-empty AND NOT a correct refusal (NPC asserted something without basis).

---

## Current state

- `evals/cases/anti_hallucination_demo.json` — 41 labeled cases, schema documented in file header.
  First non-comment object has keys: `id`, `world`, `npc_id`, `question`, `expected_verdict`,
  `knowledge_basis`, `expected_fact_substrings`, `category`.
- `evals/runner.py` — existing runner; loads `*.yaml` cases only. Does NOT load JSON.
  Reuse the httpx client pattern, `_run_case` structure, and `write_report` from this file.
- `evals/matchers.py` — `keyword_any`, `keyword_none`, `tone_judge`, `affirms_judge`.
  Do NOT call into `matchers.evaluate()` from the new runner — keep the new runner
  self-contained so it can be run independently of the YAML runner.
- `Makefile:138-144` — existing `eval` target pattern to clone for new target.

## Files to create / edit

### New files

- **`evals/anti_hallucination_runner.py`** — standalone runner (see design below)
- **`tests/unit/test_anti_hallucination_runner.py`** — unit tests (no HTTP, mock httpx)

### Edited files

- **`Makefile`** — add `eval-anti-hallucination` target (after line 148 `eval-report:`)

---

## Runner design (`evals/anti_hallucination_runner.py`)

```python
"""
Module: anti_hallucination_runner
Layer: evals (eval harness — not part of src/)
Purpose: Run evals/cases/anti_hallucination_demo.json against the live engine
         and report grounded/refusal/hallucination metrics.
Dependencies: httpx, json, pathlib, argparse, sys
Used by: Makefile eval-anti-hallucination target, CI
Does NOT: import from src/npc_engine/, call LLM judges, modify graph state
"""
```

Key public surface:
- `run(base_url, api_key, fixture_path, report_dir) -> int` — main entry, returns exit code
- `AntiHallucinationSummary` — Pydantic BaseModel with fields:
  `total: int`, `grounded_total: int`, `grounded_passed: int`,
  `refusal_total: int`, `refusal_passed: int`, `hallucination_count: int`,
  `over_refusal_count: int` (grounded case where NPC failed to surface the fact)
- `format_summary(summary: AntiHallucinationSummary) -> list[str]` — human-readable lines

**Do NOT exceed 300 lines.** The runner has no LLM judge calls — keep it simple.

## Makefile target

```makefile
eval-anti-hallucination:
	@echo "Running anti-hallucination eval against $(BASE_URL) ..."
	$(PYTHON) evals/anti_hallucination_runner.py \
		--base-url $(BASE_URL) \
		--api-key $(API_KEY) \
		--fixture evals/cases/anti_hallucination_demo.json \
		--reports evals/reports
```

Add to the `.PHONY` line and after `eval-report:`.

---

## Test plan

Write `tests/unit/test_anti_hallucination_runner.py` FIRST. The tests must NOT make
HTTP calls — mock `httpx.Client` via `unittest.mock.patch`.

Key test cases:
1. `grounded` case: response contains expected substring → PASS, `grounded_passed += 1`
2. `grounded` case: response missing all substrings → FAIL, `over_refusal_count += 1`
3. `refusal` case: response contains "don't know" → PASS, `refusal_passed += 1`
4. `refusal` case: response contains no refusal keyword + non-empty → FAIL, `hallucination_count += 1`
5. NPC not found (404) → case skipped, counts unaffected
6. `format_summary` with known counts → correct line output

```bash
pytest tests/unit/test_anti_hallucination_runner.py -q   # must fail first, then pass
```

## Done when

- `pytest tests/unit/test_anti_hallucination_runner.py` passes (all 6+ cases)
- `make eval-anti-hallucination` runs without error against a seeded demo world
  (or prints "NPC not found — skip" for each case if world not seeded, exit 0)
- Summary output includes `grounded: N/M correct`, `refusal: N/M correct`, `hallucinations: K`
- `make check` (lint + type) is green

## Effort: M  |  Value: high (demo metric)  |  First slice: complete
