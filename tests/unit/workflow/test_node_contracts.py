"""Tests for contracts shared by built-in and declarative graphs."""

import pytest

from forge.workflow.node_contracts import contracted_node, contracts_for


def test_contracts_for_returns_only_registered_nodes() -> None:
    contracts = contracts_for({"setup_workspace": object(), "generate_prd": object()})
    assert set(contracts) == {"setup_workspace"}


@pytest.mark.asyncio
async def test_create_pr_fails_fast_without_repository_or_workspace() -> None:
    called = False

    async def create_pr(state: dict) -> dict:
        nonlocal called
        called = True
        return state

    result = await contracted_node("create_pr", create_pr)({"ticket_key": "TEST-1"})

    assert called is False
    assert result["is_blocked"] is True
    assert result["precondition_result"]["missing"] == [
        "repositories_resolved",
        "workspace_ready",
    ]


@pytest.mark.asyncio
async def test_ci_fails_fast_without_pull_request() -> None:
    called = False

    async def evaluate_ci(state: dict) -> dict:
        nonlocal called
        called = True
        return state

    result = await contracted_node("ci_evaluator", evaluate_ci)({"ticket_key": "TEST-1"})

    assert called is False
    assert result["is_blocked"] is True
    assert result["last_error"] == "Pull request must exist before CI evaluation"
