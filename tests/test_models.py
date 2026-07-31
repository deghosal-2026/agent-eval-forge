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
