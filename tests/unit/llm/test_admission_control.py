"""
test_admission_control.py - Two-class LLM admission gate: interactive pre-empts background.

RED anchor (T8.1): all three assertions fail today because admission_control.py
does not exist.

Does NOT: call a live backend, assert on wall-clock latency, sleep.

Dependencies injected: asyncio events for task coordination.
"""
from __future__ import annotations

import asyncio

import pytest

from npc_engine.engines.llm.admission_control import (
    INTERACTIVE_ENGINES,
    LLM_BACKEND_QUEUE_WAIT_METRIC,
    LLMAdmissionGate,
    classify_engine,
)
from npc_engine.utils.errors import LLMRequestError
from npc_engine.utils.metrics import get_metrics_registry, reset_metrics_registry


def setup_function() -> None:
    reset_metrics_registry()


# ---------------------------------------------------------------------------
# classify_engine
# ---------------------------------------------------------------------------


def test_dialogue_is_interactive() -> None:
    assert classify_engine("dialogue") == "interactive"


def test_proactive_dialogue_is_interactive() -> None:
    assert classify_engine("proactive_dialogue") == "interactive"


def test_memory_consolidation_is_background() -> None:
    assert classify_engine("memory_consolidation") == "background"


def test_chapter_is_background() -> None:
    assert classify_engine("chapter") == "background"


def test_quest_generation_is_background() -> None:
    assert classify_engine("quest_generation") == "background"


def test_interactive_engines_constant_is_frozenset() -> None:
    assert isinstance(INTERACTIVE_ENGINES, frozenset)
    assert "dialogue" in INTERACTIVE_ENGINES
    assert "proactive_dialogue" in INTERACTIVE_ENGINES


# ---------------------------------------------------------------------------
# Bounded wait: N background calls in flight, interactive acquires reserved slot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interactive_acquires_reserved_slot_while_backgrounds_in_flight() -> None:
    """With max_concurrent=3 (2 background + 1 reserved), interactive enters
    the third slot immediately while 2 background calls hold the other two.
    Timing is asserted via event-loop ordering, not wall clock."""
    gate = LLMAdmissionGate(max_concurrent=3)

    n_holding = 0
    all_holding = asyncio.Event()
    release = asyncio.Event()

    async def hold_background() -> None:
        nonlocal n_holding
        async with gate.enter("memory_consolidation"):
            n_holding += 1
            if n_holding >= 2:
                all_holding.set()
            await release.wait()

    t1 = asyncio.create_task(hold_background())
    t2 = asyncio.create_task(hold_background())
    await all_holding.wait()  # both background slots are now occupied

    # Interactive should acquire the reserved slot without waiting for background
    acquired = False
    async with gate.enter("dialogue"):
        acquired = True

    assert acquired, "interactive call must acquire even with N background calls in flight"

    release.set()
    await asyncio.gather(t1, t2)


# ---------------------------------------------------------------------------
# Shedding: background shed rather than queued when interactive is active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_shed_when_interactive_active() -> None:
    """While an interactive call holds a slot, a background call must be
    rejected with LLMRequestError(detail='admission_rejected') — not queued."""
    gate = LLMAdmissionGate(max_concurrent=2)

    interactive_entered = asyncio.Event()
    interactive_release = asyncio.Event()

    async def interactive() -> None:
        async with gate.enter("dialogue"):
            interactive_entered.set()
            await interactive_release.wait()

    task = asyncio.create_task(interactive())
    await interactive_entered.wait()  # interactive is now active

    # Background call must be shed immediately
    with pytest.raises(LLMRequestError) as exc_info:
        async with gate.enter("memory_consolidation"):
            pass  # must not reach here

    assert exc_info.value.detail == "admission_rejected", (
        "gate must raise LLMRequestError(detail='admission_rejected') when shedding"
    )

    interactive_release.set()
    await task


@pytest.mark.asyncio
async def test_background_shed_when_interactive_pending() -> None:
    """While an interactive call is pending (waiting for a slot), newly arriving
    background calls must also be shed."""
    gate = LLMAdmissionGate(max_concurrent=2)

    # Fill the one background slot and the one interactive-reserved slot
    bg_release = asyncio.Event()
    interactive_release = asyncio.Event()
    interactive_entered = asyncio.Event()

    async def hold_background() -> None:
        async with gate.enter("memory_consolidation"):
            await bg_release.wait()

    async def interactive() -> None:
        async with gate.enter("dialogue"):
            interactive_entered.set()
            await interactive_release.wait()

    # 1. background fills its one slot
    bg_task = asyncio.create_task(hold_background())
    await asyncio.sleep(0)  # yield so background can acquire

    # 2. interactive is now pending (slot is taken by background)
    interactive_task = asyncio.create_task(interactive())
    await asyncio.sleep(0)  # yield so interactive increments _interactive_count

    # 3. another background call arrives while interactive is pending
    with pytest.raises(LLMRequestError) as exc_info:
        async with gate.enter("chapter"):
            pass

    assert exc_info.value.detail == "admission_rejected"

    bg_release.set()
    interactive_release.set()
    await asyncio.gather(bg_task, interactive_task)


# ---------------------------------------------------------------------------
# Metric: llm_backend_queue_wait_seconds observed for both classes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_wait_metric_observed_for_interactive() -> None:
    gate = LLMAdmissionGate(max_concurrent=2)

    async with gate.enter("dialogue"):
        pass

    snap = get_metrics_registry().snapshot()
    obs_keys = set(snap.get("observations", {}).keys())
    assert any(
        LLM_BACKEND_QUEUE_WAIT_METRIC in k and "class=interactive" in k
        for k in obs_keys
    ), f"interactive wait not recorded; observations={obs_keys}"


@pytest.mark.asyncio
async def test_queue_wait_metric_observed_for_background_when_admitted() -> None:
    gate = LLMAdmissionGate(max_concurrent=2)

    async with gate.enter("memory_consolidation"):
        pass

    snap = get_metrics_registry().snapshot()
    obs_keys = set(snap.get("observations", {}).keys())
    assert any(
        LLM_BACKEND_QUEUE_WAIT_METRIC in k and "class=background" in k
        for k in obs_keys
    ), f"background wait not recorded on admission; observations={obs_keys}"


@pytest.mark.asyncio
async def test_queue_wait_metric_observed_for_background_when_shed() -> None:
    """Shedding a background call must still record a wait observation."""
    gate = LLMAdmissionGate(max_concurrent=2)

    holding = asyncio.Event()
    release = asyncio.Event()

    async def interactive() -> None:
        async with gate.enter("dialogue"):
            holding.set()
            await release.wait()

    task = asyncio.create_task(interactive())
    await holding.wait()

    # Shed the background call
    with pytest.raises(LLMRequestError):
        async with gate.enter("quest_generation"):
            pass

    snap = get_metrics_registry().snapshot()
    obs_keys = set(snap.get("observations", {}).keys())
    assert any(
        LLM_BACKEND_QUEUE_WAIT_METRIC in k and "class=background" in k
        for k in obs_keys
    ), f"background wait not recorded on shed; observations={obs_keys}"

    release.set()
    await task
