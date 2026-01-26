from __future__ import annotations

import pytest

from agent_platform.diffing import validate_diff_text
from agent_platform.policy import FilesystemPolicy, Policy


def _policy(max_files: int = 5, max_lines: int = 20) -> Policy:
    return Policy(
        filesystem=FilesystemPolicy(
            denied_paths=[".env", ".git/**"],
            max_files_touched=max_files,
            max_lines_changed=max_lines,
        )
    )


def test_accepts_valid_diff() -> None:
    diff_text = (
        "diff --git a/foo.txt b/foo.txt\n"
        "index 0000000..1111111 100644\n"
        "--- a/foo.txt\n"
        "+++ b/foo.txt\n"
        "@@ -0,0 +1,1 @@\n"
        "+hi\n"
    )
    stats = validate_diff_text(diff_text, _policy())
    assert stats.touched_files == ["foo.txt"]
    assert stats.added_lines == 1


def test_rejects_non_diff() -> None:
    with pytest.raises(ValueError):
        validate_diff_text("hello world", _policy())


def test_rejects_denied_glob() -> None:
    diff_text = (
        "diff --git a/.env b/.env\n"
        "index 0000000..1111111 100644\n"
        "--- a/.env\n"
        "+++ b/.env\n"
        "@@ -0,0 +1,1 @@\n"
        "+SECRET=1\n"
    )
    with pytest.raises(ValueError):
        validate_diff_text(diff_text, _policy())


def test_enforces_file_limit() -> None:
    diff_text = (
        "diff --git a/a.txt b/a.txt\n"
        "--- a/a.txt\n"
        "+++ b/a.txt\n"
        "@@ -0,0 +1,1 @@\n"
        "+a\n"
        "diff --git a/b.txt b/b.txt\n"
        "--- a/b.txt\n"
        "+++ b/b.txt\n"
        "@@ -0,0 +1,1 @@\n"
        "+b\n"
    )
    with pytest.raises(ValueError):
        validate_diff_text(diff_text, _policy(max_files=1))


def test_enforces_line_limit() -> None:
    diff_text = (
        "diff --git a/foo.txt b/foo.txt\n"
        "--- a/foo.txt\n"
        "+++ b/foo.txt\n"
        "@@ -0,0 +3,3 @@\n"
        "+a\n"
        "+b\n"
        "+c\n"
    )
    with pytest.raises(ValueError):
        validate_diff_text(diff_text, _policy(max_lines=2))
