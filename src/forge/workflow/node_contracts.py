"""Allowlisted precondition contracts shared by built-in and declarative graphs."""

from collections.abc import Callable
from typing import Any

from forge.workflow.preconditions import (
    CapabilityName,
    NodeContract,
    PreconditionAction,
    Requirement,
    with_preconditions,
)

NODE_CONTRACTS: dict[str, NodeContract] = {
    "implement_work": NodeContract(
        requires=(
            Requirement(
                CapabilityName.REPOSITORIES,
                PreconditionAction.BLOCK,
                "Repository must be resolved before implementation",
            ),
            Requirement(
                CapabilityName.WORKSPACE,
                PreconditionAction.BLOCK,
                "Workspace must exist before implementation",
            ),
            Requirement(
                CapabilityName.PLANNING_CONTEXT,
                PreconditionAction.BLOCK,
                "At least one implementation artifact must exist",
            ),
        )
    ),
    "setup_workspace": NodeContract(
        requires=(
            Requirement(
                CapabilityName.REPOSITORIES,
                PreconditionAction.BLOCK,
                "Repository must be resolved before workspace setup",
            ),
        )
    ),
    "create_pr": NodeContract(
        requires=(
            Requirement(
                CapabilityName.REPOSITORIES,
                PreconditionAction.BLOCK,
                "Repository must be resolved before pull request creation",
            ),
            Requirement(
                CapabilityName.WORKSPACE,
                PreconditionAction.BLOCK,
                "Workspace must exist before pull request creation",
            ),
        )
    ),
    "ci_evaluator": NodeContract(
        requires=(
            Requirement(
                CapabilityName.PULL_REQUEST,
                PreconditionAction.BLOCK,
                "Pull request must exist before CI evaluation",
            ),
        )
    ),
}


def contracts_for(nodes: dict[str, Any]) -> dict[str, NodeContract]:
    """Return contracts applicable to a profile's allowlisted nodes."""
    return {name: NODE_CONTRACTS[name] for name in nodes if name in NODE_CONTRACTS}


def contracted_node(name: str, node: Callable[..., Any]) -> Callable[..., Any]:
    """Apply the registered contract while preserving unregistered behavior."""
    return with_preconditions(node, NODE_CONTRACTS.get(name), node_name=name)
