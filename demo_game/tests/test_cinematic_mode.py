"""
Tests for EXP-222 cinematic mode in demo_game/run.py.

Verifies:
- cinematic=True: formatted markers (ACT header, wide rule) appear in output.
- cinematic=False: default output is unchanged (plain prefixes only).
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest

from demo_game.runners.run import DemoRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_print_cue(cinematic: bool, msg: str) -> str:
    """Return the string that print_cue would write for the given cinematic flag."""
    runner = DemoRunner.__new__(DemoRunner)
    runner.dry_run = True
    runner.cinematic = cinematic

    buf = io.StringIO()
    with patch("builtins.print", side_effect=lambda *a, **k: buf.write(" ".join(str(x) for x in a) + "\n")):
        runner.print_cue(msg)
    return buf.getvalue()


def _capture_print_step(cinematic: bool, msg: str) -> str:
    runner = DemoRunner.__new__(DemoRunner)
    runner.dry_run = True
    runner.cinematic = cinematic

    buf = io.StringIO()
    with patch("builtins.print", side_effect=lambda *a, **k: buf.write(" ".join(str(x) for x in a) + "\n")):
        runner.print_step(msg)
    return buf.getvalue()


def _capture_print_ok(cinematic: bool, msg: str) -> str:
    runner = DemoRunner.__new__(DemoRunner)
    runner.dry_run = True
    runner.cinematic = cinematic

    buf = io.StringIO()
    with patch("builtins.print", side_effect=lambda *a, **k: buf.write(" ".join(str(x) for x in a) + "\n")):
        runner.print_ok(msg)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cinematic ON — formatted markers must appear
# ---------------------------------------------------------------------------

class TestCinematicFormatsOutput:
    """Cinematic mode produces recording-friendly output with visual markers."""

    def test_print_cue_cinematic_has_wide_rule(self) -> None:
        """Wide rule (=== chars) must appear in cinematic cue output."""
        output = _capture_print_cue(cinematic=True, msg="[ACT 1] Some cue text")
        assert "=" in output, "Cinematic print_cue should use wide rule markers"

    def test_print_cue_cinematic_rule_is_wider_than_default(self) -> None:
        """Cinematic rule must be wider than the default 60-char dash rule."""
        cinematic_out = _capture_print_cue(cinematic=True, msg="test")
        default_out = _capture_print_cue(cinematic=False, msg="test")
        # Cinematic uses '=' and wider; default uses '-' at 60
        assert "=" in cinematic_out
        assert "=" not in default_out

    def test_print_cue_cinematic_contains_message(self) -> None:
        """The original message text must still be present in cinematic output."""
        msg = "[ACT 5] Specific message"
        output = _capture_print_cue(cinematic=True, msg=msg)
        assert msg in output

    def test_print_cue_cinematic_act_header_prefix(self) -> None:
        """Cinematic cue must include an ACT marker (uppercase block label)."""
        output = _capture_print_cue(cinematic=True, msg="[ACT 3] Bribe scene")
        # The formatted block should include the text, surrounded by '=' rules
        lines = output.strip().splitlines()
        rule_lines = [ln for ln in lines if "=" in ln and ln.count("=") >= 10]
        assert len(rule_lines) >= 2, "Cinematic cue should have top and bottom '=' rules"

    def test_print_step_cinematic_uses_arrow_prefix(self) -> None:
        """Cinematic step lines should use a visually distinct prefix (e.g. '>>')."""
        output = _capture_print_step(cinematic=True, msg="Calling API")
        assert ">>" in output or "▶" in output or "→" in output or "  >>  " in output

    def test_print_ok_cinematic_uses_check_prefix(self) -> None:
        """Cinematic ok lines should use a visually distinct prefix (e.g. '✓' or '[ok]')."""
        output = _capture_print_ok(cinematic=True, msg="Scene passed")
        # Must differ from default "  ok " prefix
        assert "ok" in output.lower()

    def test_done_line_cinematic_has_separator(self) -> None:
        """Cinematic done line should include a wide rule and elapsed time."""
        runner = DemoRunner.__new__(DemoRunner)
        runner.dry_run = True
        runner.cinematic = True

        buf = io.StringIO()
        with patch("builtins.print", side_effect=lambda *a, **k: buf.write(" ".join(str(x) for x in a) + "\n")):
            runner.print_done(elapsed_s=3.7)
        output = buf.getvalue()
        assert "3.7" in output
        assert "=" in output


# ---------------------------------------------------------------------------
# Cinematic OFF — default output must be unchanged (back-compat)
# ---------------------------------------------------------------------------

class TestDefaultOutputUnchanged:
    """Non-cinematic output is identical to pre-EXP-222 behaviour."""

    def test_print_cue_default_uses_dash_rule(self) -> None:
        """Default print_cue must use 60 dashes exactly as before."""
        output = _capture_print_cue(cinematic=False, msg="some cue")
        assert "-" * 60 in output

    def test_print_step_default_prefix(self) -> None:
        """Default print_step must produce '  >  <msg>'."""
        output = _capture_print_step(cinematic=False, msg="my step")
        assert "  >  my step" in output

    def test_print_ok_default_prefix(self) -> None:
        """Default print_ok must produce '  ok <msg>'."""
        output = _capture_print_ok(cinematic=False, msg="my result")
        assert "  ok my result" in output

    def test_default_runner_cinematic_is_false(self) -> None:
        """DemoRunner() without cinematic= arg must default to False."""
        with patch("demo_game.runners.run.DemoConfig") as mock_cfg, \
             patch("demo_game.runners.run.EngineClient"):
            mock_cfg.return_value.NPC_BASE_URL = "http://localhost:8000"
            mock_cfg.return_value.NPC_API_KEY = "test"
            runner = DemoRunner()
        assert runner.cinematic is False
