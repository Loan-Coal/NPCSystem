"""
test_route_helpers.py - Unit tests for the canonical API response envelopes.

Covers S20.1: OkEnvelope[T] (generic success envelope) and ErrEnvelope
(documented error envelope) used as route `response_model` for typed OpenAPI
bodies. Also asserts the runtime `ok_response()` dict path is unchanged.

Does NOT: touch Neo4j, FastAPI app wiring, or any I/O.
"""

from __future__ import annotations

from pydantic import BaseModel

from npc_engine.api.route_helpers import ErrEnvelope, OkEnvelope, ok_response


class _Payload(BaseModel):
    """Minimal payload model for parametrising the generic envelope."""

    value: int


def test_ok_envelope_is_generic_and_validates_typed_data():
    """OkEnvelope[_Payload] should validate a typed data field and default success/meta."""
    env = OkEnvelope[_Payload](data=_Payload(value=7))
    assert env.success is True
    assert env.data.value == 7
    assert env.meta is None


def test_ok_envelope_accepts_meta():
    """meta is an optional dict carried through unchanged."""
    env = OkEnvelope[_Payload](data=_Payload(value=1), meta={"page": 2})
    assert env.meta == {"page": 2}


def test_ok_envelope_rejects_wrong_typed_data():
    """A payload that does not match the type parameter must fail validation."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OkEnvelope[_Payload](data={"value": "not-an-int"})


def test_err_envelope_defaults_success_false():
    """ErrEnvelope carries success=False plus error/message; detail optional."""
    err = ErrEnvelope(error="not_found", message="Resource not found")
    assert err.success is False
    assert err.error == "not_found"
    assert err.message == "Resource not found"
    assert err.detail is None


def test_ok_response_runtime_dict_unchanged():
    """ok_response() must still return a plain dict (no runtime behaviour change)."""
    result = ok_response({"belief_id": "b1"})
    assert result == {"success": True, "data": {"belief_id": "b1"}, "meta": None}
    assert isinstance(result, dict)
