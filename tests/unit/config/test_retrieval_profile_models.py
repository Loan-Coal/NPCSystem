"""
Module: tests.unit.config.test_retrieval_profile_models
Layer: test (unit)
Purpose: Contract tests for RetrievalProfile and its STRICT resolution. The profile is
         the A/B switch for context experiments, so the binding property is that an
         unknown profile name is an error, never a silent fallback.
Dependencies: pytest; npc_engine.schema.retrieval_profile_models; npc_engine.utils.errors
Used by: make test (pytest discovery)

Why strictness is the headline test. LLMConfig.resolve_weights() deliberately falls back
to defaults on an unknown profile name, which is right for weights. Reusing that behaviour
here would let a run record `retrieval_profile="aggressive"` while actually having used the
default — an arm claiming a variant it never ran. That is the exact class of defect the
eval programme exists to catch, so it is pinned here rather than left to review.
"""

from __future__ import annotations

import pytest

from npc_engine.schema.retrieval_profile_models import (
    DEFAULT_RETRIEVAL_PROFILE_NAME,
    RetrievalProfile,
    build_default_profile,
    resolve_retrieval_profile,
)
from npc_engine.utils.errors import RetrievalProfileNotFoundError


def _profile(**overrides: object) -> RetrievalProfile:
    base: dict[str, object] = {
        "weight_profile": None,
        "rag_top_k": 5,
        "graph_rag_top_k": 5,
        "events_limit": 5,
        "cross_encoder_enabled": False,
        "skip_rag": False,
    }
    base.update(overrides)
    return RetrievalProfile(**base)  # type: ignore[arg-type]


def test_profile_is_frozen() -> None:
    # quality-ok: pydantic v2 frozen models raise ValidationError; the assertion is "any mutation is rejected"
    with pytest.raises(Exception):
        _profile().rag_top_k = 99  # type: ignore[misc]


def test_unknown_profile_name_raises_rather_than_falling_back() -> None:
    """The binding contract: a name nobody defined is an error, not the default.

    A silent fallback would let an arm record a profile it never used.
    """
    fallback = _profile()
    with pytest.raises(RetrievalProfileNotFoundError) as excinfo:
        resolve_retrieval_profile("no_such_profile", profiles={}, fallback=fallback)

    assert "no_such_profile" in str(excinfo.value)


def test_unknown_name_raises_even_when_other_profiles_exist() -> None:
    """A populated registry must not make a typo resolve to something plausible."""
    with pytest.raises(RetrievalProfileNotFoundError):
        resolve_retrieval_profile(
            "aggresive",  # deliberate typo of a real name
            profiles={"aggressive": _profile(rag_top_k=20)},
            fallback=_profile(),
        )


def test_known_profile_resolves_to_its_own_values() -> None:
    wanted = _profile(rag_top_k=20, cross_encoder_enabled=True)
    resolved = resolve_retrieval_profile("aggressive", profiles={"aggressive": wanted}, fallback=_profile())

    assert resolved == wanted


def test_default_name_resolves_to_the_fallback_without_being_registered() -> None:
    """`default` is always resolvable — it is what production runs with no override,
    and requiring it to be declared in YAML would make the engine unbootable."""
    fallback = _profile(rag_top_k=7)
    resolved = resolve_retrieval_profile(DEFAULT_RETRIEVAL_PROFILE_NAME, profiles={}, fallback=fallback)

    assert resolved == fallback


def test_none_name_resolves_to_the_fallback() -> None:
    """No profile requested is not an error — it is the default path."""
    fallback = _profile(rag_top_k=7)

    assert resolve_retrieval_profile(None, profiles={}, fallback=fallback) == fallback


def test_build_default_profile_maps_one_top_k_onto_all_three_call_sites() -> None:
    """RAG_TOP_K currently drives graph RAG, vector search AND event fetching
    (context_builder.py:241-252). The profile splits them, but the DEFAULT must
    reproduce today's behaviour exactly or this becomes an engine change."""
    built = build_default_profile(rag_top_k=5, cross_encoder_enabled=False)

    assert built.rag_top_k == 5
    assert built.graph_rag_top_k == 5
    assert built.events_limit == 5
    assert built.cross_encoder_enabled is False
    assert built.skip_rag is False
    assert built.weight_profile is None


def test_the_three_top_k_fields_are_independent() -> None:
    """The point of the split: a top-k experiment must not silently change event fetching."""
    p = _profile(rag_top_k=20, graph_rag_top_k=3, events_limit=5)

    assert (p.rag_top_k, p.graph_rag_top_k, p.events_limit) == (20, 3, 5)


@pytest.mark.parametrize("field", ["rag_top_k", "graph_rag_top_k", "events_limit"])
def test_top_k_fields_reject_non_positive_values(field: str) -> None:
    """build_serialized_context already raises on RAG_TOP_K <= 0; the profile refuses earlier."""
    # quality-ok: pydantic v2 raises ValidationError; the assertion is "the value is rejected"
    with pytest.raises(Exception):
        _profile(**{field: 0})


def test_profile_rejects_unknown_fields() -> None:
    """extra='forbid' so a mistyped YAML key is a startup error, not a silently ignored knob."""
    # quality-ok: pydantic v2 raises ValidationError; the assertion is "the key is rejected"
    with pytest.raises(Exception):
        _profile(cross_encodr_enabled=True)


# ---------------------------------------------------------------------------
# A2 — the registry on LLMConfig and the Settings default
# ---------------------------------------------------------------------------


def test_settings_declares_a_default_retrieval_profile() -> None:
    """Production must have ONE declared configuration, so ops can answer
    'what is the engine running as' without reading request logs."""
    from npc_engine.config import Settings

    settings = Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
    )

    assert settings.RETRIEVAL_PROFILE == DEFAULT_RETRIEVAL_PROFILE_NAME


def test_llm_config_carries_a_retrieval_profile_registry() -> None:
    """Profiles are declared in the engine's llm_config.yaml, beside weight_profiles."""
    from tests.unit.retrieval.test_context_builder import _llm_config

    cfg = _llm_config()

    assert cfg.retrieval_profiles == {}


def test_llm_config_resolution_is_strict_unlike_resolve_weights() -> None:
    """The contrast that matters, asserted directly rather than left to review:
    resolve_weights() falls back for an unknown name; retrieval profiles must not."""
    from tests.unit.retrieval.test_context_builder import _llm_config

    cfg = _llm_config()
    fallback = _profile()

    # resolve_weights is lenient by design — this is the behaviour NOT to copy.
    assert cfg.resolve_weights("no_such_weight_profile") == cfg.relevance_weights

    with pytest.raises(RetrievalProfileNotFoundError):
        cfg.resolve_retrieval_profile("no_such_retrieval_profile", fallback=fallback)
