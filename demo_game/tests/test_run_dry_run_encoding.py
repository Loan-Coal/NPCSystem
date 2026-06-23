"""
test_run_dry_run_encoding.py - Regression for ISSUE-100: the scripted demo runner
must complete the full --dry-run sequence (past the ACT-8 determinism beat) even
when stdout uses the Windows cp1252 codec, which cannot encode glyphs like the
U+2192 arrow printed in several scene cues.

Before the fix, `main()` never reconfigured stdout to UTF-8, so printing the ACT-8
cue raised UnicodeEncodeError. The fix wires the existing ensure_utf8_stdout()
helper into main().

Does NOT: make API calls (dry-run path is fully offline).
"""

from __future__ import annotations

import io
import sys

from demo_game.runners.run import main


def _run_dry_run_on_cp1252_stdout(monkeypatch) -> str:
    """Invoke the demo runner in --dry-run mode with a cp1252-backed stdout.

    Returns:
        The full captured output, decoded as UTF-8.
    """
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "argv", ["run", "--dry-run"])

    main()

    stream.flush()
    return buffer.getvalue().decode("utf-8", errors="replace")


def test_dry_run_completes_through_act8_on_cp1252_stdout(monkeypatch) -> None:
    output = _run_dry_run_on_cp1252_stdout(monkeypatch)

    # The ACT-8 determinism cue is the glyph that crashed cp1252 stdout.
    assert "Determinism proof" in output
    # The run reached its end without raising UnicodeEncodeError.
    assert "[done]" in output
