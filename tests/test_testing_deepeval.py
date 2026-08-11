"""Tests for ``evalforge.testing.deepeval`` — DeepEval integration stub."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from evalforge.testing.deepeval import DeepEvalIntegration


def _make_mock_module(name: str, **attrs: object) -> ModuleType:
    mod = ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


def _install_deepeval_mocks(**metrics_attrs: object) -> dict[str, ModuleType]:
    mock_faithfulness = MagicMock()
    mock_faithfulness.score = 0.85
    mock_faithfulness.reason = "High faithfulness"
    mock_geval = MagicMock()
    mock_geval.score = 0.90
    mock_geval.reason = "Good trajectory"
    mock_faithfulness_class = MagicMock(return_value=mock_faithfulness)
    mock_geval_class = MagicMock(return_value=mock_geval)

    if metrics_attrs:
        for k, v in metrics_attrs.items():
            if k == "faithfulness_score":
                mock_faithfulness.score = v
            elif k == "faithfulness_reason":
                mock_faithfulness.reason = v
            elif k == "geval_score":
                mock_geval.score = v
            elif k == "geval_reason":
                mock_geval.reason = v

    mock_llm_test_case_class = MagicMock()
    mock_llm_test_case_params = ModuleType("deepeval.test_case.LLMTestCaseParams")
    mock_llm_test_case_params.INPUT = "input"
    mock_llm_test_case_params.ACTUAL_OUTPUT = "actual_output"

    mock_metrics_mod = _make_mock_module(
        "deepeval.metrics",
        FaithfulnessMetric=mock_faithfulness_class,
        GEval=mock_geval_class,
    )
    mock_test_case_mod = _make_mock_module(
        "deepeval.test_case",
        LLMTestCase=mock_llm_test_case_class,
        LLMTestCaseParams=mock_llm_test_case_params,
    )
    mock_deepeval = _make_mock_module("deepeval")

    return {
        "deepeval": mock_deepeval,
        "deepeval.metrics": mock_metrics_mod,
        "deepeval.test_case": mock_test_case_mod,
    }


class TestDeepEvalIntegrationInit:
    """Tests for DeepEvalIntegration.__init__."""

    def test_initial_state_disabled(self) -> None:
        integration = DeepEvalIntegration()
        assert integration._enabled is False


class TestDeepEvalIntegrationEnable:
    """Tests for DeepEvalIntegration.enable."""

    def test_enable_when_deepeval_installed(self) -> None:
        integration = DeepEvalIntegration()
        with patch.dict(sys.modules, {"deepeval": MagicMock()}):
            integration.enable()
        assert integration._enabled is True

    def test_enable_raises_import_error_when_not_installed(self) -> None:
        integration = DeepEvalIntegration()
        with patch.dict(sys.modules, {}):
            sys.modules.pop("deepeval", None)
            with pytest.raises(ImportError, match="DeepEval is not installed"):
                integration.enable()
        assert integration._enabled is False


class TestDeepEvalIntegrationScoreTrajectory:
    """Tests for DeepEvalIntegration.score_trajectory."""

    def test_score_returns_fallback_when_not_enabled(self) -> None:
        integration = DeepEvalIntegration()
        result = integration.score_trajectory([], {})
        assert result["engine"] == "evalforge"
        assert result["score"] is None
        assert result["metrics"] == {}
        assert "DeepEval not enabled" in result["error"]

    def test_score_returns_metrics_when_enabled(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mocks = _install_deepeval_mocks()
        with patch.dict(sys.modules, mocks):
            context = {
                "input": "test input",
                "output": "test output",
                "expected": "expected output",
                "retrieval_context": ["doc1"],
                "conversation_context": ["ctx1"],
            }
            result = integration.score_trajectory([{"step": 1}], context)

        assert result["engine"] == "deepeval"
        assert result["score"] == 0.85
        assert result["error"] is None
        assert result["metrics"]["faithfulness"]["score"] == 0.85
        assert result["metrics"]["faithfulness"]["reason"] == "High faithfulness"
        assert result["metrics"]["g_eval"]["score"] == 0.90
        assert result["metrics"]["g_eval"]["reason"] == "Good trajectory"

    def test_score_handles_exception_gracefully(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mock_deepeval = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.FaithfulnessMetric = MagicMock(side_effect=ValueError("API error"))
        mock_metrics.GEval = MagicMock()
        mock_test_case = MagicMock()
        mock_test_case.LLMTestCaseParams = MagicMock()
        mock_test_case.LLMTestCaseParams.INPUT = "input"
        _make_mock_module("deepeval")
        mocks = {
            "deepeval": mock_deepeval,
            "deepeval.metrics": mock_metrics,
            "deepeval.test_case": mock_test_case,
        }

        with patch.dict(sys.modules, mocks):
            result = integration.score_trajectory([], {"input": "hi"})

        assert result["engine"] == "deepeval"
        assert result["score"] is None
        assert result["metrics"] == {}
        assert "API error" in result["error"]

    def test_score_uses_g_eval_when_faithfulness_is_none(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mocks = _install_deepeval_mocks(faithfulness_score=None)
        with patch.dict(sys.modules, mocks):
            result = integration.score_trajectory([], {})

        assert result["score"] == 0.90

    def test_score_default_empty_context_values(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mocks = _install_deepeval_mocks()
        with patch.dict(sys.modules, mocks):
            integration.score_trajectory([], {})

        llm_test_case_class = mocks["deepeval.test_case"].LLMTestCase
        call_kwargs = llm_test_case_class.call_args.kwargs
        assert call_kwargs["input"] == ""
        assert call_kwargs["actual_output"] == ""
        assert call_kwargs["expected_output"] == ""
        assert call_kwargs["retrieval_context"] == []
        assert call_kwargs["context"] == []


class TestDeepEvalIntegrationToRuntimeCallback:
    """Tests for DeepEvalIntegration.to_runtime_callback."""

    def test_callback_returns_none_when_not_enabled(self) -> None:
        integration = DeepEvalIntegration()
        callback = integration.to_runtime_callback()
        result = callback({"event": "test"})
        assert result is None

    def test_callback_traces_when_enabled(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mock_tracer = MagicMock()
        mock_tracing = _make_mock_module("deepeval.tracing", Tracer=mock_tracer)
        mock_deepeval = _make_mock_module("deepeval", tracing=mock_tracing)

        with patch.dict(sys.modules, {"deepeval": mock_deepeval, "deepeval.tracing": mock_tracing}):
            callback = integration.to_runtime_callback()
            callback({"event": "test_event"})

        mock_tracer.trace.assert_called_once_with({"event": "test_event"})

    def test_callback_silently_swallows_exceptions(self) -> None:
        integration = DeepEvalIntegration()
        integration._enabled = True

        mock_tracer = MagicMock()
        mock_tracer.trace.side_effect = RuntimeError("Trace failed")
        mock_tracing = _make_mock_module("deepeval.tracing", Tracer=mock_tracer)
        mock_deepeval = _make_mock_module("deepeval", tracing=mock_tracing)

        with patch.dict(sys.modules, {"deepeval": mock_deepeval, "deepeval.tracing": mock_tracing}):
            callback = integration.to_runtime_callback()
            result = callback({"event": "test"})

        assert result is None
        mock_tracer.trace.assert_called_once()
