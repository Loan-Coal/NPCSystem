"""
test_prompt_window_constants_are_honest.py - The prompt-window reserves must track the
prompt the engine actually sends (P1 of the prompt-window plan).

Why this exists: the previous constant was `21707 // 4` -- the BYTE SIZE OF A YAML FILE,
including the `system:` key and every line's indentation. The engine never sends that
artifact. Measured live on 2026-08-26, the real assembled prompt is ~5,500 tokens and the
4096-token window clamped every dialogue prompt to 2,050 tokens, so roughly 70% of every
prompt -- most of the behavioural rules -- never reached the model. A constant nobody can
check against the real prompt is how that survived.

Both bounds matter. The upper bound catches a system prompt that grew past its reserve.
The lower bound catches a reserve left stale-high after a prompt diet, which would silently
starve the context budget instead.

Does NOT: call an LLM, or assert anything about a live window.
"""

from __future__ import annotations

from typing import get_args

import pytest
import yaml

from npc_engine.config import ContentRating
from npc_engine.config_prompt_window import (
    DIALOGUE_OUTPUT_TOKEN_RESERVE,
    PROMPT_WINDOW_OVERHEAD_TOKENS,
    SYSTEM_PROMPT_TOKEN_RESERVE,
    PROMPT_HEADER_RESERVE_TOKENS,
)
from npc_engine.engines.dialogue.prompt_builder import build_system_prompt
from npc_engine.retrieval.context.context_utils import estimate_tokens

# How far below its reserve the assembled prompt may sit before the reserve is stale.
# Wide enough to absorb a rule edit, narrow enough to catch a prompt diet nobody re-measured.
_RESERVE_SLACK_TOKENS = 400

_DIALOGUE_ENGINE_CONFIG = "src/npc_engine/engines/dialogue/llm_config.yaml"


@pytest.mark.parametrize("content_rating", list(get_args(ContentRating)))
def test_system_prompt_reserve_bounds_the_real_assembled_prompt(
    content_rating: ContentRating,
) -> None:
    """The reserve must bound what build_system_prompt actually returns, at every rating.

    Uses the engine's own estimator, not a re-implemented len//4, so the test cannot
    drift from the arithmetic the budget chain performs.
    """
    tokens = estimate_tokens(build_system_prompt(content_rating=content_rating))

    assert tokens <= SYSTEM_PROMPT_TOKEN_RESERVE, (
        f"the assembled system prompt at rating {content_rating!r} is {tokens} tokens, "
        f"above its {SYSTEM_PROMPT_TOKEN_RESERVE}-token reserve; raise the reserve "
        f"(and the window) or shorten the prompt"
    )
    assert tokens >= SYSTEM_PROMPT_TOKEN_RESERVE - _RESERVE_SLACK_TOKENS, (
        f"the assembled system prompt at rating {content_rating!r} is only {tokens} tokens "
        f"against a {SYSTEM_PROMPT_TOKEN_RESERVE}-token reserve; the prompt shrank and the "
        f"reserve is now stale-high, silently starving PROMPT_TOKEN_BUDGET"
    )


def test_output_reserve_matches_the_dialogue_engine_max_tokens() -> None:
    """The output reserve mirrors llm.max_tokens, which config/ may not import."""
    with open(_DIALOGUE_ENGINE_CONFIG, encoding="utf-8") as handle:
        engine_config = yaml.safe_load(handle)

    assert engine_config["llm"]["max_tokens"] == DIALOGUE_OUTPUT_TOKEN_RESERVE, (
        "engines/dialogue/llm_config.yaml llm.max_tokens is the source of truth for the "
        "output reserve; config_prompt_window mirrors it because config/ may depend on nothing"
    )


def test_the_overhead_is_the_sum_of_its_named_parts() -> None:
    """The overhead is a sum, not a magic number — that was the original defect."""
    assert PROMPT_WINDOW_OVERHEAD_TOKENS == (
        SYSTEM_PROMPT_TOKEN_RESERVE + DIALOGUE_OUTPUT_TOKEN_RESERVE + PROMPT_HEADER_RESERVE_TOKENS
    )
