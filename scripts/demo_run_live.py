"""
Module: demo_run_live
Layer: harness
Purpose: Play the scripted demo (demo_game/runners/run.py SCENES) through REAL API calls
    against a running stack and judge the run: did it reach the final act, and did any act
    produce an empty required beat. A nightly report, never a `make check` gate (T2.4,
    DEC-280(a), Finding R6-04).
Does NOT: boot, seed or reset a stack (`make eval-stack-up` / `eval-stack-seed` /
    `eval-stack-reset` do that); drive scenes itself — it reuses DemoRunner via its
    `cache` and `on_scene` hooks, so there is exactly one demo driver.
Dependencies: demo_game.runners.run (DemoRunner, SCENES, LLMCache), httpx.
Used by: `make demo-run-live`, scripts/expand_loop.sh (post-run report).

Required beats:
    * every dialogue reply (WebSocket streaming beats and REST beats) is non-empty;
    * ACT 5's forced event tick leaves a military battle event at the barracks in the
      events feed (the live confirmation T1.2 was waiting for).
    Info/skip displays (quest, emotion, proactive, player-model) are not required.

The LLM cache is replaced by an in-memory recorder that never hits, so every beat goes
live — a warm `.cache/demo` would otherwise skip the WebSocket and hide a slot leak.

Exit codes:
    0  PASS — final act reached, no empty required beat
    1  FAIL — the demo died, hung, or a required beat was empty
    2  the stack is unavailable, or its /health SHA does not match --expect-sha
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import httpx
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from demo_game.encoding_utils import ensure_utf8_stdout  # noqa: E402
from demo_game.runners.run import SCENES, DemoRunner, LLMCache  # noqa: E402
from demo_game.runners.run_scenes import NarratorCue, Scene  # noqa: E402

EXIT_PASS = 0
EXIT_DEMO_BROKEN = 1
EXIT_STACK_UNAVAILABLE = 2

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT_S = 1800.0
HEALTH_TIMEOUT_S = 5.0
EVENT_FEED_LIMIT = 100

FINAL_SCENE_NAME = "outro"
ACT5 = 5
ACT5_BEAT_NAME = "military_tick"
BATTLE_EVENT_TYPE = "military"
BATTLE_LOCATION_ID = "loc_guard_barracks"
RESPONSE_KEY = "npc_response"
ACT_RE = re.compile(r"\bACT (\d+)\b")

StackStatus = Literal["up", "unavailable", "stale"]
HttpGet = Callable[[str], httpx.Response]


class DialogueRecord(BaseModel):
    """One NPC reply observed during the run, tagged with the act and scene it came from."""

    model_config = ConfigDict(frozen=True)
    act: int | None
    beat: str | None
    text: str


class EmptyBeat(BaseModel):
    """A required beat that produced nothing."""

    model_config = ConfigDict(frozen=True)
    act: int | None
    beat: str | None


class DiedIn(BaseModel):
    """Where and why the run stopped before its final scene."""

    model_config = ConfigDict(frozen=True)
    act: int | None
    scene: str | None
    reason: str


class RunOutcome(BaseModel):
    """How DemoRunner.run ended: cleanly, with an exception, or by hanging past the timeout."""

    model_config = ConfigDict(frozen=True)
    error: str | None = None
    timed_out: bool = False


class LiveDemoVerdict(BaseModel):
    """The judged result of one live demo run."""

    model_config = ConfigDict(frozen=True)
    reached_final_act: bool
    acts_reached: int
    final_act: int
    died_in: DiedIn | None
    empty_beats: list[EmptyBeat]
    act5_battle_event: bool
    dialogue_beats: int

    @property
    def ok(self) -> bool:
        """True when the run completed and every required beat had content."""
        return self.reached_final_act and not self.empty_beats


class ActTracker:
    """`on_scene` observer: remembers the current act and the last scene started.

    Written from the runner thread and read by the main thread only after the run ends or
    times out; single attribute assignments, so no lock is needed.
    """

    def __init__(self) -> None:
        self.current_act: int | None = None
        self.last_scene: str | None = None

    def observe(self, scene: Scene) -> None:
        """Record that `scene` is about to execute."""
        self.last_scene = scene.name
        if isinstance(scene, NarratorCue):
            match = ACT_RE.search(scene.text)
            if match:
                self.current_act = int(match.group(1))


class RecordingCache(LLMCache):
    """An LLMCache that never hits and records every reply in memory (no disk writes)."""

    def __init__(self, tracker: ActTracker) -> None:  # noqa: D107 — deliberately skips mkdir
        self.readonly = False
        self.tracker = tracker
        self.records: list[DialogueRecord] = []

    def get(self, npc_id: str, player_input: str) -> dict[str, Any] | None:
        """Always miss, so every dialogue beat goes through the live API."""
        return None

    def put(self, npc_id: str, player_input: str, response: dict[str, Any]) -> None:
        """Record the reply against the current act and scene."""
        self.records.append(_record(self.tracker, response))


def _record(tracker: ActTracker, response: dict[str, Any]) -> DialogueRecord:
    text = str(response.get(RESPONSE_KEY) or "")
    return DialogueRecord(act=tracker.current_act, beat=tracker.last_scene, text=text)


def record_rest_dialogue(client: Any, tracker: ActTracker, records: list[DialogueRecord]) -> None:
    """Wrap `client.post_dialogue` on this instance so REST dialogue beats are recorded too.

    Args:
        client: The runner's EngineClient (only this instance is patched).
        tracker: Supplies the act/scene tag for each reply.
        records: Shared list the replies are appended to.
    """
    original = client.post_dialogue

    def _recording(*args: Any, **kwargs: Any) -> dict[str, Any]:
        response = original(*args, **kwargs)
        records.append(_record(tracker, response))
        return response

    client.post_dialogue = _recording


def run_with_watchdog(target: Callable[[], None], timeout_s: float) -> RunOutcome:
    """Run `target` in a daemon thread; a hang past `timeout_s` becomes a timeout outcome.

    The demo's WebSocket worker can block forever on a recv timeout, so the nightly must
    not wait on it unbounded. The daemon thread is abandoned on timeout; the process exits.
    """
    errors: list[str] = []

    def _body() -> None:
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 — reported as the run's failure reason
            errors.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=_body, name="demo-run-live", daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        return RunOutcome(timed_out=True)
    return RunOutcome(error=errors[0] if errors else None)


def final_act_number(scenes: Sequence[Scene] = SCENES) -> int:
    """Return the highest act number named by a narrator cue in the scene list."""
    acts = [int(m.group(1)) for s in scenes if isinstance(s, NarratorCue) for m in ACT_RE.finditer(s.text)]
    return max(acts)


def is_act5_battle_event(event: dict[str, Any]) -> bool:
    """True for the military event ACT 5's forced evt_21 tick creates at the barracks."""
    return event.get("event_type") == BATTLE_EVENT_TYPE and event.get("location_id") == BATTLE_LOCATION_ID


def _died_in(tracker: ActTracker, outcome: RunOutcome) -> DiedIn | None:
    if outcome.timed_out:
        return DiedIn(act=tracker.current_act, scene=tracker.last_scene, reason="timeout")
    if outcome.error is not None:
        return DiedIn(act=tracker.current_act, scene=tracker.last_scene, reason=outcome.error)
    if tracker.last_scene != FINAL_SCENE_NAME:
        return DiedIn(act=tracker.current_act, scene=tracker.last_scene, reason="stopped early")
    return None


def build_verdict(
    tracker: ActTracker,
    records: Sequence[DialogueRecord],
    outcome: RunOutcome,
    events: Sequence[dict[str, Any]],
) -> LiveDemoVerdict:
    """Judge a finished (or dead) run.

    Args:
        tracker: Where the run got to.
        records: Every dialogue reply observed.
        outcome: How the run ended.
        events: The events feed read after the run.
    Returns:
        The verdict; `ok` is False on any death, hang, or empty required beat.
    """
    empty = [EmptyBeat(act=r.act, beat=r.beat) for r in records if not r.text.strip()]
    battle = any(is_act5_battle_event(e) for e in events)
    if not battle:
        empty.append(EmptyBeat(act=ACT5, beat=ACT5_BEAT_NAME))
    died = _died_in(tracker, outcome)
    return LiveDemoVerdict(
        reached_final_act=died is None,
        acts_reached=tracker.current_act or 0,
        final_act=final_act_number(),
        died_in=died,
        empty_beats=empty,
        act5_battle_event=battle,
        dialogue_beats=len(records),
    )


def summary_line(verdict: LiveDemoVerdict) -> str:
    """The one-line result the overnight loop tails."""
    status = "PASS" if verdict.ok else "FAIL"
    return (
        f"DEMO_LIVE={status} acts_reached={verdict.acts_reached}/{verdict.final_act} "
        f"empty_beats={len(verdict.empty_beats)} act5_battle={'yes' if verdict.act5_battle_event else 'no'}"
    )


def probe_health(base_url: str, expect_sha: str | None, http_get: HttpGet) -> StackStatus:
    """Classify the stack at `base_url` as up, unavailable, or running a stale image."""
    try:
        resp = http_get(f"{base_url.rstrip('/')}/health")
    except httpx.HTTPError:
        return "unavailable"
    if resp.status_code != httpx.codes.OK:
        return "unavailable"
    version = str(resp.json().get("data", {}).get("version", ""))
    if expect_sha and version != expect_sha:
        return "stale"
    return "up"


def _read_events(runner: DemoRunner) -> list[dict[str, Any]]:
    try:
        return runner.client.get_recent_events(limit=EVENT_FEED_LIMIT)
    except Exception as exc:  # noqa: BLE001 — a dead stack after the run is reported, not raised
        print(f"[demo-run-live] events feed unreadable after run: {exc}", file=sys.stderr)
        return []


def play_demo(timeout_s: float) -> LiveDemoVerdict:
    """Run the real SCENES live through DemoRunner and judge the result."""
    tracker = ActTracker()
    cache = RecordingCache(tracker)
    runner = DemoRunner(cache=cache)
    rest_records: list[DialogueRecord] = []
    record_rest_dialogue(runner.client, tracker, rest_records)
    outcome = run_with_watchdog(lambda: runner.run(on_scene=tracker.observe), timeout_s)
    events = _read_events(runner)
    return build_verdict(tracker, [*cache.records, *rest_records], outcome, events)


def _print_report(verdict: LiveDemoVerdict) -> None:
    print("\n[demo-run-live] ---------------- verdict ----------------")
    print(f"  reached final act : {verdict.reached_final_act}")
    if verdict.died_in is not None:
        d = verdict.died_in
        print(f"  died in           : ACT {d.act} scene={d.scene} reason={d.reason}")
    print(f"  dialogue beats    : {verdict.dialogue_beats}")
    for beat in verdict.empty_beats:
        print(f"  EMPTY beat        : ACT {beat.act} {beat.beat}")
    print(f"  ACT 5 battle event: {'yes' if verdict.act5_battle_event else 'no'}")
    print(summary_line(verdict))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play the scripted demo against a live stack.")
    parser.add_argument("--base-url", default=os.environ.get("NPC_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--expect-sha", default=None, help="Fail with exit 2 if /health reports another SHA.")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Probe the stack, play the demo, print the verdict, return the exit code."""
    ensure_utf8_stdout()
    args = _parse_args(argv)
    status = probe_health(args.base_url, args.expect_sha, lambda url: httpx.get(url, timeout=HEALTH_TIMEOUT_S))
    if status != "up":
        label = "STACK_UNAVAILABLE" if status == "unavailable" else "STALE_IMAGE"
        print(f"DEMO_LIVE={label} base_url={args.base_url}")
        return EXIT_STACK_UNAVAILABLE
    os.environ["NPC_BASE_URL"] = args.base_url
    verdict = play_demo(args.timeout_s)
    _print_report(verdict)
    return EXIT_PASS if verdict.ok else EXIT_DEMO_BROKEN


if __name__ == "__main__":
    raise SystemExit(main())
