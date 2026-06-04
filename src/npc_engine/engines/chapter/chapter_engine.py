"""
Module: chapter_engine
Layer: engines
Purpose: Detects chapter transitions via quest density and creates LLM-labeled CHAPTER nodes.
Does NOT: perform graph writes directly — delegates to graph.chapter_writer.
Dependencies: graph.chapter_queries, graph.chapter_writer, engines.llm.protocols,
              common.yaml_utils, engines.chapter.chapter_labeler
Dependencies injected: LLMClientProtocol, AsyncSession (per call).
Used by: scheduler.tick_scheduler, api.dependency_singletons

NOTE: ~320 lines after extracting label_chapter_by_rules to chapter_labeler.py.
ChapterEngine is a single cohesive class; six tightly-coupled async methods share
injected state. Further splitting separates behaviour from state without gain. DEC-059.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.graph.faction_queries import get_faction_standings_summary
from npc_engine.graph.chapter_queries import (
    count_completed_quests_since_tick,
    get_completed_quests_since_tick,
    get_current_chapter,
    get_max_beat_intensity_in_chapter,
    get_recent_events_for_chapter,
)
from npc_engine.graph.chapter_writer import (
    close_chapter,
    create_chapter,
    link_event_to_chapter,
)
from npc_engine.config import get_settings
from npc_engine.world.world_reader import get_world_state
from npc_engine.engines.chapter.chapter_labeler import label_chapter_by_rules

if TYPE_CHECKING:
    from npc_engine.engines.llm.protocols import LLMClientProtocol


LOGGER = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "chapter"
    / "chapter_label_v1.yaml"
)

_DEFAULT_QUEST_THRESHOLD = 3
_DEFAULT_BEAT_INTENSITY_THRESHOLD = 70
_DEFAULT_WINDOW_TICKS = 20
_DEFAULT_MAX_TOKENS = 150
_DEFAULT_TEMPERATURE = 0.5

_FALLBACK_THEMES = ["conflict", "discovery", "betrayal", "alliance", "crisis"]


class ChapterEngine:
    """Detects narrative chapter transitions and labels them via LLM.

    On each tick:
    1. If no chapter is open, open one with a placeholder title.
    2. Check whether the current chapter should close: quest count in the last
       ``window_ticks`` ticks exceeds ``quest_threshold``, or max beat intensity
       in the chapter exceeds ``beat_intensity_threshold``.
    3. If transition detected: close the current chapter, call LLM to label it,
       open a new chapter with the generated title/theme.
    4. Link high-severity events from the current tick window to the open chapter.
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        *,
        quest_threshold: int = _DEFAULT_QUEST_THRESHOLD,
        beat_intensity_threshold: int = _DEFAULT_BEAT_INTENSITY_THRESHOLD,
        window_ticks: int = _DEFAULT_WINDOW_TICKS,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
    ) -> None:
        """Initialise the chapter engine.

        Args:
            llm_client: LLM adapter for generating chapter titles and themes.
            quest_threshold: Number of completed quests in ``window_ticks`` that
                triggers a chapter transition.
            beat_intensity_threshold: Maximum NARRATIVE_BEAT intensity that triggers
                a chapter transition.
            window_ticks: Lookback window (in ticks) for quest and beat detection.
            max_tokens: Maximum tokens to generate in LLM calls.
            temperature: Sampling temperature for LLM calls.
        """
        self._llm = llm_client
        self._quest_threshold = quest_threshold
        self._beat_intensity_threshold = beat_intensity_threshold
        self._window_ticks = window_ticks
        self._max_tokens = max_tokens
        self._temperature = temperature
        prompt_data = load_yaml_mapping(_PROMPT_PATH, "chapter_label_v1.yaml must be a mapping")
        self._system_prompt: str = prompt_data["system"]
        self._user_template: str = prompt_data["user_template"]

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict:
        """Run chapter detection and optional transition logic for the current tick.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.

        Returns:
            Dict with ``tick_id``, ``chapter_id`` (current open chapter),
            ``transition`` (True if a new chapter was opened), and
            ``chapter_name`` (the current chapter's name).
        """
        current = await get_current_chapter(session)

        if current is None:
            chapter_id = await self._open_new_chapter(session, tick_id, prior_chapter=None)
            return {
                "tick_id": tick_id,
                "chapter_id": chapter_id,
                "transition": True,
                "chapter_name": "Prologue",
            }

        transition = await self._should_transition(session, tick_id, current)
        if transition:
            label = await self._label_chapter(session, tick_id, current)
            await close_chapter(session, chapter_id=current["id"], ended_at_tick=tick_id)
            new_chapter_id = await self._open_new_chapter(
                session, tick_id, prior_chapter=label
            )
            LOGGER.info(
                "Chapter transition at tick %d: %r → new chapter %s",
                tick_id,
                label.get("title"),
                new_chapter_id,
            )
            return {
                "tick_id": tick_id,
                "chapter_id": new_chapter_id,
                "transition": True,
                "chapter_name": label.get("title", "Untitled Chapter"),
            }

        await self._link_recent_events(session, tick_id, current["id"])
        return {
            "tick_id": tick_id,
            "chapter_id": current["id"],
            "transition": False,
            "chapter_name": current["name"],
        }

    async def _should_transition(
        self,
        session: AsyncSession,
        tick_id: int,
        current: dict,
    ) -> bool:
        """Return True if quest density or beat intensity warrant a chapter close.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick.
            current: Current open chapter dict.

        Returns:
            True if a transition should occur.
        """
        since_tick = max(0, tick_id - self._window_ticks)
        quest_count = await count_completed_quests_since_tick(session, since_tick=since_tick)
        if quest_count >= self._quest_threshold:
            LOGGER.debug(
                "Chapter transition trigger: quest_count=%d >= threshold=%d",
                quest_count,
                self._quest_threshold,
            )
            return True

        max_intensity = await get_max_beat_intensity_in_chapter(
            session, chapter_id=current["id"]
        )
        if max_intensity >= self._beat_intensity_threshold:
            LOGGER.debug(
                "Chapter transition trigger: beat_intensity=%d >= threshold=%d",
                max_intensity,
                self._beat_intensity_threshold,
            )
            return True

        return False

    async def _label_chapter(
        self,
        session: AsyncSession,
        tick_id: int,
        current: dict,
    ) -> dict:
        """Call the LLM to generate a title, description, and theme for the closed chapter.

        Returns a dict with keys ``title``, ``description``, and ``theme``.
        Falls back to rule-based values if the LLM call fails or returns malformed JSON.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick for event lookback.
            current: Current open chapter dict.

        Returns:
            Dict with ``title``, ``description``, ``theme`` strings.
        """
        since_tick = max(0, current.get("started_at_tick", 0))
        (events, quests), (world_state, faction_standings) = await asyncio.gather(
            asyncio.gather(
                get_recent_events_for_chapter(session, since_tick=since_tick),
                get_completed_quests_since_tick(session, since_tick=since_tick),
            ),
            asyncio.gather(
                get_world_state(session, world_id=get_settings().WORLD_ID),
                get_faction_standings_summary(session, limit=5),
            ),
        )

        events_text = "\n".join(
            f"- [{e['event_type']}] {e['summary']}" for e in events
        ) or "(no events)"
        quests_text = "\n".join(f"- {q['title']}" for q in quests) or "(no quests)"
        conditions_text = ", ".join(world_state.active_conditions) or "(none)"
        factions_text = "\n".join(
            f"- {f['name']} (power: {f['power_score']})" for f in faction_standings
        ) or "(none)"

        user_message = self._user_template.format(
            events_text=events_text,
            quests_text=quests_text,
            active_conditions=conditions_text,
            dominant_factions=factions_text,
        )

        try:
            raw = await self._llm.generate(
                prompt=user_message,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=self._system_prompt,
            )
            label = json.loads(raw.strip())
            if not isinstance(label, dict):
                raise ValueError("LLM returned non-dict JSON")
            return {
                "title": str(label.get("title", "Untitled Chapter")),
                "description": str(label.get("description", "")),
                "theme": str(label.get("theme", "mystery")),
            }
        except Exception:
            LOGGER.exception(
                "LLM chapter labeling failed at tick %d — using rule-based fallback", tick_id
            )
            return label_chapter_by_rules(events)

    async def _open_new_chapter(
        self,
        session: AsyncSession,
        tick_id: int,
        prior_chapter: dict | None,
    ) -> str:
        """Create a new open CHAPTER node.

        Args:
            session: Active Neo4j async session.
            tick_id: Starting tick for the new chapter.
            prior_chapter: Label dict from the previous chapter (or None for prologue).

        Returns:
            New chapter ID.
        """
        chapter_id = str(uuid.uuid4())
        name = prior_chapter.get("title", "New Chapter") if prior_chapter else "Prologue"
        theme = prior_chapter.get("theme") if prior_chapter else None
        await create_chapter(
            session,
            chapter_id=chapter_id,
            name=name,
            started_at_tick=tick_id,
            theme=theme,
            status="open",
        )
        return chapter_id

    async def _link_recent_events(
        self,
        session: AsyncSession,
        tick_id: int,
        chapter_id: str,
    ) -> None:
        """Link recent high-severity events to the open chapter.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick.
            chapter_id: Open chapter ID.
        """
        events = await get_recent_events_for_chapter(
            session, since_tick=tick_id, limit=5
        )
        for event in events:
            if event.get("severity", 0) >= 60:
                await link_event_to_chapter(
                    session,
                    event_id=event["id"],
                    chapter_id=chapter_id,
                    tick_id=tick_id,
                )
