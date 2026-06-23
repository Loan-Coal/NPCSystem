"""Tests for npc_engine.setup.neo4j_manager — Neo4j lifecycle management."""
from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from npc_engine.setup.neo4j_manager import (
    NEO4J_BOLT_URL,
    NEO4J_HTTP_URL,
    Neo4jManager,
    Neo4jNotInstalledError,
    Neo4jStartupError,
)


class TestNeo4jManagerIsRunning:
    def test_returns_true_on_200(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(Neo4jManager().is_running())

        assert result is True

    def test_returns_false_on_non_200(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(Neo4jManager().is_running())

        assert result is False

    def test_returns_false_on_connect_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(Neo4jManager().is_running())

        assert result is False


class TestNeo4jManagerIsInstalled:
    def test_returns_true_when_on_path(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/neo4j"):
            assert Neo4jManager().is_installed() is True

    def test_returns_false_when_not_on_path(self) -> None:
        with patch("shutil.which", return_value=None):
            assert Neo4jManager().is_installed() is False


class TestNeo4jManagerLaunch:
    def test_returns_popen_when_installed(self) -> None:
        fake_proc = MagicMock(spec=subprocess.Popen)
        with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
            proc = Neo4jManager().launch()
        assert proc is fake_proc
        mock_popen.assert_called_once()

    def test_raises_not_installed_when_binary_not_found(self) -> None:
        with patch("subprocess.Popen", side_effect=FileNotFoundError("neo4j")):
            with pytest.raises(Neo4jNotInstalledError):
                Neo4jManager().launch()


class TestNeo4jManagerUrls:
    def test_get_bolt_url_returns_default(self) -> None:
        assert Neo4jManager().get_bolt_url() == NEO4J_BOLT_URL

    def test_custom_urls_in_constructor(self) -> None:
        mgr = Neo4jManager(
            http_url="http://myhost:7474", bolt_url="bolt://myhost:7687"
        )
        assert mgr.get_bolt_url() == "bolt://myhost:7687"

    def test_default_constants_are_localhost(self) -> None:
        assert "localhost" in NEO4J_HTTP_URL
        assert "localhost" in NEO4J_BOLT_URL

    def test_neo4j_startup_error_is_distinct_from_not_installed(self) -> None:
        err = Neo4jStartupError("timeout")
        assert isinstance(err, Exception)
        assert not isinstance(err, Neo4jNotInstalledError)
