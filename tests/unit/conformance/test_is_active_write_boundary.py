"""
test_is_active_write_boundary.py - Pins the prevention half of DEC-252 / ISSUE-258:
the validated write path refuses a Character or Faction with no `is_active`, so the
strict readers can never be handed a node they will silently hide.

Does NOT: touch Neo4j; this exercises registry validation only.

Dependencies injected: the real TypeRegistry built from the tracked base schema.
"""

from __future__ import annotations

import pytest

from npc_engine.api.dependencies_infra import get_type_registry
from npc_engine.type_registry.validation import RegistryOperation, validate_node_payload
from npc_engine.utils.errors import RegistryPayloadValidationError

_CHARACTER_WITHOUT_IS_ACTIVE = {
    "id": "npc-under-test",
    "name": "Under Test",
    "archetype": "merchant",
    "biography": "Exists only in this test.",
    "is_player": False,
    "created_at": "2026-09-02T00:00:00Z",
    "updated_at": "2026-09-02T00:00:00Z",
    "last_graph_updated_at": "2026-09-02T00:00:00Z",
    "gossipy": 50,
    "credulity": 50,
    "honesty": 50,
}

_FACTION_WITHOUT_IS_ACTIVE = {
    "id": "faction-under-test",
    "name": "Under Test",
    "archetype": "guild",
    "created_at": "2026-09-02T00:00:00Z",
    "last_graph_updated_at": "2026-09-02T00:00:00Z",
}


@pytest.mark.parametrize(
    ("node_type", "payload"),
    [("character", _CHARACTER_WITHOUT_IS_ACTIVE), ("faction", _FACTION_WITHOUT_IS_ACTIVE)],
)
def test_write_without_is_active_is_rejected(node_type: str, payload: dict[str, object]) -> None:
    """Both node types that declare `is_active` refuse a write that omits it.

    This is what makes DEC-252's strict reader safe: absence cannot arrive through the
    validated path, so a node the readers hide is a node that never should have existed.
    ISSUE-258 proposed a backfill migration instead; measured against the live graph,
    Character was 23/23 and Faction 10/10 already carrying the field, so the obligation
    is prevention and this test is where it is pinned.
    """
    with pytest.raises(RegistryPayloadValidationError) as caught:
        validate_node_payload(
            registry=get_type_registry(),
            node_type=node_type,
            operation=RegistryOperation.CREATE,
            payload=dict(payload),
        )

    assert "is_active" in str(caught.value)


@pytest.mark.parametrize(
    ("node_type", "payload"),
    [("character", _CHARACTER_WITHOUT_IS_ACTIVE), ("faction", _FACTION_WITHOUT_IS_ACTIVE)],
)
def test_the_same_write_is_accepted_with_is_active(node_type: str, payload: dict[str, object]) -> None:
    """The counterfactual: the rejection above is about the flag and nothing else."""
    validated = validate_node_payload(
        registry=get_type_registry(),
        node_type=node_type,
        operation=RegistryOperation.CREATE,
        payload={**payload, "is_active": True},
    )

    assert validated["is_active"] is True
