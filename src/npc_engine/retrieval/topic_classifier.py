"""
topic_classifier.py - Keyword-based player message topic detection for dialogue weight profiles.

Does NOT: call LLM adapters, access graph data, or perform any I/O.

Dependencies injected: None.
"""

# Keywords that indicate the player is engaging with a quest flow (task inquiry,
# objective update, reward collection, delivery / kill / fetch). When matched,
# the retrieval pipeline boosts quest context over social/relationship context.
_QUEST_KEYWORDS: frozenset[str] = frozenset({
    "quest", "mission", "task", "objective", "reward", "bounty",
    "deliver", "delivery", "fetch", "find", "kill", "slay", "defeat",
    "complete", "completed", "done", "finished", "assignment",
    "contract", "job", "hired", "payment", "hand in", "turn in",
    "brought", "collected", "slain", "retrieved",
})


def detect_dialogue_profile(player_message: str) -> str:
    """Return the weight profile name that best matches the player's message topic.

    Uses keyword matching against the lowercased message. Falls back to the
    general social profile when no quest-related vocabulary is found.

    Args:
        player_message: Raw player message string from the dialogue request.

    Returns:
        A profile name that exists in DEFAULT_WEIGHT_PROFILES:
        - ``"rpg_dialogue_quest"`` for quest-focused turns
        - ``"rpg_dialogue_social"`` for all other turns (default)
    """
    lowered = player_message.lower()
    if any(kw in lowered for kw in _QUEST_KEYWORDS):
        return "rpg_dialogue_quest"
    return "rpg_dialogue_social"
