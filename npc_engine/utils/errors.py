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
