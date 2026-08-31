"""
Module: tests.unit.config.test_shipped_window_holds_the_measured_ceiling
Layer: test (unit)
Purpose: Pin the SHIPPED context window against the MEASURED assembled-context demand,
         so a window that is internally coherent but too small to hold its own context
         cannot ship.
Dependencies: pytest; npc_engine.config, npc_engine.config_prompt_window,
              npc_engine.schema.llm_schema_loader
Used by: make test (pytest discovery)

WHAT THIS CATCHES THAT test_config_prompt_window DOES NOT
`TestShippedDefaultsAreCoherent` asserts the reserves SUM to no more than the window —
`system + budget + output + headers <= context_length`. That is coherence, and it is
satisfied by construction for every window, because the budget is DERIVED as
`window - overhead`. It says nothing about whether the budget that falls out is big
enough for the context the engine actually assembles.

It was not. Measured 2026-08-27 (DEC-215) over the eight-NPC probe roster on the clean
eval baseline at corpus_sha 2b19e47a, with RAG live:

    mira_innkeeper  1151   aldric_merchant 1031   lira_fence 1027   captain_sorn  995
    vex_spymaster    922   harwick_guard    910   old_henryk  962   bren_smith    832

At the then-shipped default of 8192, `PROMPT_TOKEN_BUDGET` derives to
`8192 - 7130 = 1062`, which is BELOW three of those eight. The window validator passed
and the configuration that ships would still have dropped tier-A items on
`mira_innkeeper`, `aldric_merchant` and `lira_fence` — re-arming ISSUE-209 on the
default path and regressing the inner life D8 protects.

`.env` is untracked, so `config.py`'s class default is what every other checkout runs.
These assertions therefore read the CLASS DEFAULT via `model_fields`, never `Settings()`,
which would pick up whatever the local `.env` happens to say and pass vacuously.

Does NOT: perform HTTP, hit the engine, read the graph, or call an LLM.
"""

from __future__ import annotations

from pathlib import Path

from npc_engine.config import MIN_PROMPT_TOKEN_BUDGET, Settings
from npc_engine.config_prompt_window import PROMPT_WINDOW_OVERHEAD_TOKENS
from npc_engine.schema.llm_schema_loader import load_llm_config

MEASURED_ROSTER_CEILING_TOKENS = 1151
"""Largest assembled context across the 8-NPC probe roster (DEC-215).

`mira_innkeeper`, default arm, clean baseline, `make probe-ceiling`. This is the LARGER
of the two totals the debug route reports — the per-item sum (1151) and the serialized
blob (1130) — because a window sized to the smaller has headroom that does not exist.
"""

MEASURED_TIER_MAXIMA: dict[str, int] = {"tier_a": 857, "tier_b": 96, "tier_c": 145}
"""Largest per-tier spend across the same roster and the same run (DEC-215)."""

SESSION_ALLOWANCE_TOKENS = 1200
"""`session_turns_budget_tokens` from the shipped llm_config.yaml.

The eval harness never sends a `session_id`, so none of the measured figures include
session history — but a game client does, and session turns are tier-A items inside the
same budget. Nothing enforces this cap on the live path (ISSUE-225), so it is used here
as the DESIGN INTENT the window must accommodate, not as a guarantee.
"""

_SHIPPED_CONFIG = "config/llm_config.yaml"


def _code_default_window() -> int:
    """The OLLAMA_CONTEXT_LENGTH a checkout runs with no .env, read off the class."""
    return int(Settings.model_fields["OLLAMA_CONTEXT_LENGTH"].default)


def _code_default_budget() -> int:
    """PROMPT_TOKEN_BUDGET as _derive_prompt_token_budget would derive it, .env aside."""
    return max(MIN_PROMPT_TOKEN_BUDGET, _code_default_window() - PROMPT_WINDOW_OVERHEAD_TOKENS)


def _shipped_tier_budgets():
    """Tier ceilings from the YAML the package actually ships."""
    package_root = Path(__file__).resolve().parents[3] / "src" / "npc_engine"
    return load_llm_config(config_path=str(package_root / _SHIPPED_CONFIG)).tier_budget_tokens


def test_the_shipped_default_budget_holds_the_measured_roster_ceiling() -> None:
    """RED anchor: at the 8192 default the budget was 1062 against a measured 1151."""
    budget = _code_default_budget()
    assert budget >= MEASURED_ROSTER_CEILING_TOKENS, (
        f"the shipped default window {_code_default_window()} derives a budget of "
        f"{budget}, which is below the measured roster ceiling of "
        f"{MEASURED_ROSTER_CEILING_TOKENS}: the configuration that ships cannot hold "
        f"its own assembled context and will drop tier-A items (ISSUE-209, D8)"
    )


def test_the_shipped_default_budget_also_holds_a_full_session_history() -> None:
    """Session turns are tier-A items in the same budget, and the eval never sends any."""
    required = MEASURED_ROSTER_CEILING_TOKENS + SESSION_ALLOWANCE_TOKENS
    assert _code_default_budget() >= required, (
        f"budget {_code_default_budget()} does not hold the measured ceiling plus the "
        f"{SESSION_ALLOWANCE_TOKENS}-token session allowance ({required})"
    )


def test_the_derived_budget_is_the_window_minus_the_named_overhead() -> None:
    """The budget is a SUM OF NAMED PARTS subtracted from the window, never a literal."""
    assert _code_default_budget() == _code_default_window() - PROMPT_WINDOW_OVERHEAD_TOKENS


def test_every_shipped_tier_ceiling_clears_its_measured_maximum() -> None:
    """A ceiling below measured demand silently truncates the tier it names."""
    tiers = _shipped_tier_budgets()
    for tier, measured in MEASURED_TIER_MAXIMA.items():
        assert getattr(tiers, tier) > measured, (
            f"tier ceiling {tier}={getattr(tiers, tier)} does not clear its measured "
            f"maximum of {measured} tokens"
        )


def test_the_tier_a_ceiling_stays_above_the_tier_a_fraction_floor() -> None:
    """Otherwise DEC-203's reclaim is dead.

    `_tier_a_cap_with_reclaim` returns `min(ceiling, max(fraction_floor, leftover))`. A
    ceiling at or below the floor makes the ceiling bind unconditionally, so tier A can
    never take up what tiers B and C leave — which is the ISSUE-197 starvation DEC-203
    was written to fix.
    """
    package_root = Path(__file__).resolve().parents[3] / "src" / "npc_engine"
    config = load_llm_config(config_path=str(package_root / _SHIPPED_CONFIG))
    floor = int(_code_default_budget() * config.tier_a_fraction)
    assert config.tier_budget_tokens.tier_a > floor, (
        f"tier_a ceiling {config.tier_budget_tokens.tier_a} is not above the tier-A "
        f"fraction floor {floor}, so the DEC-203 reclaim can never widen tier A"
    )


def test_the_tier_a_ceiling_holds_the_measured_tier_a_spend_plus_a_session() -> None:
    """Tier A carries beliefs, goals and memories AND the session turns."""
    required = MEASURED_TIER_MAXIMA["tier_a"] + SESSION_ALLOWANCE_TOKENS
    assert _shipped_tier_budgets().tier_a >= required, (
        f"tier_a ceiling {_shipped_tier_budgets().tier_a} does not hold the measured "
        f"tier-A spend plus a full session ({required})"
    )
