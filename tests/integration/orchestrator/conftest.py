"""Isolation fixtures shared by orchestrator integration tests."""

from unittest.mock import MagicMock, Mock, patch

import pytest


def _prepared_workspace(module, state: dict):
    workspace_path = state.get("workspace_path")
    if not workspace_path:
        raise ValueError("Workspace not set up")
    git = (
        module.GitOperations.return_value if isinstance(module.GitOperations, Mock) else MagicMock()
    )
    return workspace_path, git


@pytest.fixture(autouse=True)
def isolate_workspace_recovery():
    """Keep integration scenarios hermetic after workspace recovery was introduced."""
    from forge.workflow.nodes import implementation, local_reviewer

    with (
        patch(
            "forge.workflow.nodes.implementation.prepare_workspace",
            side_effect=lambda state: _prepared_workspace(implementation, state),
        ),
        patch(
            "forge.workflow.nodes.local_reviewer.prepare_workspace",
            side_effect=lambda state: _prepared_workspace(local_reviewer, state),
        ),
    ):
        yield
