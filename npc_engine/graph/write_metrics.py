"""
write_metrics.py - Graph write operation metric helpers.

Does NOT: execute graph queries or manage transactions.

Dependencies injected: None.
"""

from time import perf_counter

from utils.metrics import increment_metric, observe_metric


GRAPH_WRITES_METRIC = "graph_writes_total"
GRAPH_WRITE_LATENCY_METRIC = "graph_write_latency_seconds"
CURRENCY_TRANSFERS_METRIC = "currency_transfers_total"


def record_graph_write_metrics(*, operation: str, result: str, started_at: float) -> None:
    """Record graph write count and latency with bounded operation labels.

    Args:
        operation: Label identifying the write operation type (e.g. "relation_delta").
        result: Outcome label, either "success" or "failure".
        started_at: ``perf_counter()`` timestamp captured before the operation began.
    """
    labels = {"operation": operation, "result": result}
    increment_metric(metric=GRAPH_WRITES_METRIC, labels=labels)
    observe_metric(metric=GRAPH_WRITE_LATENCY_METRIC, value=perf_counter() - started_at, labels=labels)
