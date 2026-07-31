import sys
from pathlib import Path

from evalforge.adapters.subprocess import SubprocessAdapter
from evalforge.models.pack import Scenario

FIXTURES = Path(__file__).parent / "fixtures"
AGENT = f"{sys.executable} {FIXTURES / 'echo_agent.py'}"


def make_scenario(mode: str = "") -> Scenario:
    ctx = {"mode": mode} if mode else {}
    return Scenario(id="sc-1", title="T", input="hello", context=ctx)


def test_subprocess_envelope() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "echo: hello"
    assert artifact.cost.total_tokens == 2
    assert artifact.trajectory[0].type == "response"
    assert artifact.id == "run-1-sc-1"


def test_subprocess_raw_text_fallback() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="raw"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "completed"
    assert artifact.output.final == "raw text answer"
    assert artifact.trajectory == []
    assert artifact.cost.total_tokens == 0


def test_subprocess_stderr_ignored_but_json_parsed() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="log_and_json"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.output.final == "from envelope"


def test_subprocess_nonzero_exit_marks_error() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="fail"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10},
    )
    assert artifact.status == "error"
    assert "boom" in (artifact.error or "")


def test_subprocess_timeout_marks_timeout() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="slow"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 1},
    )
    assert artifact.status == "timeout"


def test_subprocess_strict_output_error() -> None:
    adapter = SubprocessAdapter()
    artifact = adapter.run(
        make_scenario(mode="raw"),
        {"command": AGENT, "run_id": "run-1", "timeout_seconds": 10, "strict_output": True},
    )
    assert artifact.status == "error"
