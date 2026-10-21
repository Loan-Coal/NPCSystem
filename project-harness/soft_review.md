
## 2026-10-21 20:54:43 — phase T21

## Review of T21 Phase Commits

**Findings:**

1. **Regex anchoring inconsistency** — `TASK_FROZEN_RE` in `expand_loop.sh:120` ends with `\.claude/settings` (no anchor), which matches `.claude/settings_backup` or other prefix-matched files unintentionally. Paths like `scripts/(...)$` and `\.claude/commands/expand-linear-next\.md$` are end-anchored; settings should be too: `\.claude/settings($|/)` to avoid false positives.

2. **Test coverage gap** — `test_expand_loop_frozen_paths.py` has three cases (frozen hit, allowed path, history rewrite) but no case testing both frozen-path write AND history rewrite simultaneously. The code handles this (`reason="$reason; frozen paths: $hits"`) but it's untested.

3. **Docstring accuracy** — Function comment in `expand_loop.sh:643` says "resets HEAD to `<before_sha>`" but also calls `git clean -fd`, which removes untracked files. The reset behavior should clarify both operations.

4. **Edge case in history detection** — If a task rewrites history to an ancestor commit that still contains a frozen-path modification, the check will correctly flag it. However, the order of operations (baseline-drift check before frozen-path check) means an intermediate state could exist. Ordering is correct as-is, but worth noting.

5. **No validation of `TASK_FROZEN_RE` syntax** — The regex string is complex and unvalidated at script load time. A syntax error in the pattern would silently fail (grep returns nothing), possibly allowing unintended writes. Consider adding a test that validates the regex parses correctly.

All other code follows CLAUDE.md rules: functions <40 lines, proper nesting, module/function docstrings present, no layer violations. LOC baseline updated correctly.
