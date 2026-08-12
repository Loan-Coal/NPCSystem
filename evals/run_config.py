"""
Module: run_config
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 run-config model capturing exact reproducibility metadata
         for one eval generation run: LLM config, judge model, git state, golden-set version.
Dependencies: pydantic, subprocess, logging, pathlib, yaml, judge_config (evals/).
Used by: evals/eval_records.py (EVAL-P1.3), evals/generate_runner.py (EVAL-P1.4).

Note: No ``seed`` field — LLMGenerateProtocol.generate() has no seed parameter and
ollama_adapter.py never sets options.seed. Claiming reproducibility via seed would be
dishonest (DEC-146). Retrieved context is an approximation from GET /v1/admin/debug/retrieval
which re-runs retrieval with session_turns=[] — also noted per EVAL-P1 constraint.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

import judge_config as _judge_config

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
_VERSION_KEY = "version"

_GOLDEN_SET_HEX_CHARS = 12
_HARNESS_VERSION_HEX_CHARS = 12
_DEFAULT_RETRIEVAL_PROFILE = "default"
_CASE_YAML_GLOB = "*.yaml"
_EVAL_PROMPTS_DIR = _REPO_ROOT / "prompts" / "eval"
_MATCHERS_FILE = _REPO_ROOT / "evals" / "matchers.py"


class GoldenSetVersionError(ValueError):
    """Raised when golden_set_version cannot be computed due to an empty or missing cases dir."""

    def __init__(self, cases_dir: Path) -> None:
        """Initialise with the offending directory path."""
        super().__init__(
            f"Cannot compute golden_set_version: no case files found in {cases_dir!r}. "
            "Provide a directory containing at least one case file."
        )
        self.cases_dir = cases_dir


class RunConfig(BaseModel):
    """Exact reproducibility snapshot for one eval generation run.

    Frozen so instances are immutable once created — safe to embed in TranscriptFile.

    Attributes:
        prompt_version: Dialogue prompt version from engines/dialogue/llm_config.yaml
            (string-coerced so it remains stable when the YAML value is non-integer).
        generation_model: LLM model name used for generation (e.g. 'qwen2.5:7b').
        temperature: Sampling temperature from llm_config.yaml.
        top_p: Top-p nucleus sampling parameter from llm_config.yaml.
        max_tokens: Maximum token budget per generation from llm_config.yaml.
        judge_model: LLM model used for judging (must differ from generation_model,
            enforced by judge_config.resolve_judge_model()).
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

    No ``seed`` field: LLMGenerateProtocol.generate() has no seed parameter and
    ollama_adapter.py never sets options.seed — claiming seed reproducibility would
    be dishonest (DEC-146).
    """

    model_config = ConfigDict(frozen=True)

    prompt_version: str
    generation_model: str
    temperature: float
    top_p: float
    max_tokens: int
    judge_model: str
    retrieval_profile: str
    git_sha: str
    golden_set_version: str
    harness_version: str


def resolve_golden_set_version(cases_dir: Path) -> str:
    """Compute a content-stable version hash from case file names and bytes.

    Hashes each file's name and byte content in sorted-name order with SHA-256.
    Returns the first 12 hex characters — stable across mtime changes, unstable
    across any content or naming edit.

    The retrieved context recorded in each GenerationRecord is an approximation
    (re-run from GET /v1/admin/debug/retrieval with session_turns=[]) — this hash
    describes what was in the case files, not what retrieval returned.

    Args:
        cases_dir: Directory containing eval case files.
    Returns:
        12-hex-char content hash string.
    Raises:
        GoldenSetVersionError: If cases_dir has no files (including missing dir).
    """
    try:
        files = sorted(
            (f for f in cases_dir.iterdir() if f.is_file()),
            key=lambda f: f.name,
        )
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        _logger.warning("golden_set_version: cannot list %s: %s", cases_dir, exc)
        files = []

    if not files:
        raise GoldenSetVersionError(cases_dir)

    digest = hashlib.sha256()
    for f in files:
        digest.update(f.name.encode())
        digest.update(f.read_bytes())

    return digest.hexdigest()[:_GOLDEN_SET_HEX_CHARS]


def _feed_case_files(digest: "hashlib._Hash", cases_dir: Path) -> None:
    for f in sorted(
        (f for f in cases_dir.rglob(_CASE_YAML_GLOB) if f.is_file()),
        key=lambda p: str(p.relative_to(cases_dir)),
    ):
        digest.update(str(f.relative_to(cases_dir)).encode())
        digest.update(f.read_bytes())


def _feed_prompt_yamls(digest: "hashlib._Hash", prompts_eval_dir: Path) -> None:
    try:
        prompt_files = sorted(
            (f for f in prompts_eval_dir.glob(_CASE_YAML_GLOB) if f.is_file()),
            key=lambda f: f.name,
        )
    except (FileNotFoundError, OSError) as exc:
        _logger.warning("harness_version: cannot list %s: %s", prompts_eval_dir, exc)
        return
    for f in prompt_files:
        digest.update(f.name.encode())
        digest.update(f.read_bytes())


def resolve_harness_version(
    *,
    cases_dir: Path,
    prompts_eval_dir: Path,
    matchers_path: Path,
) -> str:
    """Compute a content-stable harness version covering all comparability inputs.

    Hashes recursive .yaml case files, judge prompt .yaml files, and matchers.py.
    Non-yaml files (e.g. README.md) in cases_dir are excluded intentionally.

    Args:
        cases_dir: Root directory of eval cases; .yaml files discovered recursively.
        prompts_eval_dir: Directory containing judge criteria .yaml files.
        matchers_path: Path to evals/matchers.py (encodes judge sampling options).
    Returns:
        12-hex-char content hash string.
    Raises:
        FileNotFoundError: If matchers_path does not exist.
    """
    digest = hashlib.sha256()
    _feed_case_files(digest, cases_dir)
    _feed_prompt_yamls(digest, prompts_eval_dir)
    digest.update(matchers_path.read_bytes())
    return digest.hexdigest()[:_HARNESS_VERSION_HEX_CHARS]


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
) -> RunConfig:
    """Build a RunConfig from live engine config, git state, and judge resolution.

    Reads llm_config.yaml for generation parameters (model, temperature, top_p,
    max_tokens, prompt version); calls git for the commit SHA; calls
    judge_config.resolve_judge_model() for the judge model; computes
    golden_set_version from case file content and harness_version from all
    comparability inputs (cases, judge prompts, matchers).

    Args:
        retrieval_profile: Named retrieval configuration; defaults to 'default'.
        cases_dir: Directory of eval case files; defaults to evals/cases/.
        config_path: Override path to the dialogue llm_config.yaml (for testing).
        prompts_eval_dir: Override path to judge prompt .yaml directory (for testing);
            defaults to prompts/eval/ relative to the repo root.
        matchers_path: Override path to evals/matchers.py (for testing).
    Returns:
        Frozen RunConfig instance.
    Raises:
        JudgeModelCollisionError: If the resolved judge model equals the generation model.
        GoldenSetVersionError: If cases_dir is empty or missing.
        RuntimeError: If git rev-parse fails.
        FileNotFoundError: If llm_config.yaml or matchers_path cannot be found.
        KeyError: If llm_config.yaml is missing required keys (llm.model, etc.).
    """
    path = config_path or _DIALOGUE_LLM_CONFIG
    data = _read_llm_config(path)
    llm = data[_LLM_KEY]
    prompt = data[_PROMPT_KEY]

    generation_model = str(llm[_MODEL_KEY])
    judge_model = _judge_config.resolve_judge_model()

    resolved_cases_dir = cases_dir or _CASES_DIR
    return RunConfig(
        prompt_version=str(prompt[_VERSION_KEY]),
        generation_model=generation_model,
        temperature=float(llm[_TEMPERATURE_KEY]),
        top_p=float(llm[_TOP_P_KEY]),
        max_tokens=int(llm[_MAX_TOKENS_KEY]),
        judge_model=judge_model,
        retrieval_profile=retrieval_profile,
        git_sha=_resolve_git_sha(),
        golden_set_version=resolve_golden_set_version(resolved_cases_dir),
        harness_version=resolve_harness_version(
            cases_dir=resolved_cases_dir,
            prompts_eval_dir=prompts_eval_dir or _EVAL_PROMPTS_DIR,
            matchers_path=matchers_path or _MATCHERS_FILE,
        ),
    )
