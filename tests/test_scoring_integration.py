"""Integration test: score the full launch pack with mock agents + mock judge."""

from pathlib import Path

from evalforge.models.pack import ScenarioPack
from evalforge.runner import Runner
from evalforge.scoring.engine import ScoringEngine
from evalforge.scoring.judge.mock import MockJudge

LAUNCH_PACK = Path(__file__).parent.parent / "scenarios" / "core-launch.yaml"
AGENT_CONFIG = {"type": "python", "module": "fixtures.agents", "timeout_seconds": 10}


def test_score_launch_pack_with_mock_judge(tmp_path) -> None:
    runner = Runner(agent_config=AGENT_CONFIG, output_dir=tmp_path)
    pack = runner.load_pack(LAUNCH_PACK)
    assert isinstance(pack, ScenarioPack)
    artifacts = runner.run_all()
    assert len(artifacts) == 20

    engine = ScoringEngine(pack)
    judge = MockJudge(score=0.85, rationale="mock judge verdict")
    result = engine.score_run(artifacts, judge=judge)
    assert result.exit_code in (0, 1, 4)
    assert len(result.scenario_scores) == 20
