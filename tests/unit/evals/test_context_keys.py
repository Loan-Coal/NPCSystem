"""
Module: test_context_keys
Layer: test (unit)
Purpose: Verify node_id_from_key correctly strips prefix from context item keys.
Dependencies: pytest, evals.context_keys
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from evals.context_keys import node_id_from_key


# ---------------------------------------------------------------------------
# Prefix-stripping tests
# ---------------------------------------------------------------------------


def test_rag_prefix_strips_to_node_id() -> None:
    """rag:northern_war_begins → northern_war_begins."""
    assert node_id_from_key("rag:northern_war_begins") == "northern_war_begins"


def test_character_prefix_strips_to_node_id() -> None:
    """character:mira_innkeeper → mira_innkeeper."""
    assert node_id_from_key("character:mira_innkeeper") == "mira_innkeeper"


def test_location_prefix_strips_to_node_id() -> None:
    """location:tavern → tavern."""
    assert node_id_from_key("location:tavern") == "tavern"


def test_bare_key_round_trips() -> None:
    """A key with no colon is returned unchanged."""
    assert node_id_from_key("northern_war_begins") == "northern_war_begins"


def test_multiple_colons_uses_last_segment() -> None:
    """Only the last colon segment is taken when multiple colons exist."""
    assert node_id_from_key("a:b:c") == "c"
