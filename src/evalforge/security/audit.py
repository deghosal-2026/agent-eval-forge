"""Audit trail for evaluation runs.

Records every run invocation, its configuration, results, and any
security-relevant events (sandbox activations, key sanitizations, etc.)
to an append-only JSON log file.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditTrail:
    """Append-only audit trail for evaluation runs.

    Each call to :meth:`record` appends a JSON line to
    ``<base_dir>/audit/audit.log``.
    """

    def __init__(self, base_dir: str | Path = ".evalforge") -> None:
        self._log_dir = Path(base_dir) / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "audit.log"

    def record(self, event: str, details: dict[str, Any]) -> None:
        """Record a single audit event.

        Args:
            event: Event type (e.g. ``"run_start"``, ``"run_complete"``,
                ``"sandbox_active"``, ``"key_sanitized"``).
            details: Event-specific data.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "details": details,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Read all audit events, optionally filtered by type."""
        if not self._log_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self._log_path.read_text().strip().split("\n"):
            if not line:
                continue
            entry = json.loads(line)
            if event_type is None or entry.get("event") == event_type:
                events.append(entry)
        return events
