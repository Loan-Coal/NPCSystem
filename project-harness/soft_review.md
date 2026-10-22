
## 2026-10-21 20:54:43 — phase T21

## Review of T21 Phase Commits

**Findings:**

1. **Regex anchoring inconsistency** — `TASK_FROZEN_RE` in `expand_loop.sh:120` ends with `\.claude/settings` (no anchor), which matches `.claude/settings_backup` or other prefix-matched files unintentionally. Paths like `scripts/(...)$` and `\.claude/commands/expand-linear-next\.md$` are end-anchored; settings should be too: `\.claude/settings($|/)` to avoid false positives.

2. **Test coverage gap** — `test_expand_loop_frozen_paths.py` has three cases (frozen hit, allowed path, history rewrite) but no case testing both frozen-path write AND history rewrite simultaneously. The code handles this (`reason="$reason; frozen paths: $hits"`) but it's untested.

3. **Docstring accuracy** — Function comment in `expand_loop.sh:643` says "resets HEAD to `<before_sha>`" but also calls `git clean -fd`, which removes untracked files. The reset behavior should clarify both operations.

4. **Edge case in history detection** — If a task rewrites history to an ancestor commit that still contains a frozen-path modification, the check will correctly flag it. However, the order of operations (baseline-drift check before frozen-path check) means an intermediate state could exist. Ordering is correct as-is, but worth noting.

5. **No validation of `TASK_FROZEN_RE` syntax** — The regex string is complex and unvalidated at script load time. A syntax error in the pattern would silently fail (grep returns nothing), possibly allowing unintended writes. Consider adding a test that validates the regex parses correctly.

All other code follows CLAUDE.md rules: functions <40 lines, proper nesting, module/function docstrings present, no layer violations. LOC baseline updated correctly.

## 2026-10-21 23:12:44 — phase T22

Now let me get the five concrete findings by reviewing the full diff carefully:

**Findings Summary:**

1. **HARNESS_GATES.md gate removal**: The "Contracts" row (`make check-contracts` / `check-contract-sync`) was removed from the documented harness gates table, but the Makefile targets still exist (lines 181-182). This creates inconsistency: either the gate should remain documented (if still enforced) or the targets should be deleted. Currently, the documentation claims these checks don't exist as gates.

2. **Git subprocess error handling gap in _is_tracked()**: The `_is_tracked()` function (check_ledger_ids.py:164-172) uses `subprocess.run(..., check=False)` and only checks `returncode == 0`. This conflates "file not in index" (exit 1) with "git not available" (exit 127), potentially causing false positives for missing reports when git fails.

3. **Archive DECISIONS.md inclusion changes collision semantics**: Adding "archive/DECISIONS_history.md" to _DECISION_FILES means DEC ids in the archive are now treated as "declared" for collision detection. If someone accidentally creates DEC-150 when it exists in the archive, it flags correctly. But the docstring doesn't explain this behavior—it only mentions detecting "undocumented" collisions, not what "documented" means with an archive present.

4. **Test tripwire deletion lost design documentation**: The 150+ line `test_real_roadmap_fence_state_tripwire()` function in test_roadmap_cursor.py was deleted. While the simpler replacement test is functionally correct, the docstring contained extensive historical context about past issues (ISSUE-134, ISSUE-136, DEC-153, DEC-160, DEC-178, DEC-233, DEC-252) and design rationale that is now inaccessible from the code.

5. **Type ratchet gate changed from baseline to hard fail**: HARNESS_GATES.md changed the Types gate from "baseline ratchet" (`make type-ratchet` allows errors up to baseline) to "hard fail" (`make type` requires 0 errors). The Makefile was updated to remove the `type-ratchet` target itself, but this is a significant behavioral change (stricter enforcement) that could break builds if mypy errors exist. This should be marked as a major gate strengthening in the commit message or ROADMAP.

## 2026-10-22 01:31:30 — phase T23

Reading the T23 commits (T23.1 through T23.4), focusing on correctness, edge cases, and CLAUDE.md rule violations:

**1. Missing test for `main(--npc)` dispatch logic (CLAUDE.md: "Every public function gets a happy-path test and a failure test")**
   - `main()` is public but tests call `chat_repl()` directly, bypassing the argparse branching. The `--npc` argument path is untested.

**2. No exception handling in `chat_repl()` loop**
   - If `dialogue_ws_worker()` or `_print_reply()` raises, the REPL crashes instead of catching and continuing to the next stdin line. REPL should tolerate transient failures.

**3. Silent failure in `_print_reply()` if queue never receives "done" event**
   - If the queue is empty (no "done" pushed by worker), the function returns without output. User sees nothing. Should either warn or wait with a timeout.

**4. Missing test for error case in `_print_reply()`**
   - The `elif kind == "error"` branch is untested. No test verifies that an error on the queue is raised.

**5. LOC baseline updated but no regression test**
   - `scripts/loc_baseline.txt` changed from 121188 → 107737 (−13,451, within spec), but the "Rule 1 — Reverse LOC ratchet" gate (`make check-loc-ratchet`) isn't mentioned as passing. Verify `make check` is green before merge.

## 2026-10-22 03:31:11 — phase T24

**Review of T24 diff - 5 concrete findings:**

1. **[CRITICAL] Unused DemoRunner instance in pillars.py:main()** — Lines 458-462 create a `runner` that's never run. The code then calls `_run_demo_with_recorder()` which creates a *different* `DemoRunner` inside a thread, and the original `runner` remains uninitialized. Subsequent calls to `_make_pillar_reads(runner.client, recorder)` use a client that was never set up. Either pass the runner to `_run_demo_with_recorder()` or capture it from the thread.

2. **[MODERATE] Misleading docstring in _write_verdicts()** — Says "Append verdicts as JSONL" but uses `open("w")` which overwrites. Should say "Write verdicts as JSONL" or document the overwrite behavior.

3. **[MODERATE] FEEL pillar falsely passes edge case** — In green_facts.jsonl, the third emotion read has both valence=0 and arousal=0, yet still counts as non-neutral due to the condition `valence != 0 or arousal != 0`. A read with valence=-0.5 and arousal=0 would also pass, which may not represent actual emotion change. Consider requiring *both* to be non-zero or using an absolute magnitude threshold.

4. **[LOW] Defensive fallback in check_gossip never exercises** — Pattern `body.get("data", body)` assumes body might lack a "data" key, but all fixtures have `{"data": {...}}` structure. Dead defensive code; either assert the structure or document why the fallback exists.

5. **[INFO] Committed red baseline hides backend issues (ISSUE-379, ISSUE-380)** — The pillar verdicts are intentionally red (acknowledging interaction_count and seeds_used are broken), but the code doesn't validate this is *expected*. A future operator might misread red verdicts as a test failure rather than a documented known issue.
