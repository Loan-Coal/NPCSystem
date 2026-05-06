"""
llm_client.py - Thin wrapper for dialogue structured generation with timeout fallback.

Does NOT: build prompts or mutate graph state.

Dependencies injected: LLMClientProtocol.
"""

import json
from pathlib import Path

from npc_engine.engines.dialogue.dialogue_models import DialogueResponse
from pydantic import ValidationError
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.retrieval.context_utils import estimate_tokens
from npc_engine.utils.errors import LLMRequestError, LLMTimeoutError
from npc_engine.utils.metrics import increment_metric


LLM_CALLS_METRIC = "llm_calls_total"
LLM_TOKENS_IN_METRIC = "llm_tokens_in_total"
LLM_TOKENS_OUT_METRIC = "llm_tokens_out_total"
LLM_ENGINE_LABEL = "dialogue"


class DialogueLLMClient:
    """Dialogue-oriented structured LLM client wrapper."""

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        fallback_path: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        stop_sequences: list[str],
    ) -> None:
        """Initialise the dialogue LLM client wrapper.

        Args:
            llm_client: Underlying LLM adapter implementing LLMClientProtocol.
            fallback_path: Path to the JSON fallback response file.
            max_tokens: Maximum tokens to request from the LLM per call.
            temperature: Sampling temperature forwarded to streaming calls.
            top_p: Nucleus sampling probability mass forwarded to all generation calls.
            stop_sequences: Token sequences that halt generation, forwarded to all calls.
        """

        self._llm_client = llm_client
        self._fallback_path = fallback_path
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._stop_sequences = stop_sequences

    async def generate_response(self, prompt: str) -> dict:
        """Request a structured dialogue response, falling back on timeout or errors.

        Args:
            prompt: Full dialogue prompt string built by prompt_builder.

        Returns:
            Dict conforming to the DialogueResponse schema, validated by Pydantic.
            Returns a deterministic fallback dict on LLMTimeoutError, LLMRequestError,
            or ValidationError.
        """

        schema = DialogueResponse.model_json_schema()
        model_name = self._llm_client.model_name()
        labels = {"engine": LLM_ENGINE_LABEL, "backend": model_name, "mode": "structured"}
        increment_metric(metric=LLM_CALLS_METRIC, labels=labels)
        increment_metric(metric=LLM_TOKENS_IN_METRIC, amount=float(estimate_tokens(prompt)), labels=labels)
        try:
            response = await self._llm_client.generate_structured(
                prompt=prompt,
                schema=schema,
                max_tokens=self._max_tokens,
                top_p=self._top_p,
                stop_sequences=self._stop_sequences,
            )
            normalized_response = DialogueResponse.model_validate(response).model_dump(mode="python")
            increment_metric(
                metric=LLM_TOKENS_OUT_METRIC,
                amount=float(estimate_tokens(json.dumps(normalized_response, sort_keys=True, ensure_ascii=True))),
                labels=labels,
            )
            return normalized_response
        except LLMTimeoutError:
            return self._fallback_with_metrics(labels=labels, fallback_reason="timeout")
        except LLMRequestError:
            return self._fallback_with_metrics(labels=labels, fallback_reason="request_error")
        except ValidationError:
            return self._fallback_with_metrics(labels=labels, fallback_reason="validation_error")

    def fallback_response_payload(self) -> dict:
        """Return a deterministic fallback payload for callers that need safe recovery.

        Returns:
            Dict loaded from the configured fallback JSON file.
        """

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

    def _fallback_with_metrics(self, labels: dict[str, str], fallback_reason: str) -> dict:
        """Emit fallback token metrics and return default payload."""

        fallback = self._load_fallback_dialogue()
        increment_metric(
            metric=LLM_TOKENS_OUT_METRIC,
            amount=float(estimate_tokens(json.dumps(fallback, sort_keys=True, ensure_ascii=True))),
            labels={**labels, "fallback": fallback_reason},
        )
        return fallback

    async def stream_text(self, prompt: str) -> list[str]:
        """Stream raw token chunks from the LLM backend.

        Args:
            prompt: Full dialogue prompt string.

        Returns:
            List of token chunk strings. Returns a single-element list containing
            the fallback npc_response text on LLMTimeoutError or LLMRequestError.
        """

        model_name = self._llm_client.model_name()
        labels = {"engine": LLM_ENGINE_LABEL, "backend": model_name, "mode": "stream"}
        increment_metric(metric=LLM_CALLS_METRIC, labels=labels)
        increment_metric(metric=LLM_TOKENS_IN_METRIC, amount=float(estimate_tokens(prompt)), labels=labels)
        try:
            chunks = [
                chunk
                async for chunk in self._llm_client.stream(
                    prompt=prompt,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    stop_sequences=self._stop_sequences,
                )
            ]
            increment_metric(
                metric=LLM_TOKENS_OUT_METRIC,
                amount=float(estimate_tokens("".join(chunks))),
                labels=labels,
            )
            return chunks
        except (LLMTimeoutError, LLMRequestError):
            fallback = self._load_fallback_dialogue()
            text = str(fallback["npc_response"])
            increment_metric(
                metric=LLM_TOKENS_OUT_METRIC,
                amount=float(estimate_tokens(text)),
                labels={**labels, "fallback": "error"},
            )
            return [text]
