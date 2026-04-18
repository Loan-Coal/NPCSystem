"""
errors.py - Defines custom exception types for domain and boundary failures.

Does NOT: map errors to HTTP responses or log exceptions.

Dependencies injected: None.
"""

from dataclasses import dataclass


class NPCSystemError(Exception):
    """Base class for all project-specific exceptions."""


@dataclass(frozen=True)
class AuthError(NPCSystemError):
    """Raised when API key validation fails."""

    reason: str

    def __str__(self) -> str:
        return f"AuthError(reason={self.reason})"


@dataclass(frozen=True)
class GraphUnavailableError(NPCSystemError):
    """Raised when the graph database is not reachable."""

    uri: str
    cause: str

    def __str__(self) -> str:
        return f"GraphUnavailableError(uri={self.uri}, cause={self.cause})"


@dataclass(frozen=True)
class LLMTimeoutError(NPCSystemError):
    """Raised when an LLM call exceeds its timeout contract."""

    model: str
    timeout_s: float

    def __str__(self) -> str:
        return f"LLMTimeoutError(model={self.model}, timeout_s={self.timeout_s})"


@dataclass(frozen=True)
class LLMRequestError(NPCSystemError):
    """Raised when LLM transport or response parsing fails."""

    model: str
    detail: str

    def __str__(self) -> str:
        return f"LLMRequestError(model={self.model}, detail={self.detail})"


@dataclass(frozen=True)
class RelationEdgeNotFoundError(NPCSystemError):
    """Raised when a directed RELATES_TO edge is missing."""

    src_id: str
    dst_id: str

    def __str__(self) -> str:
        return f"RelationEdgeNotFoundError(src_id={self.src_id}, dst_id={self.dst_id})"


@dataclass(frozen=True)
class SchemaMisconfiguredError(NPCSystemError):
    """Raised when the schema file path or file content is invalid."""

    schema_path: str
    detail: str

    def __str__(self) -> str:
        return f"SchemaMisconfiguredError(schema_path={self.schema_path}, detail={self.detail})"


@dataclass(frozen=True)
class SchemaValidationError(NPCSystemError):
    """Raised when schema content violates the meta-schema contract."""

    schema_path: str
    detail: str

    def __str__(self) -> str:
        return f"SchemaValidationError(schema_path={self.schema_path}, detail={self.detail})"


@dataclass(frozen=True)
class NodeNotFoundError(NPCSystemError):
    """Raised when a graph node is not found for a requested operation."""

    node_type: str
    node_id: str

    def __str__(self) -> str:
        return f"NodeNotFoundError(node_type={self.node_type}, node_id={self.node_id})"


@dataclass(frozen=True)
class ImmutableFieldError(NPCSystemError):
    """Raised when a patch request tries to change immutable fields."""

    field_name: str
    node_type: str

    def __str__(self) -> str:
        return f"ImmutableFieldError(field_name={self.field_name}, node_type={self.node_type})"


@dataclass(frozen=True)
class IdempotencyKeyRequiredError(NPCSystemError):
    """Raised when a mutating request omits the required idempotency header."""

    header_name: str

    def __str__(self) -> str:
        return f"IdempotencyKeyRequiredError(header_name={self.header_name})"


@dataclass(frozen=True)
class IdempotencyKeyInvalidError(NPCSystemError):
    """Raised when the idempotency header value is not a valid UUIDv4 string."""

    header_name: str
    value: str

    def __str__(self) -> str:
        return f"IdempotencyKeyInvalidError(header_name={self.header_name}, value={self.value})"


@dataclass(frozen=True)
class LLMConfigMisconfiguredError(NPCSystemError):
    """Raised when llm_config file path is missing or unreadable."""

    config_path: str
    detail: str

    def __str__(self) -> str:
        return f"LLMConfigMisconfiguredError(config_path={self.config_path}, detail={self.detail})"


@dataclass(frozen=True)
class LLMConfigValidationError(NPCSystemError):
    """Raised when llm_config content violates the expected schema."""

    config_path: str
    detail: str

    def __str__(self) -> str:
        return f"LLMConfigValidationError(config_path={self.config_path}, detail={self.detail})"


@dataclass(frozen=True)
class ContractValidationError(NPCSystemError):
    """Raised when an engine contract file cannot be parsed or validated."""

    contract_path: str
    detail: str

    def __str__(self) -> str:
        return f"ContractValidationError(contract_path={self.contract_path}, detail={self.detail})"


@dataclass(frozen=True)
class CurrencyValidationError(NPCSystemError):
    """Raised when requested currency mutation violates configured bounds."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"CurrencyValidationError(code={self.code}, detail={self.detail})"


@dataclass(frozen=True)
class CurrencyInsufficientFundsError(NPCSystemError):
    """Raised when transfer source balance cannot satisfy a debit."""

    source_id: str
    amount: int
    available_balance: int

    def __str__(self) -> str:
        return (
            "CurrencyInsufficientFundsError("
            f"source_id={self.source_id}, amount={self.amount}, available_balance={self.available_balance})"
        )


@dataclass
class ItemTransferValidationError(NPCSystemError):
    """Raised when requested item transfer violates write guard conditions."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"ItemTransferValidationError(code={self.code}, detail={self.detail})"


@dataclass
class QuestTransitionError(NPCSystemError):
    """Raised when quest lifecycle transition preconditions are not met."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"QuestTransitionError(code={self.code}, detail={self.detail})"


@dataclass
class QuestProvenanceError(NPCSystemError):
    """Raised when quest lifecycle event provenance payload is incomplete."""

    detail: str

    def __str__(self) -> str:
        return f"QuestProvenanceError(detail={self.detail})"
