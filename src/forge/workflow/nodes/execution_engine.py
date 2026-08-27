"""Shared engine for repository-scoped implementation nodes.

Workflow nodes remain responsible for resolving a work item and its artifacts.
This module owns the invariant execution mechanics once that context is known.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.sandbox.runner import ContainerRunner
from forge.workflow.nodes.git_persistence import PushPersistenceError, push_to_fork_with_retry
from forge.workflow.utils import merge_review_exhaustion
from forge.workspace.git_ops import GitOperations
from forge.workspace.handoff import capture_handoff


@dataclass(frozen=True)
class ExecutionArtifact:
    """A resolved planning artifact supplied to an implementation run."""

    title: str
    content: str


class ExecutionPersistenceError(Exception):
    """A durable push failed after execution state was collected."""

    def __init__(self, state: dict[str, Any], cause: PushPersistenceError) -> None:
        super().__init__(str(cause))
        self.state = state
        self.cause = cause


@dataclass(frozen=True)
class ExecutionRequest:
    """Normalized input shared by task- and artifact-based implementation."""

    ticket_key: str
    work_id: str
    repository: str
    workspace_path: str
    summary: str
    description: str
    node_name: str
    step_name: str
    policy_key: str
    commit_message: str
    description_title: str = "Work Item Description"
    artifacts: Sequence[ExecutionArtifact] = field(default_factory=tuple)
    review_feedback: str | None = None
    skill_name: str = "implement-task"
    critical_instructions: Sequence[str] = field(default_factory=tuple)
    runner_options: Mapping[str, Any] = field(default_factory=dict)


def build_execution_prompt(request: ExecutionRequest) -> str:
    """Render resolved work and supporting artifacts into a stable prompt."""
    sections = [
        f"You are implementing changes for [{request.work_id}].",
        (
            "## Repository Execution Scope\n"
            f"Current repository: `{request.repository}`\n"
            "Implement and validate only the work that belongs to "
            f"`{request.repository}`. Do not search for, create, or modify files "
            "assigned to other repositories. Those repositories are handled in "
            "separate workspaces. Completion for this run is evaluated only "
            "against the current repository's scope."
        ),
    ]
    if request.review_feedback:
        sections.append(
            "## Previous Qualitative Review Feedback\n"
            "Please address the following feedback from the qualitative review:\n"
            f"{request.review_feedback}"
        )
    sections.extend(
        f"## {artifact.title}\n{artifact.content}"
        for artifact in request.artifacts
        if artifact.content
    )
    sections.append(f"## {request.description_title}\n{request.description}")
    if request.critical_instructions:
        instructions = "\n".join(
            f"{index}. {instruction}"
            for index, instruction in enumerate(request.critical_instructions, start=1)
        )
        sections.append(f"## Critical Instructions\n{instructions}")
    return "\n\n".join(sections) + "\n"


async def run_and_persist_execution(
    state: Mapping[str, Any],
    request: ExecutionRequest,
    *,
    runner: ContainerRunner,
    git: GitOperations,
    prompt: str,
) -> dict[str, Any]:
    """Run one normalized work item, commit changes, and durably push them.

    ``prompt`` is accepted separately so a workflow can inject Jira references
    after rendering without coupling this engine to a specific state type.
    Push failures intentionally propagate for the calling node to apply its
    workflow-specific retry state.
    """
    result = await runner.run(
        workspace_path=Path(request.workspace_path),
        task_summary=request.summary,
        task_description=prompt,
        ticket_key=request.ticket_key,
        task_key=request.work_id,
        repo_name=request.repository,
        step_name=request.step_name,
        policy_key=request.policy_key,
        skill_name=request.skill_name,
        **request.runner_options,
    )
    updated = merge_review_exhaustion(dict(state), result, request.work_id, request.step_name)
    updated = capture_handoff(
        request.workspace_path,
        request.repository,
        request.work_id,
        updated,
    )

    committed = False
    if git.has_uncommitted_changes():
        git.stage_all()
        committed = git.commit(request.commit_message)

    previous_commit = updated.get("commit_info") or {}
    execution_state = {
        **updated,
        "task_execution_results": {
            "success": result.success,
            "exit_code": result.exit_code,
            "error_message": result.error_message,
        },
        "task_execution_logs": {
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        "commit_info": {
            "sha": git.get_current_sha(),
            "message": request.commit_message,
            "committed": bool(previous_commit.get("committed", False) or committed),
        },
        "current_node": request.node_name,
        "last_error": None if result.success else result.error_message,
        "retry_count": 0 if result.success else state.get("retry_count", 0) + 1,
    }
    try:
        await push_to_fork_with_retry(git)
    except PushPersistenceError as exc:
        raise ExecutionPersistenceError(execution_state, exc) from exc
    return execution_state
