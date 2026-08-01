import pytest

from evalforge.adapters.factory import create_adapter
from evalforge.adapters.http import HttpAdapter
from evalforge.adapters.pydantic_ai import PydanticAIAdapter
from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.adapters.subprocess import SubprocessAdapter


def test_create_subprocess() -> None:
    assert isinstance(create_adapter({"type": "subprocess", "command": "echo"}), SubprocessAdapter)


def test_create_python() -> None:
    assert isinstance(create_adapter({"type": "python", "module": "x"}), PythonImportAdapter)


def test_create_http() -> None:
    assert isinstance(create_adapter({"type": "http", "url": "http://x"}), HttpAdapter)


def test_create_pydantic_ai() -> None:
    assert isinstance(create_adapter({"type": "pydantic-ai", "module": "x"}), PydanticAIAdapter)


def test_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown adapter type"):
        create_adapter({"type": "nope"})
