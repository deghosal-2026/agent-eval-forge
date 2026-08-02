import json

from evalforge.models.artifact import (
    Cost,
    RunArtifact,
    RunOutput,
    RunTimestamps,
    TrajectoryStep,
)
from evalforge.models.errors import (
    AdapterError,
    AgentTimeoutError,
    EvalForgeError,
    PackParseError,
)
from evalforge.models.pack import Budget, Expected, Metric, Scenario, ScenarioPack, Tool


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


def test_tool_model() -> None:
    tool = Tool(name="policy_lookup", description="Look up policies")
    assert tool.name == "policy_lookup"
    assert tool.description == "Look up policies"
    assert Tool(name="x").description is None


def test_expected_exact() -> None:
    exp = Expected(type="exact", value="the answer")
    assert exp.type == "exact"
    assert exp.value == "the answer"


def test_expected_rubric() -> None:
    exp = Expected(type="rubric", criteria=["must do X", "must not do Y"])
    assert exp.criteria == ["must do X", "must not do Y"]


def test_metric_defaults() -> None:
    m = Metric()
    assert m.weight == 1.0
    assert m.threshold is None


def test_budget_optional_fields() -> None:
    b = Budget(max_steps=3)
    assert b.max_steps == 3
    assert b.max_tokens is None
    assert b.max_cost_usd is None


def test_scenario_roundtrip() -> None:
    sc = Scenario(
        id="sc-1",
        title="Title",
        goal="Goal",
        input="the input",
        context={"tier": "premium"},
        allowed_tools=[Tool(name="tool_a")],
        expected=Expected(type="exact", value="v"),
        metrics={"task_completion": Metric(threshold=1.0)},
        tags=["retrieval"],
    )
    assert sc.id == "sc-1"
    assert sc.context == {"tier": "premium"}
    assert sc.allowed_tools[0].name == "tool_a"
    assert sc.metrics["task_completion"].threshold == 1.0
    assert sc.tags == ["retrieval"]


def test_scenario_pack_roundtrip() -> None:
    pack = ScenarioPack(
        pack={"name": "p", "version": "1.0.0"},
        scenarios=[Scenario(id="s1", title="T", input="i")],
    )
    assert pack.pack.name == "p"
    assert pack.pack.version == "1.0.0"
    assert len(pack.scenarios) == 1
    # pydantic accepts dict for nested model via model_validate too
    assert pack.scenarios[0].input == "i"


def test_trajectory_step() -> None:
    step = TrajectoryStep(
        type="tool_call",
        tool="policy_lookup",
        args={"q": "ret"},
        duration_ms=800,
    )
    assert step.type == "tool_call"
    assert step.tool == "policy_lookup"
    assert step.args == {"q": "ret"}
    assert step.duration_ms == 800


def test_cost_defaults() -> None:
    c = Cost()
    assert c.input_tokens == 0
    assert c.total_tokens == 0
    assert c.cost_usd == 0.0


def test_run_artifact_roundtrip() -> None:
    artifact = RunArtifact(
        id="run-1",
        scenario_id="sc-1",
        agent={"framework": "mock"},
        timestamp=RunTimestamps(
            start="2026-01-01T00:00:00Z", end="2026-01-01T00:00:02Z", duration_ms=2000
        ),
        output=RunOutput(final="done", structured=None),
        trajectory=[TrajectoryStep(type="response", content="done", duration_ms=2000)],
        cost=Cost(input_tokens=10, output_tokens=5, total_tokens=15, cost_usd=0.001),
        status="completed",
    )
    data = json.loads(artifact.model_dump_json())
    restored = RunArtifact.model_validate(data)
    assert restored == artifact
    assert restored.status == "completed"


def test_run_artifact_default_status() -> None:
    a = RunArtifact(
        id="r",
        scenario_id="s",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
    )
    assert a.status == "completed"
    assert a.cost == Cost()
    assert a.trajectory == []
    assert a.output.final is None
