"""Unit tests for ``scripts/demo_run_live.py`` (T2.4, DEC-280(a)).

``make check`` never boots the app, so the two Sprint-1 CRITICALs — the WebSocket slot leak
that killed the demo in ACT 6, and the military engine losing the game on tick 5 — passed
every gate. ``demo-run-live`` plays the real scripted demo against a live stack. These tests
pin its verdict logic with no I/O: every runner, client and health probe is faked.

* the act a failure landed in is named (so a RED run shows *where* the demo died);
* an empty dialogue reply is a failed required beat, not a quiet success;
* ACT 5 must leave its battle event in the events feed (the T1.2 live confirmation);
* a hang is a failure, not an eternal wait;
* no stack means exit 2 — a report the overnight loop logs, never a red gate.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import demo_run_live as live  # noqa: E402

from demo_game.runners.run_scenes import ClockTick, NarratorCue, StreamingDialogueBeat  # noqa: E402

BATTLE_EVENT: dict[str, Any] = {
    "event_id": "e1", "event_type": "military", "label": "Iron Legion forces were sighted",
    "severity": 85, "tick_id": 3, "location_id": "loc_guard_barracks", "src_character_id": "",
}


def _cue(text: str) -> NarratorCue:
    return NarratorCue(name=f"cue_{text[:6]}", text=text)


def _beat(name: str) -> StreamingDialogueBeat:
    return StreamingDialogueBeat(name=name, npc_id="mira_innkeeper", label="Mira", player_input="hi")


# ---------------------------------------------------------------------------
# ActTracker
# ---------------------------------------------------------------------------

def test_tracker_reads_act_numbers_from_both_cue_styles() -> None:
    tracker = live.ActTracker()
    tracker.observe(_cue("[ACT 6] Networked reputation."))
    assert tracker.current_act == 6
    tracker.observe(_cue("ACT 10 — Memory: The innkeeper recalls your history."))
    assert tracker.current_act == 10
    tracker.observe(ClockTick(name="t", delta_ticks=1))
    assert (tracker.current_act, tracker.last_scene) == (10, "t")


def test_tracker_ignores_narration_without_an_act_number() -> None:
    tracker = live.ActTracker()
    tracker.observe(_cue("[NARRATION] Clock advances."))
    assert tracker.current_act is None


def test_final_act_is_derived_from_the_real_scene_list() -> None:
    assert live.final_act_number() == 12


# ---------------------------------------------------------------------------
# Recording dialogue
# ---------------------------------------------------------------------------

def test_recording_cache_never_hits_and_records_each_reply() -> None:
    tracker = live.ActTracker()
    tracker.observe(_cue("[ACT 1] Gossip"))
    tracker.observe(_beat("beat_1_sorn"))
    cache = live.RecordingCache(tracker)
    assert cache.get("captain_sorn", "hello") is None
    cache.put("captain_sorn", "hello", {"npc_response": "The north burns."})
    assert cache.records == [live.DialogueRecord(act=1, beat="beat_1_sorn", text="The north burns.")]


def test_recording_cache_writes_nothing_to_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cache = live.RecordingCache(live.ActTracker())
    cache.put("npc", "hi", {"npc_response": "x"})
    assert list(tmp_path.iterdir()) == []


def test_rest_dialogue_wrapper_records_and_passes_the_response_through() -> None:
    class _Client:
        def post_dialogue(self, **kwargs: Any) -> dict[str, Any]:
            return {"npc_response": "", "echo": kwargs["npc_id"]}

    tracker = live.ActTracker()
    tracker.observe(_cue("[ACT 9] Anti-hallucination"))
    tracker.observe(_beat("beat_anti_hallucination"))
    records: list[live.DialogueRecord] = []
    client = _Client()
    live.record_rest_dialogue(client, tracker, records)
    assert client.post_dialogue(npc_id="aldric_merchant")["echo"] == "aldric_merchant"
    assert records == [live.DialogueRecord(act=9, beat="beat_anti_hallucination", text="")]


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------

def test_watchdog_reports_a_clean_run() -> None:
    assert live.run_with_watchdog(lambda: None, timeout_s=5) == live.RunOutcome()


def test_watchdog_captures_the_exception_that_killed_the_run() -> None:
    def _dies() -> None:
        raise RuntimeError("WS dialogue error for mira_innkeeper: HTTP 403")

    outcome = live.run_with_watchdog(_dies, timeout_s=5)
    assert outcome.timed_out is False
    assert outcome.error is not None and "HTTP 403" in outcome.error


def test_watchdog_turns_a_hang_into_a_timeout() -> None:
    outcome = live.run_with_watchdog(lambda: time.sleep(5), timeout_s=0.05)
    assert outcome.timed_out is True


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def _tracker_at(act: int, scene: str) -> live.ActTracker:
    tracker = live.ActTracker()
    tracker.observe(_cue(f"[ACT {act}] x"))
    tracker.observe(ClockTick(name=scene, delta_ticks=1))
    return tracker


def _good_records() -> list[live.DialogueRecord]:
    return [live.DialogueRecord(act=1, beat="beat_1_sorn", text="The north burns.")]


def test_verdict_passes_a_complete_run() -> None:
    verdict = live.build_verdict(
        _tracker_at(12, live.FINAL_SCENE_NAME), _good_records(), live.RunOutcome(), [BATTLE_EVENT]
    )
    assert verdict.ok is True
    assert verdict.reached_final_act is True
    assert verdict.died_in is None


def test_verdict_names_the_act_where_the_demo_died() -> None:
    outcome = live.RunOutcome(error="RuntimeError: WS dialogue error for mira_innkeeper")
    verdict = live.build_verdict(
        _tracker_at(6, "beat_6_mira_propagated"), _good_records(), outcome, [BATTLE_EVENT]
    )
    assert verdict.ok is False
    assert verdict.reached_final_act is False
    assert verdict.died_in is not None
    assert (verdict.died_in.act, verdict.died_in.scene) == (6, "beat_6_mira_propagated")
    assert "WS dialogue error" in verdict.died_in.reason


def test_verdict_fails_on_a_hang() -> None:
    verdict = live.build_verdict(
        _tracker_at(7, "beat_mira_corrected"), _good_records(), live.RunOutcome(timed_out=True), []
    )
    assert verdict.ok is False
    assert verdict.died_in is not None and verdict.died_in.reason == "timeout"


def test_verdict_fails_on_an_empty_dialogue_reply() -> None:
    records = [*_good_records(), live.DialogueRecord(act=3, beat="beat_5_lira", text="   ")]
    verdict = live.build_verdict(
        _tracker_at(12, live.FINAL_SCENE_NAME), records, live.RunOutcome(), [BATTLE_EVENT]
    )
    assert verdict.ok is False
    assert verdict.empty_beats == [live.EmptyBeat(act=3, beat="beat_5_lira")]


def test_verdict_fails_when_act5_left_no_battle_event() -> None:
    other = {**BATTLE_EVENT, "event_type": "fire", "location_id": "loc_market_square"}
    verdict = live.build_verdict(
        _tracker_at(12, live.FINAL_SCENE_NAME), _good_records(), live.RunOutcome(), [other]
    )
    assert verdict.ok is False
    assert verdict.act5_battle_event is False
    assert live.EmptyBeat(act=5, beat=live.ACT5_BEAT_NAME) in verdict.empty_beats


def test_summary_line_is_machine_readable() -> None:
    verdict = live.build_verdict(
        _tracker_at(6, "beat_6"), _good_records(), live.RunOutcome(error="boom"), []
    )
    assert live.summary_line(verdict) == (
        "DEMO_LIVE=FAIL acts_reached=6/12 empty_beats=1 act5_battle=no"
    )


# ---------------------------------------------------------------------------
# Health probe + main exit codes
# ---------------------------------------------------------------------------

def _health(version: str) -> httpx.Response:
    return httpx.Response(200, json={"data": {"status": "ok", "version": version}})


def test_probe_reports_up_when_health_answers() -> None:
    assert live.probe_health("http://x", None, lambda url: _health("abc")) == "up"


def test_probe_reports_unavailable_when_connection_refused() -> None:
    def _refused(url: str) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert live.probe_health("http://x", None, _refused) == "unavailable"


def test_probe_reports_stale_on_sha_mismatch() -> None:
    assert live.probe_health("http://x", "new1234", lambda url: _health("old9999")) == "stale"


def test_main_exits_2_without_touching_the_demo_when_no_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "probe_health", lambda *a, **k: "unavailable")

    def _must_not_run(*a: Any, **k: Any) -> Any:
        raise AssertionError("demo must not start without a stack")

    monkeypatch.setattr(live, "play_demo", _must_not_run)
    assert live.main(["--base-url", "http://x"]) == live.EXIT_STACK_UNAVAILABLE


def test_main_exits_1_on_a_failed_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "probe_health", lambda *a, **k: "up")
    failed = live.build_verdict(_tracker_at(6, "beat_6"), [], live.RunOutcome(error="boom"), [])
    monkeypatch.setattr(live, "play_demo", lambda timeout_s: failed)
    assert live.main(["--base-url", "http://x"]) == live.EXIT_DEMO_BROKEN


def test_main_exits_0_on_a_passing_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "probe_health", lambda *a, **k: "up")
    passed = live.build_verdict(
        _tracker_at(12, live.FINAL_SCENE_NAME), _good_records(), live.RunOutcome(), [BATTLE_EVENT]
    )
    monkeypatch.setattr(live, "play_demo", lambda timeout_s: passed)
    assert live.main(["--base-url", "http://x"]) == live.EXIT_PASS
