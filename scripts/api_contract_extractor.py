#!/usr/bin/env python
"""
Module: api_contract_extractor
Layer: scripts (dev tooling)
Purpose: Build an ApiContract from the live app, deterministically and from a pinned
         environment, so the same source tree yields the same contract on any machine.
Does NOT: compare contracts, read the baseline, or write any file.
Dependencies: os, typing, fastapi, api_contract_models, npc_engine
Dependencies injected: None.
Used by: scripts/check_api_contract.py, tests/unit/scripts/test_api_contract_extractor.py

Two things this does that reading app.openapi() alone cannot:

1. Operations are enumerated from `app.routes`, not from the OpenAPI paths. Measured
   at R5.1: the app serves 148 APIRoutes plus one APIWebSocketRoute (/v1/ws/dialogue),
   and app.openapi() contains zero WebSocket entries. A gate built only on OpenAPI
   would let the streaming route — which docs/INTEGRATION.md sells as part of the
   contract — be deleted silently.
2. Prose is stripped (description, summary, title, example, operationId, tags). Those
   fields are ~2/3 of the raw schema and change whenever a docstring does. A baseline
   whose diffs are mostly prose trains reviewers to re-record without reading, which is
   how the R4.7-deleted live_openapi.json lost its credibility before it lost accuracy.

The environment is pinned rather than inherited because Settings reads a .env that is
gitignored: a fresh clone, a worktree and CI would otherwise each produce a different
contract, or fail outright on the required API_KEY_SECRET.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from api_contract_models import (
    OPTIONAL_MARKER,
    PREFIX_PLACEHOLDER,
    REQUIRED_MARKER,
    ApiContract,
    OperationSpec,
    ParamSpec,
    SchemaSpec,
)

# A fixed, non-placeholder secret >= 16 chars, so Settings validates identically
# everywhere. It is not a credential: it is only ever used to construct the app
# in-process for schema extraction, and the app is never served.
_PINNED_ENV: dict[str, str] = {
    "API_KEY_SECRET": "api_contract_gate_fixed_secret",
    "ENV": "dev",
    "API_V1_PREFIX": "/v1",
}

# This gate must measure the tree it lives in. scripts/ is on sys.path when the CLI
# runs, but src/ is not, so a `pip install -e .` elsewhere (or a stale non-editable
# install) would otherwise be imported instead — measured during R5.1, where the gate
# read a different checkout entirely and stayed green through two real breaking changes.
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

# Applied at import time, not inside build_app(): build_contract() imports npc_engine
# submodules before it calls build_app(), and the first such import is what binds the
# npc_engine package path for the whole process. Patching later is too late.
if str(_SRC_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(_SRC_ROOT))

_WEBSOCKET_METHOD = "WEBSOCKET"
_JSON_CONTENT = "application/json"
_SCHEMA_PREFIX = "#/components/schemas/"


def build_app() -> Any:
    """Return a freshly constructed app under the pinned contract environment."""
    os.environ.update(_PINNED_ENV)
    from npc_engine.config import get_settings
    from npc_engine.main import create_app

    get_settings.cache_clear()
    return create_app()


def template_path(path: str, prefix: str) -> str:
    """Replace the live version prefix with a placeholder so a bump is one diff line."""
    if prefix and path.startswith(prefix):
        return PREFIX_PLACEHOLDER + path[len(prefix) :]
    return path


def ref_name(node: dict[str, Any] | None) -> str | None:
    """Return the component schema name a node references, directly or via a union."""
    if not isinstance(node, dict):
        return None
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith(_SCHEMA_PREFIX):
        return ref[len(_SCHEMA_PREFIX) :]
    for key in ("anyOf", "allOf", "oneOf"):
        for member in node.get(key, []) or []:
            name = ref_name(member)
            if name is not None:
                return name
    return ref_name(node.get("items")) if "items" in node else None


def canonical_type(prop: dict[str, Any]) -> str:
    """Return a stable type name for one property, ignoring prose and constraints."""
    declared = prop.get("type")
    if isinstance(declared, str):
        return declared
    referenced = ref_name(prop)
    return referenced if referenced is not None else "any"


def encode_schema(name: str, node: dict[str, Any]) -> SchemaSpec:
    """Return the recorded shape of one component schema."""
    properties: dict[str, Any] = node.get("properties", {}) or {}
    required = set(node.get("required", []) or [])
    fields: dict[str, str] = {}
    enums: dict[str, tuple[str, ...]] = {}
    refs: set[str] = set()
    for field, prop in properties.items():
        marker = REQUIRED_MARKER if field in required else OPTIONAL_MARKER
        fields[field] = canonical_type(prop) + marker
        members = prop.get("enum")
        if isinstance(members, list):
            enums[field] = tuple(sorted(str(member) for member in members))
        referenced = ref_name(prop)
        if referenced is not None:
            refs.add(referenced)
    return SchemaSpec(name=name, fields=fields, enums=enums, refs=tuple(sorted(refs)))


def _params_of(operation: dict[str, Any]) -> tuple[ParamSpec, ...]:
    """Return the recorded parameters of one OpenAPI operation, in a stable order."""
    params = [
        ParamSpec(
            name=str(entry.get("name", "")),
            location=str(entry.get("in", "")),
            required=bool(entry.get("required", False)),
            type_name=canonical_type(entry.get("schema", {}) or {}),
        )
        for entry in operation.get("parameters", []) or []
    ]
    return tuple(sorted(params, key=lambda p: (p.location, p.name)))


def _responses_of(operation: dict[str, Any]) -> tuple[tuple[str, ...], dict[str, str]]:
    """Return the declared status codes and the schema name each one returns."""
    responses: dict[str, Any] = operation.get("responses", {}) or {}
    schemas: dict[str, str] = {}
    for status, body in responses.items():
        content = (body or {}).get("content", {}) or {}
        name = ref_name((content.get(_JSON_CONTENT, {}) or {}).get("schema"))
        if name is not None:
            schemas[str(status)] = name
    return tuple(sorted(str(status) for status in responses)), schemas


def _request_schema_of(operation: dict[str, Any]) -> str | None:
    """Return the component schema name of the JSON request body, when there is one."""
    body = operation.get("requestBody") or {}
    content = body.get("content", {}) or {}
    return ref_name((content.get(_JSON_CONTENT, {}) or {}).get("schema"))


def _http_operation(method: str, path: str, spec: dict[str, Any], auth_required: bool) -> OperationSpec:
    """Return the recorded shape of one HTTP operation."""
    status_codes, response_schemas = _responses_of(spec)
    return OperationSpec(
        method=method,
        path=path,
        auth_required=auth_required,
        deprecated=bool(spec.get("deprecated", False)),
        status_codes=status_codes,
        request_schema=_request_schema_of(spec),
        response_schemas=response_schemas,
        params=_params_of(spec),
    )


def operation_key(method: str, path: str) -> str:
    """Return the stable contract key for one operation."""
    return f"{method} {path}"


def build_contract() -> ApiContract:
    """Return the contract of the live app, with the version prefix templated."""
    from fastapi.routing import APIRoute, APIWebSocketRoute

    from npc_engine.auth.middleware_helpers import is_public_path

    app = build_app()
    prefix = _PINNED_ENV["API_V1_PREFIX"]
    document = app.openapi()
    paths: dict[str, Any] = document.get("paths", {}) or {}
    operations: dict[str, OperationSpec] = {}

    for route in app.routes:
        auth_required = not is_public_path(route.path, env=_PINNED_ENV["ENV"])
        templated = template_path(route.path, prefix)
        if isinstance(route, APIWebSocketRoute):
            key = operation_key(_WEBSOCKET_METHOD, templated)
            operations[key] = OperationSpec(
                method=_WEBSOCKET_METHOD, path=templated, auth_required=auth_required
            )
            continue
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or set()):
            spec = (paths.get(route.path, {}) or {}).get(method.lower())
            if spec is None:
                continue
            operations[operation_key(method, templated)] = _http_operation(
                method, templated, spec, auth_required
            )

    components: dict[str, Any] = (document.get("components", {}) or {}).get("schemas", {}) or {}
    schemas = {name: encode_schema(name, node) for name, node in sorted(components.items())}
    return ApiContract(api_v1_prefix=prefix, operations=operations, schemas=schemas)
