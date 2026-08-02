"""Security module for agent evaluation.

Provides audit trail logging, sandbox execution, egress policy enforcement,
secret sanitization, security-focused scorers, and trust policy management.

Sub-modules:
    audit: Append-only JSON audit trail for evaluation runs.
    sandbox: Subprocess and Docker sandboxing for untrusted packs.
    egress: Network egress policy controller and builder.
    sanitize: API key and secret redaction utilities.
    evals: Security-focused scorers (prompt injection, exfiltration, SSRF, sandbox escape).
    policy: Trust policy matrix for pack/adapter combinations.
"""

from evalforge.security.audit import AuditTrail
from evalforge.security.sandbox import DockerConfig, SandboxConfig, run_in_container, sandboxed_run
from evalforge.security.sanitize import SANITIZE_PATTERNS, sanitize_config

__all__ = [
    "SANITIZE_PATTERNS",
    "AuditTrail",
    "DockerConfig",
    "SandboxConfig",
    "run_in_container",
    "sandboxed_run",
    "sanitize_config",
]
