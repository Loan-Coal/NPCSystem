"""
Module: probe_context_ceiling
Layer: scripts (operator tooling — not part of npc_engine, not part of evals)
Purpose: The 8-NPC assembled-context CEILING probe. Reports, per NPC, how many tokens
         the context system actually asks for with RAG on, and whether the configured
         window's budget dropped anything — the two inputs P10's window trim is derived
         from.
Does NOT: generate dialogue, call an LLM, mutate the graph, or judge anything.
Dependencies injected: base URL, API key, NPC list, player id and arm are all arguments.
Used by: make probe-ceiling.

WHY THIS EXISTS ALONGSIDE probe_inner_life.py
`probe_inner_life` answers "is the slot POPULATED" and reports presence, never a token
total. P10 has to choose a context window, and that decision needs the number presence
cannot give: what does assembly COST, per NPC, at the top of the roster. Before this
module the answer existed for two of the eight NPCs, quoted from a scratchpad session,
and DEC-204's table was measured on a different roster with tier B empty.

THE TWO TOTALS, AND WHY BOTH ARE REPORTED
The debug route returns two numbers that are not the same number:

  * top-level `total_tokens` — the estimate of the SERIALIZED context blob. This is the
    quantity `_trim_to_serialized_budget` compares against PROMPT_TOKEN_BUDGET, so it is
    the one that decides whether an item is evicted.
  * `context_receipt.total_tokens` — the SUM of per-item estimates. The comment above
    `_tier_a_cap_with_reclaim` records that this OVER-counts the serialized size more
    often than it under-counts, because orphan keys are charged here and contribute no
    bytes.

Measured on captain_sorn at corpus_sha 2b19e47a: 978 serialized, 995 summed. `ceiling`
is the LARGER of the two, because a window sized to the smaller one has headroom that
does not exist. Pinned by tests/unit/scripts/test_probe_context_ceiling.py.

READING THE ISSUE-209 COLUMN
ISSUE-209 is a TIER-A selection defect: `_fit_tier_a_pinned_pool` and `_fill_tier_a` both
SKIP an item that does not fit rather than stopping, which makes selection non-monotone in
the cap. It can only fire when tier A actually skips something, so a run with no tier-A
`tier_soft_cap` or `prompt_budget` drop has not re-opened it. A `final_trim` drop is a
different mechanism — the post-serialization loop only ever removes — and ISSUE-197
misattributed the bug to it once already, so the two are kept apart here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass

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
"""The same eight NPCs scripts/probe_inner_life.py uses.

Duplicated rather than imported because `scripts/` has no `__init__.py` and importing
across it would put the repo root on sys.path. The duplication is guarded:
test_the_roster_is_identical_to_the_inner_life_probe fails if the two ever diverge.
"""

REPORTED_TIERS: tuple[str, ...] = ("tier0", "tierA", "tierB", "tierC")
"""Mirrors retrieval.context.context_receipt.REPORTED_TIERS. An omitted tier reads as
'not measured'; a tier reported at zero is a measurement."""

ISSUE_209_STAGES: frozenset[str] = frozenset({"tier_soft_cap", "prompt_budget"})
"""The two drop reasons produced by a greedy tier-A SKIP. `final_trim` is not one."""

ISSUE_209_TIER = "tierA"
"""ISSUE-209 is a tier-A selection defect; tiers B and C are compressed, not skipped."""


@dataclass(frozen=True)
class CeilingRow:
    """One NPC's assembled-context cost at the window the engine is running.

    Attributes:
        npc_id: NPC the context was assembled for.
        retrieval_profile: Resolved arm name the assembly ran under.
        serialized_tokens: Estimate of the serialized context blob.
        summed_tokens: Sum of per-item estimates from the receipt.
        ceiling_tokens: The larger of the two, which is what a window must hold.
        tiers: tier name -> (items, tokens), one entry per REPORTED_TIERS row.
        prompt_token_budget: The budget this assembly was held to.
        dropped: Every drop as 'key:tier:reason'.
        issue_209_drops: Tier-A greedy-skip drops only, as 'key:reason'.
    """

    npc_id: str
    retrieval_profile: str
    serialized_tokens: int
    summed_tokens: int
    ceiling_tokens: int
    tiers: dict[str, tuple[int, int]]
    prompt_token_budget: int
    dropped: tuple[str, ...]
    issue_209_drops: tuple[str, ...]


def extract_ceiling(payload: dict) -> CeilingRow:
    """Reduce one debug-retrieval response to its cost row.

    Args:
        payload: Parsed JSON body of GET /v1/admin/debug/retrieval.

    Returns:
        The populated CeilingRow.

    Raises:
        ValueError: When the response carries no receipt. A cached assembly publishes
            none (DEC-195); reporting zeros there would read as "this NPC spent nothing",
            which is the opposite of the truth.
    """
    receipt = payload.get("context_receipt")
    if not receipt:
        raise ValueError(
            f"no context receipt for npc_id={payload.get('npc_id')!r}: the assembly was "
            f"served from cache, so its cost was never measured"
        )
    spend = {row["tier"]: (int(row["items"]), int(row["tokens"])) for row in receipt["tier_spend"]}
    dropped = tuple(receipt.get("dropped", ()))
    serialized = int(payload.get("total_tokens", 0))
    summed = int(receipt.get("total_tokens", 0))
    return CeilingRow(
        npc_id=str(payload.get("npc_id", "")),
        retrieval_profile=str(receipt.get("retrieval_profile", "")),
        serialized_tokens=serialized,
        summed_tokens=summed,
        ceiling_tokens=max(serialized, summed),
        tiers={tier: spend.get(tier, (0, 0)) for tier in REPORTED_TIERS},
        prompt_token_budget=int(receipt.get("prompt_token_budget", 0)),
        dropped=tuple(f"{d['key']}:{d['tier']}:{d['reason']}" for d in dropped),
        issue_209_drops=tuple(
            f"{d['key']}:{d['reason']}"
            for d in dropped
            if d["tier"] == ISSUE_209_TIER and d["reason"] in ISSUE_209_STAGES
        ),
    )


def probe_one(
    *, base_url: str, api_key: str, npc_id: str, player_id: str, query: str,
    retrieval_profile: str | None,
) -> CeilingRow:
    """Assemble one NPC's context through the debug route and reduce it to its cost row.

    Args:
        base_url: Engine base URL.
        api_key: Admin API key.
        npc_id: NPC to probe.
        player_id: Player the context is assembled for.
        query: Retrieval signal.
        retrieval_profile: Named arm, or None for the deployment default.

    Returns:
        The NPC's CeilingRow.

    Raises:
        urllib.error.HTTPError: On any non-2xx, including the 400 an undeclared arm gives.
        ValueError: When the engine returns no receipt.
    """
    params = {"npc_id": npc_id, "query": query, "player_id": player_id}
    if retrieval_profile:
        params["retrieval_profile"] = retrieval_profile
    url = f"{base_url.rstrip('/')}/v1/admin/debug/retrieval?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
        return extract_ceiling(json.loads(response.read().decode("utf-8")))


def _tier_cells(row: CeilingRow) -> str:
    """Render one row's four tier columns as 'items/tokens'."""
    return "".join(f"{f'{row.tiers[t][0]}/{row.tiers[t][1]}':>12}" for t in REPORTED_TIERS)


def _print_report(label: str, rows: list[CeilingRow], player_id: str) -> None:
    """Print the per-NPC cost matrix, the roster ceiling, and the ISSUE-209 verdict."""
    budgets = sorted({row.prompt_token_budget for row in rows})
    arms = sorted({row.retrieval_profile for row in rows})
    print(f"\nCONTEXT-CEILING PROBE — {label}   player_id={player_id}   npcs={len(rows)}")
    print(f"budget={budgets}   arm={arms}")
    header = (
        f"{'npc':<18}"
        + "".join(f"{t:>12}" for t in REPORTED_TIERS)
        + f"{'summed':>10}{'serial':>10}{'CEILING':>10}{'drops':>8}"
    )
    print(header)
    for row in rows:
        print(
            f"{row.npc_id:<18}{_tier_cells(row)}"
            f"{row.summed_tokens:>10}{row.serialized_tokens:>10}"
            f"{row.ceiling_tokens:>10}{len(row.dropped):>8}"
        )
    print("-" * len(header))
    print(f"ROSTER CEILING (max over NPCs): {max(r.ceiling_tokens for r in rows)} tokens")
    _print_issue_209(rows)


def _print_issue_209(rows: list[CeilingRow]) -> None:
    """Print gate 11: per NPC, did this window re-open ISSUE-209's non-monotone skip."""
    print("\nISSUE-209 (tier-A greedy skip) at this window, per NPC:")
    for row in rows:
        verdict = ", ".join(row.issue_209_drops) if row.issue_209_drops else "NOT re-opened"
        print(f"  {row.npc_id:<18} {verdict}")
    other = [d for row in rows for d in row.dropped if "final_trim" in d or ":tierB:" in d]
    print(f"  other drops (not ISSUE-209): {other or 'none'}")


def main(argv: list[str] | None = None) -> int:
    """Probe every NPC and print the cost report.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 when the engine could not be reached.
    """
    parser = argparse.ArgumentParser(
        prog="python scripts/probe_context_ceiling.py",
        description="8-NPC assembled-context ceiling probe (no LLM call).",
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
    try:
        rows = [
            probe_one(
                base_url=parsed.base_url, api_key=api_key, npc_id=npc_id,
                player_id=parsed.player_id, query=parsed.query,
                retrieval_profile=parsed.retrieval_profile,
            )
            for npc_id in (tuple(parsed.npc) if parsed.npc else PROBE_NPCS)
        ]
    except Exception as exc:  # noqa: BLE001 - operator tool: report and exit non-zero
        print(f"ERROR: probe failed against {parsed.base_url}: {exc!r}")
        return 1
    _print_report(parsed.label, rows, parsed.player_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
