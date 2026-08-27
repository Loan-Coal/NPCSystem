"""
Module: test_shipped_retrieval_profiles
Layer: test (unit)
Purpose: Pin the retrieval profiles the engine actually SHIPS — the A/B arms an eval
         run can select by name. DEC-194 made the switch real and strictly resolved,
         but no profile was ever declared, so `--profiles default,X` returned HTTP 400
         for every X and a context A/B could not be run at all.
Dependencies: pytest, yaml; npc_engine.schema (load_llm_config, build_default_profile)
Used by: pytest (make test / make check)

WHY THE ARMS ARE SINGLE-VARIABLE
Each declared arm differs from the default profile in exactly ONE field. An arm that
moved two knobs at once would produce a delta no one could attribute — the defect
DEC-194 called out when it split RAG_TOP_K's three meanings apart. These assertions
are what stop a later "while I'm here" edit from quietly reintroducing that.

WHY THE ARMS ARE COARSE
Measured resolution on the current batteries: the regression gate needs a >=6.4pp drop
on guard (n=78) before it fires, and refusal_judge sits at kappa 0.225 (DEC-188,
ISSUE-184). A subtle arm cannot clear that floor, so the arms are deliberately drastic —
chosen to produce an effect the instrument can actually see, or to prove there is none.

WHY EVERY ARM SUBTRACTS (DEC-214)
The arms were originally sized against JUDGE RESOLUTION alone, because tier B carried
zero items on every run ever recorded (DEC-208) and "does this arm change anything?" was
unanswerable. It is answerable now, and the answer for the two additive arms was NO:
`wide_events` at events_limit=15 and `wide_rag` at rag_top_k=15 produced item_keys
BYTE-IDENTICAL to default on 2/2 probe cases, because a raised ceiling cannot add an item
that does not exist. Measured supply on the 8-NPC roster, clean eval world:

    knob            default   measured supply        headroom to RAISE
    events_limit          5   max 2 known by ANY      0 on 8/8
    rag_top_k             5   3-8 per NPC             0 on 6/8

So a ceiling knob on this world is only an arm when it is LOWERED. `narrow_rag` at 2 sits
below the minimum measured supply of 3, which is what makes it bind on every NPC rather
than on the two with spare supply. The rule this module now enforces:

    AN ARM MAY NOT RAISE A CEILING ABOVE THE SUPPLY THAT WAS MEASURED FOR IT.

Pinned by test_no_declared_arm_raises_a_ceiling_above_the_measured_supply. The measured
numbers themselves are recorded in llm_config.yaml's `retrieval_profile_exposure:` block
and checked by tests/unit/config/test_declared_arm_exposure.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from npc_engine.schema.llm_schema_loader import load_llm_config
from npc_engine.schema.retrieval_profile_models import (
    RetrievalProfile,
    build_default_profile,
)
from npc_engine.utils.errors import RetrievalProfileNotFoundError

# Matches Settings.RAG_TOP_K / Settings.CROSS_ENCODER_ENABLED defaults, which are what
# build_default_profile is fed in production (context_profile_resolver).
_DEFAULT_RAG_TOP_K: int = 5
_DEFAULT_CROSS_ENCODER: bool = False

_SHIPPED_CONFIG: str = "config/llm_config.yaml"

# The arms this repo commits to shipping. Each entry is (name, the single field that
# may differ from the default profile).
#
# RETIRED 2026-08-27 (DEC-214), both for zero measured exposure and NOT replaced by a
# resized version of themselves:
#   * wide_events (events_limit=15) — no Character in the eval world knows more than 2
#     events, so the default limit of 5 already exceeds supply. Dead at any value >= 2.
#   * wide_rag (rag_top_k=15) — the vector candidate set is 3-8 nodes, so the default
#     top-k of 5 already retrieves substantially everything in scope.
_DECLARED_ARMS: tuple[tuple[str, str], ...] = (
    ("no_rag", "skip_rag"),
    ("narrow_rag", "rag_top_k"),
    ("no_memories", "disabled_slots"),
)

_MIN_MEASURED_RAG_SUPPLY: int = 3
"""Smallest vector-candidate set measured over the 8-NPC probe roster (DEC-214).

bren_smith and vex_spymaster, on the clean eval baseline at corpus_sha 2b19e47a1755354e.
A `rag_top_k` arm strictly below this binds on EVERY NPC; one at or above it binds only
on the NPCs that happen to have spare supply, which is how `wide_rag` came to be inert.
"""

_MAX_MEASURED_EVENT_SUPPLY: int = 2
"""Most events any Character in the eval world KNOWS_ABOUT (DEC-214).

`MATCH (c:Character)-[:KNOWS_ABOUT]->(e:Event) RETURN c.id, count(e)` over all 23
Characters: 16 know 1 or 2, 7 know none. This is why `events_limit` is not an arm at any
value >= 2 and was retired rather than resized.
"""

_TIER_A_ARM_SLOT: str = "memories"
"""The tier-A slot the tier-A arm withholds (DEC-214).

CONTENT occupancy measured 8/8 on the probe roster, which is a stricter test than
presence in item_keys. `nearby_npcs` was the first choice and was rejected on measurement:
its item is present on 8/8 but its text is the empty list `[]` for bren_smith, so the
serialized context is IDENTICAL under that arm for one of eight NPCs. `memories` is
populated on 8/8 by the same instrument that reports the P0-P8 `memories 8/8` headline.
"""

# Which TIER a profile knob moves. P8 made this distinction load-bearing: before it,
# every one of these was inert (tierB.items was 0 on every run ever recorded), so
# grouping them was harmless. See test_no_declared_arm_varies_both_a_tier_a_and_a_
# tier_b_knob for why it is not harmless now.
_TIER_A_KNOBS: frozenset[str] = frozenset({"events_limit"})
"""Knobs that bound a DIRECT GRAPH READ feeding tier A (`get_events_for_npc`)."""

_TIER_B_KNOBS: frozenset[str] = frozenset(
    {"rag_top_k", "graph_rag_top_k", "cross_encoder_enabled", "skip_rag"}
)
"""Knobs that bound the VECTOR SEARCH feeding tiers B and C.

`rag_top_k` and `graph_rag_top_k` stay ONE knob: they are the same quantity at two call
sites and `GRAPH_RAG_ENABLED` picks which one fires, so an arm that widened only the one
that is switched off would not be the arm it claims to be.
"""

_CROSS_TIER_KNOBS: frozenset[str] = frozenset(
    {"weight_profile", "enabled_tiers", "slot_cap_overrides"}
)
"""Knobs that are not a single tier's: ranking weights and the P8 tier/cap gates.

`disabled_slots` was in this set until DEC-214 and is NOT any more. It is resolvable to a
tier — every slot it can name declares one — and leaving it here let the tier-A arm opt
itself out of the one-arm-one-tier rule by naming a knob neither side of the rule sees.
"""

_SLOT_RESOLVED_KNOBS: frozenset[str] = frozenset({"disabled_slots"})
"""Knobs whose tier is decided by the SLOTS they name, not by the knob itself."""


def _tiers_named_by_disabled_slots(arm: RetrievalProfile) -> frozenset[str]:
    """Return the tiers of the slots this arm withholds, resolved from the declaration table.

    A slot name nobody declares raises: it would silently withhold nothing, and an arm
    that withholds nothing is not an arm.
    """
    from npc_engine.retrieval.context.context_slots import CONTEXT_SLOTS

    by_key = {slot.key: slot.tier for slot in CONTEXT_SLOTS}
    unknown = sorted(set(arm.disabled_slots) - set(by_key))
    assert not unknown, f"disabled_slots names undeclared slot(s) {unknown}"
    return frozenset(by_key[key] for key in arm.disabled_slots)


def _default_profile() -> RetrievalProfile:
    return build_default_profile(
        rag_top_k=_DEFAULT_RAG_TOP_K, cross_encoder_enabled=_DEFAULT_CROSS_ENCODER
    )


def _shipped_profiles() -> dict[str, RetrievalProfile]:
    package_root = Path(__file__).resolve().parents[3] / "src" / "npc_engine"
    return load_llm_config(config_path=str(package_root / _SHIPPED_CONFIG)).retrieval_profiles


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,_varied", _DECLARED_ARMS)
def test_the_engine_ships_the_declared_ab_arm(name: str, _varied: str) -> None:
    """An arm that is not declared cannot be run: resolution is strict by DEC-194, so
    `evals generate --profiles default,<name>` would 400 rather than silently fall
    back. Before these were declared the registry was empty and no context A/B was
    possible at all."""
    assert name in _shipped_profiles(), (
        f"{name!r} is not declared in {_SHIPPED_CONFIG}; declared: "
        f"{sorted(_shipped_profiles())}"
    )


@pytest.mark.parametrize("name,varied", _DECLARED_ARMS)
def test_each_arm_differs_from_default_in_exactly_one_field(name: str, varied: str) -> None:
    """One knob per arm, so a measured delta is attributable to that knob.

    graph_rag_top_k is allowed to move WITH rag_top_k: they are the same quantity at two
    call sites, and GRAPH_RAG_ENABLED decides which one fires, so an arm that widened
    only the switched-off one would not be the arm it claims to be.

    `events_limit` was in this group until P9 and is NOT any more. It feeds tier A; the
    other two feed tiers B and C. That distinction was harmless while tier B carried
    zero items on every run ever recorded, and stopped being harmless when P8 made it
    carry 2-3 (DEC-212). See test_no_declared_arm_varies_both_a_tier_a_and_a_tier_b_knob.
    """
    top_k_group = {"rag_top_k", "graph_rag_top_k"}
    allowed = top_k_group if varied in top_k_group else {varied}

    arm = _shipped_profiles()[name]
    default = _default_profile()
    differing = {
        field
        for field in type(default).model_fields
        if getattr(arm, field) != getattr(default, field)
    }
    assert differing, f"{name!r} is identical to the default profile — it is not an arm"
    assert differing <= allowed, (
        f"{name!r} differs from default in {sorted(differing)}, but this arm is only "
        f"allowed to vary {sorted(allowed)} — a two-knob arm produces an unattributable delta"
    )


# ---------------------------------------------------------------------------
# The arms are actually coarse, and strictness still holds
# ---------------------------------------------------------------------------


def test_the_no_rag_arm_really_skips_retrieval() -> None:
    """The highest-information contrast available: it answers 'does tier-B retrieval
    change measured behaviour at all', which nothing in this repo has established."""
    assert _shipped_profiles()["no_rag"].skip_rag is True


def test_the_narrow_rag_arm_sits_below_the_measured_supply_so_its_ceiling_binds() -> None:
    """A ceiling knob is only an arm where it is BELOW supply, and this world's supply
    is 3-8 candidates per NPC. At or above the minimum of 3 the arm would bind on some
    NPCs and not others; strictly below it, it binds on all of them.

    Also required to be a large step, for the same reason the retired `wide_rag` was:
    a 4 vs 5 arm cannot clear the >=6.4pp judge floor. Down is the only direction this
    world offers, so the multiple is inverted.

    `events_limit` must stay AT the default here, or this becomes a two-tier arm.
    """
    narrow = _shipped_profiles()["narrow_rag"]
    assert narrow.rag_top_k < _MIN_MEASURED_RAG_SUPPLY, (
        f"narrow_rag at rag_top_k={narrow.rag_top_k} does not bind on an NPC whose "
        f"candidate set is only {_MIN_MEASURED_RAG_SUPPLY}"
    )
    assert narrow.rag_top_k * 2 <= _DEFAULT_RAG_TOP_K
    assert narrow.graph_rag_top_k == narrow.rag_top_k
    assert narrow.events_limit == _DEFAULT_RAG_TOP_K
    assert narrow.skip_rag is False


def test_the_tier_a_arm_withholds_a_slot_the_whole_probe_roster_carries() -> None:
    """The live replacement for the retired `wide_events` — P9 split a tier-A arm out of
    `wide_rag` so a delta could be attributed to a tier, and retiring the dead arm
    without replacing it would have discarded that split.

    `memories` is a tier-A slot (context_slots.py, priority 90, path npc.memories) whose
    CONTENT is populated on 8 of 8 roster NPCs, so withholding it removes exactly one
    item per NPC AND changes what the model reads. Presence in item_keys is not enough:
    `nearby_npcs` is present on 8/8 but empty (`[]`) for bren_smith, so that arm would
    have left one NPC's serialized context byte-identical. The vector search must be left
    entirely alone.
    """
    arm = _shipped_profiles()["no_memories"]
    assert arm.disabled_slots == frozenset({_TIER_A_ARM_SLOT})
    assert arm.rag_top_k == _DEFAULT_RAG_TOP_K
    assert arm.graph_rag_top_k == _DEFAULT_RAG_TOP_K
    assert arm.events_limit == _DEFAULT_RAG_TOP_K
    assert arm.skip_rag is False


def test_no_declared_arm_raises_a_ceiling_above_the_measured_supply() -> None:
    """THE RULE DEC-214 INSTALLS: an arm may not raise a limit past its measured supply.

    `wide_events` and `wide_rag` were both declared before tier B carried anything, so
    "does this arm change anything?" could not be asked; they were sized against judge
    resolution instead and each turned out to be a ceiling above its own supply. This
    catches a resized version of either at declaration time rather than at gate 4.
    """
    default = _default_profile()
    for name, arm in _shipped_profiles().items():
        assert arm.events_limit <= max(default.events_limit, _MAX_MEASURED_EVENT_SUPPLY), (
            f"{name!r} raises events_limit to {arm.events_limit}, above both the default "
            f"and the measured supply of {_MAX_MEASURED_EVENT_SUPPLY} events per NPC — "
            f"it cannot add a row that does not exist"
        )
        assert arm.rag_top_k <= max(default.rag_top_k, _MIN_MEASURED_RAG_SUPPLY), (
            f"{name!r} raises rag_top_k to {arm.rag_top_k}; the smallest measured "
            f"candidate set is {_MIN_MEASURED_RAG_SUPPLY} and the default top-k is "
            f"already {default.rag_top_k}, so the raise has no exposure"
        )


def test_no_declared_arm_varies_both_a_tier_a_and_a_tier_b_knob() -> None:
    """One arm, one TIER — otherwise the delta is split across two mechanisms.

    P8 turned tier B on: `tierB.items` was 0 on every run ever recorded and is now 2-3
    per NPC (DEC-212). That makes the old `{rag_top_k, graph_rag_top_k, events_limit}`
    grouping unsafe. `events_limit` bounds `get_events_for_npc`, which produces tier-A
    `event:` items; `rag_top_k` bounds the vector search, which produces tier-B and
    tier-C `rag:` items. An arm moving both moves two tiers through two mechanisms and
    the receipt cannot say which one carried the effect.

    The grouping was defensible only while all three knobs were inert. They are not.

    DEC-214: `disabled_slots` is resolved to the tier of the slot it names, so the
    tier-A arm is checked by this rule rather than sliding past it as a cross-tier knob.
    """
    default = _default_profile()
    for name, arm in _shipped_profiles().items():
        differing = {
            field
            for field in type(default).model_fields
            if getattr(arm, field) != getattr(default, field)
        }
        tiers = frozenset()
        if differing & _TIER_A_KNOBS:
            tiers |= {"tierA"}
        if differing & _TIER_B_KNOBS:
            tiers |= {"tierB"}
        if "disabled_slots" in differing:
            tiers |= _tiers_named_by_disabled_slots(arm)
        assert len(tiers) <= 1, (
            f"{name!r} varies knobs {sorted(differing)}, which move tiers "
            f"{sorted(tiers)}; a delta from this arm is unattributable to either tier"
        )


def test_every_declared_arm_varies_a_knob_this_test_module_has_classified() -> None:
    """A knob nobody classified cannot be checked by the tier test above.

    Without this, adding `disabled_slots` to an arm would silently opt that arm out of
    the one-tier rule — the test would pass by finding nothing on both sides.
    """
    default = _default_profile()
    classified = _TIER_A_KNOBS | _TIER_B_KNOBS | _CROSS_TIER_KNOBS | _SLOT_RESOLVED_KNOBS
    unclassified = set(type(default).model_fields) - classified
    assert not unclassified, (
        f"RetrievalProfile fields {sorted(unclassified)} are not classified as tier-A, "
        f"tier-B or cross-tier, so test_no_declared_arm_varies_both_a_tier_a_and_a_"
        f"tier_b_knob cannot see them"
    )


def test_an_undeclared_arm_is_still_refused() -> None:
    """Declaring arms must not have loosened resolution: an arm that silently fell back
    would let a run record a profile it never used (DEC-194, decision 2)."""
    from npc_engine.schema.retrieval_profile_models import resolve_retrieval_profile

    with pytest.raises(RetrievalProfileNotFoundError):
        resolve_retrieval_profile(
            "not_a_declared_arm", profiles=_shipped_profiles(), fallback=_default_profile()
        )


def test_the_default_name_still_resolves_without_being_declared() -> None:
    """'default' must stay resolvable without a YAML entry, or omitting it would make
    the engine unbootable (retrieval_profile_models.DEFAULT_RETRIEVAL_PROFILE_NAME)."""
    from npc_engine.schema.retrieval_profile_models import resolve_retrieval_profile

    resolved = resolve_retrieval_profile(
        "default", profiles=_shipped_profiles(), fallback=_default_profile()
    )
    assert resolved == _default_profile()
