"""Test file used by test_pytest_plugin to verify fixtures resolve with CLI opts."""
pytest_plugins = ["evalforge.pytest_plugin"]


def test_resolve(agent_config, scenario_pack):
    assert agent_config["type"] == "python"
    assert scenario_pack is not None
