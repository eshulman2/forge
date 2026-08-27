"""Shared prompt boundaries for repository-scoped workflow passes."""

from forge.prompts import load_prompt


def implementation_repository_scope(repository: str, workspace_path: str) -> str:
    """Describe the hard repository boundary for an implementation pass."""
    return load_prompt(
        "repository-implementation-scope",
        repository=repository,
        workspace_path=workspace_path,
    )


def review_repository_scope(repository: str, workspace_path: str) -> str:
    """Describe the hard repository boundary for a review pass."""
    return load_prompt(
        "repository-review-scope",
        repository=repository,
        workspace_path=workspace_path,
    )
