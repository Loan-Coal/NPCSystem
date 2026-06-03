"""
test_cypher_label_injection.py - Regression tests for dynamic Cypher label sanitization (SEV-17).

Does NOT: touch a real Neo4j database (uses a recording stub session).

Dependencies injected: None.
"""

import pytest

from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.engines.quest_generation.slot_models import SlotDefinition
from npc_engine.graph.generic_graph_utils import cypher_identifier, resolve_node_label
from npc_engine.graph.graph_admin_service import GraphAdminService

_INJECTION_LABEL = "Character`}) MATCH (n2) DETACH DELETE n2 //"


class _RecordStub:
    def __init__(self, value: dict[str, int]):
        self._value = value

    def __getitem__(self, key: str) -> int:
        return self._value[key]


class _ResultStub:
    def __init__(self, record: _RecordStub | None):
        self._record = record

    async def single(self) -> _RecordStub | None:
        return self._record

    async def consume(self) -> None:
        return None

    def __aiter__(self):
        async def _gen():
            if False:
                yield None

        return _gen()


class _RecordingSession:
    """Records the Cypher query string passed to run() and returns a canned result."""

    def __init__(self, record: _RecordStub | None):
        self.queries: list[str] = []
        self._record = record

    async def run(self, query: str, **_: object) -> _ResultStub:
        self.queries.append(query)
        return _ResultStub(self._record)


@pytest.mark.asyncio
async def test_hard_delete_node_escapes_label() -> None:
    """A malicious label must be backtick-escaped, not interpolated raw into Cypher."""

    session = _RecordingSession(_RecordStub({"deleted_edges": 0}))
    service = GraphAdminService(session=session)  # type: ignore[arg-type]

    await service._hard_delete_node(label=_INJECTION_LABEL, node_id="x")

    query = session.queries[0]
    assert cypher_identifier(_INJECTION_LABEL) in query
    # The break-out must not appear outside the backtick-quoted identifier.
    assert "}) MATCH (n2) DETACH DELETE n2 //" not in query.replace(cypher_identifier(_INJECTION_LABEL), "")


@pytest.mark.asyncio
async def test_get_candidates_escapes_label() -> None:
    """Quest-gen candidate query must backtick-escape the slot node_type label."""

    session = _RecordingSession(record=None)
    engine = object.__new__(QuestGenerationEngine)
    node_type = "event`) DETACH DELETE n //"
    slots = (SlotDefinition(name="target", node_type=node_type, required=True),)

    await engine._get_candidates(session, slots)  # type: ignore[arg-type]

    query = session.queries[0]
    escaped = cypher_identifier(resolve_node_label(node_type))
    assert escaped in query
    assert ") DETACH DELETE n //" not in query.replace(escaped, "")
