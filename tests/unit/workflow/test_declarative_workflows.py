from __future__ import annotations

from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from forge.orchestrator.worker import OrchestratorWorker
from forge.workflow.declarative.catalog import get_state_profile
from forge.workflow.declarative.cli import cmd_workflow
from forge.workflow.declarative.compiler import (
    DeclarativeWorkflowCompiler,
    WorkflowValidationError,
)
from forge.workflow.declarative.loader import load_workflow_value
from forge.workflow.declarative.models import WORKFLOW_PROPERTY_PREFIX
from forge.workflow.declarative.resolver import (
    load_project_workflow,
    selected_workflow_name,
)
from forge.workflow.declarative.workflow import DeclarativeWorkflow
from forge.workflow.nodes.workspace_setup import teardown_workspace
from forge.workflow.preconditions import (
    CapabilityName,
    NodeContract,
    PreconditionAction,
    Requirement,
)


def definition_value(
    *, revision: int = 1, steps: dict | None = None, state: str = "feature"
) -> dict:
    return {
        "apiVersion": "forge/v1",
        "kind": "Workflow",
        "metadata": {"name": "short-feature", "revision": revision},
        "spec": {
            "state": state,
            "entry": "generate_prd",
            "steps": steps or {"generate_prd": {"next": "__end__"}},
        },
    }


def test_loads_strict_definition_and_computes_stable_digest() -> None:
    first = load_workflow_value(definition_value())
    second = load_workflow_value(definition_value())

    assert first.digest == second.digest
    assert first.property_key == f"{WORKFLOW_PROPERTY_PREFIX}short-feature"


def test_rejects_unknown_fields() -> None:
    value = definition_value()
    value["spec"]["execute"] = "os.system"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_workflow_value(value)


def test_rejects_property_larger_than_jira_limit() -> None:
    value = definition_value(revision=2)
    value["spec"]["resume"] = {
        "fromRevisions": {"1": {f"retired_node_{index}": "generate_prd" for index in range(2_000)}}
    }

    with pytest.raises(ValueError, match="32768"):
        load_workflow_value(value)


def test_compiles_allowlisted_node() -> None:
    definition = load_workflow_value(definition_value())
    graph = DeclarativeWorkflowCompiler(definition).build_graph().compile()

    assert "generate_prd" in graph.nodes
    assert "_forge_entry" in graph.nodes


def test_declarative_teardown_does_not_use_builtin_repo_router() -> None:
    assert get_state_profile("feature").nodes["teardown_workspace"] is teardown_workspace


@pytest.mark.asyncio
async def test_terminal_declarative_teardown_completes_without_hidden_stage() -> None:
    value = definition_value(steps={"teardown_workspace": {"next": "__end__"}})
    value["spec"]["entry"] = "teardown_workspace"
    graph = DeclarativeWorkflowCompiler(load_workflow_value(value)).build_graph().compile()

    result = await graph.ainvoke(
        {
            "ticket_key": "PROJ-1",
            "current_node": "teardown_workspace",
            "workspace_path": None,
        }
    )

    assert result["current_node"] == "complete"


@pytest.mark.asyncio
async def test_runtime_transition_budget_blocks_before_side_effect() -> None:
    value = definition_value(
        steps={
            "prd_approval_gate": {
                "route": "route_prd_approval",
                "branches": {"__end__": "__end__"},
            }
        }
    )
    value["spec"]["entry"] = "prd_approval_gate"
    graph = DeclarativeWorkflowCompiler(load_workflow_value(value)).build_graph().compile()

    result = await graph.ainvoke(
        {
            "ticket_key": "PROJ-1",
            "current_node": "entry",
            "workflow_transition_count": 500,
        }
    )

    assert result["is_blocked"] is True
    assert "exceeded 500 transitions" in result["last_error"]


@pytest.mark.asyncio
async def test_guarded_node_enforces_opt_in_contract_before_side_effect() -> None:
    called = False

    async def create_pr(state: dict) -> dict:
        nonlocal called
        called = True
        return state

    contract = NodeContract(
        requires=(Requirement(CapabilityName.CODE_CHANGES, PreconditionAction.SKIP),)
    )
    node = DeclarativeWorkflowCompiler._guarded_node(
        create_pr,
        "create_pr",
        terminal=False,
        contract=contract,
    )

    result = await node({"ticket_key": "PROJ-1"})

    assert called is False
    assert result["precondition_result"]["action"] == "skip"
    assert result["workflow_transition_count"] == 1


@pytest.mark.asyncio
async def test_guarded_node_without_contract_remains_backward_compatible() -> None:
    async def node(state: dict) -> dict:
        return {**state, "called": True}

    guarded = DeclarativeWorkflowCompiler._guarded_node(
        node,
        "generate_prd",
        terminal=False,
    )

    result = await guarded({"ticket_key": "PROJ-1"})

    assert result["called"] is True
    assert "precondition_result" not in result


def test_rejects_unknown_node_and_unreachable_node() -> None:
    unknown = load_workflow_value(definition_value(steps={"shell": {"next": "__end__"}}))
    with pytest.raises(WorkflowValidationError, match="entry node"):
        DeclarativeWorkflowCompiler(unknown).validate()

    unreachable = load_workflow_value(
        definition_value(
            steps={
                "generate_prd": {"next": "__end__"},
                "generate_spec": {"next": "__end__"},
            }
        )
    )
    with pytest.raises(WorkflowValidationError, match="unreachable"):
        DeclarativeWorkflowCompiler(unreachable).validate()


def test_rejects_unknown_registered_router_outcome() -> None:
    value = definition_value(
        steps={
            "spec_approval_gate": {
                "route": "route_spec_approval",
                "branches": {"generate_tasks": "generate_prd"},
            },
            "generate_prd": {"next": "__end__"},
        }
    )
    value["spec"]["entry"] = "spec_approval_gate"

    with pytest.raises(WorkflowValidationError, match="unknown outcome 'generate_tasks'"):
        DeclarativeWorkflowCompiler(load_workflow_value(value)).validate()


def test_accepts_registered_router_outcome() -> None:
    value = definition_value(
        steps={
            "spec_approval_gate": {
                "route": "route_spec_approval",
                "branches": {"decompose_epics": "generate_prd"},
            },
            "generate_prd": {"next": "__end__"},
        }
    )
    value["spec"]["entry"] = "spec_approval_gate"

    DeclarativeWorkflowCompiler(load_workflow_value(value)).validate()


def test_rejects_unguarded_cycle_but_allows_gate_cycle() -> None:
    unsafe = load_workflow_value(
        definition_value(
            steps={
                "generate_prd": {
                    "route": "route_current_node",
                    "branches": {"again": "generate_prd", "done": "__end__"},
                }
            }
        )
    )
    with pytest.raises(WorkflowValidationError, match="no approved pause"):
        DeclarativeWorkflowCompiler(unsafe).validate()

    guarded = load_workflow_value(
        definition_value(
            steps={
                "generate_prd": {"next": "prd_approval_gate"},
                "prd_approval_gate": {
                    "route": "route_prd_approval",
                    "branches": {
                        "regenerate_prd": "generate_prd",
                        "generate_spec": "__end__",
                    },
                },
            }
        )
    )
    DeclarativeWorkflowCompiler(guarded).validate()


def test_label_selection_is_explicit_and_unambiguous() -> None:
    assert selected_workflow_name(["forge:managed", "forge:workflow:short-feature"]) == (
        "short-feature"
    )
    assert selected_workflow_name(["forge:managed"]) is None
    with pytest.raises(ValueError, match="multiple"):
        selected_workflow_name(["forge:workflow:a", "forge:workflow:b"])


@pytest.mark.asyncio
async def test_load_project_workflow_checks_property_metadata_name() -> None:
    jira = AsyncMock()
    jira.get_project_property.return_value = definition_value()

    workflow = await load_project_workflow(jira, "PROJ", "short-feature")

    assert workflow.cache_key.startswith("custom:PROJ:short-feature:1:")
    jira.get_project_property.assert_awaited_once_with("PROJ", "forge.workflow.short-feature")


def test_resume_adopts_revision_and_requires_mapping_for_removed_node() -> None:
    current = DeclarativeWorkflow(load_workflow_value(definition_value(revision=1)), "PROJ")
    state = {
        **current.workflow_metadata(),
        "current_node": "generate_prd",
        "workflow_transition_count": 7,
    }
    updated_value = definition_value(
        revision=2,
        steps={"generate_spec": {"next": "__end__"}},
    )
    updated_value["spec"]["entry"] = "generate_spec"
    updated_value["spec"]["resume"] = {"fromRevisions": {"1": {"generate_prd": "generate_spec"}}}
    updated = DeclarativeWorkflow(load_workflow_value(updated_value), "PROJ")

    migrated = updated.migrate_state(state)

    assert migrated["current_node"] == "generate_spec"
    assert migrated["workflow_revision"] == 2
    assert migrated["workflow_transition_count"] == 7


def test_resume_rejects_same_revision_mutation() -> None:
    original = DeclarativeWorkflow(load_workflow_value(definition_value()), "PROJ")
    changed_value = definition_value(steps={"generate_spec": {"next": "__end__"}})
    changed_value["spec"]["entry"] = "generate_spec"
    changed = DeclarativeWorkflow(load_workflow_value(changed_value), "PROJ")

    with pytest.raises(WorkflowValidationError, match="without incrementing"):
        changed.migrate_state({**original.workflow_metadata(), "current_node": "entry"})


@pytest.mark.asyncio
async def test_worker_resolves_label_selected_workflow() -> None:
    worker = OrchestratorWorker.__new__(OrchestratorWorker)
    worker._checkpointer = MagicMock()
    worker._checkpointer.aget = AsyncMock(return_value=None)
    jira = MagicMock()
    jira.get_project_property = AsyncMock(return_value=definition_value())
    jira.close = AsyncMock()

    with patch("forge.orchestrator.worker.JiraClient", return_value=jira):
        workflow = await worker._resolve_custom_workflow(
            "PROJ-1", ["forge:managed", "forge:workflow:short-feature"]
        )

    assert workflow is not None
    assert workflow.name == "short-feature"
    assert workflow.project_key == "PROJ"


@pytest.mark.asyncio
async def test_worker_keeps_checkpoint_workflow_identity_when_label_is_removed() -> None:
    worker = OrchestratorWorker.__new__(OrchestratorWorker)
    worker._checkpointer = MagicMock()
    worker._checkpointer.aget = AsyncMock(
        return_value={
            "channel_values": {
                "workflow_name": "short-feature",
                "workflow_project_key": "PROJ",
            }
        }
    )
    jira = MagicMock()
    jira.get_project_property = AsyncMock(return_value=definition_value())
    jira.close = AsyncMock()

    with patch("forge.orchestrator.worker.JiraClient", return_value=jira):
        workflow = await worker._resolve_custom_workflow("PROJ-1", [])

    assert workflow is not None
    assert workflow.name == "short-feature"


def test_worker_cache_key_separates_custom_revisions() -> None:
    worker = OrchestratorWorker.__new__(OrchestratorWorker)
    worker._compiled_workflows = {}
    worker._checkpointer = None
    first = DeclarativeWorkflow(load_workflow_value(definition_value(revision=1)), "PROJ")
    second = DeclarativeWorkflow(load_workflow_value(definition_value(revision=2)), "PROJ")

    first_compiled = worker._get_compiled_workflow(first)
    second_compiled = worker._get_compiled_workflow(second)

    assert first_compiled is not second_compiled
    assert len(worker._compiled_workflows) == 2


@pytest.mark.asyncio
async def test_cli_publish_validates_and_stores_canonical_json(tmp_path) -> None:
    source = tmp_path / "workflow.yaml"
    source.write_text(
        """apiVersion: forge/v1
kind: Workflow
metadata:
  name: short-feature
  revision: 1
spec:
  state: feature
  entry: generate_prd
  steps:
    generate_prd:
      next: __end__
""",
        encoding="utf-8",
    )
    jira = MagicMock()
    jira.get_project_property = AsyncMock(return_value=None)
    jira.set_project_property = AsyncMock()
    jira.close = AsyncMock()

    with patch("forge.workflow.declarative.cli.JiraClient", return_value=jira):
        result = await cmd_workflow(
            Namespace(workflow_command="publish", project_key="proj", file=str(source))
        )

    assert result == 0
    key, value = jira.set_project_property.await_args.args[1:]
    assert key == "forge.workflow.short-feature"
    assert value["apiVersion"] == "forge/v1"
    assert value["metadata"]["revision"] == 1
    jira.close.assert_awaited_once()
