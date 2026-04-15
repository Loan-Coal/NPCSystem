"""
test_architecture_conformance.py - Enforces core architecture constraints.

Does NOT: validate runtime business behavior.

Dependencies injected: None.
"""

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _python_files() -> list[Path]:
    return [
        path
        for path in PROJECT_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts
    ]


def test_all_python_files_have_module_docstring_contract() -> None:
    """Every module must include scope and dependency docstring fields."""

    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        assert text.startswith('"""'), f"Missing module docstring in {path}"
        assert "Does NOT:" in text, f"Missing scope boundary in {path}"
        assert "Dependencies injected:" in text, f"Missing dependency declaration in {path}"


def test_no_wildcard_imports() -> None:
    """Wildcard imports are banned across the codebase."""

    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        wildcard_import_pattern = re.compile(r"^\s*(from\s+\S+\s+import\s+\*)", re.MULTILINE)
        assert wildcard_import_pattern.search(text) is None, f"Wildcard import found in {path}"


def test_engines_do_not_import_concrete_llm_adapters() -> None:
    """Engine modules must depend on abstractions, not concrete adapters."""

    engines_dir = PROJECT_ROOT / "engines"
    if not engines_dir.exists():
        return

    for path in engines_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "factory.py":
            continue
        if path.parent.name == "llm" and path.name.endswith("_adapter.py"):
            continue
        banned_imports = (
            "mistral_adapter",
            "llama_adapter",
            "openai_adapter",
        )
        for banned_import in banned_imports:
            assert banned_import not in text, f"Concrete adapter import found in {path}"
