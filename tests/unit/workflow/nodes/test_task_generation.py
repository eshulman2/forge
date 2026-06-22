"""Unit tests for task generation revision state."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.workflow.nodes.task_generation import generate_tasks, regenerate_all_tasks


@pytest.fixture
def base_state():
    return {
        "ticket_key": "MYPROJ-1",
        "ticket_type": "Feature",
        "spec_content": "Build a backend service.",
        "epic_keys": ["MYPROJ-10"],
        "task_keys": [],
        "tasks_by_repo": {},
        "retry_count": 0,
    }


@pytest.fixture
def mock_parent_issue():
    issue = MagicMock()
    issue.project_key = "MYPROJ"
    issue.summary = "Feature summary"
    return issue


@pytest.fixture
def mock_epic_issue():
    issue = MagicMock()
    issue.summary = "Epic summary"
    issue.description = "Implement the backend pieces."
    return issue


@pytest.fixture
def mock_tasks_data():
    return [
        {
            "summary": "Task One",
            "description": "Do the first thing.",
            "repo": "acme/backend",
        }
    ]


class TestTaskRevisionState:
    """Tests for task revision state cleanup."""

    @pytest.mark.asyncio
    async def test_generate_tasks_clears_revision_flags_on_success(
        self, base_state, mock_parent_issue, mock_epic_issue, mock_tasks_data
    ):
        """Successful task generation must not leave a pending revision at the gate."""
        state = {
            **base_state,
            "feedback_comment": "Split the tasks differently.",
            "revision_requested": True,
            "current_task_key": "MYPROJ-99",
            "current_epic_key": "MYPROJ-10",
        }

        with (
            patch("forge.workflow.nodes.task_generation.JiraClient") as MockJira,
            patch("forge.workflow.nodes.task_generation.ForgeAgent") as MockAgent,
            patch("forge.workflow.nodes.task_generation.post_status_comment"),
            patch(
                "forge.workflow.nodes.task_generation._generate_tasks_for_epic",
                new_callable=AsyncMock,
                return_value=mock_tasks_data,
            ),
        ):
            mock_jira = AsyncMock()
            MockJira.return_value = mock_jira
            mock_jira.get_issue = AsyncMock(side_effect=[mock_parent_issue, mock_epic_issue])
            mock_jira.get_labels = AsyncMock(return_value=["repo:acme/backend"])
            mock_jira.create_task = AsyncMock(return_value="MYPROJ-100")
            mock_jira.set_workflow_label = AsyncMock()
            mock_jira.close = AsyncMock()
            MockAgent.return_value = AsyncMock()

            result = await generate_tasks(state)

        assert result["task_keys"] == ["MYPROJ-100"]
        assert result["current_node"] == "task_approval_gate"
        assert result["revision_requested"] is False
        assert result["feedback_comment"] is None
        assert result["current_task_key"] is None
        assert result["current_epic_key"] is None

    @pytest.mark.asyncio
    async def test_regenerate_all_tasks_clears_revision_flags_after_new_tasks(
        self, base_state, mock_parent_issue, mock_epic_issue, mock_tasks_data
    ):
        """Full task regeneration should return to the gate without looping."""
        state = {
            **base_state,
            "task_keys": ["MYPROJ-20", "MYPROJ-21"],
            "tasks_by_repo": {"acme/backend": ["MYPROJ-20", "MYPROJ-21"]},
            "feedback_comment": "Use smaller implementation tasks.",
            "revision_requested": True,
            "current_epic_key": "MYPROJ-10",
        }

        with (
            patch("forge.workflow.nodes.task_generation.JiraClient") as MockJira,
            patch("forge.workflow.nodes.task_generation.ForgeAgent") as MockAgent,
            patch("forge.workflow.nodes.task_generation.post_status_comment"),
            patch(
                "forge.workflow.nodes.task_generation._generate_tasks_for_epic",
                new_callable=AsyncMock,
                return_value=mock_tasks_data,
            ),
        ):
            mock_jira = AsyncMock()
            MockJira.return_value = mock_jira
            mock_jira.archive_issue = AsyncMock()
            mock_jira.get_issue = AsyncMock(side_effect=[mock_parent_issue, mock_epic_issue])
            mock_jira.get_labels = AsyncMock(return_value=["repo:acme/backend"])
            mock_jira.create_task = AsyncMock(return_value="MYPROJ-100")
            mock_jira.set_workflow_label = AsyncMock()
            mock_jira.close = AsyncMock()
            MockAgent.return_value = AsyncMock()

            result = await regenerate_all_tasks(state)

        assert mock_jira.archive_issue.call_count == 2
        assert result["task_keys"] == ["MYPROJ-100"]
        assert result["current_node"] == "task_approval_gate"
        assert result["revision_requested"] is False
        assert result["feedback_comment"] is None
        assert result["current_epic_key"] is None
