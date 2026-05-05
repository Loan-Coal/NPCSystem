"""
model_factory.py - Produces runtime Pydantic models from npc_engine.schema extension fields.

Does NOT: persist model instances.

Dependencies injected: SchemaConfig.
"""

from typing import Any

from pydantic import BaseModel, Field, create_model

from npc_engine.schema.schema_models import ExtensionField, SchemaConfig


TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


def _build_field(field_config: ExtensionField) -> tuple[Any, Any]:
    """Build dynamic model field definition from extension metadata."""

    field_type = TYPE_MAP[field_config.type]
    default = field_config.default

    if field_config.type in {"int", "float"} and field_config.range is not None:
        lower, upper = field_config.range
        return field_type, Field(default=default, ge=lower, le=upper)

    return field_type, Field(default=default)


def generate_runtime_models(schema: SchemaConfig) -> dict[str, type[BaseModel]]:
    """Generate one dynamic Pydantic model per core type with extension fields.

    Args:
        schema: SchemaConfig — the loaded and validated game schema.

    Returns:
        Dict mapping core type name to a dynamically generated Pydantic BaseModel subclass
        whose fields correspond to the type's extension_fields with range constraints applied.
    """

    models: dict[str, type[BaseModel]] = {}
    for type_name, type_config in schema.core_types.items():
        fields: dict[str, Any] = {
            field_name: _build_field(field_config)
            for field_name, field_config in type_config.extension_fields.items()
        }
        model_name = f"{type_name.title()}ExtensionModel"
        models[type_name] = create_model(model_name, **fields)
    return models
