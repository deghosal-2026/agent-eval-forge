"""Tests for :class:`evalforge.scenarios.registry.ScenarioRegistry`."""

from __future__ import annotations

from pathlib import Path

from evalforge.scenarios.registry import ScenarioRegistry

_PACK_YAML = """\
pack:
  name: "test-pack"
  version: "0.1.0"
  description: "A test pack"
scenarios:
  - id: "sc-1"
    title: "Scenario one"
    input: "Hello"
    expected:
      type: "exact"
      value: "world"
    metrics:
      task_completion:
        threshold: 0.8
  - id: "sc-2"
    title: "Scenario two"
    input: "Hi"
    expected:
      type: "contains"
      value: ["hi"]
    metrics:
      task_completion:
        threshold: 0.5
"""

_PACK_JSON = """{
  "pack": {
    "name": "json-pack",
    "version": "2.0.0",
    "description": "A JSON pack"
  },
  "scenarios": [
    {
      "id": "sc-json-1",
      "title": "JSON scenario",
      "input": "Test",
      "expected": {"type": "exact", "value": "result"},
      "metrics": {"task_completion": {"threshold": 0.9}}
    }
  ]
}
"""


def test_discover_packs_in_directory(tmp_path: Path) -> None:
    sc_scenarios = tmp_path / "sc_scenarios"
    sc_scenarios.mkdir()
    (sc_scenarios / "pack-a.yaml").write_text(_PACK_YAML)

    reg = ScenarioRegistry()
    packs = reg.discover(search_paths=[str(sc_scenarios)])
    assert len(packs) == 1
    assert packs[0].name == "test-pack"


def test_discover_multiple_packs(tmp_path: Path) -> None:
    sc_scenarios = tmp_path / "sc_scenarios"
    sc_scenarios.mkdir()
    (sc_scenarios / "pack-a.yaml").write_text(_PACK_YAML)

    _PACK_B = _PACK_YAML.replace("test-pack", "pack-b").replace("A test pack", "Pack B")
    (sc_scenarios / "pack-b.yaml").write_text(_PACK_B)

    reg = ScenarioRegistry()
    packs = reg.discover(search_paths=[str(sc_scenarios)])
    assert len(packs) == 2
    names = {p.name for p in packs}
    assert names == {"test-pack", "pack-b"}


def test_list_packs_with_correct_metadata(tmp_path: Path) -> None:
    sc_scenarios = tmp_path / "sc_scenarios"
    sc_scenarios.mkdir()
    (sc_scenarios / "pack-a.yaml").write_text(_PACK_YAML)

    reg = ScenarioRegistry()
    reg.discover(search_paths=[str(sc_scenarios)])

    packs = reg.list()
    assert len(packs) == 1
    p = packs[0]
    assert p.name == "test-pack"
    assert p.version == "0.1.0"
    assert p.scenario_count == 2
    assert p.description == "A test pack"


def test_find_by_name(tmp_path: Path) -> None:
    sc_scenarios = tmp_path / "sc_scenarios"
    sc_scenarios.mkdir()
    (sc_scenarios / "pack-a.yaml").write_text(_PACK_YAML)

    reg = ScenarioRegistry()
    reg.discover(search_paths=[str(sc_scenarios)])

    found = reg.find("test-pack")
    assert found is not None
    assert found.name == "test-pack"

    missing = reg.find("nonexistent")
    assert missing is None


def test_handles_empty_directory_gracefully(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    reg = ScenarioRegistry()
    packs = reg.discover(search_paths=[str(empty_dir)])
    assert packs == []


def test_handles_nonexistent_directory(tmp_path: Path) -> None:
    reg = ScenarioRegistry()
    packs = reg.discover(search_paths=["/nonexistent/path/12345"])
    assert packs == []


def test_add_single_pack(tmp_path: Path) -> None:
    pack_path = tmp_path / "standalone.yaml"
    pack_path.write_text(_PACK_YAML)

    reg = ScenarioRegistry()
    info = reg.add(str(pack_path))
    assert info is not None
    assert info.name == "test-pack"
    assert info.scenario_count == 2

    listed = reg.list()
    assert len(listed) == 1
    assert listed[0].name == "test-pack"


def test_add_invalid_file_returns_none(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.txt"
    bad_path.write_text("not yaml or json")

    reg = ScenarioRegistry()
    info = reg.add(str(bad_path))
    assert info is None


def test_discover_json_pack(tmp_path: Path) -> None:
    sc_scenarios = tmp_path / "sc_scenarios"
    sc_scenarios.mkdir()
    (sc_scenarios / "pack.json").write_text(_PACK_JSON)

    reg = ScenarioRegistry()
    packs = reg.discover(search_paths=[str(sc_scenarios)])
    assert len(packs) == 1
    assert packs[0].name == "json-pack"
    assert packs[0].version == "2.0.0"
    assert packs[0].scenario_count == 1
