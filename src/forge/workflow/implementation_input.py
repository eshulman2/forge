"""Resolve workflow-specific planning state into repository-scoped implementation input."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from forge.integrations.jira.models import JiraIssue
from forge.workflow.base import ArtifactRef, WorkUnit

ArtifactKind = Literal["task", "epic_plan", "plan", "spec", "rca", "prd", "ticket"]


class NoPendingImplementationWork(Exception):
    """The repository has known work units, but all have already completed."""


class IssueReader(Protocol):
    """The small Jira API surface needed by the resolver."""

    async def get_issue(self, issue_key: str) -> JiraIssue: ...


@dataclass(frozen=True)
class ResolvedImplementationInput:
    """Normalized input shared by Feature, Bug, and Task-takeover execution."""

    work_unit: WorkUnit
    context_artifacts: tuple[ArtifactRef, ...]
    instructions: str
    summary: str | None = None

    def state_update(self, state: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return checkpoint-safe normalized state fields for this decision.

        Existing artifacts and work units are retained by identity so resolution
        across repositories or retries builds an audit trail instead of replacing it.
        """
        existing_artifacts = list((state or {}).get("artifacts") or [])
        artifacts_by_id = {artifact.get("id"): artifact for artifact in existing_artifacts}
        for artifact in self.context_artifacts:
            artifacts_by_id[artifact.get("id")] = artifact

        existing_units = list((state or {}).get("work_units") or [])
        units_by_id = {unit.get("id"): unit for unit in existing_units}
        previous = units_by_id.get(self.work_unit["id"])
        if previous and previous.get("status") == "completed":
            units_by_id[self.work_unit["id"]] = previous
        else:
            units_by_id[self.work_unit["id"]] = self.work_unit
        return {
            "artifacts": list(artifacts_by_id.values()),
            "work_units": list(units_by_id.values()),
            "current_work_unit_id": self.work_unit["id"],
            "work_resolution": {
                "strategy": "task_first",
                "selected_work_unit_id": self.work_unit["id"],
                "selected_artifact_id": self.work_unit["source_artifact_ids"][0],
            },
        }


def _digest(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _repo_labels(issue: JiraIssue) -> set[str]:
    return {label.removeprefix("repo:") for label in issue.labels if label.startswith("repo:")}


def _content(issue: JiraIssue) -> str:
    return issue.description.strip()


def _issue_artifact(kind: ArtifactKind, issue: JiraIssue, repository: str) -> ArtifactRef:
    content = _content(issue)
    return {
        "id": f"jira:{issue.key}:{kind}",
        "kind": kind,
        "source": issue.key,
        "content": content,
        "digest": _digest(content),
        "repository": repository,
    }


def _state_artifact(kind: ArtifactKind, field: str, content: Any) -> ArtifactRef | None:
    if not isinstance(content, str) or not content.strip():
        return None
    normalized = content.strip()
    digest = _digest(normalized)
    return {
        "id": f"state:{field}:{digest[7:19]}",
        "kind": kind,
        "source": field,
        "content": normalized,
        "digest": digest,
        "repository": None,
    }


def _assert_issue_repository(issue: JiraIssue, repository: str) -> None:
    repos = _repo_labels(issue)
    if repos and repository not in repos:
        raise ValueError(
            f"Jira issue {issue.key} is scoped to {sorted(repos)}, not current repository {repository}"
        )


def _task_candidates(state: Mapping[str, Any], repository: str) -> list[str]:
    implemented = set(state.get("implemented_tasks") or [])
    implemented.update(
        unit.get("id", "")
        for unit in state.get("work_units") or []
        if unit.get("status") == "completed"
    )
    mapped = state.get("tasks_by_repo") or {}
    candidates: list[str] = []
    current = state.get("current_task_key")
    if isinstance(current, str) and current and current not in implemented:
        for other_repo, keys in mapped.items():
            if other_repo != repository and current in (keys or []):
                raise ValueError(f"Current task {current} belongs to repository {other_repo}")
        candidates.append(current)
    for key in mapped.get(repository, []):
        if isinstance(key, str) and key not in implemented and key not in candidates:
            candidates.append(key)
    ticket_type = state.get("ticket_type")
    ticket_type_name = getattr(ticket_type, "value", ticket_type)
    ticket_key = state.get("ticket_key")
    if (
        ticket_type_name in {"Task", "Epic"}
        and isinstance(ticket_key, str)
        and ticket_key not in implemented
        and ticket_key not in candidates
    ):
        candidates.append(ticket_key)
    return candidates


async def resolve_implementation_input(
    state: Mapping[str, Any], jira: IssueReader
) -> ResolvedImplementationInput:
    """Resolve task-first implementation input, strictly scoped to ``current_repo``.

    Primary work precedence is current Task, the first pending repository Task,
    repository Epic plan, plan, spec, RCA, PRD, then the root ticket. Lower-level
    available artifacts are retained as ordered context rather than discarded.
    """
    repository = state.get("current_repo")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("current_repo is required to resolve implementation input")
    repository = repository.strip()

    artifacts: list[ArtifactRef] = []
    summaries: dict[str, str] = {}
    task_keys = _task_candidates(state, repository)
    repository_tasks = (state.get("tasks_by_repo") or {}).get(repository, [])
    if repository_tasks and not task_keys:
        raise NoPendingImplementationWork(f"All Jira tasks are complete for {repository}")
    for task_key in task_keys[:1]:
        issue = await jira.get_issue(task_key)
        _assert_issue_repository(issue, repository)
        artifact = _issue_artifact("task", issue, repository)
        if not artifact["content"] and issue.summary.strip():
            artifact["content"] = issue.summary.strip()
            artifact["digest"] = _digest(artifact["content"])
        if artifact["content"]:
            artifacts.append(artifact)
            summaries[artifact["id"]] = issue.summary

    for epic_key in state.get("epic_keys") or []:
        if not isinstance(epic_key, str):
            continue
        issue = await jira.get_issue(epic_key)
        # Epic plans are never treated as global: they must explicitly name this repo.
        if repository not in _repo_labels(issue):
            continue
        artifact = _issue_artifact("epic_plan", issue, repository)
        if artifact["content"]:
            artifacts.append(artifact)
            summaries[artifact["id"]] = issue.summary

    state_fields: tuple[tuple[ArtifactKind, str], ...] = (
        ("plan", "plan_content"),
        ("spec", "spec_content"),
        ("rca", "rca_content"),
        ("prd", "prd_content"),
    )
    for kind, field in state_fields:
        state_artifact = _state_artifact(kind, field, state.get(field))
        if state_artifact:
            artifacts.append(state_artifact)

    ticket_key = state.get("ticket_key")
    if isinstance(ticket_key, str) and ticket_key and ticket_key not in task_keys[:1]:
        issue = await jira.get_issue(ticket_key)
        _assert_issue_repository(issue, repository)
        artifact = _issue_artifact("ticket", issue, repository)
        if artifact["content"]:
            artifacts.append(artifact)
            summaries[artifact["id"]] = issue.summary

    if not artifacts:
        raise ValueError(f"No implementation artifact is available for repository {repository}")

    primary = artifacts[0]
    jira_key = (
        primary["source"]
        if primary["source"] not in {"plan_content", "spec_content", "rca_content", "prd_content"}
        else None
    )
    work_id = jira_key or f"internal:{repository}:{primary['kind']}:{primary['digest'][7:19]}"
    completed_ids = set(state.get("implemented_tasks") or [])
    completed_ids.update(
        unit.get("id", "")
        for unit in state.get("work_units") or []
        if unit.get("status") == "completed"
    )
    if work_id in completed_ids:
        raise NoPendingImplementationWork(f"Work unit {work_id} is already complete")
    work_unit: WorkUnit = {
        "id": work_id,
        "kind": primary["kind"],
        "key": jira_key,
        "repository": repository,
        "status": "pending",
        "source_artifact_ids": [primary["id"]],
    }
    return ResolvedImplementationInput(
        work_unit=work_unit,
        context_artifacts=tuple(artifacts),
        instructions=primary["content"],
        summary=summaries.get(primary["id"]),
    )
