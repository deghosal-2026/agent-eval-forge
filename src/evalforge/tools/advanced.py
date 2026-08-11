"""Advanced evaluation features — batch implementation of v0.3 X-items.

X4: Multi-Agent Orchestration Evals
X5: Tool Approval Workflow Evals
X6: Latency/Throughput Stress Testing
X7: Budget-Aware Optimization
X8: Provider/Model Matrix Runner
X9: Prompt Template Versioning & Diffs
X11: Compliance Hooks (SOC2-Ready)
X12: Triage Assistant (LLM Summaries) — integrated into analytics
X13: HTML Report with Deep Links & Diff Views
X14: Data Lake Export (Parquet/Delta)
X15: Public Leaderboard Integration (Opt-In)
X16: Pack Registry & Signing (Sigstore)
X17: Tutorials & Notebooks Library
X18: Editor/IDE Integration (VSCode)
X19: GitHub App PR Gate (Checks API)
X20: Flakiness Profiler & Statistical Deltas
X21: A/B Gating and Canarying
X23: Distributed Executor (Queue/Workers)
X24: Telemetry Export (Prometheus/Grafana)
X25: Governance (RBAC/Policy DSL)
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, ClassVar

# X4: Multi-Agent Orchestration Evals ------------------------------------------

@dataclass
class MultiAgentScenario:
    """Describes a multi-agent orchestration scenario.

    Attributes:
        agents: List of agent descriptors (each contains ``name``, ``role``, ``agent_spec``).
        interaction_order: Ordered list of agent groups that execute sequentially.
        shared_context: Global context passed to all agents.
        expected_collaboration: Expected handoff/collaboration sequence.
    """
    agents: list[dict[str, Any]]  # [{name, role, agent_spec}]
    interaction_order: list[list[str]]  # e.g. [["planner"], ["worker","worker"]]
    shared_context: dict[str, Any] = field(default_factory=dict)
    expected_collaboration: list[str] = field(default_factory=list)


class MultiAgentEvaluator:
    """Evaluates multi-agent orchestration scenarios (X4)."""

    @staticmethod
    def evaluate(interactions: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyse a sequence of multi-agent interactions.

        Counts unique agents, handoffs, and errors. A scenario passes iff
        there are zero errors.

        Args:
            interactions: Ordered list of interaction dicts, each with
                ``agent``, ``type``, and optionally ``error`` keys.

        Returns:
            Dict with keys ``agents_involved``, ``total_interactions``,
            ``handoffs``, ``errors``, ``error_details``, ``passed``.
        """
        agents_seen: Counter[str] = Counter()
        errors: list[str] = []
        handoffs: int = 0
        for step in interactions:
            agent = step.get("agent", "unknown")
            agents_seen[agent] += 1
            if step.get("type") == "handoff":
                handoffs += 1
            if step.get("error"):
                errors.append(f"{agent}: {step['error']}")
        return {
            "agents_involved": len(agents_seen),
            "total_interactions": len(interactions),
            "handoffs": handoffs,
            "errors": len(errors),
            "error_details": errors,
            "passed": len(errors) == 0,
        }


# X5: Tool Approval Workflow Evals ---------------------------------------------

@dataclass
class ApprovalWorkflow:
    """Defines the approval policy for a single tool.

    Attributes:
        tool: Name of the tool.
        requires_approval: Whether human approval is mandatory.
        approver_role: Role permitted to approve (e.g. ``"human"``).
        max_auto_approvals: Number of automatic approvals allowed before
            requiring explicit approval.
    """
    tool: str
    requires_approval: bool
    approver_role: str = "human"
    max_auto_approvals: int = 0


class ToolApprovalEvaluator:
    """Evaluates tool approval workflows (X5)."""

    @staticmethod
    def check_approval(
        tool_calls: list[dict[str, Any]], workflow: ApprovalWorkflow
    ) -> dict[str, Any]:
        """Check a sequence of tool calls against the approval workflow policy.

        Args:
            tool_calls: Ordered list of tool-call dicts, each with ``tool``,
                ``approved``, and ``approved_by`` keys.
            workflow: The :class:`ApprovalWorkflow` policy to enforce.

        Returns:
            Dict with ``tool``, ``violations`` (list of strings),
            ``auto_approvals_used``, and ``passed``.
        """
        violations: list[str] = []
        auto_count = 0
        for call in tool_calls:
            if call.get("tool") != workflow.tool:
                continue
            if workflow.requires_approval:
                if not call.get("approved"):
                    violations.append(
                        f"Tool {workflow.tool} called without approval"
                    )
                elif call.get("approved_by") != workflow.approver_role:
                    if auto_count >= workflow.max_auto_approvals:
                        violations.append(
                            f"Tool {workflow.tool} exceeded auto-approval limit"
                        )
                    else:
                        auto_count += 1
        return {
            "tool": workflow.tool,
            "violations": violations,
            "auto_approvals_used": auto_count,
            "passed": len(violations) == 0,
        }


# X6: Latency/Throughput Stress Testing ----------------------------------------

@dataclass
class StressTestResult:
    """Result of a latency/throughput stress test.

    Attributes:
        scenarios: Number of scenarios executed.
        total_duration_ms: Sum of all scenario durations.
        avg_duration_ms: Mean scenario duration.
        p50_ms: Median latency.
        p95_ms: 95th percentile latency.
        p99_ms: 99th percentile latency.
        throughput_per_sec: Scenarios per second.
        passed: Whether p95 <= threshold_ms.
        threshold_ms: Latency threshold used for pass/fail.
    """
    scenarios: int
    total_duration_ms: float
    avg_duration_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float
    passed: bool
    threshold_ms: float


class StressTester:
    """Runs latency/throughput stress tests (X6)."""

    @staticmethod
    def analyze_durations(
        durations_ms: list[float], threshold_ms: float = 5000
    ) -> StressTestResult:
        """Compute latency statistics and pass/fail against a threshold.

        Args:
            durations_ms: List of individual scenario durations in milliseconds.
            threshold_ms: P95 must be below this value for the test to pass.

        Returns:
            A :class:`StressTestResult`.
        """
        if not durations_ms:
            return StressTestResult(0, 0, 0, 0, 0, 0, 0, True, threshold_ms)
        sorted_d = sorted(durations_ms)
        n = len(sorted_d)
        total = sum(sorted_d)
        p50 = sorted_d[n // 2]
        p95 = sorted_d[int(n * 0.95)]
        p99 = sorted_d[int(n * 0.99)] if n > 10 else sorted_d[-1]
        throughput = n / (total / 1000) if total > 0 else 0
        return StressTestResult(
            scenarios=n,
            total_duration_ms=total,
            avg_duration_ms=total / n,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            throughput_per_sec=round(throughput, 2),
            passed=p95 <= threshold_ms,
            threshold_ms=threshold_ms,
        )


# X7: Budget-Aware Optimization ------------------------------------------------

@dataclass
class BudgetProfile:
    """A budget envelope for evaluation runs.

    Attributes:
        name: Human-readable profile name (e.g. ``"minimal"``).
        max_steps: Maximum allowed agent steps per scenario.
        max_cost_usd: Maximum allowed cost in USD per scenario.
        success_threshold: Minimum pass rate required (0.0 - 1.0).
    """
    name: str
    max_steps: int
    max_cost_usd: float
    success_threshold: float  # minimum pass rate


class BudgetOptimizer:
    """Optimizes budget-aware acceptance envelopes (X7)."""

    @staticmethod
    def find_minimal_budget(
        results: list[dict[str, Any]], target_pass_rate: float = 0.8
    ) -> BudgetProfile:
        """Find the smallest budget profile that still meets the target pass rate.

        Tests profiles from cheapest (``minimal``) to most expensive
        (``generous``) and returns the first that satisfies the pass rate.

        Args:
            results: List of run result dicts, each with ``passed``, ``steps``,
                and ``cost_usd`` keys.
            target_pass_rate: Minimum acceptable pass rate (default 0.8).

        Returns:
            A :class:`BudgetProfile`; falls back to ``unbounded`` if none match.
        """
        for profile in [
            BudgetProfile("minimal", 3, 0.01, target_pass_rate),
            BudgetProfile("moderate", 10, 0.05, target_pass_rate),
            BudgetProfile("generous", 50, 0.25, target_pass_rate),
        ]:
            passed = sum(
                1
                for r in results
                if r.get("passed")
                and r.get("steps", 999) <= profile.max_steps
                and r.get("cost_usd", 999) <= profile.max_cost_usd
            )
            rate = passed / len(results) if results else 0
            if rate >= target_pass_rate:
                return profile
        return BudgetProfile("unbounded", 999, 999, 0)


# X8: Provider/Model Matrix Runner ---------------------------------------------

@dataclass
class ModelMatrixEntry:
    """Aggregated result for a single provider/model combination.

    Attributes:
        provider: Provider name (e.g. ``"openai"``).
        model: Model identifier (e.g. ``"gpt-4o"``).
        avg_score: Mean evaluation score across scenarios.
        avg_cost_usd: Mean cost per scenario.
        avg_duration_ms: Mean duration per scenario.
        scenarios_run: Number of scenarios executed in this entry.
    """
    provider: str
    model: str
    avg_score: float
    avg_cost_usd: float
    avg_duration_ms: float
    scenarios_run: int


class ModelMatrixRunner:
    """Runs scenarios across provider/model combinations (X8).

    Collects per-call results and provides aggregation plus top-N
    selections by score or cost.
    """

    def __init__(self) -> None:
        self._results: list[ModelMatrixEntry] = []

    def add_result(
        self, provider: str, model: str, score: float, cost: float, duration: float
    ) -> None:
        """Register a single scenario result for a provider/model pair.

        Args:
            provider: Provider name.
            model: Model identifier.
            score: Evaluation score for this scenario.
            cost: Cost in USD for this scenario.
            duration: Duration in milliseconds for this scenario.
        """
        self._results.append(ModelMatrixEntry(provider, model, score, cost, duration, 1))

    def aggregate(self) -> list[ModelMatrixEntry]:
        """Combine results from the same provider/model pair.

        Returns:
            List of :class:`ModelMatrixEntry` with averaged metrics.
        """
        aggregated: dict[tuple[str, str], list[ModelMatrixEntry]] = {}
        for r in self._results:
            key = (r.provider, r.model)
            aggregated.setdefault(key, []).append(r)
        return [
            ModelMatrixEntry(
                provider=provider,
                model=model,
                avg_score=sum(e.avg_score for e in entries) / len(entries),
                avg_cost_usd=sum(e.avg_cost_usd for e in entries) / len(entries),
                avg_duration_ms=sum(e.avg_duration_ms for e in entries) / len(entries),
                scenarios_run=len(entries),
            )
            for (provider, model), entries in aggregated.items()
        ]

    def best_by_score(self) -> ModelMatrixEntry | None:
        """Return the provider/model entry with the highest average score.

        Returns:
            The top-scoring entry, or ``None`` if no results exist.
        """
        aggregated = self.aggregate()
        if not aggregated:
            return None
        return max(aggregated, key=lambda e: e.avg_score)

    def best_by_cost(self) -> ModelMatrixEntry | None:
        """Return the provider/model entry with the lowest average cost.

        Returns:
            The cheapest entry, or ``None`` if no results exist.
        """
        aggregated = self.aggregate()
        if not aggregated:
            return None
        return min(aggregated, key=lambda e: e.avg_cost_usd)


# X9: Prompt Template Versioning & Diffs ---------------------------------------

@dataclass
class PromptVersion:
    """A versioned prompt template.

    Attributes:
        version: Version identifier (e.g. ``"1.0"``).
        template: The prompt template text (may contain ``{variable}`` placeholders).
        variables: Default values or descriptions for template variables.
        created: ISO-8601 timestamp of creation.
    """
    version: str
    template: str
    variables: dict[str, str]
    created: str


@dataclass
class PromptDiff:
    """Difference between two prompt versions.

    Attributes:
        v1: First version identifier.
        v2: Second version identifier.
        added_lines: Lines present in v2 but not v1.
        removed_lines: Lines present in v1 but not v2.
        changed_variables: Variable names that differ between versions.
    """
    v1: str
    v2: str
    added_lines: list[str]
    removed_lines: list[str]
    changed_variables: list[str]


class PromptVersionManager:
    """Manages prompt template versioning and diffs (X9)."""

    def __init__(self) -> None:
        self._versions: dict[str, PromptVersion] = {}

    def save_version(self, version: PromptVersion) -> None:
        """Store a prompt version by its version string.

        Args:
            version: The :class:`PromptVersion` to store.
        """
        self._versions[version.version] = version

    def get_version(self, version: str) -> PromptVersion | None:
        """Retrieve a previously stored prompt version.

        Args:
            version: Version identifier.

        Returns:
            The :class:`PromptVersion` or ``None``.
        """
        return self._versions.get(version)

    def diff(self, v1: str, v2: str) -> PromptDiff:
        """Produce a line-level diff between two prompt versions.

        Args:
            v1: First version identifier (or raw template string).
            v2: Second version identifier (or raw template string).

        Returns:
            A :class:`PromptDiff` detailing additions, removals, and
            variable changes.
        """
        pv1 = self._versions.get(v1)
        pv2 = self._versions.get(v2)
        lines1 = (pv1.template if pv1 else v1).splitlines()
        lines2 = (pv2.template if pv2 else v2).splitlines()
        added = [ln for ln in lines2 if ln not in lines1]
        removed = [ln for ln in lines1 if ln not in lines2]
        vars1 = set(pv1.variables.keys()) if pv1 else set()
        vars2 = set(pv2.variables.keys()) if pv2 else set()
        changed_vars = list(vars2 - vars1 | vars1 - vars2)
        return PromptDiff(v1, v2, added, removed, changed_vars)


# X11: Compliance Hooks (SOC2-Ready) -------------------------------------------

@dataclass
class ComplianceRecord:
    """A single compliance audit record.

    Attributes:
        audit_id: Unique identifier for this record.
        control: The control being checked (e.g. ``"ACCESS_CONTROL"``).
        timestamp: ISO-8601 timestamp of the check.
        evidence: Arbitrary evidence dict from the check.
        passed: Whether the check passed.
    """
    audit_id: str
    control: str  # e.g. "ACCESS_CONTROL", "DATA_INTEGRITY", "CHANGE_MANAGEMENT"
    timestamp: str
    evidence: dict[str, Any]
    passed: bool


class ComplianceHooks:
    """Skeleton for SOC2 compliance hooks (X11).

    Records compliance check results and provides aggregated reports.
    """

    def __init__(self) -> None:
        self._records: list[ComplianceRecord] = []

    def record_check(self, control: str, evidence: dict[str, Any], passed: bool) -> None:
        """Record the result of a compliance control check.

        Args:
            control: Control identifier (e.g. ``"ACCESS_CONTROL"``).
            evidence: Supporting evidence dict.
            passed: Whether the check passed.
        """
        self._records.append(
            ComplianceRecord(
                audit_id=f"audit-{len(self._records)}",
                control=control,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                evidence=evidence,
                passed=passed,
            )
        )

    def is_compliant(self) -> bool:
        """Return True iff every recorded check passed."""
        return all(r.passed for r in self._records)

    def export_report(self) -> list[dict[str, Any]]:
        """Export a summary report of all compliance checks.

        Returns:
            List of dicts with ``audit_id``, ``control``, and ``passed``.
        """
        return [
            {"audit_id": r.audit_id, "control": r.control, "passed": r.passed}
            for r in self._records
        ]


# X13: HTML Report Deep Links --------------------------------

class HTMLReportEnhancer:
    """Enhances HTML reports with deep links and diff views (X13)."""

    @staticmethod
    def scenario_deep_link(scenario_id: str, base_url: str = "") -> str:
        """Generate a deep-link anchor to a specific scenario in the report.

        Args:
            scenario_id: The scenario identifier.
            base_url: Optional base URL prefix.

        Returns:
            A URL fragment like ``"#scenario-<scenario_id>"``.
        """
        return f'{base_url}#scenario-{scenario_id}'

    @staticmethod
    def diff_view(before: dict[str, Any], after: dict[str, Any]) -> str:
        """Render an HTML table showing key-level differences between two dicts.

        Args:
            before: The "before" state dict.
            after: The "after" state dict.

        Returns:
            An HTML string containing a table of changed keys.
        """
        diffs: list[str] = []
        all_keys = set(before.keys()) | set(after.keys())
        for key in sorted(all_keys):
            b_val = before.get(key)
            a_val = after.get(key)
            if b_val != a_val:
                diffs.append(f"<tr><td>{key}</td><td>{b_val}</td><td>{a_val}</td></tr>")
        if not diffs:
            return "<p>No changes.</p>"
        table = "<table><tr><th>Key</th><th>Before</th><th>After</th></tr>"
        return table + "".join(diffs) + "</table>"


# X14: Data Lake Export (Parquet/Delta) ----------------------------------------

class DataLakeExporter:
    """Exports evaluation results to data lake formats (X14)."""

    @staticmethod
    def to_jsonl(results: list[dict[str, Any]]) -> str:
        """Serialize results to newline-delimited JSON.

        Args:
            results: List of result dicts.

        Returns:
            A JSONL string (one JSON object per line).
        """
        return "\n".join(json.dumps(r) for r in results)

    @staticmethod
    def to_csv(results: list[dict[str, Any]]) -> str:
        """Serialize results to CSV (header + data rows).

        Uses keys from the first result dict as the header row.

        Args:
            results: List of result dicts (all should share the same keys).

        Returns:
            A CSV string.
        """
        if not results:
            return ""
        keys = list(results[0].keys())
        header = ",".join(keys)
        rows = [",".join(str(r.get(k, "")) for k in keys) for r in results]
        return "\n".join([header, *rows])


# X15: Public Leaderboard Integration ------------------------------------------

@dataclass
class LeaderboardEntry:
    """A single entry on the public leaderboard.

    Attributes:
        agent_name: Name of the evaluated agent.
        score: Aggregate evaluation score.
        scenarios_passed: Number of scenarios passed.
        total_scenarios: Total scenarios attempted.
        timestamp: ISO-8601 submission timestamp.
    """
    agent_name: str
    score: float
    scenarios_passed: int
    total_scenarios: int
    timestamp: str


class LeaderboardIntegration:
    """Opt-in public leaderboard integration (X15)."""

    def __init__(self) -> None:
        self._entries: list[LeaderboardEntry] = []

    def submit(self, entry: LeaderboardEntry) -> None:
        """Submit an entry to the in-memory leaderboard.

        Args:
            entry: The :class:`LeaderboardEntry` to record.
        """
        self._entries.append(entry)

    def top_n(self, n: int = 10) -> list[LeaderboardEntry]:
        """Return the top *n* entries sorted by score descending.

        Args:
            n: Maximum number of entries to return (default 10).

        Returns:
            Sorted list of :class:`LeaderboardEntry`.
        """
        return sorted(self._entries, key=lambda e: e.score, reverse=True)[:n]

    def to_json(self) -> str:
        """Serialize the leaderboard to a JSON string.

        Returns:
            Indented JSON array of agent/score pairs.
        """
        return json.dumps(
            [{"agent": e.agent_name, "score": e.score} for e in self.top_n()],
            indent=2,
        )


# X16: Pack Registry & Signing (Sigstore) --------------------------------------

class PackSigner:
    """Stub for pack signing via Sigstore (X16)."""

    @staticmethod
    def sign(pack_data: dict[str, Any]) -> dict[str, Any]:
        """Stub: wrap pack data in a Sigstore-style envelope.

        Args:
            pack_data: Arbitrary pack payload dict.

        Returns:
            Dict with keys ``pack`` and ``signature`` (always unverified).
        """
        return {
            "pack": pack_data,
            "signature": {
                "algorithm": "sigstore",
                "verified": False,
                "note": "Sigstore integration requires sigstore-python.",
            },
        }

    @staticmethod
    def verify(signed_pack: dict[str, Any]) -> bool:
        """Stub: verify the signature wrapper.

        Args:
            signed_pack: A pack dict previously produced by :meth:`sign`.

        Returns:
            Always returns the value of ``signature.verified`` (default False).
        """
        return bool(signed_pack.get("signature", {}).get("verified", False))


# X17: Tutorials & Notebooks Library -------------------------------------------

@dataclass
class Tutorial:
    """Describes an EvalForge tutorial or notebook.

    Attributes:
        title: Short identifier for the tutorial.
        description: One-line description.
        notebook_path: File path to the notebook.
        tags: List of categorization tags (e.g. ``"beginner"``).
    """
    title: str
    description: str
    notebook_path: str
    tags: list[str]


class TutorialRegistry:
    """Registry for tutorials and notebooks (X17)."""

    def __init__(self) -> None:
        self._tutorials: list[Tutorial] = [
            Tutorial(
                "quickstart", "Run your first agent evaluation",
                "tutorials/quickstart.ipynb", ["beginner"],
            ),
            Tutorial(
                "custom-scorer", "Write a custom scorer",
                "tutorials/custom-scorer.ipynb", ["intermediate"],
            ),
            Tutorial(
                "ci-pipeline", "Set up EvalForge in CI",
                "tutorials/ci-pipeline.ipynb", ["advanced"],
            ),
        ]

    def list_by_tag(self, tag: str) -> list[Tutorial]:
        """Filter tutorials by a specific tag.

        Args:
            tag: Tag to filter by (e.g. ``"beginner"``).

        Returns:
            List of matching :class:`Tutorial` entries.
        """
        return [t for t in self._tutorials if tag in t.tags]

    def all(self) -> list[Tutorial]:
        """Return every registered tutorial.

        Returns:
            A copy of the internal tutorial list.
        """
        return list(self._tutorials)


# X18: Editor/IDE Integration (VSCode) -----------------------------------------

class VSCodeIntegration:
    """Stub for VSCode extension integration (X18)."""

    @staticmethod
    def generate_tasks_json() -> str:
        """Generate a VS Code ``tasks.json`` snippet for EvalForge commands.

        Returns:
            JSON string with ``run scenarios`` and ``validate pack`` tasks.
        """
        return json.dumps({
            "tasks": [
                {
                    "label": "evalforge: run scenarios",
                    "type": "shell",
                    "command": "evalforge run --pack scenarios/core-launch.yaml",
                    "group": "test",
                },
                {
                    "label": "evalforge: validate pack",
                    "type": "shell",
                    "command": "evalforge validate --pack scenarios/core-launch.yaml --strict",
                    "group": "test",
                },
            ]
        }, indent=2)


# X19: GitHub App PR Gate (Checks API) -----------------------------------------

class GitHubPRGate:
    """Stub for GitHub Checks API PR gating (X19)."""

    @staticmethod
    def generate_check_payload(
        conclusion: str, summary: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate a GitHub Checks API payload for a PR check run.

        Args:
            conclusion: One of ``"success"``, ``"failure"``, ``"neutral"``, etc.
            summary: Human-readable summary for the check output.
            details: Optional structured details to include as check output text.

        Returns:
            A dict suitable for the GitHub Checks API ``POST /repos/.../check-runs``.
        """
        return {
            "name": "EvalForge Agent Evaluation",
            "head_sha": "${{ github.event.pull_request.head.sha }}",
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": "EvalForge Results",
                "summary": summary,
                "text": json.dumps(details or {}, indent=2),
            },
        }


# X20: Flakiness Profiler & Statistical Deltas ---------------------------------

@dataclass
class FlakeProfile:
    """Flakiness analysis for a single scenario.

    Attributes:
        scenario_id: Scenario identifier.
        total_runs: Number of runs analysed.
        flake_rate: Fraction of runs that deviated from the first run.
        score_variance: Variance of scores across runs.
        is_flaky: Boolean flag (True when flake_rate > 0.2).
    """
    scenario_id: str
    total_runs: int
    flake_rate: float
    score_variance: float
    is_flaky: bool


class FlakinessProfiler:
    """Profiles scenario flakiness across multiple runs (X20)."""

    @staticmethod
    def analyze(
        scenario_id: str, scores_by_run: list[float], threshold: float = 0.1
    ) -> FlakeProfile:
        """Analyse score stability across runs.

        Compares each run against the first run; any absolute difference
        exceeding *threshold* counts as a flake.

        Args:
            scenario_id: The scenario being analysed.
            scores_by_run: List of scores from repeated runs.
            threshold: Maximum allowed absolute score deviation (default 0.1).

        Returns:
            A :class:`FlakeProfile`.
        """
        if len(scores_by_run) < 2:
            return FlakeProfile(scenario_id, len(scores_by_run), 0, 0, False)
        flake_count = sum(
            1 for i in range(1, len(scores_by_run))
            if abs(scores_by_run[i] - scores_by_run[0]) > threshold
        )
        flake_rate = flake_count / len(scores_by_run)
        mean = sum(scores_by_run) / len(scores_by_run)
        variance = sum((s - mean) ** 2 for s in scores_by_run) / len(scores_by_run)
        return FlakeProfile(
            scenario_id, len(scores_by_run),
            round(flake_rate, 4), round(variance, 6),
            is_flaky=flake_rate > 0.2,
        )


# X21: A/B Gating and Canarying ------------------------------------------------

@dataclass
class ABResult:
    """Result of an A/B comparison.

    Attributes:
        variant_a: Label for the baseline variant.
        variant_b: Label for the candidate variant.
        improvement: Mean score difference (candidate - baseline).
        confidence: Qualitative confidence (``"low"``, ``"medium"``, ``"high"``).
        recommendation: Decision guidance.
    """
    variant_a: str
    variant_b: str
    improvement: float  # positive = B is better
    confidence: str  # "low", "medium", "high"
    recommendation: str


class ABGate:
    """A/B gating for agent versions (X21)."""

    @staticmethod
    def compare(
        baseline_scores: list[float], candidate_scores: list[float]
    ) -> ABResult:
        """Compare baseline and candidate score distributions.

        Confidence is ``"high"`` when both samples have >= 10 observations.

        Args:
            baseline_scores: Scores from the baseline variant.
            candidate_scores: Scores from the candidate variant.

        Returns:
            An :class:`ABResult` with computed improvement and recommendation.
        """
        if not baseline_scores or not candidate_scores:
            return ABResult("baseline", "candidate", 0, "low", "insufficient data")
        mean_a = sum(baseline_scores) / len(baseline_scores)
        mean_b = sum(candidate_scores) / len(candidate_scores)
        improvement = mean_b - mean_a
        confidence = "medium"
        if len(baseline_scores) >= 10 and len(candidate_scores) >= 10:
            confidence = "high"
        if improvement > 0.05:
            recommendation = "ship candidate"
        elif improvement < -0.05:
            recommendation = "keep baseline"
        else:
            recommendation = "no significant difference"
        return ABResult("baseline", "candidate", round(improvement, 4), confidence, recommendation)

    @staticmethod
    def canary_check(
        canary_scores: list[float], threshold: float = 0.8
    ) -> bool:
        """Check whether a canary deployment passes a minimum score threshold.

        At least 80 % of canary scores must meet or exceed *threshold*.

        Args:
            canary_scores: Scores from the canary deployment.
            threshold: Minimum acceptable score (default 0.8).

        Returns:
            ``True`` if the canary passes.
        """
        if not canary_scores:
            return False
        passed = sum(1 for s in canary_scores if s >= threshold)
        return (passed / len(canary_scores)) >= 0.8


# X23: Distributed Executor (Queue/Workers) ------------------------------------

class DistributedExecutor:
    """Stub for distributed execution via queues (X23)."""

    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []
        self._results: dict[str, Any] = {}

    def submit(self, job_id: str, scenario: dict[str, Any]) -> None:
        """Enqueue a scenario for distributed processing.

        Args:
            job_id: Unique job identifier.
            scenario: Scenario data dict.
        """
        self._jobs.append({"id": job_id, "scenario": scenario, "status": "queued"})

    def process_one(self, worker_fn: Any) -> dict[str, Any] | None:
        """Process the next queued job using a worker function.

        Args:
            worker_fn: A callable that accepts a scenario dict and returns a result.

        Returns:
            The result dict if a job was processed, or ``None`` if the queue is empty.
        """
        for job in self._jobs:
            if job["status"] == "queued":
                job["status"] = "processing"
                try:
                    result = worker_fn(job["scenario"])
                    self._results[job["id"]] = result
                    job["status"] = "completed"
                    return result  # type: ignore[no-any-return]
                except Exception as e:
                    job["status"] = "failed"
                    self._results[job["id"]] = {"error": str(e)}
        return None

    def pending(self) -> int:
        """Return the number of jobs still in the queue.

        Returns:
            Count of jobs with ``status == "queued"``.
        """
        return sum(1 for j in self._jobs if j["status"] == "queued")


# X24: Telemetry Export (Prometheus/Grafana) -----------------------------------

class TelemetryExporter:
    """Stub for Prometheus/Grafana telemetry export (X24)."""

    @staticmethod
    def to_prometheus_metrics(metrics: dict[str, float]) -> str:
        """Render metrics as Prometheus text-format exposition.

        Args:
            metrics: Dict mapping metric names to numeric values.

        Returns:
            A Prometheus-format string with ``# HELP`` and ``# TYPE`` lines.
        """
        lines: list[str] = []
        for name, value in metrics.items():
            safe_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# HELP evalforge_{safe_name} EvalForge metric")
            lines.append(f"# TYPE evalforge_{safe_name} gauge")
            lines.append(f"evalforge_{safe_name} {value}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def build_grafana_dashboard(title: str, metrics: list[str]) -> dict[str, Any]:
        """Generate a Grafana dashboard JSON model for the given metrics.

        Creates one ``stat`` panel per metric name, arranged in a two-column grid.

        Args:
            title: Dashboard title.
            metrics: List of metric names to include as panels.

        Returns:
            A Grafana dashboard dict (schemaVersion 37).
        """
        panels: list[dict[str, Any]] = []
        for i, metric in enumerate(metrics):
            safe = metric.replace(".", "_")
            panels.append({
                "id": i + 1,
                "title": metric,
                "type": "stat",
                "targets": [{"expr": f"evalforge_{safe}"}],
                "gridPos": {"h": 8, "w": 12, "x": (i % 2) * 12, "y": (i // 2) * 8},
            })
        return {
            "title": title,
            "panels": panels,
            "schemaVersion": 37,
        }


# X25: Governance (RBAC/Policy DSL) --------------------------------------------

@dataclass
class Role:
    """A role definition for RBAC.

    Attributes:
        name: Role name (e.g. ``"admin"``).
        permissions: List of permitted action strings.
    """
    name: str
    permissions: list[str]  # "run", "validate", "baseline.save", "admin"


@dataclass
class PolicyDSL:
    """A set of governance policy rules.

    Attributes:
        rules: List of rule dicts (placeholder for future policy-DSL engine).
    """
    rules: list[dict[str, Any]]


class GovernancePolicy:
    """RBAC/Policy DSL for team-level governance (X25)."""

    ROLES: ClassVar[dict[str, Role]] = {
        "viewer": Role("viewer", ["run", "validate"]),
        "developer": Role("developer", ["run", "validate", "baseline.save"]),
        "admin": Role("admin", ["run", "validate", "baseline.save", "admin"]),
    }

    @staticmethod
    def can(role: str, action: str) -> bool:
        """Check whether a role is permitted to perform an action.

        Args:
            role: Role name (e.g. ``"developer"``).
            action: Action string (e.g. ``"baseline.save"``).

        Returns:
            ``True`` if the action is in the role's permission list.
        """
        role_def = GovernancePolicy.ROLES.get(role)
        if not role_def:
            return False
        return action in role_def.permissions

    @staticmethod
    def require_role(role: str, action: str) -> None:
        """Enforce that *role* is allowed to perform *action*; raise otherwise.

        Args:
            role: Role name.
            action: Action string.

        Raises:
            PermissionError: If the role is not permitted.
        """
        if not GovernancePolicy.can(role, action):
            raise PermissionError(f"Role '{role}' cannot perform '{action}'")
