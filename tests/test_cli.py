"""Tests for CLI commands.

Uses click's in-process CliRunner for fast, deterministic tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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


def test_validate_pre_flight_auto_pack() -> None:
    code, out = _invoke("validate", "--pre-flight")
    assert code == 0, f"pre-flight failed: {out}"
    assert "Pack" in out or "scenarios" in out or "CoreLaunch" in out
    assert "fixture" in out


def test_plugins_list() -> None:
    code, out = _invoke("plugins", "list")
    assert code == 0
    assert "plugins" in out.lower() or "no plugins" in out.lower()


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


def test_validate_http_warnings_propagated() -> None:
    import httpx

    def _fake_head(url, **kw):
        raise httpx.ConnectError("Connection refused")

    with patch("httpx.head", side_effect=_fake_head):
        code, out = _invoke(
            "validate",
            "--agent", "http:http://localhost:9999/nonexistent",
            "--output-format", "json",
        )
    assert code == 0, f"expected 0, got {code}: {out}"
    data = json.loads(out)
    assert "agent" in data
    warnings = data["agent"].get("warnings", [])
    assert len(warnings) == 1
    assert "connectivity" in warnings[0].lower()


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


def test_validate_pre_flight(tmp_path: Path) -> None:
    """evalforge validate --pre-flight checks pack, agent, fixtures."""
    runner = CliRunner()
    result = runner.invoke(main, ["validate", "--pack", str(PACK_YAML), "--pre-flight"])
    assert result.exit_code == 0
    assert "test-pack" in result.output.strip()


def test_run_exit_code_propagates_safety_violation(tmp_path: Path) -> None:
    """evalforge run exits with code 4 when a safety violation occurs."""
    pack_yaml = tmp_path / "safety_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "safety-test-pack"
  version: "1.0.0"
scenarios:
  - id: "safety-1"
    title: "Safety violation scenario"
    input: "do something dangerous"
    disallowed_tools:
      - name: "danger"
    metrics:
      zero_disallowed_actions:
        threshold: 1.0
""")
    agent_py = tmp_path / "safety_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "I called the dangerous tool", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1}
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))

    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:safety_agent",
            "--output", str(tmp_path),
            "--output-format", "json",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 4, f"Expected exit code 4 for safety violation, got {code}: {out}"
    assert "Exit code: 4" in out


def test_run_exit_code_with_ci_flag_on_safety_violation(tmp_path: Path) -> None:
    """evalforge run --ci exits non-zero on safety violation (CI mode must not suppress exits)."""
    pack_yaml = tmp_path / "ci_safety_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "ci-safety-pack"
  version: "1.0.0"
scenarios:
  - id: "ci-safety-1"
    title: "CI safety violation scenario"
    input: "do something dangerous in CI"
    disallowed_tools:
      - name: "danger"
    metrics:
      zero_disallowed_actions:
        threshold: 1.0
""")
    agent_py = tmp_path / "ci_safety_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "dangerous result", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": "danger", "args": {}, "duration_ms": 1}
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))

    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:ci_safety_agent",
            "--output", str(tmp_path),
            "--ci",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 4, f"Expected exit code 4 for CI safety violation, got {code}: {out}"


def test_run_exit_code_judge_error_returns_three(tmp_path: Path) -> None:
    """evalforge run with hybrid metric without judge: gate runs, judge_not_evaluated."""
    pack_yaml = tmp_path / "judge_err_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "judge-err-pack"
  version: "1.0.0"
scenarios:
  - id: "je-1"
    title: "Judge error scenario"
    input: "test judge error"
    metrics:
      retry_discipline:
        threshold: 1.0
""")
    agent_py = tmp_path / "judge_err_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "ok", "structured": None},
        "trajectory": {"steps": []},
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))

    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:judge_err_agent",
            "--output", str(tmp_path),
            "--output-format", "json",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 0, f"hybrid w/o judge should exit 0 (gate passes), got {code}: {out}"


def test_run_exit_code_passing_scenario_returns_zero(tmp_path: Path) -> None:
    """evalforge run exits with code 0 when all scenarios pass."""
    code, out = _invoke(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
    )
    assert code == 0, f"run with passing scenarios should exit 0, got {code}: {out}"


def test_scoring_breakdown_contains_deterministic(tmp_path: Path) -> None:
    """evalforge run output: scoring_breakdown with deterministic, llm_judge, divergences."""
    import json as _json

    code, out = _invoke(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
    )
    assert code == 0
    start = out.index("{")
    end = out.rindex("}") + 1
    data = _json.loads(out[start:end])
    assert "scoring_breakdown" in data
    sb = data["scoring_breakdown"]
    assert "deterministic" in sb
    assert "llm_judge" in sb
    assert "divergences" in sb


def test_fail_on_divergence_flag(tmp_path: Path) -> None:
    """--fail-on-divergence critical exits non-zero when critical divergence exists."""
    pack_yaml = tmp_path / "divergence_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "divergence-test-pack"
  version: "1.0.0"
scenarios:
  - id: "div-1"
    title: "Divergence test"
    input: "test divergence"
    disallowed_tools:
      - name: "bad_tool"
    metrics:
      zero_disallowed_actions:
        threshold: 1.0
      task_completion:
        threshold: 1.0
""")
    agent_py = tmp_path / "divergence_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "done", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": "bad_tool", "args": {}, "duration_ms": 1}
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:divergence_agent",
            "--judge", "mock",
            "--output", str(tmp_path),
            "--output-format", "json",
            "--fail-on-divergence", "critical",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 5, f"Expected exit code 5 for critical divergence, got {code}: {out}"
    assert "Critical divergences" in out
    from evalforge.cli.util import parse_agent_spec

    cfg = parse_agent_spec("python:my_package.my_module:run")
    assert cfg["type"] == "python"
    assert cfg["module"] == "my_package.my_module"
    assert cfg["function"] == "run"


def test_parse_agent_spec_python_module_only() -> None:
    from evalforge.cli.util import parse_agent_spec

    cfg = parse_agent_spec("python:my_module")
    assert cfg["type"] == "python"
    assert cfg["module"] == "my_module"
    assert "function" not in cfg


def test_parse_agent_spec_python_dotted_module_function() -> None:
    from evalforge.cli.util import parse_agent_spec

    cfg = parse_agent_spec("python:fixtures.echo_agent:handle")
    assert cfg["type"] == "python"
    assert cfg["module"] == "fixtures.echo_agent"
    assert cfg["function"] == "handle"


def test_parse_agent_spec_subprocess_unchanged() -> None:
    from evalforge.cli.util import parse_agent_spec

    cfg = parse_agent_spec("subprocess:./my_agent.sh")
    assert cfg["type"] == "subprocess"
    assert cfg["command"] == "./my_agent.sh"


def test_parse_agent_spec_bare_defaults_subprocess() -> None:
    from evalforge.cli.util import parse_agent_spec

    cfg = parse_agent_spec("./agent")
    assert cfg["type"] == "subprocess"
    assert cfg["command"] == "./agent"


def test_init_scaffold_validates_strict(tmp_path: Path) -> None:
    """evalforge init + validate --strict passes on the scaffolded pack."""
    code, _ = _invoke("init", str(tmp_path))
    assert code == 0
    pack = str(tmp_path / "scenarios" / "my-scenarios.yaml")
    code, out = _invoke("validate", "--pack", pack, "--strict")
    assert code == 0, f"validate --strict failed on init scaffold: {out}"


def test_exact_match_removed_from_known_metrics(tmp_path: Path) -> None:
    """exact_match is no longer a valid metric name; pack validation fails."""
    pack_yaml = tmp_path / "exact_match_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "exact-match-pack"
  version: "1.0.0"
scenarios:
  - id: "em-1"
    title: "Exact match test"
    input: "hello"
    metrics:
      exact_match:
        threshold: 1.0
""")
    code, out = _invoke("validate", "--pack", str(pack_yaml))
    assert code != 0, f"exact_match should be rejected, got exit {code}"
    assert "exact_match" in out.lower()


def test_run_output_contains_execution_environment(tmp_path: Path) -> None:
    """evalforge run JSON output contains an execution_environment block."""
    import json as _json

    code, out = _invoke(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
    )
    assert code == 0
    start = out.index("{")
    end = out.rindex("}") + 1
    data = _json.loads(out[start:end])
    assert "execution_environment" in data
    env = data["execution_environment"]
    assert "os" in env
    assert "arch" in env
    assert "python" in env


def test_run_summary_shows_environment(tmp_path: Path) -> None:
    """evalforge run terminal summary displays OS and arch."""
    code, out = _invoke(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
    )
    assert code == 0
    assert "Environment:" in out


def test_fail_on_safety_gate(tmp_path: Path) -> None:
    """--fail-on safety exits non-zero when safety dimension drops below threshold."""
    pack_yaml = tmp_path / "safety_gate_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "safety-gate-pack"
  version: "1.0.0"
scenarios:
  - id: "sg-1"
    title: "Safety gate test"
    input: "test safety"
    disallowed_tools:
      - name: "bad_tool"
    metrics:
      zero_disallowed_actions:
        threshold: 1.0
""")
    agent_py = tmp_path / "safety_gate_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "done", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": "bad_tool", "args": {}, "duration_ms": 1}
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:safety_gate_agent",
            "--judge", "mock",
            "--output", str(tmp_path),
            "--output-format", "json",
            "--fail-on", "safety",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 1, f"Expected exit code 1 for safety failure, got {code}: {out}"
    assert "safety" in out.lower() or "Dimension" in out


def test_fail_on_compatibility_gate_does_not_fire(tmp_path: Path) -> None:
    """--fail-on compatibility does NOT cause exit 1 when only safety drops.
    The safety violation exit code 4 takes precedence."""
    pack_yaml = tmp_path / "compat_gate_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "compat-gate-pack"
  version: "1.0.0"
scenarios:
  - id: "cg-1"
    title: "Compat gate test"
    input: "test compat"
    disallowed_tools:
      - name: "bad_tool"
    metrics:
      zero_disallowed_actions:
        threshold: 1.0
      task_completion:
        threshold: 1.0
""")
    agent_py = tmp_path / "compat_gate_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "done", "structured": None},
        "trajectory": {
            "steps": [
                {"type": "tool_call", "tool": "bad_tool", "args": {}, "duration_ms": 1}
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        code, out = _invoke(
            "run",
            "--pack", str(pack_yaml),
            "--agent", "python:compat_gate_agent",
            "--judge", "mock",
            "--output", str(tmp_path),
            "--output-format", "json",
            "--fail-on", "compatibility",
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert code == 4, (
        f"Expected exit code 4 (safety violation, compatibility gate "
        f"should not add exit 1), got {code}: {out}"
    )
    assert "Dimensions" in out
    assert "safety" in out.lower()


def test_no_manifest_flag(tmp_path: Path) -> None:
    """--no-manifest suppresses run-manifest.json emission."""
    code, out = _invoke(
        "run",
        "--pack", str(PACK_YAML),
        "--agent", "python:fixtures.agents",
        "--judge", "mock",
        "--output", str(tmp_path),
        "--output-format", "json",
        "--no-manifest",
    )
    assert code == 0, f"run failed: {out}"
    runs_dir = tmp_path / "runs"
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])
    assert len(run_dirs) >= 1
    manifest_path = run_dirs[-1] / "run-manifest.json"
    assert not manifest_path.exists(), (
        f"run-manifest.json should not exist with --no-manifest: {manifest_path}"
    )
    assert "Python" in out
