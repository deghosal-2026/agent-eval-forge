"""Tests for ``evalforge init`` scaffolding command."""

from __future__ import annotations

import tomllib
from pathlib import Path

from click.testing import CliRunner

from evalforge.cli.__main__ import main


def _invoke(*args: str) -> tuple[int, str]:
    runner = CliRunner()
    result = runner.invoke(main, list(args))
    return result.exit_code, result.output.strip()


def _files_in(root: Path) -> set[str]:
    rel: set[str] = set()
    for p in root.rglob("*"):
        if p.is_file():
            rel.add(str(p.relative_to(root)))
    return rel


# ------------------------------------------------------------------
# Minimal template
# ------------------------------------------------------------------


def test_minimal_creates_expected_files(tmp_path: Path) -> None:
    code, out = _invoke("init", str(tmp_path))
    assert code == 0, f"init failed: {out}"

    files = _files_in(tmp_path)
    assert "evalforge.toml" in files
    assert "scenarios/my-scenarios.yaml" in files


def test_minimal_does_not_create_full_files(tmp_path: Path) -> None:
    code, out = _invoke("init", str(tmp_path))
    assert code == 0, f"init failed: {out}"

    files = _files_in(tmp_path)
    assert "agents/my_agent.py" not in files
    assert "tests/test_scenarios.py" not in files


def test_minimal_creates_valid_toml(tmp_path: Path) -> None:
    code, out = _invoke("init", str(tmp_path))
    assert code == 0, f"init failed: {out}"

    toml_path = tmp_path / "evalforge.toml"
    assert toml_path.exists()
    data = tomllib.loads(toml_path.read_text())
    assert "judge" in data
    assert "output" in data
    assert "scoring" in data


# ------------------------------------------------------------------
# Full template
# ------------------------------------------------------------------


def test_full_creates_expected_files(tmp_path: Path) -> None:
    code, out = _invoke("init", str(tmp_path), "--template", "full")
    assert code == 0, f"init failed: {out}"

    files = _files_in(tmp_path)
    assert "evalforge.toml" in files
    assert "scenarios/my-scenarios.yaml" in files
    assert "agents/my_agent.py" in files
    assert "tests/test_scenarios.py" in files
    assert (tmp_path / "fixtures").is_dir()


def test_full_agent_has_run_function(tmp_path: Path) -> None:
    code, out = _invoke("init", str(tmp_path), "--template", "full")
    assert code == 0, f"init failed: {out}"

    agent_path = tmp_path / "agents" / "my_agent.py"
    content = agent_path.read_text()
    assert "def run(" in content


# ------------------------------------------------------------------
# Force overwrite
# ------------------------------------------------------------------


def test_force_overwrites_existing(tmp_path: Path) -> None:
    # First, create with minimal template
    code, _out = _invoke("init", str(tmp_path))
    assert code == 0

    toml_path = tmp_path / "evalforge.toml"
    original = toml_path.read_text()

    # Modify the file so we can detect overwrite
    toml_path.write_text("# changed content")
    assert toml_path.read_text() == "# changed content"

    # Re-run with --force
    code, _out = _invoke("init", str(tmp_path), "--force")
    assert code == 0

    # File should be back to the original template content
    assert toml_path.read_text() == original


def test_minimal_pack_is_valid_yaml(tmp_path: Path) -> None:
    import yaml  # type: ignore[import-untyped]

    code, _out = _invoke("init", str(tmp_path))
    assert code == 0

    pack_path = tmp_path / "scenarios" / "my-scenarios.yaml"
    data = yaml.safe_load(pack_path.read_text())
    assert data["pack"]["name"] == "my-scenarios"
    assert len(data["scenarios"]) >= 1
    scenario = data["scenarios"][0]
    assert "id" in scenario
    assert "title" in scenario
    assert "input" in scenario
    assert "expected" in scenario
    assert "metrics" in scenario


def test_skips_existing_without_force(tmp_path: Path) -> None:
    # Create a file that will conflict
    (tmp_path / "evalforge.toml").write_text("# custom")
    code, out = _invoke("init", str(tmp_path))
    assert code == 0
    assert "Skipped" in out
    assert (tmp_path / "evalforge.toml").read_text() == "# custom"


def test_default_path_is_cwd(tmp_path: Path) -> None:
    import os

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        code, _out = _invoke("init")
        assert code == 0
        assert (tmp_path / "evalforge.toml").exists()
    finally:
        os.chdir(cwd)
