"""
Module: judge_config
Layer: evals (eval harness — not part of src/)
Purpose: Resolve the LLM-judge model/URL/timeout/temperature and enforce the judge !=
         generation model separation invariant (no self-evaluation).
Dependencies: os, glob, pathlib, logging, yaml.
Used by: evals/matchers.py, evals/run_config.py, and e2e/helpers/judge_client.py
         (single source of truth — matchers.py's judge call and run_config.py's
         provenance record read the same resolve_judge_temperature() value).
Does NOT: import from src/npc_engine/ (keeps evals/ src-free), call any LLM.

The judge model MUST differ from every engine generation model. The generation
models are discovered by reading the per-engine ``llm_config.yaml`` files — all five
currently declare qwen2.5:7b (DEC-149). An exact collision (judge == a generation
model, e.g. qwen2.5:7b) is a hard failure (JudgeModelCollisionError). A same-family
judge (e.g. qwen2.5:14b against a qwen2.5:7b fleet) is allowed but logs a loud
warning. Default judge: mixtral:8x7b (different family, per DEC-143).
"""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path

import yaml

DEFAULT_JUDGE_MODEL = "mixtral:8x7b"
DEFAULT_JUDGE_URL = "http://localhost:11434"
DEFAULT_JUDGE_TIMEOUT_S = 30.0
DEFAULT_JUDGE_TEMPERATURE = 0.0

# Three-model judge panel roster (EVAL-P21.0, DEC-183). mixtral:8x7b + qwen2.5:14b
# (same-family-as-generation, allowed with a warning) + llama3.1:8b (the
# out-of-family third seat, chosen via AskUserQuestion over gemma2:9b — both are
# fully independent from Qwen/Mixtral; llama3.1:8b was picked for its smaller
# footprint). qwen2.5:14b and qwen2.5:7b are NOT independent raters (shared
# tokenizer/corpus/tuning recipe → correlated errors); under 2-of-3 consensus a
# same-family pair would effectively cast one vote with a veto, outvoting the
# out-of-family judge whenever the pair agrees — see EVAL-P21.0's roadmap text.
DEFAULT_PANEL_MODELS: tuple[str, ...] = ("mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b")

_ENGINES_GLOB = "src/npc_engine/engines/*/llm_config.yaml"
_LLM_KEY = "llm"
_MODEL_KEY = "model"
_FAMILY_SEPARATOR = ":"

_ENV_JUDGE_MODEL = "JUDGE_MODEL"
_ENV_JUDGE_URL = "JUDGE_OLLAMA_URL"
_ENV_JUDGE_TIMEOUT = "JUDGE_TIMEOUT_SECONDS"
_ENV_JUDGE_TEMPERATURE = "JUDGE_TEMPERATURE"

_logger = logging.getLogger(__name__)


class JudgeModelCollisionError(Exception):
    """Raised when the resolved judge model equals an engine generation model.

    Self-evaluation (judge == generator) invalidates the eval; this fails loud
    rather than silently producing biased scores. Mirrors the local-exception
    precedent of ``EvalConfigError`` in matchers.py (keeps evals/ src-free).
    """

    def __init__(self, judge_model: str, generation_models: tuple[str, ...]) -> None:
        self.judge_model = judge_model
        self.generation_models = generation_models
        super().__init__(
            f"Judge model {judge_model!r} collides with an engine generation model "
            f"(generation models: {', '.join(generation_models)}). The judge MUST "
            f"differ from every generation model to avoid self-evaluation."
        )


def _repo_root() -> Path:
    """Return the repository root (parent of the evals/ directory)."""
    return Path(__file__).resolve().parents[1]


def _read_model(config_path: Path) -> str | None:
    """Return the ``llm.model`` declared in one engine llm_config.yaml, or None."""
    try:
        with config_path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except OSError as exc:
        _logger.warning("_read_model: cannot read %s: %s", config_path, exc)
        return None
    model = data.get(_LLM_KEY, {}).get(_MODEL_KEY)
    return str(model) if model else None


def discover_generation_models(repo_root: Path | None = None) -> tuple[str, ...]:
    """Discover the distinct generation models declared by the engine LLM configs.

    Args:
        repo_root: Repository root; defaults to the parent of evals/.
    Returns:
        Sorted unique tuple of generation model names (empty if none found).
    """
    root = repo_root or _repo_root()
    found: set[str] = set()
    for path_str in glob.glob(str(root / _ENGINES_GLOB)):
        model = _read_model(Path(path_str))
        if model:
            found.add(model)
    return tuple(sorted(found))


def _family(model: str) -> str:
    """Return a model's family (the part before the first ':')."""
    return model.split(_FAMILY_SEPARATOR, 1)[0]


def resolve_judge_model(
    *,
    requested: str | None = None,
    generation_models: tuple[str, ...] | None = None,
    logger: logging.Logger | None = None,
) -> str:
    """Resolve the judge model and enforce the separation invariant.

    Args:
        requested: Explicit judge model; falls back to env JUDGE_MODEL then default.
        generation_models: Generation models to check against; discovered if None.
        logger: Logger for the same-family warning; defaults to the module logger.
    Returns:
        The resolved judge model name.
    Raises:
        JudgeModelCollisionError: If the resolved judge equals a generation model.
    """
    judge = requested or os.getenv(_ENV_JUDGE_MODEL) or DEFAULT_JUDGE_MODEL
    gens = generation_models if generation_models is not None else discover_generation_models()
    if judge in gens:
        raise JudgeModelCollisionError(judge, gens)
    if _family(judge) in {_family(g) for g in gens}:
        (logger or _logger).warning(
            "judge_same_family_as_generation judge_model=%s generation_models=%s",
            judge,
            gens,
        )
    return judge


def resolve_judge_panel(
    *,
    requested: tuple[str, ...] | None = None,
    generation_models: tuple[str, ...] | None = None,
    logger: logging.Logger | None = None,
) -> tuple[str, ...]:
    """Resolve the 3-model judge panel roster, enforcing the separation invariant per seat.

    Same collision/same-family rules as resolve_judge_model, applied to every
    seat individually — a panel is not exempt from self-evaluation just because
    two of its three seats are clean.

    Args:
        requested: Explicit panel roster; falls back to DEFAULT_PANEL_MODELS.
        generation_models: Generation models to check against; discovered if None.
        logger: Logger for same-family warnings; defaults to the module logger.
    Returns:
        The resolved panel roster, in the given/default order.
    Raises:
        JudgeModelCollisionError: If any seat equals a generation model.
    """
    panel = requested if requested is not None else DEFAULT_PANEL_MODELS
    gens = generation_models if generation_models is not None else discover_generation_models()
    gen_families = {_family(g) for g in gens}
    for seat in panel:
        if seat in gens:
            raise JudgeModelCollisionError(seat, gens)
        if _family(seat) in gen_families:
            (logger or _logger).warning(
                "judge_same_family_as_generation judge_model=%s generation_models=%s",
                seat,
                gens,
            )
    return panel


def resolve_judge_url() -> str:
    """Return the judge Ollama base URL (env JUDGE_OLLAMA_URL or default)."""
    return os.getenv(_ENV_JUDGE_URL, DEFAULT_JUDGE_URL)


def resolve_judge_timeout() -> float:
    """Return the judge request timeout in seconds (env JUDGE_TIMEOUT_SECONDS or default)."""
    return float(os.getenv(_ENV_JUDGE_TIMEOUT, str(DEFAULT_JUDGE_TIMEOUT_S)))


def resolve_judge_temperature() -> float:
    """Return the judge sampling temperature (env JUDGE_TEMPERATURE or default).

    Single source of truth for the binary judge's temperature — matchers.py uses
    this value in its Ollama request options, and run_config.py records the same
    value as provenance, so the two can never drift apart (EVAL-P18.2).
    """
    return float(os.getenv(_ENV_JUDGE_TEMPERATURE, str(DEFAULT_JUDGE_TEMPERATURE)))
