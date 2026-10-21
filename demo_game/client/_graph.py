"""
Module: client._graph
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Generic graph CRUD methods: list edges, single-item node/edge reads and writes.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

from demo_game.client._base import EngineClientBase


class _GraphMixin(EngineClientBase):
    """Mixin providing generic graph read/write methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

    def get_graph_edges(
        self,
        edge_type: str,
        limit: int = 100,
        offset: int = 0,
        src_id: str | None = None,
        dst_id: str | None = None,
    ) -> list[dict]:
        """Return edges of a registered type with optional source/destination filter.

        Args:
            edge_type: Registered edge type, e.g. "KNOWS_ABOUT", "STANDS_WITH".
            limit: Maximum number of results.
            offset: Pagination offset.
            src_id: Optional filter by source node ID.
            dst_id: Optional filter by destination node ID.

        Returns:
            List of edge property dicts from the response data field.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        params: dict = {"limit": limit, "offset": offset}
        if src_id is not None:
            params["src_id"] = src_id
        if dst_id is not None:
            params["dst_id"] = dst_id
        resp = self._client.get(
            f"/v1/graph/edges/{edge_type}",
            params=params,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/graph/edges/{edge_type}")
        return resp.json().get("data", [])

    def get_node(self, node_type: str, node_id: str) -> dict | None:
        """Return one node by type and id, or None if it does not exist.

        Args:
            node_type: Registered node type, e.g. "Location", "Character".
            node_id: Node ID to fetch.

        Returns:
            Node property dict, or None if the node was not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/nodes/{node_type}/{node_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/graph/nodes/{node_type}/{node_id}")
        return resp.json().get("data")

    def get_edge(self, edge_type: str, src_id: str, dst_id: str) -> dict | None:
        """Return one edge by type, source and destination, or None if absent.

        Args:
            edge_type: Registered edge type, e.g. "STANDS_WITH", "OPPOSES".
            src_id: Source node ID.
            dst_id: Destination node ID.

        Returns:
            Edge property dict, or None if the edge was not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/edges/{edge_type}/{src_id}/{dst_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/graph/edges/{edge_type}/{src_id}/{dst_id}")
        return resp.json().get("data")

    def patch_node(self, node_type: str, node_id: str, properties: dict) -> dict | None:
        """Partially update a node; returns the updated node dict or None on 404.

        Args:
            node_type: Registered node type, e.g. "Character".
            node_id: Node ID to patch.
            properties: Partial property dict; only supplied fields are updated.

        Returns:
            Node property dict reflecting the state after the patch, or None if not found.

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.patch(
            f"/v1/graph/nodes/{node_type}/{node_id}",
            json={"properties": properties},
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"PATCH /v1/graph/nodes/{node_type}/{node_id}")
        return resp.json().get("data")

    def upsert_node(self, node_type: str, properties: dict) -> dict:
        """Upsert a node via the generic graph endpoint.

        Args:
            node_type: Registered node type, e.g. "Location", "Faction".
            properties: Property dict including the node's id field.

        Returns:
            Full API response dict (includes data and meta).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/graph/nodes/{node_type}",
            json={"properties": properties},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/graph/nodes/{node_type}")
        return resp.json()

    def upsert_edge(
        self,
        edge_type: str,
        src_id: str,
        dst_id: str,
        properties: dict | None = None,
    ) -> dict:
        """Upsert an edge between two nodes via the generic graph endpoint.

        Args:
            edge_type: Registered edge type, e.g. "STANDS_WITH", "MEMBER_OF".
            src_id: Source node ID.
            dst_id: Destination node ID.
            properties: Optional edge properties (e.g. standing, role).

        Returns:
            Full API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/graph/edges/{edge_type}",
            json={"src_id": src_id, "dst_id": dst_id, "properties": properties or {}},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/graph/edges/{edge_type}")
        return resp.json()
