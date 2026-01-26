"""Git worktree management."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeInfo:
    task_id: str
    branch: str
    path: Path


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _ensure_git_repo(repo_root: Path) -> None:
    result = _run_git(["rev-parse", "--is-inside-work-tree"], repo_root)
    if result.returncode != 0:
        raise RuntimeError(
            "Not a git repository. Initialize git before running agentctl."
        )
    head = _run_git(["rev-parse", "HEAD"], repo_root)
    if head.returncode != 0:
        raise RuntimeError(
            "Git repository has no commits. Create an initial commit before running."
        )


def create_worktree(repo_root: Path, task_id: str) -> WorktreeInfo:
    _ensure_git_repo(repo_root)
    worktree_dir = repo_root / ".agent_worktrees" / task_id
    branch_name = f"agent/{task_id}"
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    result = _run_git(
        ["worktree", "add", "-b", branch_name, str(worktree_dir)],
        repo_root,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create worktree: {result.stderr.strip() or result.stdout.strip()}"
        )
    return WorktreeInfo(task_id=task_id, branch=branch_name, path=worktree_dir)


def remove_worktree(repo_root: Path, worktree: WorktreeInfo) -> None:
    result = _run_git(["worktree", "remove", str(worktree.path)], repo_root)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to remove worktree: {result.stderr.strip() or result.stdout.strip()}"
        )
