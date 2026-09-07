"""
test_dialogue_generation_schema.py - The grammar handed to the model carries only the
fields the model actually authors.

Why this exists: decode is ~97% of a warm dialogue turn (measured 2026-09-07: 3.4-4.1s of
a 3.49-4.18s turn, against a prefix-cached 0.05s prefill), and decode scales with tokens
emitted. The model was handed the full DialogueResponse grammar -- 13 fields, ~6KB,
including $defs for ContextReceipt, DroppedItem and TierSpend, and audio_bytes offered as
a binary string. Seven of those fields are overwritten by the handler's model_copy after
generation, so every token spent on them is provably discarded.

DialogueResponse itself is unchanged: it is the published HTTP schema (api/schemas.py) and
is pinned by scripts/api_contract_baseline.json, so the generation model is a separate
class rather than a base or a subset of it.

Does NOT: call an LLM, or assert latency.

Dependencies injected: None.
"""

from __future__ import annotations

from npc_engine.engines.dialogue.dialogue_models import DialogueGeneration, DialogueResponse
from npc_engine.engines.dialogue.response_parser import parse_dialogue_response

# Written by the handler after generation, never usefully by the model.
_SERVER_POPULATED_FIELDS = (
    "emotion",
    "memories_recalled",
    "session_id",
    "cached",
    "degradation_level",
    "audio_bytes",
    "context_receipt",
)

# What the model is actually asked for, and what the prompt's Output rules describe.
_AUTHORED_FIELDS = (
    "npc_response",
    "relation_deltas",
    "mood_update",
    "action",
    "facial_expression",
    "learned_facts",
)


def test_the_generation_schema_carries_every_authored_field() -> None:
    """Cutting a field the model authors would silently drop a downstream behaviour."""
    properties = DialogueGeneration.model_json_schema()["properties"]

    assert set(properties) == set(_AUTHORED_FIELDS)


def test_the_generation_schema_omits_server_populated_fields() -> None:
    """Tokens spent on these are discarded by the handler's model_copy."""
    properties = DialogueGeneration.model_json_schema()["properties"]

    for field in _SERVER_POPULATED_FIELDS:
        assert field not in properties, f"{field} is overwritten server-side"


def test_the_generation_schema_carries_no_observability_definitions() -> None:
    """ContextReceipt and friends are eval plumbing; the NPC has no business knowing them."""
    definitions = DialogueGeneration.model_json_schema().get("$defs", {})

    assert "ContextReceipt" not in definitions
    assert "DroppedItem" not in definitions
    assert "TierSpend" not in definitions


def test_the_generation_schema_is_materially_smaller() -> None:
    """The saving is the point; a schema no smaller than before would be churn."""
    import json

    generation = len(json.dumps(DialogueGeneration.model_json_schema()))
    response = len(json.dumps(DialogueResponse.model_json_schema()))

    assert generation < response / 2


def test_only_npc_response_is_required() -> None:
    """Matches DialogueResponse: the model must always speak, everything else is optional."""
    assert DialogueGeneration.model_json_schema()["required"] == ["npc_response"]


def test_the_echo_prefix_stripper_still_applies_to_generated_text() -> None:
    """The model sometimes prepends a transcript label; that guard lives on the input side."""
    generated = DialogueGeneration.model_validate(
        {"npc_response": "player: hello\nnpc: Well met, traveller."}
    )

    assert generated.npc_response == "Well met, traveller."


def test_a_generated_payload_still_parses_into_a_full_response() -> None:
    """The handler builds DialogueResponse from this dict, so defaults must cover the rest."""
    generated = DialogueGeneration.model_validate(
        {"npc_response": "Well met.", "mood_update": "wary"}
    )

    response = parse_dialogue_response(payload=generated.model_dump(mode="python"))

    assert isinstance(response, DialogueResponse)
    assert response.npc_response == "Well met."
    assert response.session_id is None
    assert response.cached is False
    assert response.degradation_level == "full"
    assert response.memories_recalled == ()


def test_emotion_is_still_derived_from_mood_update() -> None:
    """emotion is dropped from the grammar because the response model derives it."""
    generated = DialogueGeneration.model_validate(
        {"npc_response": "Well met.", "mood_update": "wary"}
    )

    response = parse_dialogue_response(payload=generated.model_dump(mode="python"))

    assert response.emotion == "wary"
