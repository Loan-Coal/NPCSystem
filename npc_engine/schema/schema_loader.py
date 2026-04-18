"""
schema_loader.py - Loads and validates game schema configuration from YAML.

Does NOT: mutate runtime graph state.

Dependencies injected: None.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from schema.schema_models import SchemaConfig
from utils.errors import SchemaMisconfiguredError, SchemaValidationError


SCHEMA_VERSION_V1 = "1.0"


def load_game_schema(schema_path: str) -> SchemaConfig:
    """Load schema file and validate it against the schema meta-model."""

    path = Path(schema_path)
    if not path.exists():
        raise SchemaMisconfiguredError(
            schema_path=schema_path,
            detail="schema file does not exist",
        )

    try:
        loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise SchemaValidationError(schema_path=schema_path, detail=str(error)) from error

    if not isinstance(loaded, dict):
        raise SchemaValidationError(
            schema_path=schema_path,
            detail="schema root must be a YAML object",
        )

    try:
        schema = SchemaConfig.model_validate(loaded)
    except ValidationError as error:
        raise SchemaValidationError(schema_path=schema_path, detail=str(error)) from error

    if schema.schema_version != SCHEMA_VERSION_V1:
        raise SchemaValidationError(
            schema_path=schema_path,
            detail=f"unsupported schema_version: {schema.schema_version}",
        )

    return schema
