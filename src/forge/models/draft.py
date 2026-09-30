"""Data models for decomposing draft artifacts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class DraftItem(BaseModel):
    """Represents an individual proposed Story or Task inside a draft."""

    model_config = {"extra": "forbid"}

    id: int
    """Local sequential ID, e.g., 1, 2, 3."""

    summary: str
    """Brief summary of the proposed item."""

    description: str
    """Detailed description of the proposed item."""

    repo: str
    """Target repository name."""

    acceptance_criteria: list[str]
    """List of acceptance criteria for this item."""

    excluded: bool = False
    """Whether this item should be excluded from ticket creation."""

    epic_key: str | None = None
    """Optional Jira key of the parent epic for this task."""


class ForgeDecompositionDraft(BaseModel):
    """Represents the wrapper of all draft items and execution metadata."""

    parent_key: str
    """Jira key of the parent feature or epic."""

    phase: Literal["epics", "tasks"]
    """Phase of the draft, either "epics" or "tasks"."""

    items: list[DraftItem]
    """List of draft items (proposed Stories or Tasks)."""

    version: int = 1
    """Draft schema version."""

    created_at: datetime
    """Timestamp when this draft was created."""

    updated_at: datetime
    """Timestamp when this draft was last updated."""

    @model_validator(mode="after")
    def _validate_sequential_ids(self) -> "ForgeDecompositionDraft":
        """Validate that local item IDs are unique and sequential (1, 2, 3...) within the draft."""
        if not self.items:
            return self

        ids = [item.id for item in self.items]

        # Check uniqueness
        if len(ids) != len(set(ids)):
            raise ValueError("Draft item IDs must be unique.")

        # Check that IDs are sequential starting from 1
        sorted_ids = sorted(ids)
        expected_ids = list(range(1, len(self.items) + 1))
        if sorted_ids != expected_ids:
            raise ValueError(
                f"Draft item IDs must be sequential starting from 1. Got: {sorted_ids}, expected: {expected_ids}"
            )

        return self
