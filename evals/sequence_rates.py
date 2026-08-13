"""
Module: sequence_rates
Layer: evals (eval harness — not part of src/)
Purpose: EVAL-P12.4 orchestrator — run the six promoted scenarios live (k reps
         each), pool their repetition-indexed outcomes into the order-effect
         check, and render a fidelity-conditional report. The renderer has no
         access to ResetReceipts (SEQUENCE_STATS_POLICY.md §3's enforcement
         contract) — it only ever sees the SequenceStat and OrderEffectResult
         objects the runner already decided to hand it.
Dependencies: httpx, argparse, sys (stdlib), sequence_runner, sequence_reset,
              sequence_fidelity, sequence_order_effect, scenario_adapters, world_map
Used by: evals/__main__.py ("sequence" verb), Makefile eval-sequence target
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import httpx

from scenario_adapters import SCENARIO_ADAPTER_FACTORIES
from sequence_fidelity import SequenceStat
from sequence_order_effect import OrderEffectResult, order_effect_check
from sequence_reset import make_reset_fn
from sequence_runner import SequenceResult, run_sequence
from world_map import PROMOTED_SCENARIO_IDS

_DEFAULT_K: int = 3
_DEFAULT_BASE_URL: str = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Orchestration (live — requires the seeded stack)
# ---------------------------------------------------------------------------


def run_all_sequences(client: httpx.Client, k: int = _DEFAULT_K) -> tuple[SequenceResult, ...]:
    """Run every promoted scenario k times against the live API.

    Args:
        client: Authenticated httpx.Client with base_url preset.
        k: Repetitions per scenario.
    Returns:
        One SequenceResult per promoted scenario, in PROMOTED_SCENARIO_IDS order.
    """
    reset_fn = make_reset_fn(client, base_url="")
    results: list[SequenceResult] = []
    for scenario_id in sorted(PROMOTED_SCENARIO_IDS):
        scenario_fn = SCENARIO_ADAPTER_FACTORIES[scenario_id](client)
        results.append(run_sequence(scenario_id, scenario_fn, reset_fn, k))
    return tuple(results)


def pooled_order_effect(results: Sequence[SequenceResult]) -> OrderEffectResult:
    """Compute the order-effect check pooled across every scenario's repetitions.

    Args:
        results: One SequenceResult per scenario, all sharing the same k.
    Returns:
        OrderEffectResult over the [scenario][repetition] outcome matrix.
    """
    outcomes = [tuple(rep.passed for rep in result.repetitions) for result in results]
    return order_effect_check(outcomes)


# ---------------------------------------------------------------------------
# Rendering (pure — no receipts, no HTTP)
# ---------------------------------------------------------------------------


def _format_stat_line(stat: SequenceStat) -> str:
    """Render one scenario's fidelity-gated rate line.

    FULL prints the Wilson interval; PARTIAL withholds it and names what survived
    instead — the interval is never computed here, only rendered if present.
    """
    header = f"{stat.scenario_id} reaches {stat.passes}/{stat.k} (k={stat.k}, {stat.fidelity}"
    if stat.fidelity == "FULL":
        assert stat.interval is not None
        lo, hi = stat.interval
        return f"{header}) [{lo:.3f}, {hi:.3f}]"
    surviving = ", ".join(stat.surviving) or "(none named)"
    return f"{header} — CI withheld, repetitions not independent: {surviving})"


def _format_order_effect(order_effect: OrderEffectResult) -> str:
    """Render the order-effect check block (SEQUENCE_STATS_POLICY.md §4.3)."""
    rates = ", ".join(f"{r:.3f}" for r in order_effect.rates_by_repetition)
    if not order_effect.computable:
        return (
            "ORDER EFFECT CHECK: not computable "
            f"({order_effect.reason}). Rates by repetition: [{rates}]."
        )
    q_p = order_effect.cochrans_q_p
    mcnemar_p = order_effect.mcnemar_p
    mcnemar_str = f"{mcnemar_p:.4f}" if mcnemar_p is not None else "undefined (no discordant ends)"
    return (
        f"ORDER EFFECT CHECK — Cochran's Q={order_effect.cochrans_q:.3f} p={q_p:.4f}, "
        f"first-vs-last McNemar p={mcnemar_str}. Rates by repetition: [{rates}]."
    )


def render_report(
    results: Sequence[SequenceResult],
    order_effect: OrderEffectResult | None,
) -> str:
    """Render the full EVAL-P12.4 report: per-scenario rates, then the order-effect
    check whenever any scenario in the run is PARTIAL (SEQUENCE_STATS_POLICY.md §4.3:
    at PARTIAL fidelity the check is the headline output, printed in the withheld
    interval's place).

    Args:
        results: One SequenceResult per scenario.
        order_effect: Pooled order-effect check result, or None if not computed
            (only valid when every scenario is FULL fidelity).
    Returns:
        Multi-line report string.
    """
    lines = [_format_stat_line(result.stat) for result in results]
    any_partial = any(result.stat.fidelity == "PARTIAL" for result in results)
    if any_partial:
        if order_effect is None:
            raise ValueError(
                "at least one scenario is PARTIAL fidelity but no order-effect check "
                "was supplied — a run must print the check in place of the withheld "
                "interval, never neither (SEQUENCE_STATS_POLICY.md §3)."
            )
        lines.append("")
        lines.append(_format_order_effect(order_effect))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run all six promoted scenarios live and print the fidelity-conditional report."""
    parser = argparse.ArgumentParser(description="EVAL-P12.4 measured multi-turn sequence rates.")
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--k", type=int, default=_DEFAULT_K)
    args = parser.parse_args(argv)

    with httpx.Client(
        base_url=args.base_url,
        headers={"Authorization": f"Bearer {args.api_key}"},
        # /v1/clock/advance cascades through ~25 engines and can exceed 90s under load
        # (measured EVAL-P12.4 live run); 180s keeps time_passage/mood_contagion from
        # spuriously timing out mid-tick.
        timeout=180.0,
    ) as client:
        results = run_all_sequences(client, k=args.k)

    order_effect = pooled_order_effect(results) if any(
        r.stat.fidelity == "PARTIAL" for r in results
    ) else None
    print(render_report(results, order_effect))
    return 0


if __name__ == "__main__":
    sys.exit(main())
