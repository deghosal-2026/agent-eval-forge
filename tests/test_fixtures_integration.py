"""Integration tests for fixture injection through the Runner -> Adapter -> ToolStub pipeline.

Validates end-to-end fixture injection across all adapter types (python, subprocess, http)
as specified in WBS P2.1. Fixture Injection End-to-End (Runner -> Adapter -> Agent -> ToolStub).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evalforge.adapters.base import _inject_fixtures
from evalforge.fixtures.tool_stub import FixtureNotFoundError, ToolStub

PACK_PATH = Path(__file__).parent.parent / "scenarios" / "core-launch.yaml"


# ---------------------------------------------------------------------------
# ToolStub integration patterns (fixture directory, intercept, cache)
# ---------------------------------------------------------------------------


def test_tool_stub_happy_path(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "policy_lookup.json").write_text(
        json.dumps({"result": "Premium customers receive a 60-day return window."})
    )
    (fixtures_dir / "health_check.json").write_text(
        json.dumps({"service": "payment", "status": "healthy", "uptime_percent": 99.9})
    )

    stub = ToolStub(fixtures_dir=str(fixtures_dir))

    result = stub.intercept("policy_lookup")
    assert result == {"result": "Premium customers receive a 60-day return window."}

    result2 = stub.intercept("health_check")
    assert result2 == {"service": "payment", "status": "healthy", "uptime_percent": 99.9}


def test_tool_stub_missing_fixture_error(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    stub = ToolStub(fixtures_dir=str(fixtures_dir))

    with pytest.raises(FixtureNotFoundError, match="nonexistent_tool"):
        stub.intercept("nonexistent_tool")


def test_tool_stub_partial_fixtures(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "policy_lookup.json").write_text(
        json.dumps({"result": "ok"})
    )

    stub = ToolStub(fixtures_dir=str(fixtures_dir))

    result = stub.intercept("policy_lookup")
    assert result == {"result": "ok"}

    with pytest.raises(FixtureNotFoundError, match="ticket_search"):
        stub.intercept("ticket_search")


# ---------------------------------------------------------------------------
# _inject_fixtures utility stamps / skips metadata on payload
# ---------------------------------------------------------------------------


def test_inject_fixtures_stamps_payload(tmp_path: Path) -> None:
    payload: dict[str, Any] = {}
    config = {"fixtures": True, "fixtures_dir": str(tmp_path)}
    _inject_fixtures(payload, config)
    assert payload["_fixture_mode"] is True
    assert payload["_fixtures_dir"] == str(tmp_path)


def test_fixtures_skipped_when_not_fixture_mode(tmp_path: Path) -> None:
    payload: dict[str, Any] = {}
    config: dict[str, Any] = {}
    _inject_fixtures(payload, config)
    assert "_fixture_mode" not in payload
    assert "_fixtures_dir" not in payload


def test_fixture_used_recorded_in_trajectory(tmp_path: Path) -> None:
    """Runner annotates consumed fixtures as 'fixture_used: <tool>' note steps."""
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "policy_lookup.json").write_text(
        json.dumps({"result": "Premium customers receive a 60-day return window."})
    )

    pack_yaml = tmp_path / "fixture_pack.yaml"
    pack_yaml.write_text("""
pack:
  name: "fixture-pack"
  version: "1.0.0"
scenarios:
  - id: "fx-1"
    title: "Fixture usage test"
    input: "check policy"
    metrics:
      task_completion:
        threshold: 1.0
""")

    agent_py = tmp_path / "fixture_agent.py"
    agent_py.write_text('''
def run(payload: dict) -> dict:
    return {
        "schema_version": "evalforge.run_envelope.v1",
        "status": "completed",
        "output": {"final": "here is the policy", "structured": None},
        "trajectory": {
            "steps": [
                {
                    "type": "tool_call",
                    "tool": "policy_lookup",
                    "args": {},
                    "duration_ms": 1,
                }
            ]
        },
        "cost": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost_usd": 0.0},
        "error": None,
    }
''')

    import sys
    sys.path.insert(0, str(tmp_path))
    try:
        artifact = _run_one(
            agent_module="fixture_agent",
            pack_path=str(pack_yaml),
            fixtures_dir=str(fixtures_dir),
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert artifact.status == "completed"
    note_steps = [s for s in artifact.trajectory if s.type == "note"]
    assert any(
        "fixture_used: policy_lookup" in (s.content or "")
        for s in note_steps
    ), f"expected fixture_used note in trajectory, got: {artifact.trajectory}"


def _run_one(
    agent_module: str,
    pack_path: str,
    fixtures_dir: str,
) -> Any:
    """Run a single-scenario pack through the Runner with fixtures enabled."""
    from evalforge.runner import Runner

    runner = Runner(
        agent_config={
            "type": "python",
            "module": agent_module,
            "function": "run",
            "fixtures": True,
            "fixtures_dir": fixtures_dir,
            "timeout_seconds": 10,
        },
        output_dir=str(Path(pack_path).parent / "output"),
    )
    runner.load_pack(pack_path)
    return runner.run_one("fx-1")
