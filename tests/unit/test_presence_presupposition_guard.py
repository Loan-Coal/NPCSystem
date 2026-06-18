"""
test_presence_presupposition_guard.py - Unit test for the S22.5 / ISSUE-082 prompt hardening.

old_henryk affirmed false-eyewitness presuppositions ("you were at the front, weren't you?").
The system prompt (Rule 9) must carry an explicit deny-first clause for claims that the NPC
personally witnessed or was present at an event. This test asserts the clause is present in the
loaded system prompt (the live LLM-judge verification of the two cases runs under make eval-llm-demo).
"""

from __future__ import annotations

from npc_engine.engines.dialogue.prompt_builder import build_system_prompt


def test_system_prompt_has_presence_presupposition_clause() -> None:
    """The system prompt must instruct the NPC to deny false presence before answering."""
    prompt = build_system_prompt()
    assert "PRESENCE PRESUPPOSITION" in prompt
    lowered = prompt.lower()
    assert "deny" in lowered
    assert "present" in lowered or "witnessed" in lowered
