"""
dialogue_handler.py - Orchestrates context, prompting, parsing, mutation, and emotion update.

Does NOT: implement HTTP transport concerns.

Dependencies injected: AsyncSession, Settings, LLMClientProtocol, SessionStore, EmotionUpdater.
"""

from datetime import datetime, timezone
from pathlib import Path

from neo4j import AsyncSession
from pydantic import ValidationError

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest, DialogueResponse
from npc_engine.config import Settings
from npc_engine.engines.dialogue.action_resolver import resolve_action
from npc_engine.engines.dialogue.degradation import execute_with_degradation
from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.engines.dialogue.prompt_builder import build_dialogue_prompt
from npc_engine.engines.dialogue.relation_mutator import apply_dialogue_relation_deltas
from npc_engine.engines.dialogue.response_parser import parse_dialogue_response
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache
from npc_engine.schema.llm_config_models import LLMConfig
from npc_engine.utils.metrics import increment_metric


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
        embedding_index: object,
        context_cache: DialogueContextCache | None = None,
    ) -> None:
        """Initialise the dialogue handler with all engine dependencies.

        Args:
            session: Active Neo4j async session.
            settings: Application settings.
            llm_client: LLM adapter for text generation.
            llm_config: LLM configuration with tier budgets and relevance weights.
            session_store: In-memory session turn store.
            emotion_updater: Engine for reading and updating NPC emotion state.
            embedding_index: Vector index supporting the EmbeddingIndexProtocol.
            context_cache: Optional in-memory dialogue context cache.
        """

        self._session = session
        self._settings = settings
        self._llm_config = llm_config
        self._session_store = session_store
        self._emotion_updater = emotion_updater
        self._embedding_index = embedding_index
        self._context_cache = context_cache
        self._llm = DialogueLLMClient(llm_client=llm_client, fallback_path=settings.LLM_FALLBACK_PATH)

    async def handle(self, request: DialogueRequest) -> DialogueResponse:
        """Execute the full dialogue flow with tiered degradation and return the response.

        Args:
            request: Incoming dialogue request from the player.

        Returns:
            Final DialogueResponse with resolved action, updated session_id, and
            degradation level indicating which tier produced the response.
        """

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
        """Produce token chunks for WebSocket streaming output.

        Args:
            request: Incoming dialogue request from the player.

        Returns:
            List of token chunk strings from the LLM stream, or a single fallback
            string on LLM error.
        """

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
