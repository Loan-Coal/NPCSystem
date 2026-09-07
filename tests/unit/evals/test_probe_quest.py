"""
Module: test_probe_quest
Layer: test (unit)
Purpose: Tests for evals/probe_quest.py — QuestProbe's generate/offer/accept/evaluate
         drive, the conversion-rate/slot-validity/referential-grounding metrics, the
         background-leak snapshot metric, and both invariants.
Dependencies: pytest, unittest.mock, probe_quest (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph_vocabulary import GraphVocabulary
from probe_quest import QUEST_PROBE_FACTORIES, QuestProbe


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _fail() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 404
    return resp


def _client(
    *,
    quest_status: str = "offered",
    drafts_count: int = 0,
    target_id: str | None = None,
    target_resolves: bool = True,
) -> MagicMock:
    client = MagicMock()
    quest_counter = {"n": 0}

    def _post(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/quests/generate"):
            quest_counter["n"] += 1
            qid = f"quest_{quest_counter['n']}"
            return _ok({"data": {"quest_id": qid, "description": "Recover the lost heirloom."}})
        if "/offer" in url or url == "/v1/quest/accept" or url == "/v1/quest/evaluate":
            return _ok({"data": {}})
        return _ok({"data": {}})

    def _get(url: str, **kwargs: object) -> MagicMock:
        if url.endswith("/quests/drafts"):
            return _ok({"data": {"count": drafts_count}})
        if "/admin/quests/" in url:
            return _ok({"data": {"quest": {"status": quest_status, "target_id": target_id}}})
        if "/graph/nodes/" in url:
            return _ok({"data": {}}) if target_resolves else _fail()
        return _ok({"data": {}})

    client.post.side_effect = _post
    client.get.side_effect = _get
    return client


def test_engine_name_is_quest() -> None:
    assert QuestProbe().engine_name == "quest"


def test_measure_before_drive_reports_only_leak_delta() -> None:
    probe = QuestProbe()
    probe.setup(_client())
    metrics = probe.measure(_client(drafts_count=0))
    assert metrics == {"background_draft_leak_delta": 0.0}


@patch("probe_quest.fetch_vocabulary")
@patch("probe_quest.load_aliases")
def test_full_cycle_reports_conversion_and_leak_delta(mock_aliases: MagicMock, mock_vocab: MagicMock) -> None:
    mock_vocab.return_value = GraphVocabulary(ids=frozenset())
    mock_aliases.return_value = MagicMock(aliases={})

    probe = QuestProbe()
    client = _client(quest_status="completed", target_id=None)
    probe.setup(client)
    probe.drive(client, ticks=3)
    metrics = probe.measure(client)

    assert metrics["quests_per_tick"] == 1.0
    assert metrics["offer_rate"] == 1.0
    assert metrics["accept_rate"] == 1.0
    assert metrics["complete_rate"] == 1.0
    assert metrics["background_draft_leak_delta"] == 0.0
    assert metrics["referential_grounding_rate"] == 1.0


def test_slot_validity_rate_is_zero_denominator_when_no_quest_has_a_target() -> None:
    probe = QuestProbe()
    client = _client(target_id=None)
    probe.setup(client)
    probe.drive(client, ticks=2)

    with patch("probe_quest.fetch_vocabulary", return_value=GraphVocabulary(ids=frozenset())), \
         patch("probe_quest.load_aliases", return_value=MagicMock(aliases={})):
        metrics = probe.measure(client)

    assert metrics["slot_validity_rate"] == 0.0


def test_slot_validity_rate_is_one_when_target_resolves() -> None:
    probe = QuestProbe()
    client = _client(target_id="npc_probe_quest_target")
    probe.setup(client)
    probe.drive(client, ticks=1)

    with patch("probe_quest.fetch_vocabulary", return_value=GraphVocabulary(ids=frozenset())), \
         patch("probe_quest.load_aliases", return_value=MagicMock(aliases={})):
        metrics = probe.measure(client)

    assert metrics["slot_validity_rate"] == 1.0


def test_invariant_slots_reference_real_nodes_fails_on_a_dangling_target() -> None:
    probe = QuestProbe()
    client = _client(target_id="npc_ghost", target_resolves=False)
    probe.setup(client)
    probe.drive(client, ticks=1)

    assert probe._invariant_slots_reference_real_nodes(client) is False


def test_invariant_slots_reference_real_nodes_holds_when_target_resolves() -> None:
    probe = QuestProbe()
    client = _client(target_id="npc_real", target_resolves=True)
    probe.setup(client)
    probe.drive(client, ticks=1)

    assert probe._invariant_slots_reference_real_nodes(client) is True


def test_invariant_no_leak_holds_when_background_count_is_unchanged() -> None:
    probe = QuestProbe()
    probe.setup(_client(drafts_count=5))
    assert probe.invariants["no_leak_during_this_run"](_client(drafts_count=5)) is True


def test_invariant_no_leak_fails_when_background_count_grows() -> None:
    probe = QuestProbe()
    probe.setup(_client(drafts_count=5))
    assert probe.invariants["no_leak_during_this_run"](_client(drafts_count=9)) is False


def test_generate_failure_is_skipped_not_recorded() -> None:
    probe = QuestProbe()
    client = MagicMock()
    client.post.side_effect = lambda url, **kw: _fail() if url.endswith("/quests/generate") else _ok({"data": {}})
    client.get.return_value = _ok({"data": {"count": 0}})

    probe.setup(client)
    probe.drive(client, ticks=3)

    assert probe._quests == []


def test_quest_probe_factory_is_registered() -> None:
    assert "quest" in QUEST_PROBE_FACTORIES
    probe = QUEST_PROBE_FACTORIES["quest"](MagicMock())
    assert probe.engine_name == "quest"
