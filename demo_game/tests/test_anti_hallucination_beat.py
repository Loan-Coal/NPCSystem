"""
Module: test_anti_hallucination_beat
Layer: demo_game (tests)
Purpose: Unit tests for AntiHallucinationBeat — verifies the beat calls
         get_graph_edges("KNOWS_ABOUT") for aldric_merchant, calls post_dialogue
         with the correct NPC and player message, and prints the response without
         raising. No live engine required.
Dependencies: demo_game.run_scenes (AntiHallucinationBeat)
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.run_scenes import AntiHallucinationBeat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REFUSAL_TEXT = "I'm afraid I know nothing of any war in the north, friend."

_DIALOGUE_RESPONSE = {
    "npc_response": _REFUSAL_TEXT,
    "npc_id": "aldric_merchant",
}


def _make_runner(
    dry_run: bool = False,
    knows_about_edges: list[dict] | None = None,
    dialogue_response: dict | None = None,
) -> MagicMock:
    """Build a minimal mock DemoRunner for AntiHallucinationBeat tests."""
    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client.get_graph_edges.return_value = knows_about_edges if knows_about_edges is not None else []
    runner.client.post_dialogue.return_value = dialogue_response or _DIALOGUE_RESPONSE
    return runner


# ---------------------------------------------------------------------------
# AntiHallucinationBeat
# ---------------------------------------------------------------------------

class TestAntiHallucinationBeat:
    """Tests for the anti-hallucination scripted demo beat."""

    def test_execute_does_not_raise(self) -> None:
        """Beat completes without raising when Aldric has no KNOWS_ABOUT edges."""
        runner = _make_runner()
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)  # should not raise

    def test_calls_get_graph_edges_for_knows_about(self) -> None:
        """Beat fetches KNOWS_ABOUT edges filtered to aldric_merchant."""
        runner = _make_runner()
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        runner.client.get_graph_edges.assert_called_once()
        call_kwargs = runner.client.get_graph_edges.call_args
        # first positional arg must be the edge type
        assert call_kwargs.args[0] == "KNOWS_ABOUT" or call_kwargs.kwargs.get("edge_type") == "KNOWS_ABOUT"

    def test_get_graph_edges_filtered_to_aldric(self) -> None:
        """Beat passes src_id='aldric_merchant' to get_graph_edges."""
        runner = _make_runner()
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        call_kwargs = runner.client.get_graph_edges.call_args
        src_id = call_kwargs.kwargs.get("src_id") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert src_id == "aldric_merchant"

    def test_calls_post_dialogue_with_aldric(self) -> None:
        """Beat calls post_dialogue with aldric_merchant as the NPC."""
        runner = _make_runner()
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        runner.client.post_dialogue.assert_called_once()
        call_kwargs = runner.client.post_dialogue.call_args.kwargs
        assert call_kwargs.get("npc_id") == "aldric_merchant"

    def test_post_dialogue_message_mentions_war(self) -> None:
        """Beat player_message asks about the northern war."""
        runner = _make_runner()
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        call_kwargs = runner.client.post_dialogue.call_args.kwargs
        msg: str = call_kwargs.get("player_message", "")
        assert "war" in msg.lower() or "north" in msg.lower()

    def test_prints_npc_response(self) -> None:
        """Beat prints the NPC response text to stdout."""
        runner = _make_runner(dialogue_response=_DIALOGUE_RESPONSE)
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        # print_ok or print_step is called with text containing the response
        all_calls = [str(c) for c in runner.print_ok.call_args_list + runner.print_step.call_args_list]
        response_snippet = _REFUSAL_TEXT[:30]
        assert any(response_snippet in call for call in all_calls)

    def test_dry_run_skips_api_calls(self) -> None:
        """Beat skips all API calls when dry_run=True."""
        runner = _make_runner(dry_run=True)
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        runner.client.get_graph_edges.assert_not_called()
        runner.client.post_dialogue.assert_not_called()

    def test_zero_edges_reported(self) -> None:
        """Beat reports 0 KNOWS_ABOUT edges for aldric_merchant."""
        runner = _make_runner(knows_about_edges=[])
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        beat.execute(runner)
        all_calls = [str(c) for c in runner.print_ok.call_args_list + runner.print_step.call_args_list]
        # Confirm the output mentions 0 edges
        assert any("0" in call for call in all_calls)

    def test_name_field(self) -> None:
        """Beat stores the name field correctly."""
        beat = AntiHallucinationBeat(name="beat_anti_hallucination")
        assert beat.name == "beat_anti_hallucination"
