"""
test_topic_classifier.py - Unit tests for dialogue topic detection.

Does NOT: call LLM adapters or access graph/vector data.

Dependencies injected: None.
"""

import pytest

from npc_engine.retrieval.embedding import detect_dialogue_profile


@pytest.mark.parametrize("message", [
    "Are the streets safe to travel?",
    "What do you think of the king?",
    "How are you feeling today?",
    "Tell me about this town.",
    "I heard there was a plague nearby.",
    "What's the weather like?",
    "Do you know anyone who can help me?",
])
def test_social_messages_return_social_profile(message: str) -> None:
    assert detect_dialogue_profile(message) == "rpg_dialogue_social"


@pytest.mark.parametrize("message", [
    "I've completed the quest you gave me.",
    "Here is the item you asked me to fetch.",
    "I slain the bandits. Where's my reward?",
    "I finished the mission.",
    "Can you give me a new task?",
    "I collected the bounty.",
    "The contract is done.",
    "I've retrieved the artifact.",
    "I want to hand in my assignment.",
    "I killed the wolves. Payment please.",
])
def test_quest_messages_return_quest_profile(message: str) -> None:
    assert detect_dialogue_profile(message) == "rpg_dialogue_quest"


def test_empty_message_returns_social_profile() -> None:
    assert detect_dialogue_profile("") == "rpg_dialogue_social"


def test_case_insensitive_matching() -> None:
    assert detect_dialogue_profile("I COMPLETED THE QUEST") == "rpg_dialogue_quest"
    assert detect_dialogue_profile("QUEST") == "rpg_dialogue_quest"
