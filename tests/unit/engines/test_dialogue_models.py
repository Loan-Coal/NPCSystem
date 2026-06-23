"""Tests for dialogue_models.py — DialogueRequest input validation."""

import pytest
from pydantic import ValidationError

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest
from npc_engine.config import MAX_PLAYER_MESSAGE_CHARS


def _make_request(**kwargs: object) -> DialogueRequest:
    defaults = dict(player_id="p1", npc_id="npc1", player_message="hello")
    defaults.update(kwargs)
    return DialogueRequest(**defaults)  # type: ignore[arg-type]


def test_valid_request_accepted() -> None:
    req = _make_request(player_message="Tell me about the war.")
    assert req.player_message == "Tell me about the war."


def test_message_at_max_length_accepted() -> None:
    msg = "a" * MAX_PLAYER_MESSAGE_CHARS
    req = _make_request(player_message=msg)
    assert len(req.player_message) == MAX_PLAYER_MESSAGE_CHARS


def test_message_over_max_length_rejected() -> None:
    msg = "a" * (MAX_PLAYER_MESSAGE_CHARS + 1)
    with pytest.raises(ValidationError):
        _make_request(player_message=msg)


def test_max_player_message_chars_is_1000() -> None:
    assert MAX_PLAYER_MESSAGE_CHARS == 1000
