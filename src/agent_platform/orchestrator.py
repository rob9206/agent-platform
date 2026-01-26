"""Run loop orchestrator."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .cancel import is_cancelled
from .diffing import DiffStats, validate_diff_text
from .policy import Policy, load_policy
from .run_logging import RunLogger
from .sandbox.docker_runner import DockerRunResult, run_in_docker
from .worktrees import WorktreeInfo, create_worktree, remove_worktree


DEPS_TOUCH_PATTERNS = [
    "pyproject.toml",
    "requirements*.txt",
    "package*.json",
    "poetry.lock",
]


@dataclass(frozen=True)
class RunResult:
    task_id: str
    status: str
    worktree: Optional[WorktreeInfo]
    diff_stats: DiffStats
    deps_ran: bool
    deps_result: Optional[DockerRunResult]
    test_result: Optional[DockerRunResult]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_task_id(task: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", task.strip().lower())[:40].strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{slug or 'task'}"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _should_run_deps(touched_files: List[str]) -> bool:
    for path in touched_files:
        for pattern in DEPS_TOUCH_PATTERNS:
            file_path = Path(path)
            if file_path.match(pattern) or file_path.name == pattern or file_path.match(f"**/{pattern}"):
                return True
    return False


def _apply_patch(diff_text: str, worktree_path: Path) -> None:
    if diff_text.strip() == "NO_CHANGES":
        return
    result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=diff_text,
        text=True,
        capture_output=True,
        cwd=str(worktree_path),
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git apply failed: {message}")


def run_task(
    repo_root: Path,
    task: str,
    diff_text: str,
    test_cmd: str,
    deps_cmd: Optional[str],
    keep_worktree: bool,
    policy_path: Path,
) -> RunResult:
    task_id = _safe_task_id(task)
    run_dir = repo_root / ".agent_runs" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger = RunLogger(task_id=task_id, log_path=run_dir / "events.jsonl")
    (run_dir / "test_output.txt").write_text("", encoding="utf-8")

    diff_path = run_dir / "diff.patch"
    diff_path.write_text(diff_text, encoding="utf-8")
    logger.log("run_started", {"task": task, "task_id": task_id})

    worktree: Optional[WorktreeInfo] = None
    diff_stats = DiffStats(touched_files=[], added_lines=0, removed_lines=0)
    deps_result: Optional[DockerRunResult] = None
    test_result: Optional[DockerRunResult] = None
    deps_ran = False
    status = "failed"
    error_message: Optional[str] = None
    start_time = _utc_iso()

    try:
        policy_result = load_policy(policy_path)
        policy = policy_result.policy
        logger.log("policy_loaded", {"path": str(policy_path)})

        diff_stats = validate_diff_text(diff_text, policy)
        logger.log("diff_validated", diff_stats.__dict__)

        worktree = create_worktree(repo_root, task_id)
        logger.log("worktree_created", {"path": str(worktree.path), "branch": worktree.branch})

        if is_cancelled(run_dir):
            status = "cancelled"
            return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)

        _apply_patch(diff_text, worktree.path)
        logger.log("patch_applied", {"touched_files": diff_stats.touched_files})

        if is_cancelled(run_dir):
            status = "cancelled"
            return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)

        deps_needed = deps_cmd is not None and _should_run_deps(diff_stats.touched_files)
        if deps_needed:
            deps_ran = True
            logger.log("deps_started", {"command": deps_cmd})
            deps_result = run_in_docker(
                deps_cmd,
                worktree.path,
                policy,
                phase="deps",
                network_override="on",
            )
            logger.log(
                "deps_finished",
                {
                    "exit_code": deps_result.exit_code,
                    "timed_out": deps_result.timed_out,
                    "docker_args": deps_result.docker_args,
                },
            )
            if deps_result.exit_code != 0:
                status = "failed"
                return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)

        if is_cancelled(run_dir):
            status = "cancelled"
            return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)

        logger.log("test_started", {"command": test_cmd})
        test_result = run_in_docker(
            test_cmd,
            worktree.path,
            policy,
            phase="test",
            network_override="off",
        )
        (run_dir / "test_output.txt").write_text(test_result.output, encoding="utf-8")
        logger.log(
            "test_finished",
            {
                "exit_code": test_result.exit_code,
                "timed_out": test_result.timed_out,
                "docker_args": test_result.docker_args,
            },
        )

        status = "success" if test_result.exit_code == 0 else "failed"
        return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)
    except Exception as exc:  # noqa: BLE001 - surface as run failure
        error_message = str(exc)
        logger.log("run_failed", {"error": error_message})
        status = "failed"
        return RunResult(task_id, status, worktree, diff_stats, deps_ran, deps_result, test_result)
    finally:
        finish_time = _utc_iso()
        summary = {
            "task_id": task_id,
            "task": task,
            "status": status,
            "error": error_message,
            "started_at": start_time,
            "finished_at": finish_time,
            "diff": {
                "touched_files": diff_stats.touched_files,
                "added_lines": diff_stats.added_lines,
                "removed_lines": diff_stats.removed_lines,
            },
            "deps_ran": deps_ran,
            "deps_exit_code": deps_result.exit_code if deps_result else None,
            "test_exit_code": test_result.exit_code if test_result else None,
            "worktree": str(worktree.path) if worktree else None,
        }
        _write_json(run_dir / "run.json", summary)
        logger.log("run_finished", {"status": status})
        if worktree and not keep_worktree:
            try:
                remove_worktree(repo_root, worktree)
                logger.log("worktree_removed", {"path": str(worktree.path)})
            except RuntimeError as exc:
                logger.log("worktree_remove_failed", {"error": str(exc)})
