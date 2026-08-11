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
_DEFAULT_RETRIEVAL_PROFILE = "default"


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
) -> RunConfig:
    """Build a RunConfig from live engine config, git state, and judge resolution.

    Reads llm_config.yaml for generation parameters (model, temperature, top_p,
    max_tokens, prompt version); calls git for the commit SHA; calls
    judge_config.resolve_judge_model() for the judge model; computes
    golden_set_version from case file content via resolve_golden_set_version().

    Args:
        retrieval_profile: Named retrieval configuration; defaults to 'default'.
        cases_dir: Directory of eval case files used to compute golden_set_version;
            defaults to evals/cases/ relative to the repo root.
        config_path: Override path to the dialogue llm_config.yaml (for testing).
    Returns:
        Frozen RunConfig instance.
    Raises:
        JudgeModelCollisionError: If the resolved judge model equals the generation model.
        GoldenSetVersionError: If cases_dir is empty or missing.
        RuntimeError: If git rev-parse fails.
        FileNotFoundError: If llm_config.yaml cannot be found at config_path.
        KeyError: If llm_config.yaml is missing required keys (llm.model, etc.).
    """
    path = config_path or _DIALOGUE_LLM_CONFIG
    data = _read_llm_config(path)
    llm = data[_LLM_KEY]
    prompt = data[_PROMPT_KEY]

    generation_model = str(llm[_MODEL_KEY])
    judge_model = _judge_config.resolve_judge_model()

    return RunConfig(
        prompt_version=str(prompt[_VERSION_KEY]),
        generation_model=generation_model,
        temperature=float(llm[_TEMPERATURE_KEY]),
        top_p=float(llm[_TOP_P_KEY]),
        max_tokens=int(llm[_MAX_TOKENS_KEY]),
        judge_model=judge_model,
        retrieval_profile=retrieval_profile,
        git_sha=_resolve_git_sha(),
        golden_set_version=resolve_golden_set_version(cases_dir or _CASES_DIR),
    )
