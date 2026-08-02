"""Secrets and PII scanning on evaluation artifacts (X10).

Scans RunArtifacts and scenario outputs for leaked secrets, API keys,
and personally identifiable information before persisting to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ScanIssue:
    """A single secret/PII detection result.

    Attributes:
        location: Where the match was found (e.g. ``"output.final"``,
            ``"trajectory.step.N.tool"``).
        issue_type: Category of the match (e.g. ``"api_key"``, ``"pii_email"``).
        matched: Truncated (20 chars + ``"..."``) representation of the match.
        severity: One of ``"critical"``, ``"high"``, ``"medium"``, ``"low"``.
    """
    location: str
    issue_type: str
    matched: str
    severity: str


@dataclass
class ScanReport:
    """Aggregated scan results for a single artifact.

    Attributes:
        artifact_id: Identifier of the scanned artifact.
        issues: List of :class:`ScanIssue` found.
        clean: ``True`` if no issues were detected.
    """
    artifact_id: str
    issues: list[ScanIssue] = field(default_factory=list)
    clean: bool = True


class SecretsScanner:
    """Scans artifacts for secrets and PII before persistence."""

    PATTERNS: ClassVar[list[tuple[str, str, str]]] = [
        # OpenAI / Anthropic API keys
        (r"sk-[a-zA-Z0-9]{20,}", "api_key", "critical"),
        (r"sk-ant-[a-zA-Z0-9-_]{20,}", "api_key", "critical"),
        # GitHub tokens
        (r"gh[pousr]_[a-zA-Z0-9]{20,}", "token", "critical"),
        (r"gho_[a-zA-Z0-9]{20,}", "token", "critical"),
        # AWS access keys
        (r"AKIA[0-9A-Z]{16}", "aws_key", "critical"),
        # Generic secret patterns (key=value or key: value)
        (r"(?i)(?:api[-_]?key|secret|password|token)\s*[:=]\s*[\"']?[a-zA-Z0-9_-]{8,}[\"']?", "token", "high"),  # noqa: E501
        # PII: email
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "pii_email", "medium"),
        # PII: phone (US-style)
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "pii_phone", "medium"),
        # IP addresses
        (r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", "ip_address", "low"),
        # PII: credit card (Luhn not checked)
        (r"\b(?:\d{4}[ -]?){3}\d{4}\b", "pii_cc", "high"),
        # PII: US SSN
        (r"\b\d{3}-\d{2}-\d{4}\b", "pii_ssn", "high"),
    ]

    @staticmethod
    def scan_text(text: str, location: str = "unknown") -> list[ScanIssue]:
        """Scan a single string for secrets and PII using the compiled patterns.

        Args:
            text: The string to scan.
            location: A human-readable location label for reporting.

        Returns:
            List of :class:`ScanIssue` for every match found.
        """
        issues: list[ScanIssue] = []
        if not text:
            return issues
        for pattern, issue_type, severity in SecretsScanner.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched = match.group(0)
                issues.append(ScanIssue(location, issue_type, matched[:20] + "...", severity))
        return issues

    @staticmethod
    def scan_artifact(artifact: dict[str, Any]) -> ScanReport:
        """Scan a full artifact dict (output + trajectory + error) for secrets.

        Args:
            artifact: The artifact dict to scan.

        Returns:
            A :class:`ScanReport` with all findings.
        """
        report = ScanReport(artifact_id=artifact.get("id", "unknown"))
        output = artifact.get("output", {})
        if isinstance(output, dict):
            final = output.get("final", "")
            if isinstance(final, str):
                report.issues.extend(SecretsScanner.scan_text(final, "output.final"))
            structured = output.get("structured")
            if isinstance(structured, dict | list):
                report.issues.extend(
                    SecretsScanner.scan_text(str(structured), "output.structured")
                )
        trajectory = artifact.get("trajectory", [])
        if isinstance(trajectory, list):
            for i, step in enumerate(trajectory):
                if isinstance(step, dict):
                    for field in ("content", "result", "args"):
                        val = step.get(field)
                        if isinstance(val, str | dict | list):
                            report.issues.extend(
                                SecretsScanner.scan_text(str(val), f"trajectory.{i}.{field}")
                            )
        error = artifact.get("error")
        if isinstance(error, str):
            report.issues.extend(SecretsScanner.scan_text(error, "error"))
        report.clean = len(report.issues) == 0
        return report

    @staticmethod
    def sanitize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        """Return a sanitised copy of the artifact with secrets redacted.

        Currently redacts found secrets from ``output.final`` by replacing
        matches with ``[REDACTED:<type>]``.

        Args:
            artifact: The original artifact dict.

        Returns:
            A sanitised copy.
        """
        sanitized = dict(artifact)
        report = SecretsScanner.scan_artifact(artifact)
        for issue in report.issues:
            replacement = f"[REDACTED:{issue.issue_type}]"
            if issue.location == "output.final":
                final = sanitized.get("output", {}).get("final", "")
                if isinstance(final, str):
                    sanitized.setdefault("output", {})["final"] = re.sub(
                        re.escape(issue.matched[:-3]), replacement, final
                    )
        return sanitized
