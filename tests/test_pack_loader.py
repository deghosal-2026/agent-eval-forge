from pathlib import Path

import pytest

from evalforge.loading.pack_loader import load_pack
from evalforge.models.errors import PackParseError

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"

VALID_PACK = FIXTURES / "valid_pack.yaml"
INVALID_PACK = FIXTURES / "invalid_pack.yaml"


def test_load_valid_yaml_pack() -> None:
    pack = load_pack(VALID_PACK)
    assert pack.pack.name == "test-pack"
    assert pack.pack.version == "1.0.0"
    assert len(pack.scenarios) == 2
    assert pack.scenarios[0].id == "sc-1"
    assert pack.scenarios[1].id == "sc-2"


def test_load_valid_json_pack() -> None:
    pack = load_pack(FIXTURES / "valid_pack.json")
    assert len(pack.scenarios) == 2


def test_duplicate_ids_raise() -> None:
    with pytest.raises(PackParseError, match="duplicate scenario id"):
        load_pack(FIXTURES / "duplicate_pack.yaml")


def test_missing_required_fields_raise() -> None:
    with pytest.raises(PackParseError, match="missing required field"):
        load_pack(FIXTURES / "missing_field_pack.yaml")


def test_invalid_metric_raises() -> None:
    with pytest.raises(PackParseError, match="unknown metric"):
        load_pack(FIXTURES / "bad_metric_pack.yaml")


def test_threshold_out_of_range_raises() -> None:
    with pytest.raises(PackParseError, match="threshold"):
        load_pack(FIXTURES / "bad_threshold_pack.yaml")


def test_string_threshold_raises() -> None:
    with pytest.raises(PackParseError, match="threshold"):
        load_pack(FIXTURES / "bad_threshold_type_pack.yaml")


def test_malformed_yaml_raises_with_line() -> None:
    with pytest.raises(PackParseError) as excinfo:
        load_pack(FIXTURES / "malformed_pack.yaml")
    assert excinfo.value.line is not None


def test_missing_file_raises() -> None:
    with pytest.raises(PackParseError):
        load_pack(FIXTURES / "nope.yaml")


def test_pack_loader_caches_identical_load(tmp_path: Path) -> None:
    """Loading the same pack twice should skip validation on the second load."""
    pack_file = tmp_path / "pack_a.yaml"
    pack_file.write_text("""\
pack:
  name: "cache-test-pack"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "Scenario one"
    input: "input one"
""")
    pack1 = load_pack(pack_file)
    pack2 = load_pack(pack_file)
    assert pack1.pack.name == pack2.pack.name
    assert len(pack1.scenarios) == len(pack2.scenarios)


def test_pack_loader_revalidates_on_content_change(tmp_path: Path) -> None:
    """Modifying pack content after first load should trigger revalidation."""
    pack_file = tmp_path / "pack_b.yaml"
    pack_file.write_text("""\
pack:
  name: "v1-pack"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "Scenario one"
    input: "input one"
""")
    pack1 = load_pack(pack_file)
    assert pack1.pack.name == "v1-pack"

    pack_file.write_text("""\
pack:
  name: "v2-pack"
  version: "2.0.0"
scenarios:
  - id: "sc-2"
    title: "Scenario two"
    input: "input two"
""")
    pack2 = load_pack(pack_file)
    assert pack2.pack.name == "v2-pack"
    assert pack2.pack.version == "2.0.0"
    assert pack2.scenarios[0].id == "sc-2"


def test_pack_loader_cache_independent_paths(tmp_path: Path) -> None:
    """Two different pack files should not interfere with each other's cache."""
    pack_a = tmp_path / "pack_a.yaml"
    pack_a.write_text("""\
pack:
  name: "pack-alpha"
  version: "1.0.0"
scenarios:
  - id: "sc-a"
    title: "Alpha"
    input: "alpha input"
""")
    pack_b = tmp_path / "pack_b.yaml"
    pack_b.write_text("""\
pack:
  name: "pack-beta"
  version: "2.0.0"
scenarios:
  - id: "sc-b"
    title: "Beta"
    input: "beta input"
    tags: [beta]
    metrics:
      task_completion: {threshold: 0.8}
""")
    result_a = load_pack(pack_a)
    result_b = load_pack(pack_b)
    assert result_a.pack.name == "pack-alpha"
    assert result_b.pack.name == "pack-beta"
    assert len(result_a.scenarios) == 1
    assert len(result_b.scenarios) == 1
    assert result_a.scenarios[0].id == "sc-a"
    assert result_b.scenarios[0].id == "sc-b"


def test_pack_loader_cache_by_hash(tmp_path: Path) -> None:
    """Same content at different paths should both load successfully."""
    content = """\
pack:
  name: "hash-keyed-pack"
  version: "1.0.0"
scenarios:
  - id: "sc-1"
    title: "Same content"
    input: "same input"
"""
    path1 = tmp_path / "path1.yaml"
    path2 = tmp_path / "path2.yaml"
    path1.write_text(content)
    path2.write_text(content)
    pack1 = load_pack(path1)
    pack2 = load_pack(path2)
    assert pack1.pack.name == pack2.pack.name
    assert pack1.scenarios[0].id == pack2.scenarios[0].id
