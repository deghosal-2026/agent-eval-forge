"""Adapter error taxonomy — normalizes errors into actionable reason strings.

Maps adapter exceptions to structured, consistent error categories so
``result.json`` reason strings are actionable across runs and adapters.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar


class AdapterErrorTaxonomy:
    """Normalizes adapter errors into actionable, consistent reason strings."""

    ERROR_CATEGORIES: ClassVar[dict[str, str]] = {
        "import_error": (
            "Agent module could not be imported. "
            "Check module path and dependencies."
        ),
        "function_missing": (
            "Agent function not found. "
            "Verify the function name in agent spec."
        ),
        "timeout": (
            "Agent exceeded timeout. "
            "Increase --timeout or optimize agent."
        ),
        "crash": (
            "Agent process crashed. "
            "Check agent stderr for details."
        ),
        "invalid_output": (
            "Agent output is not valid JSON "
            "or missing required fields."
        ),
        "connection_refused": (
            "Agent HTTP server not reachable. "
            "Start the agent server first."
        ),
        "api_key_missing": (
            "API key not found in environment. "
            "Set the required env var."
        ),
        "sandbox_violation": (
            "Agent attempted forbidden operation "
            "in sandbox mode."
        ),
        "network_blocked": (
            "Agent attempted network access "
            "in network-isolated mode."
        ),
        "unknown": "An unexpected error occurred.",
    }

    _PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (re.compile(r"ModuleNotFoundError|ImportError|No module named"), "import_error"),
        (re.compile(r"AttributeError.*has no attribute|function.*not found"), "function_missing"),
        (re.compile(r"TimeoutExpired|timed out|TimeoutError"), "timeout"),
        (re.compile(r"non-zero exit|crash|segfault|killed"), "crash"),
        (re.compile(r"JSONDecodeError|not valid JSON|not a JSON object"), "invalid_output"),
        (re.compile(r"ConnectionError|Connection refused|ConnectError"), "connection_refused"),
        (re.compile(r"api_key|API_KEY|Authorization|401|403"), "api_key_missing"),
        (re.compile(r"sandbox|forbidden|permission denied"), "sandbox_violation"),
        (re.compile(r"network|egress|blocked"), "network_blocked"),
    ]

    @staticmethod
    def categorize(error: Exception) -> str:
        """Categorize an error into a known category."""
        msg = str(error)
        for pattern, category in AdapterErrorTaxonomy._PATTERNS:
            if pattern.search(msg):
                return category
        return "unknown"

    @staticmethod
    def normalize(error: Exception, adapter_type: str) -> dict[str, Any]:
        """Normalize an error into a structured reason dict."""
        category = AdapterErrorTaxonomy.categorize(error)
        return {
            "category": category,
            "reason": str(error),
            "actionable": AdapterErrorTaxonomy.ERROR_CATEGORIES.get(
                category, AdapterErrorTaxonomy.ERROR_CATEGORIES["unknown"]
            ),
            "adapter_type": adapter_type,
        }

    @staticmethod
    def to_result_json(error: Exception, adapter_type: str) -> dict[str, Any]:
        """Generate a result.json-compatible error envelope."""
        normalized = AdapterErrorTaxonomy.normalize(error, adapter_type)
        return {
            "schema_version": "evalforge.run_envelope.v1",
            "status": "error",
            "output": {"final": None, "structured": None},
            "trajectory": {"steps": []},
            "cost": None,
            "error": normalized["reason"],
            "error_category": normalized["category"],
            "error_actionable": normalized["actionable"],
            "adapter_type": adapter_type,
        }
