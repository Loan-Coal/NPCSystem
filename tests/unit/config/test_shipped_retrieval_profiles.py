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
ISSUE-184). A subtle arm cannot clear that floor, so the first arms are deliberately
drastic — skip retrieval entirely, or triple every top-k — chosen to produce an effect
the instrument can actually see, or to prove there is none.
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
_DECLARED_ARMS: tuple[tuple[str, str], ...] = (
    ("no_rag", "skip_rag"),
    ("wide_rag", "rag_top_k"),
)


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

    graph_rag_top_k and events_limit are allowed to move WITH rag_top_k: DEC-194 split
    them apart precisely so they need not, but a 'wider retrieval' arm that widened
    only the vector search would not be the arm it claims to be. They are treated as
    one knob here and named as such.
    """
    top_k_group = {"rag_top_k", "graph_rag_top_k", "events_limit"}
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


def test_the_wide_rag_arm_is_a_large_multiple_of_the_default_top_k() -> None:
    """A 6 vs 5 arm would be indistinguishable from noise at this dataset's resolution.
    Requiring at least a doubling keeps the declared arm honest about that."""
    wide = _shipped_profiles()["wide_rag"]
    assert wide.rag_top_k >= 2 * _DEFAULT_RAG_TOP_K
    assert wide.graph_rag_top_k >= 2 * _DEFAULT_RAG_TOP_K
    assert wide.events_limit >= 2 * _DEFAULT_RAG_TOP_K


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
