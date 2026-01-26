"""Docker sandbox runner."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ..policy import Policy


@dataclass(frozen=True)
class DockerRunResult:
    command: str
    exit_code: int
    output: str
    timed_out: bool
    docker_args: List[str]


def _filtered_env(policy: Policy) -> Dict[str, str]:
    allowed_prefixes = policy.sandbox.env.allowlist_prefixes
    denylist = {key.upper() for key in policy.sandbox.env.denylist_keys}
    filtered: Dict[str, str] = {}
    for key, value in os.environ.items():
        if key.upper() in denylist:
            continue
        if any(key.startswith(prefix) for prefix in allowed_prefixes):
            filtered[key] = value
    return filtered


def run_in_docker(
    command: str,
    worktree_path: Path,
    policy: Policy,
    phase: str,
    network_override: str | None = None,
    timeout_minutes: int | None = None,
) -> DockerRunResult:
    phase_policy = policy.phase(phase)
    if not policy.is_command_allowed(phase, command):
        raise ValueError(f"Command not allowed in phase '{phase}': {command}")

    if network_override not in (None, "on", "off"):
        raise ValueError("network_override must be 'on', 'off', or None.")
    network = network_override or phase_policy.network or policy.sandbox.network_default
    if network == "on" and phase_policy.network != "on":
        raise ValueError(f"Network access is not allowed for phase '{phase}'.")
    network_arg = "bridge" if network == "on" else "none"

    timeout = (timeout_minutes or policy.sandbox.time_limit_minutes) * 60

    docker_args = [
        "docker",
        "run",
        "--rm",
        "--network",
        network_arg,
        "--cpus",
        str(policy.sandbox.cpu_limit),
        "--memory",
        str(policy.sandbox.memory_limit),
        "--pids-limit",
        str(policy.sandbox.pids_limit),
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{worktree_path}:/repo:rw",
        "--workdir",
        "/repo",
    ]

    for key, value in _filtered_env(policy).items():
        docker_args.extend(["-e", f"{key}={value}"])

    docker_args.extend([policy.sandbox.image, "sh", "-lc", command])

    try:
        completed = subprocess.run(
            docker_args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return DockerRunResult(
            command=command,
            exit_code=completed.returncode,
            output=output,
            timed_out=False,
            docker_args=docker_args,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return DockerRunResult(
            command=command,
            exit_code=124,
            output=output,
            timed_out=True,
            docker_args=docker_args,
        )
