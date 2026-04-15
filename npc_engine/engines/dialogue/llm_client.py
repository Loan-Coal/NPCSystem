"""
llm_client.py - Thin wrapper for dialogue structured generation with timeout fallback.

Does NOT: build prompts or mutate graph state.

Dependencies injected: LLMClientProtocol.
"""

import json
from pathlib import Path

from api.schemas import DialogueResponse
from engines.llm.protocols import LLMClientProtocol
from utils.errors import LLMRequestError, LLMTimeoutError


class DialogueLLMClient:
    """Dialogue-oriented structured LLM client wrapper."""

    def __init__(self, llm_client: LLMClientProtocol, fallback_path: str):
        self._llm_client = llm_client
        self._fallback_path = fallback_path

    async def generate_response(self, prompt: str) -> dict:
        """Request structured dialogue response with fallback on timeout."""

        schema = DialogueResponse.model_json_schema()
        try:
            return await self._llm_client.generate_structured(prompt=prompt, schema=schema, max_tokens=512)
        except LLMTimeoutError:
            return self._load_fallback_dialogue()

    def _load_fallback_dialogue(self) -> dict:
        """Load default fallback dialogue response."""

        fallback_map = json.loads(Path(self._fallback_path).read_text(encoding="utf-8"))
        responses = fallback_map.get("default", ["I need a moment to think."])
        return {
            "npc_response": responses[0],
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 20},
        }

    async def stream_text(self, prompt: str) -> list[str]:
        """Stream raw token chunks from LLM backend."""

        try:
            return [chunk async for chunk in self._llm_client.stream(prompt=prompt, max_tokens=512, temperature=0.7)]
        except (LLMTimeoutError, LLMRequestError):
            fallback = self._load_fallback_dialogue()
            return [str(fallback["npc_response"])]
