"""Tests for the EvalForge pytest plugin and test CLI command."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import evalforge.pytest_plugin  # noqa: F401 — ensures plugin loads

pytest_plugins = ["evalforge.pytest_plugin"]

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


@pytest.mark.evalforge(pack=str(PACK_YAML))
def test_plugin_parametrize_scenarios(scenario: object) -> None:
    """@pytest.mark.evalforge(pack=...) parametrizes over scenarios."""
    from evalforge.models.pack import Scenario

    assert isinstance(scenario, Scenario)
    assert scenario.id


@pytest.mark.evalforge(pack=str(PACK_YAML))
@pytest.mark.evalforge_tags("tag-a")
def test_plugin_tags_marker_filters(scenario: object) -> None:
    """@pytest.mark.evalforge_tags filters parametrized scenarios."""
    from evalforge.models.pack import Scenario

    assert isinstance(scenario, Scenario)
    assert "tag-a" in scenario.tags


def test_plugin_agent_config_skips_without_opts() -> None:
    """agent_config fixture skips when no --evalforge-agent is provided."""
    code = subprocess.call(  # noqa: S603
        [
            sys.executable, "-m", "pytest",
            "-c", str(Path(__file__).parent.parent / "pyproject.toml"),
            "-p", "evalforge.pytest_plugin",
            "--no-header",
            "-q",
            str(Path(__file__).parent / "fixtures" / "pytest_skip_agent.py"),
        ],
        cwd=Path(__file__).parent.parent,
    )
    assert code == 0  # skip is a pass in pytest


def test_plugin_pack_skips_without_opts() -> None:
    """scenario_pack fixture skips when no --evalforge-pack is provided."""
    code = subprocess.call(  # noqa: S603
        [
            sys.executable, "-m", "pytest",
            "-c", str(Path(__file__).parent.parent / "pyproject.toml"),
            "-p", "evalforge.pytest_plugin",
            "--no-header",
            "-q",
            str(Path(__file__).parent / "fixtures" / "pytest_skip_pack.py"),
        ],
        cwd=Path(__file__).parent.parent,
    )
    assert code == 0


def test_plugin_fixtures_resolve_with_cli_opts() -> None:
    """Fixtures resolve when CLI options are provided."""
    code = subprocess.call(  # noqa: S603
        [
            sys.executable, "-m", "pytest",
            "-c", str(Path(__file__).parent.parent / "pyproject.toml"),
            "-p", "evalforge.pytest_plugin",
            "--no-header",
            "-q",
            f"--evalforge-pack={PACK_YAML}",
            "--evalforge-agent=python:fixtures.agents",
            str(Path(__file__).parent / "fixtures" / "pytest_resolve.py"),
        ],
        cwd=Path(__file__).parent.parent,
    )
    assert code == 0


def test_cli_test_run_with_mock_agent(tmp_path: Path) -> None:
    """evalforge test run discovers and runs scenarios with mock agent."""
    from click.testing import CliRunner

    from evalforge.cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "test", "run",
            "--scenarios-dir", str(SCENARIOS_DIR),
            "--agent", "python:fixtures.agents",
            "--judge", "mock",
            "--output", str(tmp_path),
            "--output-format", "json",
        ],
    )
    assert result.exit_code == 0, f"test run failed: {result.output}"
    assert "Test run complete" in result.output
    report_json = tmp_path / "test-report.json"
    assert report_json.exists()
    data = json.loads(report_json.read_text())
    assert data["packs"] >= 1
    assert data["total_scenarios"] > 0


def test_cli_test_run_empty_directory(tmp_path: Path) -> None:
    """evalforge test run fails gracefully with no packs found."""
    from click.testing import CliRunner

    from evalforge.cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "test", "run",
            "--scenarios-dir", str(tmp_path),
            "--agent", "python:fixtures.agents",
            "--judge", "mock",
            "--output", str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "No scenario packs found" in result.output


def test_cli_test_run_help() -> None:
    """evalforge test run --help displays usage."""
    from click.testing import CliRunner

    from evalforge.cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["test", "run", "--help"])
    assert result.exit_code == 0
    assert "--scenarios-dir" in result.output
    assert "--agent" in result.output
    assert "--output-format" in result.output


def test_output_formatter_github_actions_run(tmp_path: Path) -> None:
    """GitHub Actions output format produces expected sections."""
    from evalforge.cli.formatter import OutputFormatter

    formatter = OutputFormatter("github-actions")
    result = {
        "run_id": "run-test-001",
        "pack_name": "test-pack",
        "pack_version": "1.0.0",
        "total_scenarios": 5,
        "passed": 4,
        "warned": 0,
        "failed": 1,
        "exit_code": 1,
        "duration_ms": 1234,
        "safety_violations": [],
    }
    output = formatter.format_run_result(result)
    assert output is not None
    assert "EvalForge Run Results" in output
    assert "✅ Passed" in output
    assert "❌ Failed" in output


def test_output_formatter_github_actions_comparison() -> None:
    """GitHub Actions output for comparison report."""

    from evalforge.cli.formatter import OutputFormatter
    from evalforge.comparison.engine import ComparisonResult
    from evalforge.comparison.report import ComparisonReport
    from evalforge.scoring.result import RunScore

    formatter = OutputFormatter("github-actions")
    comp_result = ComparisonResult(
        scenario_deltas={},
        family_deltas={},
        aggregate={
            "total_scenarios": 5,
            "regressed": 1,
            "improved": 2,
            "new_failures": 0,
            "new_passes": 1,
            "unchanged": 3,
            "overall_score_delta": -0.05,
        },
    )
    candidate_score = RunScore(
        scenario_scores={},
        totals={"passed": 0, "warned": 0, "failed": 0},
        safety_violations=[],
        exit_code=1,
    )
    report = ComparisonReport(
        baseline_name="v1.0.0",
        candidate_name="run-test-001",
        result=comp_result,
        candidate_score=candidate_score,
    )
    output = formatter.format_comparison(report)
    assert output is not None
    assert "EvalForge Comparison Report" in output
    assert "regressed" in output.lower()


def test_output_formatter_github_actions_validation() -> None:
    """GitHub Actions output for validation results."""
    from evalforge.cli.formatter import OutputFormatter

    formatter = OutputFormatter("github-actions")
    results = {
        "pack": {"valid": True, "message": "Pack loaded"},
        "agent": {"valid": True, "message": "Adapter created"},
    }
    output = formatter.format_validation(results)
    assert output is not None
    assert "EvalForge Validation Results" in output


def test_output_formatter_github_actions_test_result() -> None:
    """GitHub Actions output for multi-pack test results."""
    from evalforge.cli.formatter import OutputFormatter

    formatter = OutputFormatter("github-actions")
    summary = {
        "packs": 2,
        "total_scenarios": 10,
        "passed": 8,
        "warned": 1,
        "failed": 1,
        "duration_ms": 5000,
        "safety_violations": [],
    }
    output = formatter.format_test_result(summary)
    assert output is not None
    assert "EvalForge Test Run Results" in output
