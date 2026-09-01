"""
Module: test_run_config
Layer: test (unit)
Purpose: Unit tests for evals/run_config.py — RunConfig model and resolve_run_config().
Dependencies: pathlib, yaml, run_config (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml

from run_config import (
    GoldenSetVersionError,
    ModelDigestUnavailableError,
    RunConfig,
    resolve_golden_set_version,
    resolve_run_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DIALOGUE_LLM_CONFIG = _REPO_ROOT / "src" / "npc_engine" / "engines" / "dialogue" / "llm_config.yaml"

_MINIMAL_CONFIG: dict = {
    "engine": "dialogue",
    "llm": {
        "backend": "ollama",
        "model": "test-model:7b",
        "temperature": 0.5,
        "max_tokens": 256,
        "top_p": 0.9,
        "stop_sequences": [],
    },
    "prompt": {
        "name": "dialogue_main",
        "version": 42,
    },
}


_STUB_GEN_DIGEST = "sha256:stub-generation"
_STUB_JUDGE_DIGEST = "sha256:stub-judge"
_STUB_OLLAMA_VERSION = "0.0.0-stub"


def _offline_probes(**overrides: object) -> dict:
    """Return resolve_run_config kwargs that never touch the network.

    tests/unit/conftest.py blocks real socket connects, and resolve_run_config now
    refuses a None digest, so every unit-test call injects its probes explicitly.
    """
    probes: dict = {
        "fetch_generation_digest": lambda _m, _u: _STUB_GEN_DIGEST,
        "fetch_judge_digest": lambda _m, _u: _STUB_JUDGE_DIGEST,
        "fetch_ollama_version_fn": lambda _u: _STUB_OLLAMA_VERSION,
        "fetch_corpus_fingerprint": lambda: None,
    }
    probes.update(overrides)
    return probes


@pytest.fixture()
def tmp_llm_config(tmp_path: Path) -> Path:
    """Write a minimal llm_config.yaml to a temp directory and return its path."""
    config_path = tmp_path / "llm_config.yaml"
    config_path.write_text(yaml.dump(_MINIMAL_CONFIG), encoding="utf-8")
    return config_path


def test_resolve_reads_dialogue_llm_config() -> None:
    """resolve_run_config() returns generation_model matching llm_config.yaml's llm.model."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    expected_data = yaml.safe_load(_DIALOGUE_LLM_CONFIG.read_text(encoding="utf-8"))
    assert config.generation_model == expected_data["llm"]["model"]


def test_resolve_reads_prompt_version() -> None:
    """resolve_run_config() returns prompt_version matching llm_config.yaml's prompt.version."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    expected_data = yaml.safe_load(_DIALOGUE_LLM_CONFIG.read_text(encoding="utf-8"))
    assert config.prompt_version == str(expected_data["prompt"]["version"])


def test_git_sha_is_seven_chars() -> None:
    """resolve_run_config() includes a non-empty 7-char git SHA.

    This went red on 2026-09-01 without any change to `run_config.py`: with `core.abbrev`
    unset, git auto-scales its abbreviation with the repository's object count, and the
    repo crossed the threshold from 7 to 8. `_resolve_git_sha` now pins `--short=7`.

    Do NOT repair a future failure here by loosening this to `>= 7`. The width is the
    point: these configs are compared across runs, so a `git_sha` that silently widens
    makes one commit record two different identities and breaks that comparison. If seven
    characters ever become ambiguous in this repository, widen the producer and this
    assertion together, deliberately.
    """
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    assert len(config.git_sha) == 7
    assert config.git_sha.strip()


def test_run_config_is_frozen(tmp_llm_config: Path) -> None:
    """RunConfig is immutable — setattr raises ValidationError (Pydantic frozen model)."""
    config = resolve_run_config(config_path=tmp_llm_config, **_offline_probes())
    # quality-ok: the assertion is 'any mutation is rejected' and the two model families raise different types (pydantic v2 frozen -> ValidationError, frozen dataclass -> FrozenInstanceError); narrowing per-site is deferred, see ISSUES
    with pytest.raises(Exception):
        setattr(config, "generation_model", "other")


def test_seed_field_present_defaults_to_none() -> None:
    """RunConfig has a seed field (DEC-176); it defaults to None for pre-EVAL-P20.0 artifacts."""
    assert "seed" in RunConfig.model_fields
    assert RunConfig.model_fields["seed"].default is None


def test_resolve_reads_seed_from_dialogue_llm_config() -> None:
    """The committed dialogue llm_config.yaml seed reaches RunConfig — guards silent removal."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG, **_offline_probes())
    expected_data = yaml.safe_load(_DIALOGUE_LLM_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(expected_data["llm"]["seed"], int)
    assert config.seed == expected_data["llm"]["seed"]


def test_resolve_seed_is_none_when_config_omits_it(tmp_llm_config: Path) -> None:
    """An engine config without a seed key resolves to None, not a KeyError."""
    config = resolve_run_config(config_path=tmp_llm_config, **_offline_probes())
    assert config.seed is None


def test_resolve_with_custom_retrieval_profile(tmp_path: Path, tmp_llm_config: Path) -> None:
    """resolve_run_config() forwards retrieval_profile; golden_set_version is computed from cases_dir."""
    case_file = tmp_path / "case.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")
    config = resolve_run_config(
        config_path=tmp_llm_config,
        retrieval_profile="strict",
        cases_dir=tmp_path,
        **_offline_probes(),
    )
    assert config.retrieval_profile == "strict"
    assert len(config.golden_set_version) == 12


def test_run_config_fields_from_minimal_yaml(tmp_llm_config: Path) -> None:
    """resolve_run_config() correctly maps all llm YAML fields to RunConfig attributes."""
    config = resolve_run_config(config_path=tmp_llm_config, **_offline_probes())
    assert config.generation_model == "test-model:7b"
    assert config.temperature == 0.5
    assert config.max_tokens == 256
    assert config.top_p == 0.9
    assert config.prompt_version == "42"


# ---------------------------------------------------------------------------
# EVAL-P1.5: honest golden_set_version
# ---------------------------------------------------------------------------


def test_golden_set_version_changes_when_a_case_changes(tmp_path: Path, tmp_llm_config: Path) -> None:
    """golden_set_version is content-derived — editing a case file changes the version."""
    case_file = tmp_path / "case_001.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")

    config_before = resolve_run_config(config_path=tmp_llm_config, cases_dir=tmp_path, **_offline_probes())

    case_file.write_text("prompt: world", encoding="utf-8")

    config_after = resolve_run_config(config_path=tmp_llm_config, cases_dir=tmp_path, **_offline_probes())

    assert config_before.golden_set_version != config_after.golden_set_version


def test_golden_set_version_stable_across_mtime_change(tmp_path: Path) -> None:
    """golden_set_version does not change when only a file's mtime changes."""
    case_file = tmp_path / "case.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")

    v1 = resolve_golden_set_version(tmp_path)

    # advance mtime by 5 seconds without touching content
    future = time.time() + 5
    os.utime(case_file, (future, future))

    v2 = resolve_golden_set_version(tmp_path)

    assert v1 == v2


def test_golden_set_version_error_on_empty_dir(tmp_path: Path) -> None:
    """resolve_golden_set_version raises GoldenSetVersionError when the directory is empty."""
    with pytest.raises(GoldenSetVersionError):
        resolve_golden_set_version(tmp_path)


def test_golden_set_version_error_on_missing_dir(tmp_path: Path) -> None:
    """resolve_golden_set_version raises GoldenSetVersionError when the directory is missing."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(GoldenSetVersionError):
        resolve_golden_set_version(missing)


def test_golden_set_version_is_12_hex_chars(tmp_path: Path) -> None:
    """resolve_golden_set_version returns a 12-character lowercase hex string."""
    (tmp_path / "case.yaml").write_text("a: 1", encoding="utf-8")
    version = resolve_golden_set_version(tmp_path)
    assert len(version) == 12
    assert all(c in "0123456789abcdef" for c in version)


# ---------------------------------------------------------------------------
# EVAL-P18.1: harness_version replaces golden_set_version as comparability key
# ---------------------------------------------------------------------------


def test_editing_a_judge_criteria_changes_harness_version(
    tmp_path: Path, tmp_llm_config: Path
) -> None:
    """harness_version changes when a judge criteria yaml file is edited."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "case_001.yaml").write_text("prompt: hello", encoding="utf-8")

    prompts_eval_dir = tmp_path / "prompts_eval"
    prompts_eval_dir.mkdir()
    judge_file = prompts_eval_dir / "refusal_judge.yaml"
    judge_file.write_text("criteria: do not hallucinate", encoding="utf-8")

    matchers_path = tmp_path / "matchers.py"
    matchers_path.write_text("# matchers stub", encoding="utf-8")

    config_before = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        **_offline_probes(),
    )

    judge_file.write_text("criteria: hallucination is acceptable", encoding="utf-8")

    config_after = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        **_offline_probes(),
    )

    assert config_before.harness_version != config_after.harness_version


def test_readme_in_cases_does_not_change_harness_version(
    tmp_path: Path, tmp_llm_config: Path
) -> None:
    """harness_version is stable when a non-yaml file is added to cases_dir."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "case_001.yaml").write_text("prompt: hello", encoding="utf-8")

    prompts_eval_dir = tmp_path / "prompts_eval"
    prompts_eval_dir.mkdir()
    (prompts_eval_dir / "refusal_judge.yaml").write_text("criteria: test", encoding="utf-8")

    matchers_path = tmp_path / "matchers.py"
    matchers_path.write_text("# matchers stub", encoding="utf-8")

    config_before = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        **_offline_probes(),
    )

    (cases_dir / "README.md").write_text("# Cases documentation", encoding="utf-8")

    config_after = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        **_offline_probes(),
    )

    assert config_before.harness_version == config_after.harness_version


# ---------------------------------------------------------------------------
# EVAL-P18.2: Record model identity, not model names
# ---------------------------------------------------------------------------


def test_meta_records_model_digest_not_just_tag(
    tmp_path: Path, tmp_llm_config: Path
) -> None:
    """Same model tag but different digest produces detectably different RunConfig instances."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "case.yaml").write_text("prompt: hi", encoding="utf-8")

    prompts_eval_dir = tmp_path / "prompts_eval"
    prompts_eval_dir.mkdir()
    (prompts_eval_dir / "judge.yaml").write_text("criteria: t", encoding="utf-8")

    matchers_path = tmp_path / "matchers.py"
    matchers_path.write_text("# stub", encoding="utf-8")

    dialogue_prompts_dir = tmp_path / "prompts"
    dialogue_prompts_dir.mkdir()
    (dialogue_prompts_dir / "d.yaml").write_text("p: x", encoding="utf-8")

    config_a = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        dialogue_prompts_dir=dialogue_prompts_dir,
        **_offline_probes(
            fetch_generation_digest=lambda _m, _u: "digest-v1",
            fetch_judge_digest=lambda _m, _u: "digest-jv1",
            fetch_ollama_version_fn=lambda _u: "0.1.0",
        ),
    )
    config_b = resolve_run_config(
        config_path=tmp_llm_config,
        cases_dir=cases_dir,
        prompts_eval_dir=prompts_eval_dir,
        matchers_path=matchers_path,
        dialogue_prompts_dir=dialogue_prompts_dir,
        **_offline_probes(
            fetch_generation_digest=lambda _m, _u: "digest-v2",
            fetch_judge_digest=lambda _m, _u: "digest-jv2",
            fetch_ollama_version_fn=lambda _u: "0.1.0",
        ),
    )

    assert config_a.generation_model == config_b.generation_model  # same tag
    assert config_a.generation_model_digest != config_b.generation_model_digest
    assert config_a.judge_model_digest != config_b.judge_model_digest
    assert config_a.ollama_version == "0.1.0"
    assert isinstance(config_a.judge_temperature, float)
    assert isinstance(config_a.dialogue_prompt_hash, str)
    assert len(config_a.dialogue_prompt_hash) == 12


# ---------------------------------------------------------------------------
# R2.1: a missing model digest is fatal, not silently recorded as None
# ---------------------------------------------------------------------------


def test_resolve_raises_when_digest_unavailable(tmp_llm_config: Path) -> None:
    """A digest fetcher returning None raises instead of recording an unattributable run."""
    with pytest.raises(ModelDigestUnavailableError):
        resolve_run_config(
            config_path=tmp_llm_config,
            **_offline_probes(fetch_generation_digest=lambda _m, _u: None),
        )


def test_resolve_raises_when_judge_digest_unavailable(tmp_llm_config: Path) -> None:
    """The judge digest is guarded too — self-evaluation metadata must be attributable."""
    with pytest.raises(ModelDigestUnavailableError):
        resolve_run_config(
            config_path=tmp_llm_config,
            **_offline_probes(fetch_judge_digest=lambda _m, _u: None),
        )
