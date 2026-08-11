"""Benchmark loading and conversion.

Loads external benchmark datasets (SWE-bench, WebArena) and converts them
into EvalForge scenario packs for evaluation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from evalforge.models.pack import (
    Budget,
    Expected,
    Metric,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)

logger = logging.getLogger("evalforge.benchmarks")

# Tool definitions for SWE-bench tasks (code editing and shell execution).
_SWE_BENCH_TOOLS = [
    {"name": "read_file", "description": "Read file contents from the repository"},
    {"name": "write_file", "description": "Write or modify a file in the repository"},
    {"name": "execute_command", "description": "Execute a shell command"},
]

# Tool definitions for WebArena tasks (browser-based web interaction).
_WEBARENA_TOOLS = [
    {"name": "navigate", "description": "Navigate to a URL"},
    {"name": "click", "description": "Click an element on the page"},
    {"name": "type", "description": "Type text into an input field"},
    {"name": "extract", "description": "Extract content from the page"},
]


@dataclass
class BenchmarkTask:
    """A single benchmark task converted to an EvalForge scenario.

    Attributes:
        task_id: Unique identifier for the task.
        category: Benchmark category (e.g. ``"swe-bench"``, ``"webarena"``).
        prompt: The task instruction/prompt text.
        expected: Expected output or evaluation criteria.
        tools: List of tool definitions available to the agent.
        reference_output: Optional reference answer for comparison.
    """

    task_id: str
    category: str
    prompt: str
    expected: dict[str, Any]
    tools: list[dict[str, str]]
    reference_output: str | None = None


class _BenchmarkLoadError(Exception):
    """Raised when a benchmark dataset cannot be parsed."""


class BenchmarkLoader:
    """Loads external benchmarks and converts them to EvalForge scenario packs.

    Supports SWE-bench (JSONL format) and WebArena (JSON array format) natively,
    with conversion to :class:`ScenarioPack` for evaluation.
    """

    def load_swe_bench(self, dataset_path: str | Path) -> list[BenchmarkTask]:
        """Load SWE-bench style tasks from a JSONL file.

        Each line is a JSON object with fields like ``instance_id``, ``repo``,
        ``problem_statement``, ``base_commit``, ``patch``, ``hints_text``,
        ``FAIL_TO_PASS``, and ``PASS_TO_PASS``.

        Args:
            dataset_path: Path to the JSONL file.

        Returns:
            A list of :class:`BenchmarkTask` objects.

        Raises:
            FileNotFoundError: If the dataset file does not exist.
            _BenchmarkLoadError: If JSON parsing fails.
        """
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"SWE-bench dataset not found: {path}")

        tasks: list[BenchmarkTask] = []
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise _BenchmarkLoadError(
                        f"Invalid JSONL at line {line_num} in {path}: {exc}"
                    ) from exc
                tasks.append(self._parse_swe_bench_task(raw, line_num))
        logger.info("Loaded %d SWE-bench tasks from %s", len(tasks), path)
        return tasks

    def load_webarena(self, dataset_path: str | Path) -> list[BenchmarkTask]:
        """Load WebArena style tasks from a JSON file.

        Expects a JSON array of objects with fields like ``task_id``,
        ``intent`` / ``intent_template``, ``sites``, ``start_urls``,
        ``expected``, and ``eval``.

        Args:
            dataset_path: Path to the JSON file.

        Returns:
            A list of :class:`BenchmarkTask` objects.

        Raises:
            FileNotFoundError: If the dataset file does not exist.
            _BenchmarkLoadError: If JSON parsing fails or format is invalid.
        """
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"WebArena dataset not found: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise _BenchmarkLoadError(
                f"Invalid JSON in {path}: {exc}"
            ) from exc

        if not isinstance(raw, list):
            raise _BenchmarkLoadError(
                f"WebArena dataset must be a JSON array, got {type(raw).__name__}"
            )

        tasks: list[BenchmarkTask] = []
        for idx, item in enumerate(raw):
            tasks.append(self._parse_webarena_task(item, idx))
        logger.info("Loaded %d WebArena tasks from %s", len(tasks), path)
        return tasks

    def _parse_swe_bench_task(
        self, raw: dict[str, Any], line_num: int
    ) -> BenchmarkTask:
        """Parse a single SWE-bench JSONL line into a BenchmarkTask.

        Args:
            raw: The parsed JSON object for one task.
            line_num: Line number in the source file (for error messages).

        Returns:
            A :class:`BenchmarkTask` with SWE-bench fields mapped.
        """
        task_id = raw.get("instance_id", f"swe-unknown-{line_num}")
        repo = raw.get("repo", "unknown/repo")
        issue = raw.get("issue", raw.get("problem_statement", ""))
        base_commit = raw.get("base_commit", "")

        context = f"Repository: {repo}\nBase commit: {base_commit}\n\n{issue}"

        expected: dict[str, Any] = {
            "type": "exact",
            "patch": raw.get("patch", ""),
            "repo": repo,
            "base_commit": base_commit,
        }
        if "hints_text" in raw:
            expected["hints_text"] = raw["hints_text"]
        if "FAIL_TO_PASS" in raw:
            expected["fail_to_pass"] = raw["FAIL_TO_PASS"]
        if "PASS_TO_PASS" in raw:
            expected["pass_to_pass"] = raw["PASS_TO_PASS"]

        return BenchmarkTask(
            task_id=task_id,
            category="swe-bench",
            prompt=context,
            expected=expected,
            tools=_SWE_BENCH_TOOLS,
            reference_output=raw.get("patch"),
        )

    def _parse_webarena_task(
        self, raw: dict[str, Any], idx: int
    ) -> BenchmarkTask:
        """Parse a single WebArena JSON object into a BenchmarkTask.

        Args:
            raw: The parsed JSON object for one task.
            idx: Index in the array (for generating fallback IDs).

        Returns:
            A :class:`BenchmarkTask` with WebArena fields mapped.
        """
        task_id = raw.get("task_id", f"wa-unknown-{idx}")
        intent = raw.get("intent", raw.get("intent_template", ""))
        sites = raw.get("sites", [])
        start_urls = raw.get("start_urls", raw.get("start_url", []))

        if isinstance(start_urls, str):
            start_urls = [start_urls]

        prompt_parts = [intent]
        if sites:
            prompt_parts.insert(0, f"Sites: {', '.join(sites)}")
        if start_urls:
            prompt_parts.append(f"Start URL(s): {', '.join(start_urls)}")

        expected: dict[str, Any] = raw.get("expected", {})
        if not isinstance(expected, dict):
            expected = {"value": expected}

        return BenchmarkTask(
            task_id=task_id,
            category="webarena",
            prompt="\n".join(prompt_parts),
            expected=expected,
            tools=_WEBARENA_TOOLS,
            reference_output=raw.get("eval", {}).get("reference_answer")
            if isinstance(raw.get("eval"), dict)
            else None,
        )

    def convert_to_pack(
        self, tasks: list[BenchmarkTask], pack_name: str
    ) -> ScenarioPack:
        """Convert benchmark tasks to an EvalForge scenario pack.

        Validates for duplicate task IDs, sanitizes scenario IDs, builds
        tool lists, expected outputs, and metrics from task data.

        Args:
            tasks: List of benchmark tasks to convert.
            pack_name: Name for the generated pack.

        Returns:
            A :class:`ScenarioPack` ready for evaluation.

        Raises:
            ValueError: If duplicate task IDs are found.
        """
        seen_ids: set[str] = set()
        scenarios: list[Scenario] = []
        for task in tasks:
            if task.task_id in seen_ids:
                raise ValueError(
                    f"Duplicate task id in conversion: {task.task_id}"
                )
            seen_ids.add(task.task_id)

            sanitized_id = self._sanitize_scenario_id(task.task_id)
            tools = [Tool(name=t["name"], description=t.get("description")) for t in task.tools]
            expected = self._build_expected(task)
            metrics = self._build_metrics(task)
            tags = [task.category]

            scenario = Scenario(
                id=sanitized_id,
                title=f"[{task.category}] {task.task_id}",
                goal=task.prompt.split("\n")[0] if task.prompt else task.task_id,
                input=task.prompt,
                allowed_tools=tools,
                expected=expected,
                metrics=metrics,
                tags=tags,
                difficulty="medium",
                budget=Budget(max_steps=20, max_tokens=8192),
            )
            scenarios.append(scenario)

        pack_meta = PackMetadata(
            name=pack_name,
            version="1.0.0",
            description=f"Auto-generated from benchmark tasks ({len(tasks)} scenarios)",
            trust="external",
        )
        return ScenarioPack(pack=pack_meta, scenarios=scenarios)

    def export_pack(
        self,
        tasks: list[BenchmarkTask],
        output_path: str | Path,
        pack_name: str,
    ) -> Path:
        """Export benchmark tasks as a scenario pack YAML file.

        Args:
            tasks: List of benchmark tasks to export.
            output_path: Path for the output YAML file.
            pack_name: Name for the pack.

        Returns:
            The path to the written YAML file.
        """
        pack = self.convert_to_pack(tasks, pack_name)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = pack.model_dump(exclude_none=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
        logger.info("Exported pack %s to %s", pack_name, output_path)
        return output_path

    @staticmethod
    def _sanitize_scenario_id(task_id: str) -> str:
        """Sanitize a task ID for use as a scenario ID.

        Replaces non-alphanumeric characters (except ``_`` and ``-``) with
        hyphens and strips leading/trailing hyphens.

        Args:
            task_id: The raw task ID string.

        Returns:
            A sanitized scenario ID string.
        """
        sanitized = "".join(c if c.isalnum() or c in "_-" else "-" for c in task_id)
        return sanitized.strip("-") or "unknown"

    @staticmethod
    def _build_expected(task: BenchmarkTask) -> Expected:
        """Build an :class:`Expected` object from a benchmark task.

        Supports exact, schema, tool_trace, tool_args, and rubric expected types.

        Args:
            task: The benchmark task to build expected output from.

        Returns:
            An :class:`Expected` object with the appropriate type and value.
        """
        expected = task.expected
        etype = expected.get("type", "exact")
        if etype not in ("exact", "schema", "tool_trace", "rubric", "tool_args"):
            etype = "exact"

        if etype == "exact":
            value = (
                expected.get("value")
                or task.reference_output
                or expected.get("reference_answer", "")
            )
            return Expected(type="exact", value=str(value))

        if etype == "schema":
            return Expected(
                type="schema",
                schema=expected.get("schema"),
                required_fields=expected.get("required_fields"),
            )

        if etype == "tool_trace":
            return Expected(
                type="tool_trace",
                trace=expected.get("trace", []),
                required_tools=expected.get("required_tools"),
            )

        if etype == "tool_args":
            tool = expected.get("tool", expected.get("tool_name"))
            args = expected.get("args", expected.get("tool_args", {}))
            return Expected(type="tool_args", tool=tool, args=args)

        return Expected(
            type="rubric",
            criteria=expected.get("criteria", [expected.get("description", "")]),
        )

    @staticmethod
    def _build_metrics(task: BenchmarkTask) -> dict[str, Metric]:
        """Build default metric configuration for a benchmark task.

        Assigns weights and thresholds based on the task category:
        - SWE-bench: output_correctness, tool_correctness, task_completion
        - WebArena: task_completion, tool_correctness, navigation_efficiency
        - Other: task_completion (full weight)

        Args:
            task: The benchmark task to build metrics for.

        Returns:
            A dict mapping metric names to :class:`Metric` objects.
        """
        metrics: dict[str, Metric] = {}
        if task.category == "swe-bench":
            metrics["output_correctness"] = Metric(weight=0.4, threshold=0.5)
            metrics["tool_correctness"] = Metric(weight=0.3, threshold=0.5)
            metrics["task_completion"] = Metric(weight=0.3, threshold=0.7)
        elif task.category == "webarena":
            metrics["task_completion"] = Metric(weight=0.5, threshold=0.7)
            metrics["tool_correctness"] = Metric(weight=0.2, threshold=0.5)
            metrics["navigation_efficiency"] = Metric(weight=0.3, threshold=0.5)
        else:
            metrics["task_completion"] = Metric(weight=1.0, threshold=0.7)
        return metrics


class BenchmarkRegistry:
    """Registry of known benchmark formats and their loaders.

    Built-in loaders for "swe-bench" and "webarena" are registered
    automatically. Custom loaders can be added via :meth:`register`.
    """

    def __init__(self) -> None:
        """Initialize the registry with built-in benchmark loaders."""
        self._loaders: dict[str, Callable[[str], list[BenchmarkTask]]] = {}
        self._register_builtins()

    def register(self, name: str, loader_fn: Callable[[str], list[BenchmarkTask]]) -> None:
        """Register a custom benchmark loader.

        Args:
            name: The name to register the loader under.
            loader_fn: A callable that takes a dataset path string and
                returns a list of :class:`BenchmarkTask` objects.
        """
        if name in self._loaders:
            logger.warning("Overwriting registered benchmark loader: %s", name)
        self._loaders[name] = loader_fn

    def load(self, name: str, path: str | Path) -> list[BenchmarkTask]:
        """Load a benchmark using a registered loader.

        Args:
            name: The registered benchmark format name.
            path: Path to the dataset file.

        Returns:
            A list of :class:`BenchmarkTask` objects.

        Raises:
            ValueError: If the format name is not registered.
        """
        if name not in self._loaders:
            available = ", ".join(sorted(self._loaders)) or "(none)"
            raise ValueError(
                f"Unknown benchmark format: {name}. Registered: {available}"
            )
        path = str(path)
        return self._loaders[name](path)

    def _register_builtins(self) -> None:
        """Register the built-in SWE-bench and WebArena loaders."""
        loader = BenchmarkLoader()
        self.register("swe-bench", lambda p: loader.load_swe_bench(p))
        self.register("webarena", lambda p: loader.load_webarena(p))
