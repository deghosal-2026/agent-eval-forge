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


def test_malformed_yaml_raises_with_line() -> None:
    with pytest.raises(PackParseError) as excinfo:
        load_pack(FIXTURES / "malformed_pack.yaml")
    assert excinfo.value.line is not None


def test_missing_file_raises() -> None:
    with pytest.raises(PackParseError):
        load_pack(FIXTURES / "nope.yaml")
