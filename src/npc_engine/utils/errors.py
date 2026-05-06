"""
errors.py - Defines custom exception types for domain and boundary failures.

Does NOT: map errors to HTTP responses or log exceptions.

Dependencies injected: None.
"""
# Exception classes use @dataclass(frozen=True) for field immutability (STRUCT-06).
# StructuredNPCSystemError.__init_subclass__ patches each frozen subclass's __setattr__
# to allow Python's exception machinery to set __traceback__, __cause__, and __context__,
# which frozen=True would otherwise block.
# All P1 deferred migrations completed as of service #17.

from dataclasses import dataclass


class NPCSystemError(Exception):
    """Base class for all project-specific exceptions."""


class StructuredNPCSystemError(NPCSystemError):
    """Base class that provides a stable ClassName(field=value, ...) string."""

    _EXCEPTION_MACHINERY_ATTRS: frozenset[str] = frozenset(
        {"__traceback__", "__cause__", "__context__", "__suppress_context__"}
    )

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        original_setattr = cls.__dict__.get("__setattr__")
        if original_setattr is None:
            return
        # Wrap the frozen __setattr__ so Python's exception machinery can still
        # set __traceback__, __cause__, and __context__ after raise.
        _machinery = StructuredNPCSystemError._EXCEPTION_MACHINERY_ATTRS

        def _patched_setattr(self: object, name: str, value: object, _orig: object = original_setattr) -> None:
            if name in _machinery:
                object.__setattr__(self, name, value)
            else:
                _orig(self, name, value)  # type: ignore[operator]

        cls.__setattr__ = _patched_setattr  # type: ignore[method-assign]

    def __str__(self) -> str:
        """Return 'ClassName(field=value, ...)' for all instance fields."""
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
class RegistryValidationError(StructuredNPCSystemError):
    """Raised when registry extension files fail validation or merge checks."""

    source: str
    detail: str


@dataclass(frozen=True)
class RegistryPayloadValidationError(StructuredNPCSystemError):
    """Raised when registry topology or payload validation fails at runtime."""

    code: str
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
class EngineModelConfigMisconfiguredError(StructuredNPCSystemError):
    """Raised when a per-engine llm_config file is missing or unreadable."""

    engine: str
    config_path: str
    detail: str


@dataclass(frozen=True)
class EngineModelConfigValidationError(StructuredNPCSystemError):
    """Raised when a per-engine llm_config file fails schema validation."""

    engine: str
    config_path: str
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


@dataclass(frozen=True)
class ItemTransferValidationError(StructuredNPCSystemError):
    """Raised when requested item transfer violates write guard conditions."""

    code: str
    detail: str


@dataclass(frozen=True)
class QuestTransitionError(StructuredNPCSystemError):
    """Raised when quest lifecycle transition preconditions are not met."""

    code: str
    detail: str


@dataclass(frozen=True)
class QuestProvenanceError(StructuredNPCSystemError):
    """Raised when quest lifecycle event provenance payload is incomplete."""

    detail: str


@dataclass(frozen=True)
class RelationDeltaExceededError(StructuredNPCSystemError):
    """Raised when requested relation delta exceeds configured per-turn or window bounds."""

    field: str
    requested_delta: int
    max_allowed: int
    context: str


class TokenBudgetExceededError(Exception):
    """Raised when mandatory tier0 context alone exceeds the token budget."""


@dataclass(frozen=True)
class ContextBudgetError(Exception):
    """Raised for tier-specific context budget overflow during prompt assembly."""

    tier: str
    used_tokens: int
    budget_tokens: int
    detail: str

    def __str__(self) -> str:
        """Return structured representation for logging and error propagation."""
        return (
            "ContextBudgetError("
            f"tier={self.tier}, used_tokens={self.used_tokens}, "
            f"budget_tokens={self.budget_tokens}, detail={self.detail})"
        )
