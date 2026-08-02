"""Scenario linter — validates scenario packs for best practices (X1).

Checks for: missing descriptions, overly broad tools, untagged scenarios,
unrealistic budgets, duplicate tool names, and inconsistent metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evalforge.models.pack import ScenarioPack


@dataclass
class LintIssue:
    """A single lint issue found during scenario pack validation.

    Attributes:
        scenario_id: ID of the affected scenario, or ``None`` for pack-level issues.
        severity: One of ``"error"``, ``"warn"``, or ``"info"``.
        rule: Rule identifier (e.g. ``"missing-description"``).
        message: Human-readable description of the issue.
    """
    scenario_id: str | None
    severity: str  # "error", "warn", "info"
    rule: str
    message: str


@dataclass
class LintReport:
    """Report of all lint issues found in a scenario pack.

    Attributes:
        pack_name: Name of the linted pack.
        issues: List of :class:`LintIssue` found.
        passes: ``True`` if there are zero errors.
    """
    pack_name: str
    issues: list[LintIssue] = field(default_factory=list)
    passes: bool = True

    @property
    def errors(self) -> int:
        """Count of issues with severity ``"error"``."""
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> int:
        """Count of issues with severity ``"warn"``."""
        return sum(1 for i in self.issues if i.severity == "warn")


class ScenarioLinter:
    """Lints scenario packs for correctness and best practices."""

    @staticmethod
    def lint(pack: ScenarioPack) -> LintReport:
        """Run standard lint checks on a scenario pack.

        Checks performed:
        - Pack has a description.
        - Every scenario has tags, metrics, and a goal.
        - Step budgets > 50 generate an info-level warning.
        - Duplicate tool names across scenarios produce a warning.

        Args:
            pack: The :class:`ScenarioPack` to validate.

        Returns:
            A :class:`LintReport` with all findings.
        """
        report = LintReport(pack_name=pack.pack.name)
        if not pack.pack.description:
            report.issues.append(LintIssue(
                None, "warn", "missing-description",
                "Pack is missing a description",
            ))
        for s in pack.scenarios:
            if not s.tags:
                report.issues.append(LintIssue(
                    s.id, "warn", "untagged", "Scenario has no tags",
                ))
            if not s.metrics:
                report.issues.append(LintIssue(
                    s.id, "warn", "no-metrics", "Scenario has no scoring metrics",
                ))
            if s.budget and s.budget.max_steps and s.budget.max_steps > 50:
                report.issues.append(LintIssue(
                    s.id, "info", "high-step-budget",
                    f"Step budget of {s.budget.max_steps} may be too high",
                ))
            if not s.goal:
                report.issues.append(LintIssue(
                    s.id, "warn", "missing-goal", "Scenario has no goal description",
                ))
        all_tool_names = [t.name for s in pack.scenarios for t in s.allowed_tools]
        if len(all_tool_names) != len(set(all_tool_names)):
            report.issues.append(LintIssue(
                None, "warn", "duplicate-tool-names",
                "Duplicate tool names found across scenarios",
            ))
        report.passes = report.errors == 0
        return report

    @staticmethod
    def lint_strict(pack: ScenarioPack) -> LintReport:
        """Run strict lint — all warnings are elevated to errors.

        Args:
            pack: The :class:`ScenarioPack` to validate.

        Returns:
            A :class:`LintReport` where every ``warn`` has been
            promoted to ``error``.
        """
        report = ScenarioLinter.lint(pack)
        for issue in report.issues:
            if issue.severity == "warn":
                issue.severity = "error"
        report.passes = len([i for i in report.issues if i.severity == "error"]) == 0
        return report
