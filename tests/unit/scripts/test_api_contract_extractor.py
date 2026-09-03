"""
Module: tests.unit.scripts.test_api_contract_extractor
Layer: tests
Purpose: Pin the properties the R5.1 gate depends on — WebSocket coverage, prefix
         templating, prose stripping and determinism — plus the pure encoders.
Dependencies: pathlib, sys, api_contract_extractor, api_contract_models
Used by: make test (pytest discovery), make check via test-cov

The WebSocket assertion is the load-bearing one. app.openapi() contains 0 WebSocket
entries while app.routes contains one (/v1/ws/dialogue), so a gate built on OpenAPI
alone would let the streaming route be deleted in silence. Measured during R5.1:
renaming that route is caught only because operations come from app.routes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from api_contract_extractor import (  # noqa: E402
    build_contract,
    canonical_type,
    encode_schema,
    ref_name,
    template_path,
)
from api_contract_models import PREFIX_PLACEHOLDER  # noqa: E402


def test_template_path_replaces_only_a_leading_prefix() -> None:
    assert template_path("/v1/npc/state", "/v1") == f"{PREFIX_PLACEHOLDER}/npc/state"
    assert template_path("/health", "/v1") == "/health"


def test_ref_name_reads_direct_union_and_array_references() -> None:
    assert ref_name({"$ref": "#/components/schemas/Foo"}) == "Foo"
    assert ref_name({"anyOf": [{"type": "null"}, {"$ref": "#/components/schemas/Bar"}]}) == "Bar"
    assert ref_name({"items": {"$ref": "#/components/schemas/Baz"}}) == "Baz"
    assert ref_name({"type": "string"}) is None
    assert ref_name(None) is None


def test_canonical_type_ignores_constraints_and_prose() -> None:
    assert canonical_type({"type": "integer", "maximum": 100, "title": "Trust"}) == "integer"
    assert canonical_type({"$ref": "#/components/schemas/Mood"}) == "Mood"
    assert canonical_type({}) == "any"


def test_encode_schema_marks_required_and_collects_enums_and_refs() -> None:
    spec = encode_schema(
        "Sample",
        {
            "required": ["npc_id"],
            "properties": {
                "npc_id": {"type": "string"},
                "mood": {"type": "string", "enum": ["calm", "angry"]},
                "owner": {"$ref": "#/components/schemas/Character"},
            },
        },
    )
    assert spec.fields == {"npc_id": "string!", "mood": "string?", "owner": "Character?"}
    assert spec.enums == {"mood": ("angry", "calm")}
    assert spec.refs == ("Character",)


def test_contract_records_the_websocket_route_openapi_omits() -> None:
    contract = build_contract()
    websockets = [key for key in contract.operations if key.startswith("WEBSOCKET ")]
    assert websockets == [f"WEBSOCKET {PREFIX_PLACEHOLDER}/ws/dialogue"], (
        "the streaming route must be in the contract; app.openapi() does not list it"
    )


def test_contract_templates_the_version_prefix() -> None:
    contract = build_contract()
    literal = [key for key in contract.operations if "/v1/" in key]
    assert not literal, f"prefix left un-templated in {literal[:3]}"
    assert any(PREFIX_PLACEHOLDER in key for key in contract.operations)


def test_recorded_schemas_carry_only_contract_keys() -> None:
    """Prose cannot enter the record, because a SchemaSpec has nowhere to put it.

    Asserting on substrings would be wrong: "description" and "title" are real API
    field NAMES (CreateGoalRequest.description, QuestOfferRequest.title), so a naive
    substring check fails on correct output. The property that matters is structural.
    """
    contract = build_contract()
    for name, schema in contract.schemas.items():
        assert set(schema.model_dump().keys()) == {"name", "fields", "enums", "refs"}, name


def test_recorded_contract_is_far_smaller_than_the_raw_schema() -> None:
    """Prose is ~2/3 of app.openapi(); a baseline full of it trains blind re-recording."""
    import json

    from api_contract_extractor import build_app

    raw = len(json.dumps(build_app().openapi(), sort_keys=True))
    recorded = len(build_contract().model_dump_json())
    assert recorded < raw / 2, f"recorded {recorded} vs raw {raw}: prose is not being stripped"


def test_extraction_is_deterministic() -> None:
    assert build_contract().model_dump_json() == build_contract().model_dump_json()
