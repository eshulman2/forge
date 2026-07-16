"""Unit tests for implement_task structured logging."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.fixtures.workflow_states import make_workflow_state

from forge.integrations.jira.models import JiraIssue


def _make_state(
    ticket_key: str = "TEST-123",
    current_task_key: str = "TEST-456",
    workspace_path: str = "/tmp/workspace",
    current_repo: str = "org/repo",
    **overrides,
):
    """Create a workflow state for implement_task tests."""
    return make_workflow_state(
        ticket_key=ticket_key,
        current_node="implement_task",
        current_task_key=current_task_key,
        workspace_path=workspace_path,
        current_repo=current_repo,
        task_keys=[current_task_key],
        tasks_by_repo={current_repo: [current_task_key]},
        implemented_tasks=[],
        **overrides,
    )


def _make_mock_jira(summary: str = "Test Task Summary", description: str = "Test description"):
    """Create a mock JiraClient with configurable issue data."""
    jira = MagicMock()
    jira.get_issue = AsyncMock(
        return_value=JiraIssue(
            key="TEST-456",
            id="10001",
            summary=summary,
            description=description,
            status="In Progress",
            issue_type="Task",
        )
    )
    jira.close = AsyncMock()
    return jira


def _make_successful_runner():
    """Create a mock ContainerRunner that returns success."""
    from forge.sandbox.runner import ContainerResult

    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=ContainerResult(
            success=True,
            exit_code=0,
            stdout="Success",
            stderr="",
            tests_passed=True,
        )
    )
    return runner


def _make_failed_runner(error_message: str = "Container failed"):
    """Create a mock ContainerRunner that returns failure."""
    from forge.sandbox.runner import ContainerResult

    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=ContainerResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error",
            tests_passed=False,
            error_message=error_message,
        )
    )
    return runner


class TestImplementTaskStructuredLogging:
    """Tests for structured logging in implement_task node."""

    @pytest.mark.asyncio
    async def test_logs_implementation_started_with_structured_fields(self, caplog):
        """Verify start log has event, task_name, feature_id, task_id fields."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary="Implement login feature")
        mock_runner = _make_successful_runner()

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_started"
        ]
        assert len(started_records) == 1, "Expected exactly one implementation_started log"

        record = started_records[0]
        assert record.levelno == logging.INFO
        assert record.event == "implementation_started"
        assert record.task_name == "Implement login feature"
        assert record.feature_id == "FEAT-100"
        assert record.task_id == "TASK-200"

    @pytest.mark.asyncio
    async def test_logs_implementation_completed_on_success(self, caplog):
        """Verify success end log has event, task_name, feature_id, task_id, success=True."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary="Implement login feature")
        mock_runner = _make_successful_runner()

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_completed log record
        completed_records = [
            r
            for r in caplog.records
            if hasattr(r, "event") and r.event == "implementation_completed"
        ]
        assert len(completed_records) == 1, "Expected exactly one implementation_completed log"

        record = completed_records[0]
        assert record.levelno == logging.INFO
        assert record.event == "implementation_completed"
        assert record.task_name == "Implement login feature"
        assert record.feature_id == "FEAT-100"
        assert record.task_id == "TASK-200"
        assert record.success is True

    @pytest.mark.asyncio
    async def test_logs_implementation_ended_on_failure(self, caplog):
        """Verify failure end log has event, task_name, feature_id, task_id, success=False."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary="Implement login feature")
        mock_runner = _make_failed_runner(error_message="Container execution failed")

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.error_handler.notify_error", AsyncMock()),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_ended log record
        ended_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_ended"
        ]
        assert len(ended_records) == 1, "Expected exactly one implementation_ended log"

        record = ended_records[0]
        assert record.levelno == logging.INFO
        assert record.event == "implementation_ended"
        assert record.task_name == "Implement login feature"
        assert record.feature_id == "FEAT-100"
        assert record.task_id == "TASK-200"
        assert record.success is False

    @pytest.mark.asyncio
    async def test_logs_implementation_ended_on_exception(self, caplog):
        """Verify exception path emits end log with success=False."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary="Implement login feature")

        # Runner raises an exception
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(side_effect=RuntimeError("Unexpected container error"))

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            patch("forge.workflow.nodes.error_handler.notify_error", AsyncMock()),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_ended log record
        ended_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_ended"
        ]
        assert len(ended_records) == 1, "Expected exactly one implementation_ended log"

        record = ended_records[0]
        assert record.levelno == logging.INFO
        assert record.event == "implementation_ended"
        assert record.task_name == "Implement login feature"
        assert record.feature_id == "FEAT-100"
        assert record.task_id == "TASK-200"
        assert record.success is False

    @pytest.mark.asyncio
    async def test_logs_unknown_task_name_when_jira_fails_early(self, caplog):
        """Verify placeholder 'unknown' is used when Jira fetch fails."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")

        # Jira client raises exception
        mock_jira = MagicMock()
        mock_jira.get_issue = AsyncMock(side_effect=RuntimeError("Jira unavailable"))
        mock_jira.close = AsyncMock()

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.error_handler.notify_error", AsyncMock()),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_ended log record
        ended_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_ended"
        ]
        assert len(ended_records) == 1, "Expected exactly one implementation_ended log"

        record = ended_records[0]
        assert record.levelno == logging.INFO
        assert record.event == "implementation_ended"
        assert record.task_name == "unknown"
        assert record.feature_id == "FEAT-100"
        assert record.task_id == "TASK-200"
        assert record.success is False

    @pytest.mark.asyncio
    async def test_logs_empty_task_summary_as_empty_string(self, caplog):
        """Verify empty summary is handled as empty string, not placeholder."""
        from forge.workflow.nodes.implementation import implement_task

        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary="")  # Empty summary
        mock_runner = _make_successful_runner()

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_started"
        ]
        assert len(started_records) == 1, "Expected exactly one implementation_started log"

        record = started_records[0]
        assert record.levelno == logging.INFO
        assert record.task_name == ""

    @pytest.mark.asyncio
    async def test_logs_special_characters_in_task_summary(self, caplog):
        """Verify special characters in summary are not escaped."""
        from forge.workflow.nodes.implementation import implement_task

        special_summary = "Fix bug: <script>alert('xss')</script> & more \"quotes\""
        state = _make_state(ticket_key="FEAT-100", current_task_key="TASK-200")
        mock_jira = _make_mock_jira(summary=special_summary)
        mock_runner = _make_successful_runner()

        with (
            patch("forge.workflow.nodes.implementation.get_settings"),
            patch("forge.workflow.nodes.implementation.JiraClient", return_value=mock_jira),
            patch("forge.workflow.nodes.implementation.ContainerRunner", return_value=mock_runner),
            caplog.at_level(logging.INFO, logger="forge.workflow.nodes.implementation"),
        ):
            await implement_task(state)

        # Find the implementation_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "implementation_started"
        ]
        assert len(started_records) == 1, "Expected exactly one implementation_started log"

        record = started_records[0]
        assert record.levelno == logging.INFO
        # Verify special characters are NOT escaped - passed through as-is
        assert record.task_name == special_summary
        assert "<script>" in record.task_name
        assert "'" in record.task_name
        assert '"' in record.task_name
        assert "&" in record.task_name
