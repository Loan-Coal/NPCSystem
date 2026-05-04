# Reusable Patterns

_(Populated as refactor proceeds. Append only. Use dated headers.)_

## 2026-05-01

## Pattern: Frozen Exception Dataclasses
**When to use:** Every domain exception in this codebase.
**Why:** Exceptions are value objects — they carry diagnostic context and are never modified after construction. `frozen=True` enforces STRUCT-06 (immutability) and enables hashing/equality comparisons in test assertions.
**Example:**
```python
from dataclasses import dataclass
from utils.errors import StructuredNPCSystemError

@dataclass(frozen=True)
class MyServiceError(StructuredNPCSystemError):
    """Raised when X violates Y."""
    code: str
    detail: str
```
**First applied in:** utils (service #1)
