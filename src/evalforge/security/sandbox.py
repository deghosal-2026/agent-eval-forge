"""Sandbox for running untrusted scenario packs.

When ``--sandbox`` is enabled, the subprocess adapter:
- Strips all env vars except a minimal allowlist
- Sets ``EVALFORGE_SANDBOX=1`` in the child process
- Adds a 2x timeout multiplier to prevent DoS

Also provides Docker-based sandboxing via :func:`run_in_container`.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field

# Minimal env vars allowed in sandbox mode. Only these variables are
# forwarded from the parent process into the sandboxed child process.
SANDBOX_ALLOWLIST = {
    "PATH", "HOME", "TMPDIR", "USER",
    "EVALFORGE_SANDBOX", "EVALFORGE_FIXTURES_DIR",
}


@dataclass
class SandboxConfig:
    """Configuration for sandboxed agent execution via subprocess.

    Attributes:
        enabled: Whether sandbox restrictions are active.
        allowlist: Set of environment variable keys permitted in the sandbox.
        timeout_multiplier: Factor applied to the configured timeout to
            account for sandbox overhead.
    """

    enabled: bool = False
    allowlist: set[str] = field(default_factory=lambda: SANDBOX_ALLOWLIST)
    timeout_multiplier: float = 2.0


def sandboxed_run(
    args: list[str],
    config: SandboxConfig,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
    input: str | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with sandbox restrictions.

    S603 notes: ``subprocess.run`` is called with user-supplied args (the agent
    command), but this is the security boundary — all callers go through trust
    policy enforcement before reaching this function. The env stripping here
    is the primary sandbox mechanism.

    Args:
        args: Command and arguments for the subprocess.
        config: Sandbox configuration (enable/disable, allowlist, timeout).
        env: Additional environment variables to include (filtered through
            the allowlist when sandbox is enabled).
        timeout: Timeout in seconds (multiplied by
            ``config.timeout_multiplier`` when sandboxed).
        input: Optional stdin string for the subprocess.
        cwd: Working directory for the subprocess.

    Returns:
        The completed process result with captured stdout and stderr.
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
            cwd=cwd,
        )

    # Build a stripped-down environment from the allowlist
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
        cwd=cwd,
    )


@dataclass
class DockerConfig:
    """Configuration for Docker-based agent execution.

    Attributes:
        image: Docker image name to run.
        network_disabled: Whether to disable networking (``--network none``).
        read_only_root: Whether to mount the root filesystem as read-only.
        memory_limit: Memory limit string (e.g. ``"512m"``).
        cpu_limit: CPU limit in cores.
        add_host_gateway: On Linux, add
            ``host.docker.internal:host-gateway`` mapping to match
            Docker Desktop behavior.
    """

    image: str = "evalforge-agent-runner"
    network_disabled: bool = True
    read_only_root: bool = True
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    # When true, add host.docker.internal mapping to the container (Linux only)
    # so in-container code can reach services on the host via
    # http://host.docker.internal:PORT, matching Docker Desktop behavior.
    add_host_gateway: bool = False


def run_in_container(
    agent_cmd: list[str],
    payload_str: str,
    config: DockerConfig,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run an agent inside a Docker container with isolation.

    Builds a ``docker run`` command with the specified security constraints
    (network disabled, read-only root, memory/CPU limits). Optionally logs
    container output for debugging.

    Args:
        agent_cmd: The agent command and arguments to run inside the container.
        payload_str: Input to pass to the agent via stdin.
        config: Docker sandbox configuration.
        timeout: Timeout in seconds for the container execution.

    Returns:
        The completed process result with captured stdout and stderr.
    """
    docker_args = ["docker", "run", "--rm"]
    if config.network_disabled:
        docker_args.extend(["--network", "none"])
    if config.read_only_root:
        docker_args.extend(["--read-only"])
    if config.memory_limit:
        docker_args.extend(["--memory", config.memory_limit])
    if config.cpu_limit:
        docker_args.extend(["--cpus", str(config.cpu_limit)])
    # Map host.docker.internal to the host gateway on Linux when requested
    try:
        import platform as _pf
        _is_linux = (_pf.system() == "Linux")
    except Exception:
        _is_linux = False
    if config.add_host_gateway and _is_linux:
        docker_args.extend(["--add-host", "host.docker.internal:host-gateway"])
    # S108: tmpfs path is hardcoded and non-configurable — this is intentional
    # for the Docker sandbox to prevent accidental FS writes. The tmpfs is
    # ephemeral and limited to 64MB, so no realistic risk of filling /tmp.
    docker_args.extend(["--tmpfs", "/tmp:noexec,nosuid,size=64m"])  # noqa: S108
    docker_args.append(config.image)
    docker_args.extend(agent_cmd)

    started_ts = time.time()
    result = subprocess.run(  # noqa: S603
        docker_args,
        input=payload_str,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    finished_ts = time.time()

    # Optional logging of container interactions for test artifacts.
    # Controlled by the EVALFORGE_DOCKER_LOG_DIR environment variable.
    log_dir = os.environ.get("EVALFORGE_DOCKER_LOG_DIR")
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            entry_dir = os.path.join(
                log_dir,
                f"run-{int(started_ts*1000)}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
            )
            os.makedirs(entry_dir, exist_ok=True)
            with open(os.path.join(entry_dir, "stdout.txt"), "w", encoding="utf-8") as f_out:
                f_out.write(result.stdout or "")
            with open(os.path.join(entry_dir, "stderr.txt"), "w", encoding="utf-8") as f_err:
                f_err.write(result.stderr or "")
            meta = {
                "agent_cmd": agent_cmd,
                "payload_len": len(payload_str or ""),
                "docker_args": docker_args,
                "returncode": result.returncode,
                "started_ts": started_ts,
                "finished_ts": finished_ts,
                "duration_sec": finished_ts - started_ts,
                "config": {
                    "image": config.image,
                    "network_disabled": config.network_disabled,
                    "read_only_root": config.read_only_root,
                    "memory_limit": config.memory_limit,
                    "cpu_limit": config.cpu_limit,
                },
            }
            with open(os.path.join(entry_dir, "meta.json"), "w", encoding="utf-8") as f_meta:
                json.dump(meta, f_meta, indent=2)
        except Exception:  # noqa: S110
            # Logging should never break execution
            pass

    return result
