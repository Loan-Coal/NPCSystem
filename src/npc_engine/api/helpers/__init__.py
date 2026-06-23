"""
Package: helpers
Layer: api
Purpose: Per-route helper utilities for response shaping, error mapping, action classification, quest transitions, and graph warnings.
Public surface: OkEnvelope, ErrEnvelope, ok_response, error_response, graph_error_to_http, require_node, is_currency_action, has_valid_currency_payload, resolve_request_id, resolve_session_scope, resolve_currency_reason, relation_deltas_for_action, quest_error_status, quest_error_to_http, build_transition_meta, to_objective_inputs, emit_graph_warnings, attach_warnings_meta.
Does NOT: define routes, middleware, or dependency injection.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .route_helpers import (
    ErrEnvelope,
    OkEnvelope,
    error_response,
    graph_error_to_http,
    ok_response,
    require_node,
)
from .action_helpers import (
    has_valid_currency_payload,
    is_currency_action,
    relation_deltas_for_action,
    resolve_currency_reason,
    resolve_request_id,
    resolve_session_scope,
)
from .graph_warning_helpers import attach_warnings_meta, emit_graph_warnings
from .quest_helpers import (
    build_transition_meta,
    quest_error_status,
    quest_error_to_http,
    to_objective_inputs,
)

__all__ = [
    "OkEnvelope",
    "ErrEnvelope",
    "ok_response",
    "error_response",
    "graph_error_to_http",
    "require_node",
    "is_currency_action",
    "has_valid_currency_payload",
    "resolve_request_id",
    "resolve_session_scope",
    "resolve_currency_reason",
    "relation_deltas_for_action",
    "quest_error_status",
    "quest_error_to_http",
    "build_transition_meta",
    "to_objective_inputs",
    "emit_graph_warnings",
    "attach_warnings_meta",
]
