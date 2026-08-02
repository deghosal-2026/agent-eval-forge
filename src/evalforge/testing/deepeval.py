"""DeepEval integration stub for advanced trajectory scoring.

Layer 4: Optional integration with DeepEval for G-Eval, faithfulness, and
contextual relevancy metrics. Falls back to EvalForge built-in scoring if
DeepEval is not installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class DeepEvalIntegration:
    """Integrates DeepEval metrics (faithfulness, G-Eval) into trajectory scoring.

    Wraps the deepeval library behind a lazy-enable pattern so the rest of
    EvalForge does not require deepeval at install time.
    """

    def __init__(self) -> None:
        """Initialise integration in disabled state — call .enable() to activate."""
        self._enabled = False

    def enable(self) -> None:
        """Attempt to import deepeval; raises ImportError if not installed."""
        try:
            import deepeval  # type: ignore[import-not-found]  # noqa: F401
        except ImportError as err:
            raise ImportError(
                "DeepEval is not installed. Install with: pip install deepeval"
            ) from err
        self._enabled = True

    def score_trajectory(
        self, trajectory: list[dict[str, Any]], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Score a full trajectory with DeepEval metrics.

        Args:
            trajectory: Ordered list of trajectory step dicts (not used directly
                by DeepEval — context keys are the primary input).
            context: Dict with keys ``input``, ``output``, ``expected``,
                ``retrieval_context``, and ``conversation_context``.

        Returns:
            Dict with keys ``engine``, ``score``, ``metrics``, ``error``.
        """
        # Return a fallback result when deepeval was never enabled.
        if not self._enabled:
            return {
                "engine": "evalforge",
                "score": None,
                "metrics": {},
                "error": "DeepEval not enabled. Call .enable() first.",
            }
        try:
            from deepeval.metrics import FaithfulnessMetric, GEval  # type: ignore[import-not-found]
            from deepeval.test_case import (  # type: ignore[import-not-found]
                LLMTestCase,
                LLMTestCaseParams,
            )

            results: dict[str, Any] = {}
            test_case = LLMTestCase(
                input=context.get("input", ""),
                actual_output=context.get("output", ""),
                expected_output=context.get("expected", ""),
                retrieval_context=context.get("retrieval_context", []),
                context=context.get("conversation_context", []),
            )
            faithfulness = FaithfulnessMetric()
            faithfulness.measure(test_case)
            results["faithfulness"] = {
                "score": faithfulness.score,
                "reason": faithfulness.reason,
            }

            g_eval = GEval(
                name="trajectory_quality",
                criteria="Evaluate the overall quality of the agent trajectory.",
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
            )
            g_eval.measure(test_case)
            results["g_eval"] = {
                "score": g_eval.score,
                "reason": g_eval.reason,
            }

            return {
                "engine": "deepeval",
                "score": faithfulness.score or g_eval.score,
                "metrics": results,
                "error": None,
            }
        except Exception as exc:
            return {
                "engine": "deepeval",
                "score": None,
                "metrics": {},
                "error": str(exc),
            }

    def to_runtime_callback(self) -> Callable[[dict[str, Any]], None]:
        """Return a callback that forwards runtime events into DeepEval tracing.

        Returns:
            A callable accepting an event dict; safe to use as a LangGraph
            callback or a general-purpose event handler.
        """
        def _callback(event: dict[str, Any]) -> None:
            if not self._enabled:
                return
            try:
                from deepeval.tracing import Tracer  # type: ignore[import-not-found]
                Tracer.trace(event)
            except Exception:  # noqa: S110
                pass

        return _callback
