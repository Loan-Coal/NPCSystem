"""
Module: arm_probe_gates
Layer: evals (eval harness — not part of src/)
Purpose: The four P9 gates, in order. Each is independently runnable and each fails
         LOUDLY with a reason rather than passing silently on an empty input.
Does NOT: print, parse argv, or decide the exit code — that is arm_probe.py.
Dependencies injected: the ProbeClient and the arm list are arguments.
Used by: evals.arm_probe.

THE ORDER IS LOAD-BEARING
  1 config  -> the arms differ from default in exactly one field, and one TIER
  2 corpus  -> item_count > 0 AND the fingerprint is IDENTICAL across arms
  3 isolation -> no cache-key collision between an arm and default
  4 effect  -> receipts whose item_keys differ, with tier B actually carrying something

Each is meaningless until the previous holds, and the failure modes are silent ones:
  * a cache-isolation test passes trivially when every arm retrieves nothing, which is
    what had been happening on every run ever recorded (tierB.items == 0). That is why
    gate 2 goes SECOND rather than last.
  * gate 4 would pass on tier-A noise if it only compared item_keys. An arm whose runs
    both carry zero tier-B items is not evidence that retrieval did anything, so that
    case is an explicit FAILURE here, not a pass.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Sequence

from arm_probe_client import ProbeClient
from arm_probe_models import ArmObservation, GateResult

__all__ = [
    "CONFIG_GATE_TESTS",
    "ISOLATION_GATE_TESTS",
    "gate_1_config",
    "gate_2_corpus",
    "gate_3_isolation",
    "gate_4_effect",
]

CONFIG_GATE_TESTS = "tests/unit/config/test_shipped_retrieval_profiles.py"
ISOLATION_GATE_TESTS = "tests/unit/retrieval/test_partial_cache_profile_isolation.py"

_TIER_B = "tierB"
_CORPUS_IDENTITY_FIELDS = (
    "corpus_item_count",
    "corpus_embedding_model",
    "corpus_embedding_dim",
    "corpus_sha",
)


def _run_pytest(path: str, number: int, name: str) -> GateResult:
    """Run one pytest module as a gate and turn its verdict into a GateResult."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "-p", "no:cacheprovider", "--no-cov"],
        capture_output=True,
        text=True,
    )
    tail = [line for line in completed.stdout.splitlines() if line.strip()][-6:]
    return GateResult(
        number=number,
        name=name,
        passed=completed.returncode == 0,
        detail=(path, *tail),
    )


def gate_1_config(*, tests_path: str = CONFIG_GATE_TESTS) -> GateResult:
    """Gate 1 — every declared arm differs from default in exactly one field, one tier.

    Args:
        tests_path: The pytest module to run.
    Returns:
        The gate's verdict, carrying pytest's own summary lines as evidence.
    """
    return _run_pytest(tests_path, 1, "config: one arm, one knob, one tier")


def gate_2_corpus(
    *, client: ProbeClient, arms: Sequence[str], corpus_fields: Any
) -> GateResult:
    """Gate 2 — the corpus is non-empty and its fingerprint is IDENTICAL across arms.

    Reads the fields RunConfig RECORDS (via `_run_config_corpus.corpus_fields`, the same
    resolver `resolve_run_config` calls) rather than probing independently, so this gate
    checks the thing a generation record will actually carry. `paired_arms` interleaves
    arms inside one run — rep, then case, then profile — so a corpus that moved mid-run
    would land unevenly across arms and be indistinguishable from a treatment effect
    (DEC-210). Identical-across-arms is the check; non-zero alone is not.

    Args:
        client: Authenticated probe client.
        arms: Arm names to resolve the fingerprint under.
        corpus_fields: The `_run_config_corpus.corpus_fields` callable.
    Returns:
        The gate's verdict.
    """
    detail: list[str] = []
    report = client.rehydrate()
    detail.append(
        f"rehydrate: nodes_read={report['nodes_read']} upserted={report['upserted']} "
        f"missing_embedding={report['missing_embedding']} "
        f"reconcile_passes={report['reconcile_passes']}"
    )
    if int(report["nodes_read"]) == 0:
        detail.append("FAIL: rehydrate read ZERO nodes — the corpus cannot be populated")
        return GateResult(number=2, name="corpus", passed=False, detail=tuple(detail))

    per_arm = {arm: corpus_fields(client.corpus_fingerprint) for arm in arms}
    for arm, fields in per_arm.items():
        detail.append(
            f"  {arm:<14} item_count={fields.get('corpus_item_count')} "
            f"model={fields.get('corpus_embedding_model')} "
            f"dim={fields.get('corpus_embedding_dim')} "
            f"sha={str(fields.get('corpus_sha'))[:16]}..."
        )
    return _judge_corpus(per_arm, detail)


def _judge_corpus(per_arm: dict[str, Any], detail: list[str]) -> GateResult:
    """Decide gate 2 from the per-arm fingerprints. Split out for the 40-line cap."""
    missing = [arm for arm, fields in per_arm.items() if not fields]
    if missing:
        detail.append(f"FAIL: the engine could not be asked for the corpus under {missing}")
        return GateResult(number=2, name="corpus", passed=False, detail=tuple(detail))

    counts = {fields["corpus_item_count"] for fields in per_arm.values()}
    if counts == {0}:
        detail.append("FAIL: item_count is 0 — every arm would retrieve nothing")
        return GateResult(number=2, name="corpus", passed=False, detail=tuple(detail))

    for field in _CORPUS_IDENTITY_FIELDS:
        values = {str(fields.get(field)) for fields in per_arm.values()}
        if len(values) != 1:
            detail.append(f"FAIL: {field} DIFFERS across arms: {sorted(values)}")
            return GateResult(number=2, name="corpus", passed=False, detail=tuple(detail))
        if field == "corpus_sha" and not values.pop():
            detail.append(
                "FAIL: corpus_sha is EMPTY — identical-across-arms would be vacuous, and "
                "membership is the only field that can detect the corpus moving"
            )
            return GateResult(number=2, name="corpus", passed=False, detail=tuple(detail))
    detail.append("fingerprint identical across all arms, and non-empty")
    return GateResult(number=2, name="corpus", passed=True, detail=tuple(detail))


def gate_3_isolation(*, tests_path: str = ISOLATION_GATE_TESTS) -> GateResult:
    """Gate 3 — one arm is never served another arm's cached data (P7, DEC-207).

    Args:
        tests_path: The pytest module to run.
    Returns:
        The gate's verdict.
    """
    return _run_pytest(tests_path, 3, "isolation: no cache-key collision between arms")


def _pairing_verdict(
    *, arm: str, expects_rag: bool, default_runs: list[ArmObservation],
    arm_runs: list[ArmObservation],
) -> tuple[bool, list[str]]:
    """Score one (default vs arm) pairing across every case. Returns (passed, lines)."""
    lines: list[str] = []
    differing = [
        d.npc_id for d, a in zip(default_runs, arm_runs) if d.item_keys != a.item_keys
    ]
    exposed = [
        d.npc_id
        for d, a in zip(default_runs, arm_runs)
        if max(d.tier_items(_TIER_B), a.tier_items(_TIER_B)) > 0
    ]
    arm_tier_b = [a.tier_items(_TIER_B) for a in arm_runs]
    lines.append(
        f"  {arm:<14} item_keys differ on {len(differing)}/{len(arm_runs)} cases "
        f"{differing}; arm tierB items={arm_tier_b}; "
        f"default tierB items={[d.tier_items(_TIER_B) for d in default_runs]}"
    )
    passed = True
    if not differing:
        supply = ", ".join(
            f"{d.npc_id}: event:={d.count_keys('event:')} rag:={d.count_keys('rag:')}"
            for d in default_runs
        )
        lines.append(f"  FAIL {arm}: item_keys IDENTICAL to default on every case")
        lines.append(
            f"       supply at default ({supply}) — if the arm raises a limit above "
            f"these, it has NO EXPOSURE and a paired run of it is a guaranteed null"
        )
        passed = False
    if len(exposed) != len(arm_runs):
        lines.append(
            f"  FAIL {arm}: some case carried ZERO tier-B items in BOTH runs — any "
            f"item_keys difference there is tier-A noise, not retrieval"
        )
        passed = False
    if expects_rag and not all(count > 0 for count in arm_tier_b):
        lines.append(f"  FAIL {arm}: a RAG arm assembled zero tier-B items")
        passed = False
    if not expects_rag and any(count > 0 for count in arm_tier_b):
        lines.append(f"  FAIL {arm}: a no-RAG arm assembled tier-B items anyway")
        passed = False
    return passed, lines


def gate_4_effect(
    *, default_runs: list[ArmObservation], arm_runs: dict[str, list[ArmObservation]],
    expects_rag: dict[str, bool],
) -> GateResult:
    """Gate 4 — every arm produces receipts that differ from default, with tier B live.

    Config-differs plus keys-differ is NOT sufficient. An arm whose two runs both carry
    zero tier-B items has demonstrated nothing about retrieval, so that is a failure
    here rather than a pass on tier-A noise.

    Args:
        default_runs: The default arm's observation per case, in case order.
        arm_runs: Each arm's observations per case, in the same case order.
        expects_rag: Whether each arm should assemble tier-B items at all.
    Returns:
        The gate's verdict.
    """
    if not default_runs or not arm_runs:
        return GateResult(
            number=4, name="effect", passed=False,
            detail=("FAIL: nothing was observed — an empty probe must not read as a pass",),
        )
    detail: list[str] = []
    passed = True
    for arm, runs in arm_runs.items():
        arm_passed, lines = _pairing_verdict(
            arm=arm, expects_rag=expects_rag[arm],
            default_runs=default_runs, arm_runs=runs,
        )
        detail.extend(lines)
        passed = passed and arm_passed
    return GateResult(number=4, name="effect", passed=passed, detail=tuple(detail))
