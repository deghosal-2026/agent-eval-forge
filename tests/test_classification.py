from __future__ import annotations

from evalforge.classification import AgentClassifier, InfraTags


class TestInfraTags:
    def test_all_tags_defined(self) -> None:
        expected = [
            "needs_gateway",
            "writes_root",
            "needs_db",
            "import_side_effects",
            "needs_gpu",
            "needs_api_key",
            "network_access",
            "filesystem_write",
        ]
        assert set(InfraTags.ALL_TAGS) == set(expected)


class TestAgentClassifier:
    def test_classify_api_key(self) -> None:
        config = {"env": {"OPENAI_API_KEY": "sk-xxx"}}
        tags = AgentClassifier.classify(config)
        assert InfraTags.NEEDS_API_KEY in tags

    def test_classify_network_access(self) -> None:
        config = {"module": "agent", "function": "run", "deps": ["httpx"]}
        tags = AgentClassifier.classify(config)
        assert InfraTags.NETWORK_ACCESS in tags

    def test_classify_db(self) -> None:
        source = "import sqlalchemy\nengine = create_engine(url)"
        tags = AgentClassifier.from_source(source)
        assert InfraTags.NEEDS_DB in tags

    def test_classify_no_tags(self) -> None:
        config = {"module": "simple", "function": "run"}
        tags = AgentClassifier.classify(config)
        assert tags == []

    def test_classify_dedup(self) -> None:
        source = "import httpx\nimport requests\n"
        tags = AgentClassifier.from_source(source)
        assert tags.count(InfraTags.NETWORK_ACCESS) == 1
