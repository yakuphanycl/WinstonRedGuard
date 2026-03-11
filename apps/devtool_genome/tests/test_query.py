from devtool_genome.core.query import search_tools


def test_search_tools_finds_python_related_tools() -> None:
    results = search_tools("python")

    names = [tool.name for tool in results]

    assert "pytest" in names
    assert "ruff" in names


def test_search_tools_returns_empty_for_unknown_query() -> None:
    results = search_tools("totally-unknown-tool-xyz")

    assert results == []