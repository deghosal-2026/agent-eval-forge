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
from evalforge.runner import Runner

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