"""
test_errors_machinery.py - Regression for the frozen-exception traceback bug.

Domain exceptions are @dataclass(frozen=True). Python's exception machinery (and
asyncio/concurrent.futures when an exception crosses an executor or await
boundary) assigns __traceback__/__cause__/__context__ EXPLICITLY. frozen=True
blocks that with FrozenInstanceError ("cannot assign to field '__traceback__'"),
which surfaced as HTTP 500 on the dialogue LLM-error/degradation path instead of
a graceful fallback.

These tests assert every frozen StructuredNPCSystemError subclass accepts the
exception-machinery attributes while still rejecting assignment to its own
declared fields (immutability preserved).

Does NOT: touch I/O.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from npc_engine.utils import errors
from npc_engine.utils.errors import LLMTimeoutError, StructuredNPCSystemError

_MACHINERY_ATTRS = ("__traceback__", "__cause__", "__context__")


def _frozen_exception_classes() -> list[type]:
    """All concrete frozen StructuredNPCSystemError subclasses defined in errors.py."""
    out: list[type] = []
    for value in vars(errors).values():
        if (
            isinstance(value, type)
            and issubclass(value, StructuredNPCSystemError)
            and is_dataclass(value)
        ):
            out.append(value)
    return out


def _instantiate(cls: type) -> Exception:
    """Build an instance of a frozen exception dataclass with dummy field values."""
    kwargs = {f.name: f"_{f.name}" for f in fields(cls)}  # type: ignore[arg-type]
    return cls(**kwargs)  # type: ignore[call-arg]


@pytest.mark.parametrize("attr", _MACHINERY_ATTRS)
def test_llm_timeout_error_accepts_machinery_attr(attr: str) -> None:
    exc = LLMTimeoutError(model="qwen2.5:14b", timeout_s=30.0)
    # The contract is that frozen=True does not block these — i.e. no
    # FrozenInstanceError.
    setattr(exc, attr, None)
    assert getattr(exc, attr) is None


def test_suppress_context_is_not_frozen() -> None:
    """__suppress_context__ (a bool BaseException getset) must also be settable."""
    exc = LLMTimeoutError(model="qwen2.5:14b", timeout_s=30.0)
    exc.__suppress_context__ = True  # must NOT raise FrozenInstanceError
    assert exc.__suppress_context__ is True


def test_all_frozen_exceptions_accept_traceback() -> None:
    classes = _frozen_exception_classes()
    assert classes, "expected to discover frozen exception classes"
    for cls in classes:
        exc = _instantiate(cls)
        try:
            exc.__traceback__ = None
            exc.__cause__ = None
            exc.__context__ = None
        except FrozenInstanceError as err:  # pragma: no cover - the bug
            pytest.fail(f"{cls.__name__} blocked exception machinery: {err}")


def test_declared_fields_remain_immutable() -> None:
    """The fix must not break frozen-ness: declared fields still reject assignment."""
    exc = LLMTimeoutError(model="qwen2.5:14b", timeout_s=30.0)
    with pytest.raises(FrozenInstanceError):
        exc.model = "other"  # type: ignore[misc]
