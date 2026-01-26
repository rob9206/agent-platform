from __future__ import annotations

from pathlib import Path

import pytest

from agent_platform.policy import load_policy


def test_load_policy_defaults(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("{}", encoding="utf-8")
    result = load_policy(policy_path)
    assert result.policy.sandbox.image
    assert result.policy.filesystem.max_files_touched > 0


def test_load_policy_invalid_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("sandbox: [1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(policy_path)
