"""Isolation fixtures shared by orchestrator integration tests."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest


def _prepared_workspace(module: Any, state: dict[str, Any]) -> tuple[str, Any]:
    workspace_path = state.get("workspace_path")
    if not workspace_path:
        raise ValueError("Workspace not set up")
    # Reuse an outer test patch when present so assertions observe the same mock.
    # Tests without a GitOperations patch only need an inert hermetic stand-in.
    git = (
        module.GitOperations.return_value if isinstance(module.GitOperations, Mock) else MagicMock()
    )
    return workspace_path, git


@pytest.fixture(autouse=True)
def isolate_workspace_recovery(request: pytest.FixtureRequest):
    """Keep scenarios hermetic unless they explicitly test real recovery behavior."""
    if request.node.get_closest_marker("real_workspace_recovery") is not None:
        yield
        return

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
