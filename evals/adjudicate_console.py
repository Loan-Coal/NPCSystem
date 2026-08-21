"""
Module: adjudicate_console
Layer: evals (eval harness — not part of src/)
Purpose: The console presentation and input-parsing half of the adjudication CLI —
         how one calibration row is displayed to a human, and how their keystroke is
         read back as a canonical command. Split out of adjudicate.py, which exceeded
         the 300-line cap; that module keeps the adjudication FLOW (which rows are
         pending, applying a verdict, persisting) and imports these.
Dependencies: typing (Callable); calibration_records (CalibrationLabel)
Used by: adjudicate (run_adjudication)
Does NOT: read or write the labels file — persistence belongs to adjudicate
"""

from __future__ import annotations

from typing import Callable

from calibration_records import CalibrationLabel

# Accepted single-letter forms. 'n' (not 'f') is fail, because 'f' already means
# flip on a row that has a pre_label.
SHORTCUTS: dict[str, str] = {
    "k": "keep",
    "f": "flip",
    "p": "pass",
    "n": "fail",
    "s": "skip",
}


def _format_row_prompt(row: CalibrationLabel, index: int, total: int) -> str:
    """Return a formatted display string for one adjudication row.

    Shows criteria and, when present, player_message and observed — without
    these an adjudicator judging an in_set/range/schema row cannot see the
    response field the scorer actually inspects, since that field is absent
    from output_text entirely.
    """
    lines = [f"\n[{index}/{total}] scorer={row.scorer}  record_id={row.record_id}"]
    if row.needs_review and row.prior_human_verdict is not None:
        prior_str = "PASS" if row.prior_human_verdict else "FAIL"
        lines.append(
            f"⚠ DRIFTED: content changed since last adjudication "
            f"(prior human verdict: {prior_str})"
        )
    if row.player_message:
        lines.append(f"player_message:\n  {row.player_message}")
    lines.append(f"criteria:\n  {row.criteria or '(none recorded)'}")
    if row.pre_label is None:
        lines.append("pre_label : none (cleared on drift — no current reference opinion)")
    else:
        label_str = "PASS" if row.pre_label else "FAIL"
        lines.append(f"pre_label : {label_str}")
    lines.append(f"output_text:\n  {row.output_text}")
    if row.observed:
        lines.append(f"observed:\n  {row.observed}")
    lines.append("")
    if row.pre_label is None:
        lines.append("  pass(p) / fail(n) / skip(s): ")
    else:
        lines.append("  keep(k) / flip(f) / skip(s): ")
    return "\n".join(lines)


def _read_command(
    read_line: Callable[[], str],
    print_fn: Callable[[str], None],
    *,
    has_pre_label: bool = True,
) -> str:
    """Read a valid adjudication command, looping until valid input received.

    The accepted command set depends on whether the row has a pre_label:
    'keep'/'flip' compare against it and are only offered when it is set;
    'pass'/'fail' are the direct-verdict commands for a row whose pre_label
    was cleared to None on drift (EVAL-P20.3a / ISSUE-153). 'skip' is always
    accepted. Restricting the accepted set here (rather than relying on
    apply_verdict's ValueError) keeps a mismatched command a re-prompt, not a
    crash, mid-session.

    Args:
        read_line: Callable that returns one line of user input.
        print_fn: Callable for printing retry prompts.
        has_pre_label: Whether the current row's pre_label is set.
    Returns:
        Canonical command name: 'keep', 'flip', 'pass', 'fail', or 'skip'.
    """
    accepted = {"keep", "flip"} if has_pre_label else {"pass", "fail"}
    accepted.add("skip")
    hint = "keep/flip/skip or k/f/s" if has_pre_label else "pass/fail/skip or p/n/s"
    while True:
        raw = read_line().strip().lower()
        command = SHORTCUTS.get(raw, raw)
        if command in accepted:
            return command
        print_fn(f"  Invalid input {raw!r}. Enter {hint}.")
