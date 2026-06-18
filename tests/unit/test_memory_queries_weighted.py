"""
test_memory_queries_weighted.py — Pure-Python unit tests for the charge-weighted decay formula
and the CYPHER_DECAY_VIVIDNESS_WEIGHTED constant.

Does NOT: connect to Neo4j. No I/O.
"""

from __future__ import annotations

import pytest

from npc_engine.graph.memory_queries import CYPHER_DECAY_VIVIDNESS_WEIGHTED


# ---------------------------------------------------------------------------
# Formula parity tests (mirrors Cypher logic in Python)
# ---------------------------------------------------------------------------


def _weighted_decay_rate(charge: int, base_decay: int = 5, charge_divisor: int = 20) -> int:
    """Python mirror of the Cypher decay formula: max(1, base_decay - charge // charge_divisor)."""
    return max(1, base_decay - charge // charge_divisor)


def test_charge_divisor_formula_high_charge():
    """High emotional_charge (80) yields minimum decay rate of 1."""
    assert _weighted_decay_rate(80) == 1


def test_charge_divisor_formula_zero_charge():
    """Zero emotional_charge yields full base decay rate of 5."""
    assert _weighted_decay_rate(0) == 5


def test_charge_divisor_formula_mid_charge():
    """Mid emotional_charge (40) yields decay rate of 3."""
    assert _weighted_decay_rate(40) == 3


def test_cypher_constant_exists():
    """CYPHER_DECAY_VIVIDNESS_WEIGHTED must be a non-empty string."""
    assert isinstance(CYPHER_DECAY_VIVIDNESS_WEIGHTED, str)
    assert len(CYPHER_DECAY_VIVIDNESS_WEIGHTED.strip()) > 0
