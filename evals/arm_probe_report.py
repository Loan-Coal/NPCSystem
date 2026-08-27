"""
Module: arm_probe_report
Layer: evals (eval harness — not part of src/)
Purpose: Printing for the arm probe — gate verdicts, the per-arm observation table, and
         the MDE section.
Does NOT: decide anything, call the engine, or compute retrieval.
Dependencies injected: everything is an argument.
Used by: evals.arm_probe.

Evidence is printed on PASS as well as on failure. A gate whose output appears only when
it fails cannot be checked for having run at all, and "silently passed on an empty input"
is the failure mode this whole phase exists to prevent.
"""

from __future__ import annotations

from arm_probe_models import ArmObservation, GateResult
from mde import (
    RECORDED_BASE_RATE,
    RECORDED_GUARD_FLOOR_PP,
    RECORDED_GUARD_N,
    RECORDED_KAPPAS,
    JudgeCriterion,
    arm_pairing_mde,
    implied_discordance_rate,
    required_pairs_for,
)

__all__ = ["print_gate", "print_mde_section", "print_observations"]

_RULE = "=" * 78
_TIERS = ("tier0", "tierA", "tierB", "tierC")
_TARGET_TRUE_EFFECT_PP = RECORDED_GUARD_FLOOR_PP


def print_gate(result: GateResult) -> None:
    """Print one gate's verdict and its evidence.

    Args:
        result: The gate verdict to render.
    """
    status = "PASS" if result.passed else "FAIL"
    print(f"\n[GATE {result.number}] {status}  {result.name}")
    for line in result.detail:
        print(f"    {line}")


def _spend(observation: ArmObservation) -> str:
    """Render one observation's per-tier spend as 'tier0 3/93 tierA 8/687 ...'."""
    return "  ".join(
        f"{tier} {observation.tier_items(tier)}/{observation.tier_tokens(tier)}"
        for tier in _TIERS
    )


def print_observations(
    default_runs: list[ArmObservation], arm_runs: dict[str, list[ArmObservation]]
) -> None:
    """Print what each arm retrieved per case, and how it differs from default.

    Args:
        default_runs: The default arm's observations, in case order.
        arm_runs: Each arm's observations, in the same case order.
    """
    print(f"\n{_RULE}\nPER-ARM RETRIEVAL (2 cases x {len(arm_runs) + 1} arms, k=1)\n{_RULE}")
    for index, baseline in enumerate(default_runs):
        print(f"\n{baseline.npc_id}  query={baseline.query!r}")
        print(
            f"  SUPPLY at default: event: items={baseline.count_keys('event:')}  "
            f"rag: items={baseline.count_keys('rag:')}   "
            f"(a limit raised above the supply cannot change anything)"
        )
        print(f"  {'default':<14} {_spend(baseline)}   total={baseline.total_tokens}")
        for arm, runs in arm_runs.items():
            observation = runs[index]
            added = tuple(k for k in observation.item_keys if k not in baseline.item_keys)
            removed = tuple(k for k in baseline.item_keys if k not in observation.item_keys)
            print(f"  {arm:<14} {_spend(observation)}   total={observation.total_tokens}")
            print(f"  {'':<14}   +{list(added)}  -{list(removed)}")


def print_mde_section(*, comparisons: int) -> None:
    """Print the per-arm-pairing minimum detectable effect.

    Args:
        comparisons: Number of simultaneous (default vs arm) pairings, for Bonferroni.
    """
    p_d = implied_discordance_rate(
        mde=RECORDED_GUARD_FLOOR_PP / 100.0, n_pairs=RECORDED_GUARD_N
    )
    print(f"\n{_RULE}\nMINIMUM DETECTABLE EFFECT PER ARM PAIRING\n{_RULE}")
    print(
        f"Recorded inputs: n={RECORDED_GUARD_N} guard pairs, floor "
        f"{RECORDED_GUARD_FLOOR_PP}pp, base rate {RECORDED_BASE_RATE} (llm_config.yaml, "
        f"ISSUE-184).\nImplied discordance rate p_d = {p_d * 100:.2f}% "
        f"(independence bound {2 * RECORDED_BASE_RATE * (1 - RECORDED_BASE_RATE) * 100:.2f}%)."
    )
    print(f"\n{'criterion':<16}{'kappa':>7}{'observed':>11}{'TRUE MDE':>11}  n for a "
          f"{_TARGET_TRUE_EFFECT_PP}pp true effect")
    for name, kappa in RECORDED_KAPPAS:
        row = arm_pairing_mde(
            criterion=JudgeCriterion(name=name, kappa=kappa),
            n_pairs=RECORDED_GUARD_N,
            discordance_rate=p_d,
            comparisons=comparisons,
        )
        needed = required_pairs_for(
            true_effect_pp=_TARGET_TRUE_EFFECT_PP, kappa=kappa,
            discordance_rate=p_d, comparisons=comparisons,
        )
        true_mde = f"{row.true_mde_pp:.1f}pp" if row.detectable else "UNRESOLVABLE"
        print(
            f"{name:<16}{kappa:>7.3f}{row.observed_mde_pp:>10.1f}pp{true_mde:>11}"
            f"  n={needed:,.0f}"
        )
    print(
        f"\nBonferroni over {comparisons} pairings. TRUE MDE is what the underlying rate "
        f"must move\nto survive judge noise at the recorded kappa — a rate at "
        f"{RECORDED_BASE_RATE * 100:.1f}% can fall at most "
        f"{RECORDED_BASE_RATE * 100:.1f}pp."
    )
