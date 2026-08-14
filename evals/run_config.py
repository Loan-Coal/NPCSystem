"""
Module: run_config
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 run-config model capturing exact reproducibility metadata
         for one eval generation run: LLM config, judge model, model digests, git state,
         golden-set version, harness version, and dialogue prompt hash.
Dependencies: pydantic, subprocess, logging, pathlib, yaml, judge_config, engine_adapter,
              _run_config_hashing (evals/).
Used by: evals/eval_records.py (EVAL-P1.3), evals/generate_runner.py (EVAL-P1.4).

Note: ``seed`` is recorded and is real (EVAL-P20.0 / DEC-176, reversing the ``seed``-absent
half of DEC-146). LLMGenerateProtocol now carries an optional ``seed`` on generate/
generate_structured/stream; ollama_adapter.py sets ``options.seed``; and the dialogue engine
forwards the value from its llm_config.yaml — the same file this module reads temperature,
top_p and max_tokens from, so the recorded seed is exactly as trustworthy as those. DEC-146
was right that claiming a seed the adapter never sets is dishonest; this makes the claim true
rather than removing it. A seed is not a bit-identical guarantee across differing
model/quantisation/driver, which is why ``generation_model_digest`` and ``ollama_version``
are recorded alongside it. Retrieved context is an approximation from
GET /v1/admin/debug/retrieval which re-runs retrieval with session_turns=[] — also noted per
EVAL-P1 constraint.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import BaseModel, ConfigDict

import judge_config as _judge_config
from _run_config_hashing import (
    GoldenSetVersionError,
    hash_dialogue_prompts as _hash_dialogue_prompts,
    resolve_golden_set_version,
    resolve_harness_version,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_logger = logging.getLogger(__name__)
_DIALOGUE_LLM_CONFIG = (
    _REPO_ROOT / "src" / "npc_engine" / "engines" / "dialogue" / "llm_config.yaml"
)
_CASES_DIR = _REPO_ROOT / "evals" / "cases"

_LLM_KEY = "llm"
_PROMPT_KEY = "prompt"
_MODEL_KEY = "model"
_TEMPERATURE_KEY = "temperature"
_TOP_P_KEY = "top_p"
_MAX_TOKENS_KEY = "max_tokens"
_SEED_KEY = "seed"
_VERSION_KEY = "version"

_DEFAULT_RETRIEVAL_PROFILE = "default"
_EVAL_PROMPTS_DIR = _REPO_ROOT / "prompts" / "eval"
_MATCHERS_FILE = _REPO_ROOT / "evals" / "matchers.py"
_DIALOGUE_PROMPTS_DIR = _REPO_ROOT / "src" / "npc_engine" / "prompts"

# Re-export for callers that import from run_config (e.g. test_run_config.py).
__all__ = [
    "GoldenSetVersionError",
    "RunConfig",
    "resolve_golden_set_version",
    "resolve_run_config",
]


class RunConfig(BaseModel):
    """Exact reproducibility snapshot for one eval generation run.

    Frozen so instances are immutable once created — safe to embed in TranscriptFile.

    Attributes:
        prompt_version: Dialogue prompt version from engines/dialogue/llm_config.yaml
            (string-coerced so it remains stable when the YAML value is non-integer).
        generation_model: LLM model tag used for generation (e.g. 'qwen2.5:7b').
        generation_model_digest: Ollama content digest for generation_model (from
            /api/show). None when Ollama is unreachable at config resolution time.
        temperature: Sampling temperature from llm_config.yaml.
        top_p: Top-p nucleus sampling parameter from llm_config.yaml.
        max_tokens: Maximum token budget per generation from llm_config.yaml.
        seed: Deterministic sampling seed from llm_config.yaml, forwarded by the dialogue
            engine to the adapter's options.seed. None for runs generated before EVAL-P20.0
            (and for any engine that does not set one), which is why it defaults — the
            committed pre-seed artifact k3_73e6c36 must keep loading.
        judge_model: LLM model tag used for judging (must differ from generation_model,
            enforced by judge_config.resolve_judge_model()).
        judge_model_digest: Ollama content digest for judge_model (from /api/show).
            None when Ollama is unreachable at config resolution time.
        judge_temperature: Sampling temperature used by the binary judge, read from
            judge_config.resolve_judge_temperature() — the same call matchers.py
            makes for its Ollama request options, so this field can never drift from
            what the judge actually ran with.
        ollama_version: Ollama server version string (from /api/version).
            None when Ollama is unreachable at config resolution time.
        retrieval_profile: Named retrieval configuration applied during generation.
            Not yet wired to any retrieval configuration — the value is recorded for
            future use but does not currently select a retrieval strategy.
        git_sha: Short (7-char) git commit hash at the time resolve_run_config() ran.
        golden_set_version: First 12 hex chars of a SHA-256 digest over sorted case file
            names and bytes — changes on any content edit, stable across mtime-only changes.
        harness_version: First 12 hex chars of a SHA-256 digest covering all comparability
            inputs: recursive .yaml case files, prompts/eval/*.yaml judge criteria, and
            evals/matchers.py (which encodes judge sampling options). Replaces
            golden_set_version as the comparability key — two runs are comparable only
            when their harness_version values match.
        dialogue_prompt_hash: First 12 hex chars of a SHA-256 digest over all YAML files
            under src/npc_engine/prompts/ — changes when any runtime LLM prompt changes.

    The ``seed`` field is honest as of EVAL-P20.0 (DEC-176): the protocol carries an
    optional seed, ollama_adapter.py sets ``options.seed``, and the dialogue engine forwards
    the llm_config.yaml value on every structured call. Two runs at the same seed with the
    same harness_version reproduce text, which is what lets human labels survive a
    regeneration. This reverses only the ``seed``-absent half of DEC-146; DEC-146's
    objection — that a recorded seed the adapter never sets is a lie — stands, and is
    answered by making the seed real rather than by dropping the field.
    """

    model_config = ConfigDict(frozen=True)

    prompt_version: str
    generation_model: str
    generation_model_digest: str | None = None
    temperature: float
    top_p: float
    max_tokens: int
    seed: int | None = None
    judge_model: str
    judge_model_digest: str | None = None
    judge_temperature: float = _judge_config.DEFAULT_JUDGE_TEMPERATURE
    ollama_version: str | None = None
    retrieval_profile: str
    git_sha: str
    golden_set_version: str
    harness_version: str
    dialogue_prompt_hash: str = ""


def _read_llm_config(config_path: Path) -> dict[str, Any]:
    """Parse an engine llm_config.yaml and return its raw dict.

    Args:
        config_path: Path to the YAML file.
    Returns:
        Parsed YAML dict (never None — missing file raises before this returns).
    Raises:
        FileNotFoundError: If config_path does not exist.
    """
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _resolve_git_sha() -> str:
    """Return the short (7-char) HEAD commit hash via subprocess.

    Returns:
        7-character hex SHA string.
    Raises:
        RuntimeError: If git is unavailable or the working tree is not a repository.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def resolve_run_config(
    *,
    retrieval_profile: str = _DEFAULT_RETRIEVAL_PROFILE,
    cases_dir: Path | None = None,
    config_path: Path | None = None,
    prompts_eval_dir: Path | None = None,
    matchers_path: Path | None = None,
    dialogue_prompts_dir: Path | None = None,
    fetch_generation_digest: Callable[[str, str], str | None] | None = None,
    fetch_judge_digest: Callable[[str, str], str | None] | None = None,
    fetch_ollama_version_fn: Callable[[str], str | None] | None = None,
    judge_temperature: float | None = None,
) -> RunConfig:
    """Build a RunConfig from live engine config, git state, and judge resolution.

    Reads llm_config.yaml for generation parameters (model, temperature, top_p,
    max_tokens, prompt version); calls git for the commit SHA; calls
    judge_config.resolve_judge_model() for the judge model; computes
    golden_set_version from case file content and harness_version from all
    comparability inputs (cases, judge prompts, matchers); probes Ollama for model
    digests and server version.

    Args:
        retrieval_profile: Named retrieval configuration; defaults to 'default'.
        cases_dir: Directory of eval case files; defaults to evals/cases/.
        config_path: Override path to the dialogue llm_config.yaml (for testing).
        prompts_eval_dir: Override path to judge prompt .yaml directory (for testing);
            defaults to prompts/eval/ relative to the repo root.
        matchers_path: Override path to evals/matchers.py (for testing).
        dialogue_prompts_dir: Override path to runtime prompt tree (for testing);
            defaults to src/npc_engine/prompts/.
        fetch_generation_digest: Callable(model, url) -> digest; defaults to
            engine_adapter.fetch_model_digest. Injectable for tests.
        fetch_judge_digest: Callable(model, url) -> digest; defaults to
            engine_adapter.fetch_model_digest. Injectable for tests.
        fetch_ollama_version_fn: Callable(url) -> version; defaults to
            engine_adapter.fetch_ollama_version. Injectable for tests.
        judge_temperature: Sampling temperature used by the binary judge; defaults to
            judge_config.resolve_judge_temperature() — the same value matchers.py
            uses for its Ollama request options, so the two can never drift apart.
            Injectable for tests.
    Returns:
        Frozen RunConfig instance.
    Raises:
        JudgeModelCollisionError: If the resolved judge model equals the generation model.
        GoldenSetVersionError: If cases_dir is empty or missing.
        RuntimeError: If git rev-parse fails.
        FileNotFoundError: If llm_config.yaml or matchers_path cannot be found.
        KeyError: If llm_config.yaml is missing required keys (llm.model, etc.).
    """
    import engine_adapter as _engine_adapter

    path = config_path or _DIALOGUE_LLM_CONFIG
    data = _read_llm_config(path)
    llm = data[_LLM_KEY]
    prompt = data[_PROMPT_KEY]

    generation_model = str(llm[_MODEL_KEY])
    judge_model = _judge_config.resolve_judge_model()
    ollama_url = _judge_config.resolve_judge_url()
    resolved_judge_temperature = (
        judge_temperature
        if judge_temperature is not None
        else _judge_config.resolve_judge_temperature()
    )

    gen_digest_fn = fetch_generation_digest or _engine_adapter.fetch_model_digest
    judge_digest_fn = fetch_judge_digest or _engine_adapter.fetch_model_digest
    version_fn = fetch_ollama_version_fn or _engine_adapter.fetch_ollama_version

    resolved_cases_dir = cases_dir or _CASES_DIR
    resolved_prompts_dir = dialogue_prompts_dir or _DIALOGUE_PROMPTS_DIR

    return RunConfig(
        prompt_version=str(prompt[_VERSION_KEY]),
        generation_model=generation_model,
        generation_model_digest=gen_digest_fn(generation_model, ollama_url),
        temperature=float(llm[_TEMPERATURE_KEY]),
        top_p=float(llm[_TOP_P_KEY]),
        max_tokens=int(llm[_MAX_TOKENS_KEY]),
        seed=llm.get(_SEED_KEY),
        judge_model=judge_model,
        judge_model_digest=judge_digest_fn(judge_model, ollama_url),
        judge_temperature=resolved_judge_temperature,
        ollama_version=version_fn(ollama_url),
        retrieval_profile=retrieval_profile,
        git_sha=_resolve_git_sha(),
        golden_set_version=resolve_golden_set_version(resolved_cases_dir),
        harness_version=resolve_harness_version(
            cases_dir=resolved_cases_dir,
            prompts_eval_dir=prompts_eval_dir or _EVAL_PROMPTS_DIR,
            matchers_path=matchers_path or _MATCHERS_FILE,
        ),
        dialogue_prompt_hash=_hash_dialogue_prompts(resolved_prompts_dir),
    )
