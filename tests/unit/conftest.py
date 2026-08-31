"""
Module: conftest (tests/unit)
Layer: test (unit)
Purpose: Enforce the "unit tests do no I/O, no DB, no network" rule for everything
         under tests/unit/ by blocking real socket connects for the whole session.
Dependencies: pytest, socket, threading.
Used by: pytest — collected automatically for every test under tests/unit/.

Why a socket patch and not an httpx patch: httpx is imported lazily inside three
separate function bodies in evals/engine_adapter.py, so a module-attribute patch would
miss a future fourth. Every outbound TCP call funnels through socket.socket.connect
regardless of which client library makes it.

Why socketpair() is exempt: on Windows asyncio has no os-level socketpair, so every
event loop builds its wakeup self-pipe out of a loopback socket pair. Those connects
are process-internal by construction — they never leave the machine and never reach a
service — so permitting them inside socket.socketpair() costs nothing. The exemption is
scoped to that one call, not to loopback addresses in general; a probe of
http://localhost:11434 is still blocked, which is the whole point.
"""

from __future__ import annotations

import socket
import threading
from typing import Any, Iterator

import pytest

_REAL_CONNECT = socket.socket.connect
_REAL_SOCKETPAIR = socket.socketpair
_permitted = threading.local()


class NetworkAccessInUnitTestError(RuntimeError):
    """Raised when a unit test attempts a real network connection.

    Unit tests must mock all infrastructure (CLAUDE.md, "Test layout"). A live call
    makes the test slow and dependent on a service being up — the exact failure mode
    R2.1 fixes, where tests/unit/evals/test_run_config.py spent 152 s probing an
    absent Ollama. Inject a fake for the dependency instead of reaching the network.
    """

    def __init__(self, address: Any) -> None:
        self.address = address
        super().__init__(
            f"Unit test attempted a network connection to {address!r}. Unit tests "
            f"must not perform I/O — inject a fake or stub for this dependency."
        )


def _blocked_connect(self: socket.socket, address: Any) -> Any:
    if getattr(_permitted, "socketpair", False):
        return _REAL_CONNECT(self, address)
    raise NetworkAccessInUnitTestError(address)


def _permitted_socketpair(*args: Any, **kwargs: Any) -> Any:
    """Run socket.socketpair() with the connect block lifted for this thread only."""
    _permitted.socketpair = True
    try:
        return _REAL_SOCKETPAIR(*args, **kwargs)
    finally:
        _permitted.socketpair = False


@pytest.fixture(scope="session", autouse=True)
def _no_network() -> Iterator[None]:
    """Block real socket connects for the duration of the unit-test session."""
    socket.socket.connect = _blocked_connect  # type: ignore[method-assign]
    socket.socketpair = _permitted_socketpair  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = _REAL_CONNECT  # type: ignore[method-assign]
        socket.socketpair = _REAL_SOCKETPAIR  # type: ignore[assignment]
