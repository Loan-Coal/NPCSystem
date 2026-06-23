"""
Module: api.routes.setup.setup
Layer: api
Purpose: Auth-exempt, localhost-only setup routes for the first-run wizard.
         POST /setup/validate — validate LLM path A or B (INTEG-01).
         GET  /setup/config   — read persisted wizard config (INTEG-02).
         POST /setup/config   — write wizard config (INTEG-02).
Dependencies: npc_engine.setup.path_validator, npc_engine.setup.wizard_config.
Used by: api.router_registry (registered under /setup prefix); SHIP-05b Unity wizard.
Does NOT: require auth (auth.middleware exempts /setup/* via DEC-131); perform
          graph reads/writes; call LLM.
Dependencies injected: config_dir path injected via query param (test overrides);
                       validate_path_a / validate_path_b imported directly.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query
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
async def get_config(
    config_dir: Annotated[str | None, Query(include_in_schema=False)] = None,
) -> Any:
    """Return the persisted wizard config, or 404 if not yet written.

    Returns:
        OkEnvelope wrapping a ``WizardConfig`` if the file exists.

    Raises:
        HTTPException 404: When the wizard config file has not been written yet.
    """
    import pathlib

    dir_path = pathlib.Path(config_dir) if config_dir else None
    cfg: WizardConfig | None
    if dir_path is not None:
        cfg = load_wizard_config(config_dir=dir_path)
    else:
        cfg = load_wizard_config()

    if cfg is None:
        raise HTTPException(status_code=_HTTP_NOT_FOUND, detail="Wizard config not found.")
    return ok_response(cfg.model_dump())


@router.post("/config", response_model=OkEnvelope[WizardConfig])
async def post_config(
    body: Annotated[WizardConfig, Body()],
    config_dir: Annotated[str | None, Query(include_in_schema=False)] = None,
) -> Any:
    """Persist the wizard config and echo it back.

    Args:
        body: The wizard configuration to store.
        config_dir: Override config directory (test injection only, hidden from schema).

    Returns:
        OkEnvelope wrapping the saved ``WizardConfig``.
    """
    import pathlib

    dir_path = pathlib.Path(config_dir) if config_dir else None
    if dir_path is not None:
        save_wizard_config(body, config_dir=dir_path)
    else:
        save_wizard_config(body)
    return ok_response(body.model_dump())
