"""
enum_validator.py - Builds merged enum value sets from base and schema extensions.
Layer: config
Purpose: Builds merged enum value sets from base and schema extensions.

Does NOT: validate API requests directly.

Dependencies injected: SchemaConfig.
"""
from __future__ import annotations

from dataclasses import dataclass

from npc_engine.schema.schema_models import SchemaConfig


BASE_EVENT_TYPES = {"crime", "battle", "trade", "discovery"}
BASE_PARTICIPATION_ROLES = {"perpetrator", "victim", "witness", "bystander"}


@dataclass(frozen=True)
class EnumValueSet:
    """Merged accepted enum values used by validators."""

    event_type: frozenset[str]
    participation_role: frozenset[str]


def build_enum_values(schema: SchemaConfig) -> EnumValueSet:
    """Merge base enum values with schema-defined extensions.

    Args:
        schema: SchemaConfig — the loaded and validated game schema.

    Returns:
        EnumValueSet with frozensets of accepted event_type and participation_role values.
    """

    event_type = frozenset(BASE_EVENT_TYPES.union(schema.enum_extensions.event_type))
    participation_role = frozenset(
        BASE_PARTICIPATION_ROLES.union(schema.enum_extensions.participation_role)
    )
    return EnumValueSet(event_type=event_type, participation_role=participation_role)
