"""
Module: seed_http
Layer: data (tooling, not application code)
Purpose: HTTP helpers for the world seeder — issue GET/POST requests to the API,
         track success/skip/failure counts, and expose existence checks.
Does NOT: import any npc_engine application code.
Dependencies injected: base_url and api_key passed per call.
Used by: data.api_seeder
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Counter:
    """Mutable seed-run counters with print-on-record and abort helpers."""

    ok: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)

    def record(self, label: str, status: int) -> None:
        """Record an API call result and print one line of output."""
        if 200 <= status < 300:
            self.ok += 1
            print(f"  [OK]   {label}")
        elif status == 409:
            self.skipped += 1
            print(f"  [SKIP] {label} (already exists)")
        else:
            self.failed += 1
            self.failures.append(f"{label} (HTTP {status})")
            print(f"  [FAIL] {label} (HTTP {status})")

    def abort_if_failed(self) -> None:
        """Raise SystemExit when any hard failure has occurred."""
        if self.failed:
            print(f"\nAborting: {self.failed} failure(s): {self.failures}")
            sys.exit(1)

    def summary(self) -> int:
        """Print totals and return exit code (0 = success, 1 = any failure)."""
        total = self.ok + self.skipped + self.failed
        print(f"\n{self.ok} created, {self.skipped} skipped, {self.failed} failed / {total} total")
        return 1 if self.failed else 0


def call(method: str, url: str, api_key: str, body: dict | None = None) -> tuple[int, Any]:
    """Execute an HTTP request and return (status_code, parsed_body).

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Full request URL.
        api_key: Bearer token for authentication.
        body: Optional JSON-serializable request body.

    Returns:
        Tuple of (HTTP status code, parsed JSON body or empty dict on error).
    """
    data = json.dumps(body).encode() if body is not None else None
    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


def post_node(base: str, api_key: str, node_type: str, props: dict) -> int:
    """POST a node upsert; returns HTTP status."""
    status, _ = call("POST", f"{base}/v1/graph/nodes/{node_type}", api_key, {"properties": props})
    return status


def post_edge(base: str, api_key: str, edge_type: str, src: str, dst: str, props: dict | None = None) -> int:
    """POST an edge upsert; returns HTTP status."""
    body: dict[str, Any] = {"src_id": src, "dst_id": dst, "properties": props or {}}
    status, _ = call("POST", f"{base}/v1/graph/edges/{edge_type}", api_key, body)
    return status


def node_exists(base: str, api_key: str, node_type: str, node_id: str) -> bool:
    """Return True when a node with the given type and stable id already exists.

    Uses GET /v1/graph/nodes/{node_type}/{node_id}.  Any non-200 response
    (including 404) is treated as "does not exist".
    """
    status, _ = call("GET", f"{base}/v1/graph/nodes/{node_type}/{node_id}", api_key)
    return status == 200


def faction_exists(base: str, api_key: str, faction_id: str) -> bool:
    """Return True when the faction with the given stable id already exists.

    Uses GET /v1/admin/factions/{faction_id}.  Any non-200 response is treated
    as "does not exist".
    """
    status, _ = call("GET", f"{base}/v1/admin/factions/{faction_id}", api_key)
    return status == 200


def edge_exists(base: str, api_key: str, edge_type: str, src: str, dst: str) -> bool:
    """Return True when the directed edge between src and dst already exists.

    Uses GET /v1/graph/edges/{edge_type}?src_id={src}&dst_id={dst}.  Any
    non-200 response is treated as "does not exist".
    """
    url = f"{base}/v1/graph/edges/{edge_type}?src_id={src}&dst_id={dst}"
    status, _ = call("GET", url, api_key)
    return status == 200
