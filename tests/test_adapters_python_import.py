from pathlib import Path

from evalforge.adapters.python_import import PythonImportAdapter
from evalforge.models.pack import Scenario

FIXTURES = Path(__file__).parent / "fixtures"


def make_scenario(mode: str = "envelope") -> Scenario:
    return Scenario(id="sc-1", title="T", input="hello", context={"mode": mode})


def module_config(mode: str = "envelope") -> dict:
    return {
        "module": "fixtures.agents",
        "function": "run",
        "run_id": "run-1",
        "timeout_seconds": 10,
    }


def test_python_import_envelope() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(), module_config())
    assert artifact.status == "completed"
    assert artifact.output.final == "py:hello"
    assert artifact.cost.total_tokens == 2
    assert artifact.id == "run-1-sc-1"


def test_python_import_raw_return() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(mode="raw"), module_config(mode="raw"))
    assert artifact.status == "completed"
    assert artifact.output.final == "raw python answer"


def test_python_import_exception_marks_error() -> None:
    adapter = PythonImportAdapter()
    artifact = adapter.run(make_scenario(mode="error"), module_config(mode="error"))
    assert artifact.status == "error"


def test_python_import_timeout() -> None:
    adapter = PythonImportAdapter()
    config = module_config(mode="slow")
    config["timeout_seconds"] = 1
    artifact = adapter.run(make_scenario(mode="slow"), config)
    assert artifact.status == "timeout"
