"""
test_common_json_utils.py - Unit tests for shared JSON utility helpers.

Does NOT: validate domain-specific schemas.

Dependencies injected: None.
"""

from common.json_utils import dump_json, parse_json_list, parse_json_object


def test_parse_json_object_accepts_native_dict() -> None:
    """Native dict payloads should be returned unchanged."""

    payload = {"faction": 5}
    assert parse_json_object(payload) == payload


def test_parse_json_object_parses_json_string_and_falls_back() -> None:
    """String object payloads should parse; invalid JSON should return empty dict."""

    assert parse_json_object('{"faction": 10}') == {"faction": 10}
    assert parse_json_object("not-json") == {}
    assert parse_json_object("[1,2,3]") == {}


def test_parse_json_list_accepts_native_list() -> None:
    """Native list payloads should be returned unchanged."""

    payload = ["storm", "night"]
    assert parse_json_list(payload) == payload


def test_parse_json_list_parses_json_string_and_falls_back() -> None:
    """String list payloads should parse; invalid JSON should return empty list."""

    assert parse_json_list('["rain", "fog"]') == ["rain", "fog"]
    assert parse_json_list("not-json") == []
    assert parse_json_list('{"k": "v"}') == []


def test_dump_json_serializes_payload() -> None:
    """Helper should delegate to JSON serialization consistently."""

    assert dump_json({"weather": "clear"}) == '{"weather": "clear"}'
