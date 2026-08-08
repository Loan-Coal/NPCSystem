"""
Module: test_case_drafts
Layer: test (unit)
Purpose: Unit tests for evals/case_drafts.py draft generation.
         Uses a fixture HTTP client — no live graph required.
Dependencies: pytest, yaml, pathlib, case_drafts, runner
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# Ensure evals/ is importable as a flat package.
_EVALS_DIR = str(Path(__file__).parents[3] / "evals")
if _EVALS_DIR not in sys.path:
    sys.path.insert(0, _EVALS_DIR)

import case_drafts  # noqa: E402  (must follow sys.path setup)
from case_drafts import generate_drafts
from runner import _load_cases  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture HTTP client
# ---------------------------------------------------------------------------

# 3 NPCs, 5 grounded facts:
#   npc_a -> KNOWS_ABOUT: [fact_x, fact_y]   (2 edges)
#   npc_b -> BELIEVES:    [fact_z]             (1 edge)
#   npc_c -> HAS_GOAL:    [fact_w]             (1 edge)
#           HAS_MEMORY:   [fact_v]             (1 edge)
# Total = 5 drafts expected.

_FIXTURE_NPC_IDS: list[str] = ["npc_a", "npc_b", "npc_c"]

_FIXTURE_EDGES: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("KNOWS_ABOUT", "npc_a"): [{"dst_id": "fact_x"}, {"dst_id": "fact_y"}],
    ("BELIEVES", "npc_b"): [{"dst_id": "fact_z"}],
    ("HAS_GOAL", "npc_c"): [{"dst_id": "fact_w"}],
    ("HAS_MEMORY", "npc_c"): [{"dst_id": "fact_v"}],
}

_EXPECTED_DRAFT_COUNT: int = 5


class _FakeResponse:
    """Minimal fake HTTP response."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return {"data": self._data}


class _FixtureClient:
    """Fake HTTP client backed by _FIXTURE_EDGES.

    Parses the edge_type from the URL and the src_id from query params,
    returning the matching fixture rows (or an empty list).
    """

    def get(self, url: str, *, params: dict[str, Any] | None = None) -> _FakeResponse:
        """Return fixture edge rows for the given edge_type and src_id."""
        params = params or {}
        edge_type = url.rstrip("/").rsplit("/", 1)[-1]
        src_id = params.get("src_id", "")
        data = _FIXTURE_EDGES.get((edge_type, src_id), [])
        return _FakeResponse(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_draft_is_written_to_drafts_dir_not_cases_dir(tmp_path: Path) -> None:
    """Drafts land in <drafts_dir>, not in the parent cases directory."""
    cases_dir = tmp_path / "cases"
    drafts_dir = cases_dir / "_drafts"
    cases_dir.mkdir()

    result = generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        drafts_dir,
        base_url="http://fake",
    )

    assert len(result.written) == _EXPECTED_DRAFT_COUNT
    for path in result.written:
        assert path.parent == drafts_dir, f"{path.name} is not under drafts_dir"
        assert path.suffix == ".yaml"
    # cases_dir root must contain no YAML files
    assert list(cases_dir.glob("*.yaml")) == []


def test_five_drafts_from_fixture_graph(tmp_path: Path) -> None:
    """A fixture graph with 3 NPCs and 5 grounded facts yields exactly 5 drafts."""
    result = generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        tmp_path / "_drafts",
        base_url="http://fake",
    )
    assert len(result.written) == _EXPECTED_DRAFT_COUNT


def test_each_draft_has_grounded_by_comment(tmp_path: Path) -> None:
    """Each draft file names its grounding edge in a # grounded_by: comment."""
    drafts_dir = tmp_path / "_drafts"
    generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        drafts_dir,
        base_url="http://fake",
    )
    draft_files = sorted(drafts_dir.glob("draft_*.yaml"))
    assert len(draft_files) == _EXPECTED_DRAFT_COUNT
    for path in draft_files:
        text = path.read_text(encoding="utf-8")
        assert "# grounded_by:" in text, f"Missing # grounded_by: in {path.name}"


def test_load_cases_does_not_include_drafts(tmp_path: Path) -> None:
    """_load_cases on the cases_dir root does not see files in the _drafts subdir."""
    cases_dir = tmp_path / "cases"
    drafts_dir = cases_dir / "_drafts"
    cases_dir.mkdir()

    # Write one promoted case to the cases_dir root
    promoted = cases_dir / "case_pos_foo.yaml"
    promoted.write_text("case_id: case_pos_foo\nseed: {}\n", encoding="utf-8")

    generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        drafts_dir,
        base_url="http://fake",
    )

    loaded = _load_cases(cases_dir)
    assert len(loaded) == 1
    assert loaded[0]["case_id"] == "case_pos_foo"


def test_generate_drafts_is_idempotent(tmp_path: Path) -> None:
    """Running generate_drafts twice: second call skips all existing drafts."""
    drafts_dir = tmp_path / "_drafts"
    result_first = generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        drafts_dir,
        base_url="http://fake",
    )
    result_second = generate_drafts(
        _FixtureClient(),
        _FIXTURE_NPC_IDS,
        drafts_dir,
        base_url="http://fake",
    )

    assert len(result_first.written) == _EXPECTED_DRAFT_COUNT
    assert len(result_first.skipped) == 0
    assert len(result_second.written) == 0
    assert len(result_second.skipped) == _EXPECTED_DRAFT_COUNT
    names_first = {p.name for p in result_first.written}
    names_second = {p.name for p in result_second.skipped}
    assert names_first == names_second
