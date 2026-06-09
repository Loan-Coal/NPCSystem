"""
dialogue_handler.py - Orchestrates context, prompting, parsing, mutation, and emotion update.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: implement HTTP transport concerns.

Dependencies injected: AsyncSession, Settings, LLMClientProtocol, EngineModelConfig,
                       SessionStore, EmotionUpdater, KnowledgeExtractionEngine (optional).

300-LINE WAIVER: This file is the central orchestrator for the dialogue turn pipeline.
A split would be artificial — all methods belong to a single handler class. The file
was already 312 lines before EXP-53 added 27 lines (DI wiring + guarded call block).
Splitting DialogueHandler across files would harm cohesion with no meaningful gain.
Ref: DECISIONS.md (DEC-072 OCP note).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from neo4j import AsyncSession
from pydantic import ValidationError

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest, DialogueResponse
from npc_engine.config import Settings
from npc_engine.engines.dialogue.action_resolver import resolve_action
from npc_engine.engines.dialogue.degradation import execute_with_degradation
from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.engines.dialogue.prompt_builder import build_dialogue_prompt, build_system_prompt
from npc_engine.engines.dialogue.relation_mutator import apply_dialogue_relation_deltas
from npc_engine.engines.dialogue.response_parser import parse_dialogue_response
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.engines.routine.routine_queries import set_routine_override
from npc_engine.engines.tts.protocols import TTSClientProtocol
from npc_engine.engines.tts.voice_modulator import modulate as modulate_voice
from npc_engine.engines.tts.voice_params import VoiceParams
from npc_engine.graph.graph_reader import get_npc_voice_descriptor
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.context_protocols import EmbeddingIndexProtocol
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.metrics import increment_metric
from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
    KnowledgeExtractionEngine,
)
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_reader import get_world_state


_logger = logging.getLogger(__name__)

LLM_VALIDATION_FAILURES_METRIC = "llm_validation_failures_total"
TTS_FAILURES_METRIC = "tts_failures_total"


def resolve_log_prompts(settings: Settings) -> bool:
    """Return True only when prompt logging is enabled AND environment is dev.

    Per project security rules, prompt/response logging must be suppressed in
    staging and prod even when the LOG_LLM_PROMPTS flag is set to True.

    Args:
        settings: Application settings instance.

    Returns:
        True when LOG_LLM_PROMPTS is True and ENV equals "dev"; False otherwise.
    """
    return settings.LOG_LLM_PROMPTS and settings.ENV == "dev"


class DialogueHandler:
    """Dialogue engine orchestrator."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        llm_client: LLMClientProtocol,
        llm_config: LLMConfig,
        engine_model_config: EngineModelConfig,
        session_store: SessionStore,
        emotion_updater: EmotionUpdater,
        embedding_index: EmbeddingIndexProtocol,
        context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
        tts_client: TTSClientProtocol | None = None,
        knowledge_engine: KnowledgeExtractionEngine | None = None,
    ) -> None:
        """Initialise the dialogue handler with all engine dependencies.

        Args:
            session: Active Neo4j async session.
            settings: Application settings.
            llm_client: LLM adapter for text generation.
            llm_config: Context pipeline config (tier budgets and relevance weights).
            engine_model_config: Per-engine LLM config (model params, timeouts, fallback).
            session_store: In-memory session turn store.
            emotion_updater: Engine for reading and updating NPC emotion state.
            embedding_index: Vector index supporting the EmbeddingIndexProtocol.
            context_cache: Optional in-memory dialogue context cache.
            tts_client: Optional TTS adapter; used when settings.TTS_ENABLED is True.
            knowledge_engine: Optional engine for persisting player-stated facts as
                belief nodes (EXP-53).  Guarded by KNOWLEDGE_LEARNING_ENABLED flag.
        """

        self._session = session
        self._settings = settings
        self._llm_config = llm_config
        self._engine_model_config = engine_model_config
        self._session_store = session_store
        self._emotion_updater = emotion_updater
        self._embedding_index = embedding_index
        self._context_cache = context_cache
        self._tts_client = tts_client
        self._knowledge_engine = knowledge_engine
        self._memory_engine = MemoryEngine()
        self._llm = DialogueLLMClient(
            llm_client=llm_client,
            fallback_path=settings.LLM_FALLBACK_PATH,
            max_tokens=engine_model_config.llm.max_tokens,
            temperature=engine_model_config.llm.temperature,
            top_p=engine_model_config.llm.top_p,
            stop_sequences=list(engine_model_config.llm.stop_sequences),
            log_prompts=resolve_log_prompts(settings),
        )
        self._system_prompt = build_system_prompt()

    async def handle(self, request: DialogueRequest) -> DialogueResponse:
        """Execute the full dialogue flow with tiered degradation and return the response.

        Args:
            request: Incoming dialogue request from the player.

        Returns:
            Final DialogueResponse with resolved action, updated session_id, and
            degradation level indicating which tier produced the response.
        """

        turns = await self._session_store.get_turns(player_id=request.player_id, npc_id=request.npc_id)
        current_emotion = await self._emotion_updater.get_state(npc_id=request.npc_id)

        parsed_response, level = await execute_with_degradation(
            full_factory=lambda: self._run_llm_pipeline(
                request=request, turns=turns, current_emotion=current_emotion, skip_rag=False
            ),
            graph_only_factory=lambda: self._run_llm_pipeline(
                request=request, turns=turns, current_emotion=current_emotion, skip_rag=True
            ),
            archetype="default",
            canned_dir=Path(self._settings.CANNED_RESPONSES_DIR),
            full_timeout=self._engine_model_config.timeouts_ms.full / 1000.0,
            graph_only_timeout=(self._engine_model_config.timeouts_ms.graph_only or 0) / 1000.0,
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

        tick_id = int(datetime.now(timezone.utc).timestamp())
        if level != "canned":
            await apply_dialogue_relation_deltas(
                session=self._session,
                settings=self._settings,
                npc_id=request.npc_id,
                player_id=request.player_id,
                relation_deltas=final_response.relation_deltas,
                cause_id=f"dialogue:{request.player_id}:{request.npc_id}",
                tick_id=tick_id,
            )

        new_emotion = await self._emotion_updater.apply_dialogue_mood(
            npc_id=request.npc_id, mood_update=final_response.mood_update
        )
        if getattr(new_emotion, "arousal", 0) > 70:
            world_state = await get_world_state(session=self._session, world_id=self._settings.WORLD_ID)
            game_time = TimePoint(
                year=world_state.year,
                season=world_state.season,
                day=world_state.day,
                time_of_day=world_state.time_of_day,
            )
            await self._memory_engine.create_from_arousal(
                self._session,
                character_id=request.npc_id,
                arousal=new_emotion.arousal,
                content=f"{request.player_message} — {final_response.npc_response}",
                game_time=game_time,
            )
        if (
            self._knowledge_engine is not None
            and getattr(self._settings, "KNOWLEDGE_LEARNING_ENABLED", False)
            and final_response.learned_facts
        ):
            world_state = await get_world_state(
                session=self._session, world_id=self._settings.WORLD_ID
            )
            game_time_str = (
                f"Year {world_state.year} {world_state.season} "
                f"Day {world_state.day} {world_state.time_of_day}"
            )
            await self._knowledge_engine.process(
                self._session,
                npc_id=request.npc_id,
                player_id=request.player_id,
                tick=tick_id,
                learned_facts=list(final_response.learned_facts),
                game_time_str=game_time_str,
            )
        if new_emotion.valence < -60:
            await set_routine_override(
                session=self._session,
                character_id=request.npc_id,
                location_id="home",
                expires_at_tick=tick_id + 5,
            )
        await self._session_store.append_turns(
            player_id=request.player_id,
            npc_id=request.npc_id,
            new_turns=[
                f"player: {request.player_message}",
                f"npc: {final_response.npc_response}",
            ],
        )
        if getattr(self._settings, "TTS_ENABLED", False) and getattr(self, "_tts_client", None) is not None:
            final_response = await self._synthesize_audio(
                response=final_response, npc_id=request.npc_id
            )
        return final_response

    async def _synthesize_audio(
        self, response: DialogueResponse, npc_id: str
    ) -> DialogueResponse:
        """Call the TTS backend and attach audio bytes to the response.

        Fetches the NPC's voice_descriptor from the graph to build VoiceParams.
        On TTS failure the original response (without audio) is returned so the
        dialogue turn is never blocked by a TTS outage.

        Args:
            response: The fully resolved dialogue response awaiting audio.
            npc_id: NPC identifier used to look up voice configuration.

        Returns:
            Response with audio_bytes populated, or original on synthesis error.
        """
        voice_descriptor = await get_npc_voice_descriptor(
            session=self._session, npc_id=npc_id
        )
        base_params = VoiceParams(voice_id=voice_descriptor or "default")
        current_emotion = await self._emotion_updater.get_state(npc_id=npc_id)
        voice_params = modulate_voice(base_params=base_params, emotion_state=current_emotion)
        try:
            audio = await self._tts_client.synthesize(  # type: ignore[union-attr]
                text=response.npc_response, voice_params=voice_params
            )
            return response.model_copy(update={"audio_bytes": audio})
        except Exception as exc:
            _logger.warning(
                "tts_failure",
                extra={"npc_id": npc_id, "error": str(exc)},
                exc_info=True,
            )
            increment_metric(TTS_FAILURES_METRIC)
            return response

    async def stream(self, request: DialogueRequest) -> list[str]:
        """Produce token chunks for WebSocket streaming output.

        Args:
            request: Incoming dialogue request from the player.

        Returns:
            List of token chunk strings from the LLM stream, or a single fallback
            string on LLM error.
        """

        turns = await self._session_store.get_turns(player_id=request.player_id, npc_id=request.npc_id)
        current_emotion = await self._emotion_updater.get_state(npc_id=request.npc_id)
        prompt = await self._build_dialogue_prompt(
            request=request,
            turns=turns,
            current_emotion=current_emotion,
        )
        return await self._llm.stream_text(prompt=prompt, system=self._system_prompt)

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
        raw_response = await self._llm.generate_response(prompt=prompt, system=self._system_prompt)
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
            player_id=request.player_id,
            explicit_node_ids=frozenset(request.explicit_node_ids),
        )
        return build_dialogue_prompt(request=request, serialized_context=serialized_context)
