"""
Module: test_gossip_chain
Layer: demo_game (tests)
Purpose: TDD unit tests for GossipChainWidget — empty state, data load, draw smoke.
         No pygame display init required.
Dependencies: demo_game.ui.gossip_chain, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from demo_game.ui.gossip_chain import GossipChainWidget


# ---------------------------------------------------------------------------
# Mock font
# ---------------------------------------------------------------------------


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


_SAMPLE_EDGES = [
    {
        "src_id": "captain_sorn",
        "distortion_level": 0.0,
        "distorted_summary": "The northern war has begun.",
    },
    {
        "src_id": "mira_innkeeper",
        "distortion_level": 0.22,
        "distorted_summary": "There is trouble up north.",
    },
    {
        "src_id": "old_henryk",
        "distortion_level": 0.61,
        "distorted_summary": "Bandits or something happened.",
    },
]


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_gossip_chain_starts_empty() -> None:
    """Widget starts with no chain data."""
    widget = GossipChainWidget(_MockFont(), _MockFont())
    assert widget._edges == []


# ---------------------------------------------------------------------------
# set_chain
# ---------------------------------------------------------------------------


def test_gossip_chain_set_chain_stores_edges() -> None:
    """set_chain() stores the provided edge list."""
    widget = GossipChainWidget(_MockFont(), _MockFont())
    widget.set_chain(_SAMPLE_EDGES)
    assert len(widget._edges) == 3


def test_gossip_chain_set_chain_sorts_by_distortion() -> None:
    """set_chain() sorts edges by distortion_level ascending."""
    shuffled = [_SAMPLE_EDGES[2], _SAMPLE_EDGES[0], _SAMPLE_EDGES[1]]
    widget = GossipChainWidget(_MockFont(), _MockFont())
    widget.set_chain(shuffled)
    levels = [e["distortion_level"] for e in widget._edges]
    assert levels == sorted(levels)


def test_gossip_chain_set_chain_empty_clears() -> None:
    """set_chain([]) clears previous data."""
    widget = GossipChainWidget(_MockFont(), _MockFont())
    widget.set_chain(_SAMPLE_EDGES)
    widget.set_chain([])
    assert widget._edges == []


# ---------------------------------------------------------------------------
# draw — smoke tests (no crash)
# ---------------------------------------------------------------------------


def test_gossip_chain_draw_empty_no_crash() -> None:
    """draw() with no data must not raise."""
    widget = GossipChainWidget(_MockFont(), _MockFont())
    surface = MagicMock()
    with patch("demo_game.ui.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))


def test_gossip_chain_draw_with_data_no_crash() -> None:
    """draw() with chain data must not raise."""
    widget = GossipChainWidget(_MockFont(), _MockFont())
    widget.set_chain(_SAMPLE_EDGES)
    surface = MagicMock()
    with patch("demo_game.ui.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))
