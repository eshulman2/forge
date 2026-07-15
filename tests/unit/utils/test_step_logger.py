"""Unit tests for step logger context validation utilities."""

import logging
import re
import time

import pytest

from forge.utils.step_logger import (
    PLACEHOLDER_UNAVAILABLE,
    ValidationResult,
    log_step_end,
    log_step_start,
    step_logging_context,
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


# -----------------------------------------------------------------------------
# Tests for step_logging_context
# -----------------------------------------------------------------------------


class TestStepLoggingContext:
    """Tests for step_logging_context context manager."""

    def test_context_manager_logs_start_and_end_on_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Context manager logs start and end on successful execution."""
        with (
            caplog.at_level(logging.INFO, logger="forge.utils.step_logger"),
            step_logging_context(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            ),
        ):
            pass  # Successful execution

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 2

        # First log should indicate start, second should indicate end
        assert "Step starting" in info_records[0].message
        assert "Step ended" in info_records[1].message

        # Both logs should contain context values
        for record in info_records:
            assert "deploy-service" in record.message
            assert "FEAT-123" in record.message
            assert "TASK-456" in record.message

    def test_context_manager_logs_start_and_end_when_exception_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Context manager logs start and end when exception is raised."""
        with (
            caplog.at_level(logging.INFO, logger="forge.utils.step_logger"),
            pytest.raises(ValueError, match="test error"),
            step_logging_context(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            ),
        ):
            raise ValueError("test error")

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 2

        # First log should indicate start, second should indicate end
        assert "Step starting" in info_records[0].message
        assert "Step ended" in info_records[1].message

    def test_context_manager_exception_is_reraised_not_swallowed(self) -> None:
        """Exception is re-raised after end log (not swallowed)."""
        with (
            pytest.raises(RuntimeError, match="intentional exception"),
            step_logging_context(
                task_name="deploy-service",
                feature_id="FEAT-123",
                task_id="TASK-456",
            ),
        ):
            raise RuntimeError("intentional exception")

    def test_context_manager_end_log_emitted_before_exception_propagates(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """End log is emitted before exception propagates.

        This test verifies that the finally block executes and logs
        'Step ended' before the exception reaches the outer scope.
        """
        end_log_emitted = False
        exception_caught = False

        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            try:
                with step_logging_context(
                    task_name="deploy-service",
                    feature_id="FEAT-123",
                    task_id="TASK-456",
                ):
                    raise ValueError("test error")
            except ValueError:
                # Check if end log was emitted before we caught the exception
                info_records = [r for r in caplog.records if r.levelno == logging.INFO]
                end_log_emitted = any("Step ended" in r.message for r in info_records)
                exception_caught = True

        # Verify both conditions
        assert exception_caught, "Exception should have been caught"
        assert end_log_emitted, "End log should be emitted before exception propagates"


# -----------------------------------------------------------------------------
# Performance Tests
# -----------------------------------------------------------------------------


class TestStepLoggerPerformance:
    """Performance tests for step logger functions.

    These tests verify logging overhead is <10ms per call as specified
    in FN-001/FN-002 requirements. This is a basic sanity check,
    not a rigorous benchmark.
    """

    def test_log_step_start_overhead_under_10ms(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_step_start overhead is <10ms per call."""
        iterations = 100
        max_allowed_ms = 10.0

        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            start_time = time.perf_counter()
            for _ in range(iterations):
                log_step_start(
                    task_name="deploy-service",
                    feature_id="FEAT-123",
                    task_id="TASK-456",
                )
            end_time = time.perf_counter()

        total_duration_ms = (end_time - start_time) * 1000
        average_duration_ms = total_duration_ms / iterations

        assert average_duration_ms < max_allowed_ms, (
            f"log_step_start average duration {average_duration_ms:.3f}ms "
            f"exceeds {max_allowed_ms}ms threshold"
        )

    def test_log_step_end_overhead_under_10ms(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_step_end overhead is <10ms per call."""
        iterations = 100
        max_allowed_ms = 10.0

        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            start_time = time.perf_counter()
            for _ in range(iterations):
                log_step_end(
                    task_name="deploy-service",
                    feature_id="FEAT-123",
                    task_id="TASK-456",
                )
            end_time = time.perf_counter()

        total_duration_ms = (end_time - start_time) * 1000
        average_duration_ms = total_duration_ms / iterations

        assert average_duration_ms < max_allowed_ms, (
            f"log_step_end average duration {average_duration_ms:.3f}ms "
            f"exceeds {max_allowed_ms}ms threshold"
        )

    def test_step_logging_context_overhead_under_10ms(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify step_logging_context overhead is <10ms per call.

        Note: This measures the combined overhead of start + end logging.
        The 10ms threshold applies to the context manager entry/exit combined.
        """
        iterations = 100
        max_allowed_ms = 10.0

        with caplog.at_level(logging.INFO, logger="forge.utils.step_logger"):
            start_time = time.perf_counter()
            for _ in range(iterations):
                with step_logging_context(
                    task_name="deploy-service",
                    feature_id="FEAT-123",
                    task_id="TASK-456",
                ):
                    pass  # Empty context block
            end_time = time.perf_counter()

        total_duration_ms = (end_time - start_time) * 1000
        average_duration_ms = total_duration_ms / iterations

        assert average_duration_ms < max_allowed_ms, (
            f"step_logging_context average duration {average_duration_ms:.3f}ms "
            f"exceeds {max_allowed_ms}ms threshold"
        )
