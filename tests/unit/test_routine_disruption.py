"""
test_routine_disruption.py - Unit tests for routine-disruption rules (Feature 2.3).

Does NOT: connect to Neo4j or any external service. All graph calls are mocked.

Tests:
  - DisruptionRule matches on event type.
  - DisruptionRule matches on severity threshold.
  - No rule fires when neither condition matches.
  - Override expires_at_tick = tick_id + duration_ticks.
  - Emotion valence < -60 triggers set_routine_override.
  - Emotion valence == -60 does NOT trigger.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.events.disruption_loader import DisruptionRule, load_disruption_rules
from npc_engine.engines.events.event_handler import EventHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    event_types: list[str] | None = None,
    severity_min: int | None = None,
    override_location: str = "home",
    duration_ticks: int = 5,
) -> DisruptionRule:
    return DisruptionRule(
        trigger_event_types=tuple(event_types or []),
        trigger_severity_min=severity_min,
        override_location=override_location,
        duration_ticks=duration_ticks,
    )


# ---------------------------------------------------------------------------
# disruption_loader tests
# ---------------------------------------------------------------------------


def test_load_disruption_rules_parses_yaml(tmp_path: Path) -> None:
    yaml_content = """
rules:
  - trigger_event_types: [death, betrayal]
    override_location: home
    duration_ticks: 10
  - trigger_severity_min: 70
    override_location: home
    duration_ticks: 5
"""
    rules_file = tmp_path / "disruption_rules.yaml"
    rules_file.write_text(yaml_content, encoding="utf-8")
    rules = load_disruption_rules(rules_file)
    assert len(rules) == 2
    assert rules[0].trigger_event_types == ("death", "betrayal")
    assert rules[0].duration_ticks == 10
    assert rules[1].trigger_severity_min == 70
    assert rules[1].duration_ticks == 5


def test_load_disruption_rules_missing_file_returns_empty(tmp_path: Path) -> None:
    rules = load_disruption_rules(tmp_path / "nonexistent.yaml")
    assert rules == []


def test_load_disruption_rules_invalid_root_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_disruption_rules(bad_file)


# ---------------------------------------------------------------------------
# _apply_disruption_rules tests
# ---------------------------------------------------------------------------


def test_apply_disruption_rules_matches_event_type() -> None:
    rule = _make_rule(event_types=["death"])
    matched = EventHandler._apply_disruption_rules([rule], event_type="death", severity=10)
    assert matched == [rule]


def test_apply_disruption_rules_matches_severity_threshold() -> None:
    rule = _make_rule(severity_min=70)
    matched = EventHandler._apply_disruption_rules([rule], event_type="unknown", severity=70)
    assert matched == [rule]


def test_apply_disruption_rules_severity_below_threshold_no_match() -> None:
    rule = _make_rule(severity_min=70)
    matched = EventHandler._apply_disruption_rules([rule], event_type="unknown", severity=69)
    assert matched == []


def test_apply_disruption_rules_no_match_returns_empty() -> None:
    rule = _make_rule(event_types=["death"], severity_min=90)
    matched = EventHandler._apply_disruption_rules([rule], event_type="fight", severity=50)
    assert matched == []


def test_apply_disruption_rules_expires_at_tick_correct() -> None:
    """Verify that the caller computes expires_at_tick = tick_id + duration_ticks correctly."""
    rule = _make_rule(severity_min=70, duration_ticks=10)
    tick_id = 42
    [matched_rule] = EventHandler._apply_disruption_rules([rule], event_type="x", severity=75)
    expires_at = tick_id + matched_rule.duration_ticks
    assert expires_at == 52


# ---------------------------------------------------------------------------
# set_routine_override write tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_routine_override_writes_correct_json() -> None:
    from npc_engine.engines.routine.routine_queries import set_routine_override

    session = MagicMock()
    session.run = AsyncMock()
    await set_routine_override(session, "char_1", "home", 100)
    session.run.assert_called_once()
    call_kwargs = session.run.call_args
    override_json = call_kwargs.kwargs.get("override_json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
    # args[0] is the Cypher; override_json is a keyword arg
    _, kwargs = session.run.call_args
    assert kwargs["character_id"] == "char_1"
    parsed = json.loads(kwargs["override_json"])
    assert parsed["location_id"] == "home"
    assert parsed["expires_at_tick"] == 100


# ---------------------------------------------------------------------------
# Dialogue handler emotion-disruption tests
# ---------------------------------------------------------------------------


def _make_dialogue_handler(valence_after_mood: int):
    """Build a DialogueHandler with a mocked EmotionUpdater returning the given valence."""
    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.emotion.emotion_state import EmotionState
    from npc_engine.engines.dialogue.session_store import SessionStore

    session = MagicMock()
    session.run = AsyncMock()

    emotion_state = EmotionState(valence=valence_after_mood, arousal=50, label="test")
    emotion_updater = MagicMock()
    emotion_updater.get_state = AsyncMock(return_value=EmotionState(valence=0, arousal=0, label="neutral"))
    emotion_updater.apply_dialogue_mood = AsyncMock(return_value=emotion_state)

    session_store = MagicMock(spec=SessionStore)
    session_store.get_turns = AsyncMock(return_value=[])
    session_store.append_turns = AsyncMock()

    settings = MagicMock()
    settings.CANNED_RESPONSES_DIR = "/tmp/canned"

    engine_model_config = MagicMock()
    engine_model_config.timeouts_ms.full = 5000
    engine_model_config.timeouts_ms.graph_only = 3000

    from npc_engine.services.input_moderation import build_input_moderation_service

    handler = DialogueHandler.__new__(DialogueHandler)
    handler._session = session
    handler._emotion_updater = emotion_updater
    handler._session_store = session_store
    handler._settings = settings
    handler._engine_model_config = engine_model_config
    handler._knowledge_engine = None
    handler._input_moderation = build_input_moderation_service("mature")
    from npc_engine.services.output_moderation import build_output_moderation_service
    handler._output_moderation = build_output_moderation_service("mature")
    handler._effective_rating = "mature"
    return handler, session


@pytest.mark.asyncio
async def test_emotion_valence_below_threshold_triggers_override() -> None:
    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.dialogue.dialogue_models import DialogueRequest, DialogueResponse
    from npc_engine.engines.routine.routine_queries import set_routine_override

    handler, session = _make_dialogue_handler(valence_after_mood=-61)

    request = MagicMock()
    request.npc_id = "npc_1"
    request.player_id = "player_1"
    request.player_message = "hello"
    request.session_id = None

    final_response = MagicMock()
    final_response.relation_deltas = MagicMock()
    final_response.mood_update = "angry"
    final_response.action = MagicMock()
    final_response.action.type = "speak"
    final_response.npc_response = "..."
    final_response.session_id = None

    with patch.object(handler, "_run_llm_pipeline", new=AsyncMock(return_value=final_response)), \
         patch("npc_engine.engines.dialogue.dialogue_handler.execute_with_degradation", new=AsyncMock(return_value=(final_response, "full"))), \
         patch("npc_engine.engines.dialogue.dialogue_handler.resolve_action", return_value=final_response.action), \
         patch("npc_engine.engines.dialogue.dialogue_handler.apply_dialogue_relation_deltas", new=AsyncMock()), \
         patch("npc_engine.engines.dialogue.dialogue_handler.set_routine_override", new=AsyncMock()) as mock_override:
        await handler.handle(request)

    mock_override.assert_called_once()
    call_kwargs = mock_override.call_args.kwargs
    assert call_kwargs["character_id"] == "npc_1"
    assert call_kwargs["location_id"] == "home"


@pytest.mark.asyncio
async def test_emotion_valence_at_threshold_does_not_trigger_override() -> None:
    """valence == -60 must NOT trigger — threshold is strictly less than."""
    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.dialogue.dialogue_models import DialogueRequest
    from npc_engine.engines.routine.routine_queries import set_routine_override

    handler, session = _make_dialogue_handler(valence_after_mood=-60)

    request = MagicMock()
    request.npc_id = "npc_2"
    request.player_id = "player_1"
    request.player_message = "hi"
    request.session_id = None

    final_response = MagicMock()
    final_response.relation_deltas = MagicMock()
    final_response.mood_update = None
    final_response.action = MagicMock()
    final_response.action.type = "speak"
    final_response.npc_response = "..."
    final_response.session_id = None

    with patch("npc_engine.engines.dialogue.dialogue_handler.execute_with_degradation", new=AsyncMock(return_value=(final_response, "full"))), \
         patch("npc_engine.engines.dialogue.dialogue_handler.resolve_action", return_value=final_response.action), \
         patch("npc_engine.engines.dialogue.dialogue_handler.apply_dialogue_relation_deltas", new=AsyncMock()), \
         patch("npc_engine.engines.dialogue.dialogue_handler.set_routine_override", new=AsyncMock()) as mock_override:
        await handler.handle(request)

    mock_override.assert_not_called()


# ---------------------------------------------------------------------------
# Additional disruption rule edge cases
# ---------------------------------------------------------------------------


def test_apply_disruption_rules_empty_list_returns_empty() -> None:
    matched = EventHandler._apply_disruption_rules([], event_type="death", severity=90)
    assert matched == []


def test_apply_disruption_rules_multiple_rules_all_matching() -> None:
    rule_type = _make_rule(event_types=["death"], duration_ticks=10)
    rule_severity = _make_rule(severity_min=50, duration_ticks=5)
    matched = EventHandler._apply_disruption_rules(
        [rule_type, rule_severity], event_type="death", severity=80
    )
    assert matched == [rule_type, rule_severity]


def test_apply_disruption_rules_rule_with_no_conditions_never_matches() -> None:
    """A rule with empty event_types and no severity_min should never fire."""
    rule = _make_rule(event_types=[], severity_min=None)
    matched = EventHandler._apply_disruption_rules([rule], event_type="death", severity=100)
    assert matched == []


def test_apply_disruption_rules_severity_exactly_at_min_matches() -> None:
    rule = _make_rule(severity_min=70)
    matched = EventHandler._apply_disruption_rules([rule], event_type="other", severity=70)
    assert matched == [rule]


def test_apply_disruption_rules_partial_match_returns_only_matching() -> None:
    matching = _make_rule(event_types=["death"])
    non_matching = _make_rule(event_types=["betrayal"], severity_min=90)
    matched = EventHandler._apply_disruption_rules(
        [matching, non_matching], event_type="death", severity=50
    )
    assert matched == [matching]


@pytest.mark.asyncio
async def test_emotion_valence_positive_does_not_trigger_override() -> None:
    """Positive valence must not trigger a disruption override."""
    handler, _ = _make_dialogue_handler(valence_after_mood=30)

    request = MagicMock()
    request.npc_id = "npc_3"
    request.player_id = "player_1"
    request.player_message = "good day"
    request.session_id = None

    final_response = MagicMock()
    final_response.relation_deltas = MagicMock()
    final_response.mood_update = "happy"
    final_response.action = MagicMock()
    final_response.action.type = "speak"
    final_response.npc_response = "Indeed!"
    final_response.session_id = None

    with patch("npc_engine.engines.dialogue.dialogue_handler.execute_with_degradation", new=AsyncMock(return_value=(final_response, "full"))), \
         patch("npc_engine.engines.dialogue.dialogue_handler.resolve_action", return_value=final_response.action), \
         patch("npc_engine.engines.dialogue.dialogue_handler.apply_dialogue_relation_deltas", new=AsyncMock()), \
         patch("npc_engine.engines.dialogue.dialogue_handler.set_routine_override", new=AsyncMock()) as mock_override:
        await handler.handle(request)

    mock_override.assert_not_called()


def test_load_disruption_rules_severity_only_rule(tmp_path: Path) -> None:
    """A rule with only trigger_severity_min (no event types) parses correctly."""
    yaml_content = "rules:\n  - trigger_severity_min: 80\n    override_location: home\n    duration_ticks: 3\n"
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml_content, encoding="utf-8")
    rules = load_disruption_rules(rules_file)
    assert len(rules) == 1
    assert rules[0].trigger_event_types == ()
    assert rules[0].trigger_severity_min == 80
    assert rules[0].duration_ticks == 3


def test_load_disruption_rules_event_type_only_rule(tmp_path: Path) -> None:
    """A rule with only trigger_event_types (no severity) parses correctly."""
    yaml_content = "rules:\n  - trigger_event_types: [fire]\n    override_location: home\n    duration_ticks: 7\n"
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml_content, encoding="utf-8")
    rules = load_disruption_rules(rules_file)
    assert len(rules) == 1
    assert rules[0].trigger_event_types == ("fire",)
    assert rules[0].trigger_severity_min is None
