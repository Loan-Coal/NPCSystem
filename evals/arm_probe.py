"""
Module: arm_probe
Layer: evals (eval harness — not part of src/)
Purpose: `make eval-arm-probe`. Runs the four P9 gates in order over 2 cases x N arms at
         k=1, diffs each arm's item_keys and tier_spend, prints the corpus fingerprint
         and the per-arm-pairing MDE, and exits non-zero if any gate fails.
Does NOT: generate dialogue, call an LLM, judge anything, or write a generation record.
Dependencies injected: base URL, API key, cases and arms are all arguments/env.
Used by: make eval-arm-probe.

WHAT THIS IS FOR
It is the thing standing between an operator and a ten-hour null result. Each gate is
independently runnable (`--gate 2`), the order is load-bearing, and the run stops at the
first failure because every later gate is meaningless until the earlier one holds.

k=1 IS DELIBERATE. This probe measures EXPOSURE — does the arm reach the model with
different context — not effect size. Repetitions buy nothing: context assembly at a fixed
world state is deterministic given (npc_id, query, player_id, arm), so a second rep would
reproduce the first exactly. Effect size is what the MDE section is about, and the MDE
says what a ten-hour run could resolve if it ran.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _run_config_corpus import corpus_fields  # noqa: E402
from arm_probe_client import ProbeClient  # noqa: E402
from arm_probe_gates import (  # noqa: E402
    gate_1_config,
    gate_2_corpus,
    gate_3_isolation,
    gate_4_effect,
)
from arm_probe_models import ArmObservation, GateResult  # noqa: E402
from arm_probe_report import print_gate, print_mde_section, print_observations  # noqa: E402

_DEFAULT_BASE_URL = "http://localhost:8000"
_DEFAULT_PLAYER_ID = "player_demo"

PROBE_CASES: tuple[tuple[str, str], ...] = (
    ("captain_sorn", "what news"),
    ("old_henryk", "what news"),
)
"""The two cases DEC-212 measured tier B on, so P9's numbers compare to P8's directly."""


def _declared_arms() -> dict[str, object]:
    """Return every declared arm, resolved to the profile the engine would apply."""
    import engine_adapter

    return {
        name: engine_adapter.resolve_retrieval_profile(name)
        for name in sorted(engine_adapter.declared_retrieval_profiles())
    }


def _observe_all(
    client: ProbeClient, arms: dict[str, object], player_id: str
) -> tuple[list[ArmObservation], dict[str, list[ArmObservation]]]:
    """Assemble every case under default and under every declared arm."""
    default_runs = [
        client.observe(npc_id=npc, query=query, player_id=player_id, arm=None)
        for npc, query in PROBE_CASES
    ]
    arm_runs = {
        arm: [
            client.observe(npc_id=npc, query=query, player_id=player_id, arm=arm)
            for npc, query in PROBE_CASES
        ]
        for arm in arms
    }
    return default_runs, arm_runs


def _live_gates(
    client: ProbeClient, arms: dict[str, object], player_id: str, selected: str
) -> list[GateResult]:
    """Run the gates that need a live engine (2 and 4), honouring --gate."""
    results: list[GateResult] = []
    names = ["default", *arms]
    if selected in ("all", "2"):
        results.append(gate_2_corpus(client=client, arms=names, corpus_fields=corpus_fields))
        if not results[-1].passed:
            return results
    if selected in ("all", "4"):
        default_runs, arm_runs = _observe_all(client, arms, player_id)
        print_observations(default_runs, arm_runs)
        results.append(
            gate_4_effect(
                default_runs=default_runs,
                arm_runs=arm_runs,
                expects_rag={
                    arm: not profile.skip_rag and "tierB" in profile.enabled_tiers
                    for arm, profile in arms.items()
                },
            )
        )
    return results


def _run(base_url: str, api_key: str, player_id: str, selected: str) -> int:
    """Run the selected gates in order and return the process exit code."""
    started = time.perf_counter()
    arms = _declared_arms()
    print(f"Declared arms: {sorted(arms)}  |  cases: {[npc for npc, _ in PROBE_CASES]}")
    results: list[GateResult] = []
    if selected in ("all", "1"):
        results.append(gate_1_config())
    if results and not results[-1].passed:
        return _finish(results, arms, started)
    if selected in ("all", "3"):
        results.append(gate_3_isolation())
        if not results[-1].passed and selected == "all":
            return _finish(results, arms, started)
    with ProbeClient(base_url=base_url, api_key=api_key) as client:
        results.extend(_live_gates(client, arms, player_id, selected))
    return _finish(results, arms, started)


def _finish(results: list[GateResult], arms: dict[str, object], started: float) -> int:
    """Print every verdict, the MDE, the runtime, and return the exit code."""
    for result in results:
        print_gate(result)
    print_mde_section(comparisons=max(1, len(arms)))
    elapsed = time.perf_counter() - started
    failed = [r for r in results if not r.passed]
    print(f"\nArm probe runtime: {elapsed:.1f}s")
    if failed:
        print(f"RESULT: FAILED at gate {failed[0].number} ({failed[0].name})")
        return 1
    print(f"RESULT: all {len(results)} gate(s) passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the probe.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 when every selected gate passed, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        prog="python -m evals.arm_probe",
        description="P9 arm probe — four ordered gates over 2 cases x N arms at k=1.",
    )
    parser.add_argument("--gate", default="all", choices=["all", "1", "2", "3", "4"])
    parser.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", _DEFAULT_BASE_URL))
    parser.add_argument("--player-id", default=_DEFAULT_PLAYER_ID)
    parsed = parser.parse_args(sys.argv[1:] if argv is None else argv)
    api_key = os.environ.get("API_KEY_SECRET", "")
    if not api_key and parsed.gate in ("all", "2", "4"):
        print("ERROR: API_KEY_SECRET is not set; gates 2 and 4 need the live engine.")
        return 1
    return _run(parsed.base_url, api_key, parsed.player_id, parsed.gate)


if __name__ == "__main__":
    sys.exit(main())
