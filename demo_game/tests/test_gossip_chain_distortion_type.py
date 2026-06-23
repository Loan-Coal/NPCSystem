"""
Module: test_gossip_chain_distortion_type
Layer: demo_game (tests)
Purpose: TDD unit tests verifying that GossipChainWidget renders distortion_type
         badges ([EXAGGERATION], [OMISSION]) for each hop in the CHAIN tab.
Dependencies: demo_game.ui.gossip_chain, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pygame
import pytest

from demo_game.ui.boards.gossip_chain import GossipChainWidget


# ---------------------------------------------------------------------------
# Mock font that records render calls
# ---------------------------------------------------------------------------


class _TrackingFont:
    """Font mock that stores every text passed to render()."""

    def __init__(self) -> None:
        self.rendered_texts: list[str] = []

    def get_linesize(self) -> int:
        return 16

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        self.rendered_texts.append(text)
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 8
        surf.get_height.return_value = 16
        return surf


_EDGES_WITH_TYPES = [
    {
        "src_id": "captain_sorn",
        "distortion_level": 0.0,
        "distorted_summary": "The northern war has begun.",
        "distortion_type": None,
    },
    {
        "src_id": "mira_innkeeper",
        "distortion_level": 0.22,
        "distorted_summary": "There is trouble up north.",
        "distortion_type": "exaggeration",
    },
    {
        "src_id": "old_henryk",
        "distortion_level": 0.61,
        "distorted_summary": "Bandits or something happened.",
        "distortion_type": "omission",
    },
]


# ---------------------------------------------------------------------------
# draw does not raise
# ---------------------------------------------------------------------------


def test_draw_with_distortion_types_no_crash() -> None:
    """draw() with distortion_type fields present must not raise."""
    font = _TrackingFont()
    widget = GossipChainWidget(font, font)
    widget.set_chain(_EDGES_WITH_TYPES)
    surface = MagicMock()
    with patch("demo_game.ui.boards.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))


# ---------------------------------------------------------------------------
# distortion-type badge text is rendered
# ---------------------------------------------------------------------------


def test_exaggeration_badge_rendered() -> None:
    """draw() must call font.render with a string containing 'EXAGGERATION'."""
    font = _TrackingFont()
    widget = GossipChainWidget(font, font)
    widget.set_chain(_EDGES_WITH_TYPES)
    surface = MagicMock()
    with patch("demo_game.ui.boards.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))
    assert any("EXAGGERATION" in t for t in font.rendered_texts), (
        f"Expected 'EXAGGERATION' in rendered texts; got: {font.rendered_texts}"
    )


def test_omission_badge_rendered() -> None:
    """draw() must call font.render with a string containing 'OMISSION'."""
    font = _TrackingFont()
    widget = GossipChainWidget(font, font)
    widget.set_chain(_EDGES_WITH_TYPES)
    surface = MagicMock()
    with patch("demo_game.ui.boards.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))
    assert any("OMISSION" in t for t in font.rendered_texts), (
        f"Expected 'OMISSION' in rendered texts; got: {font.rendered_texts}"
    )


def test_none_distortion_type_no_badge() -> None:
    """draw() must NOT render a badge when distortion_type is None."""
    font = _TrackingFont()
    widget = GossipChainWidget(font, font)
    widget.set_chain(_EDGES_WITH_TYPES)
    surface = MagicMock()
    with patch("demo_game.ui.boards.gossip_chain.pygame.draw"):
        widget.draw(surface, pygame.Rect(0, 0, 400, 500))
    # captain_sorn has None distortion_type — no "[NONE]" badge should appear
    assert not any("[NONE]" in t for t in font.rendered_texts), (
        f"Unexpected [NONE] badge in rendered texts: {font.rendered_texts}"
    )
