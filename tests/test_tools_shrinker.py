"""Tests for evalforge.tools.shrinker."""

from __future__ import annotations

from evalforge.tools.shrinker import MinimizeResult, ReproMinimizer


class TestMinimizeResult:
    def test_instantiation_all_fields(self) -> None:
        result = MinimizeResult(
            original_input="hello world",
            minimized_input="hel",
            original_tool_count=5,
            minimized_tool_count=2,
            iterations=10,
            reduction_pct=70.0,
            still_fails=True,
            failure_signature="scenario-1",
        )
        assert result.original_input == "hello world"
        assert result.minimized_input == "hel"
        assert result.original_tool_count == 5
        assert result.minimized_tool_count == 2
        assert result.iterations == 10
        assert result.reduction_pct == 70.0
        assert result.still_fails is True
        assert result.failure_signature == "scenario-1"

    def test_default_values(self) -> None:
        result = MinimizeResult(
            original_input="",
            minimized_input="",
            original_tool_count=0,
            minimized_tool_count=0,
            iterations=0,
            reduction_pct=0.0,
            still_fails=False,
            failure_signature="",
        )
        assert result.original_input == ""
        assert result.minimized_input == ""
        assert result.original_tool_count == 0
        assert result.minimized_tool_count == 0
        assert result.iterations == 0
        assert result.reduction_pct == 0.0
        assert result.still_fails is False
        assert result.failure_signature == ""


class TestReproMinimizerConstants:
    def test_max_iterations(self) -> None:
        assert ReproMinimizer.MAX_ITERATIONS == 50

    def test_min_input_length(self) -> None:
        assert ReproMinimizer.MIN_INPUT_LENGTH == 3


class TestReproMinimizerInit:
    def test_result_starts_none(self) -> None:
        m = ReproMinimizer()
        assert m._result is None


class TestHalveInput:
    def test_halve_long_string(self) -> None:
        assert ReproMinimizer._halve_input("abcdefgh") == "abcd"

    def test_halve_at_min_length_boundary(self) -> None:
        assert ReproMinimizer._halve_input("abc") == "abc"

    def test_halve_below_min_length(self) -> None:
        assert ReproMinimizer._halve_input("ab") == "ab"

    def test_halve_empty_string(self) -> None:
        assert ReproMinimizer._halve_input("") == ""

    def test_halve_odd_length(self) -> None:
        assert ReproMinimizer._halve_input("abcde") == "ab"

    def test_halve_exactly_min_length(self) -> None:
        assert ReproMinimizer._halve_input("xyz") == "xyz"


class TestShrinkSentence:
    def test_multi_line_drops_after_first(self) -> None:
        assert ReproMinimizer._shrink_sentence("hello\nworld\nfoo") == "hello"

    def test_two_lines_drops_second(self) -> None:
        assert ReproMinimizer._shrink_sentence("first\nsecond") == "first"

    def test_single_line_halves_words(self) -> None:
        assert ReproMinimizer._shrink_sentence("one two three four") == "one two"

    def test_single_line_odd_words(self) -> None:
        assert ReproMinimizer._shrink_sentence("one two three") == "one"

    def test_single_word_unchanged(self) -> None:
        assert ReproMinimizer._shrink_sentence("hello") == "hello"

    def test_empty_string_unchanged(self) -> None:
        assert ReproMinimizer._shrink_sentence("") == ""

    def test_multi_line_single_word_per_line(self) -> None:
        assert ReproMinimizer._shrink_sentence("a\nb") == "a"


class TestMinimizeEdgeCases:
    def test_empty_input_and_tools(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.original_input == ""
        assert result.minimized_input == ""
        assert result.original_tool_count == 0
        assert result.minimized_tool_count == 0
        assert result.iterations == 0
        assert result.reduction_pct == 0.0
        assert result.still_fails is True
        assert result.failure_signature == ""

    def test_empty_input_single_tool_no_shrink(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "", "allowed_tools": ["tool_a"]}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.original_input == ""
        assert result.minimized_input == ""
        assert result.original_tool_count == 1
        assert result.minimized_tool_count == 1
        assert result.iterations == 0
        assert result.reduction_pct == 0.0

    def test_reduction_pct_zero_for_empty_original(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.reduction_pct == 0.0


class TestMinimizeInputHalving:
    def test_halve_input_checker_accepts(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abcdefghijklmnop", "allowed_tools": []}
        def checker(d):
            return len(d["input"]) >= 3
        result = m.minimize(scenario, checker)
        assert result.minimized_input == "abcd"
        assert result.iterations >= 1

    def test_halve_input_checker_rejects_then_falls_back(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abcdefghijklmnop", "allowed_tools": []}
        calls: list[str] = []
        accept_once = [True]

        def checker(d: dict) -> bool:
            calls.append(d["input"])
            if accept_once[0] and d["input"] == "abcdefgh":
                accept_once[0] = False
                return True
            return False

        result = m.minimize(scenario, checker)
        assert result.iterations >= 1

    def test_halve_input_checker_raises_exception(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abcdefgh", "allowed_tools": []}
        def checker(d):
            return (_ for _ in ()).throw(RuntimeError("boom"))
        result = m.minimize(scenario, checker)
        assert result.original_input == "abcdefgh"
        assert result.iterations >= 1
        assert result.minimized_input == "abcdefgh"


class TestMinimizeSentenceShrink:
    def test_shrink_sentence_after_halving_fails(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello\nworld\nfoo\nbar this is more text for length padding",
            "allowed_tools": [],
        }
        def checker(d):
            return d["input"].startswith("hello")
        result = m.minimize(scenario, checker)
        assert "hello" in result.minimized_input

    def test_shrink_sentence_checker_raises(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello\nworld\ngoodbye", "allowed_tools": []}
        def checker(d):
            return (_ for _ in ()).throw(RuntimeError("boom"))
        result = m.minimize(scenario, checker)
        assert result.original_input == "hello\nworld\ngoodbye"
        assert result.iterations >= 1


class TestMinimizeToolRemoval:
    def test_remove_tool_with_checker_accepting(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1", "t2", "t3"],
        }

        def checker(d: dict) -> bool:
            return True

        result = m.minimize(scenario, checker)
        assert result.original_tool_count == 3
        assert result.minimized_tool_count <= 2
        assert result.iterations >= 1

    def test_remove_tool_checker_rejects(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1", "t2"],
        }
        def checker(d):
            return len(d["allowed_tools"]) == 2
        result = m.minimize(scenario, checker)
        assert result.minimized_tool_count == 2
        assert result.iterations >= 1

    def test_remove_tool_checker_raises(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1", "t2"],
        }
        def checker(d):
            return (_ for _ in ()).throw(RuntimeError("boom"))
        result = m.minimize(scenario, checker)
        assert result.minimized_tool_count == 2

    def test_single_tool_no_removal_attempted(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1"],
        }
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.original_tool_count == 1
        assert result.minimized_tool_count == 1

    def test_remove_tool_iterates_multiple(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1", "t2", "t3", "t4"],
        }

        def checker(d: dict) -> bool:
            return True

        result = m.minimize(scenario, checker)
        assert result.original_tool_count == 4
        assert result.minimized_tool_count == 3

    def test_remove_tool_only_some_removable(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world test",
            "allowed_tools": ["t1", "t2", "t3"],
        }

        def checker(d: dict) -> bool:
            return "t1" not in d["allowed_tools"] or len(d["allowed_tools"]) >= 2

        result = m.minimize(scenario, checker)
        assert "t1" in result.minimized_input is False or result.minimized_tool_count >= 2
        assert result.iterations >= 1


class TestMinimizeStillFails:
    def test_still_fails_true(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.still_fails is True

    def test_still_fails_false(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello", "allowed_tools": []}
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.still_fails is False

    def test_still_fails_checker_raises(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello", "allowed_tools": []}
        def checker(d):
            return (_ for _ in ()).throw(RuntimeError("boom"))
        result = m.minimize(scenario, checker)
        assert result.still_fails is False


class TestMinimizeFailureSignature:
    def test_failure_signature_from_scenario_id(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello", "allowed_tools": [], "id": "s-42"}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.failure_signature == "s-42"

    def test_failure_signature_empty_when_no_id(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hello", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.failure_signature == ""


class TestMinimizeReductionPct:
    def test_reduction_pct_full_reduction(self) -> None:
        """Reduction where input is fully halved; pct should be >= 0."""
        m = ReproMinimizer()
        scenario = {"input": "abcdefghijklmnop", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.reduction_pct >= 0.0
        assert isinstance(result.reduction_pct, float)

    def test_reduction_pct_no_reduction(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "ab", "allowed_tools": []}
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.reduction_pct == 0.0

    def test_reduction_pct_calculation_accuracy(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abcdefgh", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        expected = round((1.0 - len(result.minimized_input) / len(result.original_input)) * 100, 1)
        assert result.reduction_pct == expected


class TestMinimizeIterationCount:
    def test_iterations_incremented_on_input_shrink(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abcdefghijklmnopqrstuvwxyz", "allowed_tools": []}
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.iterations >= 2

    def test_iterations_not_incremented_when_no_change(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "ab", "allowed_tools": []}
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.iterations == 0

    def test_iterations_incremented_on_tool_removal(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello",
            "allowed_tools": ["t1", "t2", "t3"],
        }
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.iterations >= 1


class TestMinimizeMaxIterations:
    def test_max_iterations_respected(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "x" * 1000,
            "allowed_tools": ["t1", "t2"],
        }
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.iterations <= ReproMinimizer.MAX_ITERATIONS

    def test_break_after_tool_shrink_no_input_change(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "hello world",
            "allowed_tools": ["t1", "t2", "t3"],
        }
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.minimized_tool_count == 3
        assert result.iterations == 4


class TestMinimizeCombined:
    def test_input_and_tool_shrink_combined(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "allowed_tools": ["a", "b", "c", "d", "e"],
        }
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.minimized_tool_count <= 5
        assert len(result.minimized_input) <= len(result.original_input)
        assert result.iterations >= 1

    def test_scenario_data_preserved_beyond_input_and_tools(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "abcdefgh",
            "allowed_tools": ["t1", "t2"],
            "extra_field": "preserved",
        }
        def checker(d):
            return d.get("extra_field") == "preserved"
        result = m.minimize(scenario, checker)
        assert result.still_fails is True

    def test_minimize_result_fields_are_consistent(self) -> None:
        m = ReproMinimizer()
        scenario = {
            "input": "abcdefgh",
            "allowed_tools": ["t1", "t2", "t3"],
            "id": "sc-1",
        }
        def checker(d):
            return True
        result = m.minimize(scenario, checker)
        assert result.original_input == scenario["input"]
        assert result.original_tool_count == len(scenario["allowed_tools"])
        assert result.failure_signature == scenario["id"]


class TestMinimizeNoShrinkPossible:
    def test_input_at_min_length_no_shrink_possible(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "abc", "allowed_tools": []}
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.minimized_input == "abc"
        assert result.iterations == 0
        assert result.reduction_pct == 0.0

    def test_short_input_single_tool_no_shrink(self) -> None:
        m = ReproMinimizer()
        scenario = {"input": "hi", "allowed_tools": ["tool"]}
        def checker(d):
            return False
        result = m.minimize(scenario, checker)
        assert result.minimized_input == "hi"
        assert result.minimized_tool_count == 1
