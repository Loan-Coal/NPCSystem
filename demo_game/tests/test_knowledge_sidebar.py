"""
Module: test_knowledge_sidebar
Layer: demo_game (tests)
Purpose: TDD unit tests for knowledge_sidebar_fetcher and KnowledgeSidebarWidget.
         No pygame display init required — uses mock font.
Dependencies: demo_game.knowledge_sidebar_fetcher, demo_game.ui.knowledge_sidebar,
              demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.client import EngineClientError
from demo_game.knowledge_sidebar_fetcher import fetch_npc_knowledge
from demo_game.ui.knowledge_sidebar import KnowledgeSidebarWidget


# ---------------------------------------------------------------------------
# Mock font: 8px per character, 16px line height.
# ---------------------------------------------------------------------------


class _MockFont:
    CHAR_W = 8
    LINE_H = 16

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * self.CHAR_W, self.LINE_H)

    def get_linesize(self) -> int:
        return self.LINE_H

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * self.CHAR_W
        surf.get_height.return_value = self.LINE_H
        return surf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EDGE_CLEAN = {
    "src_id": "captain_sorn",
    "dst_id": "northern_war_begins",
    "knowledge_state": "knows",
    "distorted_summary": None,
    "distortion_level": 0,
}

_EDGE_DISTORTED = {
    "src_id": "old_henryk",
    "dst_id": "northern_war_begins",
    "knowledge_state": "rumor",
    "distorted_summary": "Northmen sacked King's Pass, thousands dead",
    "distortion_level": 75,
}

_EVENT = {
    "id": "northern_war_begins",
    "name": "Northern War Begins",
    "summary": "War declared in the north; troops mobilised.",
    "description": "The northern tribes declared war on the kingdom.",
}


def _make_client(
    edges: list[dict] | None = None,
    event: dict | None = None,
    edges_raises: Exception | None = None,
    node_raises: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if edges_raises is not None:
        client.get_graph_edges.side_effect = edges_raises
    else:
        client.get_graph_edges.return_value = edges or []
    if node_raises is not None:
        client.get_node.side_effect = node_raises
    else:
        client.get_node.return_value = event
    return client


def _make_widget() -> KnowledgeSidebarWidget:
    return KnowledgeSidebarWidget(_MockFont(), _MockFont())


# ---------------------------------------------------------------------------
# fetch_npc_knowledge — fetcher tests
# ---------------------------------------------------------------------------


class TestFetchNpcKnowledge:
    def test_fetch_returns_paired_tuples(self) -> None:
        """Two edges each paired with the corresponding event node."""
        edge_a = {**_EDGE_CLEAN, "dst_id": "northern_war_begins"}
        edge_b = {**_EDGE_DISTORTED, "dst_id": "market_fire"}
        event_a = {**_EVENT, "id": "northern_war_begins"}
        event_b = {**_EVENT, "id": "market_fire", "name": "Market Fire"}

        client = MagicMock()
        client.get_graph_edges.return_value = [edge_a, edge_b]
        client.get_node.side_effect = [event_a, event_b]

        result = fetch_npc_knowledge(client, "old_henryk")

        assert len(result) == 2
        assert result[0] == (edge_a, event_a)
        assert result[1] == (edge_b, event_b)
        client.get_graph_edges.assert_called_once_with("KNOWS_ABOUT", src_id="old_henryk")
        assert client.get_node.call_count == 2

    def test_fetch_skips_missing_event(self, capsys: pytest.CaptureFixture) -> None:
        """Edge where get_node returns None is excluded from results."""
        edge = {**_EDGE_CLEAN, "dst_id": "ghost_event"}
        client = _make_client(edges=[edge], event=None)

        result = fetch_npc_knowledge(client, "captain_sorn")

        assert result == []

    def test_fetch_empty_edges_returns_empty_list(self) -> None:
        """NPC with no KNOWS_ABOUT edges → empty list, no node calls."""
        client = _make_client(edges=[])

        result = fetch_npc_knowledge(client, "mira_innkeeper")

        assert result == []
        client.get_node.assert_not_called()

    def test_fetch_propagates_engine_client_error(self) -> None:
        """EngineClientError from get_graph_edges propagates to caller."""
        client = _make_client(edges_raises=EngineClientError("server error"))

        with pytest.raises(EngineClientError):
            fetch_npc_knowledge(client, "old_henryk")

    def test_fetch_single_edge_produces_one_pair(self) -> None:
        """Single edge + event → one-element list."""
        client = _make_client(edges=[_EDGE_DISTORTED], event=_EVENT)

        result = fetch_npc_knowledge(client, "old_henryk")

        assert len(result) == 1
        edge, event = result[0]
        assert edge["distortion_level"] == 75
        assert event["name"] == "Northern War Begins"


# ---------------------------------------------------------------------------
# KnowledgeSidebarWidget — data state tests (no surface rendering)
# ---------------------------------------------------------------------------


class TestKnowledgeSidebarWidgetData:
    def test_set_data_stores_npc_name_and_pairs(self) -> None:
        """set_data sets the NPC display name and pair list."""
        widget = _make_widget()
        pairs = [(_EDGE_DISTORTED, _EVENT)]
        widget.set_data("Old Henryk", pairs)

        assert widget._npc_name == "Old Henryk"
        assert widget._pairs == pairs

    def test_clear_resets_to_empty(self) -> None:
        """clear() empties the pair list and name."""
        widget = _make_widget()
        widget.set_data("Old Henryk", [(_EDGE_DISTORTED, _EVENT)])
        widget.clear()

        assert widget._pairs == []
        assert widget._npc_name == ""

    def test_initial_state_empty(self) -> None:
        """Freshly constructed widget has no data."""
        widget = _make_widget()
        assert widget._pairs == []
        assert widget._npc_name == ""

    def test_scroll_reset_on_set_data(self) -> None:
        """set_data resets scroll to 0 so new data is shown from top."""
        widget = _make_widget()
        widget._scroll_px = 300
        widget.set_data("Mira", [(_EDGE_CLEAN, _EVENT)])
        assert widget._scroll_px == 0


# ---------------------------------------------------------------------------
# KnowledgeSidebarWidget — diff classification
# ---------------------------------------------------------------------------


class TestKnowledgeSidebarDiffClassification:
    def test_distorted_edge_classified_as_distorted(self) -> None:
        """distortion_level > 0 and distorted_summary != summary → 'distorted'."""
        widget = _make_widget()
        result = widget._classify_row(_EDGE_DISTORTED, _EVENT)
        assert result == "distorted"

    def test_clean_edge_classified_as_matching(self) -> None:
        """distortion_level == 0 → 'matching'."""
        widget = _make_widget()
        result = widget._classify_row(_EDGE_CLEAN, _EVENT)
        assert result == "matching"

    def test_missing_distorted_summary_classified_as_missing(self) -> None:
        """distorted_summary is None with distortion_level > 0 → 'missing'."""
        edge = {**_EDGE_DISTORTED, "distorted_summary": None}
        widget = _make_widget()
        result = widget._classify_row(edge, _EVENT)
        assert result == "missing"

    def test_knows_state_with_zero_distortion_classified_as_matching(self) -> None:
        """knowledge_state='knows' + distortion_level=0 → 'matching'."""
        edge = {**_EDGE_CLEAN, "knowledge_state": "knows", "distortion_level": 0}
        widget = _make_widget()
        result = widget._classify_row(edge, _EVENT)
        assert result == "matching"

    def test_rumor_state_with_matching_summary_classified_as_distorted(self) -> None:
        """knowledge_state='rumor' + distortion_level > 0 → 'distorted' even if
        distorted_summary happens to equal summary (edge props take precedence)."""
        edge = {
            "src_id": "mira_innkeeper",
            "dst_id": "northern_war_begins",
            "knowledge_state": "rumor",
            "distorted_summary": "War declared in the north; troops mobilised.",
            "distortion_level": 10,
        }
        widget = _make_widget()
        result = widget._classify_row(edge, _EVENT)
        assert result == "distorted"
