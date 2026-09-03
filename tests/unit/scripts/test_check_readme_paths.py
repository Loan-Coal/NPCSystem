"""
test_check_readme_paths.py - Counterfactual and live check for the README link gate (R4.6).

Does NOT: follow external URLs or start a server.

Dependencies injected: tmp_path for the counterfactual document.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_readme_paths import main, missing_paths, repo_relative_links

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_readme_has_no_dead_links() -> None:
    """Every repo-relative link in README.md resolves.

    Before R4.6 seven did not: the "Key files" table pointed at an `npc_engine/` source
    layout the repo replaced with `src/npc_engine/`, plus `tests/scenarios/` (it is
    `e2e/scenarios/`) and a `proposals/` directory that no longer exists.
    """
    assert missing_paths(REPO_ROOT / "README.md") == []


def test_a_dead_link_is_reported(tmp_path: Path) -> None:
    """The counterfactual: the gate can actually fail."""
    doc = tmp_path / "README.md"
    doc.write_text("[gone](does/not/exist.md) and [here](README.md)\n", encoding="utf-8")

    assert missing_paths(doc) == ["does/not/exist.md"]


def test_a_dead_link_makes_main_exit_nonzero(tmp_path: Path) -> None:
    """And the failure reaches the process exit code, not just the printed report."""
    doc = tmp_path / "README.md"
    doc.write_text("[gone](does/not/exist.md)\n", encoding="utf-8")

    assert main([str(doc)]) == 1


def test_external_and_anchor_links_are_ignored() -> None:
    """A URL or a bare anchor is not a path, so the gate must not try to resolve one."""
    text = "[a](https://example.com) [b](#section) [c](mailto:x@y.z) [d](README.md#top)"

    assert repo_relative_links(text) == ["README.md"]
