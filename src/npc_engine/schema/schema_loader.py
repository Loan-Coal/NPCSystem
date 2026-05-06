"""
schema_loader.py - Loads and validates game schema configuration from YAML.

Does NOT: mutate runtime graph state.

Dependencies injected: None.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.utils.errors import SchemaMisconfiguredError, SchemaValidationError


SCHEMA_VERSION_V1 = "1.0"


def load_game_schema(schema_path: str) -> SchemaConfig:
    """Load schema file and validate it against the schema meta-model.

    Args:
        schema_path: str — filesystem path to the game_schema.yaml file.

    Returns:
        Validated SchemaConfig instance.

    Raises:
        SchemaMisconfiguredError: if the file does not exist or cannot be read.
        SchemaValidationError: if the YAML root is not a mapping, the YAML is malformed,
            the Pydantic validation fails, or the schema_version is unsupported.
    """

    path = Path(schema_path)
    if not path.exists():
        raise SchemaMisconfiguredError(
            schema_path=schema_path,
            detail="schema file does not exist",
        )

    try:
        loaded = load_yaml_mapping(path=path, root_error_message="schema root must be a YAML object")
    except (OSError, UnicodeError) as error:
        raise SchemaMisconfiguredError(schema_path=schema_path, detail=str(error)) from error
    except (ValueError, yaml.YAMLError) as error:
        raise SchemaValidationError(schema_path=schema_path, detail=str(error)) from error

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
