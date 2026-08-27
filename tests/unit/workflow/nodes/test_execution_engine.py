"""Tests for normalized implementation execution prompts."""

from forge.workflow.nodes.execution_engine import ExecutionRequest, build_execution_prompt


def test_execution_prompt_enforces_mounted_repository_scope() -> None:
    request = ExecutionRequest(
        ticket_key="FEAT-1",
        work_id="TASK-1",
        repository="acme/backend",
        workspace_path="/tmp/forge-FEAT-1-backend",
        summary="Implement backend",
        description="The plan also describes frontend work.",
        node_name="implement_work",
        step_name="implement_work",
        policy_key="implement_task",
        commit_message="implement backend",
    )

    prompt = build_execution_prompt(request)

    assert "Current repository: `acme/backend`" in prompt
    assert "Mounted workspace: `/tmp/forge-FEAT-1-backend`" in prompt
    assert "repository assignments in the plan as hard scope boundaries" in prompt
    assert "do not treat its absence as unfinished work" in prompt
