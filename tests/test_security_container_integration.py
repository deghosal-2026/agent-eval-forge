"""Integration tests for Docker-based container execution.

These tests require:
- A working Docker installation
- Linux platform (Docker isolation behavior differs on macOS)

Each test creates a fresh Docker container via ``run_in_container`` and
verifies that the enforcement flags defined in ``DockerConfig`` are respected
at the container level. Uses the project's ``evalforge-agent-runner`` image
which has all extras pre-installed and scenario packs embedded.

Skip the file with::

    pytest -m "not docker"
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

import pytest

from evalforge.security.sandbox import DockerConfig, run_in_container

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not shutil.which("docker"), reason="docker not available"),
    pytest.mark.skipif(
        bool(os.environ.get("CI")) and platform.system() != "Linux",
        reason="Docker isolation tests require Linux in CI",
    ),
]

DOCKER_IMAGE = os.environ.get("EVALFORGE_DOCKER_IMAGE", "evalforge-agent-runner")


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(autouse=True)
def require_docker() -> None:
    if not _docker_available():
        pytest.skip("Docker daemon is not running or not accessible")


class TestContainerExecution:
    """Verify basic container execution through run_in_container."""

    def test_echo_agent_in_container(self) -> None:
        """Run echo inside a container and verify the output is captured."""
        config = DockerConfig(image=DOCKER_IMAGE)
        result = run_in_container(["echo", "hello-from-docker"], "", config, timeout=30.0)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello-from-docker"

    def test_network_isolation(self) -> None:
        """Verify that --network none blocks internet access inside the container."""
        config = DockerConfig(image=DOCKER_IMAGE, network_disabled=True)
        result = run_in_container(
            [
                "python", "-c",
                "import socket; s=socket.socket(); s.settimeout(3); s.connect(('8.8.8.8', 53))",
            ],
            "",
            config,
            timeout=15.0,
        )
        # Connection should fail — network is blocked
        assert result.returncode != 0
        assert "timeout" in result.stderr.lower() or "refused" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_readonly_filesystem(self) -> None:
        """Verify that --read-only prevents writes to the container filesystem."""
        config = DockerConfig(image=DOCKER_IMAGE, read_only_root=True)
        result = run_in_container(
            ["touch", "/test-write"],
            "",
            config,
            timeout=15.0,
        )
        assert result.returncode != 0
        assert "Read-only file system" in result.stderr

    def test_resource_limits(self) -> None:
        """Verify --cpus and --memory limits are enforced, read from cgroup."""
        config = DockerConfig(
            image=DOCKER_IMAGE,
            cpu_limit=0.5,
            memory_limit="64m",
        )
        result = run_in_container(
            [
                "python", "-c",
                (
                    "import pathlib; "
                    "cpu = pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().strip().split(); "
                    "mem = pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip(); "
                    "print(f'cpu_quota={cpu[0]},mem_max={mem}')"
                ),
            ],
            "",
            config,
            timeout=15.0,
        )
        assert result.returncode == 0
        # CPU quota: 0.5 cores = 50000 out of 100000 period
        assert "cpu_quota=50000" in result.stdout
        # Memory limit: 64m ≈ 67108864 bytes
        assert "mem_max=67108864" in result.stdout

    def test_startup_failure(self) -> None:
        """A nonexistent command inside the container should fail."""
        config = DockerConfig(image=DOCKER_IMAGE)
        # run_in_container uses docker run which will fail for nonexistent cmd
        result = run_in_container(
            ["nonexistent-command-xyz"],
            "",
            config,
            timeout=15.0,
        )
        assert result.returncode != 0

    def test_timeout(self) -> None:
        """A long-running command should hit the configured timeout."""
        config = DockerConfig(image=DOCKER_IMAGE)
        with pytest.raises(subprocess.TimeoutExpired):
            run_in_container(
                ["sleep", "60"],
                "",
                config,
                timeout=2.0,
            )