#!/usr/bin/env python
"""
Module: api_contract_models
Layer: scripts (dev tooling)
Purpose: The typed shape of the /v1 API contract and of a breaking change to it.
         One recorded contract plus one pure differ is what lets `make check` tell a
         breaking change from an additive one, which the field-drop ratchet in
         check_api_stability.py cannot do (it records field names over two files).
Does NOT: import the app, read the baseline, or perform any I/O.
Dependencies: enum, pydantic
Dependencies injected: None.
Used by: scripts/api_contract_differ.py, scripts/api_contract_extractor.py,
         scripts/check_api_contract.py, tests/unit/scripts/test_api_contract_differ.py
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Field encoding used in SchemaSpec.fields: "<canonical type><required marker>".
REQUIRED_MARKER = "!"
OPTIONAL_MARKER = "?"

# Placeholder substituted for the live settings.API_V1_PREFIX in every operation key,
# so changing the prefix reports one PREFIX_CHANGED rather than N operation removals.
PREFIX_PLACEHOLDER = "{v1}"


class BreakKind(str, Enum):
    """Every change this gate treats as breaking for an external consumer."""

    OPERATION_REMOVED = "operation_removed"
    PREFIX_CHANGED = "prefix_changed"
    STATUS_CODE_REMOVED = "status_code_removed"
    AUTH_NEWLY_REQUIRED = "auth_newly_required"
    REQUEST_FIELD_NEWLY_REQUIRED = "request_field_newly_required"
    REQUEST_FIELD_TYPE_CHANGED = "request_field_type_changed"
    REQUEST_ENUM_NARROWED = "request_enum_narrowed"
    RESPONSE_FIELD_REMOVED = "response_field_removed"
    RESPONSE_FIELD_TYPE_CHANGED = "response_field_type_changed"
    RESPONSE_ENUM_WIDENED = "response_enum_widened"
    PARAM_NEWLY_REQUIRED = "param_newly_required"


class ParamSpec(BaseModel):
    """One path, query or header parameter of an operation."""

    model_config = ConfigDict(frozen=True)
    name: str
    location: str
    required: bool
    type_name: str


class OperationSpec(BaseModel):
    """One HTTP or WebSocket operation, keyed elsewhere by "METHOD path"."""

    model_config = ConfigDict(frozen=True)
    method: str
    path: str
    auth_required: bool
    deprecated: bool = False
    status_codes: tuple[str, ...] = ()
    request_schema: str | None = None
    response_schemas: dict[str, str] = Field(default_factory=dict)
    params: tuple[ParamSpec, ...] = ()


class SchemaSpec(BaseModel):
    """One component schema: its fields, and any enum members it constrains."""

    model_config = ConfigDict(frozen=True)
    name: str
    fields: dict[str, str] = Field(default_factory=dict)
    enums: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    # Component schemas this one references. Roles propagate along these, so a model
    # nested inside a response body is diffed as a response too.
    refs: tuple[str, ...] = ()


class ApiContract(BaseModel):
    """The whole recorded surface: the version prefix, its operations and schemas."""

    model_config = ConfigDict(frozen=True)
    api_v1_prefix: str
    operations: dict[str, OperationSpec] = Field(default_factory=dict)
    schemas: dict[str, SchemaSpec] = Field(default_factory=dict)


class ContractBreak(BaseModel):
    """One breaking change, with enough detail to name the offending element."""

    model_config = ConfigDict(frozen=True)
    kind: BreakKind
    where: str
    detail: str

    def render(self) -> str:
        """Return a single human-readable report line."""
        return f"  [{self.kind.value}] {self.where}: {self.detail}"


def is_required(encoded: str) -> bool:
    """Return True when an encoded field value carries the required marker."""
    return encoded.endswith(REQUIRED_MARKER)


def type_of(encoded: str) -> str:
    """Return the canonical type name from an encoded field value."""
    return encoded.rstrip(REQUIRED_MARKER + OPTIONAL_MARKER)
