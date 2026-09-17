"""
test_dialogue_response_length_cap.py
Layer: test
Purpose: Verify that DialogueResponse enforces a maximum length on npc_response and
that the dialogue LLM config max_tokens is consistent with the schema cap.

Finding L12-12, SEV-06 (T2.2).
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from pydantic import ValidationError

from npc_engine.config import NPC_RESPONSE_MAX_CHARS
from npc_engine.engines.dialogue.dialogue_models import DialogueResponse

_LLM_CONFIG = pathlib.Path("src/npc_engine/engines/dialogue/llm_config.yaml")

# Minimum characters per token for qwen2.5:7b on English dialogue — used to
# verify that max_tokens doesn't allow more chars than the schema cap accepts.
_CHARS_PER_TOKEN_MIN = 4


class TestDialogueResponseLengthCap:
    """DialogueResponse must structurally cap npc_response length."""

    def test_rejects_over_long_npc_response(self) -> None:
        """ValidationError raised when npc_response exceeds NPC_RESPONSE_MAX_CHARS."""
        with pytest.raises(ValidationError):
            DialogueResponse(npc_response="x" * (NPC_RESPONSE_MAX_CHARS + 1))

    def test_accepts_npc_response_at_cap(self) -> None:
        """DialogueResponse accepts npc_response exactly at the cap."""
        resp = DialogueResponse(npc_response="a" * NPC_RESPONSE_MAX_CHARS)
        assert len(resp.npc_response) == NPC_RESPONSE_MAX_CHARS

    def test_max_tokens_consistent_with_schema_cap(self) -> None:
        """max_tokens in llm_config.yaml must not exceed NPC_RESPONSE_MAX_CHARS // 4.

        If max_tokens * _CHARS_PER_TOKEN_MIN > NPC_RESPONSE_MAX_CHARS the YAML permits
        more tokens than the schema's char cap allows; the token limit becomes dead code
        and the latency saving evaporates.
        """
        cfg = yaml.safe_load(_LLM_CONFIG.read_text(encoding="utf-8"))
        max_tokens: int = cfg["llm"]["max_tokens"]
        assert max_tokens * _CHARS_PER_TOKEN_MIN <= NPC_RESPONSE_MAX_CHARS, (
            f"max_tokens={max_tokens} would allow up to "
            f"{max_tokens * _CHARS_PER_TOKEN_MIN} chars at {_CHARS_PER_TOKEN_MIN} "
            f"chars/token, exceeding NPC_RESPONSE_MAX_CHARS={NPC_RESPONSE_MAX_CHARS}"
        )
