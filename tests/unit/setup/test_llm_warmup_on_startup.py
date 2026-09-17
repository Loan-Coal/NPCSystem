"""Tests for npc_engine.setup.llm_warmup — LLM startup warm-up.

RED anchor: asserts that with enabled=True startup issues exactly one generation
against a mock adapter, zero when False, and that an adapter raising during
warm-up does not prevent startup.  All three fail before the implementation exists.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from npc_engine.setup.llm_warmup import warm_up_llm


class TestWarmUpLlmEnabled:
    """warm_up_llm issues exactly one generate() call when enabled."""

    def test_issues_exactly_one_generate_call(self) -> None:
        """A single generate() is issued against the adapter when enabled=True."""
        adapter = AsyncMock()
        adapter.generate = AsyncMock(return_value="ok")
        with patch("npc_engine.setup.llm_warmup._load_warmup_prompt", return_value="."):
            asyncio.run(warm_up_llm(adapter, enabled=True))
        assert adapter.generate.call_count == 1


class TestWarmUpLlmDisabled:
    """warm_up_llm issues no generate() calls when disabled."""

    def test_issues_zero_generate_calls(self) -> None:
        """No generate() is issued when enabled=False."""
        adapter = AsyncMock()
        asyncio.run(warm_up_llm(adapter, enabled=False))
        adapter.generate.assert_not_called()


class TestWarmUpLlmFailSoft:
    """warm_up_llm swallows adapter errors and never blocks startup."""

    def test_adapter_exception_does_not_block_startup(self) -> None:
        """A raising adapter must not propagate — warm-up failure is non-fatal."""
        adapter = AsyncMock()
        adapter.generate = AsyncMock(side_effect=RuntimeError("ollama down"))
        with patch("npc_engine.setup.llm_warmup._load_warmup_prompt", return_value="."):
            asyncio.run(warm_up_llm(adapter, enabled=True))  # must not raise
        # generate was attempted (the failure is from the adapter, not a missed call).
        assert adapter.generate.call_count == 1
