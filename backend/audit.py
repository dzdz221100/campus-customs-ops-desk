"""Append-only audit trail of agent team activity (output/audit_trail.json).

Every team run appends its own entries here and nothing ever gets removed
or overwritten -- the file is read, extended, and rewritten whole each time
(small file, no DB needed, homework-scale single-process usage).
"""

from __future__ import annotations

import json
from pathlib import Path

from models import AuditEntry

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"

# How much of a tool's args/result gets written to the audit trail.
AUDIT_LOG_CHAR_LIMIT = 300


def truncate(value: object, limit: int = AUDIT_LOG_CHAR_LIMIT) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def append_audit_entries(entries: list[AuditEntry]) -> None:
    if not entries:
        return
    existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
    existing.extend(entry.model_dump() for entry in entries)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
