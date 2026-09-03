#!/usr/bin/env python
"""
Module: api_contract_differ
Layer: scripts (dev tooling)
Purpose: Decide whether the change between two recorded API contracts is breaking.
         Pure and app-free by construction, so the detector can be tested on synthetic
         contract pairs rather than only against the committed baseline — a
         baseline-only test is green today and proves nothing.
Does NOT: import the app, read or write files, or consult the baseline.
Dependencies: api_contract_models
Dependencies injected: None.
Used by: scripts/check_api_contract.py, tests/unit/scripts/test_api_contract_differ.py

The request/response asymmetry is deliberate and is the part a naive symmetric differ
gets backwards. A client SENDS requests and READS responses, so tightening a request
breaks it (a newly required field, a narrowed enum) while tightening a response does
not; and widening a response breaks it (an enum member it cannot switch on) while
widening a request does not.
"""

from __future__ import annotations

from api_contract_models import (
    ApiContract,
    BreakKind,
    ContractBreak,
    OperationSpec,
    SchemaSpec,
    is_required,
    type_of,
)


def _schema_roles(contract: ApiContract) -> tuple[set[str], set[str]]:
    """Return (request schema names, response schema names) used by the operations."""
    requests: set[str] = set()
    responses: set[str] = set()
    for operation in contract.operations.values():
        if operation.request_schema:
            requests.add(operation.request_schema)
        responses.update(operation.response_schemas.values())
    return _close_over_refs(contract, requests), _close_over_refs(contract, responses)


def _close_over_refs(contract: ApiContract, seeds: set[str]) -> set[str]:
    """Return seeds plus every schema reachable from them by $ref."""
    seen: set[str] = set()
    pending = list(seeds)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        schema = contract.schemas.get(name)
        if schema is not None:
            pending.extend(ref for ref in schema.refs if ref not in seen)
    return seen


def _diff_operation(key: str, before: OperationSpec, after: OperationSpec) -> list[ContractBreak]:
    """Return breaks for one operation present in both contracts."""
    breaks: list[ContractBreak] = []
    dropped = sorted(set(before.status_codes) - set(after.status_codes))
    if dropped:
        breaks.append(
            ContractBreak(
                kind=BreakKind.STATUS_CODE_REMOVED,
                where=key,
                detail=f"no longer declares status {', '.join(dropped)}",
            )
        )
    if after.auth_required and not before.auth_required:
        breaks.append(
            ContractBreak(
                kind=BreakKind.AUTH_NEWLY_REQUIRED,
                where=key,
                detail="was reachable without an API key and now requires one",
            )
        )
    breaks.extend(_diff_params(key, before, after))
    return breaks


def _diff_params(key: str, before: OperationSpec, after: OperationSpec) -> list[ContractBreak]:
    """Return breaks for parameters that became mandatory."""
    was_required = {(p.location, p.name): p.required for p in before.params}
    breaks: list[ContractBreak] = []
    for param in after.params:
        if not param.required:
            continue
        if was_required.get((param.location, param.name), False):
            continue
        breaks.append(
            ContractBreak(
                kind=BreakKind.PARAM_NEWLY_REQUIRED,
                where=key,
                detail=f"{param.location} parameter {param.name!r} is now required",
            )
        )
    return breaks


def _diff_operations(before: ApiContract, after: ApiContract) -> list[ContractBreak]:
    """Return breaks for removed operations and for tightened surviving ones."""
    breaks: list[ContractBreak] = []
    for key in sorted(before.operations):
        current = after.operations.get(key)
        if current is None:
            breaks.append(
                ContractBreak(
                    kind=BreakKind.OPERATION_REMOVED,
                    where=key,
                    detail="operation is no longer served",
                )
            )
            continue
        breaks.extend(_diff_operation(key, before.operations[key], current))
    return breaks


def _diff_response_schema(name: str, before: SchemaSpec, after: SchemaSpec) -> list[ContractBreak]:
    """Return breaks for a schema a client reads: fields must not vanish or change type."""
    breaks: list[ContractBreak] = []
    for field, encoded in sorted(before.fields.items()):
        current = after.fields.get(field)
        if current is None:
            breaks.append(
                ContractBreak(kind=BreakKind.RESPONSE_FIELD_REMOVED, where=name, detail=f"field {field!r} removed")
            )
        elif type_of(current) != type_of(encoded):
            breaks.append(
                ContractBreak(
                    kind=BreakKind.RESPONSE_FIELD_TYPE_CHANGED,
                    where=name,
                    detail=f"field {field!r} changed type {type_of(encoded)} -> {type_of(current)}",
                )
            )
    for field, members in sorted(before.enums.items()):
        added = sorted(set(after.enums.get(field, ())) - set(members))
        if added:
            breaks.append(
                ContractBreak(
                    kind=BreakKind.RESPONSE_ENUM_WIDENED,
                    where=name,
                    detail=f"field {field!r} may now return {', '.join(added)}",
                )
            )
    return breaks


def _diff_request_schema(name: str, before: SchemaSpec, after: SchemaSpec) -> list[ContractBreak]:
    """Return breaks for a schema a client sends: it must not become harder to satisfy."""
    breaks: list[ContractBreak] = []
    for field, encoded in sorted(after.fields.items()):
        previous = before.fields.get(field)
        if previous is None:
            if is_required(encoded):
                breaks.append(
                    ContractBreak(
                        kind=BreakKind.REQUEST_FIELD_NEWLY_REQUIRED,
                        where=name,
                        detail=f"new field {field!r} is required",
                    )
                )
            continue
        if is_required(encoded) and not is_required(previous):
            breaks.append(
                ContractBreak(
                    kind=BreakKind.REQUEST_FIELD_NEWLY_REQUIRED,
                    where=name,
                    detail=f"field {field!r} became required",
                )
            )
        elif type_of(encoded) != type_of(previous):
            breaks.append(
                ContractBreak(
                    kind=BreakKind.REQUEST_FIELD_TYPE_CHANGED,
                    where=name,
                    detail=f"field {field!r} changed type {type_of(previous)} -> {type_of(encoded)}",
                )
            )
    breaks.extend(_diff_request_enums(name, before, after))
    return breaks


def _diff_request_enums(name: str, before: SchemaSpec, after: SchemaSpec) -> list[ContractBreak]:
    """Return breaks for request enums that stopped accepting a value."""
    breaks: list[ContractBreak] = []
    for field, members in sorted(before.enums.items()):
        removed = sorted(set(members) - set(after.enums.get(field, ())))
        if removed:
            breaks.append(
                ContractBreak(
                    kind=BreakKind.REQUEST_ENUM_NARROWED,
                    where=name,
                    detail=f"field {field!r} no longer accepts {', '.join(removed)}",
                )
            )
    return breaks


def _diff_schemas(before: ApiContract, after: ApiContract) -> list[ContractBreak]:
    """Return breaks for every schema present in both contracts, by its role."""
    requests, responses = _schema_roles(before)
    breaks: list[ContractBreak] = []
    for name in sorted(before.schemas):
        current = after.schemas.get(name)
        if current is None:
            continue  # an orphaned schema is not a contract break; its operation is
        if name in responses:
            breaks.extend(_diff_response_schema(name, before.schemas[name], current))
        if name in requests:
            breaks.extend(_diff_request_schema(name, before.schemas[name], current))
    return breaks


def diff_contracts(before: ApiContract, after: ApiContract) -> list[ContractBreak]:
    """Return every breaking change from before to after; empty when only additive.

    Args:
        before: The recorded baseline contract.
        after: The contract extracted from the app under test.

    Returns:
        One ContractBreak per breaking change, in a stable order.
    """
    breaks: list[ContractBreak] = []
    if before.api_v1_prefix != after.api_v1_prefix:
        breaks.append(
            ContractBreak(
                kind=BreakKind.PREFIX_CHANGED,
                where="api_v1_prefix",
                detail=f"{before.api_v1_prefix} -> {after.api_v1_prefix}",
            )
        )
    breaks.extend(_diff_operations(before, after))
    breaks.extend(_diff_schemas(before, after))
    return breaks
