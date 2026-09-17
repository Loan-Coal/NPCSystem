"""
Module: test_mypy_evals_ratchet
Layer: test (unit)
Purpose: Pin that the evals/ mypy ratchet keeps its own incremental cache, apart from `make type`.
Dependencies: pathlib; scripts/mypy_evals_ratchet.py
Used by: pytest (make test / make check)

Why this exists: `make type` (mypy src/) and `make type-evals` (mypy evals/) shared
.mypy_cache and invalidated each other's entries on every `make check`: a warm
`mypy evals/` took 4.5 s alone and 14.5 s right after `mypy src/`, and the reverse cost
the same (DEC-283). Static check of the command only; runs no mypy.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from mypy_evals_ratchet import MYPY_COMMAND  # noqa: E402

_DEFAULT_CACHE_DIR = ".mypy_cache"


def test_evals_ratchet_uses_a_cache_dir_of_its_own() -> None:
    """The evals run must not write into the cache `mypy src/` reads."""
    assert "--cache-dir" in MYPY_COMMAND
    cache_dir = MYPY_COMMAND[MYPY_COMMAND.index("--cache-dir") + 1]
    assert Path(cache_dir) != Path(_DEFAULT_CACHE_DIR)


def test_evals_ratchet_still_targets_evals() -> None:
    """Guard the guard: a cache flag must not displace the target directory."""
    assert MYPY_COMMAND[-1] == "evals/"
