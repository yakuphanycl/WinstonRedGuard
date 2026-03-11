from devtool_genome.core.catalog import list_tools
from devtool_genome.core.query import search_tools


def test_list_tools_returns_data():
    tools = list_tools()
    assert len(tools) > 0


def test_search_tools_finds_pytest():
    results = search_tools("test")
    assert len(results) > 0
    assert any(tool.name == "pytest" for tool in results)
