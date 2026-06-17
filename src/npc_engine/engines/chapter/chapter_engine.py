"""
Module: chapter_engine
Layer: engines
Purpose: Detects chapter transitions via quest density and creates LLM-labeled CHAPTER nodes.
Does NOT: perform graph reads/writes directly — delegates to the injected ChapterGraphPort
          (chapter reads/writes + faction standings) and WorldStateGraphPort.
Dependencies: engines.ports.chapter_port, engines.ports.world_state_port, engines.llm.protocols,
              common.yaml_utils, engines.chapter.chapter_labeler, config
Dependencies injected: LLMGenerateProtocol, ChapterGraphPort, WorldStateGraphPort.
Used by: scheduler.tick_scheduler, api.dependencies_advanced.progression

NOTE: single cohesive class; six tightly-coupled async methods share injected state.
Further splitting separates behaviour from state without gain. DEC-059.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.config import get_settings
from npc_engine.engines.chapter.chapter_labeler import label_chapter_by_rules

if TYPE_CHECKING:
    from npc_engine.engines.llm.protocols import LLMGenerateProtocol
    from npc_engine.engines.ports.chapter_port import ChapterGraphPort
    from npc_engine.engines.ports.world_state_port import WorldStateGraphPort


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

# Minimum event severity for linking an event to the open chapter.
_LINK_SEVERITY_THRESHOLD = 60

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
        llm_client: LLMGenerateProtocol,
        chapter_repo: ChapterGraphPort,
        world_state_repo: WorldStateGraphPort,
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
            chapter_repo: Graph port for chapter reads/writes + faction standings.
            world_state_repo: Shared graph port for reading the WorldState.
            quest_threshold: Number of completed quests in ``window_ticks`` that
                triggers a chapter transition.
            beat_intensity_threshold: Maximum NARRATIVE_BEAT intensity that triggers
                a chapter transition.
            window_ticks: Lookback window (in ticks) for quest and beat detection.
            max_tokens: Maximum tokens to generate in LLM calls.
            temperature: Sampling temperature for LLM calls.
        """
        self._llm = llm_client
        self._chapter_repo = chapter_repo
        self._world_state_repo = world_state_repo
        self._quest_threshold = quest_threshold
        self._beat_intensity_threshold = beat_intensity_threshold
        self._window_ticks = window_ticks
        self._max_tokens = max_tokens
        self._temperature = temperature
        prompt_data = load_yaml_mapping(_PROMPT_PATH, "chapter_label_v1.yaml must be a mapping")
        self._system_prompt: str = prompt_data["system"]
        self._user_template: str = prompt_data["user_template"]

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Run chapter detection and optional transition logic for the current tick.

        Reads/writes flow through the injected ChapterGraphPort + WorldStateGraphPort,
        which own their Neo4j sessions (DEC-122 / SEV-24); the scheduler's ``session=``
        kwarg is accepted via ``**_`` and ignored.

        Args:
            tick_id: Current game tick identifier.

        Returns:
            Dict with ``tick_id``, ``chapter_id`` (current open chapter),
            ``transition`` (True if a new chapter was opened), and
            ``chapter_name`` (the current chapter's name).
        """
        current = await self._chapter_repo.get_current_chapter()

        if current is None:
            chapter_id = await self._open_new_chapter(tick_id, prior_chapter=None)
            return {
                "tick_id": tick_id,
                "chapter_id": chapter_id,
                "transition": True,
                "chapter_name": "Prologue",
            }

        transition = await self._should_transition(tick_id, current)
        if transition:
            return await self._transition_chapter(tick_id, current)

        await self._link_recent_events(tick_id, current["id"])
        return {
            "tick_id": tick_id,
            "chapter_id": current["id"],
            "transition": False,
            "chapter_name": current["name"],
        }

    async def _transition_chapter(self, tick_id: int, current: dict[str, Any]) -> dict[str, Any]:
        """Close the current chapter, label it via LLM, and open the next one.

        Args:
            tick_id: Current tick.
            current: Current open chapter dict.

        Returns:
            run_tick result dict[str, Any] for the newly opened chapter.
        """
        label = await self._label_chapter(tick_id, current)
        await self._chapter_repo.close_chapter(
            chapter_id=current["id"], ended_at_tick=tick_id
        )
        new_chapter_id = await self._open_new_chapter(tick_id, prior_chapter=label)
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

    async def _should_transition(
        self,
        tick_id: int,
        current: dict[str, Any],
    ) -> bool:
        """Return True if quest density or beat intensity warrant a chapter close.

        Args:
            tick_id: Current tick.
            current: Current open chapter dict.

        Returns:
            True if a transition should occur.
        """
        since_tick = max(0, tick_id - self._window_ticks)
        quest_count = await self._chapter_repo.count_completed_quests_since_tick(
            since_tick=since_tick
        )
        if quest_count >= self._quest_threshold:
            LOGGER.debug(
                "Chapter transition trigger: quest_count=%d >= threshold=%d",
                quest_count,
                self._quest_threshold,
            )
            return True

        max_intensity = await self._chapter_repo.get_max_beat_intensity_in_chapter(
            chapter_id=current["id"]
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
        tick_id: int,
        current: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the LLM to generate a title, description, and theme for the closed chapter.

        Returns a dict[str, Any] with keys ``title``, ``description``, and ``theme``.
        Falls back to rule-based values if the LLM call fails or returns malformed JSON.

        Args:
            tick_id: Current tick for event lookback.
            current: Current open chapter dict.

        Returns:
            Dict with ``title``, ``description``, ``theme`` strings.
        """
        since_tick = max(0, current.get("started_at_tick", 0))
        (events, quests), (world_state, faction_standings) = await asyncio.gather(
            asyncio.gather(
                self._chapter_repo.get_recent_events_for_chapter(since_tick=since_tick),
                self._chapter_repo.get_completed_quests_since_tick(since_tick=since_tick),
            ),
            asyncio.gather(
                self._world_state_repo.get_world_state(world_id=get_settings().WORLD_ID),
                self._chapter_repo.get_faction_standings_summary(limit=5),
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
                raise ValueError("LLM returned non-dict[str, Any] JSON")
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
        tick_id: int,
        prior_chapter: dict[str, Any] | None,
    ) -> str:
        """Create a new open CHAPTER node.

        Args:
            tick_id: Starting tick for the new chapter.
            prior_chapter: Label dict[str, Any] from the previous chapter (or None for prologue).

        Returns:
            New chapter ID.
        """
        chapter_id = str(uuid.uuid4())
        name = prior_chapter.get("title", "New Chapter") if prior_chapter else "Prologue"
        theme = prior_chapter.get("theme") if prior_chapter else None
        await self._chapter_repo.create_chapter(
            chapter_id=chapter_id,
            name=name,
            started_at_tick=tick_id,
            theme=theme,
            status="open",
        )
        return chapter_id

    async def _link_recent_events(
        self,
        tick_id: int,
        chapter_id: str,
    ) -> None:
        """Link recent high-severity events to the open chapter.

        Args:
            tick_id: Current tick.
            chapter_id: Open chapter ID.
        """
        events = await self._chapter_repo.get_recent_events_for_chapter(
            since_tick=tick_id, limit=5
        )
        for event in events:
            if event.get("severity", 0) >= _LINK_SEVERITY_THRESHOLD:
                await self._chapter_repo.link_event_to_chapter(
                    event_id=event["id"],
                    chapter_id=chapter_id,
                    tick_id=tick_id,
                )
