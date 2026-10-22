"""
Module: test_cache_empty_miss
Layer: demo_game (tests)
Purpose: ISSUE-348 regression — a cached reply with an empty npc_response must
         not be treated as a cache hit in DialogueBeat and StreamingDialogueBeat.
Dependencies: demo_game.runners.run_scenes, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

import queue
from unittest.mock import MagicMock

import pytest

from demo_game.runners.run_scenes import DialogueBeat, StreamingDialogueBeat


def _runner_with_cached(reply: dict) -> MagicMock:
    """Build a MagicMock runner whose cache returns *reply*."""
    runner = MagicMock()
    runner.dry_run = False
    runner.cache.get.return_value = reply
    runner.client.post_dialogue.return_value = {"npc_response": "live reply"}
    return runner


class TestDialogueBeatCacheEmptyMiss:
    def test_empty_npc_response_triggers_live_call(self) -> None:
        """DialogueBeat with {'npc_response': ''} must call post_dialogue (cache miss)."""
        runner = _runner_with_cached({"npc_response": ""})
        beat = DialogueBeat(name="t", npc_id="sorn", player_input="hello")
        beat.execute(runner)
        runner.client.post_dialogue.assert_called_once()

    def test_non_empty_npc_response_is_hit(self) -> None:
        """DialogueBeat with a real cached reply must NOT call post_dialogue (cache hit)."""
        runner = _runner_with_cached({"npc_response": "A fine morning, adventurer."})
        beat = DialogueBeat(name="t", npc_id="sorn", player_input="hello")
        beat.execute(runner)
        runner.client.post_dialogue.assert_not_called()

    def test_none_cache_result_triggers_live_call(self) -> None:
        """DialogueBeat with cache miss (None) must call post_dialogue."""
        runner = _runner_with_cached(None)
        runner.cache.get.return_value = None
        beat = DialogueBeat(name="t", npc_id="sorn", player_input="hello")
        beat.execute(runner)
        runner.client.post_dialogue.assert_called_once()


class TestStreamingDialogueBeatCacheEmptyMiss:
    def test_empty_npc_response_triggers_live_ws_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """StreamingDialogueBeat with {'npc_response': ''} must make a live WS call."""

        def _fake_ws_worker(ws_url: str, api_key: str, payload: dict, result_q: queue.Queue) -> None:
            result_q.put(("done", {}))

        monkeypatch.setattr("demo_game.runners.run_scenes.dialogue_ws_worker", _fake_ws_worker)

        runner = _runner_with_cached({"npc_response": ""})
        beat = StreamingDialogueBeat(name="t", npc_id="sorn", player_input="hello")
        beat.execute(runner)

        # cache.put is only reached via the live WS path, never via the early-return cached path
        runner.cache.put.assert_called_once()

    def test_non_empty_npc_response_skips_ws(self) -> None:
        """StreamingDialogueBeat with a real cached reply must not start a WS thread."""
        runner = _runner_with_cached({"npc_response": "Aye, there's trouble up north."})
        beat = StreamingDialogueBeat(name="t", npc_id="sorn", player_input="hello")
        beat.execute(runner)
        # cache.put is NOT called on the early-return path
        runner.cache.put.assert_not_called()
