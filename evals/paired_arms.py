"""
Module: paired_arms
Layer: evals (eval harness — not part of src/)
Purpose: Within-run paired A/B arms. Runs every case under every named retrieval profile
         inside ONE generation, interleaved per case, and writes one generation directory
         per arm so `evals compare <a> <b>` works unchanged.
Dependencies: pathlib, typing; eval_records (write_generation_dir), run_config
         (RunConfig, resolve_run_config); generation_collection (imported inside
         run_paired only, to keep this module's import graph acyclic)
Used by: generate_runner (the --profiles CLI path); tests/unit/evals/test_paired_arms.py
Does NOT: perform HTTP itself, build records, judge, or import from src/npc_engine/ — the
         per-case collectors are injected so this module stays a pure orchestrator and
         cannot import generation_collection in a cycle.

Dependencies injected: collect_yaml / collect_ah callables and the httpx client are passed
in per call; nothing is read from module-level state.

WHY ONE DIRECTORY PER ARM RATHER THAN ONE DIRECTORY HOLDING BOTH (see DEC-195).
Everything downstream of generation groups by `case_id`: compare._build_case_stats,
summary, report, and the regression gate. `record_id` is `<case>:<kind>:<index>` and the
labelled unit is `record_id#r<rep>` (record_identity.py) — neither carries an arm. Two arms
sharing one directory would therefore collapse into a single CaseStat and a single labelled
item, silently averaging the treatment away. Making them distinct means changing record
identity, which invalidates every existing human label. One directory per arm keeps identity
untouched, keeps every case_id grouping correct, and costs only a directory name.

The pairing that McNemar requires is preserved by INTERLEAVING: each case is generated under
every profile back to back, against one world state and one engine build, before the run
moves on. All of arm A followed by all of arm B would satisfy the same CLI and put world
drift inside the treatment effect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from eval_records import write_generation_dir
from run_config import RunConfig, resolve_run_config

__all__ = [
    "ARM_SEPARATOR",
    "MIN_ARMS",
    "PairedArmsError",
    "arm_gen_id",
    "collect_paired_records",
    "parse_profiles",
    "run_paired",
]

ARM_SEPARATOR: str = "__"
"""Separator between a run's gen_id and its arm's profile name.

Double underscore rather than ':' or '-': the arm name becomes a directory name on
Windows, and gen_ids already contain single underscores (`k3_73e6c36`).
"""

MIN_ARMS: int = 2
"""Fewest profiles `--profiles` accepts. One profile is `--retrieval-profile` with a
surprising output path, and admitting it would give the flag two meanings."""

# Collector signature: (case, client, base_url, repetition, retrieval_profile) -> records.
CaseCollector = Callable[[dict, Any, str, int, str], list[Any]]


class PairedArmsError(ValueError):
    """Raised when a paired-arm run is configured in a way that cannot produce valid arms.

    Attributes:
        reason: Human-readable description of what is wrong with the request.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def parse_profiles(raw: str) -> tuple[str, ...]:
    """Parse the `--profiles` value into an ordered tuple of arm names.

    Args:
        raw: Comma-separated profile names, e.g. "default,aggressive".
    Returns:
        Profile names in the order given, which is the order arms are written in.
    Raises:
        PairedArmsError: When fewer than MIN_ARMS names are given, or a name repeats.
            A repeat is refused rather than de-duplicated because two identical names
            resolve to one directory: the second arm would overwrite the first and the
            comparison would silently become a run against itself.
    """
    names = tuple(part.strip() for part in raw.split(",") if part.strip())
    if len(names) < MIN_ARMS:
        raise PairedArmsError(
            f"--profiles needs at least {MIN_ARMS} names to form a paired design, got {names!r}. "
            "Use --retrieval-profile for a single-arm run."
        )
    if len(set(names)) != len(names):
        raise PairedArmsError(f"--profiles contains a repeated name: {names!r}")
    return names


def arm_gen_id(gen_id: str, profile: str) -> str:
    """Return the generation id for one arm of a paired run.

    Args:
        gen_id: The run's base identifier.
        profile: The arm's retrieval-profile name.
    Returns:
        e.g. 'k3_abc__aggressive'. Also used verbatim as the arm's directory name.
    """
    return f"{gen_id}{ARM_SEPARATOR}{profile}"


def collect_paired_records(
    *,
    yaml_cases: Sequence[dict],
    ah_cases: Sequence[dict],
    client: Any,
    base_url: str,
    k: int,
    profiles: Sequence[str],
    collect_yaml: CaseCollector,
    collect_ah: CaseCollector,
) -> dict[str, list[Any]]:
    """Generate every case under every profile, interleaved per case, into per-arm lists.

    `k` is repetitions PER ARM, not shared across them: an arm is the unit compare.py
    intersects, it refuses a k mismatch between two runs, and each arm's meta.json records
    this same k. Two profiles at k=3 therefore make 6 dialogue calls per case.

    Args:
        yaml_cases: Loaded YAML eval cases.
        ah_cases: Loaded anti-hallucination fixture cases.
        client: Active httpx.Client with auth headers.
        base_url: NPC engine base URL.
        k: Repetitions per case per arm.
        profiles: Arm names, in output order.
        collect_yaml: Per-case collector for YAML cases.
        collect_ah: Per-case collector for anti-hallucination cases.
    Returns:
        Mapping of profile name to that arm's records, in generation order.
    """
    arms: dict[str, list[Any]] = {profile: [] for profile in profiles}
    for rep in range(k):
        for case in yaml_cases:
            for profile in profiles:
                arms[profile].extend(collect_yaml(case, client, base_url, rep, profile))
        for case in ah_cases:
            for profile in profiles:
                arms[profile].extend(collect_ah(case, client, base_url, rep, profile))
    return arms


def _arm_config(base: RunConfig, profile: str) -> RunConfig:
    """Return the base run config re-labelled for one arm.

    Copied rather than re-resolved so git_sha, model digests, ollama_version,
    harness_version and judge_model are identical across arms by construction. Re-resolving
    per arm would let those drift mid-run and the report's `Differs:` line would then name
    a cause that is not the independent variable.
    """
    return base.model_copy(update={"retrieval_profile": profile})


def _write_arms(
    *,
    out_dir: Path,
    gen_id: str,
    k: int,
    profiles: Sequence[str],
    arms: dict[str, list[Any]],
    base_config: RunConfig,
) -> tuple[Path, ...]:
    """Write each arm to its own generation directory and return the paths, in order."""
    written: list[Path] = []
    for profile in profiles:
        arm_id = arm_gen_id(gen_id, profile)
        arm_dir = out_dir / arm_id
        write_generation_dir(
            arm_dir, arms[profile], gen_id=arm_id, k=k, config=_arm_config(base_config, profile),
        )
        written.append(arm_dir)
    return tuple(written)


def run_paired(
    *, yaml_cases: Sequence[dict], ah_cases: Sequence[dict], client: Any, base_url: str,
    out_dir: Path, gen_id: str, k: int, profiles: Sequence[str],
    cases_dir: Path | None = None, config: RunConfig | None = None,
) -> tuple[Path, ...]:
    """Run a paired-arm generation and write one gen directory per arm.

    The run config is resolved ONCE, before the (slow) generation pass, so a misconfigured
    run fails in seconds and every arm shares one reproducibility snapshot.

    Args:
        yaml_cases, ah_cases: Eval cases to process.
        client, base_url: Active httpx.Client and engine base URL.
        out_dir: Base directory; each arm becomes a subdirectory of it.
        gen_id: Base run identifier; each arm's id is arm_gen_id(gen_id, profile).
        k: Repetitions per case per arm.
        profiles: Arm names, in output order.
        cases_dir: Case directory used to compute golden_set_version.
        config: Pre-resolved run config; resolved from the live repo when omitted.
    Returns:
        One path per arm, in the order the profiles were given.
    Raises:
        JudgeModelCollisionError, GoldenSetVersionError: From resolve_run_config.
    """
    import generation_collection

    base_config = config or resolve_run_config(cases_dir=cases_dir, retrieval_profile=profiles[0])
    arms = collect_paired_records(
        yaml_cases=yaml_cases, ah_cases=ah_cases, client=client, base_url=base_url, k=k,
        profiles=profiles,
        collect_yaml=generation_collection.collect_yaml_case_records,
        collect_ah=generation_collection.collect_ah_case_records,
    )
    return _write_arms(
        out_dir=out_dir, gen_id=gen_id, k=k, profiles=profiles, arms=arms,
        base_config=base_config,
    )
