"""Resolve project-scoped declarative workflows from Jira properties."""

from __future__ import annotations

from typing import Any, Protocol

from forge.workflow.declarative.loader import load_workflow_value
from forge.workflow.declarative.models import (
    WORKFLOW_LABEL_PREFIX,
    WORKFLOW_NAME_RE,
    WORKFLOW_PROPERTY_PREFIX,
)
from forge.workflow.declarative.workflow import DeclarativeWorkflow


class ProjectPropertyReader(Protocol):
    async def get_project_property(self, project_key: str, property_key: str) -> Any | None: ...


def selected_workflow_name(labels: list[str]) -> str | None:
    selected = sorted(
        {
            label[len(WORKFLOW_LABEL_PREFIX) :]
            for label in labels
            if label.startswith(WORKFLOW_LABEL_PREFIX)
        }
    )
    if len(selected) > 1:
        raise ValueError(f"multiple custom workflows selected: {', '.join(selected)}")
    if not selected:
        return None
    if not WORKFLOW_NAME_RE.fullmatch(selected[0]):
        raise ValueError(f"invalid custom workflow label: {WORKFLOW_LABEL_PREFIX}{selected[0]}")
    return selected[0]


async def load_project_workflow(
    jira: ProjectPropertyReader,
    project_key: str,
    workflow_name: str,
) -> DeclarativeWorkflow:
    value = await jira.get_project_property(
        project_key.upper(), f"{WORKFLOW_PROPERTY_PREFIX}{workflow_name}"
    )
    if value is None:
        raise ValueError(
            f"project {project_key.upper()} does not define workflow '{workflow_name}'"
        )
    definition = load_workflow_value(value)
    if definition.metadata.name != workflow_name:
        raise ValueError(
            f"workflow property name '{workflow_name}' does not match metadata name "
            f"'{definition.metadata.name}'"
        )
    return DeclarativeWorkflow(definition, project_key)
