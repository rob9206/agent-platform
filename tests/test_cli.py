from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


def test_agentctl_is_executable() -> None:
    """Verify agentctl script has execute permissions."""
    repo_root = Path(__file__).resolve().parents[1]
    agentctl_path = repo_root / "agentctl"
    assert agentctl_path.exists(), "agentctl script not found"
    
    file_stat = agentctl_path.stat()
    is_executable = bool(file_stat.st_mode & stat.S_IXUSR)
    assert is_executable, f"agentctl script is not executable (mode: {oct(file_stat.st_mode)})"
