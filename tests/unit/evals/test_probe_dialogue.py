"""
Module: test_probe_dialogue
Layer: test (unit)
Purpose: Tests for evals/probe_dialogue.py — DialogueProbe's turn-driving loop, the 3
         judged rates, entity/knowledge rates, latency percentiles, and the context-
         measurement metrics (token-budget utilisation, per-slot inclusion, drop
         attribution).
Dependencies: pytest, unittest.mock, probe_dialogue (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph_vocabulary import GraphVocabulary
from matchers import JudgeResult
from probe_dialogue import DIALOGUE_PROBE_FACTORIES, DialogueProbe, _slot_prefix


def _ok(payload: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


_RECEIPT = {
    "retrieval_profile": "default",
    "item_keys": ["character:npc_x", "memories", "rag:r1"],
    "dropped_keys": ["rag:r2"],
    "dropped": [{"key": "rag:r2", "tier": "tierC", "reason": "prompt_budget"}],
    "tier_spend": [],
    "total_tokens": 1000,
    "prompt_token_budget": 5000,
    "budget_trimmed": True,
}


def _client(npc_response: str = "Not much has changed around here.") -> MagicMock:
    client = MagicMock()

    def _post(url: str, **kwargs: object) -> MagicMock:
        if url == "/v1/dialogue":
            return _ok({"npc_response": npc_response, "context_receipt": _RECEIPT})
        return _ok({"data": {}})

    client.post.side_effect = _post
    client.get.return_value = _ok({"data": {}})
    return client


def _patched_scorers():
    return (
        patch("probe_dialogue.fetch_vocabulary", return_value=GraphVocabulary(ids=frozenset())),
        patch("probe_dialogue.load_aliases", return_value=MagicMock(aliases={})),
    )


def _yes(exp: dict, resp: dict) -> JudgeResult:
    return JudgeResult(score=True)


def test_engine_name_is_dialogue() -> None:
    assert DialogueProbe().engine_name == "dialogue"


def test_measure_before_drive_returns_empty() -> None:
    probe = DialogueProbe()
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(_client())
    assert probe.measure(MagicMock()) == {}


def test_slot_prefix_normalises_id_suffixed_keys() -> None:
    assert _slot_prefix("character:npc_probe_dialogue_abc123") == "character:*"
    assert _slot_prefix("memories") == "memories"


@patch("probe_dialogue.evaluate", side_effect=_yes)
def test_full_cycle_reports_judged_rates_and_latency(mock_evaluate: MagicMock) -> None:
    probe = DialogueProbe()
    client = _client()
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(client)
    probe.drive(client, ticks=2)

    p1, p2 = _patched_scorers()
    with p1, p2:
        metrics = probe.measure(client)

    assert metrics["tone_judge_rate"] == 1.0
    assert metrics["affirms_judge_rate"] == 1.0
    assert metrics["commits_judge_rate"] == 1.0
    assert "latency_p50_ms" in metrics
    assert "latency_p95_ms" in metrics


@patch("probe_dialogue.evaluate", side_effect=_yes)
def test_context_metrics_report_budget_utilization_and_drop_attribution(mock_evaluate: MagicMock) -> None:
    probe = DialogueProbe()
    client = _client()
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(client)
    probe.drive(client, ticks=1)

    p1, p2 = _patched_scorers()
    with p1, p2:
        metrics = probe.measure(client)

    assert metrics["token_budget_utilization"] == 1000 / 5000
    assert metrics["dropped_prompt_budget"] == 1.0
    assert metrics["dropped_tier_soft_cap"] == 0.0
    assert metrics["dropped_final_trim"] == 0.0
    assert metrics["budget_trimmed_rate"] == 1.0
    assert metrics["slot_inclusion:character:*"] == 1.0
    assert metrics["slot_inclusion:memories"] == 1.0
    assert metrics["slot_inclusion:rag:*"] == 1.0


@patch("probe_dialogue.evaluate", side_effect=lambda exp, resp: JudgeResult(score=None))
def test_judge_infra_failures_are_excluded_not_counted_as_fails(mock_evaluate: MagicMock) -> None:
    probe = DialogueProbe()
    client = _client()
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(client)
    probe.drive(client, ticks=1)

    p1, p2 = _patched_scorers()
    with p1, p2:
        metrics = probe.measure(client)

    assert metrics["tone_judge_rate"] == 0.0  # all-inconclusive: no conclusive scores


def test_invariant_fails_on_an_empty_npc_response() -> None:
    probe = DialogueProbe()
    client = _client(npc_response="")
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(client)
    probe.drive(client, ticks=1)

    assert probe.invariants["every_turn_returned_text"](client) is False


def test_invariant_holds_with_nonempty_responses() -> None:
    probe = DialogueProbe()
    client = _client()
    with patch("probe_dialogue.ensure_player_node"):
        probe.setup(client)
    probe.drive(client, ticks=1)

    assert probe.invariants["every_turn_returned_text"](client) is True


def test_dialogue_probe_factory_is_registered() -> None:
    assert "dialogue" in DIALOGUE_PROBE_FACTORIES
    probe = DIALOGUE_PROBE_FACTORIES["dialogue"](MagicMock())
    assert probe.engine_name == "dialogue"
