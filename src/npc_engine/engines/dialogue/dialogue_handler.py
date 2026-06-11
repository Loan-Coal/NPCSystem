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

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from neo4j import AsyncSession
from pydantic import ValidationError

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest, DialogueResponse
from npc_engine.config import Settings
from npc_engine.engines.dialogue.action_resolver import resolve_action
from npc_engine.engines.dialogue.degradation import DegradationLevel, execute_with_degradation, get_canned_response
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
from npc_engine.graph.graph_reader import get_npc_archetype, get_npc_voice_descriptor
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.context_protocols import EmbeddingIndexProtocol
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.metrics import increment_metric
from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
    KnowledgeExtractionEngine,
)
from npc_engine.config import ContentRating
from npc_engine.services.input_moderation import InputModerationService
from npc_engine.services.output_moderation import OutputModerationService
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_state import WorldState
from npc_engine.graph.world_state_reader import get_world_state
from npc_engine.engines.dialogue.negotiation_context import inject_active_negotiation

if TYPE_CHECKING:
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore


_logger = logging.getLogger(__name__)

LLM_VALIDATION_FAILURES_METRIC = "llm_validation_failures_total"
TTS_FAILURES_METRIC = "tts_failures_total"
HIGH_AROUSAL_THRESHOLD = 70
LOW_VALENCE_THRESHOLD = -60


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
        self, session: AsyncSession, settings: Settings, llm_client: LLMClientProtocol,
        llm_config: LLMConfig, engine_model_config: EngineModelConfig, session_store: SessionStore,
        emotion_updater: EmotionUpdater, embedding_index: EmbeddingIndexProtocol,
        input_moderation: InputModerationService, output_moderation: OutputModerationService,
        effective_rating: ContentRating = "mature",
        context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
        tts_client: TTSClientProtocol | None = None,
        knowledge_engine: KnowledgeExtractionEngine | None = None,
        negotiation_store: NegotiationStore | None = None,
    ) -> None:
        """Initialise with all engine dependencies injected.

        Args:
            input_moderation: Checks player input against the content ceiling (S16.2).
            output_moderation: Flags NPC responses that exceed the content ceiling (S16.3).
            effective_rating: The active content ceiling; informs the system prompt (S16.3).
            knowledge_engine: Optional; persists player facts as BELIEVES nodes (EXP-53),
                guarded by KNOWLEDGE_LEARNING_ENABLED.
            negotiation_store: Optional; when supplied, an active barter session is
                injected into the dialogue context so the NPC reflects live trade
                reality (S22.4, ISSUE-071). The no-store path is unchanged.
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
        self._input_moderation = input_moderation
        self._output_moderation = output_moderation
        self._effective_rating = effective_rating
        self._negotiation_store = negotiation_store
        self._memory_engine = MemoryEngine()
        self._llm = self._build_llm_client(llm_client)
        self._system_prompt = build_system_prompt(content_rating=effective_rating)

    def _build_llm_client(self, llm_client: LLMClientProtocol) -> DialogueLLMClient:
        """Construct DialogueLLMClient from stored settings and engine config."""
        cfg = self._engine_model_config.llm
        return DialogueLLMClient(
            llm_client=llm_client,
            fallback_path=self._settings.LLM_FALLBACK_PATH,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            stop_sequences=list(cfg.stop_sequences),
            log_prompts=resolve_log_prompts(self._settings),
        )

    def _apply_output_ceiling(
        self, parsed: DialogueResponse, level: DegradationLevel, canned_dir: Path, npc_id: str, archetype: str,
    ) -> tuple[DialogueResponse, DegradationLevel]:
        """Return a canned fallback when NPC output exceeds the content ceiling."""
        if not self._output_moderation.is_over_ceiling(parsed.npc_response):
            return parsed, level
        _logger.warning("output_ceiling_violation", extra={"npc_id": npc_id, "rating": self._effective_rating})
        return get_canned_response(archetype=archetype, canned_dir=canned_dir), "canned"

    async def handle(self, request: DialogueRequest) -> DialogueResponse:
        """Execute the full dialogue flow with tiered degradation and return the response.

        Raises ContentRatingViolationError (→ HTTP 422) when input exceeds the ceiling.

        Returns:
            DialogueResponse with resolved action, updated session_id, and degradation level.
        """
        self._input_moderation.check(
            player_message=request.player_message,
            player_id=request.player_id,
        )
        turns = await self._session_store.get_turns(player_id=request.player_id, npc_id=request.npc_id)
        current_emotion = await self._emotion_updater.get_state(npc_id=request.npc_id)
        archetype = await get_npc_archetype(self._session, request.npc_id) or "default"
        canned_dir = Path(self._settings.CANNED_RESPONSES_DIR)
        parsed_response, level = await execute_with_degradation(
            full_factory=lambda: self._run_llm_pipeline(request=request, turns=turns, current_emotion=current_emotion, skip_rag=False, archetype=archetype),
            graph_only_factory=lambda: self._run_llm_pipeline(request=request, turns=turns, current_emotion=current_emotion, skip_rag=True, archetype=archetype),
            archetype=archetype,
            canned_dir=canned_dir,
            full_timeout=self._engine_model_config.timeouts_ms.full / 1000.0,
            graph_only_timeout=(self._engine_model_config.timeouts_ms.graph_only or 0) / 1000.0,
        )
        parsed_response, level = self._apply_output_ceiling(parsed_response, level, canned_dir, request.npc_id, archetype)
        resolved_action = resolve_action(action=parsed_response.action)
        final_response = parsed_response.model_copy(update={
            "action": resolved_action,
            "session_id": request.session_id or f"{request.player_id}:{request.npc_id}",
            "cached": False, "degradation_level": level,
        })
        tick_id = int(datetime.now(timezone.utc).timestamp())
        new_emotion = await self._apply_relation_and_emotion(request=request, response=final_response, level=level, tick_id=tick_id)
        world_state = await self._maybe_load_world_state(response=final_response, new_emotion=new_emotion)
        await self._apply_arousal_memory(request=request, response=final_response, new_emotion=new_emotion, world_state=world_state)
        await self._apply_knowledge_and_routine(request=request, response=final_response, new_emotion=new_emotion, tick_id=tick_id, world_state=world_state)
        if getattr(self._settings, "TTS_ENABLED", False) and getattr(self, "_tts_client", None) is not None:
            final_response = await self._synthesize_audio(response=final_response, npc_id=request.npc_id)
        return final_response

    async def _apply_relation_and_emotion(self, *, request: DialogueRequest, response: DialogueResponse, level: str, tick_id: int):
        """Apply relation deltas (if not canned) and update NPC emotion; return new emotion state."""
        if level != "canned":
            await apply_dialogue_relation_deltas(
                session=self._session, settings=self._settings, npc_id=request.npc_id,
                player_id=request.player_id, relation_deltas=response.relation_deltas,
                cause_id=f"dialogue:{request.player_id}:{request.npc_id}", tick_id=tick_id,
            )
        return await self._emotion_updater.apply_dialogue_mood(
            npc_id=request.npc_id,
            mood_update=response.mood_update,
            session=self._session,
            tick=tick_id,
        )

    def _needs_world_state(self, *, response: DialogueResponse, new_emotion) -> bool:
        """True when either the arousal-memory or knowledge-learning branch will fire (ISSUE-087)."""
        arousal_branch = getattr(new_emotion, "arousal", 0) > HIGH_AROUSAL_THRESHOLD
        knowledge_branch = (
            self._knowledge_engine is not None
            and getattr(self._settings, "KNOWLEDGE_LEARNING_ENABLED", False)
            and bool(response.learned_facts)
        )
        return arousal_branch or knowledge_branch

    async def _maybe_load_world_state(self, *, response: DialogueResponse, new_emotion) -> WorldState | None:
        """Fetch world state once iff a downstream branch needs it; avoids the double read (ISSUE-087)."""
        if not self._needs_world_state(response=response, new_emotion=new_emotion):
            return None
        return await get_world_state(session=self._session, world_id=self._settings.WORLD_ID)

    async def _apply_arousal_memory(self, *, request: DialogueRequest, response: DialogueResponse, new_emotion, world_state: WorldState | None) -> None:
        """Create an episodic memory when NPC arousal exceeds the high-arousal threshold."""
        if world_state is None or getattr(new_emotion, "arousal", 0) <= HIGH_AROUSAL_THRESHOLD:
            return
        game_time = TimePoint(year=world_state.year, season=world_state.season, day=world_state.day, time_of_day=world_state.time_of_day)
        await self._memory_engine.create_from_arousal(
            self._session, character_id=request.npc_id, arousal=new_emotion.arousal,
            content=f"{request.player_message} — {response.npc_response}", game_time=game_time,
        )

    async def _apply_knowledge_and_routine(self, *, request: DialogueRequest, response: DialogueResponse, new_emotion, tick_id: int, world_state: WorldState | None) -> None:
        """Process knowledge learning, routine override, and session-turn bookkeeping."""
        if (self._knowledge_engine is not None and getattr(self._settings, "KNOWLEDGE_LEARNING_ENABLED", False) and response.learned_facts and world_state is not None):
            game_time_str = f"Year {world_state.year} {world_state.season} Day {world_state.day} {world_state.time_of_day}"
            await self._knowledge_engine.process(
                self._session, npc_id=request.npc_id, player_id=request.player_id,
                tick=tick_id, learned_facts=list(response.learned_facts), game_time_str=game_time_str,
            )
        if new_emotion.valence < LOW_VALENCE_THRESHOLD:
            await set_routine_override(session=self._session, character_id=request.npc_id, location_id="home", expires_at_tick=tick_id + 5)
        await self._session_store.append_turns(
            player_id=request.player_id, npc_id=request.npc_id,
            new_turns=[f"player: {request.player_message}", f"npc: {response.npc_response}"],
        )

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
        archetype = await get_npc_archetype(self._session, request.npc_id) or "default"
        prompt = await self._build_dialogue_prompt(
            request=request,
            turns=turns,
            current_emotion=current_emotion,
        )
        return await self._llm.stream_text(prompt=prompt, system=self._system_prompt, archetype=archetype)

    async def _run_llm_pipeline(
        self,
        *,
        request: DialogueRequest,
        turns: list[str],
        current_emotion,
        skip_rag: bool,
        archetype: str = "default",
    ) -> DialogueResponse:
        """Build context, call LLM, and parse response for one degradation tier."""

        prompt = await self._build_dialogue_prompt(
            request=request,
            turns=turns,
            current_emotion=current_emotion,
            skip_rag=skip_rag,
        )
        raw_response = await self._llm.generate_response(prompt=prompt, system=self._system_prompt, archetype=archetype)
        try:
            return parse_dialogue_response(payload=raw_response)
        except ValidationError:
            increment_metric(metric=LLM_VALIDATION_FAILURES_METRIC, labels={"engine": "dialogue"})
            fallback_payload = self._llm.fallback_response_payload(archetype=archetype)
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
        serialized_context = self._with_active_negotiation(serialized_context, request)
        return build_dialogue_prompt(request=request, serialized_context=serialized_context)

    def _with_active_negotiation(self, serialized_context: str, request: DialogueRequest) -> str:
        """Merge any active barter session for this (npc, player) into the context (S22.4)."""
        if self._negotiation_store is None:
            return serialized_context
        session = self._negotiation_store.get(request.player_id)
        return inject_active_negotiation(serialized_context, session, request.npc_id)
