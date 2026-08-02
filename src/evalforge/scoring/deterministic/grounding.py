"""Deterministic grounding scorers — factual consistency, source citation,
output grounding, and contradiction detection.

These scorers evaluate whether the agent's final output is factually supported
by the tool results it received during execution. They use string-matching
heuristics (not LLM calls) to check:

- :class:`FactualConsistencyScorer` — Are the agent's sentences supported by
  tool result content?
- :class:`SourceCitationScorer` — Does the agent cite tools that actually
  exist in the scenario or trajectory?
- :class:`OutputGroundingScorer` — Can each sentence in the output be traced
  back to a tool result?
- :class:`ContradictionDetectionScorer` — Does the agent's output contradict
  the tool results (e.g. saying "no" when a tool returned "yes")?
"""

from __future__ import annotations

import re
from typing import Any

from evalforge.models.artifact import RunArtifact
from evalforge.models.pack import Scenario
from evalforge.scoring.base import Scorer
from evalforge.scoring.registry import register_scorer
from evalforge.scoring.result import ScoreResult

_CATEGORY = "correctness"


def _extract_output_text(artifact: RunArtifact) -> str:
    """Extract the agent's final text output from a RunArtifact.

    Args:
        artifact: The run artifact to extract from.

    Returns:
        The final output string, or empty string if not set.
    """
    return artifact.output.final or ""


def _extract_tool_results(artifact: RunArtifact) -> list[dict[str, Any]]:
    """Extract all tool_result steps from the trajectory.

    Each result includes the tool name, the structured result, and the
    rendered content text.

    Args:
        artifact: The run artifact whose trajectory to scan.

    Returns:
        List of dicts with keys ``tool``, ``result``, ``content``.
    """
    results: list[dict[str, Any]] = []
    for step in artifact.trajectory or []:
        if step.type == "tool_result" and step.tool:
            results.append(
                {
                    "tool": step.tool,
                    "result": step.result,
                    "content": step.content,
                }
            )
    return results


def _extract_tool_names_from_output(output: str) -> set[str]:
    r"""Extract tool-name references from the agent's output text.

    Uses regex patterns to find tool names in various forms:
    - ``tool_name()`` — function-call syntax
    - ``tool_name tool`` — inline references
    - ``\`tool_name\``` — backtick-delimited references

    Args:
        output: The agent's final output text.

    Returns:
        Set of tool name strings found in the output.
    """
    if not output:
        return set()
    names: set[str] = set()
    patterns = [
        r"\b([a-z_]+)\(\)",
        r"\b([a-z_]+)\s+(?:tool|function|call)",
        r"`([a-z_]+)`",
    ]
    for pattern in patterns:
        names.update(re.findall(pattern, output, re.IGNORECASE))
    return names


def _check_text_in_results(text: str, results: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Check which sentences in the output text are supported by tool results.

    Splits the output into sentences, extracts content words (length > 3),
    and checks whether any tool result contains those words.

    Args:
        text: The agent's output text.
        results: Tool results extracted from the trajectory.

    Returns:
        Tuple of (list of grounded sentences, list of ungrounded sentences).
    """
    found: list[str] = []
    missing: list[str] = []
    sentences = re.split(r"[.!?]+", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
        words = set(sentence.lower().split())
        content_words = {w for w in words if len(w) > 3}
        if not content_words:
            continue
        matched = False
        for tr in results:
            result_text = str(tr.get("result", "")) + " " + str(tr.get("content", ""))
            result_lower = result_text.lower()
            if any(w in result_lower for w in content_words):
                matched = True
                break
        if matched:
            found.append(sentence)
        else:
            missing.append(sentence)
    return found, missing


def _detect_contradictions(
    output: str, results: list[dict[str, Any]]
) -> list[tuple[str, str, str]]:
    """Detect contradictions between agent output and tool results.

    Uses predefined pairs of antonym patterns (e.g. "no"/"yes", "true"/"false").
    If a tool result contains one pattern and the output contains its opposite,
    that is flagged as a contradiction.

    Args:
        output: The agent's final output text.
        results: Tool results extracted from the trajectory.

    Returns:
        List of (tool_name, tool_pattern, output_pattern) tuples for each
        detected contradiction.
    """
    contradictions: list[tuple[str, str, str]] = []
    negation_patterns = [
        (r"\bno\b", r"\byes\b"),
        (r"\btrue\b", r"\bfalse\b"),
        (r"\bcorrect\b", r"\bincorrect\b"),
        (r"\bsuccess\b", r"\bfail"),
        (r"\bpass\b", r"\bfail\b"),
        (r"\bhealthy\b", r"\bunhealthy\b"),
        (r"\bactive\b", r"\binactive\b"),
        (r"\bavailable\b", r"\bunavailable\b"),
        (r"\bexists\b", r"\bnot\s+(?:found|exist)"),
        (r"\bdeployed\b", r"\bnot\s+deployed"),
    ]

    for tr in results:
        result_text = str(tr.get("result", "")).lower()
        for neg_pat, pos_pat in negation_patterns:
            if re.search(neg_pat, result_text):
                if re.search(pos_pat, output.lower()):
                    contradictions.append(
                        (tr.get("tool", "unknown"), neg_pat, pos_pat)
                    )
            elif re.search(pos_pat, result_text):
                if re.search(neg_pat, output.lower()):
                    contradictions.append(
                        (tr.get("tool", "unknown"), pos_pat, neg_pat)
                    )
    return contradictions


@register_scorer
class FactualConsistencyScorer(Scorer):
    """Score the factual consistency of the agent's output against tool results.

    Splits the output into sentences and checks whether the key content words
    in each sentence appear in any tool result. The score is the fraction of
    sentences that are grounded in tool results.

    Returns a pass (score=1.0) when there is insufficient data to evaluate
    (no output or no tool results).

    Attributes:
        name: ``"factual_consistency"``
        category: ``"correctness"``
    """
    name = "factual_consistency"
    category = _CATEGORY

    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult:
        output = _extract_output_text(artifact)
        tool_results = _extract_tool_results(artifact)

        if not output or not tool_results:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={"note": "insufficient data to assess factual consistency"},
                source="deterministic",
                error=None,
            )

        found, missing = _check_text_in_results(output, tool_results)
        total = len(found) + len(missing) or 1
        score = len(found) / total
        threshold = metric_config.get("threshold", 0.8)
        passed = score >= threshold

        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=passed,
            category=self.category,
            blocking=False,
            detail={
                "sentences_evaluated": total,
                "sentences_grounded": len(found),
                "sentences_ungrounded": len(missing),
                "ungrounded_samples": missing[:5],
            },
            source="deterministic",
            error=None,
        )


@register_scorer
class SourceCitationScorer(Scorer):
    """Score whether the agent's citations reference valid, known tools.

    Extracts tool-like references from the output and checks each against the
    set of allowed and actually-called tools. The score is the fraction of
    references that are valid. If no references are found, returns a neutral
    score of 0.5 (neither pass nor fail by default).

    Attributes:
        name: ``"source_citation"``
        category: ``"correctness"``
    """
    name = "source_citation"
    category = _CATEGORY

    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult:
        output = _extract_output_text(artifact)
        called_tools = {
            step.tool
            for step in artifact.trajectory or []
            if step.type == "tool_call" and step.tool
        }
        allowed_tools = {t.name for t in scenario.allowed_tools or []}
        referenced_tools = _extract_tool_names_from_output(output)

        if not output:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={"note": "empty output, nothing to cite"},
                source="deterministic",
                error=None,
            )

        valid_tools = allowed_tools | called_tools
        valid_citations = referenced_tools & valid_tools
        invalid_citations = referenced_tools - valid_tools

        if not referenced_tools:
            score = 0.5
        else:
            score = len(valid_citations) / len(referenced_tools)

        threshold = metric_config.get("threshold", 0.5)
        passed = score >= threshold

        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=passed,
            category=self.category,
            blocking=False,
            detail={
                "referenced_tools": sorted(referenced_tools),
                "valid_citations": sorted(valid_citations),
                "invalid_citations": sorted(invalid_citations),
            },
            source="deterministic",
            error=None,
        )


@register_scorer
class OutputGroundingScorer(Scorer):
    """Score how well the agent's output is grounded in tool result data.

    Each sentence in the output is checked for key content words that appear
    in tool result text. The score is the fraction of grounded sentences.

    Returns a failing score (0.0) if the agent produced output without making
    any tool calls (ungrounded output). Returns a passing score (1.0) for
    empty output or output with no evaluable sentences.

    Attributes:
        name: ``"output_grounding"``
        category: ``"correctness"``
    """
    name = "output_grounding"
    category = _CATEGORY

    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult:
        output = _extract_output_text(artifact)
        tool_results = _extract_tool_results(artifact)

        if not output:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={"note": "empty output"},
                source="deterministic",
                error=None,
            )

        if not tool_results:
            return ScoreResult(
                metric=self.name,
                score=0.0,
                threshold=1.0,
                passed=False,
                category=self.category,
                blocking=False,
                detail={
                    "note": "no tool results to ground output against",
                    "violations": ["output produced without any tool calls"],
                },
                source="deterministic",
                error=None,
            )

        result_text = " ".join(
            str(tr.get("result", "")) + " " + str(tr.get("content", ""))
            for tr in tool_results
        ).lower()

        sentences = [s.strip() for s in re.split(r"[.!?]+", output) if len(s.strip()) >= 10]
        if not sentences:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={"note": "no evaluable sentences in output"},
                source="deterministic",
                error=None,
            )

        grounded_count = 0
        ungrounded: list[str] = []
        for sentence in sentences:
            words = set(sentence.lower().split())
            content_words = [w for w in words if len(w) > 3]
            if not content_words:
                grounded_count += 1
                continue
            if any(w in result_text for w in content_words):
                grounded_count += 1
            else:
                ungrounded.append(sentence)

        score = grounded_count / len(sentences)
        threshold = metric_config.get("threshold", 0.6)
        passed = score >= threshold

        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=passed,
            category=self.category,
            blocking=False,
            detail={
                "sentences_total": len(sentences),
                "sentences_grounded": grounded_count,
                "sentences_ungrounded": len(ungrounded),
                "ungrounded_samples": ungrounded[:5],
            },
            source="deterministic",
            error=None,
        )


@register_scorer
class ContradictionDetectionScorer(Scorer):
    """Score whether the agent's output contradicts tool result data.

    Uses antonym-pair pattern matching to detect contradictions (e.g. the
    tool returned "healthy" but the output says "unhealthy"). Each detected
    contradiction reduces the score by 0.25. The score is clamped to [0, 1].

    Returns a passing score (1.0) when there is insufficient data to evaluate.

    Attributes:
        name: ``"contradiction_detection"``
        category: ``"correctness"``
    """
    name = "contradiction_detection"
    category = _CATEGORY

    def score(
        self,
        artifact: RunArtifact,
        scenario: Scenario,
        metric_config: dict[str, Any],
    ) -> ScoreResult:
        output = _extract_output_text(artifact)
        tool_results = _extract_tool_results(artifact)

        if not output or not tool_results:
            return ScoreResult(
                metric=self.name,
                score=1.0,
                threshold=1.0,
                passed=True,
                category=self.category,
                blocking=False,
                detail={"note": "insufficient data to detect contradictions"},
                source="deterministic",
                error=None,
            )

        contradictions = _detect_contradictions(output, tool_results)
        violation_count = len(contradictions)

        if violation_count == 0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - violation_count * 0.25)

        threshold = metric_config.get("threshold", 0.8)
        passed = score >= threshold

        return ScoreResult(
            metric=self.name,
            score=score,
            threshold=threshold,
            passed=passed,
            category=self.category,
            blocking=False,
            detail={
                "contradictions_found": violation_count,
                "contradiction_details": [
                    {"tool": c[0], "tool_says": c[1], "output_says": c[2]}
                    for c in contradictions
                ],
            },
            source="deterministic",
            error=None,
        )
