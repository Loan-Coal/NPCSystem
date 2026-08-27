"""
Module: probe_inner_life
Layer: scripts (operator tooling — not part of npc_engine, not part of evals)
Purpose: The 8-NPC inner-life probe. Reports, per NPC, which context slots are actually
         POPULATED in the assembled context — the instrument behind every
         "beliefs 8/8, goals 8/8, memories 8/8, current_location 8/8" figure from P0-P8.
Does NOT: generate dialogue, call an LLM, mutate the graph, or judge anything.
Dependencies injected: base URL, API key, NPC list and player id are all arguments.
Used by: make probe-inner-life.

WHY THIS IS IN THE REPO (ISSUE-216)
It was not. It lived in a session-scoped scratchpad directory, so it had to be rewritten
from prose before each use, and in P8 the reconstruction initially parsed the wrong
response shape and reported a false 0/8 across the board before being corrected. A
measuring instrument rebuilt from a description before each use is not the same
instrument twice, which makes every cross-phase comparison weaker than it reads.

WHY IT LANDS IN P9 SPECIFICALLY
P9 changed its contract. Until P9 the debug route took no `player_id`, so
`get_reputation_context_for_npc` and CYPHER_PROPAGATED_REPUTATION_FOR_NPC matched against
"" and `player_reputation`, `propagated_reputation` and `player_relation` were
structurally invisible. Committing the pre-P9 probe would have committed the version P9
was about to replace.

READING THE OUTPUT
`player_relation` tracks LIVE WORLD STATE — it counts RELATES_TO edges to the player,
and an ordinary dialogue turn creates one. DEC-212 measured 2/8, then 3/8 after a handful
of verification turns. It is only comparable across phases IMMEDIATELY after
`make eval-world-reset`, and the header says so on every run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PLAYER_ID = "player_demo"
DEFAULT_QUERY = "what news"
_TIMEOUT_SECONDS = 120.0

PROBE_NPCS: tuple[str, ...] = (
    "captain_sorn",
    "mira_innkeeper",
    "old_henryk",
    "aldric_merchant",
    "lira_fence",
    "bren_smith",
    "vex_spymaster",
    "harwick_guard",
)
"""The eight NPCs the P0-P8 headline was measured on.

Fixed here rather than sampled: a probe whose roster moves between phases cannot support
"8/8 was 0/975". Override with --npc for a different set, and say so when reporting.
"""

INNER_LIFE_SLOTS: tuple[str, ...] = (
    "beliefs",
    "goals",
    "memories",
    "current_location",
    "retrieved_context",
    "nearby_npcs",
    "player_relation",
    "player_reputation",
    "propagated_reputation",
)
"""Slots reported. The last three are observable ONLY with a player_id (P9)."""

_NPC_NESTED_SLOTS = ("beliefs", "goals", "memories", "top_need", "player_memories")
"""Slots the serializer nests one level down, under the `npc` key."""

_NPC_PROFILE_NESTED_SLOTS = ("current_location",)
"""Slots nested TWO levels down, under `npc.profile`.

`context_slots.py:130` declares `current_location` at path
``npc.profile.current_location``. Reading it at `npc.current_location` returns nothing
and the probe reports a false 0/8 — which it did on its first P9 run, caught only by
comparing against DEC-212's recorded 8/8. This is the same class of mistake ISSUE-216
was filed for, made a second time, which is the argument for pinning it in a test.
"""


def _is_populated(value: object) -> bool:
    """True when a slot carries content, as opposed to being emitted empty.

    Every declared slot is emitted unconditionally (P6), so presence of the KEY says
    nothing; only the value does. 0 and False count as populated — they are measurements.
    """
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, dict, set)):
        return len(value) > 0
    return True


def extract_slots(payload: dict) -> dict[str, bool]:
    """Reduce one debug-retrieval response to slot -> populated.

    Args:
        payload: Parsed JSON body of GET /v1/admin/debug/retrieval.

    Returns:
        Mapping of every INNER_LIFE_SLOTS entry to whether it carries content.

    Slots live at THREE depths and getting that wrong is the whole failure mode:
    `beliefs`/`goals`/`memories` under `npc`, `current_location` under `npc.profile`,
    everything else at top level.
    """
    top: dict[str, object] = {}
    for item in payload.get("context_items", []):
        raw = item.get("text", "")
        try:
            top[item["key"]] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            top[item["key"]] = raw
    npc = top.get("npc")
    nested = npc if isinstance(npc, dict) else {}
    profile = nested.get("profile")
    profile_nested = profile if isinstance(profile, dict) else {}
    resolved: dict[str, bool] = {}
    for slot in INNER_LIFE_SLOTS:
        if slot in _NPC_PROFILE_NESTED_SLOTS:
            source: dict = profile_nested
        elif slot in _NPC_NESTED_SLOTS:
            source = nested
        else:
            source = top
        resolved[slot] = _is_populated(source.get(slot))
    return resolved


def probe_one(
    *, base_url: str, api_key: str, npc_id: str, player_id: str, query: str,
    retrieval_profile: str | None,
) -> dict[str, bool]:
    """Assemble one NPC's context through the debug route and reduce it to slot flags.

    Args:
        base_url: Engine base URL.
        api_key: Admin API key.
        npc_id: NPC to probe.
        player_id: Player the context is assembled for. REQUIRED — without it the three
            reputation slots are structurally empty and the probe reports a false zero.
        query: Retrieval signal.
        retrieval_profile: Named arm, or None for the deployment default.

    Returns:
        Mapping of slot to populated.

    Raises:
        urllib.error.HTTPError: On any non-2xx, including the 400 an undeclared arm gives.
    """
    params = {"npc_id": npc_id, "query": query, "player_id": player_id}
    if retrieval_profile:
        params["retrieval_profile"] = retrieval_profile
    url = f"{base_url.rstrip('/')}/v1/admin/debug/retrieval?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
        return extract_slots(json.loads(response.read().decode("utf-8")))


def _print_report(label: str, rows: dict[str, dict[str, bool]], player_id: str) -> None:
    """Print the per-NPC matrix and the N/total roll-up per slot."""
    total = len(rows)
    print(f"\nINNER-LIFE PROBE — {label}   player_id={player_id}   npcs={total}")
    print("player_relation tracks LIVE world state; compare it only right after "
          "`make eval-world-reset`.\n")
    header = f"{'npc':<18}" + "".join(f"{slot[:11]:>13}" for slot in INNER_LIFE_SLOTS)
    print(header)
    for npc_id, slots in rows.items():
        line = f"{npc_id:<18}" + "".join(
            f"{('yes' if slots[slot] else '-'):>13}" for slot in INNER_LIFE_SLOTS
        )
        print(line)
    print("-" * len(header))
    summary = f"{'TOTAL':<18}" + "".join(
        f"{f'{sum(1 for s in rows.values() if s[slot])}/{total}':>13}"
        for slot in INNER_LIFE_SLOTS
    )
    print(summary)


def main(argv: list[str] | None = None) -> int:
    """Probe every NPC and print the report.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 when the engine could not be reached.
    """
    parser = argparse.ArgumentParser(
        prog="python scripts/probe_inner_life.py",
        description="8-NPC inner-life probe through GET /v1/admin/debug/retrieval.",
    )
    parser.add_argument("label", nargs="?", default="unlabelled")
    parser.add_argument("--npc", action="append", default=None, help="Repeatable.")
    parser.add_argument("--player-id", default=DEFAULT_PLAYER_ID)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--retrieval-profile", default=None)
    parser.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", DEFAULT_BASE_URL))
    parsed = parser.parse_args(sys.argv[1:] if argv is None else argv)

    api_key = os.environ.get("API_KEY_SECRET", "")
    if not api_key:
        print("ERROR: API_KEY_SECRET is not set.")
        return 1
    npcs = tuple(parsed.npc) if parsed.npc else PROBE_NPCS
    try:
        rows = {
            npc_id: probe_one(
                base_url=parsed.base_url, api_key=api_key, npc_id=npc_id,
                player_id=parsed.player_id, query=parsed.query,
                retrieval_profile=parsed.retrieval_profile,
            )
            for npc_id in npcs
        }
    except Exception as exc:  # noqa: BLE001 - operator tool: report and exit non-zero
        print(f"ERROR: probe failed against {parsed.base_url}: {exc!r}")
        return 1
    _print_report(parsed.label, rows, parsed.player_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
