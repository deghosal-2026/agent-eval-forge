"""Sandbox for running untrusted scenario packs.

When ``--sandbox`` is enabled, the subprocess adapter:
- Strips all env vars except a minimal allowlist
- Sets ``EVALFORGE_SANDBOX=1`` in the child process
- Adds a 2x timeout multiplier to prevent DoS
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

# Minimal env vars allowed in sandbox mode
SANDBOX_ALLOWLIST = {
    "PATH", "HOME", "TMPDIR", "USER",
    "EVALFORGE_SANDBOX", "EVALFORGE_FIXTURES_DIR",
}


@dataclass
class SandboxConfig:
    """Configuration for sandboxed agent execution."""
    enabled: bool = False
    allowlist: set[str] = field(default_factory=lambda: SANDBOX_ALLOWLIST)
    timeout_multiplier: float = 2.0


def sandboxed_run(
    args: list[str],
    config: SandboxConfig,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sandbox restrictions."""
    if not config.enabled:
        return subprocess.run(
            args,
            input=input,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )

    sandbox_env: dict[str, str] = {"EVALFORGE_SANDBOX": "1"}
    for key in config.allowlist:
        if key in os.environ:
            sandbox_env[key] = os.environ[key]
    if env:
        for key in config.allowlist.intersection(env):
            sandbox_env[key] = env[key]

    return subprocess.run(
        args,
        input=input,
        capture_output=True,
        text=True,
        timeout=timeout * config.timeout_multiplier,
        env=sandbox_env,
    )
