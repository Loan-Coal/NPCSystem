"""
config_validators.py — Pure validation functions for Settings field values.
Layer: unknown
Purpose: (auto-detected — review)

Does NOT: read from environment, instantiate Settings, or perform I/O.

Dependencies injected: None.
"""

from __future__ import annotations

from pathlib import Path


# The secret shipped in the example/dev .env. Allowed in dev so the local stack
# and test suite work out of the box, but it is public (committed), so it must be
# rejected outside dev (L1-04) the same way the weak Neo4j password is.
_KNOWN_DEV_API_KEY_SECRET = "local_dev_secret_change_this_2026"


def check_api_key_secret(value: str, env: str = "dev") -> str:
    """Reject weak, placeholder, or shipped-dev API secrets.

    Args:
        value: str — raw API_KEY_SECRET value from the environment.
        env: Current ENV value ("dev", "staging", or "prod").

    Returns:
        Stripped, validated secret string.

    Raises:
        ValueError: if the value is shorter than 16 chars, matches a known
            placeholder, or is the shipped dev secret while env is not "dev".
    """
    stripped = value.strip()
    blocked = {"change-me", "replace_with_strong_secret", ""}
    if len(stripped) < 16 or stripped in blocked:
        raise ValueError("API_KEY_SECRET must be a non-placeholder secret with length >= 16")
    if stripped == _KNOWN_DEV_API_KEY_SECRET and env != "dev":
        raise ValueError(
            "API_KEY_SECRET must not use the shipped dev secret in staging/prod. "
            "Set a strong, unique secret via the API_KEY_SECRET environment variable."
        )
    return stripped


def check_idempotency_enforced(enabled: bool, env: str) -> bool:
    """Require IDEMPOTENCY_ENFORCE_HEADER outside dev (DEC-111); off = replay-able mutations.

    Args:
        enabled: Raw IDEMPOTENCY_ENFORCE_HEADER value.
        env: Current ENV value ("dev", "staging", or "prod").
    Returns:
        The flag unchanged when valid.
    Raises:
        ValueError: when enabled is False and env is not "dev".
    """
    if not enabled and env != "dev":
        raise ValueError(
            "IDEMPOTENCY_ENFORCE_HEADER must be true in staging/prod; mutating "
            "endpoints are replay-able otherwise. Set IDEMPOTENCY_ENFORCE_HEADER=true."
        )
    return enabled


def check_api_v1_prefix(value: str) -> str:
    """Ensure the API prefix is a stable, non-root absolute path segment.

    Args:
        value: str — raw API_V1_PREFIX value from the environment.

    Returns:
        Stripped prefix with trailing slash removed.

    Raises:
        ValueError: if the prefix does not start with '/' or equals '/'.
    """
    prefix = value.strip()
    if not prefix.startswith("/"):
        raise ValueError("API_V1_PREFIX must start with '/'")
    if prefix == "/":
        raise ValueError("API_V1_PREFIX cannot be '/'")
    return prefix.rstrip("/")


def check_game_schema_path(value: str, project_root: Path) -> str:
    """Reject empty schema paths and resolve relative paths from the project root.

    Args:
        value: str — raw GAME_SCHEMA_PATH value from the environment.
        project_root: Path — absolute path to the npc_engine package directory.

    Returns:
        Resolved absolute path string.

    Raises:
        ValueError: if the path is empty after stripping whitespace.
    """
    path = value.strip()
    if not path:
        raise ValueError("GAME_SCHEMA_PATH cannot be empty")
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((project_root / candidate).resolve())


def normalize_extension_sources(value: str) -> str:
    """Normalize comma-delimited extension source paths for deterministic parsing.

    Args:
        value: str — raw TYPE_REGISTRY_EXTENSION_SOURCES value from the environment.

    Returns:
        Comma-joined string of stripped, non-empty items; empty string if no valid items.
    """
    items = [item.strip() for item in value.split(",") if item.strip()]
    return ",".join(items)


def check_llm_config_path(value: str, project_root: Path) -> str:
    """Reject empty LLM config paths and resolve relative paths from the project root.

    Args:
        value: str — raw LLM_CONFIG_PATH value from the environment.
        project_root: Path — absolute path to the npc_engine package directory.

    Returns:
        Resolved absolute path string.

    Raises:
        ValueError: if the path is empty after stripping whitespace.
    """
    path = value.strip()
    if not path:
        raise ValueError("LLM_CONFIG_PATH cannot be empty")
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((project_root / candidate).resolve())


def check_idempotency_header_name(value: str) -> str:
    """Ensure the idempotency header setting is a non-empty string.

    Args:
        value: str — raw IDEMPOTENCY_HEADER_NAME value from the environment.

    Returns:
        Stripped header name string.

    Raises:
        ValueError: if the value is empty after stripping whitespace.
    """
    header_name = value.strip()
    if not header_name:
        raise ValueError("IDEMPOTENCY_HEADER_NAME cannot be empty")
    return header_name


def check_redis_url(value: str) -> str:
    """Ensure the Redis URL is non-empty.

    Args:
        value: str — raw REDIS_URL value from the environment.

    Returns:
        Stripped Redis URL string.

    Raises:
        ValueError: if the value is empty after stripping whitespace.
    """
    url = value.strip()
    if not url:
        raise ValueError("REDIS_URL cannot be empty")
    return url


def check_redis_connect_timeout(value: float) -> float:
    """Ensure the Redis connection timeout is a positive number.

    Args:
        value: float — raw REDIS_CONNECT_TIMEOUT_SECONDS value from the environment.

    Returns:
        Validated timeout in seconds.

    Raises:
        ValueError: if value is not greater than zero.
    """
    if value <= 0:
        raise ValueError("REDIS_CONNECT_TIMEOUT_SECONDS must be greater than 0")
    return value


def check_positive_idempotency_value(value: int) -> int:
    """Ensure idempotency timing values are positive integers.

    Args:
        value: int — raw timing value (pending timeout, retention hours, or cleanup interval).

    Returns:
        Validated positive integer.

    Raises:
        ValueError: if value is not greater than zero.
    """
    if value <= 0:
        raise ValueError("idempotency timing values must be greater than 0")
    return value


def check_embedding_reconcile_interval(value: int) -> int:
    """Ensure the embedding reconciler interval is a positive number of seconds.

    Args:
        value: int — raw EMBEDDING_RECONCILE_INTERVAL_SECONDS value from the environment.

    Returns:
        Validated interval in seconds.

    Raises:
        ValueError: if value is not greater than zero.
    """
    if value <= 0:
        raise ValueError("EMBEDDING_RECONCILE_INTERVAL_SECONDS must be greater than 0")
    return value


def check_currency_transfer_limit(value: int) -> int:
    """Ensure configurable currency limits are positive integers.

    Args:
        value: int — raw currency limit value (max per transaction or per session).

    Returns:
        Validated positive integer.

    Raises:
        ValueError: if value is not greater than zero.
    """
    if value <= 0:
        raise ValueError("currency limits must be greater than 0")
    return value


def check_package_data_path(value: str, project_root: Path) -> str:
    """Resolve a package-internal data file path against the package root.

    Args:
        value: str — raw path value, relative or absolute.
        project_root: Path — absolute path to the npc_engine package directory.

    Returns:
        Resolved absolute path string.

    Raises:
        ValueError: if the path is empty after stripping whitespace.
    """
    path = value.strip()
    if not path:
        raise ValueError("data path cannot be empty")
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((project_root / candidate).resolve())


_NEO4J_WEAK_PASSWORD = "password"


def check_neo4j_password(value: str, env: str) -> str:
    """Reject the default weak NEO4J_PASSWORD when running outside dev.

    In dev the literal "password" is allowed so the shared suite and local
    Docker Compose setup work without config changes. In staging/prod the
    literal is rejected to prevent accidental DB compromise.

    Args:
        value: Raw NEO4J_PASSWORD value from the environment.
        env: Current ENV value ("dev", "staging", or "prod").

    Returns:
        The password string unchanged when valid.

    Raises:
        ValueError: when value equals the weak literal and env is not "dev".
    """
    if value == _NEO4J_WEAK_PASSWORD and env != "dev":
        raise ValueError(
            "NEO4J_PASSWORD must not use the default 'password' value in staging/prod. "
            "Set a strong, unique password via the NEO4J_PASSWORD environment variable."
        )
    return value
