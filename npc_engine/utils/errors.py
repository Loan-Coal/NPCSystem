"""
errors.py - Defines custom exception types for domain and boundary failures.

Does NOT: map errors to HTTP responses or log exceptions.

Dependencies injected: None.
"""

from dataclasses import dataclass


class NPCSystemError(Exception):
    """Base class for all project-specific exceptions."""


class StructuredNPCSystemError(NPCSystemError):
    """Base class that provides a stable ClassName(field=value, ...) string."""

    def __str__(self) -> str:
        details = ", ".join(f"{field_name}={field_value}" for field_name, field_value in self.__dict__.items())
        return f"{self.__class__.__name__}({details})"


@dataclass(frozen=True)
class AuthError(StructuredNPCSystemError):
    """Raised when API key validation fails."""

    reason: str


@dataclass(frozen=True)
class GraphUnavailableError(StructuredNPCSystemError):
    """Raised when the graph database is not reachable."""

    uri: str
    cause: str


@dataclass(frozen=True)
class LLMTimeoutError(StructuredNPCSystemError):
    """Raised when an LLM call exceeds its timeout contract."""

    model: str
    timeout_s: float


@dataclass(frozen=True)
class LLMRequestError(StructuredNPCSystemError):
    """Raised when LLM transport or response parsing fails."""

    model: str
    detail: str


@dataclass(frozen=True)
class RelationEdgeNotFoundError(StructuredNPCSystemError):
    """Raised when a directed RELATES_TO edge is missing."""

    src_id: str
    dst_id: str


@dataclass(frozen=True)
class SchemaMisconfiguredError(StructuredNPCSystemError):
    """Raised when the schema file path or file content is invalid."""

    schema_path: str
    detail: str


@dataclass(frozen=True)
class SchemaValidationError(StructuredNPCSystemError):
    """Raised when schema content violates the meta-schema contract."""

    schema_path: str
    detail: str


@dataclass(frozen=True)
class NodeNotFoundError(StructuredNPCSystemError):
    """Raised when a graph node is not found for a requested operation."""

    node_type: str
    node_id: str


@dataclass(frozen=True)
class ImmutableFieldError(StructuredNPCSystemError):
    """Raised when a patch request tries to change immutable fields."""

    field_name: str
    node_type: str


@dataclass(frozen=True)
class IdempotencyKeyRequiredError(StructuredNPCSystemError):
    """Raised when a mutating request omits the required idempotency header."""

    header_name: str


@dataclass(frozen=True)
class IdempotencyKeyInvalidError(StructuredNPCSystemError):
    """Raised when the idempotency header value is not a valid UUIDv4 string."""

    header_name: str
    value: str


@dataclass(frozen=True)
class LLMConfigMisconfiguredError(StructuredNPCSystemError):
    """Raised when llm_config file path is missing or unreadable."""

    config_path: str
    detail: str


@dataclass(frozen=True)
class LLMConfigValidationError(StructuredNPCSystemError):
    """Raised when llm_config content violates the expected schema."""

    config_path: str
    detail: str


@dataclass(frozen=True)
class ContractValidationError(StructuredNPCSystemError):
    """Raised when an engine contract file cannot be parsed or validated."""

    contract_path: str
    detail: str


@dataclass(frozen=True)
class CurrencyValidationError(StructuredNPCSystemError):
    """Raised when requested currency mutation violates configured bounds."""

    code: str
    detail: str


@dataclass(frozen=True)
class CurrencyInsufficientFundsError(StructuredNPCSystemError):
    """Raised when transfer source balance cannot satisfy a debit."""

    source_id: str
    amount: int
    available_balance: int


@dataclass
class ItemTransferValidationError(StructuredNPCSystemError):
    """Raised when requested item transfer violates write guard conditions."""

    code: str
    detail: str


@dataclass
class QuestTransitionError(StructuredNPCSystemError):
    """Raised when quest lifecycle transition preconditions are not met."""

    code: str
    detail: str


@dataclass
class QuestProvenanceError(StructuredNPCSystemError):
    """Raised when quest lifecycle event provenance payload is incomplete."""

    detail: str
