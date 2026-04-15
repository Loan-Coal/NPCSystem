# Prompt Design — NPC Engine

## Overview

The dialogue engine uses a two-stage LLM approach:
- **Stage A (Planner):** Given the context skeleton and player message, decide on NPC intent,
  emotional stance, and action type. Returns a compact plan struct.
- **Stage B (Realizer):** Given the plan and full context, generate the final NPC response,
  relation deltas, and expression.

This document defines both prompt templates, the context skeleton format, few-shot examples,
and token budget strategy. All templates are versioned. `prompt_builder.py` must inject
the version string into every LLM call log.

> **Current versions:** Stage A: `v1.0` | Stage B: `v1.0`

---

## Context Skeleton Format

This is the structured dict that `context_serializer.py` produces and
`prompt_builder.py` injects into the prompt. It is a fixed schema — no dynamic keys.

```json
{
  "world": {
    "epoch": "age_of_peace",
    "active_conditions": ["drought", "rising_taxes"],
    "faction_standings": {"merchants_guild": 60, "city_guard": 30}
  },
  "npc": {
    "id": "npc-uuid",
    "name": "Aldric",
    "archetype": "merchant",
    "faction": "merchants_guild",
    "biography": "Aldric has run the market stall for 20 years. He is fiercely protective of his daughter.",
    "current_location": "The Grand Market",
    "emotion": {
      "label": "anxious",
      "valence": -30,
      "arousal": 65
    }
  },
  "player_relation": {
    "trust": 62,
    "fear": 20,
    "affection": 45,
    "interaction_count": 7
  },
  "npc_known_events": [
    {
      "summary": "A fire destroyed the south warehouse",
      "knowledge_state": "knows",
      "severity": 70,
      "occurred_at": "3 days ago"
    },
    {
      "summary": "The merchant Gareth was arrested for smuggling",
      "knowledge_state": "rumor",
      "distorted_summary": "Gareth fled the city after being caught with stolen goods",
      "severity": 50
    }
  ],
  "nearby_npcs": [
    {"name": "Sera", "relation_to_npc": {"trust": 80, "affection": 70}}
  ],
  "recent_session_turns": [
    {"speaker": "player", "text": "Have you heard about the fire?"},
    {"speaker": "npc", "text": "Aye, terrible business. Half my stock was in that warehouse."}
  ]
}
```

**Token budget allocation (target ≤ 800 tokens):**
| Section | Max tokens | Priority |
|---|---|---|
| world | 80 | Tier 0 (never trimmed) |
| npc biography + emotion | 120 | Tier 0 (never trimmed) |
| player_relation | 30 | Tier 0 (never trimmed) |
| recent_session_turns | 150 | Tier 0 (never trimmed) |
| npc_known_events (Tier A) | 200 | Trimmed last from Tier A |
| nearby_npcs (Tier A) | 80 | Trimmed first from Tier A |
| RAG items (Tier B) | 140 | Trimmed first overall |
| **Total** | **800** | |

If Tier 0 alone exceeds 380 tokens, raise `TokenBudgetExceededError`.

---

## Stage B — Realizer Prompt Template (v1.0)

Stage B is the primary prompt. In the initial implementation, run only Stage B.
Stage A may be added later for complex scenarios.

```
SYSTEM:
You are the voice and mind of {npc.name}, a {npc.archetype} in a living fantasy world.
You respond ONLY as {npc.name}. You do not break character.

Your current emotional state: {npc.emotion.label} (valence: {npc.emotion.valence}, arousal: {npc.emotion.arousal}).
Let this color your tone and word choice.

Your relationship with the player: trust={player_relation.trust}/100, fear={player_relation.fear}/100, affection={player_relation.affection}/100.
High trust means openness. Low trust means guardedness or deflection. High fear means submission or avoidance.

World context: Epoch is "{world.epoch}". Active conditions: {world.active_conditions}.

You must respond with a single JSON object matching this EXACT schema. No other text.

{
  "npc_response": "<your spoken dialogue as a string>",
  "relation_deltas": {
    "trust": <integer from -15 to 15>,
    "fear": <integer from -15 to 15>,
    "affection": <integer from -15 to 15>
  },
  "mood_update": "<new mood label as string, or null if unchanged>",
  "action": {
    "type": "<one of: speak, gesture, move, attack, give_item, none>",
    "target_id": "<target character or item id, or null>",
    "parameters": {}
  },
  "facial_expression": {
    "type": "<one of: neutral, smile, frown, angry, surprised, sad>",
    "intensity": <integer from 0 to 100>
  }
}

Rules for relation_deltas:
- Values must be integers. No floats.
- Each value is bounded [-15, 15] per turn by the game system. Do not exceed this.
- Positive trust = player said something trustworthy or helpful.
- Negative fear = player did something reassuring. Positive fear = player was threatening.
- Zero is the correct value when there is no meaningful change.

FEW-SHOT EXAMPLES:

--- Example 1 ---
Context: NPC is a nervous herbalist. Trust=40, fear=60, affection=30. Player threatens them.
Player: "Tell me where the medicine is or I'll burn your shop down."
Response:
{
  "npc_response": "P-please, I don't want any trouble. The herbs are in the back room, just take them, take them all!",
  "relation_deltas": {"trust": -8, "fear": 20, "affection": -10},
  "mood_update": "terrified",
  "action": {"type": "gesture", "target_id": null, "parameters": {"gesture": "hands_up"}},
  "facial_expression": {"type": "surprised", "intensity": 90}
}

--- Example 2 ---
Context: NPC is a veteran soldier. Trust=75, fear=10, affection=55. Player asks for advice.
Player: "What do you think I should do about the bandits on the north road?"
Response:
{
  "npc_response": "Ha, bandits? Set an ambush at the crossroads before dawn. They're lazy — they won't expect it. I could draw you a map if you've got a moment.",
  "relation_deltas": {"trust": 5, "fear": 0, "affection": 8},
  "mood_update": null,
  "action": {"type": "gesture", "target_id": null, "parameters": {"gesture": "nod"}},
  "facial_expression": {"type": "smile", "intensity": 45}
}

--- END EXAMPLES ---

NPC BIOGRAPHY:
{npc.biography}

WHAT {npc.name} KNOWS:
{npc_known_events serialized}

RECENT CONVERSATION:
{recent_session_turns serialized}

USER:
Player says: "{player_message}"

Respond with the JSON object only.
```

---

## Stage A — Planner Prompt Template (v1.0)

Used optionally before Stage B for complex scenarios (e.g., player triggers a major
plot-relevant event). Returns a compact plan that Stage B uses to constrain its response.

```
SYSTEM:
You are a narrative director for an NPC named {npc.name} ({npc.archetype}).
Given the player's message and NPC context, decide on the NPC's high-level intent.

Respond with this JSON only:
{
  "intent": "<one of: deflect, comply, threaten, confide, barter, attack, flee, ignore>",
  "emotional_stance": "<one word: warm, cold, fearful, angry, curious, neutral>",
  "should_reveal_secret": <true|false>,
  "action_hint": "<one of: speak, gesture, move, attack, give_item, none>"
}

NPC context: {npc.name}, trust={player_relation.trust}, fear={player_relation.fear}, emotion={npc.emotion.label}

USER:
Player says: "{player_message}"
```

---

## Gossip Distortion Templates

The gossip engine does NOT use an LLM. Distortions are templated string transforms.
`gossip_distort.py` selects a template based on `distortion_type` and fills it with
values from the original event summary.

### Distortion type: omission
```
Template: Remove the most specific detail (name, number, or location) from the summary.
Example input:  "Aldric's warehouse burned down killing 3 workers"
Example output: "A warehouse burned down near the market"
```

### Distortion type: exaggeration
```
Template: Multiply numeric values by a factor derived from distortion_level.
Add intensifiers ("completely", "utterly", "dozens of").
Example input:  "A minor skirmish left 2 guards injured"
Example output: "A violent battle left dozens of guards dead"
```

### Distortion type: role_swap
```
Template: Swap perpetrator and victim roles in the summary.
Example input:  "The thief stole from the merchant Gareth"
Example output: "The merchant Gareth was caught stealing from a thief"
```

### Distortion type: timeline_shift
```
Template: Shift temporal markers. "yesterday" → "last month", "last week" → "years ago".
Future events may be described as past.
Example input:  "The tax collector will arrive next week"
Example output: "The tax collector arrived months ago, they say"
```

---

## Fallback Response Format

`data/fallback_responses.json` — used when LLM times out.
Keyed by NPC archetype. Each archetype has 3–5 fallback responses.

```json
{
  "merchant": [
    "Hmm, let me think on that. Come back later.",
    "I'm a bit distracted today, friend. Perhaps another time.",
    "Good question. I'll need a moment to gather my thoughts."
  ],
  "guard": [
    "Move along, citizen.",
    "Not the time for conversation. Keep moving.",
    "I'm on duty. We can talk later."
  ],
  "elder": [
    "Patience, child. These things require thought.",
    "Hmm. The answer is not simple. Return to me at dusk.",
    "Let an old one think. Come back."
  ]
}
```

---

## Prompt Versioning Policy

When a prompt template is changed:
1. Increment the version string in this file (e.g., v1.0 → v1.1).
2. Update `prompt_builder.py` to reference the new version.
3. Log the version in every LLM call: `logger.info("llm_call", prompt_version="v1.1", ...)`.
4. Add a migration note below describing what changed and why.

### Migration Log

| Version | Date | Change |
|---|---|---|
| v1.0 | 2024-01-01 | Initial template |
