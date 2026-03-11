from devtool_genome.core.catalog import list_tools


def test_list_tools_returns_records() -> None:
    tools = list_tools()

    assert len(tools) >= 2
    assert any(tool.name == "pytest" for tool in tools)
    assert any(tool.name == "ruff" for tool in tools)