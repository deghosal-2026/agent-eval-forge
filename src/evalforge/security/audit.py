"""Audit trail for evaluation runs.

Records every run invocation, its configuration, results, and any
security-relevant events (sandbox activations, key sanitizations, etc.)
to an append-only JSON log file.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Logger for audit trail events. Used at INFO level so that security-relevant
# events are always visible in CI logs. The audit trail itself is the primary
# record; logging provides a secondary channel for real-time observability.
logger = logging.getLogger("evalforge.security")


class AuditTrail:
    """Append-only audit trail for evaluation runs.

    Each call to :meth:`record` appends a JSON line to
    ``<base_dir>/audit/audit.log``. Events are timestamped and categorized
    for later filtering via :meth:`get_events`.
    """

    def __init__(self, base_dir: str | Path = ".evalforge") -> None:
        """Initialize the audit trail directory.

        Args:
            base_dir: Root directory under which the ``audit/`` subdirectory
                and ``audit.log`` file are created. Defaults to ``.evalforge``.
        """
        self._log_dir = Path(base_dir) / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "audit.log"

    def record(self, event: str, details: dict[str, Any]) -> None:
        """Record a single audit event.

        Appends a JSON line to the audit log with an ISO-8601 UTC timestamp.

        Args:
            event: Event type (e.g. ``"run_start"``, ``"run_complete"``,
                ``"sandbox_active"``, ``"key_sanitized"``).
            details: Event-specific data keyed by name.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "details": details,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Read all audit events, optionally filtered by type.

        Args:
            event_type: If provided, only events with this ``event`` value
                are returned. If ``None``, all events are returned.

        Returns:
            List of event dicts in chronological order.
        """
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
