"""
Package: api.routes.setup
Layer: api
Purpose: First-run setup routes: validate LLM paths (INTEG-01) and
         read/write the wizard config (INTEG-02). Auth-exempt, localhost-only.
Does NOT: perform graph reads/writes, call the LLM, or require an API key.
Dependencies injected: None (re-export only).
Public surface: setup_router
"""
from __future__ import annotations

from npc_engine.api.routes.setup.setup import router as setup_router

__all__ = ["setup_router"]
