"""Tests for the fixture system."""

import json
from pathlib import Path

import pytest

from evalforge.fixtures import FixtureNotFoundError, ToolStub


def test_tool_stub_basic(tmp_path: Path) -> None:
    fixture_file = tmp_path / "lookup.json"
    fixture_file.write_text(json.dumps({"result": "ok"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    result = stub.intercept("lookup")
    assert result == {"result": "ok"}


def test_tool_stub_missing_tool(tmp_path: Path) -> None:
    stub = ToolStub(fixtures_dir=str(tmp_path))
    with pytest.raises(FixtureNotFoundError):
        stub.intercept("nonexistent_tool")


def test_tool_stub_list_with_query(tmp_path: Path) -> None:
    fixture_file = tmp_path / "search.json"
    fixtures = [{"id": 1}, {"id": 2}, {"id": 3}]
    fixture_file.write_text(json.dumps(fixtures))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    r1 = stub.intercept("search", {"query": "foo"})
    r2 = stub.intercept("search", {"query": "bar"})
    assert isinstance(r1, dict)
    assert isinstance(r2, dict)
    # Deterministic: same payload yields same result
    assert stub.intercept("search", {"query": "foo"}) == r1


def test_tool_stub_single_fixture_is_returned_directly(tmp_path: Path) -> None:
    fixture_file = tmp_path / "ping.json"
    fixture_file.write_text(json.dumps({"status": "ok"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.intercept("ping") == {"status": "ok"}


def test_tool_stub_caching(tmp_path: Path) -> None:
    fixture_file = tmp_path / "cached_tool.json"
    fixture_file.write_text(json.dumps([{"data": "v1"}]))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.intercept("cached_tool") == {"data": "v1"}
    # Modify the file on disk — cache should still return original
    fixture_file.write_text(json.dumps([{"data": "v2"}]))
    assert stub.intercept("cached_tool") == {"data": "v1"}


def test_available_tools(tmp_path: Path) -> None:
    (tmp_path / "tool_a.json").write_text("{}")
    (tmp_path / "tool_b.json").write_text("{}")
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.available_tools() == {"tool_a", "tool_b"}


def test_available_tools_empty_dir(tmp_path: Path) -> None:
    stub = ToolStub(fixtures_dir=str(tmp_path))
    assert stub.available_tools() == set()


def test_delay_ms(tmp_path: Path) -> None:
    import time
    fixture_file = tmp_path / "slow_tool.json"
    fixture_file.write_text(json.dumps({"result": "eventually"}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    stub.set_delay_ms(50)
    start = time.time()
    stub.intercept("slow_tool")
    elapsed = (time.time() - start) * 1000
    assert elapsed >= 40  # allow 10ms tolerance


def test_inject_fixtures_stamps_payload(tmp_path: Path) -> None:
    from evalforge.adapters.base import _inject_fixtures

    payload: dict = {}
    config = {"fixtures": True, "fixtures_dir": str(tmp_path)}
    _inject_fixtures(payload, config)
    assert payload["_fixture_mode"] is True
    assert payload["_fixtures_dir"] == str(tmp_path)


def test_inject_fixtures_skipped_when_not_fixture_mode(tmp_path: Path) -> None:
    from evalforge.adapters.base import _inject_fixtures

    payload: dict = {}
    config: dict = {}
    _inject_fixtures(payload, config)
    assert "_fixture_mode" not in payload


def test_tool_stub_deterministic_hash(tmp_path: Path) -> None:
    fixture_file = tmp_path / "hash_tool.json"
    fixture_file.write_text(json.dumps([{"r": "a"}, {"r": "b"}, {"r": "c"}]))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    r1 = stub.intercept("hash_tool", {"x": 1})
    r2 = stub.intercept("hash_tool", {"x": 1})
    assert r1 == r2


def test_tool_stub_verify_consumed(tmp_path: Path) -> None:
    for name in ("used_tool", "unused_tool"):
        (tmp_path / f"{name}.json").write_text(json.dumps({"ok": True}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    stub.declare_expected({"used_tool", "unused_tool"})
    stub.intercept("used_tool")
    warnings = stub.verify_consumed()
    assert len(warnings) == 1
    assert "unused_tool" in warnings[0]


def test_tool_stub_delay_ms(tmp_path: Path) -> None:
    import time
    fixture_file = tmp_path / "delayed_tool.json"
    fixture_file.write_text(json.dumps({"result": "slow", "delay_ms": 50}))
    stub = ToolStub(fixtures_dir=str(tmp_path))
    start = time.time()
    stub.intercept("delayed_tool")
    elapsed = (time.time() - start) * 1000
    assert elapsed >= 40
