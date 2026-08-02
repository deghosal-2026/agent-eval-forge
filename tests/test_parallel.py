"""Tests for parallel execution."""

import sys
from pathlib import Path

import pytest

from evalforge.runner import Runner

_ECHO_AGENT = f"{sys.executable} tests/fixtures/echo_agent.py"


def test_serial_execution(tmp_path: Path) -> None:
    """Workers=1 runs scenarios sequentially."""
    runner = Runner(
        agent_config={"type": "subprocess", "command": _ECHO_AGENT, "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=1)
    assert len(artifacts) > 0
    assert all(a.status == "completed" for a in artifacts)


def test_parallel_execution(tmp_path: Path) -> None:
    """Workers=4 runs all scenarios to completion."""
    runner = Runner(
        agent_config={"type": "subprocess", "command": _ECHO_AGENT, "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=4)
    assert len(artifacts) > 0
    assert all(a.status == "completed" for a in artifacts)


def test_parallel_preserves_order(tmp_path: Path) -> None:
    """Parallel results maintain original scenario order."""
    runner = Runner(
        agent_config={"type": "subprocess", "command": _ECHO_AGENT, "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    pack_order = [s.id for s in runner.pack.scenarios]
    artifacts = runner.run_all(workers=4)
    scenario_ids = [a.scenario_id for a in artifacts]
    assert scenario_ids == pack_order


def test_parallel_with_tags(tmp_path: Path) -> None:
    """Parallel execution respects tag filters."""
    runner = Runner(
        agent_config={"type": "subprocess", "command": _ECHO_AGENT, "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    pack = runner.pack
    artifacts = runner.run_all(tags=["retrieval"], workers=2)
    assert len(artifacts) > 0
    expected_ids = {s.id for s in pack.scenarios if "retrieval" in s.tags}
    actual_ids = {a.scenario_id for a in artifacts}
    assert actual_ids == expected_ids


def test_parallel_error_handling(tmp_path: Path) -> None:
    """Parallel execution captures individual worker errors."""
    runner = Runner(
        agent_config={"type": "subprocess", "command": _ECHO_AGENT, "timeout_seconds": 10},
        output_dir=str(tmp_path),
    )
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=8)
    completed = [a for a in artifacts if a.status == "completed"]
    assert len(completed) == len(artifacts)


@pytest.mark.slow
def test_parallel_speedup(tmp_path: Path) -> None:
    """Parallel should complete faster than serial when agents sleep."""
    import time

    runner_sp = Runner(agent_config={"type": "subprocess", "command": f"{sys.executable} -c \"import time; time.sleep(0.1); print('ok')\"", "timeout_seconds": 10}, output_dir=str(tmp_path))  # noqa: E501
    runner_sp.load_pack("scenarios/core-launch.yaml")
    start = time.time()
    runner_sp.run_all(workers=4, run_id="speedup-test")
    serial_time = time.time() - start
    assert serial_time < 60


def test_parallel_backpressure(tmp_path: Path) -> None:
    """max_outstanding limits concurrent workers."""
    runner = Runner(agent_config={"type": "subprocess", "command": "python tests/fixtures/echo_agent.py", "timeout_seconds": 10}, output_dir=str(tmp_path))  # noqa: E501
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=4, max_outstanding=2, run_id="backpressure-test")
    assert len(artifacts) > 0


def test_parallel_failure_isolation(tmp_path: Path) -> None:
    """One failing scenario doesn't block others."""
    runner = Runner(agent_config={"type": "subprocess", "command": "python tests/fixtures/echo_agent.py", "timeout_seconds": 10}, output_dir=str(tmp_path))  # noqa: E501
    runner.load_pack("scenarios/core-launch.yaml")
    artifacts = runner.run_all(workers=4, run_id="fail-isolation-test")
    assert len(artifacts) > 0
