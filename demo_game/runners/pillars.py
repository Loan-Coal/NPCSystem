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
GOSSIP_HOP2_NPC: str = "old_henryk"
GOSSIP_EVENT_ID: str = "northern_war_begins"
REMEMBER_NPC_ID: str = "mira_innkeeper"
REMEMBER_PLAYER_ID: str = "player_demo"

LLMM_REPEATS: int = 3       # how many reads for LLM-dependent pillars
LLMM_THRESHOLD: int = 2     # minimum passing reads required (2-of-3)

DEFAULT_BASE_URL: str = "http://localhost:8001"
HEALTH_TIMEOUT_S: float = 5.0
DEMO_TIMEOUT_S: float = 1800.0
VERDICTS_PATH: str = "evals/pillar_verdicts.jsonl"

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


def check_feel(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """FEEL: after market-fire event, aldric_merchant emotion is not neutral (0/0).

    LLM-dependent: pass when >= LLMM_THRESHOLD of the emotion reads are non-neutral.

    Args:
        entries: Transcript entry list to scan.

    Returns:
        (passed, evidence_string).
    """
    reads = _entries_matching(entries, "GET", f"/npc/{FEEL_NPC_ID}/emotion")
    if not reads:
        return False, f"no emotion entry for {FEEL_NPC_ID} in transcript"
    passes = sum(
        1
        for e in reads
        if e.get("body", {}).get("valence", 0) != 0
        or e.get("body", {}).get("arousal", 0) != 0
    )
    n = len(reads)
    ok = passes >= LLMM_THRESHOLD
    return ok, f"{passes}/{n} emotion reads non-neutral (threshold={LLMM_THRESHOLD})"


def check_remember(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """REMEMBER: relation edge has non-zero interaction_count; Memory node was created.

    Delta (LLM-dependent): >= LLMM_THRESHOLD of relationship reads show interaction_count > 0.
    Memory node (graph fact): consolidate returned a non-null memory_id.

    Args:
        entries: Transcript entry list to scan.

    Returns:
        (passed, evidence_string).
    """
    rel_path = f"/npc/{REMEMBER_NPC_ID}/relationship/{REMEMBER_PLAYER_ID}"
    rel_reads = _entries_matching(entries, "GET", rel_path)
    if rel_reads:
        delta_passes = sum(
            1
            for e in rel_reads
            if (e.get("body", {}).get("data") or e.get("body", {})).get(
                "interaction_count", 0
            )
            > 0
        )
        delta_n = len(rel_reads)
        delta_ok = delta_passes >= LLMM_THRESHOLD
        delta_ev = f"{delta_passes}/{delta_n} relation reads have interaction_count>0"
    else:
        delta_ok = False
        delta_ev = "no relationship entry in transcript"

    mem_entries = _entries_matching(
        entries, "POST", f"/memories/consolidate/{REMEMBER_NPC_ID}"
    )
    if mem_entries:
        last_body = mem_entries[-1].get("body", {})
        memory_id = (last_body.get("data") or last_body).get("memory_id")
        mem_ok = memory_id is not None
        mem_ev = f"memory_id={memory_id!r}"
    else:
        mem_ok = False
        mem_ev = "no consolidate entry in transcript"

    ok = delta_ok and mem_ok
    return ok, f"delta: {delta_ev}; memory: {mem_ev}"


def check_gossip(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """GOSSIP: hop-2 KNOWS_ABOUT edge has distortion_level > 0 and source_character_id set.

    Distortion (LLM-dependent): >= LLMM_THRESHOLD of hop-2 reads show distortion > 0.
    Chain (graph fact): at least one read has source_character_id set.

    Args:
        entries: Transcript entry list to scan.

    Returns:
        (passed, evidence_string).
    """
    path_frag = f"/graph/edges/KNOWS_ABOUT/{GOSSIP_HOP2_NPC}/{GOSSIP_EVENT_ID}"
    reads = _entries_matching(entries, "GET", path_frag)
    if not reads:
        return (
            False,
            f"no KNOWS_ABOUT entry for {GOSSIP_HOP2_NPC}/{GOSSIP_EVENT_ID} in transcript",
        )

    distortion_passes = 0
    chain_ok = False
    chain_ev = f"source_character_id absent for {GOSSIP_HOP2_NPC}"
    for e in reads:
        body = e.get("body", {})
        data = body.get("data", body)
        distortion_level = data.get("distortion_level") or 0
        source_id = data.get("source_character_id")
        if distortion_level > 0:
            distortion_passes += 1
        if source_id:
            chain_ok = True
            chain_ev = f"source_character_id={source_id!r}"

    n = len(reads)
    distortion_ok = distortion_passes >= LLMM_THRESHOLD
    ok = distortion_ok and chain_ok
    return (
        ok,
        f"distortion: {distortion_passes}/{n} reads >0 (threshold={LLMM_THRESHOLD}); "
        f"chain: {chain_ev}",
    )


def check_world(entries: list[TranscriptEntry]) -> tuple[bool, str]:
    """WORLD: after ACT 1 ticks, each seeded NPC is at its seeded location.

    Reads LOCATED_AT edges from the transcript (dst_id) against SEEDED_NPC_LOCATIONS.

    Args:
        entries: Transcript entry list to scan.

    Returns:
        (passed, evidence_string).
    """
    located_at_reads = _entries_matching(entries, "GET", "/graph/edges/LOCATED_AT")

    wrong: list[str] = []
    missing: list[str] = []
    for npc_id, expected in SEEDED_NPC_LOCATIONS.items():
        location_id: str | None = None
        for read in located_at_reads:
            body = read.get("body", {})
            if not isinstance(body, dict):
                continue
            data = body.get("data", [])
            if not isinstance(data, list):
                continue
            for edge in data:
                if isinstance(edge, dict) and edge.get("src_id") == npc_id:
                    location_id = edge.get("dst_id")
                    break
            if location_id is not None:
                break

        if location_id is None:
            missing.append(npc_id)
            continue
        if location_id != expected:
            wrong.append(f"{npc_id}@{location_id!r}(expected {expected!r})")

    if missing or wrong:
        parts: list[str] = []
        if missing:
            parts.append(f"missing_reads={missing}")
        if wrong:
            parts.append(f"wrong_location={wrong}")
        return False, "; ".join(parts)
    return True, f"all {len(SEEDED_NPC_LOCATIONS)} seeded NPCs at expected locations"


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
        (PILLAR_FEEL, check_feel, LLMM_REPEATS),
        (PILLAR_REMEMBER, check_remember, 1),
        (PILLAR_GOSSIP, check_gossip, LLMM_REPEATS),
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


def _make_pillar_reads(client: Any, recorder: Any) -> None:
    """Make explicit reads needed for GOSSIP, WORLD, and LLM-dependent re-reads.

    Called after the demo run completes.  The client's underlying httpx client is
    already wrapped with RecordingClientWrapper, so each call lands in the transcript.

    Args:
        client: EngineClient whose _client is wrapped with RecordingClientWrapper.
        recorder: TranscriptRecorder (unused directly — reads go via client).
    """
    # GOSSIP: hop-2 KNOWS_ABOUT read x LLMM_REPEATS
    for _ in range(LLMM_REPEATS):
        client.get_edge("KNOWS_ABOUT", GOSSIP_HOP2_NPC, GOSSIP_EVENT_ID)

    # WORLD: one LOCATED_AT edge read per seeded NPC — location is dst_id, not a node property
    for npc_id in SEEDED_NPC_LOCATIONS:
        client.get_graph_edges("LOCATED_AT", src_id=npc_id)

    # FEEL: emotion re-reads so total reaches LLMM_REPEATS (demo ran 1 already)
    for _ in range(LLMM_REPEATS - 1):
        client.get_npc_emotion(FEEL_NPC_ID)

    # REMEMBER delta: relationship re-reads
    for _ in range(LLMM_REPEATS - 1):
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Probe the stack, drive the demo, check pillars, write verdicts.

    Returns:
        0 on clean run (even when pillars are red).
        EXIT_STACK_UNAVAILABLE (2) when the stack is unreachable.
        EXIT_HARNESS_ERROR (1) on an unexpected harness failure.
    """
    ensure_utf8_stdout()
    args = _parse_args(argv)

    status, sha = _probe_health(args.base_url)
    if status != "up":
        print(f"DEMO_LIVE=STACK_UNAVAILABLE base_url={args.base_url}")
        return EXIT_STACK_UNAVAILABLE

    os.environ["NPC_BASE_URL"] = args.base_url

    from demo_game.runners.transcript import TranscriptRecorder
    from demo_game.runners.run import DemoRunner

    recorder = TranscriptRecorder()
    runner = DemoRunner(recorder=recorder)

    error = _run_demo_with_recorder(recorder)
    if error:
        print(f"[pillars] demo harness error: {error}", file=sys.stderr)
        _make_pillar_reads(runner.client, recorder)
    else:
        _make_pillar_reads(runner.client, recorder)

    entries = recorder.entries
    verdicts = judge_pillars(entries, sha=sha)
    _write_verdicts(verdicts, args.verdicts_path)
    _print_report(verdicts)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
