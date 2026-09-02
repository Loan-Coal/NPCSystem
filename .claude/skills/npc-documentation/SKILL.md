---
name: npc-documentation
description: NPC Engine docstring formats — module, function, class and __init__.py. Load before writing a new Python file or a new public function.
---

# NPC Engine — documentation

Binding (DEC-249). `project-harness/CLAUDE.md` names each rule in one line and points here.
Gated by `make check-docstrings`.

Documentation is mandatory. The `__init__.py` debugging incident happened because
this rule was implicit. It is explicit now.

### Every Python file requires:

1. **Module docstring** at the top, in this format:

```python
"""
Module: <name>
Layer: <api | engines | services | retrieval | graph | config>
Purpose: One sentence describing what this module does.
Dependencies: Which other modules this imports from.
Used by: Which other modules import from this.
"""
```

2. **Function docstrings** on every public function (one-line is acceptable for
   simple functions; multi-line for anything with non-obvious behavior). Format:

```python
def my_function(arg: str) -> int:
    """One-line summary.

    Args:
        arg: Description.
    Returns:
        Description.
    Raises:
        SomeError: When this happens.
    """
```

3. **Class docstrings** on every class.

### `__init__.py` files

These count as files. They get a docstring too, even if they are empty re-exports.
Format:

```python
"""
Package: <name>
Layer: <layer>
Purpose: One sentence describing what this package contains.
Public surface: List the names re-exported from this package.
"""
```

### What does NOT need documentation

- Private functions (leading underscore) with self-evident names. Leading-underscore
  functions are allowed to skip the docstring if and only if the function is shorter
  than 10 lines and the name is self-explanatory.
- Test functions (the test name is the documentation).
- Trivial property getters/setters.

If you are unsure whether a function needs a docstring, write one. The cost of a
one-line docstring is far less than the cost of forgetting one.
