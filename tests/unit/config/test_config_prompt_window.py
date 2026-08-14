"""
Module: test_config_prompt_window
Layer: tests/unit
Purpose: Verify the prompt-window coherence check detects an over-subscribed context
         window (RET-P0.3) — the defect where the system prompt alone exceeds it.
Dependencies: config_prompt_window, utils.errors
Used by: pytest test runner
"""

from __future__ import annotations

import pytest

from npc_engine.config_prompt_window import (
    MEASURED_SYSTEM_PROMPT_TOKENS,
    PromptWindowBreakdown,
    check_prompt_window,
    describe_prompt_window,
)
from npc_engine.utils.errors import PromptWindowError


class TestCheckPromptWindow:
    """Coherence between the declared window and everything that must fit inside it."""

    def test_raises_when_components_exceed_the_context_window(self) -> None:
        """A window smaller than the sum of its declared parts is a configuration error."""
        with pytest.raises(PromptWindowError) as exc_info:
            check_prompt_window(
                system_prompt_tokens=5426,
                prompt_token_budget=512,
                output_token_reserve=512,
                header_reserve=500,
                context_length=4096,
            )

        error = exc_info.value
        assert error.context_length == 4096
        assert error.required_tokens == 5426 + 512 + 512 + 500

    def test_does_not_raise_when_the_window_is_large_enough(self) -> None:
        """The RET-P6 target configuration must be coherent."""
        check_prompt_window(
            system_prompt_tokens=1800,
            prompt_token_budget=1200,
            output_token_reserve=512,
            header_reserve=500,
            context_length=8192,
        )

    def test_exact_fit_is_accepted(self) -> None:
        """Requiring exactly the window size is coherent, not an overflow."""
        check_prompt_window(
            system_prompt_tokens=1000,
            prompt_token_budget=500,
            output_token_reserve=400,
            header_reserve=100,
            context_length=2000,
        )


class TestCurrentDefaultsAreIncoherent:
    """Pins the defect RET-P6 exists to fix, so the fix is measurable."""

    def test_shipped_defaults_do_not_fit_the_default_window(self) -> None:
        """The system prompt alone overflows OLLAMA_CONTEXT_LENGTH=4096 today."""
        assert MEASURED_SYSTEM_PROMPT_TOKENS > 4096, (
            "If this now fits, the system-prompt diet landed — update the expectation."
        )

    def test_describe_reports_the_overflow_without_raising(self) -> None:
        """The breakdown is inspectable for warning-only use in dev."""
        breakdown = describe_prompt_window(
            system_prompt_tokens=5426,
            prompt_token_budget=512,
            output_token_reserve=512,
            header_reserve=500,
            context_length=4096,
        )

        assert isinstance(breakdown, PromptWindowBreakdown)
        assert breakdown.fits is False
        assert breakdown.overflow_tokens == (5426 + 512 + 512 + 500) - 4096
