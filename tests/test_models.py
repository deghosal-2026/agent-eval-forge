import pytest

from evalforge.models.errors import (
    AdapterError,
    AgentTimeoutError,
    EvalForgeError,
    PackParseError,
)


def test_error_hierarchy() -> None:
    assert issubclass(PackParseError, EvalForgeError)
    assert issubclass(AdapterError, EvalForgeError)
    assert issubclass(AgentTimeoutError, AdapterError)


def test_pack_parse_error_message_with_line() -> None:
    err = PackParseError("bad yaml", file="pack.yaml", line=12)
    assert str(err) == "pack.yaml:12: bad yaml"
    assert err.file == "pack.yaml"
    assert err.line == 12


def test_pack_parse_error_without_location() -> None:
    err = PackParseError("bad yaml")
    assert str(err) == "bad yaml"
    assert err.file is None
    assert err.line is None
