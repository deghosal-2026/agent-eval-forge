"""Integration tests for Docker-based container execution.

Each test creates a fresh Docker container via ``run_in_container`` and
verifies that the enforcement flags defined in ``DockerConfig`` are respected
at the container level. Uses the project's ``evalforge-agent-runner`` image
which has all extras pre-installed and scenario packs embedded.

No platform guards — tests run in Linux containers via Docker Desktop
regardless of host OS. If Docker isn't running, the test fails (not skips).
"""

from __future__ import annotations

import os
import subprocess

import pytest

from evalforge.security.sandbox import DockerConfig, run_in_container

pytestmark = [pytest.mark.docker]

DOCKER_IMAGE = os.environ.get("EVALFORGE_DOCKER_IMAGE", "evalforge-agent-runner")


def _docker_available() -> bool:
    try:
        subprocess.run(  # noqa: S603
            ["docker", "info"],  # noqa: S607
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except Exception:
        return False


def _docker_image_exists(image: str) -> bool:
    try:
        subprocess.run(  # noqa: S603
            ["docker", "image", "inspect", image],  # noqa: S607
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def require_docker() -> None:
    if not _docker_available():
        pytest.fail("Docker daemon is not running — start Docker Desktop and retry")


@pytest.fixture(autouse=True)
def ensure_image() -> None:
    """Require the prebuilt Docker image; never build implicitly in tests."""
    if not _docker_image_exists(DOCKER_IMAGE):
        pytest.fail(
            f"Required Docker image '{DOCKER_IMAGE}' not found. "
            "Build or load it explicitly before running docker tests."
        )


class TestContainerExecution:
    """Verify basic container execution through run_in_container."""

    def test_echo_agent_in_container(self) -> None:
        config = DockerConfig(image=DOCKER_IMAGE)
        result = run_in_container(["echo", "hello-from-docker"], "", config, timeout=30.0)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello-from-docker"

    def test_network_isolation(self) -> None:
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
        assert result.returncode != 0
        err = (result.stderr or "").lower()
        indicators = [
            "timeout", "timed out", "refused", "unreachable",
            "no route", "denied", "forbidden", "blocked", "network is unreachable",
        ]
        assert any(tok in err for tok in indicators), f"unexpected stderr: {result.stderr}"

    def test_readonly_filesystem(self) -> None:
        config = DockerConfig(image=DOCKER_IMAGE, read_only_root=True)
        result = run_in_container(["touch", "/test-write"], "", config, timeout=15.0)
        assert result.returncode != 0
        assert "Read-only file system" in result.stderr

    def test_resource_limits(self) -> None:
        config = DockerConfig(image=DOCKER_IMAGE, cpu_limit=0.5, memory_limit="64m")
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
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "cpu_quota=50000" in result.stdout, f"stdout: {result.stdout}"
        assert "mem_max=67108864" in result.stdout, f"stdout: {result.stdout}"

    def test_startup_failure(self) -> None:
        config = DockerConfig(image=DOCKER_IMAGE)
        result = run_in_container(["nonexistent-command-xyz"], "", config, timeout=15.0)
        assert result.returncode != 0

    def test_timeout(self) -> None:
        config = DockerConfig(image=DOCKER_IMAGE)
        with pytest.raises(subprocess.TimeoutExpired):
            run_in_container(["sleep", "60"], "", config, timeout=2.0)
