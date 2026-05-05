# Patterns Log

Reusable code and design patterns discovered during development. A pattern is
worth recording when it has been applied at least twice and would be worth
applying again.

Rules:
- Append-only.
- Each pattern has a short name, a "when to use" description, a "why" justification,
  and a minimal runnable example.
- If a pattern is superseded, mark it as `[SUPERSEDED]` and link to the replacement.
  Do not delete.

---

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
