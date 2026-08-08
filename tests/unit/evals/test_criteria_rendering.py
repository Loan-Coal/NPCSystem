"""
Module: test_criteria_rendering
Layer: test (unit)
Purpose: Unit tests for criteria_rendering.py — every deterministic matcher kind
         renders a non-empty, human-labelable criteria string, and the response
         fields a non-text matcher actually inspects are surfaced via
         observed_fields so a labeller can see what is being judged.
Dependencies: pytest, criteria_rendering (evals/), matchers (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from criteria_rendering import observed_fields, render_criteria
from eval_records import DeterministicMatcherKind
from matchers import MIN_GUARD_RESPONSE_CHARS
from typing import get_args

_RESPONSE = {
    "npc_response": "I've heard the war can be harsh on families like yours.",
    "relation_deltas": {"trust": 3},
    "action": {"type": "none"},
    "facial_expression": {"type": "sad"},
}


def test_every_deterministic_kind_renders_non_empty_criteria() -> None:
    """No deterministic matcher kind may render an empty criteria string.

    This is the regression guard for the original bug: label_export emitted
    criteria="" for all 576 deterministic records, making them unlabelable.
    """
    expectations: dict[str, dict] = {
        "schema": {"kind": "schema"},
        "min_length": {"kind": "min_length"},
        "keyword_any": {"kind": "keyword_any", "keywords": ["a", "b"]},
        "keyword_all": {"kind": "keyword_all", "keywords": ["a", "b"]},
        "keyword_none": {"kind": "keyword_none", "keywords": ["a", "b"]},
        "in_set": {"kind": "in_set", "field": "facial_expression.type", "values": ["sad"]},
        "range": {"kind": "range", "field": "relation_deltas.trust", "min": -5, "max": 10},
        "substring": {"kind": "substring", "substring": "war"},
        "regex": {"kind": "regex", "pattern": "^I"},
        "context_block_expected": {"kind": "context_block_expected", "expected_strings": ["x"]},
        "anti_hallucination_grounded": {"expected_fact_substrings": ["war", "north"]},
    }
    for kind in get_args(DeterministicMatcherKind):
        assert kind in expectations, f"no rendering fixture for matcher kind {kind!r}"
        rendered = render_criteria(kind, expectations[kind])
        assert rendered.strip(), f"{kind} rendered an empty criteria string"


def test_min_length_uses_configured_minimum() -> None:
    """min_length renders the explicit min when present."""
    assert "40" in render_criteria("min_length", {"kind": "min_length", "min": 40})


def test_min_length_falls_back_to_matcher_default() -> None:
    """min_length with no explicit min renders matchers.MIN_GUARD_RESPONSE_CHARS."""
    rendered = render_criteria("min_length", {"kind": "min_length"})
    assert str(MIN_GUARD_RESPONSE_CHARS) in rendered


def test_keyword_none_lists_every_forbidden_term() -> None:
    """keyword_none names each forbidden term so the labeller can check them."""
    rendered = render_criteria(
        "keyword_none", {"kind": "keyword_none", "keywords": ["talk to lira", "the fence is"]}
    )
    assert "talk to lira" in rendered
    assert "the fence is" in rendered


def test_in_set_names_field_and_allowed_values() -> None:
    """in_set renders both the response field path and the allowed value set."""
    rendered = render_criteria(
        "in_set", {"kind": "in_set", "field": "facial_expression.type", "values": ["sad", "neutral"]}
    )
    assert "facial_expression.type" in rendered
    assert "sad" in rendered and "neutral" in rendered


def test_range_names_field_and_bounds() -> None:
    """range renders the field path and both numeric bounds."""
    rendered = render_criteria(
        "range", {"kind": "range", "field": "relation_deltas.trust", "min": -5, "max": 10}
    )
    assert "relation_deltas.trust" in rendered
    assert "-5" in rendered and "10" in rendered


def test_observed_fields_surfaces_in_set_value() -> None:
    """in_set judges a response field, not npc_response — that value must be exposed."""
    observed = observed_fields(
        "in_set", {"kind": "in_set", "field": "facial_expression.type", "values": ["sad"]}, _RESPONSE
    )
    assert observed == {"facial_expression.type": "sad"}


def test_observed_fields_surfaces_range_value() -> None:
    """range judges a numeric response field — that value must be exposed."""
    observed = observed_fields(
        "range", {"kind": "range", "field": "relation_deltas.trust", "min": -5, "max": 10}, _RESPONSE
    )
    assert observed == {"relation_deltas.trust": 3}


def test_observed_fields_surfaces_schema_required_fields() -> None:
    """Bare schema checks four required fields — all must be exposed for labelling."""
    observed = observed_fields("schema", {"kind": "schema"}, _RESPONSE)
    for field in ("npc_response", "relation_deltas", "action", "facial_expression"):
        assert field in observed


def test_observed_fields_empty_for_text_only_matchers() -> None:
    """Text matchers judge npc_response, already carried as output_text — no extra fields."""
    assert observed_fields("keyword_none", {"kind": "keyword_none", "keywords": ["a"]}, _RESPONSE) == {}
    assert observed_fields("min_length", {"kind": "min_length"}, _RESPONSE) == {}


def test_observed_fields_handles_missing_field_without_raising() -> None:
    """A field absent from the response resolves to None rather than raising."""
    observed = observed_fields(
        "in_set", {"kind": "in_set", "field": "nope.missing", "values": ["x"]}, _RESPONSE
    )
    assert observed == {"nope.missing": None}


def test_render_criteria_rejects_unknown_kind() -> None:
    """An unrecognised matcher kind is a configuration error, not a silent empty string."""
    with pytest.raises(ValueError):
        render_criteria("not_a_real_matcher", {})
