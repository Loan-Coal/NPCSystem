# FIX-SEV-01 — Make the anti-hallucination guarantee real (CRITICAL)

**Severity:** CRITICAL · **Confidence:** Confirmed (live `make eval` = 27/31; `make scenarios` fails 2 guard cases) · **Effort:** M
**Category:** test-gap / prompt-quality · **Absorbs:** PROMPT-04, PROMPT-09, TEST-01, TEST-02, TEST-04
**Depends on:** none (do first — it is the product moat). **Blocks:** SEV-27 (output reliability proof).

## Problem
The Phase-11 headline ("0 lore hallucinations across N adversarial turns") is satisfiable by an empty response, the canned fallback line, a synonym-worded hallucination, or an out-of-character refusal. The eval correctness logic is itself untested and outside coverage. The live `make eval` already shows real leaks (27/31), and `make scenarios` fails `case_adv_leading_betrayal` + `case_neg_old_henryk_no_eyewitness_claim`.

## Current shape (verify by opening)
- All 23 guard cases `evals/cases/case_adv_*.yaml` + `case_neg_*.yaml` assert only `- kind: schema` and `- kind: keyword_none`.
- `evals/matchers.py:117-129` `_eval_schema`: `missing = [f for f in required_fields if _get_nested(resp, f) is None]` → empty string `npc_response: ""` is **not** `None`, so it passes.
- `evals/matchers.py:152-159` `_eval_keyword_none`: `found = [kw for kw in keywords if kw in text]` → `[]` on empty text → passes.
- `evals/summary.py:55-61` `headline`: prints "0 lore hallucinations across {guard_turns} adversarial turns"; `guard_turns = sum(1 for r in guard_results if not _is_skipped_case(r))` → 0 when all skip. `tests/unit/test_eval_summary.py:59-68` encodes this.
- `evals/matchers.py` + `evals/runner.py` have **zero** tests; coverage runs `--cov=npc_engine` so `evals/` is uncovered.
- Fallback that passes every blocklist: `llm_client.py:127` → `"I need a moment to think."`

## Target shape
A guard case PASSES only when the NPC actively, in-character, refuses/hedges the false premise **and** the response is substantive. The headline cannot be vacuously green. The matchers are tested.

## Steps
1. **New matcher `min_length`** in `evals/matchers.py`: fail if `npc_response` trimmed length `< MIN_GUARD_RESPONSE_CHARS` (e.g. 20). Add to every guard case.
2. **Harden `_eval_schema`**: treat empty/whitespace `npc_response` as a failure (not just `None`).
3. **Positive assertion per guard case**: add a `tone_judge` with a rubric requiring BOTH "does not confirm/repeat the false premise" AND "stays in character and engages (hedges, e.g. 'I heard…', 'they say…', or declines plausibly)". Optionally a `keyword_any` of hedging markers. This fails a generic refusal and a mute fallback alike.
4. **Detect the fallback**: add `"I need a moment to think"` (and other `fallback_responses.json` lines) to a `keyword_none` so the canned line FAILS guard cases.
5. **Non-vacuous headline** in `evals/summary.py`: when `guard_turns == 0`, emit `NO GUARD TURNS EVALUATED — guarantee not demonstrated` and make `runner.main` exit non-zero. Update `test_eval_summary.py` to assert this.
6. **Test the matchers**: new `tests/unit/test_eval_matchers.py` covering each matcher kind — happy + failure + edge (empty text, missing field, `None` numeric, unicode keyword, judge timeout via monkeypatched `httpx.post`). Add `--cov=evals` (or move matchers under a covered package) to the coverage invocation in the `Makefile`.
7. Distinguish judge-infra error from content fail (see SEV-38) so a fully-skipped LLM run cannot print a pass.

## Verification
- Stub a backend returning `""` and one returning the fallback line → run `evals/runner.py` → every guard case FAILS.
- `pytest tests/unit/test_eval_matchers.py` green; `make eval` denominator is never 0; a known-hallucinated response fed through `evaluate()` FAILS.
- Regression test: feed an over-refusing stub ("Move along.") → guard case FAILS (positive assertion).

## Notes
This is the single highest-value fix: until it lands, every "0 hallucinations" claim is unsupported and the live numbers (27/31, 2 scenario fails) contradict it.
