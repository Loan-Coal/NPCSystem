"""
Module: path_validator
Layer: config
Purpose: Async validators for the two LLM inference paths defined in wizard_config:
         path A (local Ollama) checks the daemon and model presence; path B (BYO API
         key) probes the configured endpoint with a lightweight HTTP call.
Dependencies: httpx (async HTTP), npc_engine.setup.ollama_manager, wizard_config.
Used by: SHIP-05b Unity wizard (drives validators via the /setup/validate API route
         or calls directly from the Python entry point).
Does NOT: import any engine, graph, API route, or scheduler layer.
Dependencies injected: OllamaManager api_base comes from config; httpx.AsyncClient
                       is module-level so tests can patch it.
"""
from __future__ import annotations

import enum

import httpx
from pydantic import BaseModel

from npc_engine.setup.ollama_manager import OllamaManager
from npc_engine.setup.wizard_config import WizardConfig

# Timeout (seconds) for the API health probe (path B).
_API_PROBE_TIMEOUT: float = 10.0

# HTTP 200 response code — API probe success.
_HTTP_OK: int = 200

# HTTP 401 response code — API key rejected.
_HTTP_UNAUTHORIZED: int = 401

# Relative path appended to api_url for the probe request (OpenAI-compatible).
_MODELS_PATH: str = "/models"


class ValidationStatus(str, enum.Enum):
    """Outcome of a path validation call."""

    OK = "ok"
    OLLAMA_NOT_RUNNING = "ollama_not_running"
    MODEL_NOT_PRESENT = "model_not_present"
    API_UNREACHABLE = "api_unreachable"
    API_AUTH_FAILED = "api_auth_failed"


class ValidationResult(BaseModel):
    """Result of an async path validation.

    Attributes:
        status: Outcome code. ``OK`` means the path is ready.
        message: Human-readable detail (empty on success).
    """

    status: ValidationStatus
    message: str = ""


async def validate_path_a(config: WizardConfig) -> ValidationResult:
    """Validate the local-Ollama inference path (path A).

    Checks:
    1. Ollama daemon is reachable.
    2. The configured ``local_model`` is present in the local model registry.

    Args:
        config: Wizard configuration. Uses ``config.local_model`` as the model tag
                to check; ``local_model=None`` is treated as MODEL_NOT_PRESENT.

    Returns:
        A ``ValidationResult`` with status ``OK`` if both checks pass.
    """
    manager = OllamaManager()

    if not await manager.is_running():
        return ValidationResult(
            status=ValidationStatus.OLLAMA_NOT_RUNNING,
            message="Ollama is not running. Start it or run the first-run setup.",
        )

    if not config.local_model:
        return ValidationResult(
            status=ValidationStatus.MODEL_NOT_PRESENT,
            message="No local model configured. Run the first-run setup to select one.",
        )

    if not await manager.is_model_available(config.local_model):
        return ValidationResult(
            status=ValidationStatus.MODEL_NOT_PRESENT,
            message=f"Model '{config.local_model}' is not pulled. Pull it with: ollama pull {config.local_model}",
        )

    return ValidationResult(status=ValidationStatus.OK)


async def validate_path_b(config: WizardConfig) -> ValidationResult:
    """Validate the BYO-API-key inference path (path B).

    Sends a ``GET {api_url}/models`` request with the player's API key as a
    Bearer token. A 200 response means the endpoint and key are valid.

    Args:
        config: Wizard configuration. Uses ``config.api_url`` and ``config.api_key``.
                Returns ``API_AUTH_FAILED`` immediately if ``api_key`` is None or empty.

    Returns:
        A ``ValidationResult`` with status ``OK`` on HTTP 200, ``API_AUTH_FAILED`` on
        HTTP 401 or missing key, and ``API_UNREACHABLE`` on any connection error or
        unexpected HTTP status.
    """
    if not config.api_key:
        return ValidationResult(
            status=ValidationStatus.API_AUTH_FAILED,
            message="No API key configured. Enter your API key in the wizard.",
        )
    return await _probe_api(config.api_url, config.api_key)


async def _probe_api(api_url: str, api_key: str) -> ValidationResult:
    """Send a GET /models probe and map the HTTP response to a ValidationResult."""
    probe_url = api_url.rstrip("/") + _MODELS_PATH
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=_API_PROBE_TIMEOUT) as client:
            resp = await client.get(probe_url, headers=headers)
    except httpx.HTTPError as exc:
        return ValidationResult(
            status=ValidationStatus.API_UNREACHABLE,
            message=f"Could not reach {api_url}: {exc}",
        )
    return _map_http_status(resp.status_code, api_url)


def _map_http_status(status_code: int, api_url: str) -> ValidationResult:
    """Map an HTTP status code from the API probe to a ValidationResult."""
    if status_code == _HTTP_OK:
        return ValidationResult(status=ValidationStatus.OK)
    if status_code == _HTTP_UNAUTHORIZED:
        return ValidationResult(
            status=ValidationStatus.API_AUTH_FAILED,
            message="API key rejected (HTTP 401). Check the key and try again.",
        )
    return ValidationResult(
        status=ValidationStatus.API_UNREACHABLE,
        message=f"Unexpected response from {api_url}: HTTP {status_code}",
    )
