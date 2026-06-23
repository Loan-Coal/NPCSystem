"""
Module: branch_state
Layer: demo_game
Purpose: Immutable record of all branch choices taken during a demo session.
         Persisted to .cache/demo/branch_state.json for deterministic --cached
         replay. BranchState is the sole source of truth for which options were
         chosen, enabling ending-selection logic and replay diffing.
Dependencies: json, pathlib, dataclasses
Used by: demo_game.scenarios, demo_game.ui.branch_panel,
         demo_game.tests.test_branch_state
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Cache file path — mirrors the pattern used by the aldric_quest cache in seed.py.
_CACHE_PATH: Path = Path(".cache/demo/branch_state.json")

# JSON schema version — bump if the persisted format changes.
_SCHEMA_VERSION: int = 1


@dataclass(frozen=True)
class ChoiceRecord:
    """A single recorded player choice at a branch node.

    Attributes:
        branch_id: Stable ID of the BranchNode.
        option_index: Zero-based index of the chosen option.
        label: Display label of the chosen option (for human-readable replay).
    """

    branch_id: str
    option_index: int
    label: str

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON persistence.

        Returns:
            Dict with branch_id, option_index, and label keys.
        """
        return {
            "branch_id": self.branch_id,
            "option_index": self.option_index,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChoiceRecord:
        """Deserialise from a dict previously produced by to_dict.

        Args:
            data: Dict with branch_id, option_index, and label keys.
        Returns:
            ChoiceRecord instance.
        Raises:
            KeyError: If a required key is missing.
        """
        return cls(
            branch_id=data["branch_id"],
            option_index=int(data["option_index"]),
            label=data["label"],
        )


@dataclass(frozen=True)
class BranchState:
    """Immutable ordered record of all branch choices taken this session.

    with_choice returns a new BranchState (immutability rule — never mutates).

    Attributes:
        choices: Ordered tuple of ChoiceRecord instances.
    """

    choices: tuple[ChoiceRecord, ...] = field(default_factory=tuple)

    def with_choice(self, branch_id: str, option_index: int, label: str) -> BranchState:
        """Return a new BranchState with the given choice appended.

        Args:
            branch_id: Stable ID of the BranchNode.
            option_index: Zero-based index of the chosen option.
            label: Display label of the chosen option.
        Returns:
            New BranchState with the choice appended.
        """
        new_record = ChoiceRecord(
            branch_id=branch_id,
            option_index=option_index,
            label=label,
        )
        return BranchState(choices=self.choices + (new_record,))

    def has_chosen(self, branch_id: str) -> bool:
        """Return True if a choice has been recorded for branch_id.

        Args:
            branch_id: Stable ID of the BranchNode.
        Returns:
            True if branch_id appears in choices.
        """
        return any(c.branch_id == branch_id for c in self.choices)

    def choice_for(self, branch_id: str) -> ChoiceRecord | None:
        """Return the ChoiceRecord for branch_id, or None if not yet chosen.

        Args:
            branch_id: Stable ID of the BranchNode.
        Returns:
            ChoiceRecord or None.
        """
        for c in self.choices:
            if c.branch_id == branch_id:
                return c
        return None

    def to_json(self) -> str:
        """Serialise to a JSON string.

        Returns:
            JSON string representation of this BranchState.
        """
        payload = {
            "version": _SCHEMA_VERSION,
            "choices": [c.to_dict() for c in self.choices],
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def from_json(cls, text: str) -> BranchState:
        """Deserialise from a JSON string produced by to_json.

        Args:
            text: JSON string.
        Returns:
            BranchState instance.
        Raises:
            ValueError: If the JSON is structurally invalid.
        """
        try:
            payload = json.loads(text)
            records = tuple(
                ChoiceRecord.from_dict(item) for item in payload.get("choices", [])
            )
            return cls(choices=records)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot deserialise BranchState: {exc}") from exc


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def save_branch_state(state: BranchState, path: Path = _CACHE_PATH) -> None:
    """Persist a BranchState to the cache file.

    Creates parent directories if they do not exist (mirrors seed.py pattern).

    Args:
        state: BranchState to persist.
        path: Destination file path (default: .cache/demo/branch_state.json).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json(), encoding="utf-8")


def load_branch_state(path: Path = _CACHE_PATH) -> BranchState:
    """Load a BranchState from the cache file, returning empty state if absent.

    Args:
        path: Source file path (default: .cache/demo/branch_state.json).
    Returns:
        Persisted BranchState, or a fresh empty BranchState if the file
        does not exist or is unreadable.
    """
    if not path.exists():
        return BranchState()
    try:
        return BranchState.from_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return BranchState()
