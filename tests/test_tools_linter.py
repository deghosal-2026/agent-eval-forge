"""Tests for evalforge.tools.linter."""

from evalforge.models.pack import (
    Budget,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)
from evalforge.tools.linter import LintIssue, LintReport, ScenarioLinter


class TestLintIssue:
    def test_creation(self) -> None:
        issue = LintIssue(
            scenario_id="s1",
            severity="warn",
            rule="missing-description",
            message="Pack is missing a description",
        )
        assert issue.scenario_id == "s1"
        assert issue.severity == "warn"
        assert issue.rule == "missing-description"
        assert issue.message == "Pack is missing a description"

    def test_pack_level_issue(self) -> None:
        issue = LintIssue(None, "warn", "rule-x", "msg")
        assert issue.scenario_id is None


class TestLintReport:
    def test_defaults(self) -> None:
        report = LintReport(pack_name="test-pack")
        assert report.pack_name == "test-pack"
        assert report.issues == []
        assert report.passes is True

    def test_errors_count(self) -> None:
        report = LintReport(pack_name="p")
        report.issues = [
            LintIssue(None, "error", "r1", "m1"),
            LintIssue("s1", "warn", "r2", "m2"),
            LintIssue("s2", "error", "r3", "m3"),
            LintIssue(None, "info", "r4", "m4"),
        ]
        assert report.errors == 2

    def test_warnings_count(self) -> None:
        report = LintReport(pack_name="p")
        report.issues = [
            LintIssue(None, "warn", "r1", "m1"),
            LintIssue("s1", "warn", "r2", "m2"),
            LintIssue("s2", "error", "r3", "m3"),
        ]
        assert report.warnings == 2

    def test_no_issues_returns_zero(self) -> None:
        report = LintReport(pack_name="p")
        assert report.errors == 0
        assert report.warnings == 0


def _make_pack(pack_name="test", description="a test pack", scenarios=None):
    pack_meta = PackMetadata(name=pack_name, version="1.0", description=description)
    return ScenarioPack(pack=pack_meta, scenarios=scenarios or [])


def _make_scenario(
    sid="s1",
    title="Test Scenario",
    goal="do something",
    input_text="test input",
    tags=None,
    metrics=None,
    tools=None,
    budget=None,
):
    return Scenario(
        id=sid,
        title=title,
        goal=goal,
        input=input_text,
        tags=tags or [],
        metrics=metrics or {},
        allowed_tools=tools or [],
        budget=budget,
    )


class TestScenarioLinterLint:
    def test_empty_pack_with_description(self) -> None:
        pack = _make_pack(description="a test")
        report = ScenarioLinter.lint(pack)
        assert report.passes is True
        assert report.issues == []

    def test_missing_pack_description(self) -> None:
        pack = _make_pack(description=None)
        report = ScenarioLinter.lint(pack)
        assert report.passes is True
        assert len(report.issues) == 1
        assert report.issues[0].rule == "missing-description"
        assert report.issues[0].severity == "warn"
        assert report.issues[0].scenario_id is None

    def test_scenario_with_no_tags(self) -> None:
        scenario = _make_scenario(tags=[])
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert report.passes is True
        assert any(i.rule == "untagged" for i in report.issues)
        untagged = [i for i in report.issues if i.rule == "untagged"]
        assert len(untagged) == 1
        assert untagged[0].scenario_id == "s1"
        assert untagged[0].severity == "warn"

    def test_scenario_with_tags_no_warning(self) -> None:
        scenario = _make_scenario(tags=["math", "arithmetic"])
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "untagged" for i in report.issues)

    def test_scenario_with_no_metrics(self) -> None:
        scenario = _make_scenario(metrics={})
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert any(i.rule == "no-metrics" for i in report.issues)
        no_metrics = [i for i in report.issues if i.rule == "no-metrics"]
        assert len(no_metrics) == 1
        assert no_metrics[0].severity == "warn"

    def test_scenario_with_metrics_no_warning(self) -> None:
        scenario = _make_scenario(metrics={"accuracy": Metric()})
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "no-metrics" for i in report.issues)

    def test_scenario_with_no_goal(self) -> None:
        scenario = _make_scenario(goal=None)
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert any(i.rule == "missing-goal" for i in report.issues)
        missing_goal = [i for i in report.issues if i.rule == "missing-goal"]
        assert len(missing_goal) == 1
        assert missing_goal[0].severity == "warn"

    def test_high_step_budget(self) -> None:
        scenario = _make_scenario(budget=Budget(max_steps=100))
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert any(i.rule == "high-step-budget" for i in report.issues)
        hs = [i for i in report.issues if i.rule == "high-step-budget"]
        assert len(hs) == 1
        assert hs[0].severity == "info"

    def test_low_step_budget_no_warning(self) -> None:
        scenario = _make_scenario(budget=Budget(max_steps=30))
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "high-step-budget" for i in report.issues)

    def test_budget_max_steps_none(self) -> None:
        scenario = _make_scenario(budget=Budget(max_steps=None))
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "high-step-budget" for i in report.issues)

    def test_no_budget(self) -> None:
        scenario = _make_scenario(budget=None)
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "high-step-budget" for i in report.issues)

    def test_duplicate_tool_names(self) -> None:
        s1 = _make_scenario(
            sid="s1", title="S1", tools=[Tool(name="read"), Tool(name="write")]
        )
        s2 = _make_scenario(
            sid="s2", title="S2", tools=[Tool(name="read"), Tool(name="exec")]
        )
        pack = _make_pack(scenarios=[s1, s2])
        report = ScenarioLinter.lint(pack)
        assert any(i.rule == "duplicate-tool-names" for i in report.issues)

    def test_no_duplicate_tool_names(self) -> None:
        s1 = _make_scenario(
            sid="s1", title="S1", tools=[Tool(name="read"), Tool(name="write")]
        )
        s2 = _make_scenario(
            sid="s2", title="S2", tools=[Tool(name="exec"), Tool(name="delete")]
        )
        pack = _make_pack(scenarios=[s1, s2])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "duplicate-tool-names" for i in report.issues)

    def test_multiple_issues_across_scenarios(self) -> None:
        s1 = _make_scenario(sid="s1", title="S1", tags=[], metrics={}, goal=None)
        s2 = _make_scenario(sid="s2", title="S2", tags=[], metrics={}, goal=None)
        pack = _make_pack(description=None, scenarios=[s1, s2])
        report = ScenarioLinter.lint(pack)
        assert len(report.issues) == 7

    def test_passes_false_when_errors_present(self) -> None:
        pack = _make_pack(description=None)
        ScenarioLinter.lint(pack)
        report = LintReport(pack_name="p")
        report.issues = [LintIssue(None, "error", "e1", "m1")]
        report.passes = report.errors == 0
        assert report.passes is False

    def test_budget_max_steps_exactly_50_no_warning(self) -> None:
        scenario = _make_scenario(budget=Budget(max_steps=50))
        pack = _make_pack(scenarios=[scenario])
        report = ScenarioLinter.lint(pack)
        assert not any(i.rule == "high-step-budget" for i in report.issues)


class TestScenarioLinterLintStrict:
    def test_warnings_become_errors(self) -> None:
        s1 = _make_scenario(sid="s1", title="S1", tags=[], metrics={})
        pack = _make_pack(description=None, scenarios=[s1])
        report = ScenarioLinter.lint_strict(pack)
        assert all(i.severity == "error" for i in report.issues)
        assert report.passes is False

    def test_passes_when_no_issues(self) -> None:
        s1 = _make_scenario(
            sid="s1",
            title="S1",
            tags=["tag"],
            metrics={"m": Metric()},
            tools=[Tool(name="t1")],
        )
        pack = _make_pack(scenarios=[s1])
        report = ScenarioLinter.lint_strict(pack)
        assert report.passes is True

    def test_info_remains_info(self) -> None:
        s1 = _make_scenario(
            sid="s1",
            title="S1",
            tags=["tag"],
            metrics={"m": Metric()},
            budget=Budget(max_steps=100),
        )
        pack = _make_pack(scenarios=[s1])
        report = ScenarioLinter.lint_strict(pack)
        info_issues = [i for i in report.issues if i.severity == "info"]
        assert len(info_issues) == 1
        assert report.passes is True
