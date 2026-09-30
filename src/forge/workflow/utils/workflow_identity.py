"""Helpers for preserving workflow identity across related Jira tickets."""

from typing import Any

from forge.workflow.declarative.models import WORKFLOW_LABEL_PREFIX


def workflow_identity_labels(state: dict[str, Any]) -> list[str]:
    """Return labels that identify the selected declarative workflow."""
    workflow_name = state.get("workflow_name")
    if not workflow_name:
        return []
    return [f"{WORKFLOW_LABEL_PREFIX}{workflow_name}"]
