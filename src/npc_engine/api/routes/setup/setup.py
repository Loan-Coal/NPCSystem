"""
Module: api.routes.setup.setup
Layer: api
Purpose: Dev-only auth-exempt setup routes for the first-run wizard.
         POST /setup/validate — validate LLM path A or B (INTEG-01).
         GET  /setup/config   — read persisted wizard config (INTEG-02).
         POST /setup/config   — write wizard config (INTEG-02).
Dependencies: npc_engine.setup.path_validator, npc_engine.setup.wizard_config.
Used by: api.router_registry (registered under /setup prefix); SHIP-05b Unity wizard.
Does NOT: require auth when ENV == "dev" (auth.middleware exempts /setup/* in dev
          only; DEC-131 superseded by ISSUE-227); perform graph reads/writes;
          call LLM; accept a caller-supplied config directory.
Dependencies injected: validate_path_a / validate_path_b imported directly.
                       The config directory is the wizard_config process default —
                       tests patch load_wizard_config / save_wizard_config.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict

from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.setup.path_validator import (
    ValidationResult,
    validate_path_a,
    validate_path_b,
)
from npc_engine.setup.wizard_config import (
    WizardConfig,
    load_wizard_config,
    save_wizard_config,
)

router = APIRouter(prefix="/setup", tags=["setup"])

# HTTP 404 status used when no wizard config exists on disk.
_HTTP_NOT_FOUND: int = 404


class ValidateRequest(BaseModel):
    """Request body for POST /setup/validate.

    Attributes:
        path: Which LLM path to validate — ``"a"`` (local Ollama) or ``"b"`` (BYO API key).
        config: Full wizard config used to drive the validator.
    """

    path: Literal["a", "b"]
    config: WizardConfig

    model_config = ConfigDict(frozen=True)


@router.post("/validate", response_model=OkEnvelope[ValidationResult])
async def validate_path(body: ValidateRequest) -> Any:
    """Validate LLM inference path A or B and return a typed result.

    Path A checks that Ollama is running and the configured model is pulled.
    Path B probes the configured API endpoint with the player's key (SSRF-guarded).

    Returns:
        OkEnvelope wrapping a ``ValidationResult`` with ``status`` and ``message``.
    """
    if body.path == "a":
        result: ValidationResult = await validate_path_a(body.config)
    else:
        result = await validate_path_b(body.config)
    return ok_response(result.model_dump())


@router.get("/config", response_model=OkEnvelope[WizardConfig])
async def get_config() -> Any:
    """Return the persisted wizard config, or 404 if not yet written.

    The config directory is not caller-controllable: it is the process default from
    ``wizard_config``. A hidden ``config_dir`` query param existed here for test
    injection and was removed with ISSUE-227 — tests inject by patching
    ``load_wizard_config``/``save_wizard_config``, which needs no request surface.

    Returns:
        OkEnvelope wrapping a ``WizardConfig`` if the file exists.

    Raises:
        HTTPException 404: When the wizard config file has not been written yet.
    """
    cfg: WizardConfig | None = load_wizard_config()
    if cfg is None:
        raise HTTPException(status_code=_HTTP_NOT_FOUND, detail="Wizard config not found.")
    return ok_response(cfg.model_dump())


@router.post("/config", response_model=OkEnvelope[WizardConfig])
async def post_config(body: Annotated[WizardConfig, Body()]) -> Any:
    """Persist the wizard config and echo it back.

    The destination directory is not caller-controllable. A hidden ``config_dir``
    query param previously let any caller choose the write target, which
    ``save_wizard_config`` would ``mkdir -p`` and write to as root; it was removed
    with ISSUE-227.

    Args:
        body: The wizard configuration to store.

    Returns:
        OkEnvelope wrapping the saved ``WizardConfig``.
    """
    save_wizard_config(body)
    return ok_response(body.model_dump())
