"""Unit tests for implementation node — structured logging tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestImplementationStructuredLogging:
    """Tests for implementation start/end structured logging."""

    @pytest.mark.asyncio
    async def test_start_log_emitted_with_all_fields(self, caplog):
        """TS-001: Assert INFO log with 'Implementation started' and all extra fields."""
        state = _make_state(
            ticket_key="FEAT-200",
            current_task_key="TASK-10",
        )

        mock_jira = _make_mock_jira(summary="Implement login feature")
        mock_runner = _make_mock_runner(success=True)

        with (
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            caplog.at_level(logging.INFO),
        ):
            await implement_task(state)

        # Find the start log record
        start_records = [r for r in caplog.records if "Implementation started" in r.message]
        assert len(start_records) >= 1, "Expected 'Implementation started' log"

        record = start_records[0]
        assert record.levelno == logging.INFO

        # Verify extra fields
        assert record.__dict__.get("event") == "implementation_started"
        assert record.__dict__.get("task_name") == "Implement login feature"
        assert record.__dict__.get("feature_id") == "FEAT-200"
        assert record.__dict__.get("task_id") == "TASK-10"

    @pytest.mark.asyncio
    async def test_end_log_success_emitted_on_successful_implementation(self, caplog):
        """TS-002: Assert INFO log with 'Implementation completed' and status=success."""
        state = _make_state(
            ticket_key="FEAT-300",
            current_task_key="TASK-20",
        )

        mock_jira = _make_mock_jira(summary="Add user validation")
        mock_runner = _make_mock_runner(success=True)

        with (
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            caplog.at_level(logging.INFO),
        ):
            await implement_task(state)

        # Find the completion log record
        end_records = [
            r
            for r in caplog.records
            if "Implementation completed" in r.message and "status=success" in r.message
        ]
        assert len(end_records) >= 1, "Expected 'Implementation completed' log with status=success"

        record = end_records[0]
        assert record.levelno == logging.INFO
        assert record.__dict__.get("status") == "success"

    @pytest.mark.asyncio
    async def test_end_log_failure_emitted_on_container_failure(self, caplog):
        """TS-003: Assert INFO log with status=failure when container fails."""
        state = _make_state(
            ticket_key="FEAT-400",
            current_task_key="TASK-30",
        )

        mock_jira = _make_mock_jira(summary="Fix database connection")
        mock_runner = _make_mock_runner(success=False, error_message="Container crashed")

        with (
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            patch("forge.workflow.nodes.error_handler.notify_error", new_callable=AsyncMock),
            caplog.at_level(logging.INFO),
        ):
            # Container failure triggers exception handler path
            await implement_task(state)

        # Find the failure log record
        end_records = [
            r
            for r in caplog.records
            if "Implementation completed" in r.message and "status=failure" in r.message
        ]
        assert len(end_records) >= 1, "Expected 'Implementation completed' log with status=failure"

        record = end_records[0]
        assert record.levelno == logging.INFO
        assert record.__dict__.get("status") == "failure"

    @pytest.mark.asyncio
    async def test_end_log_failure_emitted_on_exception(self, caplog):
        """TS-004: Assert failure log is emitted when Jira or container raises exception."""
        state = _make_state(
            ticket_key="FEAT-500",
            current_task_key="TASK-40",
        )

        mock_jira = _make_mock_jira(summary="Refactor API endpoints")
        # Make runner raise an exception after task_summary is set
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=RuntimeError("Network timeout"))

        with (
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            patch("forge.workflow.nodes.error_handler.notify_error", new_callable=AsyncMock),
            caplog.at_level(logging.INFO),
        ):
            result = await implement_task(state)

        # Verify exception was handled
        assert result.get("last_error") is not None

        # Find the failure log record in exception handler
        end_records = [
            r
            for r in caplog.records
            if "Implementation completed" in r.message and "status=failure" in r.message
        ]
        assert len(end_records) >= 1, "Expected failure log even on exception"

        record = end_records[0]
        assert record.__dict__.get("status") == "failure"
        assert record.__dict__.get("event") == "implementation_completed"

    @pytest.mark.asyncio
    async def test_no_task_logs_when_no_task_available(self, caplog):
        """TS-005: No implementation logs when current_task_key=None and all tasks implemented."""
        state = _make_state(
            ticket_key="FEAT-600",
            current_task_key=None,
            task_keys=["TASK-50", "TASK-51"],
            tasks_by_repo={"org/repo": ["TASK-50", "TASK-51"]},
            implemented_tasks=["TASK-50", "TASK-51"],  # All tasks already done
        )

        mock_git = MagicMock()
        mock_git.has_uncommitted_changes.return_value = False

        with (
            patch("forge.workflow.nodes.implementation.JiraClient"),
            patch("forge.workflow.nodes.implementation.ContainerRunner"),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            patch("forge.workflow.nodes.implementation.GitOperations", return_value=mock_git),
            patch("forge.workflow.nodes.implementation.Workspace"),
            caplog.at_level(logging.INFO),
        ):
            await implement_task(state)

        # Verify no implementation start/end logs
        start_logs = [r for r in caplog.records if "Implementation started" in r.message]
        end_logs = [r for r in caplog.records if "Implementation completed" in r.message]

        assert len(start_logs) == 0, "No 'Implementation started' log when no task available"
        assert len(end_logs) == 0, "No 'Implementation completed' log when no task available"

        # But there should be an "All tasks implemented" log
        all_tasks_logs = [r for r in caplog.records if "All tasks implemented" in r.message]
        assert len(all_tasks_logs) >= 1

    @pytest.mark.asyncio
    async def test_log_extra_fields_contain_correct_values(self, caplog):
        """TS-006: Verify exact values in extra dict match input state."""
        state = _make_state(
            ticket_key="PROJ-999",
            current_task_key="IMPL-777",
            current_repo="myorg/myrepo",
        )

        task_summary = "Exact Summary Match Test"
        mock_jira = _make_mock_jira(summary=task_summary)
        mock_runner = _make_mock_runner(success=True)

        with (
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.implementation.get_settings", return_value=MagicMock()),
            caplog.at_level(logging.INFO),
        ):
            await implement_task(state)

        # Check start log extra fields
        start_records = [r for r in caplog.records if "Implementation started" in r.message]
        assert len(start_records) >= 1

        start_record = start_records[0]
        assert start_record.__dict__.get("event") == "implementation_started"
        assert start_record.__dict__.get("task_name") == task_summary
        assert start_record.__dict__.get("feature_id") == "PROJ-999"
        assert start_record.__dict__.get("task_id") == "IMPL-777"

        # Check end log extra fields
        end_records = [r for r in caplog.records if "Implementation completed" in r.message]
        assert len(end_records) >= 1

        end_record = end_records[0]
        assert end_record.__dict__.get("event") == "implementation_completed"
        assert end_record.__dict__.get("task_name") == task_summary
        assert end_record.__dict__.get("feature_id") == "PROJ-999"
        assert end_record.__dict__.get("task_id") == "IMPL-777"
        assert end_record.__dict__.get("status") == "success"
