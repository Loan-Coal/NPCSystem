"""
Module: test_relation_ticker
Layer: demo_game (tests)
Purpose: Unit tests for RelationTicker — TTL polling, delta formatting, baseline
         management, and error swallowing. All pure, no live API.
Dependencies: demo_game.ui.relation_ticker, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from demo_game.client import EngineClientError
from demo_game.ui.relation_ticker import RelationSnapshot, RelationTicker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REL_DATA = {"trust": 50, "fear": 10, "affection": 20, "interaction_count": 3}
_REL_DATA_CHANGED = {"trust": 53, "fear": 9, "affection": 21, "interaction_count": 4}


def _make_client(rel_data: dict | None = None) -> MagicMock:
    """Return a mock EngineClient whose get_npc_relationship returns rel_data."""
    client = MagicMock()
    client.get_npc_relationship.return_value = rel_data
    return client


def _ticker(client: MagicMock | None = None) -> RelationTicker:
    """Build a RelationTicker with an injected mock client."""
    return RelationTicker(client or _make_client(_REL_DATA))


# ---------------------------------------------------------------------------
# test_tick_sets_baseline_on_first_fetch
# ---------------------------------------------------------------------------


def test_tick_sets_baseline_on_first_fetch() -> None:
    """No prior data: baseline must equal current after the first tick."""
    ticker = _ticker(_make_client(_REL_DATA))

    ticker.tick("mira_innkeeper")

    snap = RelationSnapshot(**_REL_DATA)
    assert ticker._baseline["mira_innkeeper"] == snap
    assert ticker._current["mira_innkeeper"] == snap


# ---------------------------------------------------------------------------
# test_tick_respects_ttl_skips_refetch
# ---------------------------------------------------------------------------


def test_tick_respects_ttl_skips_refetch() -> None:
    """Two ticks within TTL must call the client exactly once."""
    client = _make_client(_REL_DATA)
    ticker = RelationTicker(client)

    with patch("demo_game.ui.relation_ticker.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        ticker.tick("mira_innkeeper")
        # Second call still within TTL
        mock_time.monotonic.return_value = 2.0
        ticker.tick("mira_innkeeper")

    client.get_npc_relationship.assert_called_once()


# ---------------------------------------------------------------------------
# test_tick_refetches_after_ttl_expires
# ---------------------------------------------------------------------------


def test_tick_refetches_after_ttl_expires() -> None:
    """Tick called after TTL has expired must call the client a second time."""
    client = _make_client(_REL_DATA)
    ticker = RelationTicker(client)

    with patch("demo_game.ui.relation_ticker.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        ticker.tick("mira_innkeeper")
        # Advance past TTL (4.0 s)
        mock_time.monotonic.return_value = 5.0
        ticker.tick("mira_innkeeper")

    assert client.get_npc_relationship.call_count == 2


# ---------------------------------------------------------------------------
# test_get_delta_text_returns_none_before_any_tick
# ---------------------------------------------------------------------------


def test_get_delta_text_returns_none_before_any_tick() -> None:
    """get_delta_text returns None when no data has been fetched yet."""
    ticker = _ticker()
    assert ticker.get_delta_text("mira_innkeeper") is None


# ---------------------------------------------------------------------------
# test_get_delta_text_shows_zero_delta_on_same_values
# ---------------------------------------------------------------------------


def test_get_delta_text_shows_zero_delta_on_same_values() -> None:
    """When current == baseline all deltas are 0 and the string still renders."""
    ticker = _ticker(_make_client(_REL_DATA))
    ticker.tick("mira_innkeeper")

    text = ticker.get_delta_text("mira_innkeeper")

    assert text is not None
    assert "+0" in text or "0" in text


# ---------------------------------------------------------------------------
# test_get_delta_text_formats_positive_and_negative_deltas
# ---------------------------------------------------------------------------


def test_get_delta_text_formats_positive_and_negative_deltas() -> None:
    """trust +3 and fear -1 must both appear in the formatted delta text."""
    client = MagicMock()
    # First call returns baseline, second call returns changed values
    client.get_npc_relationship.side_effect = [_REL_DATA, _REL_DATA_CHANGED]
    ticker = RelationTicker(client)

    with patch("demo_game.ui.relation_ticker.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        ticker.tick("mira_innkeeper")
        # Advance past TTL so second tick fetches
        mock_time.monotonic.return_value = 5.0
        ticker.tick("mira_innkeeper")

    text = ticker.get_delta_text("mira_innkeeper")
    assert text is not None
    assert "+3" in text   # trust delta
    assert "-1" in text   # fear delta


# ---------------------------------------------------------------------------
# test_reset_baseline_promotes_current
# ---------------------------------------------------------------------------


def test_reset_baseline_promotes_current() -> None:
    """After reset_baseline, delta must be zero (current == new baseline)."""
    client = MagicMock()
    client.get_npc_relationship.side_effect = [_REL_DATA, _REL_DATA_CHANGED]
    ticker = RelationTicker(client)

    with patch("demo_game.ui.relation_ticker.time") as mock_time:
        mock_time.monotonic.return_value = 0.0
        ticker.tick("mira_innkeeper")
        mock_time.monotonic.return_value = 5.0
        ticker.tick("mira_innkeeper")

    # Deltas exist before reset
    text_before = ticker.get_delta_text("mira_innkeeper")
    assert "+3" in (text_before or "")

    ticker.reset_baseline("mira_innkeeper")

    text_after = ticker.get_delta_text("mira_innkeeper")
    # All deltas should now be zero
    assert text_after is not None
    assert "+3" not in text_after
    assert "-1" not in text_after


# ---------------------------------------------------------------------------
# test_tick_swallows_engine_client_error
# ---------------------------------------------------------------------------


def test_tick_swallows_engine_client_error() -> None:
    """EngineClientError raised by the client must not propagate from tick."""
    client = MagicMock()
    client.get_npc_relationship.side_effect = EngineClientError("API down")
    ticker = RelationTicker(client)

    # Must not raise
    ticker.tick("mira_innkeeper")
