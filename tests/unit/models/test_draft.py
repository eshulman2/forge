"""Unit tests for decomposing draft models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.draft import DraftItem, ForgeDecompositionDraft


class TestDraftItem:
    """Tests for DraftItem model validation and serialization."""

    def test_valid_draft_item(self):
        """Verify that a valid DraftItem is successfully created."""
        item = DraftItem(
            id=1,
            summary="Implement auth route",
            description="Create endpoints for signing in and signing up",
            repo="auth-service",
            acceptance_criteria=[
                "POST /login returns JWT on success",
                "POST /register creates a new user",
            ],
        )
        assert item.id == 1
        assert item.summary == "Implement auth route"
        assert item.repo == "auth-service"
        assert len(item.acceptance_criteria) == 2

    def test_invalid_draft_item_types(self):
        """Verify that invalid types for DraftItem fields raise ValidationError."""
        with pytest.raises(ValidationError):
            DraftItem(
                id="invalid_id",  # Should be int
                summary="Implement auth route",
                description="Create endpoints for signing in and signing up",
                repo="auth-service",
                acceptance_criteria=["Criteria"],
            )


class TestForgeDecompositionDraft:
    """Tests for ForgeDecompositionDraft validation, serialization, and ID rules."""

    @pytest.fixture
    def valid_items(self) -> list[DraftItem]:
        """Return a list of valid, sequential DraftItem objects."""
        return [
            DraftItem(
                id=1,
                summary="Story 1",
                description="Description 1",
                repo="repo-a",
                acceptance_criteria=["Criteria 1"],
            ),
            DraftItem(
                id=2,
                summary="Story 2",
                description="Description 2",
                repo="repo-b",
                acceptance_criteria=["Criteria 2"],
            ),
            DraftItem(
                id=3,
                summary="Story 3",
                description="Description 3",
                repo="repo-a",
                acceptance_criteria=["Criteria 3"],
            ),
        ]

    def test_valid_draft_creation(self, valid_items):
        """Verify that a valid draft with unique, sequential IDs can be created."""
        now = datetime.now(UTC)
        draft = ForgeDecompositionDraft(
            parent_key="PROJ-123",
            phase="epics",
            items=valid_items,
            version=1,
            created_at=now,
            updated_at=now,
        )
        assert draft.parent_key == "PROJ-123"
        assert draft.phase == "epics"
        assert len(draft.items) == 3
        assert draft.version == 1
        assert draft.created_at == now
        assert draft.updated_at == now

    def test_valid_draft_with_empty_items(self):
        """Verify that a draft with an empty list of items is valid."""
        now = datetime.now(UTC)
        draft = ForgeDecompositionDraft(
            parent_key="PROJ-123",
            phase="tasks",
            items=[],
            version=2,
            created_at=now,
            updated_at=now,
        )
        assert draft.items == []

    def test_invalid_phase(self, valid_items):
        """Verify that a phase other than 'epics' or 'tasks' raises ValidationError."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError) as exc_info:
            ForgeDecompositionDraft(
                parent_key="PROJ-123",
                phase="invalid",  # Invalid phase
                items=valid_items,
                created_at=now,
                updated_at=now,
            )
        assert "Input should be 'epics'" in str(exc_info.value)

    def test_duplicate_ids(self):
        """Verify that duplicate item IDs raise ValidationError."""
        now = datetime.now(UTC)
        items_with_duplicates = [
            DraftItem(
                id=1,
                summary="Story 1",
                description="Description 1",
                repo="repo-a",
                acceptance_criteria=[],
            ),
            DraftItem(
                id=1,  # Duplicate
                summary="Story 2",
                description="Description 2",
                repo="repo-b",
                acceptance_criteria=[],
            ),
        ]
        with pytest.raises(ValidationError) as exc_info:
            ForgeDecompositionDraft(
                parent_key="PROJ-123",
                phase="epics",
                items=items_with_duplicates,
                created_at=now,
                updated_at=now,
            )
        assert "Draft item IDs must be unique." in str(exc_info.value)

    def test_non_sequential_ids(self):
        """Verify that non-sequential item IDs (gaps) raise ValidationError."""
        now = datetime.now(UTC)
        items_with_gap = [
            DraftItem(
                id=1,
                summary="Story 1",
                description="D1",
                repo="repo-a",
                acceptance_criteria=[],
            ),
            DraftItem(
                id=3,  # Gap: missing ID 2
                summary="Story 2",
                description="D2",
                repo="repo-b",
                acceptance_criteria=[],
            ),
        ]
        with pytest.raises(ValidationError) as exc_info:
            ForgeDecompositionDraft(
                parent_key="PROJ-123",
                phase="epics",
                items=items_with_gap,
                created_at=now,
                updated_at=now,
            )
        assert "Draft item IDs must be sequential starting from 1." in str(exc_info.value)

    def test_sequential_not_starting_from_one(self):
        """Verify that IDs that are sequential but do not start from 1 raise ValidationError."""
        now = datetime.now(UTC)
        items_not_starting_at_one = [
            DraftItem(
                id=2,  # Starts at 2
                summary="Story 1",
                description="D1",
                repo="repo-a",
                acceptance_criteria=[],
            ),
            DraftItem(
                id=3,
                summary="Story 2",
                description="D2",
                repo="repo-b",
                acceptance_criteria=[],
            ),
        ]
        with pytest.raises(ValidationError) as exc_info:
            ForgeDecompositionDraft(
                parent_key="PROJ-123",
                phase="epics",
                items=items_not_starting_at_one,
                created_at=now,
                updated_at=now,
            )
        assert "Draft item IDs must be sequential starting from 1." in str(exc_info.value)

    def test_unordered_but_valid_ids(self):
        """Verify that items with IDs that are unique and sequential starting from 1 are valid even if unordered in input."""
        now = datetime.now(UTC)
        unordered_items = [
            DraftItem(
                id=2,
                summary="Story 2",
                description="D2",
                repo="repo-b",
                acceptance_criteria=[],
            ),
            DraftItem(
                id=1,
                summary="Story 1",
                description="D1",
                repo="repo-a",
                acceptance_criteria=[],
            ),
        ]
        draft = ForgeDecompositionDraft(
            parent_key="PROJ-123",
            phase="epics",
            items=unordered_items,
            created_at=now,
            updated_at=now,
        )
        assert len(draft.items) == 2
        # Verify the original list order is preserved (or at least valid)
        assert draft.items[0].id == 2
        assert draft.items[1].id == 1

    def test_serialization_and_deserialization(self, valid_items):
        """Verify successful JSON serialization and deserialization of the draft model."""
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        draft = ForgeDecompositionDraft(
            parent_key="PROJ-123",
            phase="epics",
            items=valid_items,
            version=1,
            created_at=now,
            updated_at=now,
        )

        # Serialize to JSON
        json_data = draft.model_dump_json()

        # Deserialize back to a new model
        restored = ForgeDecompositionDraft.model_validate_json(json_data)

        assert restored.parent_key == draft.parent_key
        assert restored.phase == draft.phase
        assert restored.version == draft.version
        assert restored.created_at == draft.created_at
        assert restored.updated_at == draft.updated_at
        assert len(restored.items) == len(draft.items)
        for original, deserialized in zip(draft.items, restored.items, strict=True):
            assert original.id == deserialized.id
            assert original.summary == deserialized.summary
            assert original.description == deserialized.description
            assert original.repo == deserialized.repo
            assert original.acceptance_criteria == deserialized.acceptance_criteria
