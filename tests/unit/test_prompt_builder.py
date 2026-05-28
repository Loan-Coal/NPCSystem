"""
test_prompt_builder.py - Unit tests for dialogue prompt assembly.

Does NOT: call LLM adapters or external services.

Dependencies injected: None.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest
from npc_engine.engines.dialogue.prompt_builder import (
    PROMPT_VERSION,
    _PROMPT_PATH,
    _extract_voice_descriptor,
    build_dialogue_prompt,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_returns_non_empty_string() -> None:
    """build_system_prompt must return a non-empty string from the YAML."""
    result = build_system_prompt()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_system_prompt_contains_epoch_must_not() -> None:
    """The authoritative epoch rule must include MUST NOT to satisfy D2 requirement."""
    result = build_system_prompt()
    assert "MUST NOT" in result


def test_build_system_prompt_epoch_is_authoritative() -> None:
    """The system prompt must mark epoch as AUTHORITATIVE."""
    result = build_system_prompt()
    assert "AUTHORITATIVE" in result


def test_build_system_prompt_contains_epistemic_certainty_rule() -> None:
    """Rule 9 must instruct the LLM to hedge rumour-sourced knowledge."""
    result = build_system_prompt()
    assert "EPISTEMIC CERTAINTY" in result


def test_build_system_prompt_active_conditions_constraint() -> None:
    """Rule 1 must include a general active_conditions constraint (R2.2)."""
    result = build_system_prompt()
    assert "ACTIVE CONDITIONS" in result
    assert "active_conditions" in result


def test_build_system_prompt_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """FileNotFoundError must propagate when the YAML file is absent."""
    missing = tmp_path / "nonexistent.yaml"
    with patch("npc_engine.engines.dialogue.prompt_builder._PROMPT_PATH", missing):
        with pytest.raises(FileNotFoundError):
            build_system_prompt()


# ---------------------------------------------------------------------------
# build_dialogue_prompt
# ---------------------------------------------------------------------------


def _make_request(
    player_message: str = "Hello",
    npc_id: str = "npc_001",
    player_id: str = "player_001",
) -> DialogueRequest:
    return DialogueRequest(
        npc_id=npc_id,
        player_id=player_id,
        player_message=player_message,
    )


def test_build_dialogue_prompt_contains_version() -> None:
    """Output must contain the current PROMPT_VERSION string."""
    result = build_dialogue_prompt(_make_request(), "{}")
    assert f"PROMPT_VERSION={PROMPT_VERSION}" in result


def test_build_dialogue_prompt_contains_npc_id() -> None:
    """Output must embed the NPC identifier."""
    result = build_dialogue_prompt(_make_request(npc_id="guard_42"), "{}")
    assert "NPC_ID=guard_42" in result


def test_build_dialogue_prompt_contains_player_id() -> None:
    """Output must embed the player identifier."""
    result = build_dialogue_prompt(_make_request(player_id="hero_007"), "{}")
    assert "PLAYER_ID=hero_007" in result


def test_build_dialogue_prompt_contains_context() -> None:
    """Output must embed the serialized context payload."""
    context = '{"world": {"epoch": "war"}}'
    result = build_dialogue_prompt(_make_request(), context)
    assert f"CONTEXT={context}" in result


def test_build_dialogue_prompt_contains_player_message() -> None:
    """Output must embed the player message verbatim."""
    result = build_dialogue_prompt(_make_request(player_message="Where is the inn?"), "{}")
    assert "PLAYER_MESSAGE=Where is the inn?" in result


def test_build_dialogue_prompt_contains_voice_descriptor_line() -> None:
    """VOICE_DESCRIPTOR line must always be present, even when empty."""
    result = build_dialogue_prompt(_make_request(), "{}")
    assert "VOICE_DESCRIPTOR=" in result


def test_build_dialogue_prompt_injects_voice_from_context() -> None:
    """Voice descriptor from npc.profile must appear in VOICE_DESCRIPTOR line."""
    import json
    ctx = json.dumps({"npc": {"profile": {"voice_descriptor": "Clipped military diction."}}})
    result = build_dialogue_prompt(_make_request(), ctx)
    assert "VOICE_DESCRIPTOR=Clipped military diction." in result


# ---------------------------------------------------------------------------
# _extract_voice_descriptor
# ---------------------------------------------------------------------------


def test_extract_voice_descriptor_reads_from_context() -> None:
    """Returns the voice_descriptor string from npc.profile."""
    import json
    ctx = json.dumps({"npc": {"profile": {"voice_descriptor": "Warm, observant."}}})
    assert _extract_voice_descriptor(ctx) == "Warm, observant."


def test_extract_voice_descriptor_empty_on_missing_field() -> None:
    """Returns empty string when voice_descriptor is absent."""
    import json
    assert _extract_voice_descriptor(json.dumps({})) == ""
    assert _extract_voice_descriptor(json.dumps({"npc": {"profile": {}}})) == ""


def test_extract_voice_descriptor_empty_on_bad_json() -> None:
    """Returns empty string for malformed context."""
    assert _extract_voice_descriptor("not-json") == ""
    assert _extract_voice_descriptor("") == ""
