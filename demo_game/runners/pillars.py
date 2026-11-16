"""
Module: pillars
Layer: demo_game (runners)
Purpose: Read a JSONL transcript and return one verdict per pillar (FEEL, REMEMBER,
         GOSSIP, WORLD, DETERMINISM). Entry point for `make demo-run-live`. Drives the
         demo via DemoRunner with TranscriptRecorder, makes pillar-specific reads,
         writes evals/pillar_verdicts.jsonl, and prints the DEMO_LIVE= status line.
Dependencies: demo_game.runners.run (DemoRunner, SCENES), demo_game.runners.transcript
              (TranscriptRecorder), httpx, pydantic
Used by: Makefile (demo-run-live), demo_game.tests.runners.test_pillars
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

import httpx
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from demo_game.encoding_utils import ensure_utf8_stdout  # noqa: E402

# ---------------------------------------------------------------------------
# Pillar identifiers
# ---------------------------------------------------------------------------

PILLAR_FEEL = "FEEL"
PILLAR_REMEMBER = "REMEMBER"
PILLAR_GOSSIP = "GOSSIP"
PILLAR_WORLD = "WORLD"
PILLAR_DETERMINISM = "DETERMINISM"

ALL_PILLARS: tuple[str, ...] = (
    PILLAR_FEEL,
    PILLAR_REMEMBER,
    PILLAR_GOSSIP,
    PILLAR_WORLD,
    PILLAR_DETERMINISM,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEEL_NPC_ID: str = "aldric_merchant"
REMEMBER_NPC_ID: str = "mira_innkeeper"
REMEMBER_PLAYER_ID: str = "player_demo"

_MARK = "MARK"  # transcript method of the phase markers main() records
_WORLD_STATE_PATH = "/graph/nodes/world_state/"
_KNOWS_ABOUT_LIST = "/graph/edges/KNOWS_ABOUT"
_LOCATED_AT_LIST = "/graph/edges/LOCATED_AT"
_DELTA_KEYS: tuple[str, ...] = ("trust", "fear", "affection")
_NOT_NPC_SOURCES: frozenset[object] = frozenset({None, "", "player", REMEMBER_PLAYER_ID})
_EDGE_PAGE: int = 200  # the API's MAX_LIMIT

DEFAULT_BASE_URL: str = "http://localhost:8001"
HEALTH_TIMEOUT_S: float = 5.0
DEMO_TIMEOUT_S: float = 1800.0
VERDICTS_PATH: str = "evals/pillar_verdicts.jsonl"

BASELINE_DONE: str = "pillars:baseline_done"
DEMO_DONE: str = "pillars:demo_done"

EXIT_OK: int = 0
EXIT_HARNESS_ERROR: int = 1
EXIT_STACK_UNAVAILABLE: int = 2

# Seeded NPC locations — from demo_game.seeds.seed_world_data._NPC_LOCATED_AT
SEEDED_NPC_LOCATIONS: dict[str, str] = {
    "mira_innkeeper": "loc_tavern",
    "lira_fence": "loc_tavern",
    "aldric_merchant": "loc_market_square",
    "old_henryk": "loc_market_square",
    "captain_sorn": "loc_guard_barracks",
    "sera_barmaid": "loc_tavern",
    "harwick_guard": "loc_guard_barracks",
    "nel_pickpocket": "loc_tavern",
}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class PillarVerdict(BaseModel):
    """One pillar's assertion result from a single run."""

    model_config = ConfigDict(frozen=True)

    pillar: str
    verdict: str  # "green" | "red"
    repeats: int
    evidence: str
    sha: str = ""


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

TranscriptEntry = dict[str, Any]


def _entries_matching(
    entries: list[TranscriptEntry],
    method: str,
    path_fragment: str,
) -> list[TranscriptEntry]:
    """Return entries whose method and path both match."""
    return [
        e for e in entries
        if e.get("method") == method and path_fragment in e.get("path", "")
    ]


# ---------------------------------------------------------------------------
# Pillar checks — pure functions over transcript entries
# ---------------------------------------------------------------------------


def _phases(
    entries: list[TranscriptEntry],
) -> tuple[list[TranscriptEntry], list[TranscriptEntry]]:
    """Split a transcript at main()'s markers into (baseline, after) entries.

    Without both markers there is no baseline, so every baseline comparison is red.
    """
    marks = [i for i, e in enumerate(entries) if e.get("method") == _MARK]
    if len(marks) < 2:
        return [], []
    return entries[: marks[0]], entries[marks[1] + 1:]


def _payload(entry: TranscriptEntry) -> Any:
    """Return a response body's ``data`` envelope content, or the body itself."""
    body = entry.get("body")
    return body.get("data", body) if isinstance(body, dict) else body


def _list_reads(entries: list[TranscriptEntry], path_suffix: str) -> list[dict[str, Any]]:
    """Union of the dict rows returned by every GET list read whose path ends with *path_suffix*."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("method") == "GET" and entry.get("path", "").endswith(path_suffix):
            rows.extend(row for row in _payload(entry) or [] if isinstance(row, dict))
    return rows


def check_feel(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """FEEL: the witness's emotion differs across the last world-state event (T25.9).

    Compares the last emotion read before the final world_state PATCH (the market
    fire) with the first read after it: a shock lowers valence and raises arousal.
    "Non-neutral" alone passed a seeded mood that the event never touched.
    """
    emotion = f"/npc/{FEEL_NPC_ID}/emotion"
    fires = [i for i, e in enumerate(entries) if e.get("method") == "PATCH" and _WORLD_STATE_PATH in e.get("path", "")]
    if not fires:
        return False, "no world_state PATCH (event) in transcript"
    before = _entries_matching(entries[: fires[-1]], "GET", emotion)
    after = _entries_matching(entries[fires[-1] + 1:], "GET", emotion)
    if not before or not after:
        return False, f"need {FEEL_NPC_ID} emotion reads around the event (before={len(before)}, after={len(after)})"
    b, a = _payload(before[-1]), _payload(after[0])
    old, new = (b.get("valence"), b.get("arousal")), (a.get("valence"), a.get("arousal"))
    shocked = (new[0] or 0) < (old[0] or 0) and (new[1] or 0) > (old[1] or 0)
    return shocked, f"{FEEL_NPC_ID} valence/arousal {old[0]}/{old[1]} -> {new[0]}/{new[1]}"


def _deltas(entry: TranscriptEntry) -> tuple[int, ...]:
    """trust/fear/affection from a relationship read; a 404 (no edge yet) is 0/0/0."""
    if entry.get("status") == 404:
        return (0, 0, 0)
    data = _payload(entry) or {}
    return tuple(int(data.get(key) or 0) for key in _DELTA_KEYS)


def check_remember(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """REMEMBER: dialogue moves trust, fear or affection, and consolidation creates a Memory.

    interaction_count rises on every turn whatever the deltas, so it proves nothing (T25.9).
    """
    rel_path = f"/npc/{REMEMBER_NPC_ID}/relationship/{REMEMBER_PLAYER_ID}"
    baseline, after = _phases(entries)
    base_reads = _entries_matching(baseline, "GET", rel_path)
    after_reads = _entries_matching(after, "GET", rel_path)
    if not base_reads or not after_reads:
        delta_ok, delta_ev = False, f"need baseline and after reads (baseline={len(base_reads)}, after={len(after_reads)})"
    else:
        old, new = _deltas(base_reads[-1]), _deltas(after_reads[-1])
        delta_ok, delta_ev = old != new, f"trust/fear/affection {old} -> {new}"
    mem_entries = _entries_matching(entries, "POST", f"/memories/consolidate/{REMEMBER_NPC_ID}")
    memory_id = (_payload(mem_entries[-1]) or {}).get("memory_id") if mem_entries else None
    return delta_ok and memory_id is not None, f"delta: {delta_ev}; memory: memory_id={memory_id!r}"


def check_gossip(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """GOSSIP: the engine propagated a new hop, and its distortion compounds (T25.9).

    The demo seeds a Sorn→Mira→Henryk chain (DEC-006), so reading it proves the seed,
    not the engine.  A hop is a KNOWS_ABOUT edge absent at baseline whose source is an
    NPC; it compounds when its source was already distorted (above 0) and the hop is at
    least as distorted.  Over a level-0 source, any hop shows fresh distortion only.
    """
    baseline, after = _phases(entries)
    before, now = _list_reads(baseline, _KNOWS_ABOUT_LIST), _list_reads(after, _KNOWS_ABOUT_LIST)
    if not now:
        return False, "no KNOWS_ABOUT list read after the run"
    known = {(e.get("src_id"), e.get("dst_id")) for e in before}
    level = {(e.get("src_id"), e.get("dst_id")): int(e.get("distortion_level") or 0) for e in now}
    hops = [
        e for e in now
        if (e.get("src_id"), e.get("dst_id")) not in known and e.get("source_character_id") not in _NOT_NPC_SOURCES
    ]
    compounding = [
        e for e in hops
        if int(e.get("distortion_level") or 0) >= level.get((e.get("source_character_id"), e.get("dst_id")), 0) > 0
    ]
    if not compounding:
        return False, f"{len(hops)} engine hop(s), none over a distorted source (>0) at >= its level (baseline edges {len(before)})"
    hop = compounding[0]
    source_level = level.get((hop.get("source_character_id"), hop.get("dst_id")), 0)
    return True, (
        f"{len(hops)} engine hop(s); e.g. {hop.get('source_character_id')}->{hop.get('src_id')} on "
        f"{hop.get('dst_id')} at {hop.get('distortion_level')} >= source {source_level}"
    )


def _locations(entries: list[TranscriptEntry]) -> dict[str, tuple[str, int]]:
    """npc_id -> (location_id, arrived_at_tick) from LOCATED_AT list reads; last read wins."""
    return {
        str(edge.get("src_id")): (str(edge.get("dst_id")), int(edge.get("arrived_at_tick") or 0))
        for edge in _list_reads(entries, _LOCATED_AT_LIST)
    }


def check_world(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """WORLD: every NPC starts where seeded; a later move carries a real arrival tick (T25.9).

    Owner, 2026-11-16: NPCs may move as the demo runs.  ISSUE-373's bug was every NPC
    snapping to one location with arrived_at_tick 0, so that is what goes red.  Like
    every baseline check, it assumes a freshly seeded stack (make eval-stack-seed).
    """
    baseline, after = _phases(entries)
    start, end = _locations(baseline), _locations(after)
    off_seed = [f"{n}@{start.get(n, ('',))[0]!r}" for n, loc in SEEDED_NPC_LOCATIONS.items() if start.get(n, ('',))[0] != loc]
    if off_seed:
        return False, f"not at seeded start: {off_seed}"
    missing = [n for n in SEEDED_NPC_LOCATIONS if n not in end]
    if missing:
        return False, f"missing_reads={missing}"
    moved = {n: end[n] for n, loc in SEEDED_NPC_LOCATIONS.items() if end[n][0] != loc}
    untimed = [f"{n}@{loc!r}" for n, (loc, tick) in moved.items() if tick <= 0]
    if untimed:
        return False, f"moved with arrived_at_tick 0: {untimed}"
    if len({end[n][0] for n in SEEDED_NPC_LOCATIONS}) == 1:
        return False, f"every NPC at one location: {end[next(iter(SEEDED_NPC_LOCATIONS))][0]!r}"
    return True, f"all {len(SEEDED_NPC_LOCATIONS)} started where seeded; moved with an arrival tick: {sorted(moved)}"


def check_determinism(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """DETERMINISM: two gossip tick results have non-empty and equal seeds_used dicts.

    A vacuous {} == {} is explicitly red.

    Args:
        entries: Transcript entry list to scan.

    Returns:
        (passed, evidence_string).
    """
    tick_entries = _entries_matching(entries, "POST", "/admin/batch/gossip_tick")
    if len(tick_entries) < 2:
        return False, f"need 2 gossip_tick entries, found {len(tick_entries)}"

    def _seeds(entry: TranscriptEntry) -> dict:
        body = entry.get("body", {})
        return (body.get("data") or body).get("seeds_used", {})

    seeds1 = _seeds(tick_entries[0])
    seeds2 = _seeds(tick_entries[1])
    if not seeds1 or not seeds2:
        return False, f"seeds_used is empty: run1={seeds1!r} run2={seeds2!r}"
    if seeds1 != seeds2:
        return False, f"seeds differ: run1_keys={sorted(seeds1)!r} run2_keys={sorted(seeds2)!r}"
    return True, f"seeds match ({len(seeds1)} pairs)"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def judge_pillars(
    entries: list[TranscriptEntry],
    sha: str = "",
) -> list[PillarVerdict]:
    """Run all pillar checks against *entries* and return one verdict per pillar.

    Args:
        entries: Transcript entry list from TranscriptRecorder.entries.
        sha: Commit SHA to stamp on every verdict (from /health).

    Returns:
        List of PillarVerdict in ALL_PILLARS order.
    """
    checks: list[tuple[str, Any, int]] = [
        (PILLAR_FEEL, check_feel, 1),
        (PILLAR_REMEMBER, check_remember, 1),
        (PILLAR_GOSSIP, check_gossip, 1),
        (PILLAR_WORLD, check_world, 1),
        (PILLAR_DETERMINISM, check_determinism, 1),
    ]
    verdicts: list[PillarVerdict] = []
    for pillar, check_fn, repeats in checks:
        ok, evidence = check_fn(entries)
        verdicts.append(
            PillarVerdict(
                pillar=pillar,
                verdict="green" if ok else "red",
                repeats=repeats,
                evidence=evidence,
                sha=sha,
            )
        )
    return verdicts


# ---------------------------------------------------------------------------
# Live-run helpers
# ---------------------------------------------------------------------------


def _probe_health(base_url: str) -> tuple[str, str]:
    """Return (status, sha) where status is 'up', 'unavailable', or 'stale'.

    Args:
        base_url: Base URL of the NPC engine stack.

    Returns:
        (status_str, sha_str).
    """
    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/health",
            timeout=HEALTH_TIMEOUT_S,
        )
    except httpx.HTTPError:
        return "unavailable", ""
    if resp.status_code != 200:
        return "unavailable", ""
    sha = str(resp.json().get("data", {}).get("version", ""))
    return "up", sha


def _run_demo_with_recorder(recorder: Any) -> str | None:
    """Drive DemoRunner in a daemon thread; return error string or None on success."""
    from demo_game.runners.run import DemoRunner, LLMCache

    errors: list[str] = []

    def _body() -> None:
        try:
            DemoRunner(recorder=recorder, cache=LLMCache(enabled=False)).run()
        except BaseException as exc:  # noqa: BLE001 — captured as error string
            errors.append(f"{type(exc).__name__}: {exc}")

    t = threading.Thread(target=_body, name="pillars-demo-run", daemon=True)
    t.start()
    t.join(DEMO_TIMEOUT_S)
    if t.is_alive():
        return "demo run timed out"
    return errors[0] if errors else None


def _make_state_reads(client: Any) -> None:
    """Read the state every pillar compares; called before and after the demo (T25.9).

    The client's httpx client is wrapped with RecordingClientWrapper, so each read lands
    in the transcript.  Re-reading one static graph value N times was not N-of-M evidence,
    so each value is read once per phase (DEC-331).

    Args:
        client: EngineClient whose _client is wrapped with RecordingClientWrapper.
    """
    for offset in range(0, 10 * _EDGE_PAGE, _EDGE_PAGE):
        if len(client.get_graph_edges("KNOWS_ABOUT", limit=_EDGE_PAGE, offset=offset)) < _EDGE_PAGE:
            break
    for npc_id in SEEDED_NPC_LOCATIONS:
        client.get_graph_edges("LOCATED_AT", src_id=npc_id)
    client.get_npc_emotion(FEEL_NPC_ID)
    client.get_npc_relationship(REMEMBER_NPC_ID, REMEMBER_PLAYER_ID)


def _write_verdicts(verdicts: list[PillarVerdict], path: str) -> None:
    """Append verdicts as JSONL to *path* (creates parent dirs as needed).

    Args:
        verdicts: List of PillarVerdict objects.
        path: Destination JSONL file path.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for v in verdicts:
            fh.write(json.dumps(v.model_dump()) + "\n")


def _print_report(verdicts: list[PillarVerdict]) -> None:
    """Print a human-readable verdict table to stdout."""
    print("\n[pillars] --------------- verdict ---------------")
    for v in verdicts:
        icon = "GREEN" if v.verdict == "green" else "RED  "
        print(f"  {icon}  {v.pillar:<14} {v.evidence}")
    all_green = all(v.verdict == "green" for v in verdicts)
    print(f"DEMO_LIVE={'PASS' if all_green else 'FAIL'}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pillar assertions against the demo stack."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NPC_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--verdicts-path",
        default=VERDICTS_PATH,
        help="JSONL output file for pillar verdicts.",
    )
    parser.add_argument(
        "--expect-sha",
        default="",
        help="Commit the stack must report on /health; a mismatch is a stale image (expand_loop.sh).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Probe the stack, read baseline state, drive the demo, read again, judge, write verdicts.

    Returns:
        EXIT_OK (0) when the demo ran to the end (even when pillars are red).
        EXIT_STACK_UNAVAILABLE (2) when the stack is unreachable or reports another commit.
        EXIT_HARNESS_ERROR (1) when the demo raised or timed out; verdicts are still written.
    """
    ensure_utf8_stdout()
    args = _parse_args(argv)

    status, sha = _probe_health(args.base_url)
    if status != "up":
        print(f"DEMO_LIVE=STACK_UNAVAILABLE base_url={args.base_url}")
        return EXIT_STACK_UNAVAILABLE
    if args.expect_sha and not (sha and (sha.startswith(args.expect_sha) or args.expect_sha.startswith(sha))):
        print(f"DEMO_LIVE=STACK_UNAVAILABLE reason=stale-image stack={sha!r} expected={args.expect_sha!r}")
        return EXIT_STACK_UNAVAILABLE

    os.environ["NPC_BASE_URL"] = args.base_url

    from demo_game.runners.transcript import TranscriptRecorder
    from demo_game.runners.run import DemoRunner

    recorder = TranscriptRecorder()
    client = DemoRunner(recorder=recorder).client
    _make_state_reads(client)
    recorder.record(method=_MARK, path=BASELINE_DONE, status=0, body=None)
    error = _run_demo_with_recorder(recorder)
    recorder.record(method=_MARK, path=DEMO_DONE, status=0, body=None)
    if error:
        print(f"[pillars] demo harness error: {error}", file=sys.stderr)
    _make_state_reads(client)

    verdicts = judge_pillars(recorder.entries, sha=sha)
    _write_verdicts(verdicts, args.verdicts_path)
    _print_report(verdicts)
    return EXIT_HARNESS_ERROR if error else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
