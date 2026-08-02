from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

DOCKER_IMAGE = "evalforge-test"


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _build_context() -> Path:
    return Path(__file__).parent.parent


def _run_container(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "run", "--rm", DOCKER_IMAGE, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(scope="module")
def docker_image() -> Generator[None, None, None]:
    if not _docker_available():
        pytest.skip("docker not available")

    result = subprocess.run(
        ["docker", "build", "-t", DOCKER_IMAGE, "-f", "Dockerfile", "."],
        cwd=_build_context(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        pytest.fail(f"docker build failed:\n{result.stderr}")

    yield

    subprocess.run(
        ["docker", "rmi", "-f", DOCKER_IMAGE],
        capture_output=True,
        timeout=30,
    )


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_help(docker_image: None) -> None:
    result = _run_container("--help")
    assert result.returncode == 0, result.stderr
    assert "EvalForge" in result.stdout
    assert "run" in result.stdout
    assert "validate" in result.stdout


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_version(docker_image: None) -> None:
    from evalforge import __version__

    result = _run_container("version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_validate_pack(docker_image: None) -> None:
    result = _run_container("validate", "--pack", "scenarios/core-launch.yaml")
    assert result.returncode == 0, f"validate failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert "scenarios" in result.stdout.lower()


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_validate_pack_strict(docker_image: None) -> None:
    result = _run_container("validate", "--pack", "scenarios/core-launch.yaml", "--strict")
    assert result.returncode == 0, f"validate strict failed:\nstdout={result.stdout}\nstderr={result.stderr}"
