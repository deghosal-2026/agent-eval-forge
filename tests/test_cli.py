"""Tests for CLI commands.

Uses click's in-process CliRunner for fast, deterministic tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from evalforge.cli.__main__ import main

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"


def _invoke(*args: str) -> tuple[int, str]:
    runner = CliRunner()
    result = runner.invoke(main, list(args))
    return result.exit_code, result.output.strip()


def test_version() -> None:
    code, out = _invoke("version")
    assert code == 0
    assert out == "0.1.0"


def test_help() -> None:
    code, out = _invoke("--help")
    assert code == 0
    assert "EvalForge" in out
    assert "run" in out
    assert "validate" in out
    assert "compare" in out
    assert "baseline" in out
    assert "cache" in out
    assert "plugins" in out


def test_run_help() -> None:
    code, out = _invoke("run", "--help")
    assert code == 0
    assert "--pack" in out
    assert "--agent" in out
    assert "--judge" in out
    assert "--ci" in out


def test_run_with_mock_agent(tmp_path: Path) -> None:
    pack_str = str(PACK_YAML)
    code, out = _invoke(
        "run",
        "--pack", pack_str,
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
    )
    assert code == 0, f"run failed: {out}"
    assert "Run complete" in out
    assert "Exit code: 0" in out
    scores_file = tmp_path / "runs"
    run_dirs = list(scores_file.iterdir())
    assert len(run_dirs) == 1
    scores_json = run_dirs[0] / "scores.json"
    assert scores_json.exists()
    data = json.loads(scores_json.read_text())
    assert data["exit_code"] == 0
    assert data["total_scenarios"] > 0


def test_run_with_tags(tmp_path: Path) -> None:
    pack_str = str(PACK_YAML)
    code, out = _invoke(
        "run",
        "--pack", pack_str,
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
        "--tags", "tag-a",
    )
    assert code == 0, f"run failed: {out}"


def test_validate_pack() -> None:
    pack_str = str(PACK_YAML)
    code, out = _invoke("validate", "--pack", pack_str)
    assert code == 0, f"validate failed: {out}"
    assert "2 scenarios" in out


def test_validate_missing_pack() -> None:
    code, _ = _invoke("validate", "--pack", "/nonexistent/pack.yaml")
    assert code == 2


def test_validate_agent() -> None:
    code, out = _invoke("validate", "--agent", "python:fixtures.agents")
    assert code == 0, f"validate agent failed: {out}"
    assert "Adapter" in out


def test_validate_bad_agent() -> None:
    code, _ = _invoke("validate", "--agent", "python:does.not.exist")
    assert code == 1


def test_validate_fixtures() -> None:
    pack_str = str(PACK_YAML)
    code, out = _invoke("validate", "--pack", pack_str, "--check-fixtures")
    assert code == 0, f"validate fixtures failed: {out}"


def test_plugins_list() -> None:
    code, out = _invoke("plugins")
    assert code == 0
    assert "Registered Scorers" in out


def test_cache_clear(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir(parents=True)
    (tmp_path / "runs" / "run-test").touch()
    code, out = _invoke("cache", "clear", "--output-dir", str(tmp_path))
    assert code == 0
    assert "Cleared" in out


def test_baseline_save_list_validate(tmp_path: Path) -> None:
    pack_str = str(PACK_YAML)
    run_dir = tmp_path / "runs" / "run-test-save"
    artifact_dir = run_dir / "artifacts"
    artifact_dir.mkdir(parents=True)

    artifact = {
        "id": "run-test-artifact",
        "scenario_id": "sc-1",
        "agent": {},
        "timestamp": {
            "start": "2026-01-01T00:00:00",
            "end": "2026-01-01T00:00:01",
            "duration_ms": 1000,
        },
        "output": {"final": "test output", "structured": None},
        "trajectory": [],
        "cost": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        "status": "completed",
        "error": None,
    }
    (artifact_dir / "sc-1.json").write_text(json.dumps(artifact))

    code, out = _invoke(
        "baseline", "save",
        "--name", "test-v1",
        "--run", str(run_dir),
        "--pack", pack_str,
        "--output-dir", str(tmp_path),
    )
    assert code == 0, f"save failed: {out}"
    assert "saved" in out

    code, out = _invoke(
        "baseline", "list",
        "--output-dir", str(tmp_path),
    )
    assert code == 0
    assert "test-v1" in out

    code, out = _invoke(
        "baseline", "validate",
        "--baseline", "test-v1",
        "--pack", pack_str,
        "--output-dir", str(tmp_path),
    )
    assert code == 0
    assert "All checks passed" in out


def test_compare_no_run_dir(tmp_path: Path) -> None:
    pack_str = str(PACK_YAML)
    code, out = _invoke(
        "compare",
        "--candidate", str(tmp_path / "nonexistent"),
        "--baseline", "test-v1",
        "--pack", pack_str,
        "--output-dir", str(tmp_path),
    )
    assert code == 1
    assert "not found" in out
