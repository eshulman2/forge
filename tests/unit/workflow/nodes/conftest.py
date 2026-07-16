"""Opt-in isolation fixtures for workflow-node unit tests."""

from unittest.mock import MagicMock, Mock, patch

import pytest


def _workspace_path(state):
    workspace_path = state.get("workspace_path")
    if not workspace_path:
        raise ValueError("Workspace not set up")
    return workspace_path


@pytest.fixture
def mock_implementation_workspace_recovery():
    """Prevent implementation-node tests from cloning a real remote."""

    def _prepare(state):
        from forge.workflow.nodes import implementation

        git = (
            implementation.GitOperations.return_value
            if isinstance(implementation.GitOperations, Mock)
            else MagicMock()
        )
        return _workspace_path(state), git

    with patch("forge.workflow.nodes.implementation.prepare_workspace", side_effect=_prepare):
        yield


@pytest.fixture
def mock_review_workspace_recovery():
    """Prevent local-review tests from cloning a real remote."""

    def _prepare(state):
        from forge.workflow.nodes import local_reviewer

        git = (
            local_reviewer.GitOperations.return_value
            if isinstance(local_reviewer.GitOperations, Mock)
            else MagicMock()
        )
        return _workspace_path(state), git

    with patch("forge.workflow.nodes.local_reviewer.prepare_workspace", side_effect=_prepare):
        yield
