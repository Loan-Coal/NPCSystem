"""
Package: demo_game.tests
Layer: demo_game (test fixtures)
Purpose: Shared pytest fixtures for demo_game unit tests.
Dependencies: unittest.mock
Used by: demo_game.tests.test_client
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


@pytest.fixture
def mock_http() -> MagicMock:
    """Mock httpx.Client for injection into EngineClient."""
    return MagicMock()


@pytest.fixture
def make_response():
    """Factory fixture returning mock httpx.Response objects."""
    return _make_response
