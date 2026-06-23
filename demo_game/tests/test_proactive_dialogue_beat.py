"""
Module: test_proactive_dialogue_beat
Layer: demo_game (tests)
Purpose: Unit tests for ProactiveDialogueBeat — NPC-initiated proactive dialogue beat.
         Covers: intent rendered, empty list degrades gracefully, dry_run skips API.
Dependencies: demo_game.beats.proactive_dialogue_beat (ProactiveDialogueBeat)
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.beats.proactive_dialogue_beat import (
    ProactiveDialogueBeat,
    _PLAYER_ID,
    _NO_PENDING_MSG,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INTENT = {
    "npc_id": "mira_innkeeper",
    "message": "Traveller! I have news you must hear.",
    "intent_type": "share_information",
    "score": 0.9,
}


def _make_runner(
    *,
    dry_run: bool = False,
    pending_intents: list[dict] | None = None,
) -> MagicMock:
    """Build a minimal mock DemoRunner with controllable pending-intents behaviour."""
    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client.get_pending_intents.return_value = (
        pending_intents if pending_intents is not None else []
    )
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProactiveDialogueBeat:
    """Unit tests for ProactiveDialogueBeat."""

    def test_dry_run_skips_api(self) -> None:
        """dry_run=True must return before any client call."""
        runner = _make_runner(dry_run=True)
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)
        runner.client.get_pending_intents.assert_not_called()

    def test_empty_intents_no_crash(self) -> None:
        """Empty pending-intents list must not raise and must print a graceful message."""
        runner = _make_runner(pending_intents=[])
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)  # must not raise

        all_calls = [str(c) for c in runner.print_ok.call_args_list + runner.print_step.call_args_list]
        assert any(_NO_PENDING_MSG in call for call in all_calls), (
            f"Expected {_NO_PENDING_MSG!r} in output, got: {all_calls}"
        )

    def test_intent_npc_line_rendered(self) -> None:
        """When one intent is pending, beat must print the NPC message."""
        runner = _make_runner(pending_intents=[_INTENT])
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)

        all_calls = [str(c) for c in runner.print_ok.call_args_list + runner.print_step.call_args_list]
        snippet = _INTENT["message"][:30]
        assert any(snippet in call for call in all_calls), (
            f"Expected NPC message snippet {snippet!r} in output, got: {all_calls}"
        )

    def test_intent_npc_id_rendered(self) -> None:
        """Beat must identify the NPC that hailed the player."""
        runner = _make_runner(pending_intents=[_INTENT])
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)

        all_calls = [str(c) for c in runner.print_ok.call_args_list + runner.print_step.call_args_list]
        assert any("mira_innkeeper" in call for call in all_calls), (
            f"Expected 'mira_innkeeper' in output, got: {all_calls}"
        )

    def test_get_pending_intents_called_with_player_id(self) -> None:
        """Beat must call get_pending_intents with the canonical player_id."""
        runner = _make_runner(pending_intents=[])
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)

        runner.client.get_pending_intents.assert_called_once_with(_PLAYER_ID)

    def test_clock_tick_before_fetch(self) -> None:
        """Beat must advance the clock once before fetching intents."""
        runner = _make_runner(pending_intents=[])
        beat = ProactiveDialogueBeat(name="act11_proactive")
        beat.execute(runner)

        runner.client.advance_clock.assert_called_once()

    def test_name_stored(self) -> None:
        """Scene name is stored correctly on the dataclass."""
        beat = ProactiveDialogueBeat(name="act11_proactive")
        assert beat.name == "act11_proactive"
