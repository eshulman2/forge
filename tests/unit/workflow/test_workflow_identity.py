"""Tests for declarative workflow identity propagation."""

from forge.workflow.utils.workflow_identity import workflow_identity_labels


def test_workflow_identity_labels_returns_selected_workflow() -> None:
    assert workflow_identity_labels({"workflow_name": "planning-smoke"}) == [
        "forge:workflow:planning-smoke"
    ]


def test_workflow_identity_labels_ignores_builtin_workflow() -> None:
    assert workflow_identity_labels({}) == []
