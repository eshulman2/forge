"""Unit tests for step logger context validation utilities."""

import logging
import re

import pytest

from forge.utils.step_logger import (
    PLACEHOLDER_UNAVAILABLE,
    ValidationResult,
    log_step_end,
    log_step_start,
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


# -----------------------------------------------------------------------------
# Tests for log_step_start
# -----------------------------------------------------------------------------


class TestLogStepStart:
    """Tests for log_step_start function."""

    def test_log_step_start_emits_info_log_with_all_context_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start emits INFO log before implementation step with all context."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        # Verify INFO log was emitted
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify message indicates "Step starting"
        assert "Step starting" in info_records[0].message

        # Verify all context values are present
        assert "deploy-service" in info_records[0].message
        assert "FEAT-123" in info_records[0].message
        assert "TASK-456" in info_records[0].message

    def test_log_step_start_emits_log_with_placeholder_for_missing_task_name(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start uses placeholder when task_name is missing."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name=None,
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify placeholder is used for missing task_name
        assert PLACEHOLDER_UNAVAILABLE in info_records[0].message
        assert f"task_name={PLACEHOLDER_UNAVAILABLE}" in info_records[0].message

    def test_log_step_start_emits_log_with_placeholder_for_missing_feature_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start uses placeholder when feature_id is missing."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id=None,
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify placeholder is used for missing feature_id
        assert f"feature_id={PLACEHOLDER_UNAVAILABLE}" in info_records[0].message

    def test_log_step_start_emits_log_with_placeholder_for_missing_task_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start uses placeholder when task_id is missing."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id=None,
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify placeholder is used for missing task_id
        assert f"task_id={PLACEHOLDER_UNAVAILABLE}" in info_records[0].message

    def test_log_step_start_emits_warning_when_context_values_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start emits WARNING log when context values are missing."""
        with caplog.at_level(logging.WARNING, logger="forge.utils.step_logger"):
            log_step_start(
                task_name=None,
                feature_id=None,
                task_id=None,
            )

        # Verify WARNING logs were emitted for each missing value
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 3

        warning_messages = [r.message for r in warning_records]
        assert any("Task name" in msg for msg in warning_messages)
        assert any("Feature ID" in msg for msg in warning_messages)
        assert any("Task ID" in msg for msg in warning_messages)

    def test_log_step_start_no_warning_when_all_context_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start does not emit WARNING when all context values present."""
        with caplog.at_level(logging.WARNING, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        # Verify no WARNING logs were emitted
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0

    def test_log_step_start_message_contains_timestamp_in_expected_format(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start message contains timestamp in ISO 8601 format."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify timestamp is in ISO 8601 format: [YYYY-MM-DDTHH:MM:SS.ffffffZ]
        # The pattern matches: [2024-01-15T10:30:00.123456Z]
        iso_timestamp_pattern = r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\]"
        assert re.search(iso_timestamp_pattern, info_records[0].message) is not None

    def test_log_step_start_indicates_start_appropriately(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start message clearly indicates 'starting' not 'ended'."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify message indicates "starting" not "ended"
        assert "Step starting" in info_records[0].message
        assert "Step ended" not in info_records[0].message

    def test_log_step_start_includes_task_name_feature_id_task_id_in_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_start includes task_name, feature_id, task_id fields in log."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="my-task",
                feature_id="FEAT-999",
                task_id="TASK-888",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        message = info_records[0].message
        assert "task_name=my-task" in message
        assert "feature_id=FEAT-999" in message
        assert "task_id=TASK-888" in message


# -----------------------------------------------------------------------------
# Tests for log_step_end
# -----------------------------------------------------------------------------


class TestLogStepEnd:
    """Tests for log_step_end function."""

    def test_log_step_end_emits_info_log_with_all_context_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end emits INFO log after implementation step with all context."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_end(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        # Verify INFO log was emitted
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify message indicates "Step ended"
        assert "Step ended" in info_records[0].message

        # Verify all context values are present
        assert "deploy-service" in info_records[0].message
        assert "FEAT-123" in info_records[0].message
        assert "TASK-456" in info_records[0].message

    def test_log_step_end_emits_log_with_placeholders_for_missing_values(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end uses placeholders for all missing values."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_end(
                task_name=None,
                feature_id=None,
                task_id=None,
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify placeholders are used for all missing values
        message = info_records[0].message
        assert f"task_name={PLACEHOLDER_UNAVAILABLE}" in message
        assert f"feature_id={PLACEHOLDER_UNAVAILABLE}" in message
        assert f"task_id={PLACEHOLDER_UNAVAILABLE}" in message

    def test_log_step_end_emits_warning_when_context_values_missing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end emits WARNING log when context values are missing."""
        with caplog.at_level(logging.WARNING, logger="forge.utils.step_logger"):
            log_step_end(
                task_name=None,
                feature_id="FEAT-123",
                task_id=None,
            )

        # Verify WARNING logs were emitted for missing values
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 2

        warning_messages = [r.message for r in warning_records]
        assert any("Task name" in msg for msg in warning_messages)
        assert any("Task ID" in msg for msg in warning_messages)

    def test_log_step_end_no_warning_when_all_context_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end does not emit WARNING when all context values present."""
        with caplog.at_level(logging.WARNING, logger="forge.utils.step_logger"):
            log_step_end(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        # Verify no WARNING logs were emitted
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0

    def test_log_step_end_message_contains_timestamp_in_expected_format(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end message contains timestamp in ISO 8601 format."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_end(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify timestamp is in ISO 8601 format: [YYYY-MM-DDTHH:MM:SS.ffffffZ]
        iso_timestamp_pattern = r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\]"
        assert re.search(iso_timestamp_pattern, info_records[0].message) is not None

    def test_log_step_end_indicates_end_appropriately(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end message clearly indicates 'ended' not 'starting'."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_end(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        # Verify message indicates "ended" not "starting"
        assert "Step ended" in info_records[0].message
        assert "Step starting" not in info_records[0].message

    def test_log_step_end_includes_task_name_feature_id_task_id_in_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_step_end includes task_name, feature_id, task_id fields in log."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_end(
                task_name="my-task",
                feature_id="FEAT-999",
                task_id="TASK-888",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1

        message = info_records[0].message
        assert "task_name=my-task" in message
        assert "feature_id=FEAT-999" in message
        assert "task_id=TASK-888" in message


class TestLogStepStartAndEndDifferentiation:
    """Tests that verify start and end logs are distinguishable."""

    def test_start_and_end_logs_are_distinguishable(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_step_start and log_step_end produce different messages."""
        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            log_step_start(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )
            log_step_end(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            )

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 2

        # First log should indicate start, second should indicate end
        assert "Step starting" in info_records[0].message
        assert "Step ended" in info_records[1].message
