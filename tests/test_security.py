"""Tests for the security module."""

import json
import os
from pathlib import Path

import pytest

from evalforge.security.audit import AuditTrail
from evalforge.security.sandbox import SandboxConfig, sandboxed_run
from evalforge.security.sanitize import sanitize_config


class TestSanitize:
    def test_redacts_api_key_keys(self) -> None:
        config = {"api_key": "sk-12345678901234567890", "model": "gpt-4"}
        result = sanitize_config(config)
        assert result["api_key"] == "[REDACTED]"
        assert result["model"] == "gpt-4"

    def test_redacts_openai_key_pattern_in_strings(self) -> None:
        config = {"prompt": "Use key sk-12345678901234567890 here"}
        result = sanitize_config(config)
        assert "sk-12345678901234567890" not in result["prompt"]
        assert "[REDACTED]" in result["prompt"]

    def test_redacts_github_token(self) -> None:
        token = "ghp_" + "a" * 36
        config = {"github_token": token}
        result = sanitize_config(config)
        assert result["github_token"] == "[REDACTED]"

    def test_nested_dict_sanitization(self) -> None:
        config = {"credentials": {"api_key": "sk-secret", "user": "admin"}}
        result = sanitize_config(config)
        assert result["credentials"]["api_key"] == "[REDACTED]"
        assert result["credentials"]["user"] == "admin"

    def test_depth_limit(self) -> None:
        deep = {}
        current = deep
        for _ in range(15):
            current["nested"] = {}
            current = current["nested"]
        result = sanitize_config(deep)
        assert "[REDACTED]" in str(result)


class TestAudit:
    def test_record_and_read(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        audit.record("run_start", {"run_id": "run-001"})
        audit.record("run_complete", {"run_id": "run-001", "passed": 5})
        events = audit.get_events()
        assert len(events) == 2
        assert events[0]["event"] == "run_start"
        assert events[0]["details"]["run_id"] == "run-001"

    def test_filter_by_event_type(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        audit.record("run_start", {})
        audit.record("run_complete", {})
        starts = audit.get_events("run_start")
        assert len(starts) == 1

    def test_empty_audit(self, tmp_path: Path) -> None:
        audit = AuditTrail(base_dir=str(tmp_path))
        assert audit.get_events() == []


class TestSandbox:
    def test_sandbox_echo(self) -> None:
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(["echo", "hello"], config)
        assert result.stdout.strip() == "hello"
        assert result.returncode == 0

    def test_sandbox_strips_env(self) -> None:
        os.environ["EVIL_VAR"] = "malicious"
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(
            ["python3", "-c", "import os; print(os.environ.get('EVIL_VAR', 'NOT_SET'))"],
            config,
        )
        assert result.stdout.strip() == "NOT_SET"

    def test_sandbox_allowlist_preserved(self) -> None:
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(
            ["python3", "-c", "import os; print(os.environ.get('PATH', 'NOT_SET')[:4])"],
            config,
        )
        assert result.stdout.strip() != "NOT_SET"

    def test_sandbox_timing(self) -> None:
        config = SandboxConfig(enabled=True, timeout_multiplier=2.0)
        import subprocess
        result = sandboxed_run(["echo", "timing"], config, timeout=10)
        assert result.stdout.strip() == "timing"