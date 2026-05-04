"""
test_errors.py - Unit tests for utils/errors.py.

Does NOT: test HTTP mapping or logging behavior.

Dependencies injected: None.
"""

# Tests for: utils.errors
# Coverage targets:
#   - StructuredNPCSystemError.__str__: field serialization format
#   - All dataclass exceptions: frozen immutability (STRUCT-06)
#   - All exceptions: NPCSystemError inheritance
#   - ItemTransferValidationError: frozen (was mutable — regression guard)
#   - QuestTransitionError: frozen (was mutable — regression guard)
#   - QuestProvenanceError: frozen (was mutable — regression guard)

import dataclasses
import pytest

from utils.errors import (
    AuthError,
    ContractValidationError,
    CurrencyInsufficientFundsError,
    CurrencyValidationError,
    GraphUnavailableError,
    IdempotencyKeyInvalidError,
    IdempotencyKeyRequiredError,
    ImmutableFieldError,
    ItemTransferValidationError,
    LLMConfigMisconfiguredError,
    LLMConfigValidationError,
    LLMRequestError,
    LLMTimeoutError,
    NodeNotFoundError,
    NPCSystemError,
    QuestProvenanceError,
    QuestTransitionError,
    RegistryPayloadValidationError,
    RegistryValidationError,
    RelationEdgeNotFoundError,
    SchemaMisconfiguredError,
    SchemaValidationError,
)


# ── inheritance ──────────────────────────────────────────────────────────────

def test_all_errors_are_npc_system_errors() -> None:
    """Every domain exception must be catchable via NPCSystemError."""
    for cls in (
        AuthError,
        GraphUnavailableError,
        LLMTimeoutError,
        LLMRequestError,
        RelationEdgeNotFoundError,
        SchemaMisconfiguredError,
        SchemaValidationError,
        RegistryValidationError,
        RegistryPayloadValidationError,
        NodeNotFoundError,
        ImmutableFieldError,
        IdempotencyKeyRequiredError,
        IdempotencyKeyInvalidError,
        LLMConfigMisconfiguredError,
        LLMConfigValidationError,
        ContractValidationError,
        CurrencyValidationError,
        CurrencyInsufficientFundsError,
        ItemTransferValidationError,
        QuestTransitionError,
        QuestProvenanceError,
    ):
        assert issubclass(cls, NPCSystemError), f"{cls.__name__} does not inherit NPCSystemError"


# ── __str__ format ────────────────────────────────────────────────────────────

def test_structured_str_serializes_all_fields() -> None:
    """__str__ must emit ClassName(field=value, ...) for every field."""
    error = GraphUnavailableError(uri="bolt://localhost:7687", cause="connection refused")
    result = str(error)
    assert result.startswith("GraphUnavailableError(")
    assert "uri=bolt://localhost:7687" in result
    assert "cause=connection refused" in result


def test_structured_str_single_field() -> None:
    """Single-field exceptions must still format correctly."""
    error = QuestProvenanceError(detail="missing quest_id")
    result = str(error)
    assert result == "QuestProvenanceError(detail=missing quest_id)"


def test_structured_str_numeric_fields() -> None:
    """Numeric fields must appear in the formatted string."""
    error = CurrencyInsufficientFundsError(source_id="npc_01", amount=500, available_balance=100)
    result = str(error)
    assert "amount=500" in result
    assert "available_balance=100" in result


# ── frozen enforcement (STRUCT-06) ────────────────────────────────────────────

def test_item_transfer_validation_error_is_frozen() -> None:
    """ItemTransferValidationError must be immutable after construction."""
    error = ItemTransferValidationError(code="ITEM_ID_REQUIRED", detail="item_id cannot be empty")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        error.code = "MUTATED"  # type: ignore[misc]


def test_quest_transition_error_is_frozen() -> None:
    """QuestTransitionError must be immutable after construction."""
    error = QuestTransitionError(code="INVALID_STATE", detail="quest not in active state")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        error.code = "MUTATED"  # type: ignore[misc]


def test_quest_provenance_error_is_frozen() -> None:
    """QuestProvenanceError must be immutable after construction."""
    error = QuestProvenanceError(detail="missing quest_id field")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        error.detail = "MUTATED"  # type: ignore[misc]


def test_auth_error_is_frozen() -> None:
    """AuthError must be immutable — verifies existing frozen exceptions are stable."""
    error = AuthError(reason="invalid api key")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        error.reason = "MUTATED"  # type: ignore[misc]


# ── field contracts ───────────────────────────────────────────────────────────

def test_llm_timeout_error_preserves_float_timeout() -> None:
    """LLMTimeoutError.timeout_s must accept and preserve float values."""
    error = LLMTimeoutError(model="mistral-7b", timeout_s=10.5)
    assert error.timeout_s == 10.5


def test_currency_insufficient_funds_preserves_int_fields() -> None:
    """CurrencyInsufficientFundsError must preserve all three integer fields."""
    error = CurrencyInsufficientFundsError(source_id="merchant_01", amount=1000, available_balance=0)
    assert error.source_id == "merchant_01"
    assert error.amount == 1000
    assert error.available_balance == 0


def test_node_not_found_error_preserves_type_and_id() -> None:
    """NodeNotFoundError must preserve node_type and node_id fields."""
    error = NodeNotFoundError(node_type="Character", node_id="npc_missing")
    assert error.node_type == "Character"
    assert error.node_id == "npc_missing"
