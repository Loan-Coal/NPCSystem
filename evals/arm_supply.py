"""
Module: arm_supply
Layer: evals (eval harness — not part of src/)
Purpose: `make eval-supply-report`. Measures, per NPC, how much SUPPLY each ceiling knob
         is bounded by, and says whether that knob can be an A/B arm at all — before one
         is declared, rather than after a probe finds it inert.
Does NOT: assemble context, call an LLM, judge anything, or declare an arm.
Dependencies injected: the roster and the default ceiling are arguments; every npc_engine
         import goes through engine_adapter (DEC-147 §2).
Used by: make eval-supply-report; the numbers it prints are what
         `retrieval_profile_exposure:` in llm_config.yaml records.

WHY THIS EXISTS (DEC-214)

`wide_events` (events_limit 5 -> 15) and `wide_rag` (rag_top_k 5 -> 15) were declared as
A/B arms and produced context byte-identical to default. Both RAISED A CEILING ABOVE ITS
OWN SUPPLY. Neither was detectable from the default receipts, and that is the whole
problem: a receipt shows `min(supply, ceiling)` items, so a saturated default and a
generous world look exactly alike. Only a graph read separates them.

    knob           default   measured supply              raise headroom
    events_limit         5   max 2 known by ANY Character   0 of 8 NPCs
    rag_top_k            5   3-8 candidates per NPC         2 of 8 NPCs

THE TWO NUMBERS THIS REPORT PRINTS, AND WHY BOTH ARE NEEDED

  raise_exposed_npcs
      How many NPCs have supply ABOVE the default ceiling. `wide_rag` scored 2 of 8 —
      not zero, which is why it was not obviously wrong, and not the roster, which is why
      a two-case probe read it as a flat zero.

  largest_full_roster_lower_value
      The largest value a LOWERING arm can take and still bind on every NPC. A cut binds
      on an NPC only below both that NPC's supply and the default ceiling, so it is one
      under the smaller of (minimum supply, default ceiling). None means no cut binds
      everywhere — which is `events_limit`'s verdict here, because one roster NPC knows
      zero events and no limit can remove an item that does not exist.

WHAT THIS CANNOT TELL YOU
Occupancy of a non-numeric slot (`disabled_slots`, `skip_rag`) is not a graph quantity —
it is whether the assembled receipt carries the item, which `make eval-arm-probe` prints
per case. This report covers the ceiling knobs, which are the ones a receipt cannot expose.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_adapter  # noqa: E402

__all__ = ["KnobSupply", "NpcSupply", "summarize_knob"]

DEFAULT_ROSTER: tuple[str, ...] = (
    "captain_sorn", "mira_innkeeper", "old_henryk", "aldric_merchant",
    "lira_fence", "bren_smith", "vex_spymaster", "harwick_guard",
)
"""The eight NPCs scripts/probe_inner_life.py measures, so supply and inner life are
reported over the SAME population and a claim about one transfers to the other."""

_MIN_TOP_K: int = 1
"""Every top-k field is `gt=0`, so a lowering arm cannot go below 1."""


class NpcSupply(BaseModel):
    """What one NPC can supply to each ceiling knob.

    Attributes:
        npc_id: The NPC measured.
        known_events: Events this NPC KNOWS_ABOUT — the supply bounding `events_limit`.
        scope_ids: Size of the DEC-209 retrieval scope before any subtraction.
        rag_supply: `(scope - known) & corpus` — what the vector search can EVER return,
            and therefore the supply bounding `rag_top_k`. Far smaller than `scope_ids`,
            because the corpus holds only the three embeddable node types.
    """

    model_config = ConfigDict(frozen=True)

    npc_id: str
    known_events: int = Field(ge=0)
    scope_ids: int = Field(ge=0)
    rag_supply: int = Field(ge=0)


class KnobSupply(BaseModel):
    """Whether one ceiling knob can be an A/B arm on the measured roster.

    Attributes:
        knob: The RetrievalProfile field this describes.
        default_ceiling: The default profile's value of it.
        roster_size: NPCs measured. Zero means nothing was measured, which is not the
            same as zero exposure and must never read as one.
        supply_min: Smallest supply across the roster.
        supply_max: Largest supply across the roster.
        raise_exposed_npcs: NPCs whose supply exceeds the default ceiling.
        largest_full_roster_lower_value: Largest lowering value that binds on every NPC,
            or None when no lowering value does.
        can_be_an_arm: True when either direction has exposure somewhere.
    """

    model_config = ConfigDict(frozen=True)

    knob: str
    default_ceiling: int
    roster_size: int = Field(ge=0)
    supply_min: int = Field(ge=0)
    supply_max: int = Field(ge=0)
    raise_exposed_npcs: int = Field(ge=0)
    largest_full_roster_lower_value: int | None = None
    can_be_an_arm: bool = False


def summarize_knob(
    *, knob: str, default_ceiling: int, supplies: Sequence[int]
) -> KnobSupply:
    """Decide, from measured supply alone, whether a ceiling knob can be an arm.

    Args:
        knob: The RetrievalProfile field name.
        default_ceiling: The default profile's value of that field.
        supplies: Measured supply, one entry per roster NPC.
    Returns:
        The populated KnobSupply verdict.
    """
    if not supplies:
        return KnobSupply(
            knob=knob, default_ceiling=default_ceiling, roster_size=0,
            supply_min=0, supply_max=0, raise_exposed_npcs=0,
        )
    binding_floor = min(min(supplies), default_ceiling)
    lower_value = binding_floor - 1
    largest_lower = lower_value if lower_value >= _MIN_TOP_K else None
    raise_exposed = sum(1 for supply in supplies if supply > default_ceiling)
    return KnobSupply(
        knob=knob,
        default_ceiling=default_ceiling,
        roster_size=len(supplies),
        supply_min=min(supplies),
        supply_max=max(supplies),
        raise_exposed_npcs=raise_exposed,
        largest_full_roster_lower_value=largest_lower,
        can_be_an_arm=raise_exposed > 0 or largest_lower is not None,
    )


async def measure_roster(session: Any, roster: Sequence[str]) -> list[NpcSupply]:
    """Read each NPC's scope, known events and corpus intersection from the graph.

    Args:
        session: Active Neo4j AsyncSession.
        roster: NPC ids to measure.
    Returns:
        One NpcSupply per roster entry, in roster order.
    """
    corpus = await engine_adapter.embedded_node_ids(session)
    rows: list[NpcSupply] = []
    for npc_id in roster:
        scope = await engine_adapter.rag_scope_ids(session, npc_id)
        known = await engine_adapter.known_event_ids(session, npc_id)
        rows.append(
            NpcSupply(
                npc_id=npc_id, known_events=len(known), scope_ids=len(scope),
                rag_supply=len((scope - known) & corpus),
            )
        )
    print(f"corpus: {len(corpus)} embedded nodes")
    return rows


def _print_rows(rows: Sequence[NpcSupply]) -> None:
    """Print the per-NPC supply table."""
    print(f"\n{'npc':<20}{'known_ev':>10}{'scope':>8}{'rag_supply':>13}")
    for row in rows:
        print(
            f"{row.npc_id:<20}{row.known_events:>10}{row.scope_ids:>8}"
            f"{row.rag_supply:>13}"
        )


def _print_verdict(summary: KnobSupply) -> None:
    """Print one knob's verdict, in the words a declaration decision needs."""
    lower = summary.largest_full_roster_lower_value
    print(
        f"\n{summary.knob}: default ceiling {summary.default_ceiling}, supply "
        f"{summary.supply_min}-{summary.supply_max} over {summary.roster_size} NPCs"
    )
    print(
        f"    RAISE  exposed on {summary.raise_exposed_npcs}/{summary.roster_size} NPCs"
        + ("  <- DEAD, nothing to take" if summary.raise_exposed_npcs == 0 else "")
        + (
            "  <- PARTIAL, a 2-case probe cannot sample this"
            if 0 < summary.raise_exposed_npcs < summary.roster_size
            else ""
        )
    )
    print(
        "    LOWER  largest value binding on every NPC: "
        + (f"{lower}" if lower is not None else "NONE  <- DEAD, no cut binds everywhere")
    )


async def _run(roster: Sequence[str], default_ceiling: int) -> int:
    """Measure the roster and print the report. Returns the process exit code."""
    embedding_index, driver = await engine_adapter.build_retrieval_stack()
    del embedding_index
    async with driver.session() as session:
        rows = await measure_roster(session, roster)
    await driver.close()
    _print_rows(rows)
    for knob, supplies in (
        ("rag_top_k", [row.rag_supply for row in rows]),
        ("events_limit", [row.known_events for row in rows]),
    ):
        _print_verdict(
            summarize_knob(knob=knob, default_ceiling=default_ceiling, supplies=supplies)
        )
    print(
        "\nRecord whatever you declare in llm_config.yaml's retrieval_profile_exposure: "
        "block,\nwith the corpus_sha these numbers were measured against (DEC-214)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the supply report.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 on success.
    """
    parser = argparse.ArgumentParser(
        prog="python -m evals.arm_supply",
        description="Measured supply per ceiling knob — run BEFORE declaring an arm.",
    )
    parser.add_argument("--npc", action="append", default=None, help="Repeatable.")
    parser.add_argument(
        "--default-ceiling", type=int,
        default=int(os.environ.get("RAG_TOP_K", "5")),
        help="The default profile's value for the ceiling knobs (Settings.RAG_TOP_K).",
    )
    parsed = parser.parse_args(sys.argv[1:] if argv is None else argv)
    roster = tuple(parsed.npc) if parsed.npc else DEFAULT_ROSTER
    return asyncio.run(_run(roster, parsed.default_ceiling))


if __name__ == "__main__":
    sys.exit(main())
