"""Policy loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class SandboxEnvPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allowlist_prefixes: List[str] = Field(default_factory=list)
    denylist_keys: List[str] = Field(default_factory=list)


class SandboxMountsPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    repo: str = "rw"
    home: str = "none"
    ssh: str = "none"
    docker_socket: str = "none"
    secrets: str = "none"


class SandboxPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workspace_strategy: str = "git_worktree"
    ephemeral: bool = True
    container_runtime: str = "docker"
    image: str = "python:3.11-slim"
    network_default: str = "off"
    cpu_limit: str = "2"
    memory_limit: str = "4g"
    pids_limit: int = 256
    time_limit_minutes: int = 20
    mounts: SandboxMountsPolicy = Field(default_factory=SandboxMountsPolicy)
    env: SandboxEnvPolicy = Field(default_factory=SandboxEnvPolicy)

    @field_validator("network_default", mode="before")
    @classmethod
    def _validate_network_default(cls, value: str | bool) -> str:
        if isinstance(value, bool):
            return "on" if value else "off"
        if value not in {"on", "off"}:
            raise ValueError("network_default must be 'on' or 'off'.")
        return value


class FilesystemPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    write_mode: str = "patch_only"
    allowed_roots: List[str] = Field(default_factory=lambda: ["./"])
    denied_paths: List[str] = Field(default_factory=list)
    max_file_write_kb: int = 512
    max_files_touched: int = 50
    max_lines_changed: int = 2000


class NetworkPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allowed_when: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)
    blocked_domains: List[str] = Field(default_factory=list)
    allow_git_over_https_only: bool = True
    forbid_plain_http: bool = True


class DirtyRoomPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    network: str = "off"
    mounts: SandboxMountsPolicy = Field(default_factory=SandboxMountsPolicy)
    time_limit_minutes: int = 20
    cpu_limit: str = "2"
    memory_limit: str = "4g"


class UnrestrictedPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    dirty_room: DirtyRoomPolicy = Field(default_factory=DirtyRoomPolicy)


class PhasePolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    network: str = "off"
    allowlist: List[str] = Field(default_factory=list)

    @field_validator("network", mode="before")
    @classmethod
    def _validate_network(cls, value: str | bool) -> str:
        if isinstance(value, bool):
            return "on" if value else "off"
        if value not in {"on", "off"}:
            raise ValueError("phase.network must be 'on' or 'off'.")
        return value


class CommandsPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allowlist: Dict[str, List[str]] = Field(default_factory=dict)
    unrestricted: UnrestrictedPolicy = Field(default_factory=UnrestrictedPolicy)


class Policy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sandbox: SandboxPolicy = Field(default_factory=SandboxPolicy)
    filesystem: FilesystemPolicy = Field(default_factory=FilesystemPolicy)
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    phases: Dict[str, PhasePolicy] = Field(default_factory=dict)
    commands: CommandsPolicy = Field(default_factory=CommandsPolicy)

    def phase(self, name: str) -> PhasePolicy:
        phase = self.phases.get(name)
        if phase is None:
            return PhasePolicy(network=self.sandbox.network_default, allowlist=["*"])
        if not phase.allowlist:
            return PhasePolicy(network=phase.network, allowlist=["*"])
        return phase

    def is_command_allowed(self, phase: str, command: str) -> bool:
        allowlist = self.phase(phase).allowlist
        return any(fnmatch(command, pattern) for pattern in allowlist)


@dataclass(frozen=True)
class PolicyLoadResult:
    policy: Policy
    raw: Dict[str, Any]


def load_policy(path: str | Path) -> PolicyLoadResult:
    """Load and validate policy from YAML."""
    policy_path = Path(path)
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    try:
        policy = Policy.model_validate(raw)
    except ValidationError as exc:
        details = []
        for error in exc.errors():
            loc = ".".join(str(item) for item in error.get("loc", [])) or "root"
            msg = error.get("msg", "invalid value")
            details.append(f"{loc}: {msg}")
        detail_text = "; ".join(details)
        raise ValueError(f"Invalid policy file: {detail_text}") from exc
    return PolicyLoadResult(policy=policy, raw=raw)
