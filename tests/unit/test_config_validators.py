"""
test_config_validators.py - Unit tests for Settings field validation functions.

Does NOT: instantiate Settings or read from environment variables.

Dependencies injected: None.
"""

from pathlib import Path

import pytest

from npc_engine.config_validators import (
    check_api_key_secret,
    check_api_v1_prefix,
    check_currency_transfer_limit,
    check_embedding_reconcile_interval,
    check_game_schema_path,
    check_idempotency_header_name,
    check_llm_config_path,
    check_positive_idempotency_value,
    check_redis_connect_timeout,
    check_redis_url,
    normalize_extension_sources,
)

_FAKE_ROOT = Path("/project/npc_engine")


# ── check_api_key_secret ──────────────────────────────────────────────────────


def test_check_api_key_secret_accepts_strong_key() -> None:
    """A sufficiently long, non-placeholder secret should be returned stripped."""

    assert check_api_key_secret("  supersecretkey1234  ") == "supersecretkey1234"


def test_check_api_key_secret_rejects_short_key() -> None:
    """A key shorter than 16 characters should raise ValueError."""

    with pytest.raises(ValueError, match="non-placeholder"):
        check_api_key_secret("tooshort")


def test_check_api_key_secret_rejects_placeholder_change_me() -> None:
    """The 'change-me' placeholder should be rejected regardless of length."""

    with pytest.raises(ValueError):
        check_api_key_secret("change-me")


def test_check_api_key_secret_rejects_empty_string() -> None:
    """An empty string should raise ValueError."""

    with pytest.raises(ValueError):
        check_api_key_secret("   ")


# ── check_api_v1_prefix ──────────────────────────────────────────────────────


def test_check_api_v1_prefix_accepts_valid_prefix() -> None:
    """A well-formed prefix like '/v1' should be returned as-is."""

    assert check_api_v1_prefix("/v1") == "/v1"


def test_check_api_v1_prefix_strips_trailing_slash() -> None:
    """A trailing slash should be removed from the prefix."""

    assert check_api_v1_prefix("/v1/") == "/v1"


def test_check_api_v1_prefix_rejects_missing_leading_slash() -> None:
    """A prefix without a leading '/' should raise ValueError."""

    with pytest.raises(ValueError, match="must start with"):
        check_api_v1_prefix("v1")


def test_check_api_v1_prefix_rejects_root_slash() -> None:
    """The bare '/' prefix should raise ValueError."""

    with pytest.raises(ValueError, match="cannot be"):
        check_api_v1_prefix("/")


# ── check_game_schema_path ───────────────────────────────────────────────────


def test_check_game_schema_path_rejects_empty() -> None:
    """An empty path should raise ValueError."""

    with pytest.raises(ValueError, match="cannot be empty"):
        check_game_schema_path("  ", _FAKE_ROOT)


def test_check_game_schema_path_returns_absolute_path_unchanged(tmp_path: Path) -> None:
    """An already-absolute path should be returned as a string without modification."""

    absolute = str(tmp_path / "game.yaml")
    result = check_game_schema_path(absolute, _FAKE_ROOT)
    assert result == absolute


def test_check_game_schema_path_resolves_relative_from_root() -> None:
    """A relative path should be resolved against the supplied project root."""

    result = check_game_schema_path("game_schema.yaml", _FAKE_ROOT)
    assert result == str((_FAKE_ROOT / "game_schema.yaml").resolve())


# ── normalize_extension_sources ──────────────────────────────────────────────


def test_normalize_extension_sources_strips_whitespace_and_joins() -> None:
    """Items with surrounding whitespace should be stripped and rejoined."""

    assert normalize_extension_sources("  a , b , c  ") == "a,b,c"


def test_normalize_extension_sources_drops_empty_items() -> None:
    """Empty items between commas should be dropped."""

    assert normalize_extension_sources("a,,b") == "a,b"


def test_normalize_extension_sources_empty_string_returns_empty() -> None:
    """An entirely empty input should return an empty string."""

    assert normalize_extension_sources("") == ""


# ── check_llm_config_path ────────────────────────────────────────────────────


def test_check_llm_config_path_rejects_empty() -> None:
    """An empty path should raise ValueError."""

    with pytest.raises(ValueError, match="cannot be empty"):
        check_llm_config_path("", _FAKE_ROOT)


def test_check_llm_config_path_resolves_relative() -> None:
    """A relative path should be resolved against the project root."""

    result = check_llm_config_path("config/llm.yaml", _FAKE_ROOT)
    assert result == str((_FAKE_ROOT / "config/llm.yaml").resolve())


# ── check_idempotency_header_name ────────────────────────────────────────────


def test_check_idempotency_header_name_accepts_valid() -> None:
    """A non-empty header name should be returned stripped."""

    assert check_idempotency_header_name("  X-Idempotency-Key  ") == "X-Idempotency-Key"


def test_check_idempotency_header_name_rejects_empty() -> None:
    """An empty header name should raise ValueError."""

    with pytest.raises(ValueError, match="cannot be empty"):
        check_idempotency_header_name("   ")


# ── check_redis_url ──────────────────────────────────────────────────────────


def test_check_redis_url_accepts_valid_url() -> None:
    """A non-empty URL should be returned stripped."""

    assert check_redis_url("  redis://localhost:6379/0  ") == "redis://localhost:6379/0"


def test_check_redis_url_rejects_empty() -> None:
    """An empty URL should raise ValueError."""

    with pytest.raises(ValueError, match="cannot be empty"):
        check_redis_url("  ")


# ── check_redis_connect_timeout ──────────────────────────────────────────────


def test_check_redis_connect_timeout_accepts_positive() -> None:
    """A positive timeout should be returned unchanged."""

    assert check_redis_connect_timeout(1.5) == 1.5


def test_check_redis_connect_timeout_rejects_zero() -> None:
    """Zero should raise ValueError."""

    with pytest.raises(ValueError, match="greater than 0"):
        check_redis_connect_timeout(0.0)


def test_check_redis_connect_timeout_rejects_negative() -> None:
    """A negative timeout should raise ValueError."""

    with pytest.raises(ValueError):
        check_redis_connect_timeout(-1.0)


# ── check_positive_idempotency_value ─────────────────────────────────────────


def test_check_positive_idempotency_value_accepts_positive() -> None:
    """A positive integer should be returned unchanged."""

    assert check_positive_idempotency_value(30) == 30


def test_check_positive_idempotency_value_rejects_zero() -> None:
    """Zero should raise ValueError."""

    with pytest.raises(ValueError, match="greater than 0"):
        check_positive_idempotency_value(0)


# ── check_embedding_reconcile_interval ───────────────────────────────────────


def test_check_embedding_reconcile_interval_accepts_positive() -> None:
    """A positive interval should be returned unchanged."""

    assert check_embedding_reconcile_interval(300) == 300


def test_check_embedding_reconcile_interval_rejects_zero() -> None:
    """Zero should raise ValueError."""

    with pytest.raises(ValueError, match="greater than 0"):
        check_embedding_reconcile_interval(0)


# ── check_currency_transfer_limit ────────────────────────────────────────────


def test_check_currency_transfer_limit_accepts_positive() -> None:
    """A positive limit should be returned unchanged."""

    assert check_currency_transfer_limit(1000) == 1000


def test_check_currency_transfer_limit_rejects_zero() -> None:
    """Zero should raise ValueError."""

    with pytest.raises(ValueError, match="greater than 0"):
        check_currency_transfer_limit(0)


def test_check_currency_transfer_limit_rejects_negative() -> None:
    """A negative limit should raise ValueError."""

    with pytest.raises(ValueError):
        check_currency_transfer_limit(-50)
