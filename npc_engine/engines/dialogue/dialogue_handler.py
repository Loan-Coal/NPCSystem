"""
dialogue_handler.py - Orchestrates context, prompting, parsing, mutation, and emotion update.

Does NOT: implement HTTP transport concerns.

Dependencies injected: AsyncSession, Settings, LLMClientProtocol, SessionStore, EmotionUpdater.
"""

from datetime import datetime, timezone
from pathlib import Path

from neo4j import AsyncSession
from pydantic import ValidationError

from api.schemas import DialogueRequest, DialogueResponse
from config import Settings
from engines.dialogue.action_resolver import resolve_action
from engines.dialogue.degradation import execute_with_degradation
from engines.dialogue.llm_client import DialogueLLMClient
from engines.dialogue.prompt_builder import build_dialogue_prompt
from engines.dialogue.relation_mutator import apply_dialogue_relation_deltas
from engines.dialogue.response_parser import parse_dialogue_response
from engines.dialogue.session_store import SessionStore
from engines.emotion.emotion_updater import EmotionUpdater
from engines.llm.protocols import LLMClientProtocol
from retrieval.context_builder import build_serialized_context
from retrieval.dialogue_context_cache import DialogueContextCache
from schema.llm_config_models import LLMConfig
from utils.metrics import increment_metric


LLM_VALIDATION_FAILURES_METRIC = "llm_validation_failures_total"


class DialogueHandler:
    """Dialogue engine orchestrator."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm_client: LLMClientProtocol,
        llm_config: LLMConfig,
        session_store: SessionStore,
        emotion_updater: EmotionUpdater,
        embedding_index,
        context_cache: DialogueContextCache | None = None,
    ):
        self._session = session
        self._settings = settings
        self._llm_config = llm_config
        self._session_store = session_store
        self._emotion_updater = emotion_updater
        self._embedding_index = embedding_index
        self._context_cache = context_cache
        self._llm = DialogueLLMClient(llm_client=llm_client, fallback_path=settings.LLM_FALLBACK_PATH)

    async def handle(self, request: DialogueRequest) -> DialogueResponse:
        """Execute full dialogue flow with tiered degradation and return response payload."""

        turns = self._session_store.get_turns(player_id=request.player_id, npc_id=request.npc_id)
        current_emotion = self._emotion_updater.get_state(npc_id=request.npc_id)

        parsed_response, level = await execute_with_degradation(
            full_factory=lambda: self._run_llm_pipeline(
                request=request, turns=turns, current_emotion=current_emotion, skip_rag=False
            ),
            graph_only_factory=lambda: self._run_llm_pipeline(
                request=request, turns=turns, current_emotion=current_emotion, skip_rag=True
            ),
            archetype="default",
            canned_dir=Path(self._settings.CANNED_RESPONSES_DIR),
            full_timeout=self._settings.DIALOGUE_FULL_TIMEOUT_SECONDS,
            graph_only_timeout=self._settings.DIALOGUE_GRAPH_ONLY_TIMEOUT_SECONDS,
        )

        resolved_action = resolve_action(action=parsed_response.action)
        final_response = parsed_response.model_copy(
            update={
                "action": resolved_action,
                "session_id": request.session_id or f"{request.player_id}:{request.npc_id}",
                "cached": False,
                "degradation_level": level,
            }
        )

        if level != "canned":
            tick_id = int(datetime.now(timezone.utc).timestamp())
            await apply_dialogue_relation_deltas(
                session=self._session,
                settings=self._settings,
                npc_id=request.npc_id,
                player_id=request.player_id,
                relation_deltas=final_response.relation_deltas,
                cause_id=f"dialogue:{request.player_id}:{request.npc_id}",
                tick_id=tick_id,
            )

        self._emotion_updater.apply_dialogue_mood(npc_id=request.npc_id, mood_update=final_response.mood_update)
        self._session_store.append_turns(
            player_id=request.player_id,
            npc_id=request.npc_id,
            new_turns=[
                f"player: {request.player_message}",
                f"npc: {final_response.npc_response}",
            ],
        )
        return final_response

    async def stream(self, request: DialogueRequest) -> list[str]:
        """Produce token chunks for WebSocket output."""

        turns = self._session_store.get_turns(player_id=request.player_id, npc_id=request.npc_id)
        current_emotion = self._emotion_updater.get_state(npc_id=request.npc_id)
        prompt = await self._build_dialogue_prompt(
            request=request,
            turns=turns,
            current_emotion=current_emotion,
        )
        return await self._llm.stream_text(prompt=prompt)

    async def _run_llm_pipeline(
        self,
        *,
        request: DialogueRequest,
        turns: list[str],
        current_emotion,
        skip_rag: bool,
    ) -> DialogueResponse:
        """Build context, call LLM, and parse response for one degradation tier."""

        prompt = await self._build_dialogue_prompt(
            request=request,
            turns=turns,
            current_emotion=current_emotion,
            skip_rag=skip_rag,
        )
        raw_response = await self._llm.generate_response(prompt=prompt)
        try:
            return parse_dialogue_response(payload=raw_response)
        except ValidationError:
            increment_metric(metric=LLM_VALIDATION_FAILURES_METRIC, labels={"engine": "dialogue"})
            fallback_payload = self._llm.fallback_response_payload()
            return parse_dialogue_response(payload=fallback_payload)

    async def _build_dialogue_prompt(
        self,
        request: DialogueRequest,
        turns: list[str],
        current_emotion,
        skip_rag: bool = False,
    ) -> str:
        """Build serialized context and prompt consistently across REST and stream paths."""

        session_id = request.session_id or f"{request.player_id}:{request.npc_id}"
        serialized_context = await build_serialized_context(
            session=self._session,
            settings=self._settings,
            llm_config=self._llm_config,
            embedding_index=self._embedding_index,
            npc_id=request.npc_id,
            player_message=request.player_message,
            session_turns=turns,
            emotion_state={"current_mood": current_emotion.label},
            context_cache=self._context_cache,
            session_id=session_id,
            skip_rag=skip_rag,
        )
        return build_dialogue_prompt(request=request, serialized_context=serialized_context)
