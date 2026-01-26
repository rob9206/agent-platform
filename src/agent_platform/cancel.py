"""Cancellation helpers."""

from __future__ import annotations

from pathlib import Path


def cancel_flag_path(run_dir: Path) -> Path:
    return run_dir / "cancel.flag"


def is_cancelled(run_dir: Path) -> bool:
    return cancel_flag_path(run_dir).exists()
