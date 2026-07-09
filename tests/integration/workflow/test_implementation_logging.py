"""Integration tests for JSON structured logging from implementation node.

These tests verify that logs emitted by implement_task are properly formatted
as JSON with all required fields when using the StructuredFormatter.

Test TS-007: Verifies JSON output includes all spec-required fields.
"""

import json
import logging
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.utils.logging import StructuredFormatter
from forge.workflow.nodes.implementation import implement_task


def _make_state(
    ticket_key: str = "FEAT-100",
    current_task_key: str | None = "TASK-1",
    workspace_path: str = "/tmp/workspace",
    current_repo: str = "org/repo",
    task_keys: list[str] | None = None,
    tasks_by_repo: dict[str, list[str]] | None = None,
    implemented_tasks: list[str] | None = None,
    context: dict | None = None,
) -> dict:
    """Create a minimal state for implementation testing."""
    if task_keys is None:
        task_keys = ["TASK-1", "TASK-2"]
    if tasks_by_repo is None:
        tasks_by_repo = {current_repo: task_keys}
    if implemented_tasks is None:
        implemented_tasks = []
    if context is None:
        context = {"guardrails": ""}

    return {
        "ticket_key": ticket_key,
        "current_task_key": current_task_key,
        "workspace_path": workspace_path,
        "current_repo": current_repo,
        "task_keys": task_keys,
        "tasks_by_repo": tasks_by_repo,
        "implemented_tasks": implemented_tasks,
        "context": context,
        "retry_count": 0,
    }


def _make_mock_jira(summary: str = "Test Task Summary", description: str = "Test description"):
    """Create a mock JiraClient with a configurable issue."""
    mock_jira = MagicMock()
    mock_issue = MagicMock()
    mock_issue.summary = summary
    mock_issue.description = description
    mock_jira.get_issue = AsyncMock(return_value=mock_issue)
    mock_jira.close = AsyncMock()
    return mock_jira


def _make_mock_runner(success: bool = True, error_message: str | None = None):
    """Create a mock ContainerRunner with configurable result."""
    mock_runner = MagicMock()
    mock_result = MagicMock()
    mock_result.success = success
    mock_result.exit_code = 0 if success else 1
    mock_result.error_message = error_message
    mock_runner.run = AsyncMock(return_value=mock_result)
    return mock_runner


class TestImplementationLoggingJSON:
    """Integration tests for JSON structured logging from implementation node."""

    @pytest.mark.asyncio
    async def test_json_output_includes_all_required_fields(self):
        """TS-007: Verify JSON output is parseable and contains all required fields.

        This test validates that:
        - Logs are properly formatted as JSON
        - Start log contains: timestamp, level, message, event, task_name, feature_id, task_id
        - End log contains all start fields plus status field
        """
        # Set up logger with StructuredFormatter
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())

        impl_logger = logging.getLogger("forge.workflow.nodes.implementation")
        original_level = impl_logger.level
        impl_logger.addHandler(handler)
        impl_logger.setLevel(logging.INFO)

        try:
            # Set up state and mocks
            state = _make_state(
                ticket_key="FEAT-JSON-100",
                current_task_key="TASK-JSON-1",
            )

            mock_jira = _make_mock_jira(summary="JSON Logging Test Task")
            mock_runner = _make_mock_runner(success=True)

            with (
                patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
                patch(
                    "forge.workflow.nodes.implementation.ContainerRunner",
                    return_value=mock_runner,
                ),
                patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            ):
                await implement_task(state)

            # Parse and verify JSON output
            stream.seek(0)
            lines = stream.readlines()

            # Verify we have log output
            assert len(lines) >= 2, "Expected at least 2 log lines (start and end)"

            # Track found logs
            found_start_log = False
            found_end_log = False

            for line in lines:
                # Each line should be valid JSON
                log_record = json.loads(line.strip())

                # Check for start log
                if "Implementation started" in log_record.get("message", ""):
                    found_start_log = True

                    # Assert required base fields
                    assert "timestamp" in log_record, "Start log missing timestamp"
                    assert log_record["level"] == "INFO", "Start log level should be INFO"
                    assert "message" in log_record, "Start log missing message"
                    assert "logger" in log_record, "Start log missing logger"

                    # Assert spec-required extra fields
                    assert log_record.get("event") == "implementation_started", (
                        "Start log missing or wrong event field"
                    )
                    assert log_record.get("task_name") == "JSON Logging Test Task", (
                        "Start log missing or wrong task_name"
                    )
                    assert log_record.get("feature_id") == "FEAT-JSON-100", (
                        "Start log missing or wrong feature_id"
                    )
                    assert log_record.get("task_id") == "TASK-JSON-1", (
                        "Start log missing or wrong task_id"
                    )

                # Check for end log with success status
                if "Implementation completed" in log_record.get(
                    "message", ""
                ) and "status=success" in log_record.get("message", ""):
                    found_end_log = True

                    # Assert required base fields
                    assert "timestamp" in log_record, "End log missing timestamp"
                    assert log_record["level"] == "INFO", "End log level should be INFO"
                    assert "message" in log_record, "End log missing message"

                    # Assert spec-required extra fields (including status)
                    assert log_record.get("event") == "implementation_completed", (
                        "End log missing or wrong event field"
                    )
                    assert log_record.get("task_name") == "JSON Logging Test Task", (
                        "End log missing or wrong task_name"
                    )
                    assert log_record.get("feature_id") == "FEAT-JSON-100", (
                        "End log missing or wrong feature_id"
                    )
                    assert log_record.get("task_id") == "TASK-JSON-1", (
                        "End log missing or wrong task_id"
                    )
                    assert log_record.get("status") == "success", (
                        "End log missing or wrong status field"
                    )

            assert found_start_log, "Did not find 'Implementation started' log"
            assert found_end_log, "Did not find 'Implementation completed' log with status=success"

        finally:
            # Cleanup: remove handler and restore log level
            impl_logger.removeHandler(handler)
            impl_logger.setLevel(original_level)

    @pytest.mark.asyncio
    async def test_json_output_failure_includes_status_field(self):
        """Verify JSON output for failure case includes status=failure.

        This test ensures that when implementation fails, the structured JSON
        output includes the status field set to 'failure'.
        """
        # Set up logger with StructuredFormatter
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())

        impl_logger = logging.getLogger("forge.workflow.nodes.implementation")
        original_level = impl_logger.level
        impl_logger.addHandler(handler)
        impl_logger.setLevel(logging.INFO)

        try:
            state = _make_state(
                ticket_key="FEAT-JSON-200",
                current_task_key="TASK-JSON-2",
            )

            mock_jira = _make_mock_jira(summary="Failing Task Test")
            mock_runner = _make_mock_runner(success=False, error_message="Container failed")

            with (
                patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
                patch(
                    "forge.workflow.nodes.implementation.ContainerRunner",
                    return_value=mock_runner,
                ),
                patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
                patch("forge.workflow.nodes.error_handler.notify_error", new_callable=AsyncMock),
            ):
                await implement_task(state)

            # Parse and verify JSON output
            stream.seek(0)
            lines = stream.readlines()

            # Find the failure end log
            found_failure_log = False

            for line in lines:
                log_record = json.loads(line.strip())

                if "Implementation completed" in log_record.get(
                    "message", ""
                ) and "status=failure" in log_record.get("message", ""):
                    found_failure_log = True

                    # Assert status field is present and correct
                    assert log_record.get("status") == "failure", (
                        "Failure log missing or wrong status field"
                    )
                    assert log_record.get("event") == "implementation_completed", (
                        "Failure log missing or wrong event field"
                    )
                    assert "timestamp" in log_record, "Failure log missing timestamp"
                    assert log_record["level"] == "INFO", "Failure log level should be INFO"

            assert found_failure_log, (
                "Did not find 'Implementation completed' log with status=failure"
            )

        finally:
            # Cleanup
            impl_logger.removeHandler(handler)
            impl_logger.setLevel(original_level)

    @pytest.mark.asyncio
    async def test_json_output_is_parseable_for_all_logs(self):
        """Verify all emitted logs are valid JSON when using StructuredFormatter.

        This test ensures no log lines fail JSON parsing, which is critical for
        log aggregation systems.
        """
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())

        impl_logger = logging.getLogger("forge.workflow.nodes.implementation")
        original_level = impl_logger.level
        impl_logger.addHandler(handler)
        impl_logger.setLevel(logging.DEBUG)  # Capture all log levels

        try:
            state = _make_state(
                ticket_key="FEAT-JSON-300",
                current_task_key="TASK-JSON-3",
            )

            mock_jira = _make_mock_jira(summary="Parse Test Task")
            mock_runner = _make_mock_runner(success=True)

            with (
                patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
                patch(
                    "forge.workflow.nodes.implementation.ContainerRunner",
                    return_value=mock_runner,
                ),
                patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            ):
                await implement_task(state)

            # Verify all lines are valid JSON
            stream.seek(0)
            lines = stream.readlines()

            assert len(lines) > 0, "Expected at least one log line"

            for i, line in enumerate(lines):
                try:
                    json.loads(line.strip())
                except json.JSONDecodeError as e:
                    pytest.fail(f"Line {i + 1} is not valid JSON: {line!r}. Error: {e}")

        finally:
            impl_logger.removeHandler(handler)
            impl_logger.setLevel(original_level)
