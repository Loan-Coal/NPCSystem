"""
test_quest_event_provenance_v14.py - Unit tests for P3 quest event provenance enforcement.

Does NOT: execute graph writes.

Dependencies injected: none.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from npc_engine.graph.event.event_writer import ensure_quest_event_provenance
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.type_registry.registry import build_type_registry
from npc_engine.utils.errors import QuestProvenanceError


def _type_registry():
    schema_path = Path(__file__).resolve().parents[3] / "src" / "npc_engine" / "game_schema.yaml"
    return build_type_registry(base_schema=load_game_schema(schema_path=str(schema_path)), extension_sources=())


def _base_event():
    event_model = _type_registry().node_models["event"]
    return event_model(
        id="evt-quest-1",
        summary="Quest offered",
        severity=10,
        location_id="town-square",
        occurred_at=datetime.now(timezone.utc).isoformat(),
        tick_id=1,
        event_type="quest_offered",
        is_public=True,
        last_graph_updated_at=datetime.now(timezone.utc).isoformat(),
    )
def test_ensure_quest_event_provenance_rejects_missing_fields() -> None:
    event = _base_event()

    with pytest.raises(QuestProvenanceError):
        ensure_quest_event_provenance(event=event)


def test_ensure_quest_event_provenance_accepts_complete_payload() -> None:
    event = _base_event().model_copy(
        update={
            "producer": "quest_lifecycle_engine",
            "origin_engine": "quest",
            "schema_version": "v1.4",
            "provenance": {
                "request_id": "req-1",
                "idempotency_key": "idem-1",
                "idempotency_request_hash": "hash-1",
                "actor_id": "player-1",
                "reason": "quest_offer",
            },
        }
    )

    ensure_quest_event_provenance(event=event)


def test_ensure_quest_event_provenance_rejects_none_provenance_values() -> None:
    event = _base_event().model_copy(
        update={
            "producer": "quest_lifecycle_engine",
            "origin_engine": "quest",
            "schema_version": "v1.4",
            "provenance": {
                "request_id": None,
                "idempotency_key": "idem-1",
                "idempotency_request_hash": "hash-1",
                "actor_id": "player-1",
                "reason": "quest_offer",
            },
        }
    )

    with pytest.raises(QuestProvenanceError):
        ensure_quest_event_provenance(event=event)
