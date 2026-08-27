"""
Module: config_prompt_window
Layer: config
Purpose: Validate that the configured LLM context window can actually hold the prompt
         the engine commits to sending (system prompt + context + output + headers).

Does NOT: load prompt files, call a tokenizer, read settings, or mutate configuration.
          All inputs are passed in as plain token counts.

Dependencies injected: None (pure functions; token counts supplied by the caller).

Used by: config.Settings (_validate_prompt_window), tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from npc_engine.utils.errors import PromptWindowError

_LOGGER = logging.getLogger(__name__)

DEV_ENV = "dev"
"""The only environment allowed to boot on an incoherent window (DEC-175)."""

__all__ = [
    "DEV_ENV",
    "DIALOGUE_OUTPUT_TOKEN_RESERVE",
    "PROMPT_HEADER_RESERVE_TOKENS",
    "PROMPT_WINDOW_OVERHEAD_TOKENS",
    "SYSTEM_PROMPT_TOKEN_RESERVE",
    "PromptWindowBreakdown",
    "check_prompt_window",
    "check_prompt_window_for_env",
    "describe_prompt_window",
]


SYSTEM_PROMPT_TOKEN_RESERVE = 5850
"""Tokens reserved for the ASSEMBLED dialogue system prompt, worst content rating.

Measured 2026-08-26: build_system_prompt() returned 5,249 tokens at 'mature', 5,473 with
system_state_v1.yaml appended, and 5,545 at 'everyone' with the content ceiling. Live
Ollama agreed within 3% (prompt_eval_count 7,130 against a len//4 estimate of 7,138 for
the whole request), so the engine's estimator is trustworthy at this scale.

Re-measured 2026-08-27 (P8): 5,780 at 'everyone'. System prompt Rule 17 (RETRIEVED
CONTEXT) added +235 tokens, and it is not optional — without a rule teaching the model
what `context.retrieved_context` is, the tier-B slot P8 exists to fill is ignored, or
worse, read as events the NPC witnessed. Raised 5600 -> 5850, which costs
PROMPT_TOKEN_BUDGET 250 tokens. This is the re-measurement P10 gate 12 calls for.

This replaces MEASURED_SYSTEM_PROMPT_TOKENS = 21707 // 4, which measured the BYTE SIZE OF
THE YAML FILE -- including the `system:` key and every line's indentation -- an artifact
the engine never sends. tests/unit/config/test_prompt_window_constants_are_honest.py
bounds this constant against the real assembly in both directions so it cannot drift again.
"""

DIALOGUE_OUTPUT_TOKEN_RESERVE = 512
"""Tokens reserved for the model's own reply.

Mirrors `llm.max_tokens` in engines/dialogue/llm_config.yaml, which is the source of truth
and which this layer may not import -- config depends on nothing. The mirror is enforced by
test_output_reserve_matches_the_dialogue_engine_max_tokens.
"""

PROMPT_HEADER_RESERVE_TOKENS = 768
"""Tokens reserved for everything in the user prompt that is not the CONTEXT block.

Measured floor ~233 tokens (PROMPT_VERSION/NPC_ID/PLAYER_ID/VOICE_DESCRIPTOR, the epoch
guard, knowledge gaps, STANDING and the fenced player message at MAX_PLAYER_MESSAGE_CHARS).
Reserved well above that because MY_ACCOUNT_i / HEARSAY_i are unbounded: prompt_builder
emits one line per known event, duplicating distorted_summary text that is already inside
CONTEXT. Shrink this only alongside a cap on those lines.
"""

PROMPT_WINDOW_OVERHEAD_TOKENS = (
    SYSTEM_PROMPT_TOKEN_RESERVE + DIALOGUE_OUTPUT_TOKEN_RESERVE + PROMPT_HEADER_RESERVE_TOKENS
)
"""Everything in the context window that is not assembled retrieval context.

The number PROMPT_TOKEN_BUDGET subtracts from OLLAMA_CONTEXT_LENGTH. It is a SUM OF NAMED
PARTS rather than a literal, which is the whole fix: the previous literal 5200 under-reserved
by ~1,680 tokens, so `required = window + 1680` held at every window size and no window
raise could ever have made the configuration coherent.
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


def _shipped_breakdown(*, prompt_token_budget: int, context_length: int) -> PromptWindowBreakdown:
    """Account a window against this module's own reserves.

    Callers cannot supply their own reserve numbers here, which is deliberate: the
    budget is derived from these same constants, and letting the check use different
    ones is how the previous 5200 literal drifted unnoticed.
    """
    return describe_prompt_window(
        system_prompt_tokens=SYSTEM_PROMPT_TOKEN_RESERVE,
        prompt_token_budget=prompt_token_budget,
        output_token_reserve=DIALOGUE_OUTPUT_TOKEN_RESERVE,
        header_reserve=PROMPT_HEADER_RESERVE_TOKENS,
        context_length=context_length,
    )


def check_prompt_window_for_env(
    *,
    prompt_token_budget: int,
    context_length: int,
    env: str,
) -> None:
    """Enforce window coherence outside dev, and merely report it inside dev.

    Dev is warning-only by deliberate choice (DEC-175): a hard failure there would brick
    local development the moment someone pins a narrow window for an experiment.

    Args:
        prompt_token_budget: Tokens the context builder is allowed to fill.
        context_length: The configured model context window (num_ctx).
        env: Current ENV value ("dev", "staging", or "prod").

    Raises:
        PromptWindowError: When the components overflow the window and env is not dev.
    """
    breakdown = _shipped_breakdown(
        prompt_token_budget=prompt_token_budget, context_length=context_length
    )
    if breakdown.fits:
        return
    if env == DEV_ENV:
        _LOGGER.warning(
            "prompt window is over-subscribed; the backend will truncate: %s",
            breakdown.describe(),
        )
        return
    raise PromptWindowError(
        context_length=breakdown.context_length,
        required_tokens=breakdown.required_tokens,
        overflow_tokens=breakdown.overflow_tokens,
        detail=breakdown.describe(),
    )
