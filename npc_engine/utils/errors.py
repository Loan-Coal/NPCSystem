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
