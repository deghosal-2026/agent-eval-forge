import json
from pathlib import Path

import pytest

from evalforge.models.pack import PackMetadata, Scenario, ScenarioPack
from evalforge.runner import Runner, generate_run_id

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"


def _mode_runner(tmp_path: Path, mode: str, timeout_seconds: int = 10) -> Runner:
    """Build a Runner preloaded with a single mode-driven scenario."""
    scenario = Scenario(
        id="sc-1", title="Scenario one", input="input one", context={"mode": mode},
    )
    pack = ScenarioPack(
        pack=PackMetadata(name="test-pack", version="1.0.0"),
        scenarios=[scenario],
    )
    runner = Runner(
        agent_config={
            "type": "python",
            "module": "fixtures.agents",
            "timeout_seconds": timeout_seconds,
        },
        output_dir=tmp_path,
    )
    runner._pack = pack
    return runner


def test_generate_run_id_format() -> None:
    rid = generate_run_id()
    assert rid.startswith("run-")
    parts = rid.split("-")
    assert len(parts) == 4


def test_runner_load_pack() -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents"})
    pack = runner.load_pack(PACK_YAML)
    assert isinstance(pack, ScenarioPack)
    assert len(pack.scenarios) == 2


def test_runner_run_one_with_mock_python_agent(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10}
    )
    runner.load_pack(PACK_YAML)
    artifact = runner.run_one("sc-1", run_id="run-test-1")
    assert artifact.status == "completed"
    assert artifact.output.final == "py:input one"
    assert artifact.scenario_id == "sc-1"


def test_runner_run_one_unknown_scenario_raises() -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents"})
    runner.load_pack(PACK_YAML)
    with pytest.raises(ValueError, match="unknown scenario"):
        runner.run_one("nope")


def test_runner_run_all_saves_artifacts(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    artifacts = runner.run_all(run_id="run-test-all")
    assert len(artifacts) == 2

    run_dir = tmp_path / "runs" / "run-test-all"
    assert (run_dir / "run.json").exists()
    index = json.loads((run_dir / "run.json").read_text())
    assert index["run_id"] == "run-test-all"
    assert index["pack"]["name"] == "test-pack"
    assert set(index["scenario_ids"]) == {"sc-1", "sc-2"}

    for scenario in ("sc-1", "sc-2"):
        artifact_path = run_dir / "artifacts" / f"{scenario}.json"
        assert artifact_path.exists()
        artifact = json.loads(artifact_path.read_text())
        assert artifact["scenario_id"] == scenario


def test_runner_run_all_tag_filter(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    # valid_pack.yaml has no tags; a tag filter matching nothing yields no runs
    artifacts = runner.run_all(tags=["retrieval"], run_id="run-tag")
    assert artifacts == []


def test_runner_run_index_sanitizes_agent_config(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={
            "type": "python",
            "module": "fixtures.agents",
            "timeout_seconds": 10,
            "api_key": "super-secret",
        },
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(run_id="run-sanitize")

    index = json.loads((tmp_path / "runs" / "run-sanitize" / "run.json").read_text())
    assert "api_key" not in index["agent"]
    assert "super-secret" not in index["agent"].values()


def test_runner_run_index_records_selected_tags(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(tags=["retrieval"], run_id="run-tags")

    index = json.loads((tmp_path / "runs" / "run-tags" / "run.json").read_text())
    assert index["selected_tags"] == ["retrieval"]


def test_runner_run_index_has_timestamps(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(run_id="run-time")

    index = json.loads((tmp_path / "runs" / "run-time" / "run.json").read_text())
    assert "start" in index["timestamps"]
    assert "end" in index["timestamps"]
    assert "duration_ms" in index["timestamps"]


def test_runner_run_id_reuse_raises(tmp_path: Path) -> None:
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=tmp_path,
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(run_id="run-dup")
    with pytest.raises(ValueError, match="already exists"):
        runner.run_all(run_id="run-dup")


def test_runner_pack_property_before_load_raises() -> None:
    runner = Runner(agent_config={"type": "python", "module": "fixtures.agents"})
    with pytest.raises(RuntimeError, match="load_pack"):
        _ = runner.pack


def test_manifest_emitted_on_run(tmp_path: Path) -> None:
    """run-manifest.json is created alongside scenario results."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(run_id="manifest-test", emit_manifest=True)
    manifest_path = tmp_path / "runs" / "manifest-test" / "run-manifest.json"
    assert manifest_path.exists(), f"manifest not found at {manifest_path}"
    data = json.loads(manifest_path.read_text())
    assert "run_id" in data
    assert data["run_id"] == "manifest-test"
    assert "host" in data
    assert "os" in data["host"]
    assert "arch" in data["host"]
    assert "python" in data["host"]
    assert "agent" in data
    assert "execution" in data
    assert "duration_ms" in data["execution"]
    assert "tool_call_count" in data["execution"]


def test_manifest_suppressed_with_flag(tmp_path: Path) -> None:
    """--no-manifest equivalent suppresses run-manifest.json."""
    runner = Runner(
        agent_config={"type": "python", "module": "fixtures.agents", "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack(PACK_YAML)
    runner.run_all(run_id="manifest-suppressed", emit_manifest=False)
    manifest_path = tmp_path / "runs" / "manifest-suppressed" / "run-manifest.json"
    assert not manifest_path.exists()


def test_manifest_model_contains_all_fields() -> None:
    """RunManifest model serializes correctly with all required fields."""
    from evalforge.models.manifest import RunManifest, collect_host_info

    host = collect_host_info()
    manifest = RunManifest(
        run_id="test-123",
        host=host,
        agent={"type": "python", "module": "test"},
        execution={"duration_ms": 100, "tool_call_count": 5, "scenario_count": 1},
    )
    data = json.loads(manifest.model_dump_json())
    assert data["run_id"] == "test-123"
    assert data["host"]["os"] == host["os"]
    assert data["host"]["arch"] == host["arch"]
    assert data["host"]["python"] == host["python"]
    assert data["agent"]["type"] == "python"
    assert data["execution"]["tool_call_count"] == 5
    assert data["execution"]["duration_ms"] == 100
    assert isinstance(data["environment"], list)
    assert isinstance(data["timestamp"], str)


def test_trace_diff_silent_empty(tmp_path: Path) -> None:
    """Agent raises an error and produces no trajectory -> trace diff shows silent_empty."""
    runner = _mode_runner(tmp_path, mode="error", timeout_seconds=10)
    artifact = runner.run_one("sc-1", run_id="run-trace-silent")
    assert artifact.status == "error"
    assert artifact.trace_diff is not None
    assert artifact.trace_diff["divergence_type"] == "silent_empty"
    assert artifact.trace_diff["divergence_point"] == "tool_dispatch"
    assert artifact.trace_diff["expected_steps"] == [
        "tool_dispatch", "model_call", "structured_output", "completion",
    ]
    assert artifact.trace_diff["actual_steps"] == []


def test_trace_diff_timeout(tmp_path: Path) -> None:
    """Agent that sleeps past the timeout -> trace diff identifies divergence."""
    runner = _mode_runner(tmp_path, mode="slow", timeout_seconds=1)
    artifact = runner.run_one("sc-1", run_id="run-trace-timeout")
    assert artifact.status == "timeout"
    assert artifact.trace_diff is not None
    assert artifact.trace_diff["divergence_type"] == "stopped_early"
    assert artifact.trace_diff["divergence_point"] == "tool_dispatch"
