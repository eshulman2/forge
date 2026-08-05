"""Repository resolution helpers for workflows."""

import contextlib
import re
from typing import Any

from forge.config import get_settings
from forge.integrations.jira.client import MissingProjectConfig

_REPO_LABEL_PREFIX = "repo:"


async def get_effective_repos(jira: Any, project_key: str) -> list[str]:
    """Return repos from the configured authority for the current mode."""
    settings = get_settings()
    if not settings.forge_require_project_config:
        repos = settings.known_repos
        if not repos:
            raise MissingProjectConfig(
                "GITHUB_KNOWN_REPOS is not set while FORGE_REQUIRE_PROJECT_CONFIG=false"
            )
        return repos
    return await jira.get_project_repos(project_key)


async def get_effective_default_repo(jira: Any, project_key: str) -> str:
    """Return the default repo from the configured authority for the current mode."""
    settings = get_settings()
    if not settings.forge_require_project_config:
        repo = settings.github_default_repo.strip()
        if not repo or "/" not in repo:
            raise MissingProjectConfig(
                "GITHUB_DEFAULT_REPO is not set while FORGE_REQUIRE_PROJECT_CONFIG=false"
            )
        return repo
    return await jira.get_project_default_repo(project_key)


def repo_from_labels(labels: list[str]) -> str | None:
    """Return repo from repo:<owner>/<repo> label when present."""
    for label in labels:
        if label.startswith(_REPO_LABEL_PREFIX):
            repo = label[len(_REPO_LABEL_PREFIX) :].strip()
            if "/" in repo:
                return repo
    return None


def repo_mentioned_in_text(text: str, known_repos: list[str]) -> str | None:
    """Infer repo from full repo name or unambiguous repo basename mentioned in ticket text."""
    if not text.strip() or not known_repos:
        return None

    text_lower = text.lower()
    for repo in known_repos:
        if repo.lower() in text_lower:
            return repo

    by_name: dict[str, list[str]] = {}
    for repo in known_repos:
        _owner, _sep, name = repo.rpartition("/")
        if name:
            by_name.setdefault(name.lower(), []).append(repo)

    for name, repos in by_name.items():
        if len(repos) != 1:
            continue
        if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", text_lower):
            return repos[0]

    return None


async def resolve_current_repo(
    jira: Any,
    issue: Any,
    comments: str,
    current_repo: str | None,
) -> tuple[str | None, list[str]]:
    """Resolve target repo from state, labels, ticket text, or project defaults."""
    known_repos: list[str] = []
    with contextlib.suppress(Exception):
        known_repos = await get_effective_repos(jira, issue.project_key)

    if current_repo and current_repo != "unknown" and "/" in current_repo:
        return current_repo, known_repos or [current_repo]

    label_repo = repo_from_labels(getattr(issue, "labels", []) or [])
    if label_repo:
        return label_repo, known_repos or [label_repo]

    ticket_text = "\n\n".join(
        part
        for part in [
            getattr(issue, "summary", "") or "",
            getattr(issue, "description", "") or "",
            comments,
        ]
        if part
    )
    mentioned_repo = repo_mentioned_in_text(ticket_text, known_repos)
    if mentioned_repo:
        return mentioned_repo, known_repos

    with contextlib.suppress(Exception):
        default_repo = await get_effective_default_repo(jira, issue.project_key)
        if default_repo:
            return default_repo, known_repos or [default_repo]

    if known_repos:
        return known_repos[0], known_repos

    return None, known_repos
