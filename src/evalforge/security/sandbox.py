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
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with sandbox restrictions.

    S603 notes: ``subprocess.run`` is called with user-supplied args (the agent
    command), but this is the security boundary — all callers go through trust
    policy enforcement before reaching this function. The env stripping here
    is the primary sandbox mechanism.
    """
    if not config.enabled:
        # Non-sandboxed path: pass through all env vars for compatibility.
        # The trust policy already verified this is an allowed combination.
        return subprocess.run(  # noqa: S603
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

    return subprocess.run(  # noqa: S603
        args,
        input=input,
        capture_output=True,
        text=True,
        timeout=timeout * config.timeout_multiplier,
        env=sandbox_env,
    )


@dataclass
class DockerConfig:
    """Configuration for Docker-based agent execution."""
    image: str = "evalforge-agent-runner"
    network_disabled: bool = True
    read_only_root: bool = True
    memory_limit: str = "512m"
    cpu_limit: float = 1.0


def run_in_container(
    agent_cmd: list[str],
    payload_str: str,
    config: DockerConfig,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run an agent inside a Docker container with isolation."""
    docker_args = ["docker", "run", "--rm"]
    if config.network_disabled:
        docker_args.extend(["--network", "none"])
    if config.read_only_root:
        docker_args.extend(["--read-only"])
    if config.memory_limit:
        docker_args.extend(["--memory", config.memory_limit])
    if config.cpu_limit:
        docker_args.extend(["--cpus", str(config.cpu_limit)])
    # S108: tmpfs path is hardcoded and non-configurable — this is intentional
    # for the Docker sandbox to prevent accidental FS writes. The tmpfs is
    # ephemeral and limited to 64MB, so no realistic risk of filling /tmp.
    docker_args.extend(["--tmpfs", "/tmp:noexec,nosuid,size=64m"])  # noqa: S108
    docker_args.append(config.image)
    docker_args.extend(agent_cmd)

    return subprocess.run(  # noqa: S603
        docker_args,
        input=payload_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
