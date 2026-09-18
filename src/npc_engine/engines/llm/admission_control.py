"""
Module: admission_control
Layer: engines
Purpose: Two-class LLM admission gate — interactive (dialogue, proactive) pre-empts
         background (tick-originated) callers. Background calls are shed, not queued,
         while any interactive call is pending or active.
Does NOT: perform generation, shape requests, or log. One arbitration point per SRP.
Dependencies injected: asyncio event loop (implicit).
Used by: engines.llm.factory (wraps every adapter at creation time).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any, AsyncGenerator, AsyncIterator, Literal

from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.utils.errors import LLMRequestError
from npc_engine.utils.metrics import observe_metric

LlmEngineClass = Literal["interactive", "background"]

LLM_BACKEND_QUEUE_WAIT_METRIC = "llm_backend_queue_wait_seconds"

# Engines whose calls are player-facing; all others are background (tick-originated).
INTERACTIVE_ENGINES: frozenset[str] = frozenset({"dialogue", "proactive_dialogue"})

_INTERACTIVE_RESERVE = 1


def classify_engine(engine_name: str) -> LlmEngineClass:
    """Return 'interactive' for player-facing engines, 'background' for tick-originated.

    Args:
        engine_name: The engine key from EngineModelConfig (e.g. 'dialogue').

    Returns:
        'interactive' if the engine is in INTERACTIVE_ENGINES, otherwise 'background'.
    """
    return "interactive" if engine_name in INTERACTIVE_ENGINES else "background"


class LLMAdmissionGate:
    """Two-class concurrency gate for LLM backend calls.

    Reserves one slot exclusively for interactive callers so a player-facing
    turn can always enter even when background slots are full. Background calls
    are shed (never queued) the moment any interactive call is pending or active.

    One shared instance should be created per process and reused across all
    engine adapters — see ``get_default_gate()``.

    Attributes:
        max_concurrent: Total backend slots including the interactive reserve.
    """

    def __init__(self, max_concurrent: int = 2) -> None:
        """Initialise the gate with total slot count (background + 1 reserve).

        Args:
            max_concurrent: Total concurrent LLM slots. Must be >= 2 so at least
                one background slot exists alongside the interactive reserve.

        Raises:
            ValueError: If max_concurrent < 2.
        """
        if max_concurrent < 2:
            raise ValueError(
                f"max_concurrent must be >= 2 (need ≥1 background + 1 interactive reserve);"
                f" got {max_concurrent}"
            )
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._background_max = max_concurrent - _INTERACTIVE_RESERVE
        self._interactive_count = 0
        self._background_held = 0

    @asynccontextmanager
    async def enter(self, engine_name: str) -> AsyncGenerator[None, None]:
        """Acquire a gate slot for the given engine, yield, then release.

        Interactive engines always get the reserved slot. Background engines are
        shed (``LLMRequestError(detail='admission_rejected')``) when any interactive
        call is pending or active, or when all background slots are occupied.

        Args:
            engine_name: Engine key used to classify the call class.

        Raises:
            LLMRequestError: When a background call is shed.
        """
        if classify_engine(engine_name) == "interactive":
            await self._acquire_interactive()
            try:
                yield
            finally:
                self._release_interactive()
        else:
            self._acquire_background_or_raise()
            try:
                t0 = perf_counter()
                await self._semaphore.acquire()
                observe_metric(
                    LLM_BACKEND_QUEUE_WAIT_METRIC,
                    perf_counter() - t0,
                    {"class": "background"},
                )
                yield
            finally:
                self._background_held -= 1
                self._semaphore.release()

    async def _acquire_interactive(self) -> None:
        self._interactive_count += 1
        t0 = perf_counter()
        await self._semaphore.acquire()
        observe_metric(
            LLM_BACKEND_QUEUE_WAIT_METRIC,
            perf_counter() - t0,
            {"class": "interactive"},
        )

    def _release_interactive(self) -> None:
        self._interactive_count -= 1
        self._semaphore.release()

    def _acquire_background_or_raise(self) -> None:
        """Synchronous pre-check; increments _background_held or raises."""
        if self._interactive_count > 0:
            observe_metric(LLM_BACKEND_QUEUE_WAIT_METRIC, 0.0, {"class": "background"})
            raise LLMRequestError(model="admission_gate", detail="admission_rejected")
        if self._background_held >= self._background_max:
            observe_metric(LLM_BACKEND_QUEUE_WAIT_METRIC, 0.0, {"class": "background"})
            raise LLMRequestError(model="admission_gate", detail="admission_rejected")
        self._background_held += 1


class GatedLLMAdapter:
    """LLMClientProtocol wrapper that routes every generation through the admission gate.

    All three generation methods (generate, generate_structured, stream) acquire the
    gate before delegating to the inner adapter. Non-generation methods (health_check,
    model_name) bypass the gate — they do not compete for the LLM backend slot.
    """

    def __init__(
        self,
        inner: LLMClientProtocol,
        gate: LLMAdmissionGate,
        engine_name: str,
    ) -> None:
        """Initialise the gated adapter.

        Args:
            inner: Concrete adapter to delegate generation calls to.
            gate: Shared admission gate instance.
            engine_name: Engine key used to classify this adapter's calls.
        """
        self._inner = inner
        self._gate = gate
        self._engine_name = engine_name

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Acquire gate slot then delegate to inner adapter's generate.

        Raises:
            LLMRequestError: If the call is a background call and is shed.
            LLMTimeoutError: Propagated from the inner adapter.
            LLMRequestError: Propagated from the inner adapter on backend errors.
        """
        async with self._gate.enter(self._engine_name):
            return await self._inner.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop_sequences=stop_sequences,
                system=system,
                seed=seed,
            )

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Acquire gate slot then delegate to inner adapter's generate_structured.

        Raises:
            LLMRequestError: If the call is a background call and is shed.
            LLMTimeoutError: Propagated from the inner adapter.
            LLMRequestError: Propagated from the inner adapter on backend errors.
        """
        async with self._gate.enter(self._engine_name):
            return await self._inner.generate_structured(
                prompt=prompt,
                schema=schema,
                max_tokens=max_tokens,
                top_p=top_p,
                stop_sequences=stop_sequences,
                system=system,
                seed=seed,
            )

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        """Acquire gate slot for the duration of the stream.

        Raises:
            LLMRequestError: If the call is a background call and is shed.
            LLMTimeoutError: Propagated from the inner adapter.
            LLMRequestError: Propagated from the inner adapter on stream errors.
        """
        async with self._gate.enter(self._engine_name):
            async for token in self._inner.stream(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop_sequences=stop_sequences,
                system=system,
                seed=seed,
            ):
                yield token

    async def health_check(self) -> bool:
        """Delegate health check without acquiring a gate slot.

        Returns:
            True if the backend is reachable, False otherwise.
        """
        return await self._inner.health_check()

    def model_name(self) -> str:
        """Return the inner adapter's model name.

        Returns:
            Model name string from the wrapped adapter.
        """
        return self._inner.model_name()

    async def close(self) -> None:
        """Delegate close to the inner adapter if it supports it."""
        close_fn = getattr(self._inner, "close", None)
        if close_fn is not None:
            await close_fn()


# ---------------------------------------------------------------------------
# Process-level gate singleton
# ---------------------------------------------------------------------------

_default_gate: LLMAdmissionGate | None = None


def get_default_gate(max_concurrent: int = 2) -> LLMAdmissionGate:
    """Return the process-level admission gate, creating it on first call.

    Args:
        max_concurrent: Passed only on the first call; ignored on subsequent calls.
            Use ``reset_default_gate()`` in tests to reset this.

    Returns:
        The shared LLMAdmissionGate instance.
    """
    global _default_gate
    if _default_gate is None:
        _default_gate = LLMAdmissionGate(max_concurrent=max_concurrent)
    return _default_gate


def reset_default_gate() -> None:
    """Replace the default gate with a fresh instance. Test isolation only."""
    global _default_gate
    _default_gate = None
