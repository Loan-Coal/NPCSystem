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

from npc_engine.config import Settings
from npc_engine.config_prompt_window import (
    DIALOGUE_OUTPUT_TOKEN_RESERVE,
    PROMPT_HEADER_RESERVE_TOKENS,
    SYSTEM_PROMPT_TOKEN_RESERVE,
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


class TestShippedDefaultsAreCoherent:
    """The shipped window must hold the prompt the engine commits to sending.

    Replaces test_shipped_defaults_do_not_fit_the_default_window, which asserted
    `MEASURED_SYSTEM_PROMPT_TOKENS > 4096` — a comparison between two LITERALS. It read
    as a tripwire for the RET-P6 window raise but could never have fired, because neither
    side was the live configuration. These read Settings, so they can.
    """

    def test_shipped_defaults_fit_the_default_window(self) -> None:
        """Everything the engine sends must fit the shipped OLLAMA_CONTEXT_LENGTH."""
        settings = Settings()

        check_prompt_window(
            system_prompt_tokens=SYSTEM_PROMPT_TOKEN_RESERVE,
            prompt_token_budget=settings.PROMPT_TOKEN_BUDGET,
            output_token_reserve=DIALOGUE_OUTPUT_TOKEN_RESERVE,
            header_reserve=PROMPT_HEADER_RESERVE_TOKENS,
            context_length=settings.OLLAMA_CONTEXT_LENGTH,
        )

    def test_the_derived_budget_is_what_the_window_actually_leaves_over(self) -> None:
        """PROMPT_TOKEN_BUDGET is the window minus every named reserve, never more."""
        settings = Settings()
        reserved = (
            SYSTEM_PROMPT_TOKEN_RESERVE
            + DIALOGUE_OUTPUT_TOKEN_RESERVE
            + PROMPT_HEADER_RESERVE_TOKENS
        )

        assert settings.PROMPT_TOKEN_BUDGET == settings.OLLAMA_CONTEXT_LENGTH - reserved

    def test_a_narrow_window_is_refused_outside_dev(self) -> None:
        """Staging and prod must not boot on a window that truncates every prompt."""
        with pytest.raises(PromptWindowError):
            Settings(ENV="staging", NEO4J_PASSWORD="not-the-default", OLLAMA_CONTEXT_LENGTH=4096)

    def test_a_narrow_window_only_warns_in_dev(self) -> None:
        """Dev still boots on an incoherent window, or local work is bricked (DEC-175)."""
        settings = Settings(ENV="dev", OLLAMA_CONTEXT_LENGTH=4096)

        assert settings.OLLAMA_CONTEXT_LENGTH == 4096

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
