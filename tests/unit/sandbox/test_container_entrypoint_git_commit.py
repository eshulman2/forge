"""Tests for the container entrypoint git fallback commit."""

import importlib.util
import subprocess
from pathlib import Path


def _load_entrypoint_module():
    module_path = Path(__file__).parents[3] / "containers" / "entrypoint.py"
    import sys

    containers_dir = str(module_path.parent)
    if containers_dir not in sys.path:
        sys.path.insert(0, containers_dir)
    spec = importlib.util.spec_from_file_location("forge_container_entrypoint", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_git_commit_excludes_forge_directory(tmp_path):
    entrypoint = _load_entrypoint_module()
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Forge Test")
    _git(tmp_path, "config", "user.email", "forge-test@example.com")

    (tmp_path / "code.txt").write_text("user-facing change\n")
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "handoff.md").write_text("internal handoff\n")

    assert entrypoint.git_commit(tmp_path, "test commit") is True

    tracked = _git(tmp_path, "ls-files").stdout.splitlines()
    assert "code.txt" in tracked
    assert ".forge/handoff.md" not in tracked


def test_git_commit_with_gitignore_and_forge_dir(tmp_path):
    """git_commit succeeds when .forge/ is in .gitignore and exists on disk."""
    entrypoint = _load_entrypoint_module()
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Forge Test")
    _git(tmp_path, "config", "user.email", "forge-test@example.com")

    (tmp_path / ".gitignore").write_text(".forge/\n")
    (tmp_path / "initial.txt").write_text("initial\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")

    # Simulate container: .forge/ exists with files, and agent left changes
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "history" / "TASK-1.json").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".forge" / "task.json").write_text('{"task_key": "TASK-1"}')
    (tmp_path / "code.py").write_text("def hello(): pass\n")

    assert entrypoint.git_commit(tmp_path, "test commit") is True

    tracked = _git(tmp_path, "ls-files").stdout.splitlines()
    assert "code.py" in tracked
    assert ".forge/task.json" not in tracked


def test_git_commit_handles_non_ascii_filenames(tmp_path):
    """git_commit correctly stages files with non-ASCII names."""
    entrypoint = _load_entrypoint_module()
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Forge Test")
    _git(tmp_path, "config", "user.email", "forge-test@example.com")

    (tmp_path / "initial.txt").write_text("initial\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")

    # Create files with non-ASCII names
    (tmp_path / "café.txt").write_text("coffee\n")
    (tmp_path / "données.py").write_text("data = True\n")

    assert entrypoint.git_commit(tmp_path, "non-ascii commit") is True

    tracked = _git(tmp_path, "ls-files").stdout.splitlines()
    # git ls-files may quote non-ASCII — check the files are committed
    log = _git(tmp_path, "log", "--oneline", "--name-only", "-1").stdout
    assert "café.txt" in log or "caf" in log
    assert "données.py" in log or "donn" in log
