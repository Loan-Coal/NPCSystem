"""
Module: config_prompt_window
Layer: config
Purpose: Validate that the configured LLM context window can actually hold the prompt
         the engine commits to sending (system prompt + context + output + headers).

Does NOT: load prompt files, call a tokenizer, read settings, or mutate configuration.
          All inputs are passed in as plain token counts.

Dependencies injected: None (pure functions; token counts supplied by the caller).

Used by: tests; RET-P6 will wire check_prompt_window into Settings validation.
"""

from __future__ import annotations

from dataclasses import dataclass

from npc_engine.utils.errors import PromptWindowError

__all__ = [
    "MEASURED_SYSTEM_PROMPT_TOKENS",
    "PromptWindowBreakdown",
    "check_prompt_window",
    "describe_prompt_window",
]


MEASURED_SYSTEM_PROMPT_TOKENS = 5426
"""Measured size of prompts/dialogue/system_v1.yaml under the engine's len//4 estimator.

21,707 chars at 4 chars/token. Recorded as a constant so the RET-P6 system-prompt diet
has a baseline to move, and so the incoherence with a 4096-token window is testable
without loading the YAML.
"""


@dataclass(frozen=True)
class PromptWindowBreakdown:
    """Component-by-component accounting of a configured context window.

    Attributes:
        system_prompt_tokens: Tokens consumed by the static system prompt.
        prompt_token_budget: Tokens reserved for assembled retrieval context.
        output_token_reserve: Tokens reserved for the model's own response.
        header_reserve: Tokens reserved for runtime guards and prompt scaffolding.
        context_length: The configured model context window.
        required_tokens: Sum of all reserved components.
        overflow_tokens: required_tokens minus context_length, floored at zero.
        fits: Whether the configuration is coherent.
    """

    system_prompt_tokens: int
    prompt_token_budget: int
    output_token_reserve: int
    header_reserve: int
    context_length: int
    required_tokens: int
    overflow_tokens: int
    fits: bool

    def describe(self) -> str:
        """Return a one-line human-readable breakdown for logs and error detail."""
        return (
            f"system={self.system_prompt_tokens} + context={self.prompt_token_budget} "
            f"+ output={self.output_token_reserve} + headers={self.header_reserve} "
            f"= {self.required_tokens} tokens against a {self.context_length}-token window"
        )


def describe_prompt_window(
    *,
    system_prompt_tokens: int,
    prompt_token_budget: int,
    output_token_reserve: int,
    header_reserve: int,
    context_length: int,
) -> PromptWindowBreakdown:
    """Compute the window accounting without raising.

    Use this for warning-only reporting in dev, where an incoherent window must be
    visible but must not prevent the process from starting.

    Args:
        system_prompt_tokens: Tokens consumed by the static system prompt.
        prompt_token_budget: Tokens reserved for assembled retrieval context.
        output_token_reserve: Tokens reserved for the model's response.
        header_reserve: Tokens reserved for runtime guards and scaffolding.
        context_length: The configured model context window.
    Returns:
        A PromptWindowBreakdown describing whether the configuration fits.
    """
    required = (
        system_prompt_tokens + prompt_token_budget + output_token_reserve + header_reserve
    )
    overflow = max(0, required - context_length)
    return PromptWindowBreakdown(
        system_prompt_tokens=system_prompt_tokens,
        prompt_token_budget=prompt_token_budget,
        output_token_reserve=output_token_reserve,
        header_reserve=header_reserve,
        context_length=context_length,
        required_tokens=required,
        overflow_tokens=overflow,
        fits=overflow == 0,
    )


def check_prompt_window(
    *,
    system_prompt_tokens: int,
    prompt_token_budget: int,
    output_token_reserve: int,
    header_reserve: int,
    context_length: int,
) -> None:
    """Raise if the configured context window cannot hold the prompt it must serve.

    Args:
        system_prompt_tokens: Tokens consumed by the static system prompt.
        prompt_token_budget: Tokens reserved for assembled retrieval context.
        output_token_reserve: Tokens reserved for the model's response.
        header_reserve: Tokens reserved for runtime guards and scaffolding.
        context_length: The configured model context window.
    Raises:
        PromptWindowError: When the components sum beyond context_length.
    """
    breakdown = describe_prompt_window(
        system_prompt_tokens=system_prompt_tokens,
        prompt_token_budget=prompt_token_budget,
        output_token_reserve=output_token_reserve,
        header_reserve=header_reserve,
        context_length=context_length,
    )
    if breakdown.fits:
        return
    raise PromptWindowError(
        context_length=breakdown.context_length,
        required_tokens=breakdown.required_tokens,
        overflow_tokens=breakdown.overflow_tokens,
        detail=breakdown.describe(),
    )
