"""Diff validation and analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Iterable, List, Set

from .policy import Policy


DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


@dataclass(frozen=True)
class DiffStats:
    touched_files: List[str]
    added_lines: int
    removed_lines: int

    @property
    def total_changed_lines(self) -> int:
        return self.added_lines + self.removed_lines


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path))


def _parse_diff(diff_text: str) -> DiffStats:
    touched: Set[str] = set()
    added = 0
    removed = 0
    current_file: str | None = None
    for line in diff_text.splitlines():
        match = DIFF_HEADER_RE.match(line)
        if match:
            a_path, b_path = match.groups()
            file_path = b_path if b_path != "/dev/null" else a_path
            current_file = _normalize_path(file_path)
            touched.add(current_file)
            continue
        if current_file is None:
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return DiffStats(touched_files=sorted(touched), added_lines=added, removed_lines=removed)


def _matches_denied(path: str, denied_globs: Iterable[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in denied_globs)


def _is_no_changes(diff_text: str) -> bool:
    if diff_text == "NO_CHANGES":
        return True
    return diff_text.strip() == "NO_CHANGES" and diff_text.strip() != ""


def validate_diff_text(diff_text: str, policy: Policy) -> DiffStats:
    if _is_no_changes(diff_text):
        return DiffStats(touched_files=[], added_lines=0, removed_lines=0)
    if not diff_text.lstrip().startswith("diff --git "):
        raise ValueError("Diff must start with 'diff --git' or be exactly NO_CHANGES.")
    stats = _parse_diff(diff_text)
    for path in stats.touched_files:
        if _matches_denied(path, policy.filesystem.denied_paths):
            raise ValueError(f"Diff touches denied path: {path}")
    if len(stats.touched_files) > policy.filesystem.max_files_touched:
        raise ValueError("Diff exceeds maximum files touched.")
    if stats.total_changed_lines > policy.filesystem.max_lines_changed:
        raise ValueError("Diff exceeds maximum lines changed.")
    return stats
