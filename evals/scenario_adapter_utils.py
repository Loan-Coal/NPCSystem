"""
Module: scenario_adapter_utils
Layer: evals (eval harness — not part of src/)
Purpose: Tiny shared helpers for the scenario_adapters* modules — a timestamp
         helper and a 2xx status check, kept out of both adapter modules so
         neither imports from the other.
Dependencies: datetime (stdlib), httpx (type only)
Used by: evals/scenario_adapters.py, evals/scenario_adapters_extra.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

GRAPH_PREFIX: str = "/v1/graph"
ADMIN_PREFIX: str = "/v1/admin"


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat()


def is_ok(resp: httpx.Response) -> bool:
    """Return True for any 2xx HTTP status."""
    return 200 <= resp.status_code < 300
