"""
Module: tests.unit.scripts.test_api_contract_differ
Layer: tests
Purpose: The RED anchor for R5.1 (CR-L12-07). Drives api_contract_differ over synthetic
         before/after contract pairs and asserts each breaking change is detected and
         each additive one is not.
Dependencies: pathlib, sys, pytest, api_contract_models, api_contract_differ
Used by: make test (pytest discovery), make check via test-cov

Why synthetic pairs and not the committed baseline: a test that only asserts
"current app == baseline" is green the day it is written and stays green while the
detector does nothing. These pairs fail against a detector that returns [], which is
exactly the counterfactual — gut diff_contracts and every breaking case reds.

The companion additive test is load-bearing in the other direction: without it a
detector that called everything a break would pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from api_contract_differ import diff_contracts  # noqa: E402
from api_contract_models import (  # noqa: E402
    ApiContract,
    BreakKind,
    OperationSpec,
    ParamSpec,
    SchemaSpec,
)

_PREFIX = "/v1"


def _operation(**overrides: object) -> OperationSpec:
    """Return a baseline GET operation, with any field overridden."""
    base: dict[str, object] = {
        "method": "GET",
        "path": "{v1}/npc/{npc_id}/state",
        "auth_required": True,
        "status_codes": ("200",),
        "response_schemas": {"200": "NpcStateResponse"},
    }
    base.update(overrides)
    return OperationSpec(**base)  # type: ignore[arg-type]


def _contract(
    operations: dict[str, OperationSpec] | None = None,
    schemas: dict[str, SchemaSpec] | None = None,
    prefix: str = _PREFIX,
) -> ApiContract:
    """Return a contract with one operation and one response schema by default."""
    if operations is None:
        operations = {"GET {v1}/npc/{npc_id}/state": _operation()}
    if schemas is None:
        schemas = {
            "NpcStateResponse": SchemaSpec(
                name="NpcStateResponse",
                fields={"npc_id": "string!", "mood": "string?"},
                enums={"mood": ("calm", "angry")},
            )
        }
    return ApiContract(api_v1_prefix=prefix, operations=operations, schemas=schemas)


def _kinds(before: ApiContract, after: ApiContract) -> set[BreakKind]:
    """Return the set of break kinds the differ reports for one pair."""
    return {break_.kind for break_ in diff_contracts(before, after)}


def test_operation_removed_is_breaking() -> None:
    assert BreakKind.OPERATION_REMOVED in _kinds(_contract(), _contract(operations={}))


def test_prefix_change_is_breaking_once() -> None:
    breaks = diff_contracts(_contract(), _contract(prefix="/v2"))
    assert [b.kind for b in breaks] == [BreakKind.PREFIX_CHANGED]


def test_status_code_removed_is_breaking() -> None:
    after = {"GET {v1}/npc/{npc_id}/state": _operation(status_codes=())}
    assert BreakKind.STATUS_CODE_REMOVED in _kinds(_contract(), _contract(operations=after))


def test_auth_newly_required_is_breaking() -> None:
    before = {"GET {v1}/npc/{npc_id}/state": _operation(auth_required=False)}
    assert BreakKind.AUTH_NEWLY_REQUIRED in _kinds(_contract(operations=before), _contract())


def test_response_field_removed_is_breaking() -> None:
    after = {"NpcStateResponse": SchemaSpec(name="NpcStateResponse", fields={"npc_id": "string!"})}
    assert BreakKind.RESPONSE_FIELD_REMOVED in _kinds(_contract(), _contract(schemas=after))


def test_response_field_type_change_is_breaking() -> None:
    after = {
        "NpcStateResponse": SchemaSpec(
            name="NpcStateResponse", fields={"npc_id": "integer!", "mood": "string?"}
        )
    }
    assert BreakKind.RESPONSE_FIELD_TYPE_CHANGED in _kinds(_contract(), _contract(schemas=after))


def test_response_enum_widened_is_breaking() -> None:
    after = {
        "NpcStateResponse": SchemaSpec(
            name="NpcStateResponse",
            fields={"npc_id": "string!", "mood": "string?"},
            enums={"mood": ("calm", "angry", "smug")},
        )
    }
    assert BreakKind.RESPONSE_ENUM_WIDENED in _kinds(_contract(), _contract(schemas=after))


def test_request_field_newly_required_is_breaking() -> None:
    request = SchemaSpec(name="TalkRequest", fields={"message": "string!", "mood": "string?"})
    tightened = SchemaSpec(name="TalkRequest", fields={"message": "string!", "mood": "string!"})
    operations = {"POST {v1}/npc/talk": _operation(method="POST", path="{v1}/npc/talk", request_schema="TalkRequest")}
    before = _contract(operations=operations, schemas={"TalkRequest": request})
    after = _contract(operations=operations, schemas={"TalkRequest": tightened})
    assert BreakKind.REQUEST_FIELD_NEWLY_REQUIRED in _kinds(before, after)


def test_request_enum_narrowed_is_breaking() -> None:
    wide = SchemaSpec(name="TalkRequest", fields={"tone": "string?"}, enums={"tone": ("warm", "cold")})
    narrow = SchemaSpec(name="TalkRequest", fields={"tone": "string?"}, enums={"tone": ("warm",)})
    operations = {"POST {v1}/npc/talk": _operation(method="POST", path="{v1}/npc/talk", request_schema="TalkRequest")}
    before = _contract(operations=operations, schemas={"TalkRequest": wide})
    after = _contract(operations=operations, schemas={"TalkRequest": narrow})
    assert BreakKind.REQUEST_ENUM_NARROWED in _kinds(before, after)


def test_param_newly_required_is_breaking() -> None:
    optional = ParamSpec(name="limit", location="query", required=False, type_name="integer")
    required = ParamSpec(name="limit", location="query", required=True, type_name="integer")
    before = {"GET {v1}/npc/{npc_id}/state": _operation(params=(optional,))}
    after = {"GET {v1}/npc/{npc_id}/state": _operation(params=(required,))}
    assert BreakKind.PARAM_NEWLY_REQUIRED in _kinds(_contract(operations=before), _contract(operations=after))


@pytest.mark.parametrize(
    "after",
    [
        pytest.param(
            _contract(
                operations={
                    "GET {v1}/npc/{npc_id}/state": _operation(),
                    "GET {v1}/npc/{npc_id}/mood": _operation(path="{v1}/npc/{npc_id}/mood"),
                }
            ),
            id="new_operation",
        ),
        pytest.param(
            _contract(operations={"GET {v1}/npc/{npc_id}/state": _operation(status_codes=("200", "404"))}),
            id="new_status_code",
        ),
        pytest.param(
            _contract(operations={"GET {v1}/npc/{npc_id}/state": _operation(deprecated=True)}),
            id="marked_deprecated",
        ),
        pytest.param(
            _contract(
                schemas={
                    "NpcStateResponse": SchemaSpec(
                        name="NpcStateResponse",
                        fields={"npc_id": "string!", "mood": "string?", "energy": "integer?"},
                        enums={"mood": ("calm", "angry")},
                    )
                }
            ),
            id="new_response_field",
        ),
        pytest.param(
            _contract(
                schemas={
                    "NpcStateResponse": SchemaSpec(
                        name="NpcStateResponse",
                        fields={"npc_id": "string!", "mood": "string!"},
                        enums={"mood": ("calm", "angry")},
                    )
                }
            ),
            id="response_field_now_always_present",
        ),
        pytest.param(
            _contract(
                operations={
                    "GET {v1}/npc/{npc_id}/state": _operation(
                        params=(ParamSpec(name="limit", location="query", required=False, type_name="integer"),)
                    )
                }
            ),
            id="new_optional_param",
        ),
        pytest.param(
            _contract(operations={"GET {v1}/npc/{npc_id}/state": _operation(auth_required=False)}),
            id="auth_relaxed",
        ),
    ],
)
def test_additive_changes_are_not_breaking(after: ApiContract) -> None:
    assert diff_contracts(_contract(), after) == []


def test_identical_contracts_report_nothing() -> None:
    assert diff_contracts(_contract(), _contract()) == []
