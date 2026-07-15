"""Unit tests for step logger context validation utilities."""

from forge.utils.step_logger import (
    PLACEHOLDER_UNAVAILABLE,
    ValidationResult,
    validate_context,
)


def test_all_context_values_present_returns_valid() -> None:
    """When all context values are present, result is valid with no warnings."""
    result = validate_context(
        task_name="my_task",
        feature_id="FEAT-123",
        task_id="TASK-456",
    )

    assert result.is_valid is True
    assert result.warnings == []


def test_missing_task_name_returns_invalid() -> None:
    """When task_name is None, result is invalid with task name warning."""
    result = validate_context(
        task_name=None,
        feature_id="FEAT-123",
        task_id="TASK-456",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Task name" in result.warnings[0]
    assert PLACEHOLDER_UNAVAILABLE in result.warnings[0]


def test_missing_feature_id_returns_invalid() -> None:
    """When feature_id is None, result is invalid with feature ID warning."""
    result = validate_context(
        task_name="my_task",
        feature_id=None,
        task_id="TASK-456",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Feature ID" in result.warnings[0]
    assert PLACEHOLDER_UNAVAILABLE in result.warnings[0]


def test_missing_task_id_returns_invalid() -> None:
    """When task_id is None, result is invalid with task ID warning."""
    result = validate_context(
        task_name="my_task",
        feature_id="FEAT-123",
        task_id=None,
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Task ID" in result.warnings[0]
    assert PLACEHOLDER_UNAVAILABLE in result.warnings[0]


def test_multiple_missing_values_returns_warnings_for_each() -> None:
    """When multiple values are missing, result has warnings for each."""
    result = validate_context(
        task_name=None,
        feature_id=None,
        task_id="TASK-456",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 2
    # Verify both missing fields are mentioned
    warning_text = " ".join(result.warnings)
    assert "Task name" in warning_text
    assert "Feature ID" in warning_text


def test_all_values_missing_returns_three_warnings() -> None:
    """When all values are missing, result has warnings for all three."""
    result = validate_context(
        task_name=None,
        feature_id=None,
        task_id=None,
    )

    assert result.is_valid is False
    assert len(result.warnings) == 3
    # Verify all missing fields are mentioned
    warning_text = " ".join(result.warnings)
    assert "Task name" in warning_text
    assert "Feature ID" in warning_text
    assert "Task ID" in warning_text


def test_empty_string_task_name_treated_as_missing() -> None:
    """Empty string task_name is treated as missing."""
    result = validate_context(
        task_name="",
        feature_id="FEAT-123",
        task_id="TASK-456",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Task name" in result.warnings[0]


def test_empty_string_feature_id_treated_as_missing() -> None:
    """Empty string feature_id is treated as missing."""
    result = validate_context(
        task_name="my_task",
        feature_id="",
        task_id="TASK-456",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Feature ID" in result.warnings[0]


def test_empty_string_task_id_treated_as_missing() -> None:
    """Empty string task_id is treated as missing."""
    result = validate_context(
        task_name="my_task",
        feature_id="FEAT-123",
        task_id="",
    )

    assert result.is_valid is False
    assert len(result.warnings) == 1
    assert "Task ID" in result.warnings[0]


def test_validation_result_default_warnings_list() -> None:
    """ValidationResult has default empty warnings list."""
    result = ValidationResult(is_valid=True)

    assert result.warnings == []


def test_validation_result_with_explicit_warnings() -> None:
    """ValidationResult can be created with explicit warnings."""
    warnings = ["Warning 1", "Warning 2"]
    result = ValidationResult(is_valid=False, warnings=warnings)

    assert result.is_valid is False
    assert result.warnings == warnings
