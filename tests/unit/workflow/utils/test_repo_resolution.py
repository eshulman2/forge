"""Tests for workflow repository configuration authority."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.integrations.jira.client import MissingProjectConfig
from forge.workflow.utils.repo_resolution import (
    get_effective_default_repo,
    get_effective_repos,
)


@pytest.mark.asyncio
async def test_local_mode_prefers_environment_repos_over_jira() -> None:
    jira = AsyncMock()
    settings = MagicMock(
        forge_require_project_config=False,
        known_repos=["local/one", "local/two"],
        github_default_repo="local/two",
    )

    with patch("forge.workflow.utils.repo_resolution.get_settings", return_value=settings):
        assert await get_effective_repos(jira, "PROJ") == ["local/one", "local/two"]
        assert await get_effective_default_repo(jira, "PROJ") == "local/two"

    jira.get_project_repos.assert_not_awaited()
    jira.get_project_default_repo.assert_not_awaited()


@pytest.mark.asyncio
async def test_production_mode_uses_only_jira_project_config() -> None:
    jira = AsyncMock()
    jira.get_project_repos.return_value = ["prod/repo"]
    jira.get_project_default_repo.return_value = "prod/repo"
    settings = MagicMock(
        forge_require_project_config=True,
        known_repos=["local/repo"],
        github_default_repo="local/repo",
    )

    with patch("forge.workflow.utils.repo_resolution.get_settings", return_value=settings):
        assert await get_effective_repos(jira, "PROJ") == ["prod/repo"]
        assert await get_effective_default_repo(jira, "PROJ") == "prod/repo"

    jira.get_project_repos.assert_awaited_once_with("PROJ")
    jira.get_project_default_repo.assert_awaited_once_with("PROJ")


@pytest.mark.asyncio
async def test_local_mode_does_not_fall_back_to_jira_when_env_is_missing() -> None:
    jira = AsyncMock()
    settings = MagicMock(
        forge_require_project_config=False,
        known_repos=[],
        github_default_repo="",
    )

    with (
        patch("forge.workflow.utils.repo_resolution.get_settings", return_value=settings),
        pytest.raises(MissingProjectConfig, match="GITHUB_KNOWN_REPOS"),
    ):
        await get_effective_repos(jira, "PROJ")

    jira.get_project_repos.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_mode_missing_default_repo_does_not_fall_back_to_jira() -> None:
    jira = AsyncMock()
    settings = MagicMock(
        forge_require_project_config=False,
        known_repos=["local/repo"],
        github_default_repo="",
    )

    with (
        patch("forge.workflow.utils.repo_resolution.get_settings", return_value=settings),
        pytest.raises(MissingProjectConfig, match="GITHUB_DEFAULT_REPO"),
    ):
        await get_effective_default_repo(jira, "PROJ")

    jira.get_project_default_repo.assert_not_awaited()
