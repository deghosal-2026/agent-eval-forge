"""Tests for evalforge.tools.fuzzer."""

from evalforge.models.pack import (
    Budget,
    PackMetadata,
    Scenario,
    ScenarioPack,
    Tool,
)
from evalforge.tools.fuzzer import FuzzConfig, FuzzedScenario, ScenarioFuzzer


class TestFuzzConfig:
    def test_defaults(self) -> None:
        c = FuzzConfig()
        assert c.num_variants == 10
        assert c.mutation_rate == 0.3
        assert c.seed == 42
        assert c.inject_noise is True
        assert c.inject_edge_cases is True
        assert c.inject_boundary is True
        assert c.inject_adversarial is True

    def test_custom_values(self) -> None:
        c = FuzzConfig(
            num_variants=5,
            mutation_rate=0.5,
            seed=99,
            inject_noise=False,
            inject_edge_cases=False,
            inject_boundary=False,
            inject_adversarial=False,
        )
        assert c.num_variants == 5
        assert c.mutation_rate == 0.5
        assert c.seed == 99
        assert c.inject_noise is False
        assert c.inject_edge_cases is False
        assert c.inject_boundary is False
        assert c.inject_adversarial is False


class TestFuzzedScenario:
    def test_creation(self) -> None:
        scenario = Scenario(id="orig", title="T", input="hello")
        fs = FuzzedScenario(
            original_id="orig",
            variant_id="orig-fuzz-noise-0",
            mutation_type="noise",
            scenario=scenario,
        )
        assert fs.original_id == "orig"
        assert fs.variant_id == "orig-fuzz-noise-0"
        assert fs.mutation_type == "noise"
        assert fs.scenario is scenario


def _make_pack(name="test", scenarios=None):
    return ScenarioPack(
        pack=PackMetadata(name=name, version="1.0"), scenarios=scenarios or []
    )


def _make_scenario(sid="s1", input_text="hello world", tools=None, tags=None, budget=None):
    return Scenario(
        id=sid,
        title=f"Title {sid}",
        goal=f"Goal {sid}",
        input=input_text,
        allowed_tools=tools or [],
        tags=tags or [],
        budget=budget,
    )


class TestScenarioFuzzerInit:
    def test_default_config(self) -> None:
        f = ScenarioFuzzer()
        assert f._config.seed == 42

    def test_custom_config(self) -> None:
        cfg = FuzzConfig(seed=123, num_variants=3)
        f = ScenarioFuzzer(cfg)
        assert f._config.seed == 123
        assert f._config.num_variants == 3

    def test_reproducible_seed(self) -> None:
        f1 = ScenarioFuzzer(FuzzConfig(seed=42))
        f2 = ScenarioFuzzer(FuzzConfig(seed=42))
        s = _make_scenario()
        pack1 = _make_pack(scenarios=[s])
        s2 = _make_scenario()
        pack2 = _make_pack(scenarios=[s2])
        result1 = f1.fuzz_pack(pack1)
        result2 = f2.fuzz_pack(pack2)
        assert [r.id for r in result1.scenarios] == [r.id for r in result2.scenarios]


class TestFuzzPack:
    def test_generates_num_variants(self) -> None:
        cfg = FuzzConfig(num_variants=3, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario()
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        assert len(result.scenarios) == 3

    def test_generates_for_multiple_scenarios_up_to_six(self) -> None:
        cfg = FuzzConfig(num_variants=2, seed=42)
        f = ScenarioFuzzer(cfg)
        scenarios = [_make_scenario(sid=f"s{i}") for i in range(7)]
        pack = _make_pack(scenarios=scenarios)
        result = f.fuzz_pack(pack)
        # fuzzer processes scenarios 0-5 (6 scenarios) * 2 variants = 12
        assert len(result.scenarios) == 12

    def test_all_variants_tagged_fuzzed(self) -> None:
        cfg = FuzzConfig(num_variants=2, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario()
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        for scenario in result.scenarios:
            assert "fuzzed" in scenario.tags

    def test_mutation_type_added_to_tags(self) -> None:
        cfg = FuzzConfig(num_variants=2, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario()
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        mutation_types = {"noise", "boundary", "adversarial", "edge"}
        for scenario in result.scenarios:
            assert any(t in mutation_types for t in scenario.tags)

    def test_budget_set_when_none(self) -> None:
        cfg = FuzzConfig(num_variants=1, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(budget=None)
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        for scenario in result.scenarios:
            assert scenario.budget is not None
            assert scenario.budget.max_steps == 5

    def test_budget_max_steps_capped_at_5(self) -> None:
        cfg = FuzzConfig(num_variants=1, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(budget=Budget(max_steps=100))
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        for scenario in result.scenarios:
            assert scenario.budget is not None
            assert scenario.budget.max_steps == 5

    def test_budget_max_steps_none_uses_default_100(self) -> None:
        cfg = FuzzConfig(num_variants=1, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(budget=Budget(max_steps=None))
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        for scenario in result.scenarios:
            assert scenario.budget is not None
            assert scenario.budget.max_steps == 5

    def test_variant_ids_unique(self) -> None:
        cfg = FuzzConfig(num_variants=5, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario()
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        ids = [s.id for s in result.scenarios]
        assert len(ids) == len(set(ids))

    def test_input_modified_for_noise(self) -> None:
        cfg = FuzzConfig(num_variants=10, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(input_text="test")
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        noise_variants = [s for s in result.scenarios if "noise" in s.id]
        assert len(noise_variants) >= 1
        for v in noise_variants:
            assert v.input != "test"

    def test_input_modified_for_boundary(self) -> None:
        cfg = FuzzConfig(num_variants=10, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(input_text="test")
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        boundary_variants = [s for s in result.scenarios if "boundary" in s.id]
        assert len(boundary_variants) >= 1

    def test_original_input_unchanged(self) -> None:
        cfg = FuzzConfig(num_variants=1, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(input_text="original input")
        pack = _make_pack(scenarios=[s])
        f.fuzz_pack(pack)
        assert s.input == "original input"

    def test_edge_case_clears_tools(self) -> None:
        cfg = FuzzConfig(num_variants=10, seed=42, inject_edge_cases=True)
        cfg.inject_noise = False
        cfg.inject_boundary = False
        cfg.inject_adversarial = False
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(tools=[Tool(name="read"), Tool(name="write")])
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        edge_variants = [s for s in result.scenarios if "edge" in s.id]
        assert len(edge_variants) >= 1
        for v in edge_variants:
            assert v.allowed_tools == []
            assert "DO NOT use any tools" in v.input

    def test_disabled_injection_does_not_generate_type(self) -> None:
        cfg = FuzzConfig(
            num_variants=20,
            seed=42,
            inject_noise=False,
            inject_boundary=False,
            inject_adversarial=False,
            inject_edge_cases=True,
        )
        f = ScenarioFuzzer(cfg)
        s = _make_scenario()
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        for scenario in result.scenarios:
            assert "noise" not in scenario.id
            assert "boundary" not in scenario.id
            assert "adversarial" not in scenario.id

    def test_no_scenarios(self) -> None:
        f = ScenarioFuzzer()
        pack = _make_pack(scenarios=[])
        result = f.fuzz_pack(pack)
        assert len(result.scenarios) == 0


class TestFuzzScenario:
    def test_adversarial_variant_generated_when_enabled(self) -> None:
        cfg = FuzzConfig(
            num_variants=50,
            seed=42,
            inject_noise=False,
            inject_boundary=False,
            inject_edge_cases=False,
            inject_adversarial=True,
        )
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(input_text="do something")
        pack = _make_pack(scenarios=[s])
        result = f.fuzz_pack(pack)
        adv_variants = [s for s in result.scenarios if "adv" in s.id]
        assert len(adv_variants) >= 1
        for v in adv_variants:
            assert v.input != "do something"
            assert "do something" in v.input

    def test_original_tags_preserved(self) -> None:
        cfg = FuzzConfig(num_variants=1, seed=42)
        f = ScenarioFuzzer(cfg)
        s = _make_scenario(tags=["important", "math"])
        result = f._fuzz_scenario(s, 0)
        assert "important" in result.scenario.tags
        assert "math" in result.scenario.tags
        assert "fuzzed" in result.scenario.tags
