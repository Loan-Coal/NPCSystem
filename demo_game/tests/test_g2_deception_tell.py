"""
Module: test_g2_deception_tell
Layer: demo_game (tests)
Purpose: Unit tests for the G2.5 deception tell in InspectPanelWidget._build_rows().
         Verifies that beliefs with is_deception=True are tagged "⚑ planted" and
         ordinary beliefs are not tagged.
Dependencies: demo_game.ui.inspect_panel, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _MockFont:
    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)

    def get_linesize(self) -> int:
        return 16

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 8
        surf.get_height.return_value = 16
        return surf


def _make_widget():
    from demo_game.ui.inspect_panel import InspectPanelWidget
    return InspectPanelWidget(_MockFont(), _MockFont())


_NORMAL_BELIEF = {
    "content": "The war is inevitable.",
    "confidence": 80,
    "is_deception": False,
}

_DECEPTION_BELIEF = {
    "content": "The grain stores are full.",
    "confidence": 70,
    "is_deception": True,
}


def _get_belief_rows(widget) -> list[str]:
    """Extract the belief row values from _build_rows()."""
    rows = widget._build_rows()
    # Row format: (kind, label, value); belief items have kind="item"
    # Collect all "item" row values that appear after the BELIEFS section header.
    result: list[str] = []
    in_beliefs = False
    for kind, label, value in rows:
        if kind == "section" and label == "BELIEFS":
            in_beliefs = True
            continue
        if kind == "section" and in_beliefs:
            break
        if in_beliefs and kind == "item":
            result.append(value)
    return result


class TestDeceptionTell:
    """Tests for the G2.5 deception tell in inspect_panel._build_rows()."""

    def test_normal_belief_has_no_deception_tag(self) -> None:
        """Ordinary beliefs (is_deception=False) must NOT show the planted tag."""
        widget = _make_widget()
        widget.set_data("mira_innkeeper", {"beliefs": [_NORMAL_BELIEF]})
        rows = _get_belief_rows(widget)
        assert rows, "Expected at least one belief row"
        assert "planted" not in rows[0]

    def test_deception_belief_has_planted_tag(self) -> None:
        """Beliefs with is_deception=True must show the ⚑ planted tag."""
        widget = _make_widget()
        widget.set_data("mira_innkeeper", {"beliefs": [_DECEPTION_BELIEF]})
        rows = _get_belief_rows(widget)
        assert rows, "Expected at least one belief row"
        assert "planted" in rows[0]

    def test_deception_does_not_alter_content(self) -> None:
        """The belief content text is preserved unchanged for deception beliefs."""
        widget = _make_widget()
        widget.set_data("mira_innkeeper", {"beliefs": [_DECEPTION_BELIEF]})
        rows = _get_belief_rows(widget)
        assert rows, "Expected at least one belief row"
        # Content should still appear in the row value.
        assert "grain" in rows[0]

    def test_mixed_beliefs_tagged_correctly(self) -> None:
        """Mixed list: only is_deception beliefs get the tag."""
        widget = _make_widget()
        widget.set_data(
            "mira_innkeeper",
            {"beliefs": [_NORMAL_BELIEF, _DECEPTION_BELIEF]},
        )
        rows = _get_belief_rows(widget)
        assert len(rows) == 2
        # First row (normal belief) — no tag.
        assert "planted" not in rows[0]
        # Second row (deception belief) — has tag.
        assert "planted" in rows[1]

    def test_missing_is_deception_field_treated_as_false(self) -> None:
        """When is_deception key is absent, belief is treated as ordinary."""
        belief_no_flag = {"content": "Something neutral.", "confidence": 50}
        widget = _make_widget()
        widget.set_data("mira_innkeeper", {"beliefs": [belief_no_flag]})
        rows = _get_belief_rows(widget)
        assert rows, "Expected at least one belief row"
        assert "planted" not in rows[0]
