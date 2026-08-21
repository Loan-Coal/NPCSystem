"""
Module: test_paired_arms
Layer: test (unit)
Purpose: Within-run paired arms (item C2) — `evals generate --profiles a,b` runs every case
         under each profile inside ONE generation, writes one gen dir per arm, and the two
         arms compare without being refused.
Dependencies: unittest.mock, pytest; paired_arms, generate_runner, compare (evals/, on
              pytest pythonpath).
Used by: pytest (make test / make check).

Why the pairing matters more than the ergonomics. A deployment-scoped switch forces a
BETWEEN-run design, putting world drift, model-load nondeterminism and judge sampling drift
inside the treatment effect. Arms are only paired — and McNemar therefore only valid — if
every case is generated under every profile against the same world state, adjacently in
time. A run that generated all of arm A and then all of arm B would satisfy the CLI and
break the statistics.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paired_arms import (
    ARM_SEPARATOR,
    PairedArmsError,
    arm_gen_id,
    collect_paired_records,
    parse_profiles,
)


# ---------------------------------------------------------------------------
# Parsing the flag
# ---------------------------------------------------------------------------


def test_parses_a_comma_separated_profile_list_in_order() -> None:
    assert parse_profiles("default,aggressive") == ("default", "aggressive")


def test_tolerates_whitespace_around_names() -> None:
    assert parse_profiles(" default , aggressive ") == ("default", "aggressive")


def test_a_single_profile_is_refused_because_it_is_not_a_paired_design() -> None:
    """--profiles default is --retrieval-profile default with a surprising output path.
    Refusing it keeps the flag meaning exactly one thing."""
    with pytest.raises(PairedArmsError):
        parse_profiles("default")


def test_a_repeated_profile_is_refused_rather_than_overwriting_its_own_arm() -> None:
    """Two identical names resolve to one gen dir, so the second arm would silently
    clobber the first and the comparison would be a run against itself."""
    with pytest.raises(PairedArmsError):
        parse_profiles("default,default")


def test_an_empty_flag_is_refused() -> None:
    with pytest.raises(PairedArmsError):
        parse_profiles(",")


def test_arm_gen_id_is_the_run_id_qualified_by_its_profile() -> None:
    assert arm_gen_id("k3_abc", "aggressive") == f"k3_abc{ARM_SEPARATOR}aggressive"


# ---------------------------------------------------------------------------
# The interleaved collection loop
# ---------------------------------------------------------------------------


def _spy_collectors() -> tuple[list[tuple[str, str, int]], object, object]:
    """Return (call log, yaml collector, ah collector) recording (case, profile, rep)."""
    calls: list[tuple[str, str, int]] = []

    def _yaml(case, client, base_url, rep, profile):
        calls.append((case["case_id"], profile, rep))
        return [f"{case['case_id']}|{profile}|{rep}"]

    def _ah(case, client, base_url, rep, profile):
        calls.append((case["npc_id"], profile, rep))
        return [f"{case['npc_id']}|{profile}|{rep}"]

    return calls, _yaml, _ah


def test_every_case_is_generated_under_every_profile() -> None:
    calls, yaml_fn, ah_fn = _spy_collectors()

    arms = collect_paired_records(
        yaml_cases=[{"case_id": "c1"}, {"case_id": "c2"}],
        ah_cases=[],
        client=MagicMock(),
        base_url="http://x",
        k=1,
        profiles=("default", "aggressive"),
        collect_yaml=yaml_fn,
        collect_ah=ah_fn,
    )

    assert set(arms) == {"default", "aggressive"}
    assert len(arms["default"]) == 2
    assert len(arms["aggressive"]) == 2


def test_arms_are_interleaved_per_case_not_run_one_after_the_other() -> None:
    """THE guard for C2. If arm A finishes before arm B starts, world drift and model-load
    nondeterminism sit between the arms and McNemar is measuring them too."""
    calls, yaml_fn, ah_fn = _spy_collectors()

    collect_paired_records(
        yaml_cases=[{"case_id": "c1"}, {"case_id": "c2"}],
        ah_cases=[],
        client=MagicMock(),
        base_url="http://x",
        k=1,
        profiles=("default", "aggressive"),
        collect_yaml=yaml_fn,
        collect_ah=ah_fn,
    )

    assert calls == [
        ("c1", "default", 0),
        ("c1", "aggressive", 0),
        ("c2", "default", 0),
        ("c2", "aggressive", 0),
    ]


def test_k_is_repetitions_per_arm_not_split_across_arms() -> None:
    """--k 3 with two profiles is 3 repetitions per arm and 6 calls per case. compare.py
    refuses a k mismatch, and k is per-arm, so splitting would make the arms uncomparable."""
    calls, yaml_fn, ah_fn = _spy_collectors()

    arms = collect_paired_records(
        yaml_cases=[{"case_id": "c1"}],
        ah_cases=[],
        client=MagicMock(),
        base_url="http://x",
        k=3,
        profiles=("default", "aggressive"),
        collect_yaml=yaml_fn,
        collect_ah=ah_fn,
    )

    assert len(arms["default"]) == 3
    assert len(arms["aggressive"]) == 3
    assert len(calls) == 6
    assert [rep for _case, _profile, rep in calls] == [0, 0, 1, 1, 2, 2]


def test_anti_hallucination_cases_are_paired_too() -> None:
    calls, yaml_fn, ah_fn = _spy_collectors()

    arms = collect_paired_records(
        yaml_cases=[],
        ah_cases=[{"npc_id": "npc_a"}],
        client=MagicMock(),
        base_url="http://x",
        k=1,
        profiles=("default", "aggressive"),
        collect_yaml=yaml_fn,
        collect_ah=ah_fn,
    )

    assert len(arms["default"]) == 1
    assert len(arms["aggressive"]) == 1


# ---------------------------------------------------------------------------
# Writing the arms, and the comparability contract between them
# ---------------------------------------------------------------------------


def _fake_run_config(profile: str = "default"):
    from run_config import RunConfig

    return RunConfig(
        prompt_version="v1.4",
        generation_model="qwen2.5:7b",
        temperature=0.7,
        top_p=0.95,
        max_tokens=512,
        judge_model="mixtral:8x7b",
        retrieval_profile=profile,
        git_sha="abc1234",
        golden_set_version="gsv123456789",
        harness_version="hv0123456789",
        dialogue_prompt_hash="dph012345678",
    )


def _post_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"npc_response": "Hello there!"}
    return resp


def _client() -> MagicMock:
    client = MagicMock()
    client.post.return_value = _post_response()
    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {"context_items": []}
    client.get.return_value = get_resp
    return client


def _yaml_case() -> dict:
    return {
        "case_id": "tc001",
        "seed": {"npc_id": "test_npc", "player_id": "test_player"},
        "input": {"player_message": "hello world"},
        "expected": [{"kind": "tone_judge", "description": "Should be friendly"}],
    }


@patch("generation_collection.preconditions.ensure_player_node")
def test_run_paired_writes_one_gen_dir_per_arm(mock_ensure: MagicMock, tmp_path: Path) -> None:
    from paired_arms import run_paired

    with patch("paired_arms.resolve_run_config", return_value=_fake_run_config()):
        paths = run_paired(
            yaml_cases=[_yaml_case()], ah_cases=[], client=_client(), base_url="http://x",
            out_dir=tmp_path, gen_id="k3_abc", k=1,
            profiles=("default", "aggressive"), cases_dir=None,
        )

    assert [p.name for p in paths] == [f"k3_abc{ARM_SEPARATOR}default", f"k3_abc{ARM_SEPARATOR}aggressive"]
    for path in paths:
        assert (path / "meta.json").exists()
        assert (path / "outputs.jsonl").exists()


@patch("generation_collection.preconditions.ensure_player_node")
def test_arms_differ_only_by_retrieval_profile(mock_ensure: MagicMock, tmp_path: Path) -> None:
    """The run config is resolved ONCE and copied per arm, so git_sha, model digests,
    harness_version and judge_model cannot drift between arms. Anything else differing
    would make the Differs: line name a cause that is not the independent variable."""
    from paired_arms import run_paired

    with patch("paired_arms.resolve_run_config", return_value=_fake_run_config()) as resolver:
        paths = run_paired(
            yaml_cases=[_yaml_case()], ah_cases=[], client=_client(), base_url="http://x",
            out_dir=tmp_path, gen_id="k3_abc", k=1,
            profiles=("default", "aggressive"), cases_dir=None,
        )

    assert resolver.call_count == 1, "resolving per arm would let git state or a model digest drift"
    configs = [json.loads((p / "meta.json").read_text(encoding="utf-8"))["config"] for p in paths]
    differing = {key for key in configs[0] if configs[0][key] != configs[1][key]}

    assert differing == {"retrieval_profile"}
    assert [c["retrieval_profile"] for c in configs] == ["default", "aggressive"]


@patch("generation_collection.preconditions.ensure_player_node")
def test_each_arm_requests_its_own_profile_from_the_engine(
    mock_ensure: MagicMock, tmp_path: Path,
) -> None:
    """An arm labelled 'aggressive' that sent no profile would be an arm claiming a
    variant it never ran — the exact failure the strict resolver exists to prevent."""
    from paired_arms import run_paired

    client = _client()
    with patch("paired_arms.resolve_run_config", return_value=_fake_run_config()):
        run_paired(
            yaml_cases=[_yaml_case()], ah_cases=[], client=client, base_url="http://x",
            out_dir=tmp_path, gen_id="k3_abc", k=1,
            profiles=("default", "aggressive"), cases_dir=None,
        )

    sent = [call.kwargs["json"]["retrieval_profile"] for call in client.post.call_args_list]

    assert sent == ["default", "aggressive"]


@patch("generation_collection.preconditions.ensure_player_node")
def test_two_arms_compare_without_refusal_and_the_report_names_the_variant(
    mock_ensure: MagicMock, tmp_path: Path,
) -> None:
    """Acceptance for C2: `evals compare <a> <b>` must report both arms, print a Differs:
    line naming retrieval_profile, and NOT refuse them on harness_version / judge / k."""
    from compare import compare_runs, format_report
    from paired_arms import run_paired

    with patch("paired_arms.resolve_run_config", return_value=_fake_run_config()):
        paths = run_paired(
            yaml_cases=[_yaml_case()], ah_cases=[], client=_client(), base_url="http://x",
            out_dir=tmp_path, gen_id="k3_abc", k=1,
            profiles=("default", "aggressive"), cases_dir=None,
        )

    for path, passed in zip(paths, (True, False)):
        row = {
            "record_id": "tc001:tone_judge:0", "case_id": "tc001", "judge_kind": "tone_judge",
            "passed": passed, "score": passed, "detail": "", "judge_model": "mixtral:8x7b",
            "repetition": 0,
        }
        (path / "judged.jsonl").write_text(json.dumps(row), encoding="utf-8")

    result = compare_runs(paths[0], paths[1])
    report = "\n".join(format_report(result))

    assert result.refusal_reason is None, result.refusal_reason
    assert result.intersection_size == 1
    assert "Differs:" in report
    assert "retrieval_profile" in report
    assert "aggressive" in report


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_generate_cli_rejects_profiles_without_a_gen_id() -> None:
    """Arms need one directory each; the legacy transcript format has nowhere to put them."""
    from generate_runner import main

    with pytest.raises(PairedArmsError):
        main(["--profiles", "default,aggressive", "--k", "1"])


def test_generate_cli_rejects_profiles_combined_with_a_single_retrieval_profile() -> None:
    """Two ways to name the arm is one way for them to disagree."""
    from generate_runner import main

    with pytest.raises(PairedArmsError):
        main([
            "--gen-id", "g1", "--profiles", "default,aggressive",
            "--retrieval-profile", "default",
        ])
