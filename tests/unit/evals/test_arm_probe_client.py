"""
Module: tests.unit.evals.test_arm_probe_client
Layer: test (unit)
Purpose: Unit tests for evals/arm_probe_client.py — ProbeClient.observe/rehydrate/
         corpus_fingerprint, covering success, HTTP errors, malformed payloads, and
         timeout. All transport mocked; no live services.
Dependencies: pytest, unittest.mock, httpx; evals.arm_probe_client, evals.arm_probe_models
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from arm_probe_client import ProbeClient  # noqa: E402
from arm_probe_models import ArmObservation  # noqa: E402

_BASE_URL = "http://localhost:8000"
_API_KEY = "test-key"

_RECEIPT_BODY = {
    "context_receipt": {
        "item_keys": ["world", "beliefs", "rag:a"],
        "tier_spend": [
            {"tier": "tier0", "items": 3, "tokens": 93},
            {"tier": "tierA", "items": 8, "tokens": 687},
        ],
        "total_tokens": 780,
    },
    "retrieval_profile": "default",
}


def _client_with_mock() -> ProbeClient:
    """Return a ProbeClient whose internal httpx.Client is replaced by a MagicMock."""
    c = ProbeClient(base_url=_BASE_URL, api_key=_API_KEY)
    c._client = MagicMock()
    return c


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


# ---------------------------------------------------------------------------
# observe — success paths
# ---------------------------------------------------------------------------


def test_observe_returns_arm_observation_on_success() -> None:
    """Well-formed receipt produces an ArmObservation with the expected fields."""
    c = _client_with_mock()
    c._client.get.return_value = _ok(_RECEIPT_BODY)

    obs = c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm=None)

    assert isinstance(obs, ArmObservation)
    assert obs.npc_id == "captain_sorn"
    assert obs.query == "what news"
    assert obs.total_tokens == 780
    assert "rag:a" in obs.item_keys


def test_observe_passes_retrieval_profile_when_arm_is_named() -> None:
    """A named arm is forwarded as retrieval_profile in the request parameters."""
    c = _client_with_mock()
    body = dict(_RECEIPT_BODY, **{"retrieval_profile": "wide_rag"})
    c._client.get.return_value = _ok(body)

    c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm="wide_rag")

    _args, kwargs = c._client.get.call_args
    assert kwargs["params"]["retrieval_profile"] == "wide_rag"


def test_observe_omits_retrieval_profile_when_arm_is_none() -> None:
    """arm=None means the deployment default; retrieval_profile must NOT appear in params."""
    c = _client_with_mock()
    c._client.get.return_value = _ok(_RECEIPT_BODY)

    c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm=None)

    _args, kwargs = c._client.get.call_args
    assert "retrieval_profile" not in kwargs["params"]


# ---------------------------------------------------------------------------
# observe — failure paths
# ---------------------------------------------------------------------------


def test_observe_raises_value_error_when_receipt_missing() -> None:
    """A cached assembly returns no receipt; scoring it would compare nothing to nothing."""
    c = _client_with_mock()
    c._client.get.return_value = _ok({"retrieval_profile": "default"})

    with pytest.raises(ValueError, match="no context receipt"):
        c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm=None)


def test_observe_raises_value_error_when_receipt_is_empty_dict() -> None:
    """An empty dict is falsy — treated the same as a missing receipt."""
    c = _client_with_mock()
    c._client.get.return_value = _ok({"context_receipt": {}, "retrieval_profile": "default"})

    with pytest.raises(ValueError, match="no context receipt"):
        c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm=None)


def test_observe_propagates_http_status_error() -> None:
    """Non-2xx responses propagate as httpx.HTTPStatusError."""
    c = _client_with_mock()
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request", request=MagicMock(), response=MagicMock()
    )
    c._client.get.return_value = resp

    with pytest.raises(httpx.HTTPStatusError):
        c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm="bad_arm")


def test_observe_propagates_timeout() -> None:
    """A transport timeout surfaces as httpx.TimeoutException."""
    c = _client_with_mock()
    c._client.get.side_effect = httpx.TimeoutException("timed out")

    with pytest.raises(httpx.TimeoutException):
        c.observe(npc_id="captain_sorn", query="what news", player_id="p1", arm=None)


# ---------------------------------------------------------------------------
# rehydrate and corpus_fingerprint
# ---------------------------------------------------------------------------


def test_rehydrate_returns_corpus_report_dict() -> None:
    """rehydrate unwraps the data envelope and returns the CorpusReport fields."""
    c = _client_with_mock()
    c._client.post.return_value = _ok({"data": {"nodes_read": 51, "upserted": 51}})

    result = c.rehydrate()

    assert result["nodes_read"] == 51
    assert result["upserted"] == 51


def test_rehydrate_propagates_http_error() -> None:
    """A non-2xx rehydrate response propagates as httpx.HTTPStatusError."""
    c = _client_with_mock()
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=MagicMock()
    )
    c._client.post.return_value = resp

    with pytest.raises(httpx.HTTPStatusError):
        c.rehydrate()


def test_corpus_fingerprint_returns_identity_dict() -> None:
    """corpus_fingerprint unwraps the data envelope and returns the store identity."""
    c = _client_with_mock()
    c._client.get.return_value = _ok({"data": {"corpus_sha": "abc123", "item_count": 51}})

    result = c.corpus_fingerprint()

    assert result["corpus_sha"] == "abc123"


def test_corpus_fingerprint_passes_include_sha_true() -> None:
    """include_sha=true is required to get the sha without touching the store."""
    c = _client_with_mock()
    c._client.get.return_value = _ok({"data": {}})

    c.corpus_fingerprint()

    _args, kwargs = c._client.get.call_args
    assert kwargs["params"]["include_sha"] == "true"


# ---------------------------------------------------------------------------
# lifecycle — close and context manager
# ---------------------------------------------------------------------------


def test_close_delegates_to_httpx_client() -> None:
    """close() releases the underlying connection pool."""
    c = _client_with_mock()
    c.close()
    c._client.close.assert_called_once()


def test_context_manager_closes_on_exit() -> None:
    """__exit__ releases the connection pool, even without an exception."""
    c = ProbeClient(base_url=_BASE_URL, api_key=_API_KEY)
    c._client = MagicMock()
    c.__enter__()
    c.__exit__(None, None, None)
    c._client.close.assert_called_once()
