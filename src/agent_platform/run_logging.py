"""Deterministic JSONL logging for runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunLogger:
    task_id: str
    log_path: Path

    def log(self, event: str, data: Dict[str, Any] | None = None) -> None:
        payload = {
            "ts": _utc_iso(),
            "task_id": self.task_id,
            "event": event,
            "data": data or {},
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True))
            handle.write("\n")
