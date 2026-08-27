"""
Module: arm_probe_client
Layer: evals (eval harness — not part of src/)
Purpose: HTTP access for the arm probe — assemble one arm's context through
         GET /v1/admin/debug/retrieval, and rehydrate/read the corpus.
Does NOT: decide gate outcomes, import npc_engine, or run an LLM.
Dependencies injected: base_url and api_key are arguments; httpx is the only client.
Used by: evals.arm_probe_gates.

WHY THE DEBUG ROUTE AND NOT A DIALOGUE TURN
Receipts exist on both paths — generation_collection.py sends
`include_context_receipt: True` and stores the parsed record. But a dialogue turn costs
an LLM generation, so 2 cases x 4 arms would be 8 generations at ~30-90s each, and the
probe's whole value is that it costs five minutes against the ten hours it can cancel.
The debug route runs the SAME `build_serialized_context_with_receipt` with the same
player_id, profile, session turns and cache parameters, and returns the same
`ContextReceipt` — with no generation.

WHAT THAT COSTS, RECORDED. The probe therefore does not exercise the dialogue engine's
degradation ladder, its legacy whole-context cache, or the prompt assembly that wraps the
context. Those are P10's to verify on the real run. What the probe DOES establish — that
two arms retrieve measurably different items, and that tier B is non-empty — is a
property of context assembly, which is exactly the layer this route calls.
"""

from __future__ import annotations

from typing import Any

import httpx

from arm_probe_models import ArmObservation, TierRow

__all__ = ["ProbeClient"]

_DEBUG_RETRIEVAL_PATH = "/v1/admin/debug/retrieval"
_REHYDRATE_PATH = "/v1/admin/vector-store/rehydrate"
_VECTOR_STORE_PATH = "/v1/admin/debug/vector-store"
_TIMEOUT_SECONDS = 120.0


def _to_observation(
    body: dict[str, Any], *, npc_id: str, query: str, arm: str | None
) -> ArmObservation:
    """Turn one debug-retrieval body into an ArmObservation.

    Args:
        body: Parsed JSON response.
        npc_id: NPC the assembly was for.
        query: Retrieval signal used.
        arm: Requested arm name, for the error message.
    Returns:
        The populated ArmObservation.
    Raises:
        ValueError: When no receipt is present — a cached assembly publishes none
            (DEC-195), and scoring a pairing without one compares nothing to nothing.
    """
    receipt = body.get("context_receipt")
    if not receipt:
        raise ValueError(
            f"no context receipt for arm={arm!r} npc_id={npc_id!r}: the assembly was "
            f"served from cache, so there is nothing to compare"
        )
    return ArmObservation(
        arm=str(body.get("retrieval_profile") or arm or "default"),
        npc_id=npc_id,
        query=query,
        item_keys=tuple(receipt.get("item_keys", ())),
        tier_spend=tuple(
            TierRow(tier=row["tier"], items=row["items"], tokens=row["tokens"])
            for row in receipt.get("tier_spend", ())
        ),
        total_tokens=int(receipt.get("total_tokens", 0)),
    )


class ProbeClient:
    """Thin authenticated client for the three admin routes the probe needs."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        """Bind the client to one engine.

        Args:
            base_url: Engine base URL, e.g. 'http://localhost:8000'.
            api_key: Admin API key.
        """
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=_TIMEOUT_SECONDS
        )

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._client.close()

    def __enter__(self) -> ProbeClient:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def observe(
        self, *, npc_id: str, query: str, player_id: str, arm: str | None
    ) -> ArmObservation:
        """Assemble one arm's context for one case and return what reached the model.

        Args:
            npc_id: NPC to assemble for.
            query: Player message used as the retrieval signal.
            player_id: Player the context is assembled for. Required by this probe, not
                optional: without it the three reputation slots are structurally empty.
            arm: Retrieval-profile name; None means the deployment default.

        Returns:
            The arm's ArmObservation.

        Raises:
            httpx.HTTPStatusError: On any non-2xx, including the 400 an undeclared arm
                produces. A probe that swallowed that would report "no difference".
            ValueError: When the engine returns no receipt — a cached assembly publishes
                none, and scoring a pairing without one would compare nothing to nothing.
        """
        params: dict[str, Any] = {"npc_id": npc_id, "query": query, "player_id": player_id}
        if arm is not None:
            params["retrieval_profile"] = arm
        response = self._client.get(f"{self._base_url}{_DEBUG_RETRIEVAL_PATH}", params=params)
        response.raise_for_status()
        return _to_observation(response.json(), npc_id=npc_id, query=query, arm=arm)

    def rehydrate(self) -> dict[str, Any]:
        """Reconcile embeddings until dry and load the store; return the CorpusReport."""
        response = self._client.post(f"{self._base_url}{_REHYDRATE_PATH}")
        response.raise_for_status()
        return dict(response.json()["data"])

    def corpus_fingerprint(self) -> dict[str, Any]:
        """Read corpus identity WITHOUT writing the store (include_sha=true)."""
        response = self._client.get(
            f"{self._base_url}{_VECTOR_STORE_PATH}", params={"include_sha": "true"}
        )
        response.raise_for_status()
        return dict(response.json()["data"])
