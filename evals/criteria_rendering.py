"""
Module: criteria_rendering
Layer: evals (eval harness — not part of src/)
Purpose: Render a deterministic matcher's expectation dict into the human-readable
         criteria string a labeller needs, and surface the response fields that
         matcher actually inspects. Deterministic GenerationRecords carry
         criteria="" (the field is reserved for LLM-judge prompts) and keep their
         real parameters in metadata["expectation"]; without this module those
         records export as unlabelable blanks.
Dependencies: typing, matchers (MIN_GUARD_RESPONSE_CHARS, _get_nested)
Used by: label_export (batch construction for the calibration labelling pass)
Does NOT: call the LLM judge, call /v1/dialogue, decide verdicts

Rendering fidelity: every string here must describe what matchers.py actually
does, including its case-insensitivity and substring (not word-boundary)
semantics. A rendering that overstates the matcher produces labels calibrated
against a scorer that does not exist.
"""

from __future__ import annotations

from typing import Any, Mapping

from matchers import MIN_GUARD_RESPONSE_CHARS, _get_nested

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mirrors matchers._eval_schema's bare-schema branch.
SCHEMA_REQUIRED_FIELDS: tuple[str, ...] = (
    "npc_response",
    "relation_deltas",
    "action",
    "facial_expression",
)

_GROUNDED_KIND: str = "anti_hallucination_grounded"

# Matcher kinds whose verdict depends on a response field other than npc_response.
_FIELD_MATCHERS: frozenset[str] = frozenset({"in_set", "range"})


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnknownMatcherKindError(ValueError):
    """Raised when a matcher kind has no rendering rule.

    A silent empty string here would reintroduce the unlabelable-batch bug,
    so an unmapped kind fails loudly instead.

    Attributes:
        kind: The unrecognised matcher kind.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(
            f"No criteria rendering rule for matcher kind {kind!r}. "
            f"Add one to criteria_rendering so the labelling batch stays labelable."
        )


# ---------------------------------------------------------------------------
# Per-kind renderers
# ---------------------------------------------------------------------------


def _quote_terms(terms: object) -> str:
    """Render a keyword list as a comma-separated quoted series."""
    if not isinstance(terms, (list, tuple)) or not terms:
        return "(none configured)"
    return ", ".join(f"'{t}'" for t in terms)


def _render_schema(exp: Mapping[str, Any]) -> str:
    field = exp.get("field")
    if field is None:
        fields = ", ".join(f"`{f}`" for f in SCHEMA_REQUIRED_FIELDS)
        return (
            f"The response must contain all required fields ({fields}), each non-null, "
            f"and `npc_response` must not be empty or whitespace-only."
        )
    return f"The response must contain the field `{field}` with a non-null value."


def _render_min_length(exp: Mapping[str, Any]) -> str:
    minimum = exp.get("min", MIN_GUARD_RESPONSE_CHARS)
    return (
        f"The NPC response, once trimmed of surrounding whitespace, must be at least "
        f"{minimum} characters long."
    )


def _render_keyword_any(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must contain at least one of these terms "
        f"(case-insensitive substring match): {_quote_terms(exp.get('keywords'))}."
    )


def _render_keyword_all(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must contain every one of these terms "
        f"(case-insensitive substring match): {_quote_terms(exp.get('keywords'))}."
    )


def _render_keyword_none(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must contain none of these forbidden terms "
        f"(case-insensitive substring match): {_quote_terms(exp.get('keywords'))}."
    )


def _render_in_set(exp: Mapping[str, Any]) -> str:
    values = ", ".join(repr(v) for v in exp.get("values", [])) or "(none configured)"
    return f"The response field `{exp.get('field', '')}` must be one of: {values}."


def _render_range(exp: Mapping[str, Any]) -> str:
    return (
        f"The response field `{exp.get('field', '')}` must be numeric and fall within "
        f"[{exp.get('min')}, {exp.get('max')}] inclusive."
    )


def _render_substring(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must contain the substring '{exp.get('substring', '')}' "
        f"(case-insensitive)."
    )


def _render_regex(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must match the regular expression `{exp.get('pattern', '')}` "
        f"(case-insensitive search)."
    )


def _render_context_block_expected(exp: Mapping[str, Any]) -> str:
    return (
        f"The prompt context block assembled for this turn must contain every one of "
        f"these strings: {_quote_terms(exp.get('expected_strings'))}."
    )


def _render_grounded(exp: Mapping[str, Any]) -> str:
    return (
        f"The NPC response must be grounded in the world facts it is allowed to know: it must "
        f"contain at least one of these substrings (case-insensitive): "
        f"{_quote_terms(exp.get('expected_fact_substrings'))}."
    )


_RENDERERS: dict[str, Any] = {
    "schema": _render_schema,
    "min_length": _render_min_length,
    "keyword_any": _render_keyword_any,
    "keyword_all": _render_keyword_all,
    "keyword_none": _render_keyword_none,
    "in_set": _render_in_set,
    "range": _render_range,
    "substring": _render_substring,
    "regex": _render_regex,
    "context_block_expected": _render_context_block_expected,
    _GROUNDED_KIND: _render_grounded,
}


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def render_criteria(scorer: str, expectation: Mapping[str, Any]) -> str:
    """Render a deterministic matcher's expectation into a labelable criteria sentence.

    Args:
        scorer: The matcher kind (e.g. 'keyword_none', 'in_set').
        expectation: The raw expectation dict stored in the record's metadata.
    Returns:
        A human-readable criteria string describing exactly what the matcher checks.
    Raises:
        UnknownMatcherKindError: If the kind has no rendering rule.
    """
    renderer = _RENDERERS.get(scorer)
    if renderer is None:
        raise UnknownMatcherKindError(scorer)
    return str(renderer(expectation))


def observed_fields(
    scorer: str,
    expectation: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract the response fields a matcher inspects beyond npc_response.

    in_set, range, and schema judge structured fields (facial_expression.type,
    relation_deltas.trust, …) that are absent from output_text. Without these a
    labeller cannot evaluate the criteria at all.

    Args:
        scorer: The matcher kind.
        expectation: The raw expectation dict.
        response: The full /v1/dialogue response body stored alongside the record.
    Returns:
        Mapping of field path to observed value; empty for text-only matchers.
        A field missing from the response resolves to None rather than raising.
    """
    if scorer in _FIELD_MATCHERS:
        field = expectation.get("field", "")
        return {field: _get_nested(dict(response), field)}

    if scorer == "schema":
        field = expectation.get("field")
        if field is not None:
            return {field: _get_nested(dict(response), field)}
        return {f: _get_nested(dict(response), f) for f in SCHEMA_REQUIRED_FIELDS}

    return {}
