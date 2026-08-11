"""Integration tests for the CLI invoked as a real OS subprocess.

Uses subprocess.run([sys.executable, "-m", "evalforge", ...]) to verify the
actual CLI entry point, not click's in-process CliRunner. This catches
packaging, import-path, and entry-point issues that CliRunner would mask.

- P1.3. CLI End-to-End as Real OS Subprocess (#172)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"
ECHO_AGENT = Path(__file__).parent / "fixtures" / "echo_agent.py"
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**__import__("os").environ, "PYTHONPATH": str(SRC_DIR)}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "evalforge", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def test_cli_help() -> None:
    """evalforge --help prints usage and exits 0."""
    cp = _run_cli("--help")
    assert cp.returncode == 0, f"stderr: {cp.stderr}"
    assert "EvalForge" in cp.stdout
    assert "run" in cp.stdout
    assert "validate" in cp.stdout


def test_cli_validate(tmp_path: Path) -> None:
    """evalforge validate --pack --strict validates a scenario pack."""
    cp = _run_cli(
        "validate",
        "--pack", str(PACK_YAML),
        "--strict",
    )
    assert cp.returncode == 0, f"stderr: {cp.stderr}"
    assert "test-pack" in cp.stdout
    assert "2 scenarios" in cp.stdout


def test_cli_run_happy_path(tmp_path: Path) -> None:
    """evalforge run with a valid pack, subprocess echo agent, and mock judge."""
    echo_agent = f"{sys.executable} tests/fixtures/echo_agent.py"
    cp = _run_cli(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", f"subprocess:{echo_agent}",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
        "--timeout", "30",
    )
    assert cp.returncode == 0, f"stdout: {cp.stdout}\nstderr: {cp.stderr}"
    assert "Run complete" in cp.stdout
    assert "Exit code:" in cp.stdout


def test_cli_run_with_fixtures(tmp_path: Path) -> None:
    """evalforge run --fixtures flag enables deterministic fixture mode."""
    echo_agent = f"{sys.executable} tests/fixtures/echo_agent.py"
    cp = _run_cli(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", f"subprocess:{echo_agent}",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
        "--timeout", "30",
        "--fixtures",
    )
    assert cp.returncode == 0, f"stderr: {cp.stderr}"
    assert "Run complete" in cp.stdout


def test_cli_run_with_sandbox(tmp_path: Path) -> None:
    """evalforge run --sandbox flag enables sandboxed environment."""
    echo_agent = f"{sys.executable} tests/fixtures/echo_agent.py"
    cp = _run_cli(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", f"subprocess:{echo_agent}",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
        "--timeout", "30",
        "--sandbox",
    )
    assert cp.returncode == 0, f"stderr: {cp.stderr}"
    assert "Run complete" in cp.stdout


def test_cli_baseline_save_list(tmp_path: Path) -> None:
    """evalforge baseline save and list work with real run data."""
    echo_agent = f"{sys.executable} {ECHO_AGENT}"
    cwd = tmp_path / "project"
    cwd.mkdir()
    cp1 = _run_cli(
        "run", "--pack", str(PACK_YAML), "--agent", f"subprocess:{echo_agent}",
        "--judge", "mock", "--output", str(cwd / ".evalforge"),
        "--output-format", "json", "--timeout", "30", cwd=cwd,
    )
    assert cp1.returncode == 0, f"stderr: {cp1.stderr}"

    # Find the run directory created by the run command
    runs_dir = cwd / ".evalforge" / "runs"
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])
    assert len(run_dirs) >= 1, f"no run dirs in {runs_dir}"
    run_dir = run_dirs[-1]

    cp2 = _run_cli(
        "baseline", "save", "--name", "v1.0", "--run", str(run_dir),
        "--pack", str(PACK_YAML), cwd=cwd,
    )
    assert cp2.returncode == 0, f"stderr: {cp2.stderr}"
    cp3 = _run_cli("baseline", "list", cwd=cwd)
    assert cp3.returncode == 0, f"stderr: {cp3.stderr}"
    assert "v1.0" in cp3.stdout or "v1.0" in cp3.stderr


def test_cli_compare(tmp_path: Path) -> None:
    """evalforge compare between two runs produces correct output."""
    echo_agent = f"{sys.executable} {ECHO_AGENT}"
    cwd = tmp_path / "project"
    cwd.mkdir()
    # Run twice to get two run directories
    for _ in range(2):
        cp = _run_cli(
            "run", "--pack", str(PACK_YAML), "--agent", f"subprocess:{echo_agent}",
            "--judge", "mock", "--output", str(cwd / ".evalforge"),
            "--output-format", "json", "--timeout", "30", cwd=cwd,
        )
        assert cp.returncode == 0, f"stderr: {cp.stderr}"

    runs_dir = cwd / ".evalforge" / "runs"
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])
    assert len(run_dirs) >= 2, f"need at least 2 runs, got {len(run_dirs)}"

    # Save first run as baseline
    cp_save = _run_cli(
        "baseline", "save", "--name", "baseline-v1", "--run", str(run_dirs[0]),
        "--pack", str(PACK_YAML), cwd=cwd,
    )
    assert cp_save.returncode == 0, f"stderr: {cp_save.stderr}"

    # Compare second run against baseline
    cp_comp = _run_cli(
        "compare", "--candidate", str(run_dirs[-1]), "--baseline", "baseline-v1",
        "--pack", str(PACK_YAML), cwd=cwd,
    )
    assert cp_comp.returncode == 0, f"stderr: {cp_comp.stderr}"
