# Interface: utils

Layer: config (no project dependencies)

## errors.py

All exceptions inherit `StructuredNPCSystemError` → `NPCSystemError` → `Exception`.
All are `@dataclass(frozen=True)` — immutable after construction.

```python
class NPCSystemError(Exception): ...
class StructuredNPCSystemError(NPCSystemError):
    def __str__(self) -> str: ...  # "ClassName(field=value, ...)"

@dataclass(frozen=True)
class AuthError(StructuredNPCSystemError):
    reason: str

@dataclass(frozen=True)
class GraphUnavailableError(StructuredNPCSystemError):
    uri: str
    cause: str

@dataclass(frozen=True)
class LLMTimeoutError(StructuredNPCSystemError):
    model: str
    timeout_s: float

@dataclass(frozen=True)
class LLMRequestError(StructuredNPCSystemError):
    model: str
    detail: str

@dataclass(frozen=True)
class RelationEdgeNotFoundError(StructuredNPCSystemError):
    src_id: str
    dst_id: str

@dataclass(frozen=True)
class SchemaMisconfiguredError(StructuredNPCSystemError):
    schema_path: str
    detail: str

@dataclass(frozen=True)
class SchemaValidationError(StructuredNPCSystemError):
    schema_path: str
    detail: str

@dataclass(frozen=True)
class RegistryValidationError(StructuredNPCSystemError):
    source: str
    detail: str

@dataclass(frozen=True)
class RegistryPayloadValidationError(StructuredNPCSystemError):
    code: str
    detail: str

@dataclass(frozen=True)
class NodeNotFoundError(StructuredNPCSystemError):
    node_type: str
    node_id: str

@dataclass(frozen=True)
class ImmutableFieldError(StructuredNPCSystemError):
    field_name: str
    node_type: str

@dataclass(frozen=True)
class IdempotencyKeyRequiredError(StructuredNPCSystemError):
    header_name: str

@dataclass(frozen=True)
class IdempotencyKeyInvalidError(StructuredNPCSystemError):
    header_name: str
    value: str

@dataclass(frozen=True)
class LLMConfigMisconfiguredError(StructuredNPCSystemError):
    config_path: str
    detail: str

@dataclass(frozen=True)
class LLMConfigValidationError(StructuredNPCSystemError):
    config_path: str
    detail: str

@dataclass(frozen=True)
class ContractValidationError(StructuredNPCSystemError):
    contract_path: str
    detail: str

@dataclass(frozen=True)
class CurrencyValidationError(StructuredNPCSystemError):
    code: str
    detail: str

@dataclass(frozen=True)
class CurrencyInsufficientFundsError(StructuredNPCSystemError):
    source_id: str
    amount: int
    available_balance: int

@dataclass(frozen=True)
class ItemTransferValidationError(StructuredNPCSystemError):  # was mutable — FIXED
    code: str
    detail: str

@dataclass(frozen=True)
class QuestTransitionError(StructuredNPCSystemError):  # was mutable — FIXED
    code: str
    detail: str

@dataclass(frozen=True)
class QuestProvenanceError(StructuredNPCSystemError):  # was mutable — FIXED
    detail: str
```

Deferred to other services: `RelationDeltaExceededError` (lives in mutation/),
`TokenBudgetExceededError` and `ContextBudgetError` (live in retrieval/).
Will be moved to errors.py when those services are refactored.

## logging.py

```python
LOGGER_NAME: str  # = "npc_engine"

def configure_logging(level: str) -> None: ...
def get_logger(name: str = LOGGER_NAME) -> logging.Logger: ...
```

NOT allowed: direct logging.getLogger() calls outside of get_logger().

## metrics.py

```python
def increment_metric(metric: str, amount: float = 1.0, labels: Mapping[str, str] | None = None) -> None: ...
def observe_metric(metric: str, value: float, labels: Mapping[str, str] | None = None) -> None: ...
def get_counter_value(metric: str, labels: Mapping[str, str] | None = None) -> float: ...
def reset_metrics_registry() -> None: ...
def get_metrics_registry() -> MetricsRegistry: ...
def route_label_from_path(path: str, api_v1_prefix: str) -> str: ...
def result_label_from_status(status_code: int) -> str: ...
```

NOT allowed: exposing raw MetricsRegistry internals outside this module for anything other than tests.
