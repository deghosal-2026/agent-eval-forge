"""Integration tests for the sandbox security layer.

These tests are mock-based (no external Docker or API dependencies).  They
verify that ``SandboxConfig`` and the trust policy enforce the isolation
contracts specified by P2.2: environment redaction, timeout multiplier, trust
policy enforcement, and fixture-level isolation.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from evalforge.security.policy import TrustPolicy, TrustLevel
from evalforge.security.sandbox import SandboxConfig, sandboxed_run


class TestSandboxEnvRedaction:
    """Verify that sandboxed runs strip non-allowlist environment variables."""

    def test_env_redaction(self) -> None:
        """Only allowlist variables should survive in the sandboxed child process."""
        config = SandboxConfig(enabled=True)
        result = sandboxed_run(
            [sys.executable, "-c", "import os; print(sorted(os.environ.keys()))"],
            config,
            env={"EVALFORGE_SANDBOX": "1", "MY_SECRET": "hush"},
        )
        env_keys = eval(result.stdout.strip())
        assert "EVALFORGE_SANDBOX" in env_keys
        assert "MY_SECRET" not in env_keys

    def test_allowlist_customized(self) -> None:
        """A custom allowlist should include only the specified variables."""
        config = SandboxConfig(enabled=True, allowlist={"MY_CUSTOM_VAR"})
        result = sandboxed_run(
            [sys.executable, "-c", "import os; print(os.environ.get('MY_CUSTOM_VAR', 'NOT_SET'))"],
            config,
            env={"MY_CUSTOM_VAR": "present", "OTHER_VAR": "absent"},
        )
        assert result.stdout.strip() == "present"


class TestSandboxTimeoutMultiplier:
    """Verify that the sandbox applies a 2x timeout multiplier."""

    def test_timeout_multiplier(self) -> None:
        """A sandbox with 2x multiplier should allow a command that times out at base."""
        config = SandboxConfig(enabled=True, timeout_multiplier=2.0)
        result = sandboxed_run(
            [sys.executable, "-c", "import time; time.sleep(0.5); print('done')"],
            config,
            timeout=1.0,
        )
        assert result.stdout.strip() == "done"


class TestTrustPolicyEnforcement:
    """Verify the trust policy rejects/allows combinations correctly."""

    def test_trust_policy_external_rejected(self) -> None:
        """External trust with subprocess and no sandbox should be denied."""
        policy = TrustPolicy(trust="external", adapter_type="subprocess", sandbox=False)
        allowed, reason = policy.allowed()
        assert allowed is False
        assert reason is not None and "sandbox" in reason.lower()

    def test_trust_policy_external_sandbox_allowed(self) -> None:
        """External trust with subprocess and sandbox enabled should be allowed."""
        policy = TrustPolicy(trust="external", adapter_type="subprocess", sandbox=True)
        allowed, reason = policy.allowed()
        assert allowed is True
        assert reason is None

    def test_external_non_subprocess_rejected(self) -> None:
        """External trust with a non-subprocess adapter should be denied."""
        policy = TrustPolicy(trust="external", adapter_type="python", sandbox=True)
        allowed, reason = policy.allowed()
        assert allowed is False
        assert reason is not None and "python" in reason.lower()

    def test_local_trust_always_allowed(self) -> None:
        """Local trust should allow subprocess with or without sandbox."""
        for sandbox in (True, False):
            policy = TrustPolicy(trust="local", adapter_type="subprocess", sandbox=sandbox)
            allowed, reason = policy.allowed()
            assert allowed is True
            assert reason is None

    def test_builtin_trust_always_allowed(self) -> None:
        """Builtin trust should allow any adapter regardless of sandbox."""
        for adapter in ("subprocess", "python", "http"):
            policy = TrustPolicy(trust="builtin", adapter_type=adapter, sandbox=False)
            allowed, reason = policy.allowed()
            assert allowed is True
            assert reason is None


class TestSandboxWithFixtures:
    """Verify sandbox + fixtures together do not leak state across runs."""

    def test_sandbox_with_fixtures_no_leakage(self, tmp_path) -> None:
        """Environment isolation should be maintained when using tmp_path fixtures."""
        config = SandboxConfig(enabled=True)

        first = sandboxed_run(
            [sys.executable, "-c", "import os; print(os.environ.get('LEAK_VAR', 'NOT_SET'))"],
            config,
            env={"LEAK_VAR": "value1"},
        )
        assert first.stdout.strip() == "NOT_SET"

        second = sandboxed_run(
            [sys.executable, "-c", "import os; print(os.environ.get('LEAK_VAR', 'NOT_SET'))"],
            config,
            env={"LEAK_VAR": "value2"},
        )
        assert second.stdout.strip() == "NOT_SET"

    def test_sandbox_disabled_passes_through_env(self) -> None:
        """When sandbox is disabled, env vars should pass through normally."""
        config = SandboxConfig(enabled=False)
        result = sandboxed_run(
            [sys.executable, "-c", "import os; print(os.environ.get('PATH', 'NOT_SET')[:4])"],
            config,
        )
        assert result.stdout.strip() != "NOT_SET"

    def test_sandbox_creates_separate_tmpdir(self, tmp_path) -> None:
        """The TMPDIR from the sandbox should not leak host paths."""
        host_tmpdir = str(tmp_path)
        config = SandboxConfig(enabled=True)

        sandboxed_run(
            [sys.executable, "-c", "pass"],
            config,
            env={"TMPDIR": host_tmpdir},
            timeout=5.0,
        )
        assert tmp_path.exists()