"""
test_base_contract_loader_labels.py - Tests for load_base_node_labels and the base node
identifier boundary check (M1.2).

Does NOT: touch Neo4j. Malformed contracts are validated through the document model and
the checker directly, so no temporary YAML is written to the package directory.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.type_registry.base_contract_loader import (
    NODE_LABEL_PATTERN,
    NODE_TYPE_PATTERN,
    _validate_node_identifiers,
    load_base_node_labels,
    load_base_node_types,
)
from npc_engine.type_registry.base_contract_models import BaseNodeTypeDocument
from npc_engine.utils.errors import RegistryValidationError


def _document(*, node_type: str, label: str) -> BaseNodeTypeDocument:
    return BaseNodeTypeDocument(node_type=node_type, label=label)


def test_load_base_node_labels_returns_a_label_for_every_shipped_kind() -> None:
    """Happy path: the label map covers exactly the same keys as the field map."""

    labels = load_base_node_labels()

    assert set(labels) == set(load_base_node_types())
    assert labels["belief"] == "Belief"
    assert labels["resource_node"] == "ResourceNode"


def test_load_base_node_labels_is_immutable() -> None:
    """The returned mapping is a MappingProxyType and cannot be mutated by a caller."""

    labels = load_base_node_labels()

    with pytest.raises(TypeError):
        labels["belief"] = "Something"  # type: ignore[index]


def test_registry_keys_are_snake_case_and_match_their_filename() -> None:
    """Regression guard for the collapsed-key defect fixed in M1.2.

    Deriving the key by lowercasing a PascalCase node_type turned `ResourceNode` into
    `resourcenode`, which no caller could reach — base_edges/produces.yaml declares
    `dst_type: resource_node`, so the edge contract dangled.
    """

    for node_key in load_base_node_types():
        assert NODE_TYPE_PATTERN.fullmatch(node_key), node_key


@pytest.mark.parametrize(
    "bad_node_type",
    ["ResourceNode", "resource-node", "1resource", "resource node", "", "resource.node"],
)
def test_validate_rejects_a_non_snake_case_node_type(bad_node_type: str) -> None:
    """Failure path: a node_type that is not a snake_case identifier fails at load."""

    with pytest.raises(RegistryValidationError) as excinfo:
        _validate_node_identifiers(
            document=_document(node_type=bad_node_type, label="Fine"),
            source="base_nodes/bad.yaml",
        )

    assert "node_type must be snake_case" in excinfo.value.detail


@pytest.mark.parametrize(
    "bad_label",
    ["Bad Label", "Bad`) DETACH DELETE n //", "Bad-Label", "9Label", "", "Bad{}"],
)
def test_validate_rejects_a_label_that_is_not_a_bare_identifier(bad_label: str) -> None:
    """Failure path: a label is the one file-supplied value that reaches Cypher.

    cypher_identifier() backtick-escapes it downstream and stays the injection guard; this
    check makes a malformed label fail at the boundary rather than reaching a query.
    """

    with pytest.raises(RegistryValidationError) as excinfo:
        _validate_node_identifiers(
            document=_document(node_type="fine", label=bad_label),
            source="base_nodes/bad.yaml",
        )

    assert "label must be a bare identifier" in excinfo.value.detail


def test_validate_accepts_a_well_formed_contract() -> None:
    """A snake_case key with a PascalCase label passes the boundary check."""

    _validate_node_identifiers(
        document=_document(node_type="resource_node", label="ResourceNode"),
        source="base_nodes/resource_node.yaml",
    )

    assert NODE_LABEL_PATTERN.fullmatch("ResourceNode")
