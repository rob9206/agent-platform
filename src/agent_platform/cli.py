"""CLI entrypoint for agent platform."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .orchestrator import run_task


def _read_diff(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a task in the agent sandbox.")
    run_parser.add_argument("--task", required=True, help="Task description text.")
    run_parser.add_argument("--diff-file", required=True, help="Diff file path or '-' for stdin.")
    run_parser.add_argument("--test-cmd", required=True, help="Test command to run.")
    run_parser.add_argument("--deps-cmd", required=False, help="Deps command to run if needed.")
    run_parser.add_argument("--keep-worktree", action="store_true", help="Keep worktree after run.")
    run_parser.add_argument(
        "--policy-file",
        default="agent_policy.yaml",
        help="Path to agent policy YAML.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        diff_text = _read_diff(args.diff_file)
        result = run_task(
            repo_root=Path.cwd(),
            task=args.task,
            diff_text=diff_text,
            test_cmd=args.test_cmd,
            deps_cmd=args.deps_cmd,
            keep_worktree=args.keep_worktree,
            policy_path=Path(args.policy_file),
        )
        return 0 if result.status == "success" else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
