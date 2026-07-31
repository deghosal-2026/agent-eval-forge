import json
from pathlib import Path

import pytest

from evalforge.models.pack import ScenarioPack
from evalforge.runner import Runner, generate_run_id

PACK_YAML = Path(__file__).parent / "fixtures" / "valid_pack.yaml"


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
