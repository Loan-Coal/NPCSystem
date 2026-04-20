"""
extension_loader.py - Resolves and validates registry extension YAML documents.

Does NOT: apply merge policies or build runtime registry state.

Dependencies injected: extension source paths.
"""

from dataclasses import dataclass
import glob
from pathlib import Path

import yaml
from pydantic import ValidationError

from common.yaml_utils import load_yaml_mapping
from type_registry.contracts import RegistryExtensionDocument
from utils.errors import RegistryValidationError


GLOB_META_CHARACTERS = {"*", "?", "["}


@dataclass(frozen=True)
class LoadedRegistryExtension:
    """Validated extension document paired with its source path."""

    source_path: str
    document: RegistryExtensionDocument


def load_registry_extensions(extension_sources: tuple[str, ...]) -> tuple[LoadedRegistryExtension, ...]:
    """Load and validate extension YAML documents from configured source paths."""

    paths = _resolve_extension_paths(extension_sources=extension_sources)
    loaded_documents: list[LoadedRegistryExtension] = []
    for path in paths:
        loaded_documents.append(_load_one_extension(path=path))
    return tuple(loaded_documents)


def _resolve_extension_paths(extension_sources: tuple[str, ...]) -> tuple[Path, ...]:
    """Resolve explicit file paths and glob patterns into concrete extension files."""

    if not extension_sources:
        return tuple()

    resolved_paths: list[Path] = []
    for source in extension_sources:
        source_value = source.strip()
        if not source_value:
            continue
        resolved_paths.extend(_resolve_one_source(source_value=source_value))

    unique_paths: dict[str, Path] = {}
    for path in resolved_paths:
        unique_paths[str(path.resolve())] = path.resolve()
    return tuple(unique_paths.values())


def _resolve_one_source(source_value: str) -> list[Path]:
    """Resolve one source item (file or glob) into concrete paths."""

    if any(character in source_value for character in GLOB_META_CHARACTERS):
        matches = [Path(match) for match in sorted(glob.glob(source_value, recursive=True))]
        if not matches:
            raise RegistryValidationError(source=source_value, detail="extension source pattern matched no files")
        return matches

    path = Path(source_value)
    if not path.exists():
        raise RegistryValidationError(source=source_value, detail="extension file does not exist")
    return [path]


def _load_one_extension(path: Path) -> LoadedRegistryExtension:
    """Load one extension file as a validated registry extension document."""

    source_path = str(path.resolve())
    try:
        loaded = load_yaml_mapping(path=path, root_error_message="registry extension root must be a YAML object")
    except (OSError, UnicodeError) as error:
        raise RegistryValidationError(source=source_path, detail=str(error)) from error
    except (ValueError, yaml.YAMLError) as error:
        raise RegistryValidationError(source=source_path, detail=str(error)) from error

    try:
        document = RegistryExtensionDocument.model_validate(loaded)
    except ValidationError as error:
        raise RegistryValidationError(source=source_path, detail=str(error)) from error

    return LoadedRegistryExtension(source_path=source_path, document=document)
