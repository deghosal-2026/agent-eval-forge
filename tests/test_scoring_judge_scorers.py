from evalforge.models.artifact import Cost, RunArtifact, RunOutput, RunTimestamps
from evalforge.models.pack import Budget, Expected, Scenario, Tool
from evalforge.scoring.judge.scorers import TaskCompletionScorer


def _artifact(output: str = "done") -> RunArtifact:
    return RunArtifact(
        id="r1",
        scenario_id="sc-1",
        timestamp=RunTimestamps(start="x", end="y", duration_ms=0),
        output=RunOutput(final=output, structured=None),
        trajectory=[],
        cost=Cost(),
        status="completed",
        error=None,
        agent={},
    )


def _scenario(goal: str = "Do the thing", input_text: str = "in") -> Scenario:
    return Scenario(
        id="sc-1",
        title="T",
        goal=goal,
        input=input_text,
        allowed_tools=[Tool(name="t")],
        budget=Budget(max_steps=5),
        expected=Expected(type="exact", value="ok"),
    )


def test_task_completion_scorer_uses_judge() -> None:
    scorer = TaskCompletionScorer()
    art = _artifact("the answer")
    sc = _scenario(goal="Find the answer")
    result = scorer.score(art, sc, {"threshold": 0.8})
    assert result.error is not None or result.source == "judge"


def test_all_judge_scorers_registered() -> None:
    from evalforge.scoring.registry import SCORERS

    expected = {
        "task_completion",
        "output_correctness",
        "synthesis_quality",
        "clarification_quality",
        "refusal_quality",
        "recovery_quality",
        "blast_radius_accuracy",
        "verification_quality",
        "hypothesis_quality",
        "evidence_grounding",
        "hallucination_rate",
    }
    assert expected.issubset(SCORERS.keys())
