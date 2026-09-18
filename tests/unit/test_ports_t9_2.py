"""
Module: test_ports_t9_2
Layer: tests
Purpose: Structural guard for T9.2 — verifies the god-port QuestGenerationGraphPort
         has been split into role-specific protocols, no method is redeclared
         across the quest_port sibling protocols, and no port imports a
         private (underscore-prefixed) graph type.
RED anchor: QuestGenerationGraphPort still exists before the split — test fails.
GREEN: god-port removed, role protocols present, no private-type imports.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path


_PORTS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "ports"
)


# ---------------------------------------------------------------------------
# 1.  God-port removed; role-specific protocols present
# ---------------------------------------------------------------------------

def test_quest_generation_god_port_removed() -> None:
    """QuestGenerationGraphPort must be absent after the T9.2 split."""
    mod = importlib.import_module("npc_engine.engines.ports.quest_generation_port")
    assert not hasattr(mod, "QuestGenerationGraphPort"), (
        "QuestGenerationGraphPort (god-port, 10 methods, 2 consumers) still present. "
        "T9.2 requires splitting it into QuestContextGraphPort and SlotValidationGraphPort."
    )


def test_quest_context_and_slot_validation_protocols_present() -> None:
    """QuestContextGraphPort and SlotValidationGraphPort must be present after the split."""
    mod = importlib.import_module("npc_engine.engines.ports.quest_generation_port")
    assert hasattr(mod, "QuestContextGraphPort"), "QuestContextGraphPort missing from quest_generation_port"
    assert hasattr(mod, "SlotValidationGraphPort"), "SlotValidationGraphPort missing from quest_generation_port"


# ---------------------------------------------------------------------------
# 2.  No method redeclared across the four quest_port sibling protocols
# ---------------------------------------------------------------------------

def test_quest_port_no_redeclared_methods() -> None:
    """No method may be declared directly in more than one of the four quest_port protocols.

    Inherited methods (from shared mixin bases) are counted once on the mixin, not on
    each inheritor, so Protocol inheritance is the correct fix.
    """
    mod = importlib.import_module("npc_engine.engines.ports.quest_port")
    protocol_names = [
        "QuestLifecycleGraphPort",
        "QuestOfferGraphPort",
        "QuestRewardGraphPort",
        "QuestChainGraphPort",
    ]
    seen: dict[str, str] = {}
    for proto_name in protocol_names:
        proto = getattr(mod, proto_name, None)
        assert proto is not None, f"{proto_name} missing from quest_port"
        # vars() returns only directly-defined members, not inherited ones.
        for name, member in vars(proto).items():
            if name.startswith("_"):
                continue
            if not callable(member):
                continue
            if name in seen:
                raise AssertionError(
                    f"Method '{name}' is directly declared in both {seen[name]} and "
                    f"{proto_name}. Extract it into a shared mixin protocol."
                )
            seen[name] = proto_name


# ---------------------------------------------------------------------------
# 3.  No private (underscore-prefixed) graph type imported by any port
# ---------------------------------------------------------------------------

def test_no_private_graph_type_imported_by_ports() -> None:
    """No port file may import a private (underscore-prefixed) type from npc_engine.graph."""
    port_files = list(_PORTS_DIR.glob("*.py"))
    assert port_files, "ports directory is empty — check path"
    violations: list[str] = []
    for path in port_files:
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("from npc_engine.graph"):
                continue
            # Extract the imported names after "import"
            if " import " in stripped:
                names_part = stripped.split(" import ", 1)[1]
                names = [n.strip().split(" as ")[0].strip() for n in names_part.split(",")]
                for name in names:
                    if name.startswith("_"):
                        violations.append(f"{path.name}: {stripped}")
    assert not violations, (
        "Port files import private (underscore-prefixed) graph types:\n"
        + "\n".join(violations)
    )
