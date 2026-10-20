"""
Module: _run_config_hashing
Layer: evals (eval harness — not part of src/)
Purpose: Content-hash helpers for run_config — golden_set_version, harness_version,
         case_set_version, and dialogue_prompt_hash. Extracted from run_config.py to
         keep that module within the 300-line limit (EVAL-P18.2).
         T16.3: harness_version covers only the instrument (matchers + prompts/eval/);
         case_set_version covers only the subject (evals/cases/).
Dependencies: hashlib, logging, pathlib (stdlib only).
Used by: evals/run_config.py
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

_GOLDEN_SET_HEX_CHARS = 12
_HARNESS_VERSION_HEX_CHARS = 12
_CASE_SET_VERSION_HEX_CHARS = 12
_DIALOGUE_PROMPT_HEX_CHARS = 12
_CASE_YAML_GLOB = "*.yaml"


class GoldenSetVersionError(ValueError):
    """Raised when golden_set_version cannot be computed due to an empty or missing cases dir."""

    def __init__(self, cases_dir: Path) -> None:
        """Initialise with the offending directory path."""
        super().__init__(
            f"Cannot compute golden_set_version: no case files found in {cases_dir!r}. "
            "Provide a directory containing at least one case file."
        )
        self.cases_dir = cases_dir


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


def resolve_case_set_version(cases_dir: Path) -> str:
    """Compute a content-stable version hash from the eval case files only.

    Hashes recursive .yaml case files under cases_dir in sorted path order.
    Changing, adding, or removing a case file changes this hash; changing the
    instrument (matchers.py or prompts/eval/) does not.

    T16.3: split from resolve_harness_version so a case edit does not orphan
    every prior run. ComparabilityKey keys on the instrument (harness_version),
    not on the subject (case_set_version) — case drift is already handled by
    compare.py's case-intersection refusal.

    Args:
        cases_dir: Root directory of eval cases; .yaml files discovered recursively.
    Returns:
        12-hex-char content hash string, or '' when cases_dir is empty or missing.
    """
    digest = hashlib.sha256()
    _feed_case_files(digest, cases_dir)
    return digest.hexdigest()[:_CASE_SET_VERSION_HEX_CHARS]


def resolve_harness_version(
    *,
    prompts_eval_dir: Path,
    matchers_path: Path,
) -> str:
    """Compute a content-stable harness version covering the eval instrument only.

    Hashes judge prompt .yaml files and matchers.py. Case files are excluded
    (T16.3): they are tracked separately by resolve_case_set_version so editing
    a case no longer orphans every prior run.

    Args:
        prompts_eval_dir: Directory containing judge criteria .yaml files.
        matchers_path: Path to evals/matchers.py (encodes judge sampling options).
    Returns:
        12-hex-char content hash string.
    Raises:
        FileNotFoundError: If matchers_path does not exist.
    """
    digest = hashlib.sha256()
    _feed_prompt_yamls(digest, prompts_eval_dir)
    digest.update(matchers_path.read_bytes())
    return digest.hexdigest()[:_HARNESS_VERSION_HEX_CHARS]


def hash_dialogue_prompts(prompts_dir: Path) -> str:
    """Hash all YAML runtime prompt files under prompts_dir recursively.

    Args:
        prompts_dir: Root of the runtime prompt tree (src/npc_engine/prompts/).
    Returns:
        12-hex-char content hash, or '' if the directory is missing or unreadable.
    """
    digest = hashlib.sha256()
    try:
        files = sorted(
            (f for f in prompts_dir.rglob(_CASE_YAML_GLOB) if f.is_file()),
            key=lambda f: str(f.relative_to(prompts_dir)),
        )
    except (FileNotFoundError, OSError) as exc:
        _logger.warning("dialogue_prompt_hash: cannot list %s: %s", prompts_dir, exc)
        return ""
    for f in files:
        digest.update(str(f.relative_to(prompts_dir)).encode())
        digest.update(f.read_bytes())
    return digest.hexdigest()[:_DIALOGUE_PROMPT_HEX_CHARS]
