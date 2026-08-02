from __future__ import annotations

import json
from pathlib import Path

from evalforge.templates.agent_wrapper import AgentWrapperTemplate


class TestAgentWrapperTemplate:
    def test_render_produces_valid_python(self) -> None:
        code = AgentWrapperTemplate.render(
            agent_name="test-agent",
            repo_url="https://github.com/test/repo",
            builder_function="my_module.build_agent",
        )
        assert "def build_agent" in code
        assert "def run" in code
        assert "my_module" in code
        assert "build_agent" in code
        compile(code, "<test>", "exec")

    def test_render_config_produces_valid_json(self) -> None:
        config_str = AgentWrapperTemplate.render_config(
            agent_name="test-agent",
            repo_url="https://github.com/test/repo",
            adapter_type="langgraph",
            setup_commands=["pip install -e ."],
            scenario_packs=["langgraph-core.yaml"],
        )
        config = json.loads(config_str)
        assert config["agent_id"] == "test-agent"
        assert config["adapter_type"] == "langgraph"
        assert config["scenario_packs"] == ["langgraph-core.yaml"]

    def test_save_writes_files(self, tmp_path: Path) -> None:
        code = AgentWrapperTemplate.render(
            "my-agent", "https://github.com/test/repo", "mod.builder"
        )
        config = AgentWrapperTemplate.render_config(
            "my-agent", "https://github.com/test/repo", "langgraph", [], []
        )
        wrapper_path, config_path = AgentWrapperTemplate.save(
            "my-agent", str(tmp_path), code, config
        )
        assert wrapper_path.exists()
        assert config_path.exists()
        assert wrapper_path.suffix == ".py"
        assert config_path.suffix == ".json"

    def test_render_with_dot_notation_builder(self) -> None:
        code = AgentWrapperTemplate.render(
            "agent1", "https://github.com/x/y", "pkg.subpkg.builder_fn"
        )
        assert "from pkg.subpkg import builder_fn" in code
