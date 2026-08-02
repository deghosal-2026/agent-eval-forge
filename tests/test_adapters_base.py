import pytest

from evalforge.adapters.base import (
    Adapter,
    _sanitize_agent,
    build_invocation_payload,
    parse_agent_stdout,
)
from evalforge.models.errors import AdapterError
from evalforge.models.pack import Budget, Scenario, Tool


class _RawEnvelopeAdapter(Adapter):
    """Adapter that returns a fixed raw envelope from _invoke."""

    name = "raw"

    def __init__(self, envelope: dict) -> None:
        self._envelope = envelope

    def _invoke(self, payload: dict, config: dict) -> dict:
        return self._envelope


def make_scenario() -> Scenario:
    return Scenario(
        id="sc-1",
        title="T",
        input="the input",
        context={"tier": "premium"},
        allowed_tools=[Tool(name="tool_a", description="desc")],
        disallowed_tools=[Tool(name="tool_b")],
        budget=Budget(max_steps=3),
    )


def test_build_invocation_payload_excludes_expected_and_metrics() -> None:
    payload = build_invocation_payload(make_scenario(), run_id="run-1")
    assert "expected" not in payload
    assert "metrics" not in payload
    assert payload["schema_version"] == "evalforge.invocation_payload.v1"
    assert payload["run_id"] == "run-1"
    assert payload["scenario_id"] == "sc-1"
    assert payload["input"] == "the input"
    assert payload["context"] == {"tier": "premium"}
    assert payload["allowed_tools"] == [{"name": "tool_a", "description": "desc"}]
    assert payload["disallowed_tools"] == [{"name": "tool_b", "description": None}]
    assert payload["budget"] == {"max_steps": 3, "max_tokens": None, "max_cost_usd": None}


def test_parse_agent_stdout_json_envelope() -> None:
    envelope = (
        '{"schema_version": "evalforge.run_envelope.v1", '
        '"status": "completed", "output": {"final": "hi"}}'
    )
    out = parse_agent_stdout(envelope)
    assert out["status"] == "completed"
    assert out["output"]["final"] == "hi"


def test_parse_agent_stdout_raw_text_fallback() -> None:
    out = parse_agent_stdout("just some text")
    assert out["status"] == "completed"
    assert out["output"]["final"] == "just some text"
    assert out["trajectory"] == {"steps": []}


def test_parse_agent_stdout_strict_raises() -> None:
    with pytest.raises(AdapterError):
        parse_agent_stdout("not json", strict=True)


def test_run_malformed_envelope_status_marks_error() -> None:
    adapter = _RawEnvelopeAdapter({"status": "garbage", "output": {"final": "hi"}})
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "error"
    assert artifact.error is not None


def test_run_envelope_with_str_output_marks_error() -> None:
    adapter = _RawEnvelopeAdapter({"output": "hello"})
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "error"


def test_run_valid_envelope_still_completes() -> None:
    adapter = _RawEnvelopeAdapter(
        {"status": "completed", "output": {"final": "hi"}, "trajectory": {"steps": []}}
    )
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "completed"
    assert artifact.output.final == "hi"


def test_run_blank_output_marks_error() -> None:
    adapter = _RawEnvelopeAdapter(
        {"status": "completed", "output": {"final": "", "structured": None}, "trajectory": {"steps": []}}  # noqa: E501
    )
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "error"
    assert "blank completion" in (artifact.error or "")


def test_run_no_output_marks_error() -> None:
    adapter = _RawEnvelopeAdapter(
        {"status": "completed", "output": {}, "trajectory": {"steps": []}}
    )
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "error"


def test_run_structured_only_still_completes() -> None:
    adapter = _RawEnvelopeAdapter(
        {"status": "completed", "output": {"structured": {"answer": 42}}, "trajectory": {"steps": []}}  # noqa: E501
    )
    artifact = adapter.run(make_scenario(), {"run_id": "run-1"})
    assert artifact.status == "completed"


def test_sanitize_agent_strips_secrets() -> None:
    cleaned = _sanitize_agent(
        {"model": "claude", "api_key": "k", "token": "t", "password": "p", "secret": "s"}
    )
    assert cleaned == {"model": "claude"}
