"""
errors.py - Defines custom exception types for domain and boundary failures.
Layer: config
Purpose: Defines custom exception types for domain and boundary failures.

Does NOT: map errors to HTTP responses or log exceptions.

Dependencies injected: None.
"""
# DEC-091 waiver: this file intentionally exceeds the 300-line limit. It is a flat
# catalog of ~35 one-class exception dataclasses sharing one base; splitting it would
# fragment a cohesive registry behind an exhaustive re-export hub with no encapsulation
# gain. Do not grow without a real split (a new error *family* with shared behaviour).
#
# Exception classes use @dataclass(frozen=True) for field immutability (STRUCT-06).
# _enable_exception_machinery() (called at module import, AFTER the dataclass decorator
# has installed each subclass's frozen __setattr__) wraps that __setattr__ so Python's
# exception machinery can still set __traceback__/__cause__/__context__ explicitly — as
# asyncio/concurrent.futures do when an exception crosses an executor or await boundary.
# Without it, frozen=True raises FrozenInstanceError there, surfacing as an HTTP 500 on
# the LLM-error/degradation path instead of a graceful fallback.
# All P1 deferred migrations completed as of service #17.

from __future__ import annotations

from dataclasses import dataclass


class NPCSystemError(Exception):
    """Base class for all project-specific exceptions."""


class StructuredNPCSystemError(NPCSystemError):
    """Base class that provides a stable ClassName(field=value, ...) string."""

    _EXCEPTION_MACHINERY_ATTRS: frozenset[str] = frozenset(
        {"__traceback__", "__cause__", "__context__", "__suppress_context__"}
    )

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


@dataclass(frozen=True)
class FactionNotFoundError(StructuredNPCSystemError):
    """Raised when a Faction node is not found for a requested operation."""

    faction_id: str


@dataclass(frozen=True)
class FactionMembershipError(StructuredNPCSystemError):
    """Raised when a membership operation cannot be completed (e.g. member not found)."""

    character_id: str
    faction_id: str
    detail: str


@dataclass(frozen=True)
class ReputationNotFoundError(StructuredNPCSystemError):
    """Raised when a HAS_REPUTATION_WITH edge is not found for a requested operation."""

    character_id: str
    faction_id: str


@dataclass(frozen=True)
class ScheduleNotFoundError(StructuredNPCSystemError):
    """Raised when a Schedule node is not found for a requested operation."""

    schedule_id: str


@dataclass(frozen=True)
class ScheduleAssignmentError(StructuredNPCSystemError):
    """Raised when a schedule assignment cannot be completed."""

    character_id: str
    schedule_id: str
    detail: str


@dataclass(frozen=True)
class TTSSynthesisError(StructuredNPCSystemError):
    """Raised when a TTS backend returns an error or times out during synthesis."""

    backend: str
    detail: str


@dataclass(frozen=True)
class ContentRatingViolationError(StructuredNPCSystemError):
    """Raised when player input exceeds the world's content rating ceiling.

    Attributes:
        player_id: The player who sent the over-ceiling message.
        rating: The effective content ceiling that was violated (e.g. 'everyone').
    """

    player_id: str
    rating: str


class TokenBudgetExceededError(Exception):
    """Raised when mandatory tier0 context alone exceeds the token budget."""


@dataclass
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


def _enable_exception_machinery(base: type) -> None:
    """Allow Python's exception machinery to set __traceback__/__cause__/__context__
    on every frozen StructuredNPCSystemError subclass.

    Wraps each subclass's @dataclass(frozen=True)-generated __setattr__ so the
    machinery attributes go through object.__setattr__ while declared fields stay
    immutable. Must run after the dataclass decorator has installed __setattr__,
    so it is invoked at module import (not in __init_subclass__, which runs before
    the decorator and therefore could never see the frozen __setattr__).
    """
    machinery = base._EXCEPTION_MACHINERY_ATTRS  # type: ignore[attr-defined]
    for cls in base.__subclasses__():
        frozen_setattr = cls.__setattr__
        if getattr(frozen_setattr, "_allows_machinery", False):
            continue

        def _patched(self: object, name: str, value: object, _orig: object = frozen_setattr) -> None:
            if name in machinery:
                object.__setattr__(self, name, value)
            else:
                _orig(self, name, value)  # type: ignore[operator]

        _patched._allows_machinery = True  # type: ignore[attr-defined]
        cls.__setattr__ = _patched  # type: ignore[assignment]
        _enable_exception_machinery(cls)


_enable_exception_machinery(StructuredNPCSystemError)
